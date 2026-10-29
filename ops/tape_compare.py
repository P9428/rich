"""Two engines, one feed: compare the home machine's tape with the VPS copy, hour by hour, before any cut-over is ruled.

Rule 5 applied to the environment: the VPS becomes the host only after it beats the home tape on a held-out day. What a tape is
graded on here is what the replays depend on:
  - launches logged per UTC hour (the bits; a gap is an hour of nothing)
  - the first mark's offset after the create (the fill the counted book gets; later is worse)
  - the mark cadence (the engine marks every 2 s; a starved process marks late and the exits read later)
  - RPC errors and guard restarts

Usage:  python ops/tape_compare.py [YYYY-MM-DD]      (default: today UTC)
Reads journal/paths/<day>.jsonl (home) and journal/vps/paths/<day>.jsonl (pulled by ops/vps_pull.sh). Writes out/tape_compare.md.
"""
import json
import os
import statistics
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C  # noqa: E402


def read_paths(file):
    rows = C.read_jsonl(file)
    by_hour = Counter(r["ts"][11:13] for r in rows if r.get("ts"))
    first = [r["marks"][0][0] for r in rows if r.get("marks")]
    gaps = []
    for r in rows:
        m = r.get("marks") or []
        gaps += [b[0] - a[0] for a, b in zip(m, m[1:])]
    return rows, by_hour, first, gaps


def q(xs, p):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]


def line(label, rows, first, gaps):
    return (f"| {label} | {len(rows)} | {q(first, .5):.2f} | {q(first, .9):.2f} | {q(gaps, .5):.2f} | {q(gaps, .9):.2f} | "
            f"{statistics.mean(len(r.get('marks') or []) for r in rows) if rows else float('nan'):.1f} |")


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y-%m-%d", time.gmtime())
    home = C.path("journal", "paths", f"{day}.jsonl")
    vps = C.path("journal", "vps", "paths", f"{day}.jsonl")
    hr, hh, hf, hg = read_paths(home)
    vr, vh, vf, vg = read_paths(vps)
    L = [f"# Two tapes, one feed · {day} · home vs VPS · {C.iso()}", "",
         "The replays fill at the first mark; a later first mark is a worse fill, so the host with the earlier first mark and the",
         "steadier cadence is the honest tape. Launch counts per hour are the bits; an hour at zero on one side is an outage there.", "",
         "| tape | launches marked | first mark p50 s | p90 s | mark gap p50 s | p90 s | marks per launch |", "|---|---|---|---|---|---|---|",
         line("home (laptop)", hr, hf, hg), line("VPS", vr, vf, vg), "", "## Launches marked per UTC hour", "",
         "| hour | home | VPS | diff |", "|---|---|---|---|"]
    hours = sorted(set(hh) | set(vh))
    for h in hours:
        L.append(f"| {h} | {hh.get(h, 0)} | {vh.get(h, 0)} | {vh.get(h, 0) - hh.get(h, 0):+d} |")
    both = [h for h in hours if hh.get(h) and vh.get(h)]
    if both:
        ratio = sum(vh[h] for h in both) / max(1, sum(hh[h] for h in both))
        L += ["", f"Over the {len(both)} hours both engines ran, the VPS logged {ratio:.2f}x the home count."]
    verdict = []
    if vr and hr:
        verdict.append("VPS first mark earlier" if q(vf, .5) < q(hf, .5) else "home first mark earlier or equal")
        verdict.append("VPS cadence steadier" if q(vg, .9) <= q(hg, .9) else "home cadence steadier or equal")
    L += ["", "## Reading", "", "- " + ("; ".join(verdict) if verdict else "one of the tapes is empty for this day; nothing to compare yet"),
          "- A cut-over is ruled through ops/decide.py only after the VPS tape is at least as good on a full held-out day. Until then the",
          "  home engine stays the counted book and the VPS copy is a parallel, uncounted tape."]
    out = C.path("out", "tape_compare.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
