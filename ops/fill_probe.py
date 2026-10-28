"""The fill probe: a handful of real 0.01 SOL buys, each made exactly where the counted book decides, to learn where a signed
transaction lands against the three states every replay grades at: the create message's reserves, the chain read at decision,
and the first on-chain mark after the send. Ruled 2026-10-28 (decisions/2026-10-28-checklist-both-contracts, the operator moved
bet 2 ahead of the gate at five buys). Nothing here touches the counted book or any contract.

Mirrors src/duval.py: the same feed (PumpPortal subscribeNewToken), the same news terms (state/news.json, written by the engine
every minute), the same screen (plain pump mint, pool pump, no mayhem, curve readable and standard, mcap under the cap), the same
chain read at decision, the same marks every 2 s and the same exits (+20 % / -5 % / 60 s) on the marks, then a real sell of the
whole position so the exit fill is measured too. One position at a time. Every attempt is a row in journal/probe.jsonl; the
summary is out/probe.md.

Wallet: ~/.rich/wallet.json (outside the repo; created 2026-10-28; key never printed). The script refuses to start under
MIN_BALANCE and stops when the buys are done, the attempts are spent, or the balance falls under the floor.

  python ops/fill_probe.py [--buys 5] [--size 0.01] [--dry]     --dry: everything but the send (and no sell)
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C   # noqa: E402
import duval as D    # noqa: E402
import websockets    # noqa: E402
from solders.keypair import Keypair                 # noqa: E402
from solders.transaction import VersionedTransaction  # noqa: E402

WALLET = os.path.expanduser("~/.rich/wallet.json")
PROBE = C.path("journal", "probe.jsonl")
OUT = C.path("out", "probe.md")
TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"
SLIPPAGE = 50            # percent; wide on purpose: the question is where the tx lands, not whether a tight limit rejects it
PRIORITY_FEE = 0.0005    # SOL; PumpPortal's priorityFee on the local tx
MIN_BALANCE = 0.06       # SOL; 5 buys at 0.01 plus fees, rent and the sells
FLOOR = 0.02             # SOL; stop when the balance falls under this
CONFIRM_S = 45           # s; a send not confirmed by then is recorded as dropped
MAX_ATTEMPTS = 12
# the fees a real trade pays through this path, measured per account on chain 2026-10-28 (five round trips): the whole amount goes
# into the curve; on top, pump.fun takes 1.26 % (three recipients), PumpPortal 0.5 %, the tx 0.000505 SOL (0.0005 priority + base);
# the token account's rent (0.001514 SOL) is paid on the buy and refunded on the sell; a one-time 0.001346 SOL account on the
# wallet's first buy. src/duval.py assumes 1 % and 0.001 SOL a side: a round trip is 3.52 % + 0.001 SOL, not 2 % + 0.002 SOL.
FEE_PCT = 0.0126 + 0.005
FEE_TX = 0.000505
RENT = 0.001514


def log(line):
    print(f"{C.iso()} {line}", flush=True)


def load_wallet():
    with open(WALLET, encoding="utf-8") as f:
        w = json.load(f)
    return Keypair.from_bytes(bytes(w["secret"]))


def rpc(method, params, tries=3, timeout=20):
    return C.http_json(C.RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), tries=tries, timeout=timeout)


def balance(pub):
    d = rpc("getBalance", [str(pub), {"commitment": "confirmed"}])
    return (d.get("result") or {}).get("value", 0) / 1e9


def read_curve(key):
    """The engine's chain read, keeping the slot the RPC answered at."""
    d = rpc("getMultipleAccounts", [[key], {"encoding": "base64", "commitment": "processed"}], tries=2, timeout=15)
    res = d.get("result") or {}
    v = ((res.get("value") or [None])[0])
    if not v or not v.get("data"):
        return None, (res.get("context") or {}).get("slot")
    return D.decode_curve(v["data"][0]), (res.get("context") or {}).get("slot")


def build_tx(pub, action, mint, amount, denominated_in_sol):
    body = {"publicKey": str(pub), "action": action, "mint": mint, "amount": amount, "denominatedInSol": "true" if denominated_in_sol else "false",
            "slippage": SLIPPAGE, "priorityFee": PRIORITY_FEE, "pool": "pump"}
    req = urllib.request.Request(TRADE_LOCAL, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    if raw[:1] == b"{" or len(raw) < 100:
        raise RuntimeError(f"trade-local refused: {raw[:200]!r}")
    return raw


def sign_and_send(kp, raw, dry):
    tx = VersionedTransaction.from_bytes(raw)
    signed = VersionedTransaction(tx.message, [kp])
    sig = str(signed.signatures[0])
    if dry:
        return sig, None
    d = rpc("sendTransaction", [base64.b64encode(bytes(signed)).decode(), {"encoding": "base64", "skipPreflight": True, "maxRetries": 3}], tries=2, timeout=20)
    if "error" in d:
        raise RuntimeError(f"sendTransaction: {d['error']}")
    return d["result"], time.time()


def wait_tx(sig, pub, mint, deadline):
    """The landed transaction: slot, block time, the wallet's SOL delta and the token delta. None if not confirmed by the deadline."""
    while time.time() < deadline:
        d = rpc("getTransaction", [sig, {"encoding": "json", "commitment": "confirmed", "maxSupportedTransactionVersion": 0}], tries=1, timeout=15)
        r = d.get("result")
        if r:
            meta = r.get("meta") or {}
            keys = r["transaction"]["message"]["accountKeys"]
            me = keys.index(str(pub)) if str(pub) in keys else 0
            sol_delta = (meta["postBalances"][me] - meta["preBalances"][me]) / 1e9
            tok = 0.0
            for b in meta.get("postTokenBalances") or []:
                if b.get("owner") == str(pub) and b.get("mint") == mint:
                    tok += float(b["uiTokenAmount"]["uiAmount"] or 0)
            for b in meta.get("preTokenBalances") or []:
                if b.get("owner") == str(pub) and b.get("mint") == mint:
                    tok -= float(b["uiTokenAmount"]["uiAmount"] or 0)
            return {"slot": r.get("slot"), "block_time": r.get("blockTime"), "err": meta.get("err"), "sol_delta": round(sol_delta, 6),
                    "tok_delta": tok, "fee": (meta.get("fee") or 0) / 1e9}
        time.sleep(1.5)
    return None


def create_slot(sig):
    try:
        d = rpc("getTransaction", [sig, {"encoding": "json", "commitment": "confirmed", "maxSupportedTransactionVersion": 0}], tries=2, timeout=15)
        r = d.get("result") or {}
        return r.get("slot"), r.get("blockTime")
    except Exception:
        return None, None


def model_price(v_sol, v_tok, size):
    """SOL per token the curve gives for `size` SOL put into it at this state (the whole amount enters the curve; fees are on top)."""
    tok = v_tok - v_sol * v_tok / (v_sol + size)
    return (size / tok) if tok > 0 else None, tok


def raw_gross(v_sol, v_tok, tokens, size):
    """Gross SOL the curve returns for `tokens` at this state, the book's own `size` added back first (as duval.mark_value, no fees)."""
    k = v_sol * v_tok
    vs = v_sol + size
    return vs - k / (k / vs + tokens)


def recompute(r):
    """The measured comparison for one landed row: landed price vs each state, the sell's gross vs the exit mark, fees paid."""
    tx, size = r.get("tx") or {}, r["size"]
    if not r.get("landed") or not tx.get("tok_delta"):
        return r
    r["landed_price"] = size / tx["tok_delta"]
    v0 = r["msg"]; ch = (r.get("read") or {}).get("chain") or {}; fm = r.get("first_mark") or {}
    states = {"msg": (v0["v_sol"], v0["v_tok"]), "read": (ch.get("v_sol"), ch.get("v_tok")), "first_mark": (fm.get("v_sol"), fm.get("v_tok"))}
    r["vs"] = {}
    for k, (vs_, vt_) in states.items():
        if vs_ and vt_:
            pm = model_price(vs_, vt_, size)[0]
            r["vs"][k] = round(r["landed_price"] / pm - 1, 4)
    s = r.get("sell") or {}
    st = s.get("tx") or {}
    if st and st.get("err") is None:
        gross = st["sol_delta"] - RENT + FEE_PCT * size + FEE_TX          # what the curve paid out, before fees and the rent refund
        s["gross_out"] = round(gross, 6)
        s["gross_pct"] = round(gross / size - 1, 4)
        ex = r.get("exit") or {}
        if ex.get("mark"):
            m = ex["mark"]
            mark_gross = raw_gross(m[1], m[2], tx["tok_delta"], size)
            ex["raw_pct_at_mark"] = round(mark_gross / size - 1, 4)
            s["vs_mark_pct"] = round(gross / size - mark_gross / size, 4)
        r["net_sol"] = round(st["sol_delta"] + tx["sol_delta"], 6)
        r["fees_sol"] = round(2 * (FEE_PCT * size + FEE_TX), 6)
    return r


class Probe:
    def __init__(self, buys, size, dry, any_launch=False):
        self.any = any_launch and dry           # dry runs only: exercise the path on any plain launch, news match or not
        self.kp = load_wallet()
        self.pub = self.kp.pubkey()
        self.buys, self.size, self.dry = buys, size, dry
        self.done, self.attempts = 0, 0
        self.busy = threading.Lock()
        self.terms, self.terms_ts = set(), 0
        self.sol_usd = (C.load_json(D.SOL_USD, {}) or {}).get("usd") or 0
        self.rows = [r for r in C.read_jsonl(PROBE) if r.get("landed") and not r.get("dry")] if os.path.exists(PROBE) else []

    def refresh(self):
        if time.time() - self.terms_ts > 30:
            n = C.load_json(D.NEWS, {}) or {}
            self.terms = set((n.get("terms") or {}).keys())
            self.terms_ts = time.time()
            self.sol_usd = (C.load_json(D.SOL_USD, {}) or {}).get("usd") or self.sol_usd

    async def run(self):
        bal = balance(self.pub)
        log(f"wallet {self.pub} balance {bal:.4f} SOL; {self.buys} buys of {self.size} SOL; dry={self.dry}; terms from {D.NEWS}")
        if not self.dry and bal < MIN_BALANCE:
            log(f"balance under {MIN_BALANCE} SOL: fund {self.pub} and rerun"); return 2
        while self.done < self.buys and self.attempts < MAX_ATTEMPTS:
            try:
                async with websockets.connect(D.PP_WS, ping_interval=20, open_timeout=20, max_size=2 ** 20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    async for raw in ws:
                        if self.done >= self.buys or self.attempts >= MAX_ATTEMPTS:
                            break
                        try:
                            m = json.loads(raw)
                        except Exception:
                            continue
                        if m.get("txType") == "create" and m.get("mint"):
                            self.on_launch(m, time.time())
            except Exception as e:
                log(f"feed error {e!r}; reconnecting")
                await asyncio.sleep(5)
        self.report()
        return 0

    def on_launch(self, m, t):
        self.refresh()
        name, sym, mint = m.get("name") or "", m.get("symbol") or "", m["mint"]
        hits = D.match(name, sym, self.terms) or (["(any: dry run)"] if self.any else [])
        if not hits or not mint.endswith("pump") or m.get("pool") not in (None, "pump") or m.get("is_mayhem_mode") or not m.get("bondingCurveKey"):
            return
        if not self.busy.acquire(blocking=False):
            return                                              # one position at a time: the measurement stays clean
        threading.Thread(target=self.attempt, args=(m, t, hits, name, sym, mint), daemon=True).start()

    def attempt(self, m, t, hits, name, sym, mint):
        try:
            self._attempt(m, t, hits, name, sym, mint)
        except Exception as e:
            log(f"attempt {mint[:8]} error {e!r}")
            C.append(PROBE, {"ts": C.iso(t), "mint": mint, "name": name[:60], "match": hits[:4], "stage": "error", "error": repr(e), "landed": False})
        finally:
            self.busy.release()

    def _attempt(self, m, t, hits, name, sym, mint):
        key = m["bondingCurveKey"]
        v0s, v0t = float(m.get("vSolInBondingCurve") or 0), float(m.get("vTokensInBondingCurve") or 0)
        row = {"ts": C.iso(t), "mint": mint, "name": name[:60], "symbol": sym[:20], "match": hits[:4], "curve": key, "create_sig": m.get("signature"),
               "msg": {"v_sol": v0s, "v_tok": v0t}, "size": self.size, "dry": self.dry, "landed": False}
        # the engine's chain read at decision, one retry
        chain, slot_read = None, None
        for _ in range(2):
            chain, slot_read = read_curve(key)
            if chain:
                break
            time.sleep(0.5)
        t_read = time.time()
        row["read"] = {"t_after_create": round(t_read - t, 2), "slot": slot_read, "chain": chain}
        why = []
        if not chain:
            why.append("curve not readable at decision")
        elif chain["complete"]:
            why.append("complete")
        elif not (0.5 <= chain["v_sol"] / max(v0s, 1e-9) <= 2.0):
            why.append("non-standard curve")
        mcap = (chain["v_sol"] / chain["v_tok"] * 1e9 * self.sol_usd) if (chain and self.sol_usd) else None
        if mcap is None or mcap >= D.MCAP_MAX_USD:
            why.append(f"mcap {mcap}")
        if time.time() - t > D.ENTRY_WINDOW_S:
            why.append("past the window")
        if why:
            row["stage"], row["why"] = "screened_out", why
            C.append(PROBE, row)
            return
        self.attempts += 1
        log(f"attempt {self.attempts}: {name[:30]!r} {mint[:8]} match {hits[:2]} mcap ${mcap:,.0f} read {row['read']['t_after_create']} s after create")
        raw = build_tx(self.pub, "buy", mint, self.size, True)
        t_built = time.time()
        sig, t_sent = sign_and_send(self.kp, raw, self.dry)
        t_sent = t_sent or time.time()
        row.update({"stage": "sent", "sig": sig, "t_built_after_create": round(t_built - t, 2), "t_sent_after_create": round(t_sent - t, 2)})
        # marks every 2 s from the send, the engine's exits on them
        marks = []
        tx = None
        t_end = t_sent + D.HOLD_S + 5
        pm_msg = model_price(v0s, v0t, self.size)
        pm_read = model_price(chain["v_sol"], chain["v_tok"], self.size)
        while time.time() < t_end:
            c, slot = read_curve(key)
            now = time.time()
            if c:
                marks.append([round(now - t_sent, 1), round(c["v_sol"], 4), int(c["v_tok"]), round(c["r_sol"], 4), slot])
            if tx is None and not self.dry and now - t_sent > 2:
                tx = wait_tx(sig, self.pub, mint, now + 0.1)
                if tx:
                    row["landed"] = tx.get("err") is None and tx["tok_delta"] > 0
                    row["tx"] = tx
                    row["t_landed_after_create"] = round((tx["block_time"] or now) - t, 1) if tx.get("block_time") else None
                    log(f"  landed slot {tx['slot']} err={tx['err']} tokens {tx['tok_delta']:.0f} sol {tx['sol_delta']:+.5f}")
                    if not row["landed"]:
                        break
            if self.dry and now - t_sent > 8:
                break
            if tx and row["landed"] and marks:
                # the engine's exit rule on the marks, valued with the book's own SOL added back (duval.mark_value)
                last = marks[-1]
                pct = D.mark_value(last[1], last[2], tx["tok_delta"], self.size) / self.size - 1
                held = now - t_sent
                why = "take" if pct >= D.TAKE else "stop" if pct <= D.STOP else "time" if held >= D.HOLD_S else None
                if why:
                    row["exit"] = {"why": why, "pct_at_mark": round(pct, 4), "held_s": round(held, 1), "mark": last}
                    break
            time.sleep(max(0.0, D.MARK_EVERY - (time.time() - now)))
        row["marks"] = marks
        if marks:
            fm = marks[0]
            row["first_mark"] = {"t_after_send": fm[0], "slot": fm[4], "v_sol": fm[1], "v_tok": fm[2]}
        row["model"] = {"price_msg": pm_msg[0], "tok_msg": pm_msg[1], "price_read": pm_read[0], "tok_read": pm_read[1]}
        if marks:
            pm_fm = model_price(marks[0][1], marks[0][2], self.size)
            row["model"].update({"price_first_mark": pm_fm[0], "tok_first_mark": pm_fm[1]})
        if row["landed"]:
            row["landed_price"] = self.size / tx["tok_delta"]
            row["vs"] = {k: round(row["landed_price"] / v - 1, 4) for k, v in (("msg", pm_msg[0]), ("read", pm_read[0]), ("first_mark", row["model"].get("price_first_mark"))) if v}
            cs, _ = create_slot(m.get("signature"))
            row["slots_after_create"] = (tx["slot"] - cs) if (cs and tx.get("slot")) else None
            row["slots_after_read"] = (tx["slot"] - slot_read) if (slot_read and tx.get("slot")) else None
            # sell everything, measured the same way
            if not self.dry:
                raw = build_tx(self.pub, "sell", mint, "100%", False)
                ssig, ts = sign_and_send(self.kp, raw, False)
                sold = wait_tx(ssig, self.pub, mint, time.time() + CONFIRM_S)
                row["sell"] = {"sig": ssig, "t_after_send": round(ts - t_sent, 1), "tx": sold}
                if sold and sold.get("err") is None:
                    row["sell"]["sol_out"] = sold["sol_delta"]
                    row["net_sol"] = round(sold["sol_delta"] + tx["sol_delta"], 6)        # both deltas include fees and rent
                    if row.get("exit"):
                        row["sell"]["vs_mark_pct"] = round((sold["sol_delta"] / self.size) - (1 + row["exit"]["pct_at_mark"]), 4)
                log(f"  sold: {row['sell'].get('sol_out')} SOL back; net {row.get('net_sol')} SOL")
            self.done += 1
            self.rows.append(row)
        elif tx is None and not self.dry:
            row["stage"] = "dropped"
            log(f"  not confirmed within the hold: dropped")
        C.append(PROBE, row)
        try:
            self.report()
        except Exception as e:
            log(f"report error {e!r}")

    def report(self):
        rows = [recompute(r) for r in self.rows]
        L = [f"# The fill probe · {C.iso()} · {len(rows)} landed buys of {self.size} SOL · wallet {self.pub}", "",
             "Where a real signed buy lands against the three states the replays grade at. 'vs' is the landed price over the curve's price "
             "at that state for the same SOL, minus one: positive means the book paid more than that state says. 'raw mark %' is the exit "
             "mark's gross on the curve; 'sell vs mark' is the sell's landed gross minus that, in points. Fees are on top of every number but "
             f"net: {FEE_PCT:.2%} and {FEE_TX} SOL a side (pump.fun 1.26 %, PumpPortal 0.5 %, tx), measured per account on chain.", "",
             "| when | name | read s after create | sent s | landed slot − create | slot − read | vs message | vs read | vs first mark | exit | raw mark % | sell vs mark | net SOL |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            vs = r.get("vs", {}); ex = r.get("exit", {}); s = r.get("sell", {})
            L.append(f"| {r['ts'][11:19]} | {r['name'][:24]} | {r['read']['t_after_create']} | {r.get('t_sent_after_create')} | {r.get('slots_after_create')} | {r.get('slots_after_read')} | "
                     f"{vs.get('msg', float('nan')):+.1%} | {vs.get('read', float('nan')):+.1%} | {vs.get('first_mark', float('nan')):+.1%} | {ex.get('why', '')} | "
                     f"{ex.get('raw_pct_at_mark', float('nan')):+.1%} | {s.get('vs_mark_pct', float('nan')):+.1%} | {r.get('net_sol', float('nan')):+.5f} |")
        if rows:
            import statistics as st
            for k in ("msg", "read", "first_mark"):
                xs = [r["vs"][k] for r in rows if k in r.get("vs", {})]
                if xs:
                    L.append(f"- landed vs {k}: median {st.median(xs):+.1%} over {len(xs)}")
            sl = [r["slots_after_read"] for r in rows if r.get("slots_after_read") is not None]
            if sl:
                L.append(f"- slots between the chain read and the landing: median {st.median(sl):.0f} (min {min(sl)}, max {max(sl)})")
            nets = [r["net_sol"] for r in rows if r.get("net_sol") is not None]
            if nets:
                L.append(f"- net over the round trips, fees, tips and rent included: {sum(nets):+.5f} SOL")
        att = [r for r in C.read_jsonl(PROBE) if not r.get("dry")] if os.path.exists(PROBE) else []
        L.append(f"- attempts in journal/probe.jsonl: {len(att)} rows; sent {sum(1 for r in att if r.get('stage') in ('sent', 'dropped'))}, landed {sum(1 for r in att if r.get('landed'))}, dropped {sum(1 for r in att if r.get('stage') == 'dropped')}, screened out {sum(1 for r in att if r.get('stage') == 'screened_out')}")
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--buys", type=int, default=5)
    ap.add_argument("--size", type=float, default=0.01)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--any", action="store_true", help="dry runs only: ignore the news match to exercise the path")
    ap.add_argument("--report", action="store_true", help="rewrite out/probe.md from journal/probe.jsonl; no feed, no send")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.report:
        pr = Probe(a.buys, a.size, True)
        pr.report()
        print(open(OUT, encoding="utf-8").read())
        raise SystemExit(0)
    raise SystemExit(asyncio.run(Probe(a.buys, a.size, a.dry, a.any).run()))
