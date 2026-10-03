"""One rich decision ruled through RI: the same laws, source masses and engine as ~/hustle/ppg/decide.py, without PPG's ledger.

Input   decisions/<date>-<slug>.json, written AFTER going to look (a step with no read is not that step)
Output  decisions/<date>-<slug>.md (the Decision Output) · -rulings.json · ri-log-<date>-<slug>.bin · one row in journal/decisions.jsonl

The file format and the law checks are PPG's (`check`): every claim is FACT, INFERENCE, ASSUMPTION, HYPOTHESIS or UNKNOWN and the label
caps its mass; no option carries a p; every option says how it fails; not survivable, or outside the circle and irreversible, is a veto;
the door is split and the irreversible half is gated. The constraint line is this repo's own readout verdict. Nothing here places an order.

Usage:  python ops/decide.py <date>-<slug>
"""
import importlib.util
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C   # noqa: E402
import readout as R  # noqa: E402

DDIR = os.path.join(ROOT, "decisions")
_spec = importlib.util.spec_from_file_location("ppg_decide", os.path.join(os.path.expanduser("~"), "hustle", "ppg", "decide.py"))
PD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PD)
J, week, OMEGA, M = PD.J, PD.week, PD.OMEGA, PD.M


def run(key):
    sys.stdout.reconfigure(encoding="utf-8")
    with open(os.path.join(DDIR, key + ".json"), encoding="utf-8") as f:
        dec = json.load(f)
    PD.check(dec)
    as_of = date.fromisoformat(dec["as_of"])
    import journal as JR  # here: journal imports readout
    s = R.stats([r["net_sol"] for r in C.read_jsonl(JR.PAPER) if r.get("kind") == "close"])
    opts = []
    for o in dec["options"]:
        veto = "L5: the downside is not survivable" if o["survivable"] is False else \
            "L6: outside the circle and irreversible" if (o["competence"] == "outside" and o["reversible"] is False) else (o.get("veto") or "")
        opts.append({**o, "veto": veto})
    rec = dec["recommendation"]
    chosen = next(o for o in opts if o["id"] == rec["option"])
    if chosen["veto"]:
        raise J.LawError(f"the recommendation points at a vetoed option ({chosen['id']}: {chosen['veto']})")

    pre = f"rich-{key}"
    pol = {"FACT": "ruling", "INFERENCE": "ruling", "ASSUMPTION": "assumed", "HYPOTHESIS": "hypothesis"}
    claims = [(f"{pre}-{c['id']}", c.get("layer", "L2"), c["label"], c["text"], [tuple(x) for x in c.get("src", [])]) for c in dec.get("claims", [])]
    claims.append((f"{pre}-M01", "L1", "FACT", f"Leg {JR.leg()} stands at {s['verdict']}: {s['why']}", [("arith", "alive", "ops/readout.py", "")]))
    claims += [(f"{pre}-opt-{o['id']}", "L3", o["label"], f"[{'VETOED' if o['veto'] else 'OPEN'}] {o['do']}",
                [("ruling", "dead", o["veto"], "veto")] if o["veto"] else ([(pol[o["label"]], "alive", o.get("basis", ""), "")] if o["label"] != "UNKNOWN" else []))
               for o in opts]
    claims.append((f"{pre}-{rec['id']}", "L4", rec["label"], rec["text"], [tuple(x) for x in rec["src"]]))

    week.ANCHOR, week.SEED = "rich-decide", b"rich-decide-ri-v1"
    ev = week.Ev(int(datetime(as_of.year, as_of.month, as_of.day, 23, 59, tzinfo=timezone.utc).timestamp()))
    lt = int(datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc).timestamp())
    for cid, _, label, text, srcs in claims:
        for n, (policy, stance, name, note) in enumerate(srcs):
            mass, unc = J.SRC[policy]
            ev.obs(f"{cid}:{n}", name or "unnamed", cid, {stance: D(mass), OMEGA: D(1) - D(mass)}, lt, unc, {"claim": text, "note": note, "policy": policy, "label": label})
    gates = [(g["name"], g["op"], g["field"], g["bar"], g.get("measured", 0), g.get("from", "")) for g in dec.get("gates", [])]
    for name, op, fld, bar, val, _ in gates:
        ev.gate(name, [op, ["field", fld], ["const", bar]])
        ev.obs(f"gate:{name}:{key}", "operator-measure", f"gate:{name}", {"alive": D("0.9"), OMEGA: D("0.1")}, lt, [M], {"claim": f"{fld} = {val}"}, {fld: val})
    state = ev.state()["propositions"]
    ruled = []
    for cid, layer, label, text, _ in claims:
        mm = week.masses(state[cid]["belief"]) if cid in state and state[cid].get("belief") is not None else {}
        ruled.append({"claim": cid, "layer": layer, "label": label, "text": text, "ruling": week.ruling(mm) if mm else "UNVERIFIED",
                      "alive": f"{mm.get('alive', D(0)):.2f}", "dead": f"{mm.get('dead', D(0)):.2f}"})
    grow = [{"gate": n, "rule": f"{f} {'>=' if op == 'ge' else '<='} {bar}", "measured": v,
             "reading": "BELIEF" if state[f"gate:{n}"]["belief"] is not None else "NO BELIEF", "from": w} for n, op, f, bar, v, w in gates]
    root, size = ev.log.root().hex(), len(ev.log)
    with open(os.path.join(DDIR, f"ri-log-{key}.bin"), "wb") as f:
        f.write(week.encode({"kind": "log_export", "anchor": "rich-decide", "entries": [ev.log.entry(i) for i in range(size)]}))

    facts = [r for r in ruled if r["layer"] in ("L0", "L1", "L2")]
    L = [f"# Decision · {dec['decision']}", "", f"{as_of:%A} {as_of} · asked by {dec.get('asked_by', 'the operator')} · log root `{root}` · size {size}", "",
         "## REALITY", "Looked at before reasoning: " + "; ".join(dec["looked"]) + "."]
    for lab in ("FACT", "INFERENCE", "ASSUMPTION", "HYPOTHESIS", "UNKNOWN"):
        L += [f"- **{lab}** · {r['text']} · _{r['ruling']}_" for r in facts if r["label"] == lab]
    L += ["", "## OPTIONS", "", "| option | status | do | circle | door |", "|---|---|---|---|---|"]
    L += [f"| {o['id']} | {'VETOED' if o['veto'] else 'open'} | {o['do']} | {o['competence']} | {'reversible' if o['reversible'] else 'IRREVERSIBLE'} |" for o in opts]
    L += ["", "## ASYMMETRY"] + [f"- **{o['id']}**: {o['asymmetry']}" for o in opts if o.get("asymmetry")]
    L += ["", "## SURVIVAL"] + [f"- **{o['id']}** fails if {o['fails_if']}" + (f" · VETOED: {o['veto']}" if o["veto"] else "") for o in opts]
    L += ["", "## INCENTIVES", f"- {dec['who_profits']}"]
    L += ["", "## LEVERAGE, OWNERSHIP, COMPOUNDING"] + [f"- **{o['id']}** leaves: {o['asset'] or 'nothing'} ({o['ownership']})" for o in opts]
    L += ["", "## SYSTEM EFFECT"] + [f"- **{o['id']}**: {o['system_effect']}" for o in opts]
    L += ["", "## THE DOOR", f"- Reversible, decided now: {dec['split']['reversible_now']}", f"- Irreversible, gated: {dec['split']['irreversible_gated']}"]
    L += ["", "## RECOMMENDATION", f"**{rec['option']}.** {rec['text']} · _{ruled[-1]['ruling']}_"]
    L += ["", "## Gates on the irreversible half", "", "| gate | rule | measured | reading | from |", "|---|---|---|---|---|"]
    L += [f"| {g['gate']} | {g['rule']} | {g['measured']} | **{g['reading']}** | {g['from']} |" for g in grow]
    body = "\n".join(L)
    L += ["", "## Ledger", "", "| claim | layer | label | ruling | m(alive) | m(dead) |", "|---|---|---|---|---|---|"]
    L += [f"| {r['claim']} | {r['layer']} | {r['label']} | **{r['ruling']}** | {r['alive']} | {r['dead']} |" for r in ruled]
    with open(os.path.join(DDIR, key + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(DDIR, key + "-rulings.json"), "w", encoding="utf-8") as f:
        json.dump({"root": root, "size": size, "options": opts, "rows": ruled, "gates": grow}, f, indent=1, ensure_ascii=False)
    C.append(C.path("journal", "decisions.jsonl"), {"key": key, "leg": JR.leg(), "decision": dec["decision"], "recommended": rec["option"],
                                                    "ruling": ruled[-1]["ruling"], "root": root})
    print(body)
    print(f"\nlog root {root} · size {size} · journalled in journal/decisions.jsonl")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.split("Usage:")[1].strip())
        raise SystemExit(2)
    try:
        raise SystemExit(run(sys.argv[1]))
    except J.LawError as e:
        print(e, file=sys.stderr)
        raise SystemExit(3)
