"""Turn a named person's words into a coin under the contract's exact-name rule. Candidates are searched in parallel; never guesses."""
import re
from concurrent.futures import ThreadPoolExecutor

import common as C

MINT_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
TICKER_RE = re.compile(r"\$([A-Za-z0-9+]{1,12})")
CAP_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b")
PLUS_RE = re.compile(r"\+{3,}")
POOL = ThreadPoolExecutor(max_workers=8)


def phrases(text, ignore):
    """Candidate phrases in priority order: mints, $tickers, +++ runs, capitalised 1-3 word n-grams.
    Amendment 1: a lone capitalised word counts only when written in capitals (ANSEM), never as sentence case (State)."""
    out = [("mint", m) for m in MINT_RE.findall(text)]
    out += [("ticker", t) for t in TICKER_RE.findall(text)]
    out += [("ticker", p) for p in PLUS_RE.findall(text)]
    seen = set()
    for g in CAP_RE.findall(text):
        words = g.split()
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                ph = " ".join(words[i:i + n])
                if ph in ignore or ph.lower() in seen or len(ph) < 3 or (n == 1 and not ph.isupper()):
                    continue
                seen.add(ph.lower())
                out.append(("name", ph))
    return out


def _lookup(kind, ph):
    pairs = [p for p in C.dex_tokens([ph]) if p.get("chainId") == "solana"] if kind == "mint" else C.dex_search(ph)
    return kind, ph, pairs


def resolve(text, event_ts, ignore=()):
    """Return (accepted, near_misses). accepted = [{'mint','symbol','name','phrase','pair'}] by the exact rule."""
    accepted, near, taken = [], [], set()
    for kind, ph, pairs in POOL.map(lambda kp: _lookup(*kp), phrases(text, set(ignore))):
        key = ph.lower()
        exact = [p for p in pairs
                 if (p["baseToken"]["symbol"].lower() == key or p["baseToken"]["name"].lower() == key or p["baseToken"]["address"] == ph)
                 and (p.get("pairCreatedAt") or 0) / 1000 < event_ts
                 and ((p.get("liquidity") or {}).get("usd") or 0) >= C.LIQ_FLOOR]
        best = C.best_pair(exact)
        if best and best["baseToken"]["address"] not in taken:
            taken.add(best["baseToken"]["address"])
            accepted.append({"mint": best["baseToken"]["address"], "symbol": best["baseToken"]["symbol"],
                             "name": best["baseToken"]["name"], "phrase": ph, "pair": best["pairAddress"]})
        elif pairs and not exact:
            top = C.best_pair(pairs)
            near.append({"phrase": ph, "closest": top["baseToken"]["symbol"], "liq": (top.get("liquidity") or {}).get("usd")})
    return accepted, near
