"""The 5 % loop replayed on the tape (observation only; nothing here trades or counts).

Walks the recorded paths (journal/paths/<day>.jsonl) and the hour's terms (journal/news/<day>.jsonl) in time order, so the meta
gate, the catalyst clock and the comparables know at each launch only what had finished before it. Runs RI-05 (src/five.py) and
RI-04's control (ops/population.py, the same curve arithmetic and fees) over the same launches, then splits the control by the
loop's own reads: gate state, class, catalyst age, comparable. That is the test of each rule as a hypothesis on RI-04's loop,
before any rule is frozen.

  python ops/five_replay.py [--days 4]      -> out/five.md, state/five_replay.json
"""
import argparse
import calendar
import collections
import glob
import json
import os
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "ops"))
import common as C        # noqa: E402
import duval as D         # noqa: E402
import five as F          # noqa: E402
import population as P    # noqa: E402

OUT = C.path("out", "five.md")
STATE = C.path("state", "five_replay.json")


def epoch(iso):
    return calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))


def load(days):
    paths, news = [], []
    for f in sorted(glob.glob(os.path.join(C.ROOT, "journal", "paths", "*.jsonl")))[-days:]:
        paths += lines(f)
    for f in sorted(glob.glob(os.path.join(C.ROOT, "journal", "news", "*.jsonl")))[-days:]:
        news += lines(f)
    return paths, news


def lines(f):
    """JSON rows of a file the engine may still be appending to (bytes, so a torn last line or a locked tail cannot raise)."""
    out = []
    try:
        with open(f, "rb") as fh:
            data = fh.read()
    except OSError as e:                       # the engine holds the tail open; a locked read is a short day, not a crash
        print(f"[five_replay] could not read {f}: {e}", file=sys.stderr)
        return out
    for raw in data.splitlines():
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw.decode("utf-8", "ignore")))
        except Exception:
            continue
    return out


def stats(trades):
    n = len(trades)
    if not n:
        return {"n": 0}
    nets = [t["net"] for t in trades]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    return {"n": n, "win": len(wins) / n, "mean": st.mean(nets), "sum": sum(nets), "med_pct": st.median(t["pct"] for t in trades),
            "pf": (sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else float("inf"), "mean_loss": (-st.mean(losses)) if losses else 0.0}


def row(name, s):
    if not s["n"]:
        return f"| {name} | 0 | | | | | |"
    return f"| {name} | {s['n']} | {s['win']:.0%} | {s['mean']:+.4f} | {s['sum']:+.1f} | {s['pf']:.2f} | {s['med_pct']:+.1%} |"


def main(days):
    paths, news = load(days)
    if not paths:
        print("no paths"); return
    events = []
    for p in paths:
        t0 = epoch(p["ts"])
        p["_t0"] = t0
        p["_end"] = t0 + (p["complete"] if p.get("complete") is not None else F.HOLD_S)
        events.append((t0, 1, "launch", p))
        events.append((p["_end"], 0, "done", p))
    for r in news:
        events.append((epoch(r["ts"]), -1, "news", r))
    events.sort(key=lambda e: (e[0], e[1]))

    meta, terms, comps = F.Meta(), F.Terms(), F.Comparables()
    open_until = []            # (t_end, terms) of the loop's open positions
    stake, cum, peak_cum = F.SIZE_SOL, 0.0, 0.0
    five_trades, reads = [], []
    ctrl_rows = []             # (p, control trade or None, read)
    # the gate and the catalyst at absolute time, for run_position
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
        # a launch at its first mark
        open_until = [(u, tt) for (u, tt) in open_until if u > t]
        open_terms = set(x for _, tt in open_until for x in tt)
        full_book = len(open_until) >= F.MAX_OPEN
        k5, size, read = F.decide(p, t, meta, terms, comps, open_terms, stake)
        ctrl = P.replay(p, P.CONTROL)
        read["ctrl"] = ctrl
        reads.append((p, read))
        if not k5 or full_book:
            if k5 and full_book:
                read["skip"] = "book full"
            continue
        p_terms = list(p["match"])
        tr = F.run_position(p["marks"], 0, size, k5, lambda ta: any(terms.alive(x, ta) for x in p_terms), lambda ta: meta.state(ta)[0], t)
        if not tr:
            continue
        tr["mint"], tr["name"], tr["ts"], tr["read"] = p["mint"], p["name"], p["ts"], read
        five_trades.append(tr)
        open_until.append((t + tr["held"], p_terms))
        cum += tr["net"]
        peak_cum = max(peak_cum, cum)
        if peak_cum - cum >= F.RESET_DD and stake > F.SIZE_SOL / 2:
            stake = F.SIZE_SOL / 2

    ctrl_all = [r["ctrl"] for _, r in reads if r["ctrl"]]
    day_set = sorted(set(p["ts"][:10] for p in paths))
    L = [f"# The 5 % loop on the tape · {C.iso()} · {len(paths)} launches over {len(day_set)} day(s) ({', '.join(day_set)})", ""]
    L += ["## Books (same tape, same fees)", "", "| book | n | win | mean SOL | sum SOL | PF | med % |", "|---|---|---|---|---|---|---|"]
    L.append(row("RI-04 control (all its entries)", stats(ctrl_all)))
    L.append(row("RI-05 the 5 % loop (max 3 open)", stats(five_trades)))
    for k in ("full", "scalp"):
        L.append(row(f"  RI-05 {k}", stats([t for t in five_trades if t["kind"] == k])))
    L.append(row("  RI-05 full, stake taken out", stats([t for t in five_trades if t["kind"] == "full" and t["stake_out"]])))
    L.append("")
    # per day
    L += ["### By day", "", "| day | control n | control mean | RI-05 n | RI-05 mean | RI-05 sum |", "|---|---|---|---|---|---|"]
    for d in day_set:
        c = stats([r["ctrl"] for p, r in reads if r["ctrl"] and p["ts"][:10] == d])
        f = stats([t for t in five_trades if t["ts"][:10] == d])
        L.append(f"| {d} | {c['n']} | {c.get('mean', 0):+.4f} | {f['n']} | {f.get('mean', 0):+.4f} | {f.get('sum', 0):+.1f} |")
    L.append("")
    # the reads as hypotheses on the control
    L += ["## Each rule as a hypothesis on RI-04's own loop (control trades split by the loop's read at entry)", ""]
    L += ["| split | n | win | mean SOL | sum SOL | PF | med % |", "|---|---|---|---|---|---|---|"]
    by = collections.defaultdict(list)
    for p, r in reads:
        if not r["ctrl"]:
            continue
        by[f"L1 gate {r['gate']}"].append(r["ctrl"])
        by[f"L2 class {r['class']}"].append(r["ctrl"])
        a = r.get("catalyst_age_s")
        by["L3 catalyst " + ("unknown" if a is None else "fresh (<30 min)" if a <= F.CATALYST_FRESH_S else "stale")].append(r["ctrl"])
        n = r.get("comparable_n")
        if n is not None:
            by["L3 comparable " + ("blank" if n == 0 else "ran" if (r.get("comparable_ceiling") or 0) >= F.RUNNER_MULT else "never ran")].append(r["ctrl"])
        if r.get("vamp") is not None:
            by["N3 vamp " + ("yes" if r["vamp"] else "no")].append(r["ctrl"])
    for k in sorted(by):
        L.append(row(k, stats(by[k])))
    L.append("")
    # dev class by init_sol bucket on the control, the one threshold the tape must set
    L += ["### The dev class: control by the creator's buy at create", "", "| init_sol | n | win | mean SOL | sum SOL | PF | med % |", "|---|---|---|---|---|---|---|"]
    bk = collections.defaultdict(list)
    for p, r in reads:
        if r["ctrl"]:
            s = p.get("init_sol") or 0
            bk["0" if s <= 0.01 else "<0.5" if s < 0.5 else "<1" if s < 1 else "<2" if s < 2 else "<5" if s < 5 else ">=5"].append(r["ctrl"])
    for k in ["0", "<0.5", "<1", "<2", "<5", ">=5"]:
        L.append(row(k, stats(bk[k])))
    L.append("")
    # why the loop did not enter
    skips = collections.Counter(r.get("skip", "entered") for _, r in reads)
    L += ["## Why the loop did not enter (every launch)", ""] + [f"- {k}: {v}" for k, v in skips.most_common()] + [""]
    # the loop's exits and the stage that loses
    L += ["## RI-05 exits (trigger that closed the position)", "", "| trigger | n | win | mean SOL | sum SOL | PF | med % |", "|---|---|---|---|---|---|---|"]
    ex = collections.defaultdict(list)
    for t in five_trades:
        ex[t["why"]].append(t)
    for k in sorted(ex, key=lambda k: stats(ex[k])["sum"]):
        L.append(row(k, stats(ex[k])))
    L.append("")
    losses = [t for t in five_trades if t["net"] <= 0]
    stage = collections.Counter()
    for t in losses:
        stage[t["why"]] += -t["net"]
    if stage:
        worst = stage.most_common(1)[0]
        L.append(f"**The most broken stage:** {worst[0]} ({worst[1]:.1f} SOL of {sum(stage.values()):.1f} SOL lost). One patch there, through RI, before any other.")
    L.append("")
    # phases at exit
    ph = collections.Counter(t["phase"] for t in five_trades)
    L.append("S-curve phase at the loop's exit: " + ", ".join(f"{k} {v}" for k, v in ph.most_common()))
    L.append("")
    # the biggest trades
    L += ["## The loop's ten best and ten worst", "", "| ts | name | kind | net | pct | why | peak | held | read |", "|---|---|---|---|---|---|---|---|---|"]
    for t in sorted(five_trades, key=lambda t: -t["net"])[:10] + sorted(five_trades, key=lambda t: t["net"])[:10]:
        rd = t["read"]
        L.append(f"| {t['ts'][11:19]} | {t['name'][:24]} | {t['kind']} | {t['net']:+.3f} | {t['pct']:+.1%} | {t['why']} | {t['peak']:+.1%} | {t['held']} | "
                 f"gate {rd.get('runner_share_1h')} age {rd.get('catalyst_age_s')} comp {rd.get('comparable_n')}/{rd.get('comparable_ceiling')} |")
    text = "\n".join(L)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    C.save_json(STATE, {"ts": C.iso(), "days": day_set, "control": stats(ctrl_all), "five": stats(five_trades),
                        "by_day": {d: stats([t for t in five_trades if t["ts"][:10] == d]) for d in day_set},
                        "skips": dict(skips), "exits": {k: stats(v) for k, v in ex.items()}})
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    main(a.days)
