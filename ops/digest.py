"""The Foresight Journal digest: one page, three windows (24 h, 7 d, 30 d), written to out/foresight.md (the body of the
Rich Foresight Doc) and out/foresight.html.
Pure reporting over journal/, forecast/ and state/. The daily task publishes the file; nothing here trades or scores."""
import datetime
import html
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C    # noqa: E402
import journal as J   # noqa: E402
import readout as R   # noqa: E402

OUT = C.path("out", "foresight.html")
OUT_MD = C.path("out", "foresight.md")   # the body of the Doc below, from "## Now" down
DOC = "https://claude.ai/code/artifact/da5f8af1-91bc-426e-a5ed-c675931ae39d"
DAY = 86400
SAY = {"ge": "at least {}", "gt": "above {}", "le": "at most {}", "lt": "below {}", "eq": "exactly {}"}
E = lambda x: html.escape(str(x))  # noqa: E731
CUT, EXCUR, BLAME = {}, {}, {}   # per build: close key -> haircut row, close key -> excursion row, pred_id -> (side, why)
pc = lambda x, spec="{:+.0%}": "n/a" if x is None else spec.format(x)  # noqa: E731


def _num(x):
    return "n/a" if x is None else f"{x:.3g}" if isinstance(x, float) else str(x)


def needs(p):
    t = p["threshold"]
    return f"between {_num(t[0])} and {_num(t[1])}" if p["direction"] == "in" else SAY[p["direction"]].format(_num(t))


def window(now, secs, data):
    """Everything that happened in the last `secs`, from rows already loaded."""
    cut = lambda rows: [r for r in rows if J._epoch(r["ts"]) >= now - secs]  # noqa: E731
    ev, paper, scores, shadow = cut(data["events"]), cut(data["paper"]), cut(data["scores"]), [r for r in cut(data["shadow"]) if J.independent(r)]
    closes = [r for r in paper if r.get("kind") == "close"]
    scored = [s for s in scores if s["brier"] is not None]
    side = lambda ok: [r for r in shadow if r["pass"] == ok]  # noqa: E731
    return {"events": len(ev), "resolved": sum(1 for e in ev if e.get("accepted")),
            "screened": sum(len(e.get("screen", [])) for e in ev), "passes": sum(1 for e in ev for x in e.get("screen", []) if x["pass"]),
            "entries": [r for r in paper if r.get("kind") == "entry"], "closes": closes,
            "net": sum(r["net_sol"] for r in closes), "wins": sum(1 for r in closes if r["net_sol"] > 0),
            "net_cut": _cut_sum(closes),
            "scores": scores, "brier": sum(s["brier"] for s in scored) / len(scored) if scored else None,
            "lessons": cut(data["lessons"]), "moves": [b for b in cut(data["beliefs"]) if b["cause"] != "seed"],
            "what_if": {ok: (len(side(ok)), sum(r["win"] for r in side(ok)), sum(r["net_sol"] for r in side(ok)) / len(side(ok)) if side(ok) else None)
                        for ok in (True, False)}}


def _key(r):
    return r["event_id"] + "|" + r["mint"]


def _cut_sum(closes):
    """Net of these closes after the fill haircut, or None when any of them has no liquidity snapshot or there is no SOL quote."""
    cut = [CUT.get(_key(r), {}).get("net_haircut") for r in closes]
    return sum(cut) if cut and None not in cut else None


def _stats(pairs):
    return '<dl class="stats">' + "".join(f"<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>" for k, v in pairs) + "</dl>"


def _list(items, empty, cap=6):
    if not items:
        return f'<p class="quiet">{E(empty)}</p>'
    more = f'<li class="quiet">and {len(items) - cap} more</li>' if len(items) > cap else ""
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items[:cap]) + more + "</ul>"


def _close(r):
    cls = "good" if r["net_sol"] > 0 else "bad"
    cut, x = CUT.get(_key(r), {}).get("net_haircut"), EXCUR.get(_key(r))
    real = f' <span class="quiet">({cut:+.3f} after the fill haircut)</span>' if cut is not None else ""
    run = (f'<br><span class="quiet">While held: best {pc(x["best_pct"])}, worst {pc(x["worst_pct"])}. In the 24 h after exit it peaked at '
           f'{pc(x["after_exit_peak_pct"])}{" so far" if x["open"] else ""}; the exits kept {pc(x["kept_of_peak"])} of the peak.</span>') if x else ""
    return (f'<b>{E(r["symbol"])}</b> <span class="{cls}">{r["net_sol"]:+.3f} SOL</span>{real} '
            f'<span class="quiet">{E(", ".join(e["why"] for e in r["exits"]))} after {r["held_s"] / 3600:.1f} h, from {E(r["event_id"].split(":")[0])}</span>{run}')


def _score(s):
    if s["outcome"] is None:
        return f'<span class="warn">Void</span> {E(s["claim"])} <span class="quiet">{"its leg ended first" if s["resolved_by"] == "superseded" else "could not be measured by its deadline"}</span>'
    cls, word = ("good", "Called it") if s["surprise_bits"] < 1 else ("bad", "Missed")
    side = BLAME.get(s["pred_id"])
    if word == "Missed" and side and side[0] in J.SIDES + ("rule",):
        word = {"market": "Missed, the market's doing", "screen": "Missed, the screen's doing", "exits": "Missed, the exits' doing",
                "rule": "Missed, the rule's doing (screen or exits)"}[side[0]]
    return (f'<span class="{cls}">{word}</span> {E(s["claim"])} <span class="quiet">{E(s["who"])} said {s["confidence"]:.0%}, '
            f'it {"happened" if s["outcome"] else "did not happen"}</span>')


def _lesson(l):
    move = f' <span class="quiet">Belief {E(l["belief"])} moved {l["p_from"]:.0%} to {l["p_to"]:.0%}.</span>' if l["belief"] and l["p_to"] is not None else ""
    rule = f'<br><span class="rule">Rule for the next leg: {E(l["rule"])}</span>' if l["rule"] else ""
    return f'{E(l["what"])} <span class="quiet">Why: {E(l["why"])}</span>{move}{rule}'


def _meter(label, value, limit, text, bad_when_full=True):
    pct = max(0.0, min(1.0, value / limit)) * 100
    cls = ("bad" if pct >= 70 else "warn" if pct >= 40 else "ok") if bad_when_full else "ok"
    return (f'<div class="meter"><div class="mrow"><span>{E(label)}</span><span>{E(text)}</span></div>'
            f'<div class="track"><div class="fill {cls}" style="width:{pct:.0f}%"></div></div></div>')


def _period(title, anchor, span, w, extra=""):
    n, wi, net = len(w["closes"]), w["wins"], w["net"]
    wf = w["what_if"]
    what_if = ""
    if wf[True][0] or wf[False][0]:
        row = lambda name, t: f"<tr><td>{name}</td><td>{t[0]}</td><td>{t[1] / t[0]:.0%}</td><td>{t[2]:+.3f}</td></tr>" if t[0] else ""  # noqa: E731
        what_if = ('<h3>What-if book</h3><p class="quiet">Every coin the screen looked at, followed for 24 hours under the contract exits. '
                   'If rejected coins do no worse than passed ones, the screen is not earning its place.</p>'
                   '<div class="scroll"><table><tr><th></th><th>coins</th><th>won</th><th>mean SOL</th></tr>'
                   + row("Passed the screen", wf[True]) + row("Rejected", wf[False]) + "</table></div>")
    return (f'<section id="{anchor}"><h2>{E(title)} <span class="quiet">{E(span)}</span></h2>'
            + _stats([("Events seen", w["events"]), ("Named a coin", w["resolved"]), ("Passed screen", f'{w["passes"]} of {w["screened"]}'),
                      ("Paper entries", len(w["entries"])), ("Closed", f"{n} ({wi} won)"), ("Net", f"{net:+.3f} SOL"),
                      ("Net after fill haircut", "n/a" if w["net_cut"] is None else f'{w["net_cut"]:+.3f} SOL')])
            + "<h3>Trades closed</h3>" + _list([_close(r) for r in reversed(w["closes"])], "No paper trade closed in this window.")
            + "<h3>Forecasts that resolved</h3>" + _list([_score(s) for s in reversed(w["scores"])], "No forecast resolved in this window.")
            + (f'<p class="quiet">Accuracy score {w["brier"]:.3f} (0 is perfect, 0.25 is a coin flip).</p>' if w["brier"] is not None else "")
            + "<h3>Lessons written</h3>" + _list([_lesson(l) for l in reversed(w["lessons"])], "No lesson written in this window.", 4)
            + what_if + extra + "</section>")


def build(now=None):
    now = now or C.now()
    CUT.clear(), EXCUR.clear(), BLAME.clear()
    CUT.update({_key(r): r for r in J.book([r for r in J.all_paper() if r.get("kind") == "close"])})
    EXCUR.update({x["key"]: x for x in J.excursions(now)})
    preds_all, scores_all = C.read_jsonl(J.PREDS), C.read_jsonl(J.SCORES)
    BLAME.update({x["pred_id"]: J.blame(x, preds_all, scores_all) for x in scores_all if x["resolved_by"] != "superseded"})
    data = {"events": C.read_jsonl(J.EVENTS), "paper": C.read_jsonl(J.PAPER), "scores": C.read_jsonl(J.SCORES),
            "lessons": C.read_jsonl(J.LESSONS), "beliefs": C.read_jsonl(J.BELIEFS), "shadow": C.read_jsonl(J.SHADOW)}
    m, leg = J.metrics(), J.leg()
    nets = [r["net_sol"] for r in data["paper"] if r.get("kind") == "close"]
    s = R.stats(nets)
    with open(os.path.join(C.ROOT, "prereg", "CONTRACT.md"), encoding="utf-8") as f:
        contract = f.read()
    start, end = re.search(r"Frozen (\d{4}-\d\d-\d\d)", contract).group(1), re.search(r"Give-up date (\d{4}-\d\d-\d\d)", contract).group(1)
    d = lambda iso: datetime.date.fromisoformat(iso)  # noqa: E731
    local = datetime.datetime.fromtimestamp(now).astimezone()
    day_n, day_all = (local.date() - d(start)).days + 1, (d(end) - d(start)).days + 1
    hb = C.load_json(C.path("monitor", "heartbeat.json"), {})
    hb_age = now - J._epoch(hb["ts"]) if hb.get("ts") else None
    alive = hb_age is not None and hb_age < 600
    owed, checks, chain = J.owed(), J.belief_checks(m), J.verify()
    strained = [c for c in checks if c["strained"]]
    open_preds = sorted(J.open_preds(), key=lambda p: p["deadline"])
    overdue = [p for p in open_preds if p["metric"] == "manual" and C.iso(now)[:10] > p["deadline"]]
    day, week, month = (window(now, k * DAY, data) for k in (1, 7, 30))
    marks = {v["mint"]: v["path"][-1][1] for v in C.load_json(J.SHADOW_STATE, {}).values() if v["path"]}

    # ---- bottom line: what a reader with one minute needs
    plain = {"INSUFFICIENT": "too early to call", "KILL": "at KILL", "SURVIVES ON PAPER": "surviving on paper", "ALIVE, S1 NOT MET": "alive but short of the bar"}
    line = [f"<b>{E(leg)} is {E(plain[s['verdict']])}</b>: {E(s['why'])}. The paper book stands at <b>{s['cum']:+.3f} SOL</b> after {s['n']} closed "
            f"trade{'s' * (s['n'] != 1)} ({s['wins']} won)."
            + (f" A real fill would have left about <b>{m['cum_net_haircut']:+.3f} SOL</b>." if m["cum_net_haircut"] is not None else "")]
    line.append(f"In the last 24 hours the sensor saw {day['events']} events, {day['resolved']} named a coin, {day['passes']} passed the screen, "
                f"{len(day['entries'])} became paper entries and {len(day['closes'])} closed for {day['net']:+.3f} SOL.")
    if day["scores"]:
        missed = sum(1 for x in day["scores"] if x["resolved_by"] != "superseded" and (x["outcome"] is None or x["surprise_bits"] >= 1))
        line.append(f"{len(day['scores'])} forecast{'s' * (len(day['scores']) != 1)} resolved today, {missed} of them a surprise.")
    elif open_preds:
        line.append(f"No forecast resolved today. The next deadline is {E(open_preds[0]['deadline'])}: {E(open_preds[0]['claim'])}.")
    todo = []
    if not alive:
        todo.append("the sensor is not heartbeating, so nothing is being recorded")
    if chain:
        todo.append("the journal's tamper check failed (" + E("; ".join(chain)) + ")")
    if owed:
        todo.append(f"{len(owed)} surprise{'s' * (len(owed) != 1)} still ha{'ve' if len(owed) != 1 else 's'} no lesson written")
    if strained:
        todo.append(f"the data contradicts belief{'s' * (len(strained) != 1)} {E(', '.join(c['id'] for c in strained))}")
    if overdue:
        todo.append(f"{len(overdue)} forecast{'s' * (len(overdue) != 1)} wait{'s' * (len(overdue) == 1)} for your yes or no")
    line.append('<span class="warn"><b>Needs attention:</b></span> ' + "; ".join(todo) + "." if todo else "<b>Nothing needs you today.</b>")

    # ---- today extras: gates, open positions, what is coming
    gates = (_meter("Trades toward the 40 needed for a verdict", s["n"], 40, f"{s['n']} of 40", bad_when_full=False)
             + _meter("Losing streak (10 in a row ends the leg)", s["streak"], 10, f"{s['streak']} of 10")
             + _meter("Drawdown (more than 8 SOL ends the leg)", s["dd"], 8, f"{s['dd']:.2f} of 8 SOL"))
    opens = []
    for p in C.load_json(C.path("state", "positions.json"), []):
        chg = f'{marks[p["mint"]] / p["entry"] - 1:+.0%} now' if p["mint"] in marks else "no mark yet"
        opens.append(f'<b>{E(p["symbol"])}</b> {E(chg)} <span class="quiet">open {(now - p["t0"]) / 3600:.1f} h, closes by the contract exits</span>')
    coming = []
    for p in open_preds[:5]:
        cur = "you decide" if p["metric"] == "manual" else f'now {_num(J.value(p["metric"], m))}, needs {needs(p)}'
        coming.append(f'<span class="date">{E(p["deadline"][5:])}</span> {E(p["claim"])} <span class="quiet">{E(p["who"])} says {p["confidence"]:.0%}; {E(cur)}</span>')
    utc = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date()
    mk_rows = ""
    for i in (2, 1, 0):
        dd = str(utc - datetime.timedelta(days=i))
        k = J.market(dd, now=now)
        if k["mk_touches"]:
            group = "still running" if k["pending"] else "n/a" if k["mk_ret24"] is None else f'{k["mk_ret24"]:+.1%}, {k["mk_up"]:.0%} up'
            mk_rows += (f'<tr><td>{E(dd[5:])}</td><td>{k["mk_touches"]:.0f}</td><td>{k["mk_resolved"]:.0f}</td><td>{k["mk_intent"]:.0f}</td>'
                        f'<td>{pc(k["mk_pass_rate"], "{:.0%}")}</td><td>{E(group)}</td></tr>')
    market = ('<h3>The market, before any rule</h3><p class="quiet">What the feeds brought each UTC day, and how the coins the screen looked at did over '
              'their next 24 hours as a group. A forecast that misses while these hold is the rule\'s miss, not the market\'s.</p>'
              '<div class="scroll"><table><tr><th>day</th><th>touches</th><th>named a coin</th><th>showed intent</th><th>passed screen</th>'
              '<th>screened coins, 24 h</th></tr>' + mk_rows + "</table></div>") if mk_rows else ""
    days = J.shadow_days()
    movers = ""
    if days:
        v = J.movers(days[-1])
        tag = lambda r: "entered" if r["entered"] else "passed, not entered" if r["pass"] else "rejected"  # noqa: E731
        item = lambda r, key: (f'<b>{E(r["symbol"])}</b> {r[key]:+.0%} <span class="quiet">{tag(r)}; the exits booked {r["net_sol"]:+.3f} SOL, '  # noqa: E731
                               f'{pc(r["kept"])} of its peak</span>')
        movers = (f'<h3>Winners and losers <span class="quiet">coins screened {E(days[-1][5:])}, followed 24 h</span></h3>'
                  f'<p class="quiet">Of the peak on offer the exits kept {pc(v["capture_entered"])} on the {v["n_entered"]} entered, '
                  f'{pc(v["capture_pass"])} on everything that passed the screen and {pc(v["capture_all"])} on all {v["n"]} screened.</p>'
                  + "<p class=\"quiet\">Ran most</p>" + _list([item(r, "peak_pct") for r in v["ran"]], "None.")
                  + "<p class=\"quiet\">Fell most</p>" + _list([item(r, "trough_pct") for r in v["fell"]], "None."))
    today_extra = (market + movers + "<h3>How close the leg is to a verdict</h3>" + gates + "<h3>Open positions</h3>" + _list(opens, "No paper position is open.")
                   + f"<h3>Next forecasts to resolve <span class=\"quiet\">{len(open_preds)} open</span></h3>" + _list(coming, "No open forecast.", 5))

    # ---- month extras: the model itself
    rows = ""
    for c in checks:
        seen = f'{c["k_now"]} of {c["n_now"]}' if c["n_now"] else "no data yet"
        state = '<span class="bad">data disagrees</span>' if c["strained"] else ('<span class="good">holding</span>' if c["n_now"] else '<span class="quiet">untested</span>')
        moved = f'{c["seed_p"]:.0%} to {c["p"]:.0%}' if c["p"] != c["seed_p"] else f'{c["p"]:.0%}'
        rows += f'<tr><td>{E(c["id"])}</td><td class="claim">{E(c["claim"])}</td><td>{moved}</td><td>{E(seen)}</td><td>{state}</td></tr>'
    who = ""
    for name in sorted({x["who"] for x in data["scores"]}):
        b, n = J._brier([x for x in data["scores"] if x["who"] == name])
        who += f"<li><b>{E(name)}</b> {n} scored, accuracy {'n/a' if b is None else f'{b:.3f}'}</li>"
    rules = [E(l["rule"]) for l in data["lessons"] if l["rule"]]
    rv = J.rivals(data["shadow"])
    rival = (f'<h3>Is the per-coin forecast learning?</h3><p>On {rv["n"]} closed coins (0 is perfect): '
             + ", ".join(f"{E(name)} {b:.3f}" for name, b in rv["brier"].items()) + f'. Ahead: <b>{E(" and ".join(rv["ahead"]))}</b>.</p>') if rv else ""
    caps = [f'<span class="date">{E(dd[5:])}</span> kept {pc(v["capture_entered"])} of the peak on {v["n_entered"]} entered, {pc(v["capture_pass"])} on passes, '
            f'{pc(v["capture_all"])} on all {v["n"]} screened' for dd in reversed(days[-30:]) for v in [J.movers(dd)]]
    sol = C.load_json(J.SOL_USD, {})
    floor = J.haircut(C.LIQ_FLOOR)
    cutnote = ("<h3>The fill haircut</h3><p class=\"quiet\">The paper book trades at the quoted price. A real order moves a thin pool: about 4 times the order "
               "size divided by the pool's liquidity, round trip, before fees."
               + (f' With SOL at ${sol["usd"]:,.0f} that is {floor / J.P.SIZE_SOL:.1%} of a trade at the ${C.LIQ_FLOOR:,} liquidity floor.' if floor is not None else "")
               + " Every paper figure on this page is shown beside its figure after that haircut.</p>")
    month_extra = ('<h3>The mental model</h3><p class="quiet">Each belief with the odds we give it. "Data" counts direct tests from the what-if book.</p>'
                   '<div class="scroll"><table><tr><th></th><th>belief</th><th>odds</th><th>data</th><th></th></tr>' + rows + "</table></div>"
                   + rival + "<h3>Capture by day</h3>" + _list(caps, "No followed coin has finished its 24 hours yet.", 10) + cutnote
                   + ("<h3>Forecasters, all time</h3><ul>" + who + "</ul>" if who else "")
                   + "<h3>Rules carried to the next leg</h3>" + _list(rules, "None yet.", 8))

    stamp = local.strftime("%A %B %d, %Y, %I:%M %p").replace(" 0", " ") + " Central"
    body = (f'<header><p class="eyebrow">rich &middot; leg {E(leg)} &middot; day {day_n} of {day_all}</p><h1>Rich Foresight</h1>'
            f'<p class="stamp">{E(stamp)} &middot; sensor <span class="{"good" if alive else "bad"}">{"running" if alive else "DOWN"}</span></p>'
            f'<p class="stamp">This page has moved. The daily update now goes to the Rich Foresight doc: <a href="{DOC}">{DOC}</a></p></header>'
            '<section class="bottom"><h2>Bottom line</h2>' + "".join(f"<p>{x}</p>" for x in line) + "</section>"
            '<nav><a href="#today">Today</a><a href="#week">This week</a><a href="#month">This month</a></nav>'
            + _period("Today", "today", "last 24 hours", day, today_extra)
            + _period("This week", "week", "last 7 days", week)
            + _period("This month", "month", "last 30 days", month, month_extra)
            + '<footer>Paper only. No order is placed. Updated once a day; trades and prices are logged every 5 minutes on the workstation.</footer>')
    # ---- the same page as markdown, for the Rich Foresight Doc (the unattended run can update a Doc; it has no Artifact tool)
    T = lambda h: html.unescape(re.sub(r"<[^>]+>", "", h.replace("<b>", "**").replace("</b>", "**").replace("<br>", " ")))  # noqa: E731

    def md_period(title, span, w, full=False):
        cutnet = "n/a" if w["net_cut"] is None else f'{w["net_cut"]:+.3f} SOL'
        live = [x for x in w["scores"] if x["resolved_by"] != "superseded"]
        gone = len(w["scores"]) - len(live)
        return ([f"## {title} ({span})", "", "| events seen | named a coin | passed screen | paper entries | closed | net | net after fill haircut |",
                 "|---|---|---|---|---|---|---|",
                 f'| {w["events"]} | {w["resolved"]} | {w["passes"]} of {w["screened"]} | {len(w["entries"])} | {len(w["closes"])} ({w["wins"]} won) | {w["net"]:+.3f} SOL | {cutnet} |',
                 "", "**Trades closed**", ""] + (["- " + T(_close(r)) for r in reversed(w["closes"])][:6] or ["- No paper trade closed in this window."])
                + ["", "**Forecasts that resolved**", ""] + ([re.sub(r"^(Called it|Void|Missed[^A-Z]*?) (?=[A-Z0-9])", r"- \1: ", T(_score(x))) for x in reversed(live)][:6] or ["- None."])
                + ([f"- {gone} forecasts of an ended leg were voided unanswered."] if gone else [])
                + (["", "**Lessons written**", ""] + (["- " + T(_lesson(l)) for l in reversed(w["lessons"])][:4] or ["- None."]) if full else
                   ["", f"**Lessons written**: {len(w['lessons'])}. Their rules are listed under This month."]))

    md = ["## Now", ""] + [y for x in line for y in (T(x), "")] + md_period("Today", "last 24 hours", day, full=True)
    mk_md = []
    for i in (2, 1, 0):
        dd = str(utc - datetime.timedelta(days=i))
        k = J.market(dd, now=now)
        if k["mk_touches"]:
            group = "still running" if k["pending"] else "n/a" if k["mk_ret24"] is None else f'{k["mk_ret24"]:+.1%}, {k["mk_up"]:.0%} up'
            mk_md.append(f'| {dd[5:]} | {k["mk_touches"]:.0f} | {k["mk_resolved"]:.0f} | {k["mk_intent"]:.0f} | {pc(k["mk_pass_rate"], "{:.0%}")} | {group} |')
    if mk_md:
        md += ["", "**The market, before any rule**", "", "| UTC day | touches | named a coin | showed intent | passed screen | screened coins, 24 h |", "|---|---|---|---|---|---|"] + mk_md
    if days:
        md += ["", f'**Winners and losers** (coins screened {days[-1][5:]}, followed 24 h). Of the peak on offer the exits kept {pc(v["capture_entered"])} on the '
                   f'{v["n_entered"]} entered, {pc(v["capture_pass"])} on everything that passed and {pc(v["capture_all"])} on all {v["n"]} screened.', ""]
        md += ["- ran: " + T(item(r, "peak_pct")) for r in v["ran"]] + ["- fell: " + T(item(r, "trough_pct")) for r in v["fell"]]
    md += ["", f"**Toward a verdict**: {s['n']} of 40 closed trades; losing streak {s['streak']} of 10; drawdown {s['dd']:.2f} of 8 SOL.",
           "", "**Open positions**", ""] + (["- " + T(o) for o in opens] or ["- No paper position is open."])
    md += ["", f"**Next forecasts to resolve** ({len(open_preds)} open)", ""] + (["- " + T(c) for c in coming] or ["- None."])
    md += [""] + md_period("This week", "last 7 days", week) + [""] + md_period("This month", "last 30 days", month)
    md += ["", "**The mental model**", "", "| | belief | odds | data | |", "|---|---|---|---|---|"]
    for c in checks:
        seen = f'{c["k_now"]} of {c["n_now"]}' if c["n_now"] else "no data yet"
        state = "data disagrees" if c["strained"] else "holding" if c["n_now"] else "untested"
        moved = f'{c["seed_p"]:.0%} to {c["p"]:.0%}' if c["p"] != c["seed_p"] else f'{c["p"]:.0%}'
        md.append(f'| {c["id"]} | {c["claim"]} | {moved} | {seen} | {state} |')
    if rv:
        md += ["", "**Is the per-coin forecast learning?** " + T(rival.split("</h3>")[1])]
    md += ["", "**Capture by day**", ""] + (["- " + T(c) for c in caps[:10]] or ["- No followed coin has finished its 24 hours yet."])
    md += ["", "**The fill haircut.** " + T(cutnote.split("</h3>")[1]), "", "**Rules carried to the next leg**", ""]
    md += ["- " + html.unescape(r) for r in rules[:8]] or ["- None yet."]
    md += ["", f"Paper only. No order is placed. Built {stamp}; sensor {'running' if alive else 'DOWN'}."]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "digest.css"), encoding="utf-8") as f:
        css = f.read()
    page = ("<title>Rich Foresight</title>\n"
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@600&display=swap">\n'
            f"<style>\n{css}</style>\n<main>{body}</main>\n")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    return OUT


if __name__ == "__main__":
    print(build())
