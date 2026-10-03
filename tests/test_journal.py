"""The Foresight Journal: the chain catches edits, forecasts resolve in their three modes, and the shadow book books the contract's exits."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "ops"))
import journal as J    # noqa: E402
import paper as P      # noqa: E402

T0 = 1_791_000_000.0


@pytest.fixture
def jr(tmp_path, monkeypatch):
    for name in ("BELIEFS", "PREDS", "SCORES", "LESSONS", "EVENTS", "PAPER", "SHADOW", "PATHS", "SHADOW_STATE", "REPORT", "EXC", "EXC_STATE", "SOL_USD", "BLIND", "MK_WAIT"):
        monkeypatch.setattr(J, name, str(tmp_path / (name.lower() + ".jsonl")))
    monkeypatch.setattr(J, "CHAINED", (J.BELIEFS, J.PREDS, J.SCORES, J.LESSONS))
    J.belief("B1", "a pass wins", 0.3, "seed", "x", k="sh_wins_pass", n="sh_n_pass")
    J.belief("B3", "a fail wins", 0.1, "seed", "x", k="sh_wins_fail", n="sh_n_fail")
    return J


def _event(jr, eid, mint, passed, price=1.0, t=T0):
    with open(jr.EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": eid, "feed": "truth", "kind": "post", "person": "p", "ts": "2026-10-03T00:00:00Z",
                            "screen": [{"mint": mint, "symbol": "S", "pass": passed, "why": [] if passed else ["liq 1 < 20000"],
                                        "snap": {"price": price, "liq": 50_000}, "t_screened": t}]}) + "\n")


def test_chain_detects_an_edit(jr):
    jr.predict("c", "closed", "ge", 40, 0.8, "2026-12-31", "b", beliefs=["B1"])
    assert jr.verify() == []
    rows = [json.loads(l) for l in open(jr.PREDS)]
    rows[0]["confidence"] = 0.2   # hindsight
    open(jr.PREDS, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
    assert jr.verify()


def test_resolution_modes_and_scores(jr):
    early = jr.predict("reaches 2", "closed", "ge", 2, 0.9, "2026-12-31", "b", when="early")
    late = jr.predict("stays under 5", "closed", "lt", 5, 0.2, "2026-10-05", "b")
    at40 = jr.predict("wr", "win_rate_at_40", "in", [0.1, 0.4], 0.8, "2026-10-05", "b", when="defined")
    m = {"closed": 3, "win_rate_at_40": None}
    assert [s["pred_id"] for s in jr.resolve_due(m, "2026-10-04")] == [early["pred_id"]]
    out = {s["pred_id"]: s for s in jr.resolve_due(m, "2026-10-06")}
    assert out[late["pred_id"]]["outcome"] == 1 and out[late["pred_id"]]["brier"] == 0.64
    assert out[at40["pred_id"]]["outcome"] is None           # never defined: void, not a miss
    assert {s["pred_id"] for s in jr.owed()} == {late["pred_id"], at40["pred_id"]}   # 2.3 bits of surprise, and a void
    jr.lesson("under 5 held", "trade rate overestimated", "model", late["pred_id"], "B1", 0.2, "halve the day-one rate")
    assert jr.current_beliefs()["B1"]["p"] == 0.2 and jr.current_beliefs()["B1"]["seed_p"] == 0.3
    assert {s["pred_id"] for s in jr.owed()} == {at40["pred_id"]} and jr.verify() == []


def test_shadow_books_contract_exits_and_keeps_watching_after_the_stop(jr):
    _event(jr, "e1", "STOPPED", True)
    _event(jr, "e2", "DEAD", False)
    _event(jr, "e3", "STOPPED", True, t=T0 + 60)    # same mint again inside 24 h: a repeat, kept but not counted
    q = lambda a, b: {"STOPPED": (a, 50_000), "DEAD": (b, 40_000)}   # noqa: E731
    jr.shadow_tick(T0 + 300, q(0.95, 1.0))
    jr.shadow_tick(T0 + 600, q(0.85, 1.0))           # -15 %: stop, booked -15 % less fees
    jr.shadow_tick(T0 + 3600, q(1.6, 1.0))           # and then it ran: stop regret
    assert jr.shadow_tick(T0 + P.TIME_STOP_S + 30, q(1.2, 1.0)) == 1   # e3 opened 60 s later, still inside its 24 h
    rows = {r["key"]: r for r in map(json.loads, open(jr.SHADOW))}
    s, d = rows["e1|STOPPED"], rows["e2|DEAD"]
    assert s["net_sol"] == -0.175 and s["exits"] == ["stop"] and s["after_stop_peak_pct"] == 0.6 and s["peak_pct"] == 0.6
    assert d["net_sol"] == -0.025 and d["exits"] == ["stale"] and d["win"] == 0   # flat at the 15-minute look: cut
    assert s["forecast"]["p_win"] == 0.3 and d["forecast"]["p_win"] == 0.1 and s["brier"] == 0.09
    st = jr.shadow_stats(list(rows.values()))
    assert (st["sh_n_pass"], st["sh_n_fail"], st["sh_wins_pass"]) == (1, 1, 0) and st["sh_fail_minus_pass"] is None
    assert json.load(open(jr.SHADOW_STATE))["e3|STOPPED"]["repeat"] == 1


def test_a_superseded_leg_voids_its_forecasts_without_owing_lessons(jr, monkeypatch):
    old = jr.predict("c", "closed", "ge", 40, 0.8, "2026-12-31", "b")
    monkeypatch.setattr(jr, "leg", lambda: "RI-99")
    new = jr.predict("c again", "closed", "ge", 40, 0.8, "2026-12-31", "b")
    out = jr.resolve_due({"closed": 1}, "2026-10-04")
    assert [(s["pred_id"], s["outcome"], s["resolved_by"]) for s in out] == [(old["pred_id"], None, "superseded")]
    assert jr.owed() == [] and [p["pred_id"] for p in jr.open_preds()] == [new["pred_id"]]


def test_late_start_is_kept_but_never_scored(jr):
    _event(jr, "e1", "M", True)
    jr.shadow_tick(T0 + 5 * 3600, {"M": (1.0, 50_000)})
    jr.shadow_tick(T0 + P.TIME_STOP_S, {"M": (1.1, 50_000)})
    row = json.loads(open(jr.SHADOW).readline())
    assert row["gap_s"] == 5 * 3600 and not jr.independent(row)


def _shadow_day(jr):
    """Three coins screened on 2026-10-03 (T0 is 04:00 UTC): RUN passes and doubles, DIP passes and is stopped, FLAT is rejected."""
    _event(jr, "e1", "RUN", True)
    _event(jr, "e2", "DIP", True)
    _event(jr, "e3", "FLAT", False)
    q = lambda a, b, c: {"RUN": (a, 50_000), "DIP": (b, 50_000), "FLAT": (c, 50_000)}   # noqa: E731
    jr.shadow_tick(T0 + 300, q(1.5, 0.95, 1.0))
    jr.shadow_tick(T0 + 600, q(2.2, 0.8, 1.01))     # RUN takes half at +120 %; DIP stops at -20 %
    jr.shadow_tick(T0 + 1200, q(1.5, 0.7, 1.02))    # RUN trails out at +50 %; FLAT is above entry at its 15-minute look
    jr.shadow_tick(T0 + P.TIME_STOP_S, q(1.2, 0.9, 1.04))


def test_market_state_is_read_only_after_the_window_and_its_shadows_close(jr):
    _shadow_day(jr)
    k = jr.market("2026-10-03", now=T0 + 2 * 86400)
    assert (k["mk_touches"], k["mk_resolved"], k["screened"], k["shadows"]) == (3, 0, 3, 3)
    assert round(k["mk_pass_rate"], 3) == 0.667 and k["mk_ret24"] == 0.04 and round(k["mk_up"], 3) == 0.667
    assert jr.market("2026-10-03", now=T0)["mk_ret24"] is None                          # the day is still running
    assert jr.market("2026-10-02", "2026-10-03", now=T0 + 2 * 86400)["mk_touches"] == 1.5   # per day over the window
    with pytest.raises(AssertionError):                                                # the 24 h figures are known a day late
        jr.predict("c", "mk_ret24@2026-10-03", "ge", 0, 0.5, "2026-10-03", "b")
    with pytest.raises(AssertionError):
        jr.predict("c", "closed", "ge", 1, 0.5, "2026-10-05", "b", rests_on="nope")


def test_a_miss_reads_as_market_when_the_market_forecast_missed_and_as_the_rule_when_it_held(jr):
    held = jr.predict("three touches", "mk_touches@2026-10-03", "ge", 3, 0.9, "2026-10-03", "b")
    wrong = jr.predict("screen passes none", "mk_pass_rate@2026-10-03", "le", 0.1, 0.9, "2026-10-03", "b")
    a = jr.predict("ten closes", "closed", "ge", 10, 0.9, "2026-10-03", "b", rests_on=held["pred_id"])
    b = jr.predict("half stop", "stop_share_at_40", "ge", 0.5, 0.9, "2026-10-03", "b", rests_on=held["pred_id"])
    c = jr.predict("net up", "cum_net", "gt", 0, 0.9, "2026-10-03", "b", rests_on=wrong["pred_id"])
    d = jr.predict("mean up", "mean_net_at_40", "gt", 0, 0.9, "2026-10-03", "b", rests_on=held["pred_id"])
    e = jr.predict("old row, names nothing", "pass_rate", "le", 0.1, 0.9, "2026-10-03", "b")
    _shadow_day(jr)
    m = {"closed": 0, "stop_share_at_40": 0.2, "cum_net": -1.0, "mean_net_at_40": -0.1, "pass_rate": 0.667}
    out = {s["pred_id"]: s for s in jr.resolve_due(m, "2026-10-04")}
    side = lambda p: jr.blame(out[p["pred_id"]])[0]   # noqa: E731
    assert out[held["pred_id"]]["outcome"] == 1 and out[wrong["pred_id"]]["outcome"] == 0
    assert (side(a), side(b), side(c), side(d), side(wrong)) == ("screen", "exits", "market", "rule", "market")
    assert jr.blame(out[e["pred_id"]]) == ("market", f"market forecast `{wrong['pred_id']}` (inferred) missed too")
    assert jr.lesson("w", "y", "model", b["pred_id"])["side"] == "exits" and jr.lesson("w", "y", "model", d["pred_id"])["side"] is None
    assert "reads as market" in jr.review() and jr.verify() == []


def test_winners_losers_and_capture_for_a_day(jr):
    _shadow_day(jr)
    with open(jr.PAPER, "a", encoding="utf-8") as f:      # the contract entered RUN only, and its live book did a little better
        f.write(json.dumps({"kind": "entry", "mint": "RUN", "symbol": "S", "event_id": "e1"}) + "\n")
        f.write(json.dumps({"kind": "close", "mint": "RUN", "symbol": "S", "event_id": "e1", "entry": 1.0, "net_sol": 0.9, "held_s": 1200,
                            "exits": [{"frac": 0.5, "pct": 1.2, "why": "take-half"}, {"frac": 0.5, "pct": 0.65, "why": "trail"}], "ts": "2026-10-03T20:20:00Z"}) + "\n")
    v = jr.movers("2026-10-03")
    assert [r["key"] for r in v["ran"]] == ["e1|RUN", "e3|FLAT", "e2|DIP"] and v["fell"][0]["key"] == "e2|DIP"
    run, dip = v["ran"][0], v["fell"][0]
    assert (run["entered"], run["peak_pct"], run["net_sol"], run["kept"]) == (True, 1.2, 0.9, 0.75)
    assert (dip["entered"], dip["pass"], dip["net_sol"], dip["kept"]) == (False, True, -0.225, None)   # booked at the mark: -20 % less fees
    assert v["capture_entered"] == 0.75 and v["n_entered"] == 1 and round(v["capture_all"], 3) == round((0.9 - 0.225 + 0.015) / 1.24, 3)
    assert jr.shadow_days() == ["2026-10-03"] and round(jr.shadow_stats([json.loads(l) for l in open(jr.SHADOW)])["sh_capture_pass"], 3) == round((0.825 - 0.225) / 1.2, 3)


def test_paper_close_carries_its_excursion_and_its_haircut(jr):
    _event(jr, "e1", "M", True, price=1.0)
    with open(jr.PAPER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "entry", "mint": "M", "symbol": "S", "event_id": "e1"}) + "\n")
        f.write(json.dumps({"kind": "close", "mint": "M", "symbol": "S", "event_id": "e1", "entry": 1.0, "net_sol": -0.175, "held_s": 900,
                            "exits": [{"frac": 1.0, "pct": -0.15, "why": "stop"}], "ts": "2026-10-03T04:15:00Z"}) + "\n")
    q = lambda p: {"M": (p, 50_000)}   # noqa: E731
    jr.shadow_tick(T0 + 300, q(1.08))
    jr.shadow_tick(T0 + 600, q(0.95))
    jr.shadow_tick(T0 + 900, q(0.88))
    assert jr.excursion_tick(T0 + 960, q(0.9)) == 1                    # one trade being followed after its exit
    jr.shadow_tick(T0 + 3600, q(1.3))
    jr.excursion_tick(T0 + 3600, q(1.3))
    live = jr.excursions(T0 + 3600)[0]
    assert live["open"] and (live["best_pct"], live["worst_pct"], live["marks_held"], live["after_exit_peak_pct"]) == (0.08, -0.12, 3, 0.3)
    assert jr.excursion_tick(T0 + 900 + P.TIME_STOP_S, q(1.1)) == 0
    row = json.loads(open(jr.EXC).readline())
    assert not row["open"] and row["after_exit_peak_pct"] == 0.3 and row["kept_of_peak"] == -0.5 and row["exit_pct"] == -0.15
    assert jr.excursion_tick(T0 + 2 * P.TIME_STOP_S, q(9.0)) == 0 and len(open(jr.EXC).readlines()) == 1   # written once

    assert jr.haircut(50_000, sol_usd=250) == 0.02 and jr.haircut(50_000) is None and jr.haircut(0, sol_usd=250) is None
    assert jr.book()[0]["net_haircut"] is None and jr.metrics()["cum_net_haircut"] is None     # no SOL quote yet: said, not guessed
    json.dump({"usd": 250}, open(jr.SOL_USD, "w"))
    assert jr.book()[0]["haircut"] == 0.02 and jr.metrics()["cum_net_haircut"] == -0.195
    assert "-0.195 after the fill haircut" in jr.headline() and "| -0.175 | -0.195 |" in jr.review()


def test_per_touch_forecast_is_scored_against_the_seed_prior_and_the_base_rate(jr):
    row = lambda passed, win, p: {"repeat": 0, "gap_s": 300, "net_sol": 0.1 if win else -0.1, "pass": passed, "win": win,   # noqa: E731
                                  "forecast": {"p_win": p}, "brier": round((p - win) ** 2, 4)}
    rv = jr.rivals([row(True, 1, 0.3), row(False, 0, 0.1), row(True, 1, 0.6), {**row(True, 0, 0.9), "gap_s": 5000}])   # the late start is not scored
    assert rv["n"] == 3 and rv["ahead"] == ["per-touch"]
    assert round(rv["brier"]["per-touch"], 4) == round((0.49 + 0.01 + 0.16) / 3, 4)
    assert round(rv["brier"]["seed prior"], 4) == round((0.49 + 0.01 + 0.49) / 3, 4)
    assert round(rv["brier"]["base rate"], 4) == round((0.25 + (2 / 3) ** 2 + 0.25) / 3, 4)
    assert jr.rivals([]) is None


def test_blind_lists_open_questions_without_anyones_odds(jr):
    a = jr.predict("first question", "closed", "ge", 40, 0.83, "2026-12-31", "secret basis")
    b = jr.predict("second question", "closed", "ge", 10, 0.17, "2026-10-10", "secret basis")
    text = jr.blind("irvin")
    assert text.index("second question") < text.index("first question") and f"--like {a['pred_id']} --who irvin" in text
    assert "0.83" not in text and "0.17" not in text and "secret" not in text and open(jr.BLIND, encoding="utf-8").read() == text
    mine = jr.predict(b["claim"], b["metric"], b["direction"], b["threshold"], 0.4, b["deadline"], "mine", who="irvin", like=b["pred_id"], today="2026-10-03")
    text = jr.blind("irvin")
    assert mine["like"] == b["pred_id"] and "second question" not in text and "first question" in text


def test_digest_page_shows_the_market_the_movers_and_the_haircut(jr, tmp_path, monkeypatch):
    import digest as DG
    monkeypatch.setattr(DG, "OUT", str(tmp_path / "foresight.html"))
    monkeypatch.setattr(DG, "OUT_MD", str(tmp_path / "foresight.md"))
    _shadow_day(jr)
    with open(jr.PAPER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "entry", "mint": "RUN", "symbol": "S", "event_id": "e1", "ts": "2026-10-03T04:00:00Z"}) + "\n")
        f.write(json.dumps({"kind": "close", "mint": "RUN", "symbol": "S", "event_id": "e1", "entry": 1.0, "net_sol": 0.9, "held_s": 1200,
                            "exits": [{"frac": 0.5, "pct": 1.2, "why": "take-half"}, {"frac": 0.5, "pct": 0.65, "why": "trail"}], "ts": "2026-10-03T04:20:00Z"}) + "\n")
    json.dump({"usd": 250}, open(jr.SOL_USD, "w"))
    jr.excursion_tick(T0 + 2 * 86400, {})
    page = open(DG.build(T0 + 2 * 86400), encoding="utf-8").read()
    for text in ("The market, before any rule", "Winners and losers", "+0.880 after the fill haircut", "Net after fill haircut", "Capture by day",
                 "the exits kept +77% of the peak", "Is the per-coin forecast learning?"):
        assert text in page, text
    assert DG.DOC in page
    md = open(DG.OUT_MD, encoding="utf-8").read()
    assert md.startswith("## Now") and "<" not in md.replace("mean loss <", "") and "&" not in md
    for text in ("## Today (last 24 hours)", "## This week", "## This month", "**The market, before any rule**", "**Winners and losers**",
                 "(+0.880 after the fill haircut)", "| B1 | a pass wins |", "**The fill haircut.**", "**Is the per-coin forecast learning?**"):
        assert text in md, text


def test_a_due_market_forecast_waits_for_its_shadows_and_voids_only_after_the_stated_tries(jr):
    a = jr.predict("screened coins fall", "mk_ret24@2026-10-03", "lt", 0, 0.7, "2026-10-04", "b")
    b = jr.predict("screened coins fall, again", "mk_ret24@2026-10-03", "lt", 0.5, 0.7, "2026-10-04", "b")
    _event(jr, "e1", "M", True)
    jr.shadow_tick(T0 + 300, {"M": (0.97, 50_000)})          # then the quotes go down: the shadow cannot close at its 24 h
    late = T0 + 2 * 86400
    assert jr.resolve_due({}, "2026-10-05", late) == [] and json.load(open(jr.MK_WAIT)) == {a["pred_id"]: 1, b["pred_id"]: 1}
    assert jr.resolve_due({}, "2026-10-05", late) == [] and jr.open_preds() != []
    jr.shadow_tick(late, {"M": (0.9, 50_000)})               # quotes are back: the shadow closes, the forecast is read
    out = jr.resolve_due({}, "2026-10-05", late)
    assert [(s["outcome"], s["value"]) for s in out] == [(1, -0.1), (1, -0.1)] and json.load(open(jr.MK_WAIT)) == {}

    c = jr.predict("never closes", "mk_ret24@2026-10-04", "lt", 0, 0.7, "2026-10-05", "b")
    _event(jr, "e2", "N", True, t=T0 + 86400)
    jr.shadow_tick(T0 + 86400 + 300, {"N": (1.0, 50_000)})
    for i in range(jr.MK_TRIES - 1):
        assert jr.resolve_due({}, "2026-10-06", late + 86400) == [], i
    out = jr.resolve_due({}, "2026-10-06", late + 86400)
    assert [(s["pred_id"], s["outcome"], s["note"]) for s in out] == [(c["pred_id"], None, f"window still open after {jr.MK_TRIES} tries")]


def test_like_is_refused_once_the_window_opens_and_a_forecaster_answers_a_question_once(jr):
    q = jr.predict("touches", "mk_touches@2026-10-10", "ge", 50, 0.8, "2026-10-10", "b")
    leg = jr.predict("closes", "closed", "ge", 3, 0.3, "2026-10-31", "b")
    again = lambda p, who, today: jr.predict(p["claim"], p["metric"], p["direction"], p["threshold"], 0.5, p["deadline"], "b", who=who, like=p["pred_id"], today=today)   # noqa: E731
    with pytest.raises(AssertionError, match="already answered"):
        again(q, "claude", "2026-10-05")
    with pytest.raises(AssertionError, match="already answered"):                       # with or without --like
        jr.predict(q["claim"], q["metric"], q["direction"], q["threshold"], 0.6, q["deadline"], "b")
    with pytest.raises(AssertionError, match="window opened 2026-10-10"):
        again(q, "irvin", "2026-10-10")
    with pytest.raises(AssertionError, match="resolved or passed"):
        again(leg, "irvin", "2026-11-01")
    assert again(q, "irvin", "2026-10-09")["like"] == q["pred_id"] and again(leg, "irvin", "2026-10-20")["who"] == "irvin"
    with pytest.raises(AssertionError, match="already answered"):
        again(q, "irvin", "2026-10-09")
    jr.resolve_due({"closed": 5}, "2026-10-06")
    assert len(jr.open_preds()) == 4


def test_retweet_share_and_gap_are_market_metrics(jr):
    def touch(eid, mint, text, t):
        with open(jr.EVENTS, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": eid, "feed": "x", "kind": "post", "person": "p", "ts": "2026-10-03T04:00:00Z", "text": text,
                                "accepted": [{"mint": mint, "phrase": "TKR", "via": "ticker"}],
                                "screen": [{"mint": mint, "symbol": "S", "pass": False, "why": ["liq 1 < 20000"], "intent": True,
                                            "snap": {"price": 1.0, "liq": 50_000}, "t_screened": t}]}) + "\n")
    for i in range(3):
        touch(f"own{i}", f"O{i}", "buying $TKR here", T0 + i)
        touch(f"rt{i}", f"R{i}", "RT @someone: $TKR is up", T0 + i)
    _event(jr, "plain", "P", False)                                               # a name match: not intent, not in either side
    q = {**{f"O{i}": (1.1, 50_000) for i in range(3)}, **{f"R{i}": (0.9, 50_000) for i in range(3)}, "P": (1.0, 50_000)}
    jr.shadow_tick(T0 + 300, q)
    jr.shadow_tick(T0 + P.TIME_STOP_S + 10, q)
    k = jr.market("2026-10-03", now=T0 + 2 * 86400)
    assert k["mk_intent"] == 6 and k["mk_rtshare"] == 0.5 and round(k["mk_rtgap"], 4) == 0.2
    assert jr.market("2026-10-03", now=T0)["mk_rtgap"] is None
    jr.predict("gap", "mk_rtgap@2026-10-03", "gt", 0, 0.6, "2026-10-04", "b")
