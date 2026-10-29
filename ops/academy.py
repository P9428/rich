"""The academy's loop: the trader in the bedroom. Every tick it pins the record (today's path file grows all day), runs a search round
when the record has grown enough, pairs every real leg with the arena, folds the legs into the ladder, counts the bank and rewrites
the review. Observation only: nothing here places an order, and nothing here changes a contract.

  python ops/academy.py                 one tick
  python ops/academy.py --loop          forever, every --every seconds (default 900), heartbeat in monitor/academy.json
  python ops/academy.py --days 4        the record window: the last day is the held-out day, the rest the fit period
  python ops/academy.py --tape vps      the VPS engine's tape (journal/vps/paths, pulled by ops/vps_pull.sh when older than an hour);
                                        its own roster, ladder and page (state/academy/vps/, out/academy-vps.md). The VPS copy is
                                        uncounted until the cut-over ruling; searching it is observation, and a cell found there is
                                        still only a candidate for a ruling. --tape both runs home then vps each tick.

State: state/academy/roster.json (every cell's figures), ladder.json, state.json (round, launches at the last round).
Out:   out/academy.md, monitor/academy.log
"""
import argparse
import os
import subprocess
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C                                   # noqa: E402
from academy import answer as AN, arena as A, bank as B, record as R, residual as RS, review as RV, rungs as RU, search as S   # noqa: E402

LOG = C.path("monitor", "academy.log")
HEART = C.path("monitor", "academy.json")
TAPES = {"home": {"paths": os.path.join(ROOT, "journal", "paths"), "state": ("state", "academy"), "out": "academy.md"},
         "vps": {"paths": os.path.join(ROOT, "journal", "vps", "paths"), "state": ("state", "academy", "vps"), "out": "academy-vps.md"}}
PULL_EVERY = 3600


def files_of(tape):
    t = TAPES[tape]
    return {"roster": C.path(*t["state"], "roster.json"), "ladder": C.path(*t["state"], "ladder.json"), "state": C.path(*t["state"], "state.json"),
            "out": C.path("out", t["out"]), "paths": t["paths"], "record": C.path(*t["state"], "record")}


def pull_vps():
    """Today's VPS tape, re-pulled when the local copy is older than PULL_EVERY (read-only scp; ops/vps_pull.sh)."""
    today = os.path.join(TAPES["vps"]["paths"], time.strftime("%Y-%m-%d", time.gmtime()) + ".jsonl")
    if os.path.exists(today) and time.time() - os.path.getmtime(today) < PULL_EVERY:
        return "vps tape fresh"
    try:
        r = subprocess.run(["bash", os.path.join(ROOT, "ops", "vps_pull.sh")], cwd=ROOT, capture_output=True, text=True, timeout=600)
        return f"vps pull rc={r.returncode}"
    except Exception as e:
        return f"vps pull failed {e!r}"


def log(line):
    msg = f"{C.iso()} {line}"
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def tick(days, force_round=False, seed=None, tape="home"):
    t0 = time.time()
    F = files_of(tape)
    pulled = pull_vps() if tape == "vps" else ""
    R.RDIR = F["record"]
    rec, pins, labels = R.load(days, F["paths"])
    if rec is None or len(set(labels)) < 2:
        log(f"[{tape}] not enough days of tape for a fit and a held-out period ({pulled})"); return None
    state = C.load_json(F["state"], {"round": 0, "launches_at_round": 0})
    roster = C.load_json(F["roster"], {})
    ladder = C.load_json(F["ladder"], {})
    fills = AN.own_fills(rec)
    n = int(len(rec["mint"]))
    grown = n - state.get("launches_at_round", 0)
    scored = 0
    if force_round or not roster or grown >= S.PACE:
        state["round"] = state.get("round", 0) + 1
        roster, scored = S.run_round(rec, labels, roster, state["round"], fills, seed=seed)
        roster = S.trim(roster)
        state["launches_at_round"] = n
        note = f"round {state['round']}: {scored} cells scored on {n} launches ({grown} new since the last round)"
    else:
        note = f"no round: the record grew by {grown} launches since round {state['round']}, the pace is {S.PACE}; legs, ladder and bank refreshed"
    tally = S.tally(roster)
    pairs = RS.pair(rec, fills, roster)
    for cid in list(ladder):
        ladder = RU.update(ladder, cid, [p for p in pairs if p["cell"] == cid])
        row = roster.get(cid)
        if row is not None and not row.get("eligible") and ladder[cid]["status"] == "rung":
            ladder = RU.retire(ladder, cid, "no longer eligible on the arena: " + "; ".join(row["not_eligible_why"][:2]))
    ctrl_row = tally["best_held"] or next(iter(roster.values()))
    post = AN.posterior(AN.prior(rec, A.score(rec, ctrl_row["cell"])), fills)
    su = B.sol_usd()
    bank_rows = B.ledger(fills, su)
    note = f"[{tape} tape] {note}" + (f"; {pulled}" if pulled else "")
    text, factor, why = RV.write(F["out"], rec, labels, pins, roster, tally, ladder, pairs, fills, post, bank_rows, su, state["round"], scored, time.time(), note)
    C.save_json(F["roster"], roster); C.save_json(F["ladder"], ladder); C.save_json(F["state"], state)
    log(f"{note}; limiting factor {factor}; {len(fills)} real legs; {time.time() - t0:.0f} s")
    hb = C.load_json(HEART, {}) if os.path.exists(HEART) else {}
    hb.update({"pid": os.getpid(), "ts": C.iso(), tape: {"round": state["round"], "launches": n, "cells": tally["cells"], "eligible": tally["eligible"],
                                                         "factor": factor, "legs": len(fills), "tick_s": round(time.time() - t0)}})
    C.save_json(HEART, hb)
    return factor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--every", type=int, default=900)
    ap.add_argument("--round", action="store_true", help="force a search round this tick")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--tape", choices=("home", "vps", "both"), default="both")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    while True:
        for tape in (("home", "vps") if a.tape == "both" else (a.tape,)):
            try:
                tick(a.days, force_round=a.round, seed=a.seed, tape=tape)
            except Exception as e:
                log(f"[{tape}] tick error {e!r}\n{traceback.format_exc()[-1500:]}")
        if not a.loop:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
