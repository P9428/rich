"""The sensor: feeds -> resolver -> breadth screen -> paper book -> alerts. Runs 24/7; heartbeat every loop."""
import asyncio
import os
import sys
import time

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
MARK_EVERY = 30


def alert(line):
    C.append(ALERTS, {"alert": line})
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if tok and chat:
        import json
        import urllib.parse
        try:
            C.http_json(f"https://api.telegram.org/bot{tok}/sendMessage",
                        json.dumps({"chat_id": chat, "text": line, "disable_web_page_preview": True}).encode(), tries=2, timeout=10)
        except Exception as e:
            C.append(ALERTS, {"telegram_error": str(e)[:120]})


class Sensor:
    def __init__(self):
        r = C.roster()
        self.state = C.load_json(STATE, {})
        self.polls = [F.TruthSocial(r["truth"], self.state), F.DexProfiles(r["x"], self.state), F.XApi(r["x"], self.state)]
        self.queue = asyncio.Queue()
        self.wallet = F.WalletTouch(r["wallets"], self.queue)
        self.ignore = r.get("ignore_terms", [])
        self.book = P.Book(BOOK, JOURNAL)
        self.seen = set(e["id"] for e in C.read_jsonl(EVENTS))
        self.last_mark = 0.0

    async def run(self):
        asyncio.create_task(self.wallet.run())
        for f in self.polls:
            asyncio.create_task(self._poll(f))
        while True:
            try:
                ev = await asyncio.wait_for(self.queue.get(), timeout=5)
                await asyncio.get_event_loop().run_in_executor(None, self.handle, ev)
            except asyncio.TimeoutError:
                pass
            if time.time() - self.last_mark >= MARK_EVERY:
                await asyncio.get_event_loop().run_in_executor(None, self.mark)
            C.save_json(HEART, {"pid": os.getpid(), "ts": C.iso(), "open": len(self.book.open), "events": len(self.seen)})

    async def _poll(self, feed):
        while True:
            try:
                for ev in await asyncio.get_event_loop().run_in_executor(None, feed.poll):
                    await self.queue.put(ev)
                C.save_json(STATE, self.state)
            except Exception as e:
                C.append(C.path("monitor", "feed-errors.log"), {"feed": type(feed).__name__, "err": str(e)[:200]})
            await asyncio.sleep(feed.POLL)

    def handle(self, ev):
        if ev["id"] in self.seen:
            return
        self.seen.add(ev["id"])
        t = time.time()
        if ev.get("mint"):
            pairs = [p for p in C.dex_tokens([ev["mint"]]) if p.get("chainId") == "solana"]
            best = C.best_pair(pairs)
            accepted = [{"mint": ev["mint"], "symbol": best["baseToken"]["symbol"], "name": best["baseToken"]["name"], "phrase": ev["kind"], "pair": best["pairAddress"]}] if best else []
            near = []
        else:
            accepted, near = R.resolve(ev["text"], t, self.ignore)
        rec = {**ev, "accepted": accepted, "near": near, "seen_at": C.iso(t)}
        results = []
        for a in accepted:
            pair = C.best_pair([p for p in C.dex_tokens([a["mint"]]) if p.get("chainId") == "solana"])
            if not pair:
                continue
            snap = S.snapshot(pair)
            ok, why = S.gate(snap)
            results.append({"mint": a["mint"], "symbol": a["symbol"], "pass": ok, "why": why, "snap": snap})
            if ok and snap["price"] > 0:
                pos = self.book.enter(a["mint"], a["symbol"], snap["price"], t, ev["id"])
                alert(f"{ev['person']} {ev['kind']} -> {a['symbol']} {a['mint']} PASS liq=${snap['liq']:,.0f} buys_h1={snap['buys_h1']} "
                      f"{'PAPER ENTRY @'+str(snap['price']) if pos else 'no entry (book full or duplicate)'}")
            else:
                alert(f"{ev['person']} {ev['kind']} -> {a['symbol']} {a['mint']} FAIL {'; '.join(why) or 'no price'}")
        rec["screen"] = results
        C.append(EVENTS, rec)
        if not accepted:
            C.append(ALERTS, {"touch_unresolved": f"{ev['feed']} {ev['person']} {ev['kind']}: {ev['text'][:140]}", "near": near[:3]})

    def mark(self):
        self.last_mark = time.time()
        if not self.book.open:
            return
        pairs = C.dex_tokens([p.mint for p in self.book.open])
        prices = {}
        for p in pairs:
            m = p["baseToken"]["address"]
            liq = (p.get("liquidity") or {}).get("usd") or 0
            if liq >= prices.get(m, (0, 0))[1]:
                prices[m] = (float(p.get("priceUsd") or 0), liq)
        before = {p.mint for p in self.book.open}
        self.book.mark_all({m: v[0] for m, v in prices.items()}, self.last_mark)
        for m in before - {p.mint for p in self.book.open}:
            last = [r for r in C.read_jsonl(JOURNAL) if r.get("kind") == "close" and r["mint"] == m][-1]
            alert(f"PAPER CLOSE {last['symbol']} net {last['net_sol']:+.3f} SOL after {last['held_s']//60} min ({', '.join(e['why'] for e in last['exits'])})")


if __name__ == "__main__":
    asyncio.run(Sensor().run())
