"""The population: one feed, many paper books, every launch scored against the chain. Observation only; nothing here trades.

The engine (src/duval.py) marks every launch on chain for 180 s and writes the path to journal/paths/<day>.jsonl. This script replays
those paths through the contract's rules (the control) and through forks of it that change one variable each (the variants), with the
same curve arithmetic and fees the live book pays. It then names the limiting factor of the loop and the variants that have earned a
look, under the promotion rule: beat the control on mean net on each of the last PROMOTE_DAYS forward days with at least
PROMOTE_N trades a day. Nothing is promoted by this script; a promoted variant is a candidate for the next contract id, ruled through RI.

  python ops/population.py [--days 3]        -> out/population.md, state/population.json
"""
import argparse
import glob
import json
import math
import os
import random
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C   # noqa: E402
import duval as D    # noqa: E402

OUT = C.path("out", "population.md")
STATE = C.path("state", "population.json")
PROMOTE_DAYS = 3
PROMOTE_N = 50
MIN_SIDE = 30

CONTROL = {"name": "control (RI-04)", "filter": "matched", "pump_only": True, "mcap_max": D.MCAP_MAX_USD, "take": D.TAKE, "stop": D.STOP,
           "hold": D.HOLD_S, "delay": 0.0, "size": D.SIZE_SOL, "first_buyer": False}
# one variable each; the names say which
VARIANTS = [
    {"name": "all launches (no news)", "filter": "all"},
    {"name": "unmatched only", "filter": "unmatched"},
    {"name": "entry +2 s (first mark)", "delay": 2.0},
    {"name": "entry +10 s", "delay": 10.0},
    {"name": "entry after first outside buy (<=10 s)", "first_buyer": True},
    {"name": "take +10 %", "take": 0.10},
    {"name": "take +30 %", "take": 0.30},
    {"name": "take +50 %", "take": 0.50},
    {"name": "stop -3 %", "stop": -0.03},
    {"name": "stop -8 %", "stop": -0.08},
    {"name": "stop -10 %", "stop": -0.10},
    {"name": "stop -20 %", "stop": -0.20},
    {"name": "hold 30 s", "hold": 30},
    {"name": "hold 120 s", "hold": 120},
    {"name": "hold 180 s", "hold": 180},
    {"name": "size 0.5 SOL", "size": 0.5},
    {"name": "size 1 SOL", "size": 1.0},
    {"name": "size 3 SOL", "size": 3.0},
    {"name": "mcap < $6K", "mcap_max": 6_000},
    {"name": "mcap < $20K", "mcap_max": 20_000},
    {"name": "any mint (not only pump suffix)", "pump_only": False},
]


def load_paths(days):
    rows = []
    for f in sorted(glob.glob(os.path.join(C.ROOT, "journal", "paths", "*.jsonl")))[-days:]:
        rows += C.read_jsonl(f)
    return rows


def replay(p, rule):
    """One launch through one rule. Returns the trade dict or None if the rule does not enter."""
    if rule["filter"] == "matched" and not p["match"]:
        return None
    if rule["filter"] == "unmatched" and p["match"]:
        return None
    if rule["pump_only"] and not p["mint"].endswith("pump"):
        return None
    if p.get("mayhem") or p.get("pool") not in (None, "pump"):
        return None
    if p.get("mcap0_usd") is None or p["mcap0_usd"] >= rule["mcap_max"]:
        return None
    marks = p["marks"]
    if not marks:
        return None
    v0s, v0t = p["v0"]
    r0 = marks[0][3]
    # the on-chain check the live book makes at decision: reserves must agree with the feed, or the curve is non-standard
    if not (0.5 <= marks[0][1] / max(v0s, 1e-9) <= 2.0) or abs(marks[0][1] * marks[0][2] / (v0s * v0t) - 1) > 0.05:
        return None
    # the entry state: the message's reserves (delay 0), the first mark at or after the delay, or the first mark showing an outside buy
    entry = None
    if rule["first_buyer"]:
        for m in marks:
            if m[0] > 10:
                break
            if m[3] > r0 + 1e-6 or m[1] > v0s * 1.01:
                entry = m
                break
        if entry is None:
            return None
    elif rule["delay"] <= 0:
        entry = [0.0, v0s, v0t, r0]
    else:
        entry = next((m for m in marks if m[0] >= rule["delay"]), None)
        if entry is None:
            return None
    size = rule["size"]
    tokens = D.buy(entry[1], entry[2], size)
    if tokens <= 0:
        return None
    t_in = entry[0]
    pct = None
    why = "end"
    peak = trough = 0.0
    for m in marks:
        if m[0] < t_in or (m is entry):
            continue
        pct = D.mark_value(m[1], m[2], tokens, size) / size - 1
        peak, trough = max(peak, pct), min(trough, pct)
        held = m[0] - t_in
        if pct >= rule["take"]:
            why = "take"; break
        if pct <= rule["stop"]:
            why = "stop"; break
        if held >= rule["hold"]:
            why = "time"; break
    if pct is None:
        return None
    return {"net": size * pct, "pct": pct, "why": why, "peak": peak, "trough": trough, "t_in": t_in}


def stats(trades):
    n = len(trades)
    if not n:
        return {"n": 0}
    nets = [t["net"] for t in trades]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    return {"n": n, "win": len(wins) / n, "mean": st.mean(nets), "sum": sum(nets), "pf": (sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else float("inf"),
            "mean_loss": (-st.mean(losses)) if losses else 0.0, "stop_share": sum(1 for t in trades if t["why"] == "stop") / n,
            "take_share": sum(1 for t in trades if t["why"] == "take") / n, "med_pct": st.median(t["pct"] for t in trades)}


def rule_of(v):
    return {**CONTROL, **v}


def book_constrained(paths, rule, max_open=D.MAX_OPEN):
    """The control as the live book would have run it: at most max_open positions, in launch order."""
    out, open_until = [], []
    for p in sorted(paths, key=lambda p: p["ts"]):
        t = D.calendar.timegm(time.strptime(p["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
        open_until = [u for u in open_until if u > t]
        if len(open_until) >= max_open:
            continue
        tr = replay(p, rule)
        if tr:
            out.append(tr)
            open_until.append(t + rule["hold"])
    return out


def diff_ci(a, b, k=400):
    """Bootstrap 90 % interval for mean(a) - mean(b)."""
    if len(a) < MIN_SIDE or len(b) < MIN_SIDE:
        return None
    rnd = random.Random(7)
    ds = []
    for _ in range(k):
        sa = [rnd.choice(a) for _ in range(len(a))]
        sb = [rnd.choice(b) for _ in range(len(b))]
        ds.append(st.mean(sa) - st.mean(sb))
    ds.sort()
    return ds[int(0.05 * k)], ds[int(0.95 * k)]


def span_days(paths):
    ts = [time.mktime(time.strptime(p["ts"][:19], "%Y-%m-%dT%H:%M:%S")) for p in paths]
    return max(1 / 24, (max(ts) - min(ts)) / 86400) if ts else 1 / 24


def limiting_factor(paths, ctrl, ctrl_book, live, days):
    """The one stage to work on, read in order: the rate of entries, then the edge, then the fill, then the exits.
    The rate is read over the hours the paths actually cover, not calendar days (an hour of paths is not a day)."""
    per_day = ctrl["n"] / span_days(paths)
    if per_day < 40:
        return f"RATE: the contract enters {per_day:.0f} a day on the paths; under 40 a day the leg cannot reach a verdict in a week. The news window or the match rule is the constraint, not the exit."
    if ctrl["n"] and ctrl["mean"] <= 0:
        first = [t["pct"] for t in ctrl_book if t["t_in"] == 0]
        return f"EDGE: mean net {ctrl['mean']:+.3f} SOL on {ctrl['n']} control trades. The loop as written does not pay on this tape; variants that change the entry or the filter are the ones to read, not the exits."
    if ctrl["stop_share"] > 0.6:
        return f"EXITS: {ctrl['stop_share']:.0%} of control trades leave on the stop. Mean net is positive but the stop dominates; the hold and the stop width are the variables to read."
    return f"COUNT: the control is positive ({ctrl['mean']:+.3f} SOL mean on {ctrl['n']}) with {per_day:.0f} entries a day; nothing binds but the number of closes. Let the count run."


def main(days):
    paths = load_paths(days)
    if not paths:
        print("no paths yet"); return
    day_set = sorted(set(p["ts"][:10] for p in paths))
    rows, trades = [], {}
    for v in [CONTROL] + VARIANTS:
        rule = rule_of(v)
        tr = [t for t in (replay(p, rule) for p in paths) if t]
        trades[v["name"]] = tr
        rows.append((v["name"], stats(tr)))
    ctrl = rows[0][1]
    ctrl_book = book_constrained(paths, CONTROL)
    cb = stats(ctrl_book)
    live_closes = [r for r in C.read_jsonl(C.path("journal", "paper.jsonl")) if r.get("kind") == "close"]
    live = stats([{"net": r["net_sol"], "pct": r["exits"][-1]["pct"], "why": r["exits"][-1]["why"], "peak": 0, "trough": 0, "t_in": 0} for r in live_closes])

    # per-day results for the promotion rule
    state = C.load_json(STATE, {})
    for d in day_set:
        dp = [p for p in paths if p["ts"][:10] == d]
        ctrl_d = stats([t for t in (replay(p, CONTROL) for p in dp) if t])
        for v in VARIANTS:
            s = stats([t for t in (replay(p, rule_of(v)) for p in dp) if t])
            state.setdefault(v["name"], {})[d] = {"n": s.get("n", 0), "mean": s.get("mean"), "ctrl_n": ctrl_d.get("n", 0), "ctrl_mean": ctrl_d.get("mean"),
                                                  "beat": bool(s.get("n", 0) >= PROMOTE_N and ctrl_d.get("n", 0) >= PROMOTE_N and s["mean"] > ctrl_d["mean"])}
    C.save_json(STATE, state)
    candidates = []
    for v in VARIANTS:
        hist = state.get(v["name"], {})
        last = [hist[d] for d in sorted(hist)[-PROMOTE_DAYS:]]
        if len(last) == PROMOTE_DAYS and all(x["beat"] for x in last):
            candidates.append(v["name"])

    L = [f"# The population · {C.iso()} · {len(paths)} launches over {len(day_set)} day(s) ({', '.join(day_set)})", ""]
    funnel = {"launches": len(paths), "pump suffix": sum(1 for p in paths if p["mint"].endswith("pump")), "news-matched": sum(1 for p in paths if p["match"]),
              "matched & < $10K & plain pump": sum(1 for p in paths if replay(p, CONTROL) is not None),
              "live entries": sum(1 for r in C.read_jsonl(C.path("journal", "paper.jsonl")) if r.get("kind") == "entry"), "live closes": len(live_closes)}
    L.append("## Funnel"); L += [f"- {k}: {v}" for k, v in funnel.items()]; L.append("")
    L.append("## Limiting factor"); L.append(limiting_factor(paths, ctrl, ctrl_book, live, len(day_set))); L.append("")
    L.append("## The hypothesis: does the headline match matter?")
    a = [t["net"] for t in trades["control (RI-04)"]]; b = [t["net"] for t in trades["unmatched only"]]
    ci = diff_ci(a, b)
    if ci:
        L.append(f"matched mean {st.mean(a):+.4f} SOL (n={len(a)}) vs unmatched {st.mean(b):+.4f} (n={len(b)}); difference 90 % interval "
                 f"[{ci[0]:+.4f}, {ci[1]:+.4f}] SOL → {'news matters (interval above 0)' if ci[0] > 0 else 'news hurts (interval below 0)' if ci[1] < 0 else 'undecided'}")
    else:
        L.append(f"not enough trades a side yet (matched {len(a)}, unmatched {len(b)}; need {MIN_SIDE} each)")
    L.append("")
    L.append("## Books (same tape, same fees, unconstrained by the 3-open limit)")
    L.append("| book | n | win | mean SOL | sum SOL | PF | mean loss | stops | takes | med % |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for name, s in rows:
        if s["n"]:
            L.append(f"| {name} | {s['n']} | {s['win']:.0%} | {s['mean']:+.4f} | {s['sum']:+.1f} | {s['pf']:.2f} | {s['mean_loss']:.3f} | {s['stop_share']:.0%} | {s['take_share']:.0%} | {s['med_pct']:+.1%} |")
        else:
            L.append(f"| {name} | 0 | | | | | | | | |")
    L.append("")
    if cb["n"]:
        L.append(f"Control as the live book would run it (max {D.MAX_OPEN} open): n={cb['n']} win={cb['win']:.0%} mean={cb['mean']:+.4f} sum={cb['sum']:+.1f} SOL")
    if live["n"]:
        L.append(f"Live book, counted: n={live['n']} win={live['win']:.0%} mean={live['mean']:+.4f} sum={live['sum']:+.1f} SOL (the replay and the book should agree; a gap is a measurement lesson)")
    L.append("")
    L.append(f"## Promotion rule: beat the control on mean net on each of the last {PROMOTE_DAYS} days with ≥ {PROMOTE_N} trades a day")
    L.append(("Candidates for the next contract id (ruled through RI, never automatic): " + ", ".join(candidates)) if candidates else "No candidate yet.")
    streaks = {v["name"]: sum(1 for d in sorted(state.get(v["name"], {}))[-PROMOTE_DAYS:] if state[v["name"]][d]["beat"]) for v in VARIANTS}
    L.append("Days beaten of the last " + str(PROMOTE_DAYS) + ": " + ", ".join(f"{k} {n}" for k, n in sorted(streaks.items(), key=lambda kv: -kv[1]) if n))
    text = "\n".join(L)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    main(a.days)
