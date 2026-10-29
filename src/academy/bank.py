"""The bank: realised SOL and USD per day from fills only (journal/probe.jsonl rows that landed, net_sol on the row, fees and rent
included). The wallet's mark is never scored. Capital is what the operator funded (FUNDED), so the figure is per unit deposited per day."""
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C   # noqa: E402

FUNDED_SOL = 0.116       # 2026-10-28 05:20Z, the fill probe wallet


def ledger(fills, sol_usd):
    days = defaultdict(lambda: {"legs": 0, "sol": 0.0})
    for f in fills:
        if f.get("net") is None:
            continue
        d = days[f["ts"][:10]]
        d["legs"] += 1; d["sol"] += f["net"]
    out, cum = [], 0.0
    for day in sorted(days):
        cum += days[day]["sol"]
        out.append({"day": day, "legs": days[day]["legs"], "sol": days[day]["sol"], "usd": days[day]["sol"] * sol_usd, "cum_sol": cum,
                    "per_unit": days[day]["sol"] / FUNDED_SOL})
    return out


def sol_usd():
    return (C.load_json(C.path("state", "sol_usd.json"), {}) or {}).get("usd") or 0.0
