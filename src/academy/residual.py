"""The residual: every real leg paired with the arena's prediction for that exact launch at that exact size. The simulator's second
score. A leg whose launch is not in the record (the tape was dark, or the mint never got a path) is listed, not scored.

residual = real net - predicted net, in SOL; the tolerance is read in points of size (TOL), because a 0.01 SOL leg and a 1.5 SOL leg
are the same bit about the simulator.
"""
import numpy as np

from . import arena as A
from . import cells as CE

TOL = 0.05          # points of size: the mean residual a group of legs may carry and still call the simulator right


def pair(rec, fills, roster):
    """One row per real leg: the cell it ran (the control when untagged), the arena's prediction, the residual."""
    idx = {m: i for i, m in enumerate(rec["mint"])}
    rows = []
    for f in fills:
        cell = roster.get(f.get("cell") or "", {}).get("cell") or CE.make(CE.CONTROL["name"])
        i = idx.get(f["mint"])
        row = {"ts": f["ts"], "mint": f["mint"], "cell": cell["id"], "size": f["size"], "real": f.get("net"), "fam": f["fam"], "exit": f.get("exit")}
        if i is None or f.get("net") is None:
            row.update({"pred": None, "resid": None, "why": "launch not in the record" if i is None else "no net on the row"})
        else:
            one = {k: (v[i:i + 1] if k != "mint" else v[i:i + 1]) for k, v in rec.items()}
            s = A.score(one, cell, size=f["size"])
            pred = float(s["net"][0]) if np.isfinite(s["net"][0]) else None
            row.update({"pred": pred, "pred_exit": A.WHY[int(s["why"][0])] if pred is not None else None,
                        "resid": (f["net"] - pred) if pred is not None else None,
                        "why": None if pred is not None else "the cell would not have entered this launch"})
        rows.append(row)
    return rows


def summary(rows, size=None):
    xs = [r for r in rows if r.get("resid") is not None and (size is None or r["size"] == size)]
    if not xs:
        return {"n": 0, "mean_pts": None, "abs_pts": None, "within": None}
    pts = np.array([r["resid"] / r["size"] for r in xs])
    return {"n": len(xs), "mean_pts": float(pts.mean()), "abs_pts": float(np.abs(pts).mean()), "within": bool(abs(pts.mean()) <= TOL),
            "real_sum": float(sum(r["real"] for r in xs)), "pred_sum": float(sum(r["pred"] for r in xs))}
