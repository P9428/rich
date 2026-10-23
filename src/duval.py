"""RI-04, the Duval loop (paper only): a fresh pump.fun launch whose name matches the hour's headlines, under $10K market cap,
entered within 30 s of creation with 1.5 SOL, out within a minute (+20 % / -20 % / 60 s, whichever first).

Feeds   PumpPortal new-token stream (keyless, push)  ·  Google News RSS sections, refreshed every 60 s, last-60-minute titles
Marks   the pump.fun bonding-curve account over RPC every 2 s; a mark is what selling the whole position would return after fees
Fills   constant-product on the curve's virtual reserves (x·y=k) with the 1 % pump fee and a 0.001 SOL tx fee each side; the entry
        fill is taken on the curve state at detection, so the book pays its own price impact on both sides
Writes  journal/events.jsonl (news-matched launches, the old touch shape), journal/paper.jsonl (entry/exit/close), journal/launches.jsonl
        (every launch, one line), state/positions.json, state/news.json, state/sol_usd.json, monitor/heartbeat.json, monitor/alerts.log
No order is ever placed.
"""
import asyncio
import base64
import calendar
import html
import json
import os
import re
import struct
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C   # noqa: E402
import websockets    # noqa: E402

PP_WS = "wss://pumpportal.fun/api/data"
GN = "https://news.google.com/rss"
LOC = "hl=en-US&gl=US&ceid=US:en"
# the search feeds with when:1h return ~100 titles each, all under an hour old; the top and section feeds lag by hours and add a few
NEWS_FEEDS = [f"{GN}/search?q={q}+when%3A1h&{LOC}" for q in ("news", "breaking", "world", "crypto+OR+bitcoin+OR+solana+OR+memecoin",
                                                             "celebrity+OR+viral+OR+trending", "elon+OR+trump+OR+musk")] \
    + [f"{GN}?{LOC}"] + [f"{GN}/headlines/section/topic/{t}?{LOC}" for t in ("WORLD", "NATION", "BUSINESS", "TECHNOLOGY", "ENTERTAINMENT", "SPORTS")]
NEWS_WINDOW_S = 3600
NEWS_POLL_S = 60
SOL_POLL_S = 60
MCAP_MAX_USD = 10_000
ENTRY_WINDOW_S = 30
SIZE_SOL = 1.5
TAKE = 0.20
STOP = -0.20
HOLD_S = 60
MARK_EVERY = 2
MAX_OPEN = 3
PUMP_FEE = 0.01
TX_FEE_SOL = 0.001
MIN_TERM = 4
WSOL = "So11111111111111111111111111111111111111112"

EVENTS = C.path("journal", "events.jsonl")
PAPER = C.path("journal", "paper.jsonl")
LAUNCHES = C.path("journal", "launches.jsonl")
ALERTS = C.path("monitor", "alerts.log")
ERRORS = C.path("monitor", "feed-errors.log")
HEART = C.path("monitor", "heartbeat.json")
BOOK = C.path("state", "positions.json")
NEWS = C.path("state", "news.json")
SOL_USD = C.path("state", "sol_usd.json")

STOP_WORDS = set("""
the this that these those what why how when where who whom whose here there after before during live update updates news report reports
says said say watch video videos photos photo opinion analysis exclusive breaking review reviews explained explainer latest today tonight
yesterday tomorrow week weekend month year years monday tuesday wednesday thursday friday saturday sunday january february march april may june
july august september october november december cnn reuters cnbc bbc nbc abc cbs fox times post journal bloomberg guardian insider yahoo npr
politico axios forbes fortune verge techcrunch variety deadline espn usa associated press wall street stock stocks market markets dow nasdaq
shares share price prices percent points million billion trillion first second third new york city state states united kingdom america american
americans president house senate congress court supreme white official officials police officer officers man woman people person family
world national international global company companies inc corp group ceo chief executive report reported reporting live updates
east west north south middle central northern southern eastern western former latest early late inside outside
about above according across after again against ahead almost along already also although always among amid announce announces announced
another anyone anything around because become becomes been before behind being below between beyond both brings calls came cannot change
changes closer coming could despite does doing done down during each either enough even ever every everyone everything finally following
from further gets getting give gives goes going gone good great having heard helps high higher hits holds huge inside into just keep
keeps know known large last later least less likely little long look looks made major makes making many might more most much must near
nearly need needs never next nothing often only onto open other others over part plan plans push pushes puts rather really right rise rises
says sees seen sends several should shows since some something soon still such take takes taking tells than their them then they thing things
think this those though three through time times told took toward turns under until upon very wants warns watch ways well went were what
where whether which while will with within without would years your
""".split())
DIRECTION = set("east west north south middle central northern southern eastern western".split())
PAIR_STOP = STOP_WORDS - DIRECTION
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’]*")


def alert(line):
    C.append(ALERTS, {"alert": line})
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if tok and chat:
        try:
            C.http_json(f"https://api.telegram.org/bot{tok}/sendMessage",
                        json.dumps({"chat_id": chat, "text": line, "disable_web_page_preview": True}).encode(), tries=2, timeout=10)
        except Exception as e:
            C.append(ALERTS, {"telegram_error": str(e)[:120]})


def err(where, e):
    C.append(ERRORS, {"feed": where, "err": str(e)[:200]})


# ---------------------------------------------------------------- the hour's news

def _caps(title):
    title = html.unescape(re.sub(r"\s+-\s+[^-]+$", "", title))       # drop the trailing ' - Source'
    words = TOKEN_RE.findall(title)
    return [(i, w) for i, w in enumerate(words) if (w[:1].isupper() and len(w) >= MIN_TERM) or (w.isupper() and len(w) >= 3)]


def _title_case(title):
    """Outlets that capitalise Every Word make capitalisation useless as a proper-noun signal."""
    words = [w for w in TOKEN_RE.findall(title) if len(w) >= MIN_TERM]
    return len(words) >= 3 and sum(1 for w in words if w[:1].isupper()) / len(words) > 0.6


def _terms(title, mid_caps=None):
    """Proper nouns (capitalised words and all-caps acronyms) and adjacent pairs of them, lower-cased, stop words out.
    With mid_caps (the words seen capitalised mid-title in sentence-case titles across the window), a word counts on its own only
    if it is in that set or all caps when it opens a sentence-case title or sits anywhere in a Title Case title: 'Fearing' and
    'Review' open sentences, 'Administration Terminates' is house style, 'Trump' recurs mid-title."""
    caps = _caps(title)
    tc = _title_case(title)
    out = set()
    for i, w in caps:
        lw = w.lower().replace("’", "'")
        if lw in STOP_WORDS or lw.isdigit():
            continue
        if mid_caps is not None and not w.isupper() and (i == 0 or tc) and lw not in mid_caps:
            continue
        out.add(lw)
    for (i, a), (j, b) in zip(caps, caps[1:]):
        if j != i + 1 or a.lower() in PAIR_STOP or b.lower() in PAIR_STOP:   # 'Middle East' is a name; 'Middle' alone is not
            continue
        if mid_caps is not None and tc and not (a.lower() in mid_caps and b.lower() in mid_caps or a.isupper() or b.isupper()):
            continue
        out.add(a.lower() + " " + b.lower())
    return out


def fetch_news():
    """Titles published inside the window, with their terms. Returns {term: [titles]}."""
    now = time.time()
    terms = {}
    titles = []
    for url in NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=C.UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read().decode("utf-8", "ignore")
        except Exception as e:
            err("news", e)
            continue
        for it in re.findall(r"<item>(.*?)</item>", raw, re.S):
            t = re.search(r"<title>(.*?)</title>", it, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", it)
            if not t or not d:
                continue
            try:
                pub = calendar.timegm(time.strptime(d.group(1).strip()[:25], "%a, %d %b %Y %H:%M:%S"))   # GMT; mktime would shift an hour
            except Exception:
                continue
            if now - pub > NEWS_WINDOW_S:
                continue
            title = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1))).strip()
            if title not in titles:
                titles.append(title)
    mid_caps = {w.lower().replace("’", "'") for title in titles if not _title_case(title) for i, w in _caps(title) if i > 0}
    for title in titles:
        for term in _terms(title, mid_caps):
            terms.setdefault(term, [])
            if title not in terms[term]:
                terms[term].append(title)
    return terms


def match(name, symbol, terms):
    """Which headline terms the launch is named after. Single terms must be whole words of the name or the symbol; pairs may run together."""
    words = set(w.lower() for w in TOKEN_RE.findall(name or ""))
    squashed = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    sym = (symbol or "").lower().lstrip("$")
    hits = []
    for term in terms:
        if " " in term:
            if term.replace(" ", "") in squashed or term == (name or "").lower():
                hits.append(term)
        elif term in words or term == sym or (len(term) >= 6 and term in squashed):
            hits.append(term)
    return sorted(hits, key=len, reverse=True)


# ---------------------------------------------------------------- the curve

def buy(v_sol, v_tok, sol):
    """Tokens received for `sol` SOL all-in on a curve with virtual reserves (v_sol, v_tok)."""
    net = sol * (1 - PUMP_FEE) - TX_FEE_SOL
    if net <= 0:
        return 0.0
    k = v_sol * v_tok
    return v_tok - k / (v_sol + net)


def sell(v_sol, v_tok, tokens):
    """SOL received for selling `tokens` into the curve, after fees."""
    k = v_sol * v_tok
    gross = v_sol - k / (v_tok + tokens)
    return max(0.0, gross * (1 - PUMP_FEE) - TX_FEE_SOL)


def decode_curve(b64):
    raw = base64.b64decode(b64)
    v_tok, v_sol, r_tok, r_sol, supply = struct.unpack_from("<QQQQQ", raw, 8)
    return {"v_tok": v_tok / 1e6, "v_sol": v_sol / 1e9, "r_tok": r_tok / 1e6, "r_sol": r_sol / 1e9, "supply": supply / 1e6, "complete": bool(raw[48])}


def rpc_curves(keys):
    d = C.http_json(C.RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                                       "params": [keys, {"encoding": "base64", "commitment": "processed"}]}).encode(), tries=2, timeout=15)
    out = {}
    for k, v in zip(keys, (d.get("result") or {}).get("value") or []):
        if v and v.get("data"):
            out[k] = decode_curve(v["data"][0])
    return out


def block_time(sig):
    try:
        d = C.http_json(C.RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getTransaction",
                                           "params": [sig, {"encoding": "json", "maxSupportedTransactionVersion": 0}]}).encode(), tries=3, timeout=20)
        return (d.get("result") or {}).get("blockTime")
    except Exception:
        return None


# ---------------------------------------------------------------- the book

class Position:
    def __init__(self, d):
        self.__dict__.update(d)

    def to_dict(self):
        return dict(self.__dict__)


class Book:
    def __init__(self):
        self.open = [Position(d) for d in C.load_json(BOOK, [])]
        self.seen = set(r["mint"] for r in C.read_jsonl(PAPER) if r.get("kind") == "entry")

    def save(self):
        C.save_json(BOOK, [p.to_dict() for p in self.open])

    def enter(self, mint, symbol, curve_key, v_sol, v_tok, sol_usd, t, event_id, sig):
        """v_sol, v_tok: the curve's virtual reserves as read on chain at decision time (not the feed's message)."""
        if mint in self.seen or len(self.open) >= MAX_OPEN:
            return None
        tokens = buy(v_sol, v_tok, SIZE_SOL)
        if tokens <= 0:
            return None
        price = SIZE_SOL / tokens                                   # SOL per token, all-in
        p = Position({"mint": mint, "symbol": symbol, "curve": curve_key, "tokens": tokens, "entry": price, "t0": t, "event_id": event_id,
                      "sig": sig, "peak": 0.0, "trough": 0.0, "marks": 0, "last_pct": 0.0, "created": None, "exits": [],
                      "entry_usd": price * sol_usd, "mcap_usd_entry": v_sol / v_tok * 1e9 * sol_usd})
        self.open.append(p)
        self.seen.add(mint)
        C.append(PAPER, {"kind": "entry", "mint": mint, "symbol": symbol, "price": price, "event_id": event_id, "size_sol": SIZE_SOL,
                         "tokens": tokens, "mcap_usd": round(p.mcap_usd_entry), "price_usd": price * sol_usd})
        self.save()
        return p

    def mark_all(self, curves, t):
        closed = []
        for p in list(self.open):
            c = curves.get(p.curve)
            if not c:
                continue
            out = sell(c["v_sol"], c["v_tok"], p.tokens)
            pct = out / SIZE_SOL - 1
            p.marks += 1
            p.last_pct = pct
            p.peak = max(p.peak, pct)
            p.trough = min(p.trough, pct)
            held = t - p.t0
            why = "take" if pct >= TAKE else "stop" if pct <= STOP else "time" if held >= HOLD_S else "complete" if c["complete"] else None
            if not why:
                continue
            e = {"t": C.iso(t), "frac": 1.0, "pct": round(pct, 4), "why": why}
            p.exits.append(e)
            C.append(PAPER, {"kind": "exit", "mint": p.mint, "symbol": p.symbol, **e})
            rec = {"kind": "close", "mint": p.mint, "symbol": p.symbol, "entry": p.entry, "net_sol": round(out - SIZE_SOL, 4), "held_s": int(held),
                   "exits": p.exits, "event_id": p.event_id, "peak_pct": round(p.peak, 4), "trough_pct": round(p.trough, 4), "marks": p.marks,
                   "mcap_usd_entry": round(p.mcap_usd_entry), "created": p.created,
                   "create_to_entry_s": round(p.t0 - p.created, 1) if p.created else None}
            C.append(PAPER, rec)
            self.open.remove(p)
            closed.append(rec)
        self.save()
        return closed


# ---------------------------------------------------------------- the loop

class Duval:
    def __init__(self):
        self.book = Book()
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.terms = C.load_json(NEWS, {}).get("terms", {})
        self.sol_usd = C.load_json(SOL_USD, {}).get("usd")
        self.launches = 0
        self.matched = 0
        self.last_launch = None
        self.event_ids = set(e["id"] for e in C.read_jsonl(EVENTS) if str(e.get("id", "")).startswith("pump:"))

    async def run(self):
        for coro in (self.news_loop(), self.sol_loop(), self.pump_loop(), self.mark_loop()):
            asyncio.create_task(coro)
        while True:
            C.save_json(HEART, {"pid": os.getpid(), "ts": C.iso(), "open": len(self.book.open), "events": self.launches, "matched": self.matched,
                                "news_terms": len(self.terms), "sol_usd": self.sol_usd, "last_launch": self.last_launch, "leg": "RI-04"})
            await asyncio.sleep(5)

    async def news_loop(self):
        while True:
            try:
                terms = await asyncio.to_thread(fetch_news)
                if terms:
                    self.terms = terms
                    C.save_json(NEWS, {"ts": C.iso(), "terms": terms})
            except Exception as e:
                err("news", e)
            await asyncio.sleep(NEWS_POLL_S)

    async def sol_loop(self):
        while True:
            try:
                d = await asyncio.to_thread(C.http_json, f"https://api.dexscreener.com/tokens/v1/solana/{WSOL}", None, 2, 15)
                px = float(d[0].get("priceUsd") or 0)
                if px > 0:
                    self.sol_usd = px
                    C.save_json(SOL_USD, {"usd": px, "ts": C.iso()})
            except Exception as e:
                err("sol_usd", e)
            await asyncio.sleep(SOL_POLL_S)

    async def pump_loop(self):
        while True:
            try:
                async with websockets.connect(PP_WS, ping_interval=20, open_timeout=20, max_size=2 ** 20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    async for raw in ws:
                        try:
                            m = json.loads(raw)
                        except Exception:
                            continue
                        if m.get("txType") == "create" and m.get("mint"):
                            self.on_launch(m, time.time())
            except Exception as e:
                err("pump", e)
                await asyncio.sleep(5)

    def on_launch(self, m, t):
        self.launches += 1
        self.last_launch = C.iso(t)
        name, sym, mint = m.get("name") or "", m.get("symbol") or "", m["mint"]
        v_sol, v_tok = float(m.get("vSolInBondingCurve") or 0), float(m.get("vTokensInBondingCurve") or 0)
        mcap_usd = (v_sol / v_tok * 1e9 * self.sol_usd) if (v_sol and v_tok and self.sol_usd) else None
        hits = match(name, sym, self.terms)
        C.append(LAUNCHES, {"ts": C.iso(t), "mint": mint, "name": name[:60], "symbol": sym[:20], "mcap_usd": round(mcap_usd) if mcap_usd else None,
                            "init_sol": m.get("solAmount"), "pool": m.get("pool"), "mayhem": bool(m.get("is_mayhem_mode")), "match": hits[:4]})
        if not hits:
            return
        self.matched += 1
        eid = f"pump:{mint}"
        if eid in self.event_ids:
            return
        self.event_ids.add(eid)
        self.pool.submit(self._decide, m, t, hits, name, sym, mint, v_sol, v_tok, mcap_usd, eid)

    def _decide(self, m, t, hits, name, sym, mint, v_sol, v_tok, mcap_usd, eid):
        """Off the feed thread: read the curve on chain, screen, enter, write the event. Errors are logged, never silent."""
        try:
            self._screen_and_enter(m, t, hits, name, sym, mint, v_sol, v_tok, mcap_usd, eid)
        except Exception as e:
            err("decide", e)

    def _screen_and_enter(self, m, t, hits, name, sym, mint, v_sol, v_tok, mcap_usd, eid):
        why = []
        if not mint.endswith("pump"):
            why.append("mint is not a pump.fun mint (no 'pump' suffix)")
        if m.get("pool") not in (None, "pump"):
            why.append(f"pool {m.get('pool')}")
        if m.get("is_mayhem_mode"):
            why.append("mayhem mode")
        chain = None
        if not why and m.get("bondingCurveKey"):
            for _ in range(2):                                   # the account exists once the create tx is processed; one retry
                chain = rpc_curves([m["bondingCurveKey"]]).get(m["bondingCurveKey"])
                if chain:
                    break
                time.sleep(0.5)
            if not chain:
                why.append("curve account not readable at decision")
            elif chain["complete"]:
                why.append("curve already complete")
            elif not (0.5 <= chain["v_sol"] / max(v_sol, 1e-9) <= 2.0):
                why.append(f"on-chain reserves differ from the feed (vSol {chain['v_sol']:.1f} vs {v_sol:.1f}): non-standard curve")
            else:
                v_sol, v_tok = chain["v_sol"], chain["v_tok"]
                mcap_usd = v_sol / v_tok * 1e9 * self.sol_usd if self.sol_usd else None
        if mcap_usd is None:
            why.append("no mcap (sol price or curve missing)")
        elif mcap_usd >= MCAP_MAX_USD:
            why.append(f"mcap ${mcap_usd:,.0f} >= ${MCAP_MAX_USD:,}")
        if time.time() - t > ENTRY_WINDOW_S:
            why.append("past the 30 s window")
        ok = not why
        snap = {"price": (v_sol / v_tok * self.sol_usd) if (v_tok and self.sol_usd) else 0, "liq": round(v_sol * (self.sol_usd or 0)),
                "mcap_usd": round(mcap_usd) if mcap_usd else None, "v_sol": v_sol, "v_tok": v_tok, "init_sol": m.get("solAmount"),
                "dev": m.get("traderPublicKey"), "age_s": round(time.time() - t, 2), "chain": chain}
        res = {"mint": mint, "symbol": sym, "pass": ok, "why": why, "snap": snap, "intent": True, "t_screened": time.time()}
        pos = None
        if ok:
            with self.lock:
                pos = self.book.enter(mint, sym, m.get("bondingCurveKey"), v_sol, v_tok, self.sol_usd, time.time(), eid, m.get("signature"))
            res["entry"] = bool(pos)
            res["t_entry"] = time.time()
            if pos:
                alert(f"LAUNCH {name} ({sym}) {mint} matches {hits[:3]} mcap ${mcap_usd:,.0f} PAPER ENTRY {SIZE_SOL} SOL @ {pos.entry:.3e} SOL/tok "
                      f"({pos.tokens/1e6:.1f}M tokens) {time.time()-t:.1f}s after the feed")
                self._stamp(pos)
            else:
                alert(f"LAUNCH {name} ({sym}) matches {hits[:3]} mcap ${mcap_usd:,.0f} PASS, no entry (book full)")
        else:
            res["entry"] = False
        accepted = [{"mint": mint, "symbol": sym, "name": name, "phrase": hits[0], "via": "ticker", "terms": hits[:4],
                     "headlines": [h for term in hits[:2] for h in self.terms.get(term, [])[:2]]}]
        C.append(EVENTS, {"id": eid, "feed": "pump", "person": "launch", "kind": "create", "text": f"{name} ({sym}) ~ {'; '.join(accepted[0]['headlines'][:2])}",
                          "when": C.iso(t), "t_src": t, "t_seen": t, "accepted": accepted, "near": [], "screen": [res],
                          "latency": {"source_to_seen": 0.0, "resolve": 0.0, "to_decision": round(time.time() - t, 3)}})

    def _stamp(self, pos):
        bt = block_time(pos.sig) if pos.sig else None
        if bt:
            with self.lock:
                pos.created = bt
                self.book.save()

    async def mark_loop(self):
        while True:
            t0 = time.time()
            if self.book.open:
                try:
                    curves = await asyncio.to_thread(rpc_curves, [p.curve for p in self.book.open])
                    with self.lock:
                        closed = self.book.mark_all(curves, time.time())
                    for rec in closed:
                        alert(f"PAPER CLOSE {rec['symbol']} net {rec['net_sol']:+.3f} SOL after {rec['held_s']}s ({rec['exits'][-1]['why']}, "
                              f"peak {rec['peak_pct']:+.0%} trough {rec['trough_pct']:+.0%}, {rec['marks']} marks)")
                except Exception as e:
                    err("mark", e)
            await asyncio.sleep(max(0.2, MARK_EVERY - (time.time() - t0)))


if __name__ == "__main__":
    asyncio.run(Duval().run())
