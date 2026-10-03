"""The Foresight Journal: what we said would happen, what happened, how surprised we were, and what we changed.

forecast/beliefs.jsonl      the mental model, one row per belief version (the last row per id is current)
forecast/predictions.jsonl  claims with a probability, written before the outcome
forecast/scores.jsonl       outcomes, resolved from journal/ by a named metric wherever one exists
forecast/lessons.jsonl      why a forecast missed (or hit for the wrong reason), and which belief moved
journal/shadow.jsonl        one row per screened touch, pass or fail: what the contract's exits would have booked over 24 h
journal/shadow_paths.jsonl  the 24 h price path behind each shadow row
journal/excursions.jsonl    one row per closed paper trade: best and worst mark while held, peak in the 24 h after exit

The four forecast files are append-only and hash-chained; `verify` fails on any edit. Observation only: nothing here
enters, exits or screens a trade.

  python ops/journal.py predict --claim ... --metric closed --direction ge --threshold 40 --confidence 0.8 --deadline 2026-12-31 --basis ...
  python ops/journal.py predict ... --metric mk_intent@2026-10-04..2026-10-17 ...   (a market forecast: written first, read after its window)
  python ops/journal.py predict ... --rests-on <market pred_id>                   (every leg forecast names the market forecast under it)
  python ops/journal.py predict --like <pred_id> --who irvin --confidence 0.6     (a second forecaster on the same question)
  python ops/journal.py blind [--who irvin]                                       (open questions without anyone's numbers, to answer first)
  python ops/journal.py market [--days 7]                                         (the market state table, day by day)
  python ops/journal.py resolve <pred_id> yes|no --note ...                       (manual metrics only)
  python ops/journal.py lesson --pred <pred_id> --what ... --why ... --cause model --belief B1 --p 0.2 --rule ...
  python ops/journal.py belief --id B9 --claim ... --p 0.6 --why ... --falsifier ...
  python ops/journal.py tick | review | metrics | verify
"""
import argparse
import calendar
import datetime
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C   # noqa: E402
import paper as P    # noqa: E402
import readout as R  # noqa: E402

BELIEFS = C.path("forecast", "beliefs.jsonl")
PREDS = C.path("forecast", "predictions.jsonl")
SCORES = C.path("forecast", "scores.jsonl")
LESSONS = C.path("forecast", "lessons.jsonl")
CHAINED = (BELIEFS, PREDS, SCORES, LESSONS)
EVENTS = C.path("journal", "events.jsonl")
PAPER = C.path("journal", "paper.jsonl")
SHADOW = C.path("journal", "shadow.jsonl")
PATHS = C.path("journal", "shadow_paths.jsonl")
SHADOW_STATE = C.path("state", "shadow.json")
EXC = C.path("journal", "excursions.jsonl")
EXC_STATE = C.path("state", "excursion.json")
SOL_USD = C.path("state", "sol_usd.json")
MK_WAIT = C.path("state", "mk_wait.json")
BLIND = C.path("out", "blind.md")
REPORT = C.path("out", "journal.md")
ERRORS = C.path("monitor", "journal-errors.log")

LATE_START_S = 900       # a shadow whose first mark came later than this missed part of the path: kept, never scored
MIN_SIDE = 8             # a pass-vs-fail comparison is undefined below this many independent rows a side
OWED_BITS = 1.0          # a resolved forecast that gave under 50 % to what happened owes a lesson
CAUSES = ("model", "variance", "measurement", "question", "execution")
OPS = {"gt": lambda x, t: x > t, "ge": lambda x, t: x >= t, "lt": lambda x, t: x < t, "le": lambda x, t: x <= t,
       "eq": lambda x, t: x == t, "in": lambda x, t: t[0] <= x <= t[1]}
AUTO_BELIEF = {True: "B1", False: "B3"}   # the belief whose seed prior forecasts a pass / a fail shadow
WSOL = "So11111111111111111111111111111111111111112"
MK_RE = re.compile(r"^(mk_(?:touches|resolved|intent|pass_rate|ret24|up|rtshare|rtgap))@(\d{4}-\d\d-\d\d)(?:\.\.(\d{4}-\d\d-\d\d))?$")
MK_LATE = ("mk_ret24", "mk_up", "mk_rtgap")   # read from 24 h shadows: known a day after the window ends
MK_TRIES = 12            # ticks (an hour) a due market forecast waits for its window's shadows to close before it voids
MIN_RT = 3               # retweets against own words is undefined below this many closed shadows a side
SIDES = ("market", "screen", "exits")
# which half of the rule a metric speaks for once the market is excused; anything else is the book's result (both halves)
SIDE = {**{k: "screen" for k in ("pass_rate", "passes", "entries", "entries_truth", "entries_wallet", "entries_x", "entries_profile", "closed",
                                 "truth_share", "sh_fail_minus_pass", "sh_wins_fail", "sh_mean_net_fail")},
        **{k: "exits" for k in ("stop_share", "stale_share", "mean_loss", "sh_stop_regret", "sh_stops_recovered", "sh_capture_pass")}}
# the market family a metric rests on, for forecasts written before they named one
REST = {**{k: "mk_intent" for k in ("closed", "entries", "entries_truth", "entries_wallet", "entries_x", "entries_profile", "kill_ever")},
        "pass_rate": "mk_pass_rate",
        **{k: "mk_ret24" for k in ("cum_net", "mean_net", "win_rate", "mean_loss", "s1", "stop_share", "stale_share", "sh_stop_regret",
                                   "sh_peak100_pass", "sh_10x_pass", "sh_fail_minus_pass")}}


# ---------------------------------------------------------------- chain

def _hash(rec):
    return hashlib.sha256(json.dumps({k: v for k, v in rec.items() if k != "h"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def chain_append(file, rec):
    rows = C.read_jsonl(file)
    rec = {**rec, "ts": rec.get("ts") or C.iso(), "prev": rows[-1]["h"] if rows else ""}
    rec["h"] = _hash(rec)
    with open(file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def verify():
    """Every forecast file must replay: each row's hash matches its content and points at the row before it."""
    bad = []
    for file in CHAINED:
        prev = ""
        for i, r in enumerate(C.read_jsonl(file), 1):
            if r.get("prev") != prev or r.get("h") != _hash(r):
                bad.append(f"{os.path.basename(file)} row {i}: chain broken")
                break
            prev = r["h"]
    return bad


def leg():
    with open(os.path.join(C.ROOT, "prereg", "CONTRACT.md"), encoding="utf-8") as f:
        m = re.search(r"contract (\S+)", f.readline())
    return m.group(1) if m else "?"


def _git():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=C.ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _epoch(iso):
    return calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))


# ---------------------------------------------------------------- shadow book

def _quotes(mints):
    """{mint: (priceUsd, liquidity)} from the deepest pair, the same mark the sensor uses."""
    out = {}
    for p in C.dex_tokens(sorted(set(mints))) if mints else []:
        m, liq = p["baseToken"]["address"], (p.get("liquidity") or {}).get("usd") or 0
        if liq >= out.get(m, (0, -1))[1]:
            out[m] = (float(p.get("priceUsd") or 0), liq)
    return out


def independent(r):
    """First touch of a mint in 24 h, watched from the start, with a quote: the rows statistics may use."""
    return r["repeat"] == 0 and r["gap_s"] is not None and r["gap_s"] <= LATE_START_S and r["net_sol"] is not None


def shadow_stats(rows):
    ind = [r for r in rows if independent(r)]
    side = {True: [r for r in ind if r["pass"]], False: [r for r in ind if not r["pass"]]}
    mean = lambda rs: sum(r["net_sol"] for r in rs) / len(rs) if rs else None  # noqa: E731
    stops = [r for r in side[True] if "stop" in r["exits"]]
    both = len(side[True]) >= MIN_SIDE and len(side[False]) >= MIN_SIDE
    return {
        "sh_n_pass": len(side[True]), "sh_n_fail": len(side[False]),
        "sh_wins_pass": sum(r["win"] for r in side[True]), "sh_wins_fail": sum(r["win"] for r in side[False]),
        "sh_peak100_pass": sum(1 for r in side[True] if r["peak_pct"] >= 1.0),
        "sh_10x_pass": sum(1 for r in side[True] if r["peak_pct"] >= 9.0),
        "sh_mean_net_pass": mean(side[True]), "sh_mean_net_fail": mean(side[False]),
        "sh_fail_minus_pass": mean(side[False]) - mean(side[True]) if both else None,
        "sh_capture_pass": _capture(side[True]),
        "sh_n_stops": len(stops), "sh_stops_recovered": sum(1 for r in stops if (r["after_stop_peak_pct"] or -1) > 0),
        "sh_stop_regret": sum(1 for r in stops if (r["after_stop_peak_pct"] or -1) > 0) / len(stops) if len(stops) >= MIN_SIDE else None,
    }


def auto_p(passed, stats, beliefs):
    """P(a shadow closes net > 0): the belief's seed prior, updated by every independent shadow closed so far."""
    seed = next(b for b in beliefs if b["id"] == AUTO_BELIEF[passed])
    side = "pass" if passed else "fail"
    return (seed["p"] * seed["n0"] + stats[f"sh_wins_{side}"]) / (seed["n0"] + stats[f"sh_n_{side}"])


def _at(path, horizon_s, entry):
    for dt, price, _ in path:
        if dt >= horizon_s:
            return round(price / entry - 1, 4) if dt - horizon_s <= LATE_START_S else None
    return None


def _finalise(s, now):
    pos, path, entry = P.Position.from_dict(s["pos"]), s["path"], s["entry"]
    row = {k: s[k] for k in ("key", "event_id", "mint", "symbol", "feed", "kind", "person", "pass", "why", "snap", "latency",
                             "entry", "repeat", "gap_s", "forecast", "leg")}
    row["t0"] = C.iso(s["t0"])
    if not path:
        return {**row, "net_sol": None, "win": None, "exits": [], "marks": 0}
    if not pos.closed:   # the quote vanished before the time stop: book what was last seen and say so
        pos._book(pos.remaining, path[-1][1] / entry - 1, now, "time-noquote")
    peak, trough = max(path, key=lambda x: x[1]), min(path, key=lambda x: x[1])
    stop_t = next((_epoch(e["t"]) - s["t0"] for e in pos.exits if e["why"] == "stop"), None)
    after = [x[1] for x in path if stop_t is not None and x[0] > stop_t]
    net = round(pos.net_sol(), 4)
    return {**row, "net_sol": net, "win": int(net > 0), "exits": [e["why"] for e in pos.exits],
            "held_s": int(_epoch(pos.exits[-1]["t"]) - s["t0"]),
            "peak_pct": round(peak[1] / entry - 1, 4), "peak_s": peak[0], "trough_pct": round(trough[1] / entry - 1, 4), "trough_s": trough[0],
            "ret_1h": _at(path, 3600, entry), "ret_6h": _at(path, 6 * 3600, entry), "ret_24h": round(path[-1][1] / entry - 1, 4),
            "after_stop_peak_pct": round(max(after) / entry - 1, 4) if after else None,
            "liq_end_ratio": round(path[-1][2] / s["snap"]["liq"], 3) if s["snap"].get("liq") else None,
            "quote_lost_s": path[-1][0] if now - s["t0"] - path[-1][0] > LATE_START_S else None,
            "brier": round((s["forecast"]["p_win"] - int(net > 0)) ** 2, 4), "marks": len(path)}


def shadow_tick(now=None, quotes=None):
    """Open a shadow for every newly screened touch, mark every open shadow, close the ones 24 h old.
    A shadow runs the contract's own exits (paper.Position) on a coin the screen passed or rejected, and keeps
    watching after a stop, so the screen and the stop can both be judged against what they turned away."""
    now = now or C.now()
    st = C.load_json(SHADOW_STATE, {})
    done = C.read_jsonl(SHADOW)
    known = set(st) | {r["key"] for r in done}
    touched = [(r["mint"], _epoch(r["t0"])) for r in done] + [(s["mint"], s["t0"]) for s in st.values()]
    stats, beliefs, this_leg = shadow_stats(done), C.read_jsonl(BELIEFS), leg()
    for ev in C.read_jsonl(EVENTS):
        for x in ev.get("screen", []):
            key, snap = ev["id"] + "|" + x["mint"], x.get("snap") or {}
            t0 = x.get("t_screened") or _epoch(ev["ts"])
            if key in known or (snap.get("price") or 0) <= 0 or now - t0 >= P.TIME_STOP_S:
                continue
            known.add(key)
            st[key] = {"key": key, "event_id": ev["id"], "mint": x["mint"], "symbol": x["symbol"], "feed": ev["feed"], "kind": ev["kind"],
                       "person": ev["person"], "pass": x["pass"], "why": x["why"], "snap": snap, "latency": ev.get("latency"),
                       "entry": snap["price"], "t0": t0, "leg": this_leg, "gap_s": None, "path": [],
                       "repeat": sum(1 for m, t in touched if m == x["mint"] and 0 <= t0 - t < P.TIME_STOP_S),
                       "forecast": {"p_win": round(auto_p(x["pass"], stats, beliefs), 4), "made": C.iso(now)},
                       "pos": P.Position(x["mint"], x["symbol"], snap["price"], t0, ev["id"]).to_dict()}
            touched.append((x["mint"], t0))
    quotes = quotes if quotes is not None else _quotes([s["mint"] for s in st.values()])
    for key, s in list(st.items()):
        price, liq = quotes.get(s["mint"], (0, 0))
        dt = now - s["t0"]
        if price > 0:
            if s["gap_s"] is None:
                s["gap_s"] = round(dt)
            s["path"].append([round(dt), price, round(liq)])
            pos = P.Position.from_dict(s["pos"])
            pos.mark(price, now)
            s["pos"] = pos.to_dict()
        if dt >= P.TIME_STOP_S:
            C.append(SHADOW, _finalise(s, now))
            C.append(PATHS, {"key": key, "path": s["path"]})
            del st[key]
    C.save_json(SHADOW_STATE, st)
    return len(st)


# ---------------------------------------------------------------- metrics

def _p50(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def metrics():
    """Every number a forecast may be resolved on. None means not yet defined (fewer than 40 closes, too few shadows)."""
    paper, events = C.read_jsonl(PAPER), C.read_jsonl(EVENTS)
    closes = [r for r in paper if r.get("kind") == "close"]
    entries = [r["event_id"].split(":")[0] for r in paper if r.get("kind") == "entry"]
    nets = [r["net_sol"] for r in closes]
    s = R.stats(nets)
    screened = [x for e in events for x in e.get("screen", [])]
    m = {"closed": s["n"], "wins": s["wins"], "win_rate": s["wins"] / s["n"] if s["n"] else None, "cum_net": s["cum"],
         "mean_net": s["mean"] if s["n"] else None, "max_dd": s["dd"],
         "kill_ever": int(any(R.stats(nets[:i])["verdict"] == "KILL" for i in range(1, len(nets) + 1))),
         "events": len(events), "resolved": sum(1 for e in events if e.get("accepted")), "screened": len(screened),
         "passes": sum(1 for x in screened if x["pass"]),
         "pass_rate": sum(1 for x in screened if x["pass"]) / len(screened) if screened else None, "entries": len(entries)}
    for feed in ("truth", "wallet", "x", "profile"):
        m[f"entries_{feed}"] = entries.count(feed)
        m[f"lat_p50_{feed}"] = _p50([e["latency"]["source_to_seen"] for e in events if e["feed"] == feed and e.get("latency")])
    at40 = R.stats(nets[:40]) if s["n"] >= 40 else None   # frozen on the first 40 closes, the count the gates wait for
    first40 = closes[:40]
    m.update({
        "win_rate_at_40": at40["wins"] / 40 if at40 else None, "mean_net_at_40": at40["mean"] if at40 else None,
        "cum_net_at_40": at40["cum"] if at40 else None, "mean_loss_at_40": at40["mean_loss"] if at40 else None,
        "s1_at_40": int(at40["verdict"] == "SURVIVES ON PAPER") if at40 else None,
        "stop_share_at_40": sum(1 for r in first40 if any(e["why"] == "stop" for e in r["exits"])) / 40 if at40 else None,
        "stale_share_at_40": sum(1 for r in first40 if any(e["why"] == "stale" for e in r["exits"])) / 40 if at40 else None,
        "truth_share_at_40": sum(1 for r in first40 if r["event_id"].startswith("truth:")) / 40 if at40 else None})
    m.update(shadow_stats([r for r in C.read_jsonl(SHADOW) if r["leg"] == leg()]))   # exits differ by leg: never pooled
    cut = [r["net_haircut"] for r in book(closes)]
    known = bool(cut) and None not in cut
    m.update({"cum_net_haircut": sum(cut) if known else None, "mean_net_haircut": sum(cut) / len(cut) if known else None})
    return m

# ---------------------------------------------------------------- market state

def _intent(ev, x):
    """Did the person mean this coin? Rows the sensor wrote before it recorded intent are read the same way it now decides."""
    if "intent" in x:
        return x["intent"]
    if ev.get("mint"):
        return ev["kind"] == "buy"
    a = next((a for a in ev.get("accepted", []) if a["mint"] == x["mint"]), {})
    ph = str(a.get("phrase", ""))
    return a.get("via") in ("mint", "ticker") or len(ph) >= 32 or ("$" + ph.lstrip("$")).lower() in (ev.get("text") or "").lower()


def market(start, end=None, now=None):
    """What the feeds brought over the UTC days start..end, whatever the contract did with it: touches seen, touches that named
    a coin and touches that showed intent (each per day), the screen's pass rate, and how the window's screened coins did over
    their 24 h as a group (median return and share up, first touches watched from the start). The 24 h figures stay None
    until the window is over and every one of its shadows has closed. rtshare is the share of intent touches that are
    retweets (the post starts 'RT @'); rtgap is the median 24 h return of intent touches in the person's own words less
    that of retweeted ones."""
    end, now = end or start, now or C.now()
    days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days + 1
    ev = [e for e in C.read_jsonl(EVENTS) if start <= e["ts"][:10] <= end]
    screened = [(e, x) for e in ev for x in e.get("screen", [])]
    sh = [r for r in C.read_jsonl(SHADOW) if independent(r) and start <= r["t0"][:10] <= end]
    pending = C.iso(now)[:10] <= end or any(start <= C.iso(s["t0"])[:10] <= end for s in C.load_json(SHADOW_STATE, {}).values())
    rets = [r["ret_24h"] for r in sh]
    rt = {e["id"] + "|" + x["mint"]: (e.get("text") or "").startswith("RT @") for e, x in screened if _intent(e, x)}
    own, rts = ([r["ret_24h"] for r in sh if rt.get(r["key"]) is flag] for flag in (False, True))
    return {"mk_rtshare": sum(rt.values()) / len(rt) if rt else None,
            "mk_rtgap": _p50(own) - _p50(rts) if not pending and len(own) >= MIN_RT and len(rts) >= MIN_RT else None,
            "mk_touches": len(ev) / days, "mk_resolved": sum(1 for e in ev if e.get("accepted")) / days,
            "mk_intent": sum(1 for e, x in screened if _intent(e, x)) / days,
            "mk_pass_rate": sum(1 for _, x in screened if x["pass"]) / len(screened) if screened else None,
            "mk_ret24": _p50(rets) if rets and not pending else None,
            "mk_up": sum(1 for x in rets if x > 0) / len(rets) if rets and not pending else None,
            "days": days, "screened": len(screened), "shadows": len(sh), "pending": pending}


def value(metric, m, now=None):
    """A forecast's metric today: a market metric is computed for its own window, anything else is read from metrics()."""
    mk = MK_RE.match(metric)
    return market(mk.group(2), mk.group(3), now)[mk.group(1)] if mk else m.get(metric)


def _base(metric):
    return re.sub(r"_at_40$", "", metric)


def rests(p, preds):
    """(market forecast, inferred) a leg forecast rests on: the one it named, else for rows written before forecasts named
    one, the same forecaster's market forecast of the matching family whose window holds the deadline (the tightest)."""
    if p.get("rests_on"):
        return next((q for q in preds if q["pred_id"] == p["rests_on"]), None), False
    fam, best = REST.get(_base(p["metric"])), None
    for q in preds:
        mk = MK_RE.match(q["metric"])
        if mk and mk.group(1) == fam and q["who"] == p["who"] and q["leg"] == p["leg"] and mk.group(2) <= p["deadline"] <= (mk.group(3) or mk.group(2)):
            if best is None or (mk.group(3) or mk.group(2)) < (MK_RE.match(best["metric"]).group(3) or MK_RE.match(best["metric"]).group(2)):
                best = q
    return best, best is not None


def blame(s, preds=None, scores=None):
    """Where a resolved forecast's miss belongs: (side, why). market: the market forecast it rested on missed too.
    screen / exits: the market did what was forecast, so the rule missed, and the metric says which half of the rule.
    rule: the metric is the book's result, which both halves make; read the capture and what-if tables to split it."""
    preds, scores = preds if preds is not None else C.read_jsonl(PREDS), scores if scores is not None else C.read_jsonl(SCORES)
    p = next(p for p in preds if p["pred_id"] == s["pred_id"])
    if MK_RE.match(p["metric"]):
        return "market", "a forecast of the market itself"
    q, inferred = rests(p, preds)
    if q is None:
        return "unassigned", "rests on no market forecast"
    qs = next((x for x in scores if x["pred_id"] == q["pred_id"]), None)
    tag = f"market forecast `{q['pred_id']}`" + (" (inferred)" if inferred else "")
    if qs is None:
        return "open", f"{tag} has not resolved"
    if qs["outcome"] is None or qs["surprise_bits"] >= OWED_BITS:
        return "market", f"{tag} missed too"
    return SIDE.get(_base(p["metric"]), "rule"), f"{tag} held"


# ---------------------------------------------------------------- winners, losers, capture

def all_paper():
    """Paper rows of every leg: the live journal and the ones archived beside it when a contract was superseded."""
    return [r for f in sorted(glob.glob(os.path.join(os.path.dirname(PAPER), "paper*.jsonl"))) for r in C.read_jsonl(f)]


def _capture(rows):
    """Booked net as a share of the peak that was on offer: sum of net over sum of peaks above entry."""
    top = sum(max(r["peak_pct"], 0.0) for r in rows)
    return sum(r["net_sol"] for r in rows) / (P.SIZE_SOL * top) if top > 0 else None


def movers(day, k=3):
    """One UTC day of the shadow book: the screened coins that ran most and fell most, whether the contract entered each,
    and how much of the peak its exits kept (the paper close where it entered, the shadow's booking where it did not)."""
    paper = all_paper()
    entered = {r["event_id"] + "|" + r["mint"] for r in paper if r.get("kind") == "entry"}
    closed = {r["event_id"] + "|" + r["mint"]: r["net_sol"] for r in paper if r.get("kind") == "close"}
    rows = []
    for r in C.read_jsonl(SHADOW):
        if independent(r) and r["t0"][:10] == day:
            net = closed.get(r["key"], r["net_sol"])
            rows.append({"key": r["key"], "symbol": r["symbol"], "pass": r["pass"], "entered": r["key"] in entered, "peak_pct": r["peak_pct"],
                         "trough_pct": r["trough_pct"], "ret_24h": r["ret_24h"], "net_sol": net,
                         "kept": round(net / (P.SIZE_SOL * r["peak_pct"]), 3) if r["peak_pct"] > 0 else None})
    return {"day": day, "n": len(rows), "ran": sorted(rows, key=lambda r: -r["peak_pct"])[:k], "fell": sorted(rows, key=lambda r: r["trough_pct"])[:k],
            "capture_entered": _capture([r for r in rows if r["entered"]]), "capture_pass": _capture([r for r in rows if r["pass"]]),
            "capture_all": _capture(rows), "n_entered": sum(1 for r in rows if r["entered"])}


def shadow_days():
    return sorted({r["t0"][:10] for r in C.read_jsonl(SHADOW) if independent(r)})


# ---------------------------------------------------------------- the haircut

def haircut(liq, sol_usd=None):
    """SOL a real round trip of the contract's size would lose against the deepest pair's mark, before fees. DexScreener
    quotes a pool's liquidity as both sides, so a buy of `usd` moves a constant-product pool about usd / (liq / 2), and
    the sale gives the same back: 4 x usd / liq of the size. An estimate from the entry snapshot, never a fill."""
    sol_usd = sol_usd or C.load_json(SOL_USD, {}).get("usd")
    if not sol_usd or not liq:
        return None
    return round(P.SIZE_SOL * min(1.0, 4 * P.SIZE_SOL * sol_usd / liq), 4)


def book(closes=None):
    """Each close of the leg beside what a real fill would have left of it: net, haircut at its entry liquidity, net after."""
    liq = {(e["id"], x["mint"]): (x.get("snap") or {}).get("liq") for e in C.read_jsonl(EVENTS) for x in e.get("screen", [])}
    out = []
    for r in closes if closes is not None else [r for r in C.read_jsonl(PAPER) if r.get("kind") == "close"]:
        h = haircut(liq.get((r["event_id"], r["mint"])))
        out.append({**r, "liq": liq.get((r["event_id"], r["mint"])), "haircut": h, "net_haircut": None if h is None else round(r["net_sol"] - h, 4)})
    return out


# ---------------------------------------------------------------- excursion on the paper trades

def _shadow_path(key):
    s = C.load_json(SHADOW_STATE, {}).get(key)
    return s["path"] if s else next((r["path"] for r in C.read_jsonl(PATHS) if r["key"] == key), [])


def _excursion(s, now):
    """Best and worst mark while the paper trade was held and the peak in the 24 h after it closed, from the shadow's
    5-minute path of the same touch plus the marks taken after the close. The live book marks every few seconds; this sees
    every fifth minute, so a best or worst between marks is missed and a short hold may have no mark at all."""
    path, entry = _shadow_path(s["key"]), s["entry"]
    held = [p for dt, p, _ in path if dt <= s["held_s"]]
    after = [p for dt, p, _ in path if s["held_s"] < dt <= s["held_s"] + P.TIME_STOP_S] + [p for _, p in s["after"]]
    pct = lambda xs, f: round(f(xs) / entry - 1, 4) if xs else None  # noqa: E731
    best, post = pct(held, max), pct(after, max)
    top = max(x for x in (best, post, 0.0) if x is not None)
    return {"key": s["key"], "mint": s["mint"], "symbol": s["symbol"], "entry": entry, "held_s": s["held_s"], "net_sol": s["net_sol"],
            "exits": s["exits"], "exit_pct": s["exit_pct"], "best_pct": best, "worst_pct": pct(held, min), "marks_held": len(held),
            "after_exit_peak_pct": post, "marks_after": len(after), "kept_of_peak": round(s["exit_pct"] / top, 3) if top > 0 else None,
            "open": now - s["t_exit"] < P.TIME_STOP_S}


def excursion_tick(now=None, quotes=None):
    """Follow every closed paper trade for 24 h after its exit, then write its excursion row. Also keeps the SOL quote the haircut uses."""
    now = now or C.now()
    st, done = C.load_json(EXC_STATE, {}), {r["key"] for r in C.read_jsonl(EXC)}
    for r in all_paper():
        key = r["event_id"] + "|" + r["mint"] if r.get("kind") == "close" else None
        if key and key not in st and key not in done:
            t_exit = _epoch(r["ts"])
            st[key] = {"key": key, "mint": r["mint"], "symbol": r["symbol"], "entry": r["entry"], "t_exit": t_exit, "held_s": r["held_s"],
                       "net_sol": r["net_sol"], "exits": [e["why"] for e in r["exits"]],
                       "exit_pct": round(sum(e["frac"] * e["pct"] for e in r["exits"]), 4), "after": []}
    if quotes is None:
        quotes = _quotes([s["mint"] for s in st.values()] + [WSOL])
        if quotes.get(WSOL, (0, 0))[0] > 0:
            C.save_json(SOL_USD, {"usd": quotes[WSOL][0], "ts": C.iso(now)})
    for key, s in list(st.items()):
        price, dt = quotes.get(s["mint"], (0, 0))[0], now - s["t_exit"]
        if price > 0 and 0 <= dt <= P.TIME_STOP_S:
            s["after"].append([round(dt), price])
        if dt >= P.TIME_STOP_S:
            C.append(EXC, _excursion(s, now))
            del st[key]
    C.save_json(EXC_STATE, st)
    return len(st)


def excursions(now=None):
    """Finished excursion rows, then the ones still inside their 24 h after exit (open: True, figures so far)."""
    now = now or C.now()
    return C.read_jsonl(EXC) + [_excursion(s, now) for s in C.load_json(EXC_STATE, {}).values()]


# ---------------------------------------------------------------- rivals for the per-touch P(win)

def rivals(rows):
    """Brier of the per-touch P(win) on closed first-touch shadows, in close order, against two rivals given the same rows:
    the frozen seed prior, and the running base rate of every screened touch so far (pass and fail pooled, add-one start)."""
    rows = [r for r in rows if independent(r)]
    if not rows:
        return None
    seeds = {b["id"]: b["p"] for b in reversed(C.read_jsonl(BELIEFS))}   # reversed: the first version of each id wins
    se, k = {"per-touch": 0.0, "seed prior": 0.0, "base rate": 0.0}, 0
    for n, r in enumerate(rows):
        se["per-touch"] += r["brier"]
        se["seed prior"] += (seeds[AUTO_BELIEF[r["pass"]]] - r["win"]) ** 2
        se["base rate"] += ((k + 1) / (n + 2) - r["win"]) ** 2
        k += r["win"]
    out = {name: v / len(rows) for name, v in se.items()}
    low = min(out.values())
    return {"n": len(rows), "brier": out, "ahead": [name for name, v in out.items() if v <= low + 1e-12]}



# ---------------------------------------------------------------- forecasts

def predict(claim, metric, direction, threshold, confidence, deadline, basis, who="claude", beliefs=(), when="deadline", tags=(),
            rests_on=None, like=None, today=None):
    """when: 'deadline' reads the metric after the deadline day; 'early' confirms the moment the claim holds;
    'defined' resolves the moment the metric exists (the *_at_40 family). metric 'manual' waits for `resolve`.
    A market metric (mk_<name>@<day>[..<day>]) is read only after its window. rests_on names the market forecast a leg
    forecast stands on, so its miss can be read as market or rule; like is the forecast whose question this answers again.
    Refused: a second answer by the same forecaster to the same question; an answer to someone's question once it has
    resolved, passed its deadline or, for a market metric, once its window has opened (the answer is then partly known)."""
    assert 0 < confidence < 1 and when in ("deadline", "early", "defined") and direction in OPS, "bad forecast"
    mk = MK_RE.match(metric)
    assert metric == "manual" or mk or metric in metrics(), f"unknown metric {metric}"
    if mk:
        last = datetime.date.fromisoformat(mk.group(3) or mk.group(2)) + datetime.timedelta(days=mk.group(1) in MK_LATE)
        assert when == "deadline" and deadline >= str(last), f"a market forecast is read after its window: deadline {last} or later, when=deadline"
    assert rests_on is None or any(p["pred_id"] == rests_on and MK_RE.match(p["metric"]) for p in C.read_jsonl(PREDS)), "rests_on must name a market forecast"
    assert all(b in {r["id"] for r in C.read_jsonl(BELIEFS)} for b in beliefs), "unknown belief id"
    time.strptime(deadline, "%Y-%m-%d")
    preds, today = C.read_jsonl(PREDS), today or C.iso()[:10]
    q = {"claim": claim, "metric": metric, "direction": direction, "threshold": threshold, "deadline": deadline}
    assert not any(p["who"] == who and _q(p) == _q(q) for p in preds), f"{who} has already answered this question"
    if like:
        assert any(p["pred_id"] == like for p in preds), f"no forecast {like}"
        assert like not in {s["pred_id"] for s in C.read_jsonl(SCORES)} and today <= deadline, "that question has resolved or passed its deadline"
        assert not mk or today < mk.group(2), f"the window opened {mk.group(2) if mk else ''}: an answer now has seen part of the outcome"
    ts = C.iso()
    return chain_append(PREDS, {"pred_id": hashlib.sha256(f"{claim}{who}{ts}".encode()).hexdigest()[:12], "ts": ts, "leg": leg(), "who": who,
                                "claim": claim, "basis": basis, "beliefs": list(beliefs), "metric": metric, "direction": direction,
                                "threshold": threshold, "confidence": confidence, "deadline": deadline, "when": when,
                                "tags": list(tags), "rests_on": rests_on, "like": like, "git": _git()})


def _score(p, outcome, value, by, note=""):
    hit = p["confidence"] if outcome else 1 - p["confidence"]
    return chain_append(SCORES, {"pred_id": p["pred_id"], "leg": p["leg"], "who": p["who"], "claim": p["claim"], "beliefs": p["beliefs"],
                                 "confidence": p["confidence"], "outcome": outcome, "value": value,
                                 "brier": None if outcome is None else round((p["confidence"] - outcome) ** 2, 4),
                                 "surprise_bits": None if outcome is None else round(-math.log2(hit), 3),
                                 "resolved_by": by, "note": note})


def open_preds():
    scored = {r["pred_id"] for r in C.read_jsonl(SCORES)}
    return [p for p in C.read_jsonl(PREDS) if p["pred_id"] not in scored]


def resolve_due(m=None, today=None, now=None):
    """Score every open forecast whose metric can now speak. A metric still undefined after the deadline voids the
    forecast (outcome null): the question was unanswerable as posed, which is itself owed a lesson. A forecast written
    for a contract that has since been superseded is voided too: its leg ended before the metric could speak.
    A due market forecast whose window still has open shadows (a quote outage kept them from closing) waits for the
    next tick and voids only after MK_TRIES tries."""
    m, today, out = m or metrics(), today or C.iso()[:10], []
    wait, still = C.load_json(MK_WAIT, {}), {}
    for p in open_preds():
        if p["metric"] == "manual":
            continue
        if p["leg"] != leg():
            out.append(_score(p, None, None, "superseded", f"leg ended, superseded by {leg()}"))
            continue
        x, late = value(p["metric"], m, now), today > p["deadline"]
        holds = None if x is None else int(OPS[p["direction"]](x, p["threshold"]))
        if (p["when"] == "early" and holds) or (p["when"] == "defined" and holds is not None) or (late and holds is not None):
            out.append(_score(p, holds, x, "metric"))
        elif late:
            mk = MK_RE.match(p["metric"])
            tries = wait.get(p["pred_id"], 0) + 1
            if mk and market(mk.group(2), mk.group(3), now)["pending"] and tries < MK_TRIES:
                still[p["pred_id"]] = tries
            else:
                out.append(_score(p, None, None, "metric", f"window still open after {tries} tries" if tries > 1 else "metric undefined at deadline"))
    if still or wait:
        C.save_json(MK_WAIT, still)
    return out


def resolve_manual(pred_id, outcome, note):
    p = next(p for p in open_preds() if p["pred_id"] == pred_id)
    assert p["metric"] == "manual", "this forecast resolves from its metric, not by hand"
    return _score(p, outcome, None, "manual", note)


def current_beliefs():
    cur = {}
    for b in C.read_jsonl(BELIEFS):
        cur[b["id"]] = {**b, "seed_p": cur.get(b["id"], b).get("seed_p", b["p"]), "versions": cur.get(b["id"], {}).get("versions", 0) + 1}
    return cur


def belief(bid, claim, p, why, falsifier, n0=10, k=None, n=None, cause="seed"):
    """k/n name the metrics that count this belief's successes and trials, when the shadow book can test it directly."""
    assert 0 < p < 1
    return chain_append(BELIEFS, {"id": bid, "claim": claim, "p": p, "n0": n0, "why": why, "falsifier": falsifier, "k": k, "n": n,
                                  "cause": cause, "leg": leg()})


def lesson(what, why, cause, pred_id=None, belief_id=None, p=None, rule=None, side=None):
    """cause: model (the belief was wrong), variance (the belief was fine, the draw was not), measurement (the instrument
    lied), question (the forecast was badly posed), execution (a bug or an outage). Only `model` should move a belief.
    side: where the miss belongs, market, screen or exits. Left out, a lesson on a forecast takes what `blame` reads."""
    assert cause in CAUSES, f"cause must be one of {CAUSES}"
    assert side is None or side in SIDES, f"side must be one of {SIDES}"
    if side is None and pred_id:
        s = next((s for s in C.read_jsonl(SCORES) if s["pred_id"] == pred_id), None)
        side = blame(s)[0] if s else None
        side = side if side in SIDES else None
    cur = current_beliefs()
    rec = {"lesson_id": hashlib.sha256(f"{what}{C.iso()}".encode()).hexdigest()[:12], "leg": leg(), "pred_id": pred_id, "what": what,
           "why": why, "cause": cause, "side": side, "belief": belief_id, "p_from": cur[belief_id]["p"] if belief_id else None, "p_to": p, "rule": rule}
    out = chain_append(LESSONS, rec)
    if belief_id and p is not None:
        b = cur[belief_id]
        belief(belief_id, b["claim"], p, why, b["falsifier"], b["n0"], b["k"], b["n"], cause=out["lesson_id"])
    return out


def owed():
    """Resolved forecasts that surprised us (or voided) and have no lesson yet. A leg ending is one lesson, not one per forecast."""
    have = {l["pred_id"] for l in C.read_jsonl(LESSONS)}
    return [s for s in C.read_jsonl(SCORES) if s["pred_id"] not in have and s["resolved_by"] != "superseded"
            and (s["outcome"] is None or s["surprise_bits"] >= OWED_BITS)]


def _tail(k, n, p):
    """Two-sided exact binomial: how often a belief of p would produce a count as unlikely as k of n."""
    pmf = [math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    return sum(x for x in pmf if x <= pmf[k] * (1 + 1e-9))


def belief_checks(m=None):
    """Each data-bound belief against the shadow book. strained = the data would be a < 5 % event if the belief were true."""
    m, out = m or metrics(), []
    for b in current_beliefs().values():
        k, n = (m.get(b["k"]), m.get(b["n"])) if b["k"] else (None, None)
        out.append({**b, "k_now": k, "n_now": n, "tail": _tail(k, n, b["p"]) if n else None,
                    "posterior": (b["seed_p"] * b["n0"] + k) / (b["n0"] + n) if n else None})
        out[-1]["strained"] = bool(n) and out[-1]["tail"] < 0.05
    return out


# ---------------------------------------------------------------- review

def _brier(rows):
    rows = [r for r in rows if r.get("brier") is not None]
    return (sum(r["brier"] for r in rows) / len(rows), len(rows)) if rows else (None, 0)


def _fmt(x, spec="{:.3f}"):
    return "-" if x is None else spec.format(x)


def headline():
    b, n = _brier(C.read_jsonl(SCORES))
    done = [r for r in C.read_jsonl(SHADOW) if independent(r)]
    m = metrics()
    cut = f"paper {m['cum_net']:+.3f} SOL, {_fmt(m['cum_net_haircut'], '{:+.3f}')} after the fill haircut; " if m["closed"] else ""
    return (f"Foresight Journal: {cut}{len(open_preds())} forecasts open, {n} scored" + (f" (Brier {b:.3f} vs 0.250 coin)" if n else "") +
            f"; lessons owed {len(owed())}; beliefs strained {sum(1 for c in belief_checks() if c['strained'])}; "
            f"shadows {len(C.load_json(SHADOW_STATE, {}))} open, {len(done)} closed clean -> out/journal.md")


def review():
    m, scores, preds, lessons = metrics(), C.read_jsonl(SCORES), {p["pred_id"]: p for p in C.read_jsonl(PREDS)}, C.read_jsonl(LESSONS)
    L = [f"# The Foresight Journal  rich  {C.iso()}  leg {leg()}", ""]
    bad = verify()
    L += [f"**CHAIN BROKEN: {'; '.join(bad)}**" if bad else "chain intact: no forecast, score, lesson or belief has been edited", ""]

    L += ["## 1. Lessons owed (write these before anything else)", ""]
    for s in owed():
        L.append(f"- `{s['pred_id']}` [{s['who']}] said {s['confidence']:.0%}: {s['claim']} -> "
                 + ("VOID (metric never defined)" if s["outcome"] is None else f"{'YES' if s['outcome'] else 'NO'} (value {s['value']}), {s['surprise_bits']:.1f} bits of surprise")
                 + " | reads as {}: {}".format(*blame(s, list(preds.values()), scores)))
    L += ["- none"] if not owed() else []

    L += ["", "## 2. The model against the data", "", "| id | belief | seed p | now p | data k/n | posterior | verdict |", "|---|---|---|---|---|---|---|"]
    for c in belief_checks(m):
        data = f"{c['k_now']}/{c['n_now']}" if c["n_now"] else "-"
        verdict = "STRAINED: revise or defend" if c["strained"] else ("consistent" if c["n_now"] else "no direct data")
        L.append(f"| {c['id']} | {c['claim']} | {c['seed_p']:.2f} | {c['p']:.2f} | {data} | {_fmt(c['posterior'], '{:.2f}')} | {verdict} |")

    L += ["", "## 3. Scoreboard (Brier: 0 is perfect, 0.25 is a coin, above 0.25 is worse than not thinking)", ""]
    for label, rows in [("all", scores)] + [(f"who={w}", [s for s in scores if s["who"] == w]) for w in sorted({s["who"] for s in scores})] \
            + [(f"leg={g}", [s for s in scores if s["leg"] == g]) for g in sorted({s["leg"] for s in scores})]:
        b, n = _brier(rows)
        L.append(f"- {label}: n={n}, Brier {_fmt(b)}, mean surprise {_fmt(sum(r['surprise_bits'] for r in rows if r['brier'] is not None) / n if n else None, '{:.2f}')} bits")
    L += ["- no forecast has resolved yet"] if not scores else []
    cal = [s for s in scores if s["brier"] is not None]
    if cal:
        L += ["", "| stated | n | came true |", "|---|---|---|"]
        for lo in (0, 0.2, 0.4, 0.6, 0.8):
            rows = [s for s in cal if lo <= s["confidence"] < lo + 0.2]
            if rows:
                L.append(f"| {lo:.0%}-{lo+0.2:.0%} (mean {sum(r['confidence'] for r in rows)/len(rows):.0%}) | {len(rows)} | {sum(r['outcome'] for r in rows)/len(rows):.0%} |")
    auto = [r for r in C.read_jsonl(SHADOW) if independent(r)]
    rv = rivals(auto)
    if rv:
        L += ["", f"- per-touch P(win) against its rivals on {rv['n']} closed first touches (Brier): "
                  + ", ".join(f"{name} {b:.3f}" for name, b in rv["brier"].items()) + f". Ahead: {' and '.join(rv['ahead'])}."]

    L += ["", "## 4. Open forecasts and where reality stands today", "", "| id | who | says | claim | metric now | needs | deadline |", "|---|---|---|---|---|---|---|"]
    for p in open_preds():
        now = "by hand" if p["metric"] == "manual" else _fmt(value(p["metric"], m), "{:.4g}")
        L.append(f"| `{p['pred_id']}` | {p['who']} | {p['confidence']:.0%} | {p['claim']} | {now} | {p['direction']} {p['threshold']} | {p['deadline']} ({p['when']}) |")

    L += ["", "## 5. What the screen turned away (shadow book: first touches, watched from the start, contract exits)", "",
          "| group | n | win rate | mean net SOL | peak >= +100% | median peak | median trough |", "|---|---|---|---|---|---|---|"]
    groups = [("PASS", [r for r in auto if r["pass"]]), ("FAIL (any)", [r for r in auto if not r["pass"]])]
    for reason in sorted({w.split()[0] for r in auto for w in r["why"]}):
        groups.append((f"fail: {reason}", [r for r in auto if any(w.split()[0] == reason for w in r["why"])]))
    for label, rows in groups:
        if rows:
            L.append(f"| {label} | {len(rows)} | {sum(r['win'] for r in rows)/len(rows):.0%} | {sum(r['net_sol'] for r in rows)/len(rows):+.3f} | "
                     f"{sum(1 for r in rows if r['peak_pct'] >= 1)/len(rows):.0%} | {_p50([r['peak_pct'] for r in rows]):+.0%} | {_p50([r['trough_pct'] for r in rows]):+.0%} |")
    L.append(f"\nstop regret (stopped passes that later traded above entry inside 24 h): {_fmt(m['sh_stop_regret'], '{:.0%}')} of {m['sh_n_stops']} stops"
             f" (reported from {MIN_SIDE})")

    L += ["", "## 6. Lessons and the rules they left for the next leg", ""]
    for l in lessons:
        move = f" {l['belief']} {l['p_from']:.2f} -> {l['p_to']:.2f}." if l["belief"] and l["p_to"] is not None else ""
        L.append(f"- {l['ts'][:10]} [{l['leg']}, {l['cause']}] {l['what']} WHY: {l['why']}{move}" + (f" RULE: {l['rule']}" if l["rule"] else ""))
        if l["pred_id"] in preds:
            L.append(f"  - forecast `{l['pred_id']}`: {preds[l['pred_id']]['claim']}")
    L += ["- none yet"] if not lessons else []
    L += _more(m)
    text = "\n".join(L) + "\n"
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def _more(m):
    """Sections 7 to 9 of the review: the market, the day's winners and losers, the paper trades as a real fill would see them."""
    today = datetime.date.fromisoformat(C.iso()[:10])
    L = ["", "## 7. Market state (what the feeds brought, whatever the contract did with it)", "",
         "| UTC day | touches | named a coin | showed intent | screen pass rate | screened coins, median 24 h | share up |", "|---|---|---|---|---|---|---|"]
    for i in range(6, -1, -1):
        d = str(today - datetime.timedelta(days=i))
        k = market(d)
        if k["mk_touches"]:
            L.append(f"| {d} | {k['mk_touches']:.0f} | {k['mk_resolved']:.0f} | {k['mk_intent']:.0f} | {_fmt(k['mk_pass_rate'], '{:.0%}')} of {k['screened']} | "
                     + ("pending" if k["pending"] else f"{_fmt(k['mk_ret24'], '{:+.1%}')} (n={k['shadows']})") + f" | {_fmt(k['mk_up'], '{:.0%}')} |")
    L += ["", "## 8. The day's winners and losers, and what the exits kept (first touches, 24 h, peak above entry = 100 %)", ""]
    days = shadow_days()[-7:]
    for d in days:
        v = movers(d)
        L.append(f"- {d}: {v['n']} coins screened, {v['n_entered']} entered. Capture: entered {_fmt(v['capture_entered'], '{:+.0%}')}, "
                 f"passed {_fmt(v['capture_pass'], '{:+.0%}')}, all screened {_fmt(v['capture_all'], '{:+.0%}')}")
        for label, rows, key in (("ran", v["ran"], "peak_pct"), ("fell", v["fell"], "trough_pct")):
            L.append(f"  - {label} most: " + "; ".join(
                f"{r['symbol']} {r[key]:+.0%} ({'ENTERED' if r['entered'] else 'passed, not entered' if r['pass'] else 'rejected'}, "
                f"booked {r['net_sol']:+.3f}, kept {_fmt(r['kept'], '{:+.0%}')})" for r in rows))
    L += ["- no shadow has closed clean yet"] if not days else []
    sol = C.load_json(SOL_USD, {})
    floor = haircut(C.LIQ_FLOOR)
    L += ["", "## 9. The paper trades as a real fill would see them", "",
          f"haircut: a {P.SIZE_SOL:g} SOL round trip against the mark costs about 4 x size / pool liquidity before fees"
          + (f" (SOL at ${sol['usd']:,.0f}: {floor / P.SIZE_SOL:.1%} at the ${C.LIQ_FLOOR:,} liquidity floor)" if floor is not None else " (no SOL quote yet)")
          + f". Leg: cum {m['cum_net']:+.3f} SOL, {_fmt(m['cum_net_haircut'], '{:+.3f}')} after haircut; mean {_fmt(m['mean_net'], '{:+.3f}')}, "
          f"{_fmt(m['mean_net_haircut'], '{:+.3f}')} after haircut.", "",
          "| trade | exits | net SOL | after haircut | best while held | worst while held | peak in 24 h after exit | kept of peak |", "|---|---|---|---|---|---|---|---|"]
    cut = {r["event_id"] + "|" + r["mint"]: r for r in book([r for r in all_paper() if r.get("kind") == "close"])}
    for x in excursions():
        b = cut.get(x["key"], {})
        L.append(f"| {x['symbol']}{' (still inside its 24 h)' if x['open'] else ''} | {', '.join(x['exits'])} | {x['net_sol']:+.3f} | {_fmt(b.get('net_haircut'), '{:+.3f}')} | "
                 f"{_fmt(x['best_pct'], '{:+.1%}')} | {_fmt(x['worst_pct'], '{:+.1%}')} | {_fmt(x['after_exit_peak_pct'], '{:+.1%}')} | {_fmt(x['kept_of_peak'], '{:+.0%}')} |")
    L += ["", "best and worst come from 5-minute marks (the live book marks every few seconds), so '-' means no mark fell inside the hold."]
    return L


def _q(p):
    return json.dumps([p["claim"], p["metric"], p["direction"], p["threshold"], p["deadline"]], sort_keys=True)


def blind(who="irvin"):
    """Open questions `who` has not answered, with nobody's odds or reasoning, and the command that answers each."""
    preds = C.read_jsonl(PREDS)
    mine, seen, L = {_q(p) for p in preds if p["who"] == who}, set(), [f"# Open questions for {who}: answer before reading anyone's odds", ""]
    for p in sorted(open_preds(), key=lambda p: p["deadline"]):
        if p["who"] != who and _q(p) not in mine and _q(p) not in seen:
            seen.add(_q(p))
            L += [f"- by {p['deadline']}: {p['claim']}", f"  `python ops/journal.py predict --like {p['pred_id']} --who {who} --confidence <your odds, 0 to 1>`"]
    L += ["- nothing open is unanswered"] if not seen else []
    text = "\n".join(L) + "\n"
    with open(BLIND, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def tick():
    try:
        shadow_tick()
        excursion_tick()
    except Exception as e:   # a DexScreener outage must not stop forecasts resolving
        C.append(ERRORS, {"where": "shadow", "err": str(e)[:200]})
    try:
        resolve_due()
        review()
    except Exception as e:
        C.append(ERRORS, {"where": "resolve", "err": str(e)[:200]})


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("tick", "review", "metrics", "verify"):
        sub.add_parser(name)
    sub.add_parser("blind").add_argument("--who", default="irvin")
    sub.add_parser("market").add_argument("--days", type=int, default=7)
    a = sub.add_parser("predict")
    a.add_argument("--like", help="pred_id whose question to answer again as another forecaster")
    for flag in ("claim", "metric", "direction", "deadline", "basis"):
        a.add_argument("--" + flag)
    a.add_argument("--threshold", help="a number, or lo,hi with --direction in")
    a.add_argument("--confidence", type=float, required=True)
    a.add_argument("--who", default="claude")
    a.add_argument("--when", default="deadline")
    a.add_argument("--beliefs", default="")
    a.add_argument("--tags", default="")
    a.add_argument("--rests-on", help="pred_id of the market forecast this rests on, or 'none' with the reason in --basis")
    a = sub.add_parser("resolve")
    a.add_argument("pred_id")
    a.add_argument("outcome", choices=("yes", "no"))
    a.add_argument("--note", required=True)
    a = sub.add_parser("lesson")
    for flag, req in (("what", True), ("why", True), ("cause", True), ("pred", False), ("belief", False), ("rule", False), ("side", False)):
        a.add_argument("--" + flag, required=req)
    a.add_argument("--p", type=float)
    a = sub.add_parser("belief")
    for flag in ("id", "claim", "why", "falsifier"):
        a.add_argument("--" + flag, required=True)
    a.add_argument("--p", type=float, required=True)
    a.add_argument("--n0", type=float, default=10)
    a.add_argument("--k")
    a.add_argument("--n")
    args = ap.parse_args()
    if args.cmd == "tick":
        tick()
    elif args.cmd == "review":
        print(review())
    elif args.cmd == "metrics":
        print(json.dumps(metrics(), indent=1))
    elif args.cmd == "verify":
        bad = verify()
        print("\n".join(bad) or "chain intact")
        sys.exit(1 if bad else 0)
    elif args.cmd == "blind":
        print(blind(args.who))
    elif args.cmd == "market":
        today = datetime.date.fromisoformat(C.iso()[:10])
        print(json.dumps({str(today - datetime.timedelta(days=i)): market(str(today - datetime.timedelta(days=i))) for i in range(args.days - 1, -1, -1)}, indent=1))
    elif args.cmd == "predict":
        src = next(p for p in C.read_jsonl(PREDS) if p["pred_id"] == args.like) if args.like else {}
        if not src and not MK_RE.match(args.metric or "") and not args.rests_on:
            ap.error("name the market forecast this rests on: --rests-on <pred_id> (write the market forecast first), or --rests-on none with the reason in --basis")
        rests_on = src.get("rests_on") if src else None if args.rests_on in (None, "none") else args.rests_on
        thr = src.get("threshold") if args.threshold is None else [float(x) for x in args.threshold.split(",")] if "," in args.threshold else float(args.threshold)
        r = predict(args.claim or src["claim"], args.metric or src["metric"], args.direction or src["direction"], thr, args.confidence,
                    args.deadline or src["deadline"], args.basis or f"second forecast on {args.like}", args.who,
                    [b for b in args.beliefs.split(",") if b] or src.get("beliefs", []), src.get("when", args.when),
                    [t for t in args.tags.split(",") if t] or src.get("tags", []), rests_on, args.like)
        print(r["pred_id"], r["claim"])
    elif args.cmd == "resolve":
        print(resolve_manual(args.pred_id, int(args.outcome == "yes"), args.note))
    elif args.cmd == "lesson":
        print(lesson(args.what, args.why, args.cause, args.pred, args.belief, args.p, args.rule, args.side)["lesson_id"])
    elif args.cmd == "belief":
        print(belief(args.id, args.claim, args.p, args.why, args.falsifier, args.n0, args.k, args.n)["h"])


if __name__ == "__main__":
    main()
