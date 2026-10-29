"""The ladder: six size rungs from 0.01 SOL to the contract's 1.5 SOL. The only way from paper to size, one rung at a time, and
nothing here places an order.

eligible   the arena says a cell is positive on the fit period AND on the strictly later held-out period (each with enough trades),
           its bootstrap lower bound on the held-out mean is above zero, and the answered mean is positive
rung 0     only by a ruling under decisions/ naming the cell id (promote(state, cell_id, slug)); the code never promotes
climb      a group of GROUP real legs at the rung whose mean residual is inside TOL and whose mean real net is positive
kill       the upper confidence bound of the real net at the rung is below zero (n >= GROUP), or the residual is wrong by twice TOL
           (the simulator is wrong about this cell at this size), or the cell stops being eligible on the arena

State: state/academy/ladder.json  {cell_id: {rung, status, promoted_by, legs: [...], history: [...]}}
"""
import math

from . import residual as RS

RUNGS = [0.01, 0.03, 0.10, 0.30, 1.00, 1.50]
GROUP = 12
Z = 1.64
FIT_N = 100
HELD_N = 30


def eligible(row):
    """row: a roster row with fit, held and answered stats."""
    fit, held = row.get("fit") or {}, row.get("held") or {}
    why = []
    if (fit.get("n") or 0) < FIT_N:
        why.append(f"fit n {fit.get('n', 0)} < {FIT_N}")
    elif fit["mean"] <= 0:
        why.append(f"fit mean {fit['mean']:+.4f} <= 0")
    if (held.get("n") or 0) < HELD_N:
        why.append(f"held-out n {held.get('n', 0)} < {HELD_N}")
    elif held["mean"] <= 0:
        why.append(f"held-out mean {held['mean']:+.4f} <= 0")
    elif row.get("held_lb") is None or row["held_lb"] <= 0:
        why.append(f"held-out lower bound {row.get('held_lb')} <= 0")
    if row.get("answered") is None or row["answered"] <= 0:
        why.append(f"answered mean {row.get('answered')} <= 0")
    return (not why), why


def promote(state, cell_id, slug):
    """Rung 0 for a cell, by a ruling. The slug is the decisions/ file that ruled it."""
    state[cell_id] = {"rung": 0, "status": "rung", "promoted_by": slug, "legs": [], "history": [{"what": "promoted to rung 0", "by": slug}]}
    return state


def update(state, cell_id, legs):
    """Fold the real legs tagged with this cell at its current rung into the ladder: climb, hold or kill."""
    s = state.get(cell_id)
    if not s or s["status"] != "rung":
        return state
    size = RUNGS[s["rung"]]
    at = [l for l in legs if l.get("resid") is not None and abs(l["size"] - size) < 1e-9]
    s["legs"] = [{"ts": l["ts"], "mint": l["mint"], "real": l["real"], "pred": l["pred"]} for l in at]
    n = len(at)
    if n < GROUP:
        s["note"] = f"{n} of {GROUP} legs at rung {s['rung']} ({size} SOL)"
        return state
    reals = [l["real"] for l in at]
    mean = sum(reals) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in reals) / (n - 1)) if n > 1 else 0.0
    ucb = mean + Z * sd / math.sqrt(n)
    res = RS.summary(at, size=size)
    if ucb < 0:
        s["status"] = "killed"; s["history"].append({"what": f"killed at rung {s['rung']}: UCB of the real net {ucb:+.5f} SOL < 0 on {n} legs"})
    elif abs(res["mean_pts"]) > 2 * RS.TOL:
        s["status"] = "killed"; s["history"].append({"what": f"killed at rung {s['rung']}: the simulator is off by {res['mean_pts']:+.3f} of size on {n} legs (twice the tolerance)"})
    elif res["within"] and mean > 0:
        if s["rung"] + 1 < len(RUNGS):
            s["history"].append({"what": f"climbed from rung {s['rung']} on {n} legs: real mean {mean:+.5f} SOL, residual {res['mean_pts']:+.3f} of size"})
            s["rung"] += 1
            s["legs"] = []
        else:
            s["note"] = "at the top rung: the contract's own size"
    else:
        s["note"] = f"holding at rung {s['rung']}: real mean {mean:+.5f} SOL, residual {res['mean_pts']:+.3f} of size on {n} legs"
    return state


def retire(state, cell_id, why):
    s = state.get(cell_id)
    if s and s["status"] == "rung":
        s["status"] = "killed"; s["history"].append({"what": f"killed off the ladder: {why}"})
    return state
