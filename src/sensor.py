"""The sensor: feeds -> resolver -> breadth screen -> paper book -> alerts. Every event carries stage timestamps so latency is a number."""
import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C          # noqa: E402
import feeds as F           # noqa: E402
import paper as P           # noqa: E402
import resolve as R         # noqa: E402
import screen as S          # noqa: E402

EVENTS = C.path("journal", "events.jsonl")
JOURNAL = C.path("journal", "paper.jsonl")
ALERTS = C.path("monitor", "alerts.log")
STATE = C.path("state", "feeds.json")
BOOK = C.path("state", "positions.json")
HEART = C.path("monitor", "heartbeat.json")
MARK_EVERY = 5
HANDLERS = ThreadPoolExecutor(max_workers=4)


def alert(line):
    C.append(ALERTS, {"alert": line})
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if tok and chat:
        try:
            C.http_json(f"https://api.telegram.org/bot{tok}/sendMessage",
                        json.dumps({"chat_id": chat, "text": line, "disable_web_page_preview": True}).encode(), tries=2, timeout=10)
        except Exception as e:
            C.append(ALERTS, {"telegram_error": str(e)[:120]})


def intent(ev, accepted):
    """Did the person mean this coin? Their own post carried its $ticker or mint, or their wallet signed the buy.
    A capitalised name, a receipt, a gift and a profile link can all be caused by anyone: screened and shadowed, never traded."""
    return ev["kind"] == "buy" if ev.get("mint") else accepted.get("via") in ("mint", "ticker")


class Sensor:
    def __init__(self):
        r = C.roster()
        self.state = C.load_json(STATE, {})
        self.queue = asyncio.Queue()
        self.polls = [F.TruthSocial(r["truth"], self.state), F.DexProfiles(r["x"], self.state)]
        self.pushes = [F.WalletTouch(r["wallets"], self.queue), F.XStream(r["x"], self.queue)]
        self.ignore = r.get("ignore_terms", [])
        self.book = P.Book(BOOK, JOURNAL)
        self.seen = set(e["id"] for e in C.read_jsonl(EVENTS))
        self.lock = asyncio.Lock()
        self.last_mark = 0.0

    async def run(self):
        for p in self.pushes:
            asyncio.create_task(p.run())
        for f in self.polls:
            asyncio.create_task(self._poll(f))
        loop = asyncio.get_event_loop()
        while True:
            try:
                ev = await asyncio.wait_for(self.queue.get(), timeout=2)
                ev["t_seen"] = time.time()
                loop.run_in_executor(HANDLERS, self.handle, ev)
            except asyncio.TimeoutError:
                pass
            if time.time() - self.last_mark >= MARK_EVERY:
                loop.run_in_executor(HANDLERS, self.mark)
            C.save_json(HEART, {"pid": os.getpid(), "ts": C.iso(), "open": len(self.book.open), "events": len(self.seen)})

    async def _poll(self, feed):
        loop = asyncio.get_event_loop()
        while True:
            try:
                for ev in await loop.run_in_executor(None, feed.poll):
                    await self.queue.put(ev)
                C.save_json(STATE, self.state)
            except Exception as e:
                C.append(C.path("monitor", "feed-errors.log"), {"feed": type(feed).__name__, "err": str(e)[:200]})
            await asyncio.sleep(feed.POLL)

    def handle(self, ev):
        if ev["id"] in self.seen:
            return
        self.seen.add(ev["id"])
        t = ev["t_seen"]
        if ev.get("mint"):
            best = C.best_pair([p for p in C.dex_tokens([ev["mint"]]) if p.get("chainId") == "solana"])
            accepted = [{"mint": ev["mint"], "symbol": best["baseToken"]["symbol"], "name": best["baseToken"]["name"],
                         "phrase": ev["kind"], "pair": best["pairAddress"], "_pair": best}] if best else []
            near = []
        else:
            accepted, near = R.resolve(ev["text"], t, self.ignore)
        t_resolved = time.time()
        results = []
        for a in accepted:
            pair = a.pop("_pair", None) or C.best_pair([p for p in C.dex_tokens([a["mint"]]) if p.get("chainId") == "solana"])
            if not pair:
                continue
            ok, why, snap = S.screen(pair)
            res = {"mint": a["mint"], "symbol": a["symbol"], "pass": ok, "why": why, "snap": snap, "intent": intent(ev, a), "t_screened": time.time()}
            if ok and not res["intent"]:
                alert(f"{ev['person']} {ev['kind']} -> {a['symbol']} {a['mint']} PASS but no intent: shadowed, not traded")
            elif ok and snap["price"] > 0:
                pos = self.book.enter(a["mint"], a["symbol"], snap["price"], time.time(), ev["id"])
                res["entry"] = bool(pos)
                res["t_entry"] = time.time()
                alert(f"{ev['person']} {ev['kind']} -> {a['symbol']} {a['mint']} PASS liq=${snap['liq']:,.0f} buys_h1={snap['buys_h1']} "
                      f"{'PAPER ENTRY @'+str(snap['price']) if pos else 'no entry (book full or duplicate)'} "
                      f"latency {time.time()-ev['t_src']:.1f}s from source")
            else:
                alert(f"{ev['person']} {ev['kind']} -> {a['symbol']} {a['mint']} FAIL {'; '.join(why) or 'no price'}")
            results.append(res)
        rec = {**ev, "accepted": accepted, "near": near, "screen": results,
               "latency": {"source_to_seen": round(t - ev["t_src"], 2), "resolve": round(t_resolved - t, 2),
                           "to_decision": round(time.time() - t, 2)}}
        C.append(EVENTS, rec)
        if not accepted:
            C.append(ALERTS, {"touch_unresolved": f"{ev['feed']} {ev['person']} {ev['kind']}: {ev['text'][:140]}", "near": near[:3]})

    def mark(self):
        self.last_mark = time.time()
        if not self.book.open:
            return
        prices = {}
        for p in C.dex_tokens([p.mint for p in self.book.open]):
            m, liq = p["baseToken"]["address"], (p.get("liquidity") or {}).get("usd") or 0
            if liq >= prices.get(m, (0, 0))[1]:
                prices[m] = (float(p.get("priceUsd") or 0), liq)
        before = {p.mint for p in self.book.open}
        self.book.mark_all({m: v[0] for m, v in prices.items()}, self.last_mark)
        for m in before - {p.mint for p in self.book.open}:
            last = [r for r in C.read_jsonl(JOURNAL) if r.get("kind") == "close" and r["mint"] == m][-1]
            alert(f"PAPER CLOSE {last['symbol']} net {last['net_sol']:+.3f} SOL after {last['held_s']//60} min ({', '.join(e['why'] for e in last['exits'])})")


if __name__ == "__main__":
    asyncio.run(Sensor().run())
