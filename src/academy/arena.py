"""The arena: every cell on every launch of the record, vectorised. Fills at the first mark at or after the entry delay (where a
signed buy was measured to land, 2026-10-28), pays the measured fees (1.76 % and 0.000505 SOL a side: pump.fun 1.26 %, PumpPortal
0.5 %, the tx; the engine's own 1 % / 0.001 SOL is the counted book's convention, not reality's), marks with the book's own SOL added
back along the curve (duval.mark_value), and exits in the contract's order: take, then stop, then trail, then the hold. A launch with
no mark after the entry is not a trade.

score(rec, cell) -> per-launch net (NaN where the cell does not enter), exit code, entry index, exit index, the tape's next move.
"""
import numpy as np

from . import record as R

FEE_PCT = 0.0126 + 0.005
FEE_TX = 0.000505
WHY = {0: "none", 1: "take", 2: "stop", 3: "trail", 4: "time", 5: "end"}


def buy(vs, vt, sol):
    net = sol * (1 - FEE_PCT) - FEE_TX
    k = vs * vt
    return np.where(net > 0, vt - k / (vs + net), 0.0)


def mark_pct(VS, VT, tokens, size):
    """pct at every mark for a position of `tokens` bought with `size` SOL: the book's own SOL added back, then sold after fees."""
    k = VS * VT
    vs = VS + (size * (1 - FEE_PCT) - FEE_TX)
    vt = k / vs
    gross = vs - k / (vt + tokens[:, None])
    out = np.maximum(0.0, gross * (1 - FEE_PCT) - FEE_TX)
    return out / size - 1


def universe_mask(rec, u):
    m = rec["plain"].astype(bool) & np.isfinite(rec["mcap0"]) & (rec["mcap0"] < u["mcap_max"])
    if u["pump_only"]:
        m &= rec["pump"].astype(bool)
    if u["filter"] == "matched":
        m &= rec["match"] >= max(1, u.get("nmatch_min") or 1)
    elif u["filter"] == "unmatched":
        m &= rec["match"] == 0
    if u.get("cls") == "narrative":
        m &= rec["cls"] == R.CLS["narrative"]
    if u.get("gate") == "live":
        m &= rec["gate"] == R.GATE["live"]
    if u.get("fam"):
        m &= np.isin(rec["fam"], [R.FAMILIES.index(f) for f in u["fam"]])
    if u.get("hours"):
        lo, hi = u["hours"]
        m &= (rec["hour"] >= lo) & (rec["hour"] < hi)
    if u.get("init_max") is not None:
        m &= rec["init"] <= u["init_max"]
    # the on-chain check the live book makes at decision: the first mark must agree with the message, or the curve is non-standard
    vs0, vt0 = rec["VS"][:, 0], rec["VT"][:, 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = vs0 / np.maximum(rec["v0s"], 1e-9)
        kk = vs0 * vt0 / (rec["v0s"] * rec["v0t"])
    m &= np.isfinite(vs0) & (ratio >= 0.5) & (ratio <= 2.0) & (np.abs(kk - 1) <= 0.05)
    return m


def entry_index(rec, e, mask):
    """The entry mark per launch (-1 where the cell does not enter)."""
    T, RS, VS = rec["T"], rec["RS"], rec["VS"]
    n, m = T.shape
    valid = np.isfinite(T)
    if e.get("wait_buy"):
        r0 = RS[:, [0]]
        cond = valid & (T <= 10) & ((RS > r0 + 1e-6) | (VS > rec["v0s"][:, None] * 1.01))
    else:
        cond = valid & (T >= (e.get("delay") or 0.0))
    has = cond.any(axis=1) & mask
    idx = np.where(has, cond.argmax(axis=1), -1)
    rows = np.arange(n)
    ok = idx >= 0
    i = np.where(ok, idx, 0)
    if e.get("rsol_min") is not None:
        ok &= RS[rows, i] >= e["rsol_min"]
    if e.get("rsol_max") is not None:
        ok &= RS[rows, i] <= e["rsol_max"]
    if e.get("mom_min") is not None:
        with np.errstate(invalid="ignore"):
            ok &= (VS[rows, i] / rec["v0s"] - 1) >= e["mom_min"]
    if e.get("up"):
        prev = np.where(i > 0, VS[rows, np.maximum(i - 1, 0)], np.nan)
        ok &= np.isfinite(prev) & (VS[rows, i] > prev)
    # a trade needs a mark after the entry
    ok &= (i + 1 < m) & np.isfinite(T[rows, np.minimum(i + 1, m - 1)])
    return np.where(ok, i, -1)


def score(rec, cell, size=None):
    """Per-launch outcome of one cell on the record."""
    size = cell["size"] if size is None else size
    mask = universe_mask(rec, cell["universe"])
    ei = entry_index(rec, cell["entry"], mask)
    n, m = rec["T"].shape
    rows = np.arange(n)
    ok = ei >= 0
    out = {"net": np.full(n, np.nan), "pct": np.full(n, np.nan), "why": np.zeros(n, dtype=np.int8), "ei": ei, "xi": np.full(n, -1),
           "next": np.full(n, np.nan)}
    if not ok.any():
        return out
    sub = rows[ok]
    T, VS, VT = rec["T"][sub], rec["VS"][sub], rec["VT"][sub]
    e = ei[sub]
    r = np.arange(len(sub))
    tokens = buy(VS[r, e], VT[r, e], size)
    with np.errstate(invalid="ignore", divide="ignore"):
        P = mark_pct(VS, VT, tokens, size)
    after = (np.arange(m)[None, :] > e[:, None]) & np.isfinite(T)
    P = np.where(after, P, np.nan)
    held = T - T[r, e][:, None]
    x = cell["exit"]
    with np.errstate(invalid="ignore"):
        take = after & (P >= x["take"])
        stop = after & (P <= x["stop"])
        timeup = after & (held >= x["hold"])
        if x.get("trail") is not None:
            peak = np.fmax.accumulate(np.where(after, P, -np.inf), axis=1)
            trail = after & (peak > 0) & (P <= peak - x["trail"])
        else:
            trail = np.zeros_like(after)
    anym = take | stop | trail | timeup
    has = anym.any(axis=1)
    last = np.where(after.any(axis=1), m - 1 - np.argmax(after[:, ::-1], axis=1), -1)
    j = np.where(has, anym.argmax(axis=1), np.maximum(last, 0))
    why = np.where(has, np.where(take[r, j], 1, np.where(stop[r, j], 2, np.where(trail[r, j], 3, 4))), 5)
    pct = P[r, j]
    good = np.isfinite(pct)
    out["net"][sub[good]] = size * pct[good]
    out["pct"][sub[good]] = pct[good]
    out["why"][sub[good]] = why[good]
    out["xi"][sub[good]] = j[good]
    # the tape's next mark after the exit: what a sell landing one mark late would have met (the prior of the answer term)
    jn = np.minimum(j + 1, m - 1)
    with np.errstate(invalid="ignore"):
        nxt = np.where(np.isfinite(P[r, jn]) & (jn > j), P[r, jn] - pct, np.nan)
    out["next"][sub[good]] = nxt[good]
    return out


def stats(net, why=None):
    x = net[np.isfinite(net)]
    n = int(len(x))
    if not n:
        return {"n": 0, "mean": None, "sum": 0.0, "pf": None, "win": None, "se": None, "stop_share": None, "take_share": None}
    wins, losses = x[x > 0], x[x <= 0]
    pf = float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else float("inf")
    s = {"n": n, "mean": float(x.mean()), "sum": float(x.sum()), "pf": pf, "win": float(len(wins) / n),
         "se": float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else None}
    if why is not None:
        w = why[np.isfinite(net)]
        s["stop_share"] = float((w == 2).mean()); s["take_share"] = float((w == 1).mean())
    return s


def boot_lb(net, k=400, q=0.05, seed=7):
    """One-sided bootstrap lower bound of the mean (the 5th percentile over k resamples)."""
    x = net[np.isfinite(net)]
    if len(x) < 10:
        return None
    rnd = np.random.default_rng(seed)
    means = rnd.choice(x, size=(k, len(x)), replace=True).mean(axis=1)
    return float(np.quantile(means, q))


def per_day(net, labels):
    return {d: stats(net[labels == d]) for d in sorted(set(labels))}
