# The seven rules applied to RI-04 and RI-05 · 2026-10-31, morning

The daily operating checklist (`docs/CHECKLIST.md`) run on both contracts at the operator's word ("apply both of these": the seven
rules and the three questions). Ruled `decisions/2026-10-31-review-vps-tape-link`. The numbers are the academy's pages at 05:52Z
and after the morning's rounds (`out/academy.md` round 11, `out/academy-vps.md` round 2), the tape comparison for the full held-out
day 10-30 (`out/tape_compare.md`, 06:22Z) and the live VPS read over ssh at 06:13Z.

## What the morning found

| what | number |
|---|---|
| home tape, 10-30 | 6 of 24 UTC hours (18–23Z), 3,125 launches |
| home tape, 10-31 to 06:24Z | 2 of 7 hours, 128 launches; blind from 23:2xZ to about 05:45Z with the heartbeat alive |
| guard restarts of the blind engine | 4 (05:00Z to 05:45Z, every 15 min), none logged a launch; the VPS logged 282 launches in hour 05Z |
| VPS tape, 10-30 | 24 of 24 hours, 12,259 launches; first mark p50 1.20 s (home 1.60), p90 2.0 (home 3.2); 1.26x the home count over the 6 common hours |
| VPS tape, 10-31 to 06:22Z | 7 of 7 hours, 2,048 launches; heartbeat alive, host up 76 days |
| the academy's copy of the VPS tape | stale since 10-30 18:31Z: the hourly pull returned rc 127 every tick |
| why | `ops/academy.py` ran a bare `bash`; CreateProcess searches System32 before PATH and finds WSL's bash, which cannot open the repo's Windows path, and whose scp waits on a host-key prompt (560 s when reproduced) |
| academy loops running | 2 (pids 20512, 22248, started 7 s apart by the task at 19:00 Central 10-30); `PermissionError` on roster.json in the log |
| home round gate | "grew by -14596 launches since round 10": 10-26 left the four-day window; no round could fire until 14,646 new launches |
| cells eligible for rung 0, either tape | 0 |
| real legs on file | 5 at 0.01 SOL (10-28): -0.00168 SOL real vs -0.00186 predicted, residual inside tolerance |

Fixed by 06:35Z on branch `review-2026-10-31` (tests in `tests/test_academy.py`; the suite is 66 passed and one failure, a live
Dex lookup untouched today):

- `ops/academy.py`: the pull runs through Git's bash by its own path with stdin closed (`bash_exe`); a non-zero rc carries the last
  line of the script's output so the page says why; `--pull` forces a pull on a tick, which is how the fix was tested from PowerShell,
  the task's environment; `due()` fires a round when the record shrank (a day left the window is a new fit period); `single_instance`
  holds `monitor/academy.lock` for the life of the loop and a second loop exits.
- `ops/vps_pull.sh`: `/usr/bin` on PATH (a non-login Git bash started from Windows has no mkdir, scp or date), BatchMode so a prompt
  fails at once, a failed copy prints its rc.
- `ops/academy.ps1`: does not start a loop while one is running, heartbeat or not.
- The VPS tape pulled by hand and scored: round 2 on 26,677 launches. The home round fired with the gate fixed: round 11 on 19,199.

## Rule by rule

| rule | RI-04 (the Duval loop, counted, KILL since 10-23) | RI-05 (the 5 % as code, replay only) |
|---|---|---|
| 1 Attack the limiting factor | The sensor, and today its link: the VPS had 24 of 24 hours and the page that grades them read none of it for 12 hours. The academy's own loop ran twice and its gate stalled. All three fixed; nothing else touched | Same stage: its cells sit on the same roster and the same tape |
| 2 Reality is the only grader | Unchanged: -0.00168 SOL over five real legs at the first-mark fill, fee floor 3.52 %. Today reality graded the plumbing: a heartbeat is not a feed (four restarts, zero launches), a `rc=127` line is not a pull, and a "round" on a 6-hour day is not a day | Graded on the same tape at the same fill; no cell of its family is positive on fit |
| 3 Bits per day | The VPS produced 12,259 launches on 10-30; the academy counted 3,118. After the pull the VPS round scored 421 cells on 26,677 launches, the first full held-out day the academy has had. The 10-31 market forecasts (150–850 matched launches) were written against a full day the home tape will not deliver | Same bits; its entries are a filter on them |
| 4 Parallel forks from one context | 67 cells on the VPS roster, 421 scored this round: 0 positive on the fit period (n ≥ 100), so 0.0 would pass the held-out bound by luck. Best held-out cell delay=10 at -0.0244 on 34, answered -0.0562 | Its forks (narrative class, L2) are on the roster and negative |
| 5 Promote on a held-out bench | No candidate on either tape. The bench itself got its day: 10-30 is the full held-out day the cut-over rule asked for, and the VPS beats the home tape on every graded axis. That ruling is the operator's (option B) | No candidate |
| 6 One rung at a time | Nothing changed in the contract, the constants, the cells or the fills. Three plumbing changes, each with a test, none a rule | Nothing changed |
| 7 The human keeps the objective, the machine the discipline | The ladder is empty and stays empty; option D (legs on the best cell) refused by the unchanged eligibility gate; option C (stop the home engine) vetoed by rule 5. The merge, the loop restart and the cut-over are the operator's; a stop of the duplicate loop was refused to this session | Nothing counted; nothing to keep |

## The three questions

1. **The one thing limiting us:** the sensor, and today the defect is the link, not the engine. The VPS logged every hour of 10-30
   and 10-31 and the academy read none of it from 10-30 18:31Z to 10-31 06:17Z because a bare `bash` resolved to WSL's. Underneath,
   the academy's own loop ran twice and its round gate stalled at a negative number. Fixing those three is the whole of today's
   reversible work. The edge is the stage below: on the first full day of tape, 0 of 421 cells are positive on fit.
2. **What reality rewards as opposed to the dashboard:** SOL net of the attainable fill, and the only real grade is -0.00168 SOL
   over five legs. The dashboard graded hours, rounds, cells scored and a heartbeat; every one of them read green or fixable while 24
   hours of bits sat unread on the VPS and the home guard restarted a blind engine four times without buying a launch. A full day of
   tape moved the limiting factor from SENSOR to SEARCH and moved the edge nowhere: the target needs +0.128 SOL a trade on a tape whose
   best cell is -0.056.
3. **The smallest sequence of bets:** 0 (done, free): the link fixed and tested from the task's environment, the loop single-instance,
   the gate unable to stall, the VPS tape scored. Its grade: tomorrow's VPS page shows 11-01 with at least 22 of 24 hours and every
   `vps pull rc=` line in `monitor/academy.log` is 0. 1 (free, operator, minutes): merge the branch, stop the duplicate loop, let the
   guard restart one loop on the new code. 2 (free, operator's ruling): the cut-over of the counted tape to the VPS, whose held-out day
   is now on file; before any rung from there the fill residual is re-measured from the VPS. 3 (free): two more held-out VPS days;
   a cell eligible on consecutive days is the claim worth a ruling. 4 (0.12 SOL, gated on 3): 12 legs at 0.01 SOL on the ruled cell.
   Nothing sizes up before reality has graded the bet before it.

## Owed to the Foresight Journal

The chained forecast files cannot be appended from a worktree without forking the chain, so the forecast on this leg is written from
the main checkout after the merge:

```
python ops/journal.py predict --claim "Every 'vps pull rc=' line written to monitor/academy.log on 2026-11-01 (UTC) reads rc=0 and out/academy-vps.md at 23:30Z shows at least 22 of 24 hours of 11-01 tape" --metric manual --direction ge --threshold 1 --confidence 0.8 --deadline 2026-11-02 --rests-on none --basis "the fix tested from PowerShell at 06:35Z 10-31 pulled 10-30 and 10-31 in 11 s with rc 0; the VPS has logged 24 of 24 hours on 10-29 and 10-30; the risk is the task environment differing from the test, which the rc line would show"
```

## What changed today under the ruling

- `ops/academy.py`: `bash_exe`, `pull_vps(force)`, `due`, `single_instance`, `--pull`; the pull's failure reason on the page.
- `ops/vps_pull.sh`: PATH, BatchMode, the rc of a failed copy.
- `ops/academy.ps1`: no second loop.
- `tests/test_academy.py`: the gate fires when the window slides; a second loop is refused the lock.
- `out/tape_compare.md` for 2026-10-30 (the full held-out day), `out/academy-vps.md` round 2, `out/academy.md` round 11.
- RI-04's contract, constants and KILL verdict are untouched. RI-05 untouched. No leg placed, no capital moves.
