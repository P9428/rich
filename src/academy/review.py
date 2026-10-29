"""The review: out/academy.md, rewritten every tick. It names the single limiting factor by a fixed rule, in this order, and stops
at the first that binds: the sensor (the tape has gaps today), the search (no cell passes fit and held-out), the answer (a cell
passes the arena but not the answer term), sim-to-real (a cell on a rung with the residual outside tolerance), the group (a cell on a
rung waiting for its legs), capital (a cell at the top rung). Every real leg is a point on the page. The page also prints what the
best cell projects to against the operator's stated target, in the operator's own units, so the gap is a number and not a mood.
"""
import time

import numpy as np

from . import arena as A
from . import cells as CE
from . import record as R
from . import residual as RS
from . import rungs as RU
from . import search as S

TARGET_USD = 10_000
TARGET_DAYS = 7


def fmt(x, f="+.4f"):
    return "" if x is None else format(x, f)


def sensor_gap(rec, labels, now):
    """Hours of today with no launch logged, up to now: the sensor's gap on the held-out day."""
    held = sorted(set(labels))[-1]
    m = labels == held
    hours = set(rec["hour"][m].astype(int))
    elapsed = int(time.gmtime(now).tm_hour) + 1 if time.strftime("%Y-%m-%d", time.gmtime(now)) == held else 24
    missing = [h for h in range(elapsed) if h not in hours]
    last = float(rec["ts"][m].max()) if m.any() else 0.0
    return {"day": held, "elapsed_h": elapsed, "hours_with_tape": len(hours), "missing": missing, "since_last_launch_s": now - last}


def limiting(gap, tally, ladder, pairs):
    if len(gap["missing"]) > 1 or gap["since_last_launch_s"] > 1800:
        return "SENSOR", f"the tape is missing {len(gap['missing'])} of {gap['elapsed_h']} hours today (last launch {gap['since_last_launch_s'] / 60:.0f} min ago); no bit is bought while the record has holes"
    on_rung = {k: v for k, v in ladder.items() if v.get("status") == "rung"}
    if not on_rung:
        if tally["eligible"] == 0:
            return "SEARCH", (f"no cell passes fit and held-out: {tally['cells']} on the roster, {tally['fit_pos']} positive on the fit period, "
                              f"{tally['held_pos']} of those positive on the held-out day, 0 past the lower bound and the answer term; "
                              f"{tally['expected_by_luck']} would pass by luck alone")
        return "RULING", f"{tally['eligible']} cell(s) eligible for rung 0 and none promoted: a ruling under decisions/ is the gate (the code never promotes)"
    for cid, s in on_rung.items():
        legs = [p for p in pairs if p["cell"] == cid and p.get("resid") is not None and abs(p["size"] - RU.RUNGS[s["rung"]]) < 1e-9]
        res = RS.summary(legs)
        if res["n"] >= RU.GROUP and not res["within"]:
            return "SIM-TO-REAL", f"cell {cid} at rung {s['rung']}: the residual is {res['mean_pts']:+.3f} of size over {res['n']} legs, outside {RS.TOL}"
        if res["n"] < RU.GROUP:
            return "GROUP", f"cell {cid} at rung {s['rung']} ({RU.RUNGS[s['rung']]} SOL) has {res['n']} of {RU.GROUP} real legs; the operator's legs are the bit"
        if s["rung"] == len(RU.RUNGS) - 1:
            return "CAPITAL", f"cell {cid} holds the top rung on {res['n']} legs"
    return "GROUP", "cells on rungs are waiting for legs"


def projection(row, gap, sol_usd):
    """What the best held-out cell projects to a day at the contract's size, against the target."""
    if not row or not row["held"]["n"]:
        return None
    frac = max(gap["hours_with_tape"], 1) / 24
    per_day = row["held"]["n"] / frac
    mean = row["answered"] if row.get("answered") is not None else row["held"]["mean"]
    sol_day = per_day * mean
    need = TARGET_USD / max(sol_usd, 1e-9) / TARGET_DAYS
    return {"entries_day": per_day, "mean": mean, "sol_day": sol_day, "usd_day": sol_day * sol_usd, "need_sol_day": need,
            "need_mean": need / per_day if per_day else None, "size": row["cell"]["size"]}


def write(path, rec, labels, pins, roster, tally, ladder, pairs, fills, post, bank_rows, sol_usd, round_no, scored_this_round, now, loop_note=""):
    gap = sensor_gap(rec, labels, now)
    factor, why = limiting(gap, tally, ladder, pairs)
    fit_m, held_m, fit_days, held = S.split(labels)
    L = [f"# The academy · {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))} · round {round_no} · {len(rec['mint'])} launches · fit {fit_days[0]}..{fit_days[-1]} · held-out {held}", ""]
    L += [f"**Limiting factor: {factor}.** {why}", ""]
    if loop_note:
        L += [loop_note, ""]
    proj = projection(tally.get("best_held"), gap, sol_usd)
    L += ["## The target in the tape's units", ""]
    L += [f"- target: ${TARGET_USD:,} in {TARGET_DAYS} days = {TARGET_USD / max(sol_usd, 1e-9):.0f} SOL at ${sol_usd:.2f} = {TARGET_USD / max(sol_usd, 1e-9) / TARGET_DAYS:.1f} SOL a day"]
    if proj:
        L += [f"- best held-out cell `{tally['best_held']['id']}` ({tally['best_held']['describe']}): {proj['entries_day']:.0f} entries a day at {proj['size']} SOL, "
              f"answered mean {proj['mean']:+.4f} SOL a trade → {proj['sol_day']:+.1f} SOL a day (${proj['usd_day']:+,.0f})",
              f"- the target needs {proj['need_mean']:+.4f} SOL a trade at that rate, {abs(proj['need_mean'] / proj['size']):.1%} of size net of a 3.5 % fee floor"]
    L += [""]
    L += ["## The record (pinned)", "", "| day | launches | bytes | sha256 | built |", "|---|---|---|---|---|"]
    L += [f"| {p['day']} | {p['launches']} | {p['bytes']:,} | {p['sha256'][:16]}… | {p['built']} |" for p in pins]
    L += [f"", f"Today: {gap['hours_with_tape']} of {gap['elapsed_h']} hours with tape; missing {gap['missing'] or 'none'}; last launch {gap['since_last_launch_s'] / 60:.0f} min ago.", ""]
    L += ["## The search", ""]
    L += [f"- cells scored this round: {scored_this_round}; on the roster: {tally['cells']}; positive on the fit period (n ≥ {RU.FIT_N}): {tally['fit_pos']}; "
          f"of those positive on the held-out day (n ≥ {RU.HELD_N}): {tally['held_pos']}; eligible (held-out lower bound > 0 and answered > 0): {tally['eligible']}; "
          f"expected to pass by luck: {tally['expected_by_luck']}", ""]
    ranked = sorted(roster.values(), key=lambda r: -(r["held"]["mean"] if r["held"]["n"] >= RU.HELD_N else -9))[:15]
    L += ["Top cells by the held-out day (the figure that counts), fit beside it:", "",
          "| id | cell | fit n | fit mean | fit PF | held n | held mean | held LB | answered | eligible |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in ranked:
        L.append(f"| {r['id']} | {r['describe'][:70]} | {r['fit']['n']} | {fmt(r['fit']['mean'])} | {fmt(r['fit']['pf'], '.2f')} | {r['held']['n']} | "
                 f"{fmt(r['held']['mean'])} | {fmt(r['held_lb'])} | {fmt(r['answered'])} | {'YES' if r['eligible'] else 'no: ' + '; '.join(r['not_eligible_why'][:2])} |")
    ctrl = roster.get(CE.make(CE.CONTROL["name"])["id"])
    if ctrl:
        L += ["", f"The control (RI-04 at the first mark, measured fees): fit {ctrl['fit']['n']} at {fmt(ctrl['fit']['mean'])} SOL, held-out {ctrl['held']['n']} at {fmt(ctrl['held']['mean'])} SOL."]
    L += ["", "## The answer term (what the launcher does to our fill, per family)", "",
          "| family | launches | prior slip (next mark after the exit) | prior p(dump) | our fills | posterior slip | posterior p |", "|---|---|---|---|---|---|---|"]
    fam_n = np.bincount(rec["fam"].astype(int), minlength=len(R.FAMILIES))
    for i, name in enumerate(R.FAMILIES):
        p = post.get(name, {})
        L.append(f"| {name} | {fam_n[i]} | {fmt(p.get('prior_slip'))} | {fmt(p.get('prior_p'), '.2f')} | {p.get('own', 0)} | {fmt(p.get('slip'))} | {fmt(p.get('p'), '.2f')} |")
    L += ["", "## The real legs and the residual (every leg a point)", ""]
    if pairs:
        L += ["| when | mint | cell | size | real SOL | predicted | residual (of size) | exit real / predicted | note |", "|---|---|---|---|---|---|---|---|---|"]
        for p in pairs:
            L.append(f"| {p['ts'][5:16]} | {p['mint'][:8]} | {p['cell']} | {p['size']} | {fmt(p['real'], '+.5f')} | {fmt(p['pred'], '+.5f')} | "
                     f"{fmt((p['resid'] / p['size']) if p.get('resid') is not None else None, '+.3f')} | {p.get('exit') or ''} / {p.get('pred_exit') or ''} | {p.get('why') or ''} |")
        res = RS.summary(pairs)
        L += ["", f"Residual over {res['n']} scored legs: mean {fmt(res['mean_pts'], '+.3f')} of size, mean absolute {fmt(res['abs_pts'], '.3f')}, "
              f"tolerance {RS.TOL}: {'inside' if res['within'] else 'outside' if res['within'] is not None else 'n/a'}; real {fmt(res.get('real_sum'), '+.5f')} vs predicted {fmt(res.get('pred_sum'), '+.5f')} SOL."]
    else:
        L += ["No real legs on file."]
    L += ["", "## The ladder", "", f"Rungs {RU.RUNGS} SOL. Rung 0 by ruling only; climb on {RU.GROUP} legs inside the tolerance with a positive mean; killed when the UCB of the real net is below zero.", ""]
    if ladder:
        for cid, s in ladder.items():
            L.append(f"- `{cid}` rung {s['rung']} ({RU.RUNGS[s['rung']]} SOL) · {s['status']} · by {s.get('promoted_by')} · {len(s.get('legs', []))} legs at this rung · {s.get('note', '')}")
            L += [f"  - {h['what']}" for h in s.get("history", [])]
    else:
        L.append("Empty: no cell has a rung. The eligible list above is the queue for a ruling.")
    L += ["", "## The bank (fills only; the wallet's mark is never scored)", ""]
    if bank_rows:
        L += ["| day | legs | SOL | USD | cumulative SOL | per unit deposited |", "|---|---|---|---|---|---|"]
        L += [f"| {b['day']} | {b['legs']} | {b['sol']:+.5f} | {b['usd']:+.2f} | {b['cum_sol']:+.5f} | {b['per_unit']:+.3%} |" for b in bank_rows]
    else:
        L.append("No fills.")
    text = "\n".join(L)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return text, factor, why
