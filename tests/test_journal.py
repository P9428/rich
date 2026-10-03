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
    for name in ("BELIEFS", "PREDS", "SCORES", "LESSONS", "EVENTS", "PAPER", "SHADOW", "PATHS", "SHADOW_STATE", "REPORT"):
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
