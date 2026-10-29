"""The search, which is the strategist: each round proposes cells from the roster (the forks, mutations of the roster's best, and
random cells from the grid), scores every one on the fit period and the strictly later held-out period, corrects it with the answer
term, and keeps the roster. A round only runs when the record has grown by PACE launches since the last one (research loops are
paced by experiments, not thinking). Every figure on the roster is the arena's own number; nothing is hand-entered.

Multiple comparisons are the search's own hazard: among K cells positive on the fit period, about 5 % pass a one-sided 95 % bound on
a held-out period by luck. The roster carries K and that expectation beside any candidate, so a lone pass reads as what it is.
"""
import random

import numpy as np

from . import answer as AN
from . import arena as A
from . import cells as CE
from . import rungs as RU

PACE = 50
N_RANDOM = 300
N_MUTATE = 20
MUTATIONS = 5
TOP = 40


def split(labels):
    """Fit = every day but the last; held-out = the last day (today, growing all day). Strictly later, never overlapping."""
    days = sorted(set(labels))
    held = days[-1]
    return (labels != held), (labels == held), days[:-1], held


def evaluate(rec, labels, cell, fills):
    fit_m, held_m, _, _ = split(labels)
    s = A.score(rec, cell)
    net, why = s["net"], s["why"]
    row = {"id": cell["id"], "name": cell["name"], "cell": cell, "describe": CE.describe(cell),
           "all": A.stats(net, why), "fit": A.stats(net[fit_m], why[fit_m]), "held": A.stats(net[held_m], why[held_m]),
           "held_lb": A.boot_lb(net[held_m]), "by_day": A.per_day(net, labels)}
    ans = AN.answered(rec, s, cell, fills)
    row.update({"answered": ans["answered"], "correction": ans.get("correction"), "mix": ans["mix"]})
    row["eligible"], row["not_eligible_why"] = RU.eligible(row)
    return row


def propose(roster, round_no, rnd):
    """The round's cells: the forks always, mutations of the roster's best on the fit period, and fresh random cells."""
    out = {c["id"]: c for c in CE.forks()}
    best = sorted((r for r in roster.values() if (r.get("fit") or {}).get("n", 0) >= RU.FIT_N), key=lambda r: -r["fit"]["mean"])[:N_MUTATE]
    for r in best:
        for _ in range(MUTATIONS):
            c = CE.mutate(r["cell"], rnd)
            out.setdefault(c["id"], c)
    for _ in range(N_RANDOM):
        c = CE.random_cell(rnd)
        out.setdefault(c["id"], c)
    return list(out.values())


def run_round(rec, labels, roster, round_no, fills, seed=None):
    rnd = random.Random(seed if seed is not None else round_no)
    cells = propose(roster, round_no, rnd)
    for c in cells:
        row = evaluate(rec, labels, c, fills)
        prev = roster.get(c["id"], {})
        row["rounds"] = prev.get("rounds", 0) + 1
        row["first_round"] = prev.get("first_round", round_no)
        row["last_round"] = round_no
        roster[c["id"]] = row
    # every older roster cell is rescored too: the held-out day grows all day, and a cell is judged on the latest record
    for cid, r in list(roster.items()):
        if r.get("last_round") != round_no:
            row = evaluate(rec, labels, r["cell"], fills)
            row.update({"rounds": r.get("rounds", 0), "first_round": r.get("first_round", round_no), "last_round": round_no})
            roster[cid] = row
    return roster, len(cells)


def tally(roster):
    rows = list(roster.values())
    fit_pos = [r for r in rows if (r.get("fit") or {}).get("n", 0) >= RU.FIT_N and r["fit"]["mean"] > 0]
    held_pos = [r for r in fit_pos if (r.get("held") or {}).get("n", 0) >= RU.HELD_N and r["held"]["mean"] > 0]
    passed = [r for r in rows if r.get("eligible")]
    return {"cells": len(rows), "fit_pos": len(fit_pos), "held_pos": len(held_pos), "eligible": len(passed),
            "expected_by_luck": round(0.05 * len(fit_pos), 2), "best_fit": max(rows, key=lambda r: (r["fit"]["mean"] if r["fit"]["n"] else -9)) if rows else None,
            "best_held": max((r for r in rows if r["held"]["n"] >= RU.HELD_N), key=lambda r: r["held"]["mean"], default=None)}


def trim(roster, keep=TOP):
    """Keep the forks, the eligible, and the best `keep` on the fit period; the rest are spun down."""
    forks = {c["id"] for c in CE.forks()}
    ranked = sorted(roster.values(), key=lambda r: -(r["fit"]["mean"] if r["fit"]["n"] >= RU.FIT_N else -9))
    keep_ids = forks | {r["id"] for r in ranked[:keep]} | {r["id"] for r in roster.values() if r.get("eligible")}
    return {k: v for k, v in roster.items() if k in keep_ids}
