"""The touch feeds. Each produces event dicts {id, feed, person, kind, text, mint?, when, t_src}: t_src is the source's own
timestamp (epoch seconds) so end-to-end latency is measurable. Polling feeds expose poll() and POLL; push feeds expose run()."""
import asyncio
import calendar
import json
import os
import re
import time
import urllib.request

import websockets

import common as C

TAG_RE = re.compile(r"<[^>]+>")
MIN_RECEIVE_SHARE = 0.001   # a receipt counts as a touch only at >= 0.1 % of supply; >= 1 % is a gift
GIFT_SHARE = 0.01


def _iso_to_epoch(s):
    """UTC ISO-8601 to epoch seconds. calendar.timegm, never mktime: mktime applies local DST and shifts by an hour."""
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


class TruthSocial:
    """Public Mastodon-style API, no key. One id lookup per account, then statuses every POLL seconds (5 s draws 429s)."""
    POLL = 12

    def __init__(self, accounts, state):
        self.accounts, self.state = accounts, state
        self.ids = {}

    def poll(self):
        out = []
        for a in self.accounts:
            key = "truth:" + a["acct"]
            if a["acct"] not in self.ids:
                self.ids[a["acct"]] = C.http_json(f"https://truthsocial.com/api/v1/accounts/lookup?acct={a['acct']}")["id"]
            last = self.state.get(key)
            for s in sorted(C.http_json(f"https://truthsocial.com/api/v1/accounts/{self.ids[a['acct']]}/statuses?limit=10&exclude_replies=false"), key=lambda s: s["id"]):
                if last is not None and s["id"] > last:
                    text = TAG_RE.sub(" ", s.get("content") or "").strip()
                    if text:
                        out.append({"id": "truth:" + s["id"], "feed": "truth", "person": a["person"], "kind": "post",
                                    "text": text, "when": s["created_at"], "t_src": _iso_to_epoch(s["created_at"])})
                if last is None or s["id"] > self.state.get(key, ""):
                    self.state[key] = s["id"]
        return out


class DexProfiles:
    """DexScreener latest profiles and boosts whose social link belongs to a roster handle."""
    POLL = 30
    URLS = (("https://api.dexscreener.com/token-profiles/latest/v1", "profile"), ("https://api.dexscreener.com/token-boosts/latest/v1", "boost"))
    LINK_RE = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)")

    def __init__(self, handles, state):
        self.handles = {h["handle"].lower(): h["person"] for h in handles}
        self.state = state
        self.seen = set(state.get("profiles_seen", []))

    def poll(self):
        out = []
        for url, kind in self.URLS:
            for p in C.http_json(url):
                if p.get("chainId") != "solana":
                    continue
                for l in p.get("links") or []:
                    m = self.LINK_RE.search(l.get("url") or "")
                    h = m.group(1).lower() if m else None
                    key = f"{kind}:{p['tokenAddress']}:{h}"
                    if h in self.handles and key not in self.seen:
                        self.seen.add(key)
                        out.append({"id": "dex:" + key, "feed": "profile", "person": self.handles[h], "kind": kind,
                                    "text": l["url"], "mint": p["tokenAddress"], "when": C.iso(), "t_src": time.time()})
        self.state["profiles_seen"] = sorted(self.seen)[-5000:]
        return out


class XStream:
    """X API v2 filtered stream: one rule covering the roster, posts pushed as they happen. Dormant without X_BEARER."""
    RULES = "https://api.x.com/2/tweets/search/stream/rules"
    STREAM = "https://api.x.com/2/tweets/search/stream?tweet.fields=created_at,author_id&expansions=author_id&user.fields=username"

    ROSTER_FILE = os.path.join(C.ROOT, "prereg", "ROSTER.json")

    def __init__(self, handles, queue):
        self.people = {h["handle"].lower(): h["person"] for h in handles}
        self.queue = queue
        self.bearer = os.environ.get("X_BEARER")
        self.roster_mtime = os.path.getmtime(self.ROSTER_FILE)
        self.resp = None

    def _reload_roster(self):
        self.people = {h["handle"].lower(): h["person"] for h in C.roster()["x"]}
        self.roster_mtime = os.path.getmtime(self.ROSTER_FILE)

    async def _watch_roster(self):
        """Discovery rewrites ROSTER.json; a changed file re-applies the rule by dropping the stream, which reconnects."""
        while True:
            await asyncio.sleep(60)
            if os.path.getmtime(self.ROSTER_FILE) != self.roster_mtime and self.resp is not None:
                self._reload_roster()
                self.resp.close()

    def _req(self, url, data=None, method=None):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": "Bearer " + self.bearer, "User-Agent": "rich/1", "Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=None if url.startswith(self.STREAM[:40]) and data is None and method is None else 30)

    @staticmethod
    def rule_for(handles):
        return " OR ".join("from:" + h for h in handles)

    def ensure_rules(self):
        want = self.rule_for(sorted(self.people))
        have = json.load(self._req(self.RULES)).get("data") or []
        if any(r["value"] == want for r in have) and len(have) == 1:
            return
        if have:
            self._req(self.RULES, json.dumps({"delete": {"ids": [r["id"] for r in have]}}).encode())
        res = json.load(self._req(self.RULES, json.dumps({"add": [{"value": want, "tag": "roster"}]}).encode()))
        if res.get("errors"):
            raise RuntimeError(res["errors"])

    async def run(self):
        if not self.bearer:
            C.append(C.path("monitor", "feed-errors.log"), {"feed": "x", "err": "dormant: no X_BEARER"})
            return
        loop = asyncio.get_event_loop()
        asyncio.create_task(self._watch_roster())
        backoff = 1
        while True:
            try:
                await loop.run_in_executor(None, self.ensure_rules)
                self.resp = await loop.run_in_executor(None, self._req, self.STREAM)
                C.append(C.path("monitor", "alerts.log"), {"x_stream": "connected", "handles": len(self.people)})
                backoff = 1
                while True:
                    line = await loop.run_in_executor(None, self.resp.readline)
                    if not line:
                        raise ConnectionError("stream closed")
                    if line.strip():
                        await self.queue.put(self._event(json.loads(line)))
            except Exception as e:
                C.append(C.path("monitor", "feed-errors.log"), {"feed": "x", "err": str(e)[:200]})
                await asyncio.sleep(backoff)
                backoff = min(60, backoff * 2)

    def _event(self, msg):
        d = msg["data"]
        users = {u["id"]: u["username"].lower() for u in (msg.get("includes") or {}).get("users", [])}
        handle = users.get(d.get("author_id"), "")
        return {"id": "x:" + d["id"], "feed": "x", "person": self.people.get(handle, handle), "kind": "post", "text": d["text"],
                "when": d.get("created_at", C.iso()), "t_src": _iso_to_epoch(d["created_at"]) if d.get("created_at") else time.time()}


class WalletTouch:
    """logsSubscribe on each roster wallet; a notification is decoded into token buys, receipts and gifts."""
    DECODE_SPACING = 1.0     # the public RPC 429s past one getTransaction a second
    FIRST_WAIT = 0.5         # confirmed txs are usually readable this soon; retried if the node has not seen it yet

    def __init__(self, wallets, queue):
        self.wallets = {w["address"]: w for w in wallets}
        self.queue = queue
        self.lock = asyncio.Lock()
        self.last_decode = 0.0

    async def run(self):
        while True:
            try:
                async with websockets.connect(C.WS, ping_interval=20, max_size=2 ** 22) as ws:
                    subs = {}
                    for i, addr in enumerate(self.wallets):
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": i + 1, "method": "logsSubscribe",
                                                  "params": [{"mentions": [addr]}, {"commitment": "confirmed"}]}))
                        subs[i + 1] = addr
                    bysub = {}
                    async for raw in ws:
                        m = json.loads(raw)
                        if "result" in m and m.get("id") in subs:
                            bysub[m["result"]] = subs[m["id"]]
                        elif m.get("method") == "logsNotification":
                            v = m["params"]["result"]["value"]
                            addr = bysub.get(m["params"]["subscription"])
                            if addr and not v.get("err"):
                                asyncio.create_task(self._decode(addr, v["signature"], time.time()))
            except Exception as e:
                C.append(C.path("monitor", "feed-errors.log"), {"feed": "wallet", "err": str(e)[:200]})
                await asyncio.sleep(5)

    async def _fetch(self, sig):
        loop = asyncio.get_event_loop()
        for attempt in range(4):
            await asyncio.sleep(self.FIRST_WAIT if attempt == 0 else 1.0)
            async with self.lock:
                wait = self.last_decode + self.DECODE_SPACING - time.time()
                if wait > 0:
                    await asyncio.sleep(wait)
                self.last_decode = time.time()
            tx = await loop.run_in_executor(None, C.rpc, "getTransaction",
                                            [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}])
            if tx:
                return tx
        return None

    async def _decode(self, addr, sig, t_seen):
        try:
            tx = await self._fetch(sig)
        except Exception as e:
            C.append(C.path("monitor", "feed-errors.log"), {"feed": "wallet", "sig": sig, "err": str(e)[:200]})
            return
        if not tx:
            return
        w = self.wallets[addr]
        delta = {}
        for side, sign in ((tx["meta"].get("preTokenBalances") or [], -1), (tx["meta"].get("postTokenBalances") or [], 1)):
            for tb in side:
                if tb.get("owner") == addr:
                    delta[tb["mint"]] = delta.get(tb["mint"], 0.0) + sign * float(tb["uiTokenAmount"]["uiAmount"] or 0)
        signer = tx["transaction"]["message"]["accountKeys"][0]["pubkey"]
        for mint, d in delta.items():
            if d <= 0 or mint.startswith("So1111"):
                continue
            kind = "buy" if signer == addr else "receive"
            share = None
            if kind == "receive":
                sup = C.rpc("getTokenSupply", [mint])["value"]
                share = d / float(sup["uiAmount"]) if sup.get("uiAmount") else None
                if share is None or share < MIN_RECEIVE_SHARE:
                    continue
                if share >= GIFT_SHARE:
                    kind = "gift"
            await self.queue.put({"id": f"wallet:{sig}:{mint}", "feed": "wallet", "person": w["person"], "kind": kind,
                                 "text": f"{w['label']} {kind} {d:,.0f} of {mint}" + (f" ({share:.2%} of supply)" if share else ""),
                                 "mint": mint, "when": C.iso(tx.get("blockTime") or t_seen), "t_src": tx.get("blockTime") or t_seen, "signer": signer})
