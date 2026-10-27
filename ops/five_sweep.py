"""Sweep the RI-05 stop on the same tape and the same entries (observation only; the source of F01 in
decisions/2026-10-27-ri05-stop-stage).

Fills at the first on-chain mark, the state the first replay used, so the sweep answers the question as it was asked: does any
stop level or arming delay move the first-mark book above water. It did not (-3.0 to -4.3 SOL for the full book at every setting),
and the entry state was the cause; see five.entry_marks. Pass --message to sweep at the message's reserves instead.

  python ops/five_sweep.py [--days 5] [--message]
"""
import argparse
import collections
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "ops"))
import five as F          # noqa: E402
import five_replay as R   # noqa: E402
import duval as D         # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=5)
ap.add_argument("--message", action="store_true", help="fill at the message's reserves (five.entry_marks) instead of the first mark")
A = ap.parse_args()
sys.stdout.reconfigure(encoding="utf-8")

paths, news = R.load(A.days)
events = []
for p in paths:
    t0 = R.epoch(p["ts"])
    p["_t0"] = t0
    p["_end"] = t0 + (p["complete"] if p.get("complete") is not None else F.HOLD_S)
    events.append((t0, 1, "launch", p))
    events.append((p["_end"], 0, "done", p))
for r in news:
    events.append((R.epoch(r["ts"]), -1, "news", r))
events.sort(key=lambda e: (e[0], e[1]))


def marks_of(p):
    return F.entry_marks(p) if A.message else p["marks"]


def run(stop, arm_s=0.0, scalp_stop=F.SCALP_STOP):
    """One pass of the loop with the full-size stop at `stop` (None = no stop), armed only after arm_s seconds."""
    F.STOP = -9 if stop is None else stop
    F.SCALP_STOP = scalp_stop
    meta, terms, comps = F.Meta(), F.Terms(), F.Comparables()
    open_until, stake = [], F.SIZE_SOL
    trades = []
    for t, _, kind, obj in events:
        if kind == "news":
            terms.update(obj["terms"], t)
            continue
        p = obj
        if kind == "done":
            if p["mint"].endswith("pump") and p["marks"] and p["marks"][0][1] > 0:
                pk = F.peak_mult(p)
                meta.add(t, pk >= F.RUNNER_MULT)
                if p["match"]:
                    comps.add(p["_t0"], p["match"], pk)
            continue
        open_until = [(u, tt) for (u, tt) in open_until if u > t]
        open_terms = set(x for _, tt in open_until for x in tt)
        if len(open_until) >= F.MAX_OPEN:
            continue
        k5, size, read = F.decide(p, t, meta, terms, comps, open_terms, stake)
        if not k5:
            continue
        p_terms = list(p["match"])
        alive = lambda ta: any(terms.alive(x, ta) for x in p_terms)   # noqa: E731
        gate = lambda ta: meta.state(ta)[0]                            # noqa: E731
        if arm_s and k5 == "full":
            tr = run_armed(marks_of(p), size, k5, alive, gate, t, stop, arm_s)
        else:
            tr = F.run_position(marks_of(p), 0, size, k5, alive, gate, t)
        if not tr:
            continue
        tr["name"], tr["read"] = p["name"], read
        trades.append(tr)
        open_until.append((t + tr["held"], p_terms))
    return trades


def run_armed(marks, size, k5, alive, gate, t, stop, arm_s):
    """The stop armed only after arm_s seconds. Run with the stop; if it stopped before arm_s, run again with no stop (the
    position survived the early dip) and then book a stop at the first mark after arm_s whose mark-to-curve value is under the
    line (approximation: net = pct * size at that mark)."""
    F.STOP = stop
    tr = F.run_position(marks, 0, size, k5, alive, gate, t)
    if tr and tr["why"] == "stop" and tr["held"] < arm_s:
        F.STOP = -9
        tr2 = F.run_position(marks, 0, size, k5, alive, gate, t)
        c = D.net_in(size)
        tokens = D.buy(marks[0][1], marks[0][2], size)
        for m in marks[1:]:
            if m[2] <= 0 or m[0] < arm_s:
                continue
            k = m[1] * m[2]
            vs = m[1] + c
            pct = D.sell(vs, k / vs, tokens) / size - 1
            if pct <= stop:
                tr2 = dict(tr2, net=round(pct * size, 4), pct=round(pct, 4), why="stop", held=round(m[0], 1))
                break
        tr = tr2
    F.STOP = stop
    return tr


def stats(tr):
    if not tr:
        return "n=0"
    nets = [t["net"] for t in tr]
    w = [n for n in nets if n > 0]
    l = [n for n in nets if n <= 0]
    pf = (sum(w) / -sum(l)) if l and sum(l) < 0 else float("inf")
    ex = collections.Counter(t["why"] for t in tr)
    return f"n={len(tr):3d} win={len(w)/len(tr):4.0%} mean={st.mean(nets):+.4f} sum={sum(nets):+6.1f} PF={pf:4.2f} exits={dict(ex)}"


print(f"fill: {'message reserves (as the counted book)' if A.message else 'first on-chain mark'}")
base = run(F.STOP)
full = [t for t in base if t["kind"] == "full"]
print("BASE full :", stats(full))
print("BASE scalp:", stats([t for t in base if t["kind"] == "scalp"]))
stops = [t for t in base if t["why"] == "stop"]
if stops:
    print(f"stops {len(stops)}: held median {st.median([t['held'] for t in stops]):.1f}s, pct median {st.median([t['pct'] for t in stops]):+.3f}, "
          f"peak>0 in {sum(1 for t in stops if t['peak'] > 0)}, held<=6s in {sum(1 for t in stops if t['held'] <= 6)}")
print("\n=== stop sweep, full-size positions (scalps unchanged at RI-04's exits) ===")
for stop in (-0.05, -0.08, -0.10, -0.15, -0.20, -0.30, None):
    tr = run(stop)
    print(f"stop {str(stop):>5}: full {stats([t for t in tr if t['kind'] == 'full'])}")
    print(f"             all  {stats(tr)}")
print("\n=== stop armed late (no stop before arm_s, then -10 %) ===")
for arm in (10, 20, 30):
    tr = run(-0.10, arm_s=arm)
    print(f"arm {arm:2d}s: full {stats([t for t in tr if t['kind'] == 'full'])}")
print("\n=== scalp stop sweep (full fixed at -5 %) ===")
for ss in (-0.05, -0.10, -0.20):
    tr = run(-0.05, scalp_stop=ss)
    print(f"scalp stop {ss}: scalp {stats([t for t in tr if t['kind'] == 'scalp'])}")
