"""The breadth screen. gate() is pure; snapshot() is built from the DexScreener pair record the resolver already holds,
and the one slow check (the pump.fun create deposit, two RPC calls) runs only when the cheap gates have passed."""
import time

import common as C

PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


def gate(snap):
    """snap: liq, age_min, buys_h1, sells_h1, mc, dev_create_sol (None = unknown or not yet checked). Returns (passed, reasons)."""
    r = []
    if snap["liq"] < C.LIQ_FLOOR:
        r.append(f"liq {snap['liq']:.0f} < {C.LIQ_FLOOR}")
    if snap["age_min"] < C.MIN_AGE_MIN:
        r.append(f"age {snap['age_min']:.1f}m < {C.MIN_AGE_MIN}")
    if snap["buys_h1"] < C.BUYERS_H1:
        r.append(f"buys_h1 {snap['buys_h1']} < {C.BUYERS_H1}")
    if snap["buys_h1"] < snap["sells_h1"]:
        r.append(f"buys {snap['buys_h1']} < sells {snap['sells_h1']}")
    if snap["mc"] and snap["mc"] > C.MAX_MC:
        r.append(f"mc {snap['mc']:.0f} > {C.MAX_MC}")
    if snap["dev_create_sol"] is not None and snap["dev_create_sol"] >= C.DEV_BUNDLE_SOL:
        r.append(f"dev bundle {snap['dev_create_sol']:.1f} SOL at create")
    return (not r), r


def dev_create_sol(mint):
    """SOL the creator deposited in the pump.fun create tx; None for non-pump mints or curves too long to read cheaply."""
    if not mint.endswith("pump"):
        return None
    from solders.pubkey import Pubkey
    curve, _ = Pubkey.find_program_address([b"bonding-curve", bytes(Pubkey.from_string(mint))], Pubkey.from_string(PUMP_PROGRAM))
    sigs = C.rpc("getSignaturesForAddress", [str(curve), {"limit": 1000}])
    if not sigs or len(sigs) >= 1000:
        return None
    tx = C.rpc("getTransaction", [sigs[-1]["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
    if not tx:
        return None
    keys = [k["pubkey"] for k in tx["transaction"]["message"]["accountKeys"]]
    if str(curve) not in keys:
        return 0.0
    i = keys.index(str(curve))
    return (tx["meta"]["postBalances"][i] - tx["meta"]["preBalances"][i]) / 1e9


def snapshot(pair):
    h1 = (pair.get("txns") or {}).get("h1") or {}
    created = (pair.get("pairCreatedAt") or 0) / 1000
    return {
        "liq": (pair.get("liquidity") or {}).get("usd") or 0.0,
        "age_min": (time.time() - created) / 60 if created else 0.0,
        "buys_h1": h1.get("buys") or 0,
        "sells_h1": h1.get("sells") or 0,
        "mc": pair.get("marketCap") or pair.get("fdv") or 0,
        "price": float(pair.get("priceUsd") or 0),
        "dev_create_sol": None,
    }


def screen(pair):
    """Cheap gates first; the RPC check only when they pass. Returns (passed, reasons, snap)."""
    snap = snapshot(pair)
    ok, why = gate(snap)
    if ok:
        snap["dev_create_sol"] = dev_create_sol(pair["baseToken"]["address"])
        ok, why = gate(snap)
    return ok, why, snap
