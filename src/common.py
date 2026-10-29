"""Shared plumbing: paths, clock, JSON lines, RPC and DexScreener with backoff, roster."""
import json
import os
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPC = os.environ.get("RICH_RPC", "https://api.mainnet-beta.solana.com")
WS = os.environ.get("RICH_WS", "wss://api.mainnet-beta.solana.com")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130", "Accept": "application/json"}
LIQ_FLOOR = 20_000
BUYERS_H1 = 50
MIN_AGE_MIN = 10
MAX_MC = 250_000_000
DEV_BUNDLE_SOL = 60.0


def path(*parts):
    p = os.path.join(ROOT, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def now():
    return time.time()


def iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now() if t is None else t))


def append(file, rec):
    rec.setdefault("ts", iso())
    with open(file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _corrupt(file, what):
    """A hard crash leaves NUL-filled files and torn lines (2026-10-09, 10-24, 10-28). They are measurement damage, not data:
    log the skip to monitor/journal-errors.log and carry on, instead of dying at startup until an operator repairs by hand."""
    try:
        append(path("monitor", "journal-errors.log"), {"where": "loader", "err": f"{what} in {os.path.relpath(file, ROOT)}"[:200]})
    except Exception:
        pass


def read_jsonl(file):
    if not os.path.exists(file):
        return []
    rows, skipped = [], 0
    with open(file, encoding="utf-8", errors="replace") as f:
        for l in f:
            if not l.strip() or l[0] == "\x00":
                skipped += l[:1] == "\x00"
                continue
            try:
                rows.append(json.loads(l))
            except ValueError:
                skipped += 1
    if skipped:
        _corrupt(file, f"skipped {skipped} unparseable line(s)")
    return rows


def load_json(file, default):
    if not os.path.exists(file):
        return default
    with open(file, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if not raw.strip("\x00 \r\n\t"):
        _corrupt(file, f"NUL-filled or empty file ({len(raw)} bytes), read as missing")
        return default
    return json.loads(raw)


def save_json(file, obj):
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, file)


def http_json(url, data=None, tries=6, timeout=40):
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, "content-type": "application/json"} if data else UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # 429s, resets, bad gateways: all retry with backoff
            err = e
            time.sleep(min(60, 2 * (i + 1)))
    raise err


def rpc(method, params):
    d = http_json(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode())
    if "error" in d:
        raise RuntimeError(d["error"])
    return d["result"]


def dex_search(q):
    d = http_json("https://api.dexscreener.com/latest/dex/search?q=" + urllib.parse.quote(q))
    return [p for p in d.get("pairs", []) if p.get("chainId") == "solana"]


def dex_tokens(mints):
    out = []
    for i in range(0, len(mints), 30):
        out += http_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(mints[i:i + 30]))
    return out


def best_pair(pairs):
    """The pair that carries the token: deepest liquidity."""
    return max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0) if pairs else None


def roster():
    return load_json(os.path.join(ROOT, "prereg", "ROSTER.json"), {})
