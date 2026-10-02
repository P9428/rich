"""The touch feeds. Each yields event dicts: {id, feed, person, kind, text, mint?, when}. State is per-feed and durable."""
import asyncio
import json
import os
import re
import time

import websockets

import common as C

TAG_RE = re.compile(r"<[^>]+>")


class TruthSocial:
    """Public Mastodon-style API; no key. One lookup per account, then statuses every POLL seconds."""
    POLL = 20

    def __init__(self, accounts, state):
        self.accounts, self.state = accounts, state
        self.ids = {}

    def _lookup(self, acct):
        if acct not in self.ids:
            self.ids[acct] = C.http_json(f"https://truthsocial.com/api/v1/accounts/lookup?acct={acct}")["id"]
        return self.ids[acct]

    def poll(self):
        out = []
        for a in self.accounts:
            uid = self._lookup(a["acct"])
            last = self.state.get("truth:" + a["acct"])
            sts = C.http_json(f"https://truthsocial.com/api/v1/accounts/{uid}/statuses?limit=10&exclude_replies=false")
            newest = None
            for s in sorted(sts, key=lambda s: s["id"]):
                if last is None or s["id"] > last:
                    text = TAG_RE.sub(" ", s.get("content") or "").strip()
                    if last is not None and text:
                        out.append({"id": "truth:" + s["id"], "feed": "truth", "person": a["person"], "kind": "post",
                                    "text": text, "when": s["created_at"]})
                    newest = s["id"]
            if newest:
                self.state["truth:" + a["acct"]] = newest
        return out


class DexProfiles:
    """DexScreener latest profiles and boosts whose social link belongs to a roster handle."""
    POLL = 30

    def __init__(self, handles, state):
        self.handles = {h["handle"].lower(): h["person"] for h in handles}
        self.state = state
        self.seen = set(state.get("profiles_seen", []))

    def poll(self):
        out = []
        for url, kind in (("https://api.dexscreener.com/token-profiles/latest/v1", "profile"),
                          ("https://api.dexscreener.com/token-boosts/latest/v1", "boost")):
            for p in C.http_json(url):
                if p.get("chainId") != "solana":
                    continue
                for l in p.get("links") or []:
                    m = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", l.get("url") or "")
                    h = m.group(1).lower() if m else None
                    key = f"{kind}:{p['tokenAddress']}:{h}"
                    if h in self.handles and key not in self.seen:
                        self.seen.add(key)
                        out.append({"id": "dex:" + key, "feed": "profile", "person": self.handles[h], "kind": kind,
                                    "text": l["url"], "mint": p["tokenAddress"], "when": C.iso()})
        self.state["profiles_seen"] = sorted(self.seen)[-5000:]
        return out


class XApi:
    """Official v2 user timelines. Dormant without X_BEARER; the gap is logged once."""
    POLL = 60

    def __init__(self, handles, state):
        self.handles, self.state = handles, state
        self.bearer = os.environ.get("X_BEARER")
        self.ids = {}

    def _get(self, url):
        import urllib.request
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.bearer, "User-Agent": "rich/1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def poll(self):
        if not self.bearer:
            return []
        out = []
        for h in self.handles:
            if h["handle"] not in self.ids:
                self.ids[h["handle"]] = self._get(f"https://api.x.com/2/users/by/username/{h['handle']}")["data"]["id"]
            since = self.state.get("x:" + h["handle"])
            q = f"https://api.x.com/2/users/{self.ids[h['handle']]}/tweets?max_results=10&tweet.fields=created_at"
            if since:
                q += "&since_id=" + since
            data = self._get(q).get("data") or []
            for t in sorted(data, key=lambda t: t["id"]):
                if since is not None:
                    out.append({"id": "x:" + t["id"], "feed": "x", "person": h["person"], "kind": "post", "text": t["text"], "when": t["created_at"]})
                self.state["x:" + h["handle"]] = t["id"]
            if since is None and data:
                self.state["x:" + h["handle"]] = max(t["id"] for t in data)
        return out


class WalletTouch:
    """logsSubscribe on each roster wallet; a notification is decoded into token receipts/buys. Runs in its own task."""

    DECODE_SPACING = 1.5  # one getTransaction per 1.5 s: the public RPC 429s past that

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
                            continue
                        if m.get("method") != "logsNotification":
                            continue
                        v = m["params"]["result"]["value"]
                        addr = bysub.get(m["params"]["subscription"])
                        if addr and not v.get("err"):
                            asyncio.create_task(self._decode(addr, v["signature"]))
            except Exception as e:
                C.append(C.path("monitor", "feed-errors.log"), {"feed": "wallet", "err": str(e)[:200]})
                await asyncio.sleep(5)

    async def _decode(self, addr, sig):
        await asyncio.sleep(2)  # let the tx reach confirmed on the RPC node
        async with self.lock:
            wait = self.last_decode + self.DECODE_SPACING - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self.last_decode = time.time()
        try:
            tx = await asyncio.get_event_loop().run_in_executor(None, C.rpc, "getTransaction",
                                                               [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}])
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
        keys = [k["pubkey"] for k in tx["transaction"]["message"]["accountKeys"]]
        signer = keys[0]
        for mint, d in delta.items():
            if d <= 0 or mint.startswith("So1111"):
                continue
            kind = "buy" if signer == addr else "receive"
            share = None
            try:
                sup = C.rpc("getTokenSupply", [mint])["value"]
                share = d / float(sup["uiAmount"]) if sup.get("uiAmount") else None
            except Exception:
                pass
            if kind == "receive" and share is not None and share >= 0.01:
                kind = "gift"
            await self.queue.put({"id": f"wallet:{sig}:{mint}", "feed": "wallet", "person": w["person"], "kind": kind,
                                 "text": f"{w['label']} {kind} {d:,.0f} of {mint}" + (f" ({share:.1%} of supply)" if share else ""),
                                 "mint": mint, "when": C.iso(tx.get("blockTime") or time.time()), "signer": signer})
