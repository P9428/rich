"""RI-05, the 5 % loop on Solana (paper only; a shadow book beside RI-04, never counted in RI-04's leg).

The 5 % (docs/INSENTOS-DUVAL.md Part 2, applied under the three interviews in docs/FIVE-PERCENT-RSI.md) as rules the tape can
score. Every function here runs identically on a live launch (src/duval.py feeds it marks) and on a recorded path
(journal/paths/<day>.jsonl, replayed by ops/five_replay.py), with the same curve arithmetic and fees RI-04 pays.

P1  arrivals, not price: the curve's real SOL is the net flow of attention; flow = ΔrSOL/Δt over FLOW_W seconds, accel = Δflow;
    the S-curve phase of a launch is read from (flow, accel): slow → exp → linear → log → flat
L1  the meta gate: the trailing-hour share of plain pump launches that touched +20 % ("runners"); under GATE_DEAD the hour is dead
    and the loop does not enter; a 15-minute collapse under GATE_RESIST closes everything (trigger c)
L2  classify before the chart: narrative (named from the hour's news) is the only tradable class; dev (the creator bought DEV_SOL+
    at create), tech (TECH words), celebrity (claims to be official) are never traded
L3  comparable and catalyst: the comparable is a prior launch of the last 24 h carrying the same term, its ceiling the best peak
    multiple among them; the catalyst clock is the term's age in the hour's news (fresh under CATALYST_FRESH_S); a blank comparable
    is a scalp (SCALP_SOL under RI-04's own exits), a comparable that never ran is zero
L4  the free trade: at +LEG1 sell exactly enough tokens to take the stake back; the remainder rides at zero cost
L5  three triggers decided at entry: (a) the catalyst lands (the term leaves the hour's news), (b) arrivals slow (flow ≤ 0 for
    SLOW_S after entry), (c) resistance in the meta; plus the physics floor (STOP) before the stake is out and the environment's
    window (HOLD_S, the path length) after it
N1-N4  no hold past a trigger, no dev/tech/celebrity, vamps only as scalps beside a held narrative, size halves after a RESET_DD
    drawdown and never adds back inside the contract
"""
import bisect
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C   # noqa: E402
import duval as D    # noqa: E402

LEG = "RI-05"
PAPER = C.path("journal", "paper.RI-05.jsonl")
STATE = C.path("state", "five.json")

# ---- constants, each measured on the tape of 2026-10-23..27 (28,189 plain pump launches) before being frozen; see docs/RI-05.md
FLOW_W = 10.0            # s; the arrivals window (runners reach their peak in a median 8 s, so 10 s resolves the leg)
ACCEL_EPS = 0.02         # SOL/s; |accel| under this is "linear"
RUNNER_MULT = 1.2        # a launch "ran" if its price touched this multiple of the create price inside the path
GATE_W = 3600            # s; the meta gate reads the runner share of the trailing hour
GATE_MIN_N = 30          # launches; fewer and the gate is unknown (unknown is closed: success is not known to be in the set)
GATE_DEAD = 0.30         # hourly runner share under this is a dead hour (q20 of the 70 measured hours; median 0.39)
RESIST_W = 900           # s; trigger (c) reads the last 15 minutes
RESIST_MIN_N = 15
GATE_RESIST = 0.20       # a 15-minute runner share under this closes every position and blocks entries for RESIST_BLOCK_S
RESIST_BLOCK_S = 900
DEV_SOL = 2.0            # creator's buy at create at or above this is the dev class (6.7 % of supply in one hand)
CATALYST_FRESH_S = 1800  # a term older than this in the hour's news is not a fresh catalyst
TERM_GAP_S = 600         # a term absent this long and back again starts a new run (a new catalyst)
COMP_W = 86400           # s; comparables are prior launches of the last day carrying the same term
SIZE_SOL = 1.5           # the full stake (RI-04's)
SCALP_SOL = 0.5          # the stake when the comparable is blank, or for a vamp beside a held narrative
LEG1 = 0.20              # the first leg: stake out
STOP = -0.05             # the physics floor before the stake is out (RI-04 Amendment 4)
SLOW_S = 10.0            # trigger (b): flow ≤ 0 for this long after entry
HOLD_S = 180             # the environment's window: paths are 180 s long, so the loop's hold is bounded by what can be replayed
SCALP_TAKE, SCALP_STOP, SCALP_HOLD = 0.20, -0.05, 60     # RI-04's own exits for scalps
MAX_OPEN = 3
RESET_DD = 6.0           # SOL; realised drawdown at or past this halves the stake for the rest of the contract (N4)

TECH = set("""ai agi agent agents protocol chain chains swap dex bot bots gpt layer l1 l2 l3 dao defi launchpad tool tools app apps api dapp
node nodes network infra infrastructure quantum blockchain terminal sdk model models llm neural compute oracle bridge wallet staking yield
vault finance labs lab tech io ios android cloud data crypto coin token tokens exchange perp perps trading trade bank pay payments mining
miner gpu gpus server servers os software hardware chip chips robot robots robotics drone drones""".split())
OFFICIAL = re.compile(r"\b(official|verified|real)\b", re.I)
WORD_RE = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------- P1 the physics: arrivals

def flow_at(marks, i, w=FLOW_W):
    """Net SOL arrival rate (SOL/s) over the trailing w seconds ending at mark i, and the rate over the window before that."""
    t, r = marks[i][0], marks[i][3]
    j = i
    while j > 0 and t - marks[j - 1][0] < w:
        j -= 1
    dt = t - marks[j][0]
    f1 = (r - marks[j][3]) / dt if dt > 0 else 0.0
    k = j
    while k > 0 and marks[j][0] - marks[k - 1][0] < w:
        k -= 1
    dt2 = marks[j][0] - marks[k][0]
    f0 = (marks[j][3] - marks[k][3]) / dt2 if dt2 > 0 else 0.0
    return f1, f0


def phase(marks, i):
    """Where on the S-curve the launch is at mark i: slow, exp, linear, log or flat."""
    f1, f0 = flow_at(marks, i)
    a = f1 - f0
    if f1 <= 0:
        return "flat" if marks[i][3] > 0.5 else "slow"
    if a > ACCEL_EPS:
        return "exp"
    if a < -ACCEL_EPS:
        return "log"
    return "linear"


def peak_mult(p):
    v0s, v0t = p["v0"]
    p0 = v0s / v0t
    best = 0.0
    for m in p["marks"]:
        if m[2] > 0:
            best = max(best, (m[1] / m[2]) / p0)
    return best


def ran(p):
    return peak_mult(p) >= RUNNER_MULT


def entry_marks(p):
    """The path with the create message's reserves prepended as mark 0: the state RI-04's control (ops/population.py) and the live
    counted book (duval.Book.enter) fill at. RI-05 must fill at the same state or the two books are not comparable: on the tape of
    2026-10-23..27 the same 204 entries made -4.9 SOL filled at the first on-chain mark and +10.2 SOL filled here, and the stop
    level mattered only at the first mark (decisions/2026-10-27-ri05-stop-stage). Whether this fill is attainable is the open
    first-buyer question both books share; the replay shows both fills side by side."""
    marks = p["marks"]
    if not marks:
        return marks
    v0s, v0t = p["v0"]
    return [[0.0, v0s, v0t, marks[0][3]]] + marks


# ---------------------------------------------------------------- L1 the meta gate

class Meta:
    """The runner share of recently finished launches. A launch is known only once its path has closed (t0 + HOLD_S)."""

    def __init__(self):
        self.done = []          # (t_end, ran) sorted by t_end

    def add(self, t_end, did_run):
        bisect.insort(self.done, (t_end, bool(did_run)))

    def share(self, now, w, min_n):
        lo = bisect.bisect_left(self.done, (now - w, False))
        hi = bisect.bisect_right(self.done, (now, True))
        rows = self.done[lo:hi]
        if len(rows) < min_n:
            return None, len(rows)
        return sum(1 for _, r in rows if r) / len(rows), len(rows)

    def state(self, now):
        """'live', 'dead', 'resist' or 'unknown', with the two shares."""
        h, nh = self.share(now, GATE_W, GATE_MIN_N)
        q, nq = self.share(now, RESIST_W, RESIST_MIN_N)
        if q is not None and q < GATE_RESIST:
            return "resist", h, q
        if h is None:
            return "unknown", h, q
        return ("dead" if h < GATE_DEAD else "live"), h, q


# ---------------------------------------------------------------- L2 classify

def classify(name, symbol, init_sol, matched):
    words = set(WORD_RE.findall((name or "").lower())) | set(WORD_RE.findall((symbol or "").lower()))
    if OFFICIAL.search(name or "") or OFFICIAL.search(symbol or ""):
        return "celebrity"
    if words & TECH:
        return "tech"
    if (init_sol or 0) >= DEV_SOL:
        return "dev"
    if matched:
        return "narrative"
    return "none"


# ---------------------------------------------------------------- L3 the catalyst clock and the comparable

class Terms:
    """The hour's terms minute by minute (journal/news/<day>.jsonl). A term's run starts when it appears after TERM_GAP_S of absence."""

    def __init__(self):
        self.run_start = {}     # term -> t the current run began
        self.last_seen = {}     # term -> t last seen
        self.t = None

    def update(self, terms, t):
        self.t = t
        for term in terms:
            last = self.last_seen.get(term)
            if last is None or t - last > TERM_GAP_S:
                self.run_start[term] = t
            self.last_seen[term] = t

    def age(self, term, t):
        if term not in self.run_start or t - self.last_seen.get(term, -1e18) > TERM_GAP_S:
            return None
        return t - self.run_start[term]

    def alive(self, term, t):
        """The catalyst is still in the hour's news (seen inside the last TERM_GAP_S)."""
        return term in self.last_seen and t - self.last_seen[term] <= TERM_GAP_S


class Comparables:
    """Finished launches of the last COMP_W seconds by term: the derivative's ceiling is the best peak among them."""

    def __init__(self):
        self.by_term = {}       # term -> list of (t0, peak_mult)

    def add(self, t0, terms, pk):
        for term in terms:
            self.by_term.setdefault(term, []).append((t0, pk))

    def ceiling(self, terms, now):
        best, n = None, 0
        for term in terms:
            for t0, pk in self.by_term.get(term, []):
                if now - COMP_W <= t0 < now:
                    n += 1
                    best = pk if best is None else max(best, pk)
        return best, n


# ---------------------------------------------------------------- L4/L5 one position through the loop

def sell_for(v_sol, v_tok, c, tokens, want):
    """Tokens to sell into the book-adjusted curve (chain state plus the book's own net SOL c) to receive `want` SOL after fees."""
    lo, hi = 0.0, tokens
    k = v_sol * v_tok
    vs = v_sol + c
    for _ in range(50):
        mid = (lo + hi) / 2
        if D.sell(vs, k / vs, mid) < want:
            lo = mid
        else:
            hi = mid
    return hi


def gross_out(v_sol, v_tok, c, x):
    """Gross SOL leaving the curve when x tokens are sold into the book-adjusted state (what the book's own impact becomes)."""
    k = v_sol * v_tok
    vs = v_sol + c
    return vs - k / (v_tok * v_sol / vs + x) if x > 0 else 0.0


def run_position(marks, entry_i, size, kind, terms_alive, meta_state, t0):
    """Replay one launch from mark entry_i under the loop. `terms_alive(t)` says whether the catalyst is still in the news at
    absolute time t, `meta_state(t)` returns the gate state. Returns the trade dict with every exit and its trigger."""
    e = marks[entry_i]
    tokens = D.buy(e[1], e[2], size)
    if tokens <= 0:
        return None
    c = D.net_in(size)                       # the book's own SOL on the curve
    rem, got, stake_out = tokens, 0.0, False
    t_in = e[0]
    exits, peak, trough = [], 0.0, 0.0
    slow_since = None
    last_i = entry_i
    for i in range(entry_i + 1, len(marks)):
        m = marks[i]
        if m[2] <= 0:
            continue
        last_i = i
        k = m[1] * m[2]
        vs = m[1] + c
        val = D.sell(vs, k / vs, rem) + got
        pct = val / size - 1
        peak, trough = max(peak, pct), min(trough, pct)
        held = m[0] - t_in
        t_abs = t0 + m[0]
        f1, _ = flow_at(marks, i)
        if f1 <= 0 and held >= 2:
            slow_since = slow_since if slow_since is not None else m[0]
        else:
            slow_since = None
        why = None
        if kind == "scalp":
            why = "take" if pct >= SCALP_TAKE else "stop" if pct <= SCALP_STOP else "time" if held >= SCALP_HOLD else None
        else:
            if not stake_out and pct >= LEG1:
                x = sell_for(m[1], m[2], c, rem, size)
                g = gross_out(m[1], m[2], c, x)
                got += D.sell(vs, k / vs, x)
                c -= g
                rem -= x
                stake_out = True
                exits.append({"t": round(m[0], 1), "frac": round(x / tokens, 3), "pct": round(pct, 4), "why": "leg1"})
                continue
            if meta_state(t_abs) == "resist":
                why = "resist"
            elif not terms_alive(t_abs):
                why = "catalyst"
            elif slow_since is not None and m[0] - slow_since >= SLOW_S:
                why = "slow"
            elif not stake_out and pct <= STOP:
                why = "stop"
            elif held >= HOLD_S:
                why = "time"
        if why:
            exits.append({"t": round(m[0], 1), "frac": round(rem / tokens, 3), "pct": round(pct, 4), "why": why})
            return {"net": round(val - size, 4), "pct": round(pct, 4), "why": why, "peak": round(peak, 4), "trough": round(trough, 4),
                    "t_in": t_in, "held": round(held, 1), "exits": exits, "kind": kind, "size": size, "stake_out": stake_out,
                    "phase": phase(marks, i)}
    # the path ended first: close at the last mark
    m = marks[last_i]
    if m[2] <= 0:
        return None
    k = m[1] * m[2]
    vs = m[1] + c
    val = D.sell(vs, k / vs, rem) + got
    pct = val / size - 1
    exits.append({"t": round(m[0], 1), "frac": round(rem / tokens, 3), "pct": round(pct, 4), "why": "end"})
    return {"net": round(val - size, 4), "pct": round(pct, 4), "why": "end", "peak": round(max(peak, pct), 4), "trough": round(min(trough, pct), 4),
            "t_in": t_in, "held": round(m[0] - t_in, 1), "exits": exits, "kind": kind, "size": size, "stake_out": stake_out, "phase": phase(marks, last_i)}


# ---------------------------------------------------------------- the decision at a launch

def decide(p, t0, meta, terms, comps, open_terms, stake):
    """The loop's read of one launch at its first mark. Returns (kind, size, read) where kind is 'full', 'scalp' or None."""
    read = {"class": classify(p["name"], p.get("sym") or p.get("symbol"), p.get("init_sol"), p["match"])}
    g, h, q = meta.state(t0)
    read["gate"] = g
    read["runner_share_1h"] = None if h is None else round(h, 3)
    if not p["mint"].endswith("pump") or p.get("pool") not in (None, "pump") or p.get("mayhem"):
        read["skip"] = "not a plain pump launch"
        return None, 0, read
    if p.get("mcap0_usd") is None or p["mcap0_usd"] >= D.MCAP_MAX_USD:
        read["skip"] = "mcap"
        return None, 0, read
    marks = p["marks"]
    if not marks or marks[0][2] <= 0:
        read["skip"] = "no mark"
        return None, 0, read
    v0s, v0t = p["v0"]
    if not (0.5 <= marks[0][1] / max(v0s, 1e-9) <= 2.0) or abs(marks[0][1] * marks[0][2] / (v0s * v0t) - 1) > 0.05:
        read["skip"] = "non-standard curve"
        return None, 0, read
    if g != "live":
        read["skip"] = f"meta {g}"
        return None, 0, read
    if read["class"] != "narrative":
        read["skip"] = f"class {read['class']}"
        return None, 0, read
    ages = [a for a in (terms.age(t, t0) for t in p["match"]) if a is not None]
    read["catalyst_age_s"] = round(min(ages)) if ages else None
    if not ages or min(ages) > CATALYST_FRESH_S:
        read["skip"] = "catalyst stale" if ages else "catalyst unknown"
        return None, 0, read
    vamp = bool(set(p["match"]) & open_terms)
    read["vamp"] = vamp
    ceil, n = comps.ceiling(p["match"], t0)
    read["comparable_n"] = n
    read["comparable_ceiling"] = None if ceil is None else round(ceil, 3)
    if vamp:
        return "scalp", SCALP_SOL, read
    if n == 0:
        return "scalp", SCALP_SOL, read
    if ceil < RUNNER_MULT:
        read["skip"] = "comparable never ran"
        return None, 0, read
    return "full", stake, read


# ---------------------------------------------------------------- the shadow book (live, fed by src/duval.py)

class Shadow:
    """Runs the loop live on the engine's tracked launches. One call per mark pass; writes journal/paper.RI-05.jsonl in the
    engine's own row shapes (entry / exit / close) plus the read. Nothing here touches RI-04's book or count."""

    def __init__(self):
        self.meta, self.terms, self.comps = Meta(), Terms(), Comparables()
        self.open = {}                                   # curve key -> position
        st = C.load_json(STATE, {})
        self.stake = st.get("stake", SIZE_SOL)
        self.peak_cum = st.get("peak_cum", 0.0)
        self.cum = st.get("cum", 0.0)
        self.seen = set(r["mint"] for r in C.read_jsonl(PAPER) if r.get("kind") == "entry")
        self.block_until = 0.0
        self.n_entries = self.n_closes = 0
        self._warm()

    def _warm(self):
        """Yesterday's and today's finished paths give the gate and the comparables something to read at startup."""
        now = time.time()
        for f in sorted(glob.glob(C.path("journal", "paths", "*.jsonl")))[-2:]:
            for line in open(f, encoding="utf-8"):
                try:
                    p = json.loads(line)
                except Exception:
                    continue
                t0 = D.calendar.timegm(time.strptime(p["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
                if now - t0 > COMP_W or not p["mint"].endswith("pump") or not p["marks"] or p["marks"][0][1] <= 0:
                    continue
                pk = peak_mult(p)
                self.meta.add(t0 + HOLD_S, pk >= RUNNER_MULT)
                if p["match"]:
                    self.comps.add(t0, p["match"], pk)
        for f in sorted(glob.glob(C.path("journal", "news", "*.jsonl")))[-1:]:
            for line in open(f, encoding="utf-8"):
                try:
                    r = json.loads(line)
                    self.terms.update(r["terms"], D.calendar.timegm(time.strptime(r["ts"][:19], "%Y-%m-%dT%H:%M:%S")))
                except Exception:
                    continue

    def on_terms(self, terms, t):
        self.terms.update(terms, t)

    def on_path_done(self, tr, t_end):
        p = {"v0": tr["v0"], "marks": tr["marks"]}
        if tr["mint"].endswith("pump") and tr["marks"] and tr["marks"][0][1] > 0:
            pk = peak_mult(p)
            self.meta.add(t_end, pk >= RUNNER_MULT)
            if tr["match"]:
                self.comps.add(tr["t0"], tr["match"], pk)

    def _save(self):
        C.save_json(STATE, {"stake": self.stake, "peak_cum": self.peak_cum, "cum": self.cum, "open": len(self.open), "ts": C.iso(),
                            "entries": self.n_entries, "closes": self.n_closes})

    def on_marks(self, tracked, now, sol_usd):
        """Called by the engine after each mark pass with its tracked launches (each carries its marks so far)."""
        g, h, q = self.meta.state(now)
        if g == "resist":
            self.block_until = max(self.block_until, now + RESIST_BLOCK_S)
        # new launches at their first mark
        for key, tr in tracked.items():
            if key in self.open or tr["mint"] in self.seen or len(tr["marks"]) != 1 or len(self.open) >= MAX_OPEN or now < self.block_until:
                continue
            p = {**tr, "mint": tr["mint"], "match": tr["match"]}
            open_terms = set(t for pos in self.open.values() for t in pos["terms"])
            kind, size, read = decide(p, tr["t0"], self.meta, self.terms, self.comps, open_terms, self.stake)
            if not kind:
                continue
            e = [0.0, tr["v0"][0], tr["v0"][1], tr["marks"][0][3]]     # the message's reserves: where the counted book fills (entry_marks)
            tokens = D.buy(e[1], e[2], size)
            if tokens <= 0:
                continue
            pos = {"mint": tr["mint"], "symbol": tr["sym"], "curve": key, "tokens": tokens, "rem": tokens, "got": 0.0, "c": D.net_in(size), "size": size,
                   "kind": kind, "t0": tr["t0"], "t_in": now, "terms": list(tr["match"]), "read": read, "exits": [], "peak": 0.0, "trough": 0.0,
                   "stake_out": False, "slow_since": None, "entry": size / tokens, "mcap_usd_entry": e[1] / e[2] * 1e9 * (sol_usd or 0)}
            self.open[key] = pos
            self.seen.add(tr["mint"])
            self.n_entries += 1
            C.append(PAPER, {"kind": "entry", "leg": LEG, "mint": tr["mint"], "symbol": tr["sym"], "name": tr["name"], "price": pos["entry"], "size_sol": size,
                             "tokens": tokens, "mcap_usd": round(pos["mcap_usd_entry"]), "kind5": kind, "read": read, "terms": pos["terms"]})
        # open positions on their latest mark
        for key, pos in list(self.open.items()):
            tr = tracked.get(key)
            if not tr or not tr["marks"]:
                self._close(key, pos, None, now, "lost")
                continue
            marks = tr["marks"]
            i = len(marks) - 1
            m = marks[i]
            if m[2] <= 0:
                continue
            k = m[1] * m[2]
            vs = m[1] + pos["c"]
            val = D.sell(vs, k / vs, pos["rem"]) + pos["got"]
            pct = val / pos["size"] - 1
            pos["peak"], pos["trough"] = max(pos["peak"], pct), min(pos["trough"], pct)
            held = now - pos["t_in"]
            f1, _ = flow_at(marks, i)
            if f1 <= 0 and held >= 2:
                pos["slow_since"] = pos["slow_since"] if pos["slow_since"] is not None else now
            else:
                pos["slow_since"] = None
            why = None
            if pos["kind"] == "scalp":
                why = "take" if pct >= SCALP_TAKE else "stop" if pct <= SCALP_STOP else "time" if held >= SCALP_HOLD else None
            else:
                if not pos["stake_out"] and pct >= LEG1:
                    x = sell_for(m[1], m[2], pos["c"], pos["rem"], pos["size"])
                    g_ = gross_out(m[1], m[2], pos["c"], x)
                    pos["got"] += D.sell(vs, k / vs, x)
                    pos["c"] -= g_
                    pos["rem"] -= x
                    pos["stake_out"] = True
                    e = {"t": C.iso(now), "frac": round(x / pos["tokens"], 3), "pct": round(pct, 4), "why": "leg1"}
                    pos["exits"].append(e)
                    C.append(PAPER, {"kind": "exit", "leg": LEG, "mint": pos["mint"], "symbol": pos["symbol"], **e})
                    continue
                if g == "resist":
                    why = "resist"
                elif not any(self.terms.alive(t, now) for t in pos["terms"]):
                    why = "catalyst"
                elif pos["slow_since"] is not None and now - pos["slow_since"] >= SLOW_S:
                    why = "slow"
                elif not pos["stake_out"] and pct <= STOP:
                    why = "stop"
                elif held >= HOLD_S or tr.get("complete") is not None:
                    why = "time" if held >= HOLD_S else "complete"
            if why:
                self._close(key, pos, (val, pct, phase(marks, i)), now, why)
        self._save()

    def _close(self, key, pos, mark, now, why):
        self.open.pop(key, None)
        if mark is None:
            val, pct, ph = pos["got"], pos["got"] / pos["size"] - 1, "lost"
        else:
            val, pct, ph = mark
        e = {"t": C.iso(now), "frac": round(pos["rem"] / pos["tokens"], 3), "pct": round(pct, 4), "why": why}
        pos["exits"].append(e)
        C.append(PAPER, {"kind": "exit", "leg": LEG, "mint": pos["mint"], "symbol": pos["symbol"], **e})
        net = round(val - pos["size"], 4)
        self.cum += net
        self.peak_cum = max(self.peak_cum, self.cum)
        if self.peak_cum - self.cum >= RESET_DD and self.stake > SIZE_SOL / 2:
            self.stake = SIZE_SOL / 2                                   # N4: reset smaller, never add back
        self.n_closes += 1
        C.append(PAPER, {"kind": "close", "leg": LEG, "mint": pos["mint"], "symbol": pos["symbol"], "entry": pos["entry"], "net_sol": net,
                         "held_s": int(now - pos["t_in"]), "exits": pos["exits"], "peak_pct": round(pos["peak"], 4), "trough_pct": round(pos["trough"], 4),
                         "mcap_usd_entry": round(pos["mcap_usd_entry"]), "kind5": pos["kind"], "size_sol": pos["size"], "stake_out": pos["stake_out"],
                         "phase": ph, "read": pos["read"], "terms": pos["terms"]})
