"""Roster discovery: find named people who are touching coins and add them under the pre-registered bar.
Sources: X recent search over the recap accounts' posts (mentions + capitalised names), DexScreener token profiles whose
social link repeats across tokens. Scoring: X users lookup (followers, account age, description).
Auto-add: followers >= AUTO_FOLLOWERS and account age >= AUTO_AGE_DAYS and not a token account. Others -> prereg/CANDIDATES.json.
Every change is appended to journal/roster.jsonl. Runs daily (rich - DISCOVER); safe to run by hand."""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C  # noqa: E402

AUTO_FOLLOWERS = 500_000
AUTO_AGE_DAYS = 365
REPEAT_LINKS = 3
MAX_ROSTER = 28           # keeps the single stream rule under X's 512-character limit
TOKEN_WORDS = re.compile(r"\b(token|coin|\$[A-Z]{2,}|CA:|contract|memecoin|airdrop|presale)\b", re.I)
MENTION_RE = re.compile(r"@([A-Za-z0-9_]{2,15})")
ROSTER_FILE = os.path.join(C.ROOT, "prereg", "ROSTER.json")
CANDIDATES = os.path.join(C.ROOT, "prereg", "CANDIDATES.json")
LOG = C.path("journal", "roster.jsonl")
BEARER = os.environ.get("X_BEARER")


def x_get(url):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + BEARER, "User-Agent": "rich/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def recap_mentions(recap_accounts, state):
    """Handles mentioned in the recap accounts' last-day posts, with the mention count."""
    counts = {}
    if not BEARER or not recap_accounts:
        return counts
    q = "(" + " OR ".join("from:" + a for a in recap_accounts) + ") -is:retweet"
    url = "https://api.x.com/2/tweets/search/recent?max_results=50&tweet.fields=entities,created_at&query=" + urllib.parse.quote(q)
    since = state.get("discover_since_id")
    if since:
        url += "&since_id=" + since
    d = x_get(url)
    for t in d.get("data") or []:
        for m in (t.get("entities") or {}).get("mentions", []):
            counts[m["username"].lower()] = counts.get(m["username"].lower(), 0) + 1
        for h in MENTION_RE.findall(t["text"]):
            counts[h.lower()] = counts.get(h.lower(), 0) + 1
    newest = (d.get("meta") or {}).get("newest_id")
    if newest:
        state["discover_since_id"] = newest
    return counts


def profile_links(state):
    """Handles that DexScreener token profiles link to, counted across days (a person being coined repeatedly)."""
    seen = state.setdefault("profile_links", {})
    for url in ("https://api.dexscreener.com/token-profiles/latest/v1", "https://api.dexscreener.com/token-boosts/latest/v1"):
        for p in C.http_json(url):
            if p.get("chainId") != "solana":
                continue
            for l in p.get("links") or []:
                m = re.search(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)(?:/status/)?", l.get("url") or "")
                if m and "/status/" not in (l.get("url") or ""):
                    h = m.group(1).lower()
                    seen.setdefault(h, {})[p["tokenAddress"]] = int(time.time())
    return {h: len(toks) for h, toks in seen.items() if len(toks) >= REPEAT_LINKS}


def score(handles):
    """X users lookup in batches of 100: followers, created_at, description."""
    out = {}
    if not BEARER:
        return out
    hs = sorted(handles)
    for i in range(0, len(hs), 100):
        d = x_get("https://api.x.com/2/users/by?user.fields=public_metrics,created_at,description,verified&usernames=" + ",".join(hs[i:i + 100]))
        for u in d.get("data") or []:
            age_days = (time.time() - time.mktime(time.strptime(u["created_at"][:19], "%Y-%m-%dT%H:%M:%S"))) / 86400
            out[u["username"].lower()] = {"handle": u["username"], "name": u["name"], "followers": u["public_metrics"]["followers_count"],
                                          "age_days": int(age_days), "description": u.get("description", ""), "token_account": bool(TOKEN_WORDS.search(u.get("description", "") + " " + u["name"]))}
    return out


def main():
    roster = C.load_json(ROSTER_FILE, {})
    state = C.load_json(C.path("state", "discover.json"), {})
    have = {h["handle"].lower() for h in roster["x"]} | {c.lower() for c in roster.get("recap_accounts", [])} | set(roster.get("x_rejected", []))
    mentions = recap_mentions(roster.get("recap_accounts", []), state)
    links = profile_links(state)
    cands = {h: {"mentions": mentions.get(h, 0), "linked_tokens": links.get(h, 0)} for h in set(mentions) | set(links) if h not in have}
    scored = score(cands)
    added, parked = [], []
    for h, s in scored.items():
        s.update(cands[h])
        if s["followers"] >= AUTO_FOLLOWERS and s["age_days"] >= AUTO_AGE_DAYS and not s["token_account"] and len(roster["x"]) < MAX_ROSTER:
            roster["x"].append({"handle": s["handle"], "person": s["name"], "added": C.iso(), "why": f"auto: {s['followers']:,} followers, {s['mentions']} recap mentions, {s['linked_tokens']} linked tokens"})
            added.append(s)
        else:
            parked.append(s)
    if added:
        C.save_json(ROSTER_FILE, roster)
    C.save_json(CANDIDATES, sorted(parked, key=lambda s: -s["followers"])[:200])
    C.save_json(C.path("state", "discover.json"), state)
    C.append(LOG, {"added": [s["handle"] for s in added], "parked": len(parked), "roster_size": len(roster["x"]), "mentions_seen": len(mentions), "linked": len(links)})
    print(f"discover: added {[s['handle'] for s in added]}, parked {len(parked)} (top: {[s['handle'] for s in sorted(parked, key=lambda s: -s['followers'])[:5]]}), roster {len(roster['x'])}")


if __name__ == "__main__":
    main()
