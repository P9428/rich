"""The answer term: what the launcher does to the book's own fill, which the tape can only suggest and a real leg measures.

On pump.fun the launcher cannot pull a pool; its answer is the dump that lands between the exit mark and the sell that follows it
(the fill probe of 2026-10-28 measured the sell landing 3 s after its mark, -19 to +12 points away on a live curve), and the slot or
two between the chain read and the buy landing. Both are per family (record.FAMILIES): a bundled launch answers a stranger's buy with
the creator's sell; an empty one mostly does nothing.

prior      from the record: the move from the exit mark to the next mark (arena 'next'), per family, over the cell's own exits
own        from journal/probe.jsonl: the real sell's gross against its mark (sell.vs_mark_pct), per family of the probed launch
posterior  the record counts as PRIOR_N fills; ten real fills outweigh the record's thousands on purpose
p          the share of exits where that move is a dump (under DUMP), the launcher's answer rate on our legs

answered mean = arena mean + size * sum over families (share of the cell's exits in the family * posterior slip)
"""
import os
import sys

import numpy as np

from . import arena as A
from . import record as R

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C   # noqa: E402

PROBE = C.path("journal", "probe.jsonl")
PRIOR_N = 10
DUMP = -0.05
RENT = 0.001514          # the token account's rent, paid on the buy and refunded on the sell (ops/fill_probe.py)


def sell_vs_mark(r):
    """The real sell's gross against the exit mark's gross, in points of size, as ops/fill_probe.recompute reads it: the sell's SOL
    delta less the rent refund plus the fees it paid, over the curve's raw payout at the mark with the book's own SOL added back.
    (The in-flight figure on the row counts the rent refund as profit: +15 points at 0.01 SOL.)"""
    s, ex, tx = r.get("sell") or {}, r.get("exit") or {}, r.get("tx") or {}
    st = s.get("tx") or {}
    m = ex.get("mark")
    if not st or st.get("err") is not None or not m or not tx.get("tok_delta"):
        return None
    size = r["size"]
    gross = st["sol_delta"] - RENT + A.FEE_PCT * size + A.FEE_TX
    k = m[1] * m[2]
    vs = m[1] + size
    mark_gross = vs - k / (k / vs + tx["tok_delta"])
    return round((gross - mark_gross) / size, 4)


def own_fills(rec=None):
    """The real legs on file, each with its family (from the record when the launch is in it, else by the row's own reads)."""
    rows = [r for r in C.read_jsonl(PROBE) if r.get("landed") and not r.get("dry")] if os.path.exists(PROBE) else []
    out = []
    fam_of = {}
    if rec is not None:
        fam_of = dict(zip(rec["mint"], rec["fam"].astype(int)))
    for r in rows:
        ch = (r.get("read") or {}).get("chain") or {}
        fam = fam_of.get(r["mint"])
        if fam is None:
            fam = R.family(0, ch.get("r_sol"))
        out.append({"ts": r["ts"], "mint": r["mint"], "fam": int(fam), "size": r["size"], "net": r.get("net_sol"),
                    "sell_vs_mark": sell_vs_mark(r), "buy_vs_first_mark": (r.get("vs") or {}).get("first_mark"),
                    "cell": r.get("cell"), "exit": (r.get("exit") or {}).get("why")})
    return out


def prior(rec, scored):
    """Per family: mean next-mark move after the exit and the dump share, over the cell's own exits on the record."""
    out = {}
    nxt, fam = scored["next"], rec["fam"].astype(int)
    for i, name in enumerate(R.FAMILIES):
        x = nxt[(fam == i) & np.isfinite(nxt)]
        out[name] = {"n": int(len(x)), "slip": float(x.mean()) if len(x) else 0.0, "p": float((x < DUMP).mean()) if len(x) else 0.0}
    return out


def posterior(pri, fills):
    out = {}
    for i, name in enumerate(R.FAMILIES):
        own = [f["sell_vs_mark"] for f in fills if f["fam"] == i and f.get("sell_vs_mark") is not None]
        n_own = len(own)
        slip = (PRIOR_N * pri[name]["slip"] + sum(own)) / (PRIOR_N + n_own)
        p = (PRIOR_N * pri[name]["p"] + sum(1 for v in own if v < DUMP)) / (PRIOR_N + n_own)
        out[name] = {"prior_n": pri[name]["n"], "prior_slip": pri[name]["slip"], "prior_p": pri[name]["p"], "own": n_own, "slip": slip, "p": p}
    return out


def answered(rec, scored, cell, fills):
    """The cell's arena mean corrected for the launcher's answer, with the family mix of its exits."""
    net, fam = scored["net"], rec["fam"].astype(int)
    ok = np.isfinite(net)
    n = int(ok.sum())
    if not n:
        return {"n": 0, "mean": None, "answered": None, "mix": {}, "post": {}}
    post = posterior(prior(rec, scored), fills)
    mix = {name: float(((fam == i) & ok).sum() / n) for i, name in enumerate(R.FAMILIES)}
    corr = sum(mix[name] * post[name]["slip"] for name in R.FAMILIES) * cell["size"]
    mean = float(net[ok].mean())
    return {"n": n, "mean": mean, "answered": mean + corr, "correction": corr, "mix": mix, "post": post}
