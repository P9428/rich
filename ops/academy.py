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


def bash_exe():
    """Git's bash by its own path. A bare 'bash' goes through CreateProcess, which searches System32 before PATH, and System32 holds
    WSL's bash: it cannot open the repo's Windows path (rc 127, every pull from 10-30 18:31Z to 10-31 06:17Z), and its own scp waits
    on a host-key prompt nobody answers (a ten-minute hang a tick) while the VPS logged a full day the home tape missed."""
    if os.name != "nt":
        return "bash"
    for p in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if os.path.exists(p):
            return p
    return "bash"


def pull_vps(force=False):
    """Today's VPS tape, re-pulled when the local copy is older than PULL_EVERY (read-only scp; ops/vps_pull.sh). The script is named
    relative to ROOT and run by Git's bash with stdin closed, so a prompt fails at once; a non-zero rc carries the last output line."""
    today = os.path.join(TAPES["vps"]["paths"], time.strftime("%Y-%m-%d", time.gmtime()) + ".jsonl")
    if not force and os.path.exists(today) and time.time() - os.path.getmtime(today) < PULL_EVERY:
        return "vps tape fresh"
    try:
        r = subprocess.run([bash_exe(), "ops/vps_pull.sh"], cwd=ROOT, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        lines = ((r.stderr or "") + "\n" + (r.stdout or "")).strip().splitlines()
        bad = [x for x in lines if "no paths for" in x or "rc " in x or "Warning" in x or "failed" in x]
        tail = (bad or lines)[-1:] if (r.returncode or bad) else []
        return f"vps pull rc={r.returncode}" + (f" ({tail[0][:120]})" if tail else "")
    except Exception as e:
        return f"vps pull failed {e!r}"


def due(n, state, roster, force=False):
    """Whether a search round is due: forced, an empty roster, or the record grown by PACE launches since the last round. A record
    that shrank (a day fell out of the --days window, so the fit period is a new contract) counts as grown by its whole length;
    without this the home tape read 'grew by -14596' on 10-31 and no round could fire until 14,646 new launches."""
    grown = n - int(state.get("launches_at_round", 0))
    if grown < 0:
        grown = n
    return bool(force or not roster or grown >= S.PACE), grown


_LOCK = None


def single_instance(lock_file):
    """Holds an OS lock on lock_file for the life of the process; None when another process holds it. The lock dies with the process,
    so a crash leaves nothing stale. Two loops started 7 s apart by the guard on 10-30 tore roster.json between them for a day."""
    global _LOCK
    f = open(lock_file, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            if f.tell() == 0:
                f.write("academy loop lock\n"); f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    _LOCK = f
    return f


def log(line):
    msg = f"{C.iso()} {line}"
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def tick(days, force_round=False, seed=None, tape="home", pull=False):
    t0 = time.time()
    F = files_of(tape)
    pulled = pull_vps(force=pull) if tape == "vps" else ""
    R.RDIR = F["record"]
    rec, pins, labels = R.load(days, F["paths"])
    if rec is None or len(set(labels)) < 2:
        log(f"[{tape}] not enough days of tape for a fit and a held-out period ({pulled})"); return None
    state = C.load_json(F["state"], {"round": 0, "launches_at_round": 0})
    roster = C.load_json(F["roster"], {})
    ladder = C.load_json(F["ladder"], {})
    fills = AN.own_fills(rec)
    n = int(len(rec["mint"]))
    fire, grown = due(n, state, roster, force_round)
    scored = 0
    if fire:
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
    ap.add_argument("--pull", action="store_true", help="re-pull the VPS tape this tick even if the local copy is fresh")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.loop and single_instance(C.path("monitor", "academy.lock")) is None:
        log("another academy loop holds monitor/academy.lock; this one exits (two loops tore the state files on 10-30/31)")
        return
    while True:
        for tape in (("home", "vps") if a.tape == "both" else (a.tape,)):
            try:
                tick(a.days, force_round=a.round, seed=a.seed, tape=tape, pull=a.pull)
            except Exception as e:
                log(f"[{tape}] tick error {e!r}\n{traceback.format_exc()[-1500:]}")
        if not a.loop:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
