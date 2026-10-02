"""Daily readout: closed paper trades against the contract's loss-first gates. Writes out/readout.txt and prints it."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C  # noqa: E402

closes = [r for r in C.read_jsonl(C.path("journal", "paper.jsonl")) if r.get("kind") == "close"]
events = C.read_jsonl(C.path("journal", "events.jsonl"))
opens = C.load_json(C.path("state", "positions.json"), [])
nets = [r["net_sol"] for r in closes]
n = len(nets)
wins = sum(1 for x in nets if x > 0)
losses = [x for x in nets if x <= 0]
streak = 0
for x in reversed(nets):
    if x <= 0:
        streak += 1
    else:
        break
peak = dd = cum = 0.0
for x in nets:
    cum += x
    peak = max(peak, cum)
    dd = max(dd, peak - cum)
mean = sum(nets) / n if n else 0.0
mean_loss = -sum(losses) / len(losses) if losses else 0.0
verdict, why = "INSUFFICIENT", f"{n}/40 closed trades"
if streak >= 10:
    verdict, why = "KILL", f"G1 {streak} consecutive losers"
elif dd > 8:
    verdict, why = "KILL", f"G2 drawdown {dd:.2f} SOL"
elif n >= 40 and wins / n < 0.25:
    verdict, why = "KILL", f"G3 win rate {wins/n:.0%}"
elif n >= 40 and mean <= 0:
    verdict, why = "KILL", f"G4 mean net {mean:+.3f} SOL"
elif n >= 40 and mean > 0 and mean_loss < 0.3:
    verdict, why = "SURVIVES ON PAPER", f"S1 mean {mean:+.3f}, mean loss {mean_loss:.3f}"
elif n >= 40:
    verdict, why = "ALIVE, S1 NOT MET", f"mean {mean:+.3f}, mean loss {mean_loss:.3f} (needs < 0.3)"
feeds = {}
for e in events:
    feeds[e["feed"]] = feeds.get(e["feed"], 0) + 1
passed = sum(1 for e in events for s in e.get("screen", []) if s["pass"])
lines = [
    f"rich readout {C.iso()}  contract RI-01",
    f"events {len(events)} by feed {feeds}; resolved {sum(1 for e in events if e.get('accepted'))}; screen passes {passed}",
    f"paper: closed {n}, open {len(opens)}, wins {wins}, cum {cum:+.3f} SOL, mean {mean:+.3f}, mean loss {mean_loss:.3f}, max dd {dd:.3f}, loss streak {streak}",
    f"VERDICT {verdict}: {why}",
]
if not os.environ.get("X_BEARER"):
    lines.append("gap: X feed dormant (no X_BEARER); 11 of 14 ledger triggers lived on X")
text = "\n".join(lines)
with open(C.path("out", "readout.txt"), "w", encoding="utf-8") as f:
    f.write(text + "\n")
print(text)
