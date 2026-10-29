# The seven rules applied to RI-04 and RI-05 · 2026-10-29, morning

The daily operating checklist (`docs/CHECKLIST.md`) run on both contracts the morning after the machine crashed twice. Ruled
`decisions/2026-10-29-checklist-tape-outage` (USABLE). The numbers are the population at the first-mark fill over 10-26..10-28
(`out/population.md`, 05:45Z), RI-05's replay over 10-24..10-28 (`out/five.md`), the readout at 05:47Z and the fill probe of 10-28
(`out/probe.md`).

## What the morning found

| what | number |
|---|---|
| hard crashes of the machine (kernel-power 41, reboot without clean shutdown) | 3 in 6 days: 10-24 09:19, 10-28 09:59, 10-28 19:44 Central |
| tape dark (no launch logged) | 16:43Z 10-28 to 05:47Z 10-29, 13.1 h |
| engine alive but blind (name resolution dead, 2,792 errors an hour) | 16:43Z to 19:44 Central 10-28, 7.3 h, heartbeat looked alive |
| UTC hours of 10-28 with tape | 17 of 24 (the lesson rule since 10-09 voids a market day under 20 h) |
| files NUL-filled by the crashes | monitor/heartbeat.json, state/shadow.json (4.3 MB), state/excursion.json (1.2 MB) |
| NUL or torn lines in journals | 10 across 7 files (shadow, shadow_paths, excursions, launches x2, paths 10-24, 10-26 x4, 10-27 x3, 10-28) |
| journal ticks failed on the damage | 286 (shadow and resolve each), readout crashed |
| guard task | ran 00:44:52 Central, result 0, did not start the engine; the script by hand at 00:47:06 did |

Repaired by 05:50Z: the three NUL files moved aside (`.nul-20261028`), the ten lines quarantined to `journal/corrupt-20261028.jsonl`
with file, line and byte count, the engine restarted (pid 26160, 11 launches tracked by 05:50Z, no feed errors since), the journal
ticking clean, the readout running. `src/common.py` loaders now read a NUL-filled file as missing and skip an unparseable line, each
logged to `monitor/journal-errors.log` (tests in `tests/test_common.py`); the running engine takes the change at its next restart.

## Rule by rule

| rule | RI-04 (the Duval loop, counted, KILL since 10-23) | RI-05 (the 5 % as code, replay only) |
|---|---|---|
| 1 Attack the limiting factor | Today the environment: the tape. 13 h dark, 7 h blind, 17 of 24 h on 10-28. The edge finding of 10-28 (every book negative at the attainable fill) stands and cannot advance without tape | Same stage. Its verdict needs held-out days and it has one partial one (10-28 to 16:43Z: -0.0324 on 44) |
| 2 Reality is the only grader | Settled on 10-28 by five real buys: the first-mark grader is reality's within 2.5 points, fee floor 3.52 %. Today reality graded the environment instead: a heartbeat is not a feed, a machine is not a host | Unchanged: graded at the first-mark fill, -0.0275 on 261 over five days (PF 0.35); only 10-28 on counts |
| 3 Bits per day | 50,588 launches scored over 10-26..10-28; 613 control entries; zero bits from 16:43Z to 05:47Z. The 10-29 touches forecast (420-900) lost 5.8 h of its day | 44 trades on its one held-out day; nothing since 16:43Z |
| 4 Parallel forks from one context | 25 forks on one feed, all negative over three days: best take +10 % at -0.0187 (PF 0.75). Six forks were positive on 10-28, none on the other two days | Its four rules run as forks; L2 narrative class is the least bad at -0.0247 (PF 0.68) |
| 5 Promote on a held-out bench | No candidate: the bench needs three positive days beating the control, and 10-28 is the only positive day any fork has had. One green day on the counted book (+4.4 SOL over 110 closes, the first) is a draw at a book -47.9 SOL deep | One held-out day, negative; no verdict |
| 6 One rung at a time | Nothing changed in the contract, the constants or the engine's rules today. The loader change is measurement, not a rule, and the engine takes it only at a restart | Nothing changed |
| 7 The human keeps the objective, the machine the discipline | The machine did not come back bigger after the green day: no gate moved, no capital moved, option D (buy a bit on the edge now) refused by the unchanged gate. The host is the operator's: the machine crashes three times in six days and the guard did not fire | Nothing counted; nothing to keep |

## The three questions

1. **The one thing limiting us:** the environment. The machine delivered 17 of 24 hours of tape on 10-28 and none of the first
   5.8 on 10-29; three hard crashes in six days; the damage they leave stopped the journal for 286 ticks. The edge is still the
   stage underneath (best of 25 forks -0.0187 SOL a trade over three days), but no bit on the edge can be bought while the tape is
   intermittent, because the bench needs three clean held-out days.
2. **What reality rewards as opposed to the tape:** uptime. The fill question closed on 10-28 (landed within 2.5 points of the
   first mark). What parted today is the heartbeat and the feed: for 7.3 hours the engine reported alive and logged nothing, and
   the guard trusts the heartbeat. Reality counts launches, not heartbeats.
3. **The smallest sequence of bets:** 0 (done, free): tape restored, damage quarantined, loaders self-healing. 1 (free, operator):
   a feed-aware heartbeat so a blind engine is restarted within ten minutes; needs one engine restart. 2 (free in SOL, a day of the
   operator): the engine on the VPS that already runs the Polymarket capture, so the tape stops depending on a machine that crashes.
   3 (free): three clean held-out days of the population and RI-05. 4 (gated on a fork positive on all three): 40 real closes at
   0.1 SOL. Nothing sizes up before reality has graded the bet before it.

## What changed today under the ruling

- `src/common.py`: `load_json` reads a NUL-filled or empty file as missing; `read_jsonl` skips NUL and torn lines; both log once per
  file to `monitor/journal-errors.log`. A malformed but non-empty JSON file still raises. Tests in `tests/test_common.py`.
- `journal/corrupt-20261028.jsonl`: the ten removed lines, by file, line and byte count. The NUL state files are kept as `.nul-20261028`.
- Four 10-28 market forecasts resolved true (Brier 0.04 each); 0 lessons owed; the 10-29 forecasts stand and resolve against the
  tape the machine delivered.
- RI-04's contract, constants and KILL verdict are untouched. No capital moves. Options B (feed-aware heartbeat) and C (the VPS) are
  the operator's.
