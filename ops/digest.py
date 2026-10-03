"""The Foresight Journal digest: one page, three windows (24 h, 7 d, 30 d), written to out/foresight.html.
Pure reporting over journal/, forecast/ and state/. The daily task publishes the file; nothing here trades or scores."""
import datetime
import html
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C    # noqa: E402
import journal as J   # noqa: E402
import readout as R   # noqa: E402

OUT = C.path("out", "foresight.html")
DAY = 86400
SAY = {"ge": "at least {}", "gt": "above {}", "le": "at most {}", "lt": "below {}", "eq": "exactly {}"}
E = lambda x: html.escape(str(x))  # noqa: E731


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
            "scores": scores, "brier": sum(s["brier"] for s in scored) / len(scored) if scored else None,
            "lessons": cut(data["lessons"]), "moves": [b for b in cut(data["beliefs"]) if b["cause"] != "seed"],
            "what_if": {ok: (len(side(ok)), sum(r["win"] for r in side(ok)), sum(r["net_sol"] for r in side(ok)) / len(side(ok)) if side(ok) else None)
                        for ok in (True, False)}}


def _stats(pairs):
    return '<dl class="stats">' + "".join(f"<div><dt>{E(k)}</dt><dd>{E(v)}</dd></div>" for k, v in pairs) + "</dl>"


def _list(items, empty, cap=6):
    if not items:
        return f'<p class="quiet">{E(empty)}</p>'
    more = f'<li class="quiet">and {len(items) - cap} more</li>' if len(items) > cap else ""
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items[:cap]) + more + "</ul>"


def _close(r):
    cls = "good" if r["net_sol"] > 0 else "bad"
    return (f'<b>{E(r["symbol"])}</b> <span class="{cls}">{r["net_sol"]:+.3f} SOL</span> '
            f'<span class="quiet">{E(", ".join(e["why"] for e in r["exits"]))} after {r["held_s"] / 3600:.1f} h, from {E(r["event_id"].split(":")[0])}</span>')


def _score(s):
    if s["outcome"] is None:
        return f'<span class="warn">Void</span> {E(s["claim"])} <span class="quiet">could not be measured by its deadline</span>'
    cls, word = ("good", "Called it") if s["surprise_bits"] < 1 else ("bad", "Missed")
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
                      ("Paper entries", len(w["entries"])), ("Closed", f"{n} ({wi} won)"), ("Net", f"{net:+.3f} SOL")])
            + "<h3>Trades closed</h3>" + _list([_close(r) for r in reversed(w["closes"])], "No paper trade closed in this window.")
            + "<h3>Forecasts that resolved</h3>" + _list([_score(s) for s in reversed(w["scores"])], "No forecast resolved in this window.")
            + (f'<p class="quiet">Accuracy score {w["brier"]:.3f} (0 is perfect, 0.25 is a coin flip).</p>' if w["brier"] is not None else "")
            + "<h3>Lessons written</h3>" + _list([_lesson(l) for l in reversed(w["lessons"])], "No lesson written in this window.", 4)
            + what_if + extra + "</section>")


def build(now=None):
    now = now or C.now()
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
            f"trade{'s' * (s['n'] != 1)} ({s['wins']} won)."]
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
        opens.append(f'<b>{E(p["symbol"])}</b> {E(chg)} <span class="quiet">open {(now - p["t0"]) / 3600:.1f} h, closes by rule: '
                     f'25% down, half off at double, or 24 h</span>')
    coming = []
    for p in open_preds[:5]:
        cur = "you decide" if p["metric"] == "manual" else f'now {_num(m.get(p["metric"]))}, needs {needs(p)}'
        coming.append(f'<span class="date">{E(p["deadline"][5:])}</span> {E(p["claim"])} <span class="quiet">{E(p["who"])} says {p["confidence"]:.0%}; {E(cur)}</span>')
    today_extra = ("<h3>How close the leg is to a verdict</h3>" + gates + "<h3>Open positions</h3>" + _list(opens, "No paper position is open.")
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
    month_extra = ('<h3>The mental model</h3><p class="quiet">Each belief with the odds we give it. "Data" counts direct tests from the what-if book.</p>'
                   '<div class="scroll"><table><tr><th></th><th>belief</th><th>odds</th><th>data</th><th></th></tr>' + rows + "</table></div>"
                   + ("<h3>Forecasters, all time</h3><ul>" + who + "</ul>" if who else "")
                   + "<h3>Rules carried to the next leg</h3>" + _list(rules, "None yet.", 8))

    stamp = local.strftime("%A %B %d, %Y, %I:%M %p").replace(" 0", " ") + " Central"
    body = (f'<header><p class="eyebrow">rich &middot; leg {E(leg)} &middot; day {day_n} of {day_all}</p><h1>Rich Foresight</h1>'
            f'<p class="stamp">{E(stamp)} &middot; sensor <span class="{"good" if alive else "bad"}">{"running" if alive else "DOWN"}</span></p></header>'
            '<section class="bottom"><h2>Bottom line</h2>' + "".join(f"<p>{x}</p>" for x in line) + "</section>"
            '<nav><a href="#today">Today</a><a href="#week">This week</a><a href="#month">This month</a></nav>'
            + _period("Today", "today", "last 24 hours", day, today_extra)
            + _period("This week", "week", "last 7 days", week)
            + _period("This month", "month", "last 30 days", month, month_extra)
            + '<footer>Paper only. No order is placed. Updated once a day; trades and prices are logged every 5 minutes on the workstation.</footer>')
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
