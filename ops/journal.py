"""The Foresight Journal: what we said would happen, what happened, how surprised we were, and what we changed.

forecast/beliefs.jsonl      the mental model, one row per belief version (the last row per id is current)
forecast/predictions.jsonl  claims with a probability, written before the outcome
forecast/scores.jsonl       outcomes, resolved from journal/ by a named metric wherever one exists
forecast/lessons.jsonl      why a forecast missed (or hit for the wrong reason), and which belief moved
journal/shadow.jsonl        one row per screened touch, pass or fail: what the contract's exits would have booked over 24 h
journal/shadow_paths.jsonl  the 24 h price path behind each shadow row

The four forecast files are append-only and hash-chained; `verify` fails on any edit. Observation only: nothing here
enters, exits or screens a trade.

  python ops/journal.py predict --claim ... --metric closed --direction ge --threshold 40 --confidence 0.8 --deadline 2026-12-31 --basis ...
  python ops/journal.py predict --like <pred_id> --who irvin --confidence 0.6     (a second forecaster on the same question)
  python ops/journal.py resolve <pred_id> yes|no --note ...                       (manual metrics only)
  python ops/journal.py lesson --pred <pred_id> --what ... --why ... --cause model --belief B1 --p 0.2 --rule ...
  python ops/journal.py belief --id B9 --claim ... --p 0.6 --why ... --falsifier ...
  python ops/journal.py tick | review | metrics | verify
"""
import argparse
import calendar
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C   # noqa: E402
import paper as P    # noqa: E402
import readout as R  # noqa: E402

BELIEFS = C.path("forecast", "beliefs.jsonl")
PREDS = C.path("forecast", "predictions.jsonl")
SCORES = C.path("forecast", "scores.jsonl")
LESSONS = C.path("forecast", "lessons.jsonl")
CHAINED = (BELIEFS, PREDS, SCORES, LESSONS)
EVENTS = C.path("journal", "events.jsonl")
PAPER = C.path("journal", "paper.jsonl")
SHADOW = C.path("journal", "shadow.jsonl")
PATHS = C.path("journal", "shadow_paths.jsonl")
SHADOW_STATE = C.path("state", "shadow.json")
REPORT = C.path("out", "journal.md")
ERRORS = C.path("monitor", "journal-errors.log")

LATE_START_S = 900       # a shadow whose first mark came later than this missed part of the path: kept, never scored
MIN_SIDE = 8             # a pass-vs-fail comparison is undefined below this many independent rows a side
OWED_BITS = 1.0          # a resolved forecast that gave under 50 % to what happened owes a lesson
CAUSES = ("model", "variance", "measurement", "question", "execution")
OPS = {"gt": lambda x, t: x > t, "ge": lambda x, t: x >= t, "lt": lambda x, t: x < t, "le": lambda x, t: x <= t,
       "eq": lambda x, t: x == t, "in": lambda x, t: t[0] <= x <= t[1]}
AUTO_BELIEF = {True: "B1", False: "B3"}   # the belief whose seed prior forecasts a pass / a fail shadow


# ---------------------------------------------------------------- chain

def _hash(rec):
    return hashlib.sha256(json.dumps({k: v for k, v in rec.items() if k != "h"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def chain_append(file, rec):
    rows = C.read_jsonl(file)
    rec = {**rec, "ts": rec.get("ts") or C.iso(), "prev": rows[-1]["h"] if rows else ""}
    rec["h"] = _hash(rec)
    with open(file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def verify():
    """Every forecast file must replay: each row's hash matches its content and points at the row before it."""
    bad = []
    for file in CHAINED:
        prev = ""
        for i, r in enumerate(C.read_jsonl(file), 1):
            if r.get("prev") != prev or r.get("h") != _hash(r):
                bad.append(f"{os.path.basename(file)} row {i}: chain broken")
                break
            prev = r["h"]
    return bad


def leg():
    with open(os.path.join(C.ROOT, "prereg", "CONTRACT.md"), encoding="utf-8") as f:
        m = re.search(r"contract (\S+)", f.readline())
    return m.group(1) if m else "?"


def _git():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=C.ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _epoch(iso):
    return calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))


# ---------------------------------------------------------------- shadow book

def _quotes(mints):
    """{mint: (priceUsd, liquidity)} from the deepest pair, the same mark the sensor uses."""
    out = {}
    for p in C.dex_tokens(sorted(set(mints))) if mints else []:
        m, liq = p["baseToken"]["address"], (p.get("liquidity") or {}).get("usd") or 0
        if liq >= out.get(m, (0, -1))[1]:
            out[m] = (float(p.get("priceUsd") or 0), liq)
    return out


def independent(r):
    """First touch of a mint in 24 h, watched from the start, with a quote: the rows statistics may use."""
    return r["repeat"] == 0 and r["gap_s"] is not None and r["gap_s"] <= LATE_START_S and r["net_sol"] is not None


def shadow_stats(rows):
    ind = [r for r in rows if independent(r)]
    side = {True: [r for r in ind if r["pass"]], False: [r for r in ind if not r["pass"]]}
    mean = lambda rs: sum(r["net_sol"] for r in rs) / len(rs) if rs else None  # noqa: E731
    stops = [r for r in side[True] if "stop" in r["exits"]]
    both = len(side[True]) >= MIN_SIDE and len(side[False]) >= MIN_SIDE
    return {
        "sh_n_pass": len(side[True]), "sh_n_fail": len(side[False]),
        "sh_wins_pass": sum(r["win"] for r in side[True]), "sh_wins_fail": sum(r["win"] for r in side[False]),
        "sh_peak100_pass": sum(1 for r in side[True] if r["peak_pct"] >= 1.0),
        "sh_10x_pass": sum(1 for r in side[True] if r["peak_pct"] >= 9.0),
        "sh_mean_net_pass": mean(side[True]), "sh_mean_net_fail": mean(side[False]),
        "sh_fail_minus_pass": mean(side[False]) - mean(side[True]) if both else None,
        "sh_n_stops": len(stops), "sh_stops_recovered": sum(1 for r in stops if (r["after_stop_peak_pct"] or -1) > 0),
        "sh_stop_regret": sum(1 for r in stops if (r["after_stop_peak_pct"] or -1) > 0) / len(stops) if len(stops) >= MIN_SIDE else None,
    }


def auto_p(passed, stats, beliefs):
    """P(a shadow closes net > 0): the belief's seed prior, updated by every independent shadow closed so far."""
    seed = next(b for b in beliefs if b["id"] == AUTO_BELIEF[passed])
    side = "pass" if passed else "fail"
    return (seed["p"] * seed["n0"] + stats[f"sh_wins_{side}"]) / (seed["n0"] + stats[f"sh_n_{side}"])


def _at(path, horizon_s, entry):
    for dt, price, _ in path:
        if dt >= horizon_s:
            return round(price / entry - 1, 4) if dt - horizon_s <= LATE_START_S else None
    return None


def _finalise(s, now):
    pos, path, entry = P.Position.from_dict(s["pos"]), s["path"], s["entry"]
    row = {k: s[k] for k in ("key", "event_id", "mint", "symbol", "feed", "kind", "person", "pass", "why", "snap", "latency",
                             "entry", "repeat", "gap_s", "forecast", "leg")}
    row["t0"] = C.iso(s["t0"])
    if not path:
        return {**row, "net_sol": None, "win": None, "exits": [], "marks": 0}
    if not pos.closed:   # the quote vanished before the time stop: book what was last seen and say so
        pos._book(pos.remaining, path[-1][1] / entry - 1, now, "time-noquote")
    peak, trough = max(path, key=lambda x: x[1]), min(path, key=lambda x: x[1])
    stop_t = next((_epoch(e["t"]) - s["t0"] for e in pos.exits if e["why"] == "stop"), None)
    after = [x[1] for x in path if stop_t is not None and x[0] > stop_t]
    net = round(pos.net_sol(), 4)
    return {**row, "net_sol": net, "win": int(net > 0), "exits": [e["why"] for e in pos.exits],
            "held_s": int(_epoch(pos.exits[-1]["t"]) - s["t0"]),
            "peak_pct": round(peak[1] / entry - 1, 4), "peak_s": peak[0], "trough_pct": round(trough[1] / entry - 1, 4), "trough_s": trough[0],
            "ret_1h": _at(path, 3600, entry), "ret_6h": _at(path, 6 * 3600, entry), "ret_24h": round(path[-1][1] / entry - 1, 4),
            "after_stop_peak_pct": round(max(after) / entry - 1, 4) if after else None,
            "liq_end_ratio": round(path[-1][2] / s["snap"]["liq"], 3) if s["snap"].get("liq") else None,
            "quote_lost_s": path[-1][0] if now - s["t0"] - path[-1][0] > LATE_START_S else None,
            "brier": round((s["forecast"]["p_win"] - int(net > 0)) ** 2, 4), "marks": len(path)}


def shadow_tick(now=None, quotes=None):
    """Open a shadow for every newly screened touch, mark every open shadow, close the ones 24 h old.
    A shadow runs the contract's own exits (paper.Position) on a coin the screen passed or rejected, and keeps
    watching after a stop, so the screen and the stop can both be judged against what they turned away."""
    now = now or C.now()
    st = C.load_json(SHADOW_STATE, {})
    done = C.read_jsonl(SHADOW)
    known = set(st) | {r["key"] for r in done}
    touched = [(r["mint"], _epoch(r["t0"])) for r in done] + [(s["mint"], s["t0"]) for s in st.values()]
    stats, beliefs, this_leg = shadow_stats(done), C.read_jsonl(BELIEFS), leg()
    for ev in C.read_jsonl(EVENTS):
        for x in ev.get("screen", []):
            key, snap = ev["id"] + "|" + x["mint"], x.get("snap") or {}
            t0 = x.get("t_screened") or _epoch(ev["ts"])
            if key in known or (snap.get("price") or 0) <= 0 or now - t0 >= P.TIME_STOP_S:
                continue
            known.add(key)
            st[key] = {"key": key, "event_id": ev["id"], "mint": x["mint"], "symbol": x["symbol"], "feed": ev["feed"], "kind": ev["kind"],
                       "person": ev["person"], "pass": x["pass"], "why": x["why"], "snap": snap, "latency": ev.get("latency"),
                       "entry": snap["price"], "t0": t0, "leg": this_leg, "gap_s": None, "path": [],
                       "repeat": sum(1 for m, t in touched if m == x["mint"] and 0 <= t0 - t < P.TIME_STOP_S),
                       "forecast": {"p_win": round(auto_p(x["pass"], stats, beliefs), 4), "made": C.iso(now)},
                       "pos": P.Position(x["mint"], x["symbol"], snap["price"], t0, ev["id"]).to_dict()}
            touched.append((x["mint"], t0))
    quotes = quotes if quotes is not None else _quotes([s["mint"] for s in st.values()])
    for key, s in list(st.items()):
        price, liq = quotes.get(s["mint"], (0, 0))
        dt = now - s["t0"]
        if price > 0:
            if s["gap_s"] is None:
                s["gap_s"] = round(dt)
            s["path"].append([round(dt), price, round(liq)])
            pos = P.Position.from_dict(s["pos"])
            pos.mark(price, now)
            s["pos"] = pos.to_dict()
        if dt >= P.TIME_STOP_S:
            C.append(SHADOW, _finalise(s, now))
            C.append(PATHS, {"key": key, "path": s["path"]})
            del st[key]
    C.save_json(SHADOW_STATE, st)
    return len(st)


# ---------------------------------------------------------------- metrics

def _p50(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def metrics():
    """Every number a forecast may be resolved on. None means not yet defined (fewer than 40 closes, too few shadows)."""
    paper, events = C.read_jsonl(PAPER), C.read_jsonl(EVENTS)
    closes = [r for r in paper if r.get("kind") == "close"]
    entries = [r["event_id"].split(":")[0] for r in paper if r.get("kind") == "entry"]
    nets = [r["net_sol"] for r in closes]
    s = R.stats(nets)
    screened = [x for e in events for x in e.get("screen", [])]
    m = {"closed": s["n"], "wins": s["wins"], "win_rate": s["wins"] / s["n"] if s["n"] else None, "cum_net": s["cum"],
         "mean_net": s["mean"] if s["n"] else None, "max_dd": s["dd"],
         "kill_ever": int(any(R.stats(nets[:i])["verdict"] == "KILL" for i in range(1, len(nets) + 1))),
         "events": len(events), "resolved": sum(1 for e in events if e.get("accepted")), "screened": len(screened),
         "passes": sum(1 for x in screened if x["pass"]),
         "pass_rate": sum(1 for x in screened if x["pass"]) / len(screened) if screened else None, "entries": len(entries)}
    for feed in ("truth", "wallet", "x", "profile"):
        m[f"entries_{feed}"] = entries.count(feed)
        m[f"lat_p50_{feed}"] = _p50([e["latency"]["source_to_seen"] for e in events if e["feed"] == feed and e.get("latency")])
    at40 = R.stats(nets[:40]) if s["n"] >= 40 else None   # frozen on the first 40 closes, the count the gates wait for
    first40 = closes[:40]
    m.update({
        "win_rate_at_40": at40["wins"] / 40 if at40 else None, "mean_net_at_40": at40["mean"] if at40 else None,
        "cum_net_at_40": at40["cum"] if at40 else None, "mean_loss_at_40": at40["mean_loss"] if at40 else None,
        "s1_at_40": int(at40["verdict"] == "SURVIVES ON PAPER") if at40 else None,
        "stop_share_at_40": sum(1 for r in first40 if any(e["why"] == "stop" for e in r["exits"])) / 40 if at40 else None,
        "stale_share_at_40": sum(1 for r in first40 if any(e["why"] == "stale" for e in r["exits"])) / 40 if at40 else None,
        "truth_share_at_40": sum(1 for r in first40 if r["event_id"].startswith("truth:")) / 40 if at40 else None})
    m.update(shadow_stats([r for r in C.read_jsonl(SHADOW) if r["leg"] == leg()]))   # exits differ by leg: never pooled
    return m


# ---------------------------------------------------------------- forecasts

def predict(claim, metric, direction, threshold, confidence, deadline, basis, who="claude", beliefs=(), when="deadline", tags=()):
    """when: 'deadline' reads the metric after the deadline day; 'early' confirms the moment the claim holds;
    'defined' resolves the moment the metric exists (the *_at_40 family). metric 'manual' waits for `resolve`."""
    assert 0 < confidence < 1 and when in ("deadline", "early", "defined") and direction in OPS, "bad forecast"
    assert metric == "manual" or metric in metrics(), f"unknown metric {metric}"
    assert all(b in {r["id"] for r in C.read_jsonl(BELIEFS)} for b in beliefs), "unknown belief id"
    time.strptime(deadline, "%Y-%m-%d")
    ts = C.iso()
    return chain_append(PREDS, {"pred_id": hashlib.sha256(f"{claim}{who}{ts}".encode()).hexdigest()[:12], "ts": ts, "leg": leg(), "who": who,
                                "claim": claim, "basis": basis, "beliefs": list(beliefs), "metric": metric, "direction": direction,
                                "threshold": threshold, "confidence": confidence, "deadline": deadline, "when": when,
                                "tags": list(tags), "git": _git()})


def _score(p, outcome, value, by, note=""):
    hit = p["confidence"] if outcome else 1 - p["confidence"]
    return chain_append(SCORES, {"pred_id": p["pred_id"], "leg": p["leg"], "who": p["who"], "claim": p["claim"], "beliefs": p["beliefs"],
                                 "confidence": p["confidence"], "outcome": outcome, "value": value,
                                 "brier": None if outcome is None else round((p["confidence"] - outcome) ** 2, 4),
                                 "surprise_bits": None if outcome is None else round(-math.log2(hit), 3),
                                 "resolved_by": by, "note": note})


def open_preds():
    scored = {r["pred_id"] for r in C.read_jsonl(SCORES)}
    return [p for p in C.read_jsonl(PREDS) if p["pred_id"] not in scored]


def resolve_due(m=None, today=None):
    """Score every open forecast whose metric can now speak. A metric still undefined after the deadline voids the
    forecast (outcome null): the question was unanswerable as posed, which is itself owed a lesson. A forecast written
    for a contract that has since been superseded is voided too: its leg ended before the metric could speak."""
    m, today, out = m or metrics(), today or C.iso()[:10], []
    for p in open_preds():
        if p["metric"] == "manual":
            continue
        if p["leg"] != leg():
            out.append(_score(p, None, None, "superseded", f"leg ended, superseded by {leg()}"))
            continue
        x, late = m.get(p["metric"]), today > p["deadline"]
        holds = None if x is None else int(OPS[p["direction"]](x, p["threshold"]))
        if (p["when"] == "early" and holds) or (p["when"] == "defined" and holds is not None) or (late and holds is not None):
            out.append(_score(p, holds, x, "metric"))
        elif late:
            out.append(_score(p, None, None, "metric", "metric undefined at deadline"))
    return out


def resolve_manual(pred_id, outcome, note):
    p = next(p for p in open_preds() if p["pred_id"] == pred_id)
    assert p["metric"] == "manual", "this forecast resolves from its metric, not by hand"
    return _score(p, outcome, None, "manual", note)


def current_beliefs():
    cur = {}
    for b in C.read_jsonl(BELIEFS):
        cur[b["id"]] = {**b, "seed_p": cur.get(b["id"], b).get("seed_p", b["p"]), "versions": cur.get(b["id"], {}).get("versions", 0) + 1}
    return cur


def belief(bid, claim, p, why, falsifier, n0=10, k=None, n=None, cause="seed"):
    """k/n name the metrics that count this belief's successes and trials, when the shadow book can test it directly."""
    assert 0 < p < 1
    return chain_append(BELIEFS, {"id": bid, "claim": claim, "p": p, "n0": n0, "why": why, "falsifier": falsifier, "k": k, "n": n,
                                  "cause": cause, "leg": leg()})


def lesson(what, why, cause, pred_id=None, belief_id=None, p=None, rule=None):
    """cause: model (the belief was wrong), variance (the belief was fine, the draw was not), measurement (the instrument
    lied), question (the forecast was badly posed), execution (a bug or an outage). Only `model` should move a belief."""
    assert cause in CAUSES, f"cause must be one of {CAUSES}"
    cur = current_beliefs()
    rec = {"lesson_id": hashlib.sha256(f"{what}{C.iso()}".encode()).hexdigest()[:12], "leg": leg(), "pred_id": pred_id, "what": what,
           "why": why, "cause": cause, "belief": belief_id, "p_from": cur[belief_id]["p"] if belief_id else None, "p_to": p, "rule": rule}
    out = chain_append(LESSONS, rec)
    if belief_id and p is not None:
        b = cur[belief_id]
        belief(belief_id, b["claim"], p, why, b["falsifier"], b["n0"], b["k"], b["n"], cause=out["lesson_id"])
    return out


def owed():
    """Resolved forecasts that surprised us (or voided) and have no lesson yet. A leg ending is one lesson, not one per forecast."""
    have = {l["pred_id"] for l in C.read_jsonl(LESSONS)}
    return [s for s in C.read_jsonl(SCORES) if s["pred_id"] not in have and s["resolved_by"] != "superseded"
            and (s["outcome"] is None or s["surprise_bits"] >= OWED_BITS)]


def _tail(k, n, p):
    """Two-sided exact binomial: how often a belief of p would produce a count as unlikely as k of n."""
    pmf = [math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    return sum(x for x in pmf if x <= pmf[k] * (1 + 1e-9))


def belief_checks(m=None):
    """Each data-bound belief against the shadow book. strained = the data would be a < 5 % event if the belief were true."""
    m, out = m or metrics(), []
    for b in current_beliefs().values():
        k, n = (m.get(b["k"]), m.get(b["n"])) if b["k"] else (None, None)
        out.append({**b, "k_now": k, "n_now": n, "tail": _tail(k, n, b["p"]) if n else None,
                    "posterior": (b["seed_p"] * b["n0"] + k) / (b["n0"] + n) if n else None})
        out[-1]["strained"] = bool(n) and out[-1]["tail"] < 0.05
    return out


# ---------------------------------------------------------------- review

def _brier(rows):
    rows = [r for r in rows if r.get("brier") is not None]
    return (sum(r["brier"] for r in rows) / len(rows), len(rows)) if rows else (None, 0)


def _fmt(x, spec="{:.3f}"):
    return "-" if x is None else spec.format(x)


def headline():
    b, n = _brier(C.read_jsonl(SCORES))
    done = [r for r in C.read_jsonl(SHADOW) if independent(r)]
    return (f"Foresight Journal: {len(open_preds())} forecasts open, {n} scored" + (f" (Brier {b:.3f} vs 0.250 coin)" if n else "") +
            f"; lessons owed {len(owed())}; beliefs strained {sum(1 for c in belief_checks() if c['strained'])}; "
            f"shadows {len(C.load_json(SHADOW_STATE, {}))} open, {len(done)} closed clean -> out/journal.md")


def review():
    m, scores, preds, lessons = metrics(), C.read_jsonl(SCORES), {p["pred_id"]: p for p in C.read_jsonl(PREDS)}, C.read_jsonl(LESSONS)
    L = [f"# The Foresight Journal  rich  {C.iso()}  leg {leg()}", ""]
    bad = verify()
    L += [f"**CHAIN BROKEN: {'; '.join(bad)}**" if bad else "chain intact: no forecast, score, lesson or belief has been edited", ""]

    L += ["## 1. Lessons owed (write these before anything else)", ""]
    for s in owed():
        L.append(f"- `{s['pred_id']}` [{s['who']}] said {s['confidence']:.0%}: {s['claim']} -> "
                 + ("VOID (metric never defined)" if s["outcome"] is None else f"{'YES' if s['outcome'] else 'NO'} (value {s['value']}), {s['surprise_bits']:.1f} bits of surprise"))
    L += ["- none"] if not owed() else []

    L += ["", "## 2. The model against the data", "", "| id | belief | seed p | now p | data k/n | posterior | verdict |", "|---|---|---|---|---|---|---|"]
    for c in belief_checks(m):
        data = f"{c['k_now']}/{c['n_now']}" if c["n_now"] else "-"
        verdict = "STRAINED: revise or defend" if c["strained"] else ("consistent" if c["n_now"] else "no direct data")
        L.append(f"| {c['id']} | {c['claim']} | {c['seed_p']:.2f} | {c['p']:.2f} | {data} | {_fmt(c['posterior'], '{:.2f}')} | {verdict} |")

    L += ["", "## 3. Scoreboard (Brier: 0 is perfect, 0.25 is a coin, above 0.25 is worse than not thinking)", ""]
    for label, rows in [("all", scores)] + [(f"who={w}", [s for s in scores if s["who"] == w]) for w in sorted({s["who"] for s in scores})] \
            + [(f"leg={g}", [s for s in scores if s["leg"] == g]) for g in sorted({s["leg"] for s in scores})]:
        b, n = _brier(rows)
        L.append(f"- {label}: n={n}, Brier {_fmt(b)}, mean surprise {_fmt(sum(r['surprise_bits'] for r in rows if r['brier'] is not None) / n if n else None, '{:.2f}')} bits")
    L += ["- no forecast has resolved yet"] if not scores else []
    cal = [s for s in scores if s["brier"] is not None]
    if cal:
        L += ["", "| stated | n | came true |", "|---|---|---|"]
        for lo in (0, 0.2, 0.4, 0.6, 0.8):
            rows = [s for s in cal if lo <= s["confidence"] < lo + 0.2]
            if rows:
                L.append(f"| {lo:.0%}-{lo+0.2:.0%} (mean {sum(r['confidence'] for r in rows)/len(rows):.0%}) | {len(rows)} | {sum(r['outcome'] for r in rows)/len(rows):.0%} |")
    auto = [r for r in C.read_jsonl(SHADOW) if independent(r)]
    if auto:
        seeds = {b["id"]: b["p"] for b in reversed(C.read_jsonl(BELIEFS))}   # reversed: the first version of each id wins
        base = sum((seeds[AUTO_BELIEF[r["pass"]]] - r["win"]) ** 2 for r in auto) / len(auto)
        got = sum(r["brier"] for r in auto) / len(auto)
        L += ["", f"- per-touch P(win), updated after every close: n={len(auto)}, Brier {got:.3f} against {base:.3f} for the frozen seed prior "
                  f"(learning skill {1 - got / base:+.1%})" if base else ""]

    L += ["", "## 4. Open forecasts and where reality stands today", "", "| id | who | says | claim | metric now | needs | deadline |", "|---|---|---|---|---|---|---|"]
    for p in open_preds():
        now = "by hand" if p["metric"] == "manual" else _fmt(m.get(p["metric"]), "{:.4g}")
        L.append(f"| `{p['pred_id']}` | {p['who']} | {p['confidence']:.0%} | {p['claim']} | {now} | {p['direction']} {p['threshold']} | {p['deadline']} ({p['when']}) |")

    L += ["", "## 5. What the screen turned away (shadow book: first touches, watched from the start, contract exits)", "",
          "| group | n | win rate | mean net SOL | peak >= +100% | median peak | median trough |", "|---|---|---|---|---|---|---|"]
    groups = [("PASS", [r for r in auto if r["pass"]]), ("FAIL (any)", [r for r in auto if not r["pass"]])]
    for reason in sorted({w.split()[0] for r in auto for w in r["why"]}):
        groups.append((f"fail: {reason}", [r for r in auto if any(w.split()[0] == reason for w in r["why"])]))
    for label, rows in groups:
        if rows:
            L.append(f"| {label} | {len(rows)} | {sum(r['win'] for r in rows)/len(rows):.0%} | {sum(r['net_sol'] for r in rows)/len(rows):+.3f} | "
                     f"{sum(1 for r in rows if r['peak_pct'] >= 1)/len(rows):.0%} | {_p50([r['peak_pct'] for r in rows]):+.0%} | {_p50([r['trough_pct'] for r in rows]):+.0%} |")
    L.append(f"\nstop regret (stopped passes that later traded above entry inside 24 h): {_fmt(m['sh_stop_regret'], '{:.0%}')} of {m['sh_n_stops']} stops"
             f" (reported from {MIN_SIDE})")

    L += ["", "## 6. Lessons and the rules they left for the next leg", ""]
    for l in lessons:
        move = f" {l['belief']} {l['p_from']:.2f} -> {l['p_to']:.2f}." if l["belief"] and l["p_to"] is not None else ""
        L.append(f"- {l['ts'][:10]} [{l['leg']}, {l['cause']}] {l['what']} WHY: {l['why']}{move}" + (f" RULE: {l['rule']}" if l["rule"] else ""))
        if l["pred_id"] in preds:
            L.append(f"  - forecast `{l['pred_id']}`: {preds[l['pred_id']]['claim']}")
    L += ["- none yet"] if not lessons else []
    text = "\n".join(L) + "\n"
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def tick():
    try:
        shadow_tick()
    except Exception as e:   # a DexScreener outage must not stop forecasts resolving
        C.append(ERRORS, {"where": "shadow", "err": str(e)[:200]})
    try:
        resolve_due()
        review()
    except Exception as e:
        C.append(ERRORS, {"where": "resolve", "err": str(e)[:200]})


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("tick", "review", "metrics", "verify"):
        sub.add_parser(name)
    a = sub.add_parser("predict")
    a.add_argument("--like", help="pred_id whose question to answer again as another forecaster")
    for flag in ("claim", "metric", "direction", "deadline", "basis"):
        a.add_argument("--" + flag)
    a.add_argument("--threshold", help="a number, or lo,hi with --direction in")
    a.add_argument("--confidence", type=float, required=True)
    a.add_argument("--who", default="claude")
    a.add_argument("--when", default="deadline")
    a.add_argument("--beliefs", default="")
    a.add_argument("--tags", default="")
    a = sub.add_parser("resolve")
    a.add_argument("pred_id")
    a.add_argument("outcome", choices=("yes", "no"))
    a.add_argument("--note", required=True)
    a = sub.add_parser("lesson")
    for flag, req in (("what", True), ("why", True), ("cause", True), ("pred", False), ("belief", False), ("rule", False)):
        a.add_argument("--" + flag, required=req)
    a.add_argument("--p", type=float)
    a = sub.add_parser("belief")
    for flag in ("id", "claim", "why", "falsifier"):
        a.add_argument("--" + flag, required=True)
    a.add_argument("--p", type=float, required=True)
    a.add_argument("--n0", type=float, default=10)
    a.add_argument("--k")
    a.add_argument("--n")
    args = ap.parse_args()
    if args.cmd == "tick":
        tick()
    elif args.cmd == "review":
        print(review())
    elif args.cmd == "metrics":
        print(json.dumps(metrics(), indent=1))
    elif args.cmd == "verify":
        bad = verify()
        print("\n".join(bad) or "chain intact")
        sys.exit(1 if bad else 0)
    elif args.cmd == "predict":
        src = next(p for p in C.read_jsonl(PREDS) if p["pred_id"] == args.like) if args.like else {}
        thr = src.get("threshold") if args.threshold is None else [float(x) for x in args.threshold.split(",")] if "," in args.threshold else float(args.threshold)
        r = predict(args.claim or src["claim"], args.metric or src["metric"], args.direction or src["direction"], thr, args.confidence,
                    args.deadline or src["deadline"], args.basis or f"second forecast on {args.like}", args.who,
                    [b for b in args.beliefs.split(",") if b] or src.get("beliefs", []), src.get("when", args.when),
                    [t for t in args.tags.split(",") if t] or src.get("tags", []))
        print(r["pred_id"], r["claim"])
    elif args.cmd == "resolve":
        print(resolve_manual(args.pred_id, int(args.outcome == "yes"), args.note))
    elif args.cmd == "lesson":
        print(lesson(args.what, args.why, args.cause, args.pred, args.belief, args.p, args.rule)["lesson_id"])
    elif args.cmd == "belief":
        print(belief(args.id, args.claim, args.p, args.why, args.falsifier, args.n0, args.k, args.n)["h"])


if __name__ == "__main__":
    main()
