# The seven rules applied to RI-04 and RI-05 · 2026-10-28, evening

The daily operating checklist (`docs/CHECKLIST.md`) run on both contracts on the same tape, after the morning's ruling that every
replay had been grading at a fill the counted book does not get (`decisions/2026-10-28-ri04-fill-grader`). Ruled
`decisions/2026-10-28-checklist-both-contracts`. The numbers are the population at the first-mark fill over 10-26..10-28
(`out/population.md`) and RI-05's replay over 10-25..10-28 (`out/five.md`).

## Rule by rule

| rule | RI-04 (the Duval loop, counted, KILL since 10-23) | RI-05 (the 5 % as code, replay only) |
|---|---|---|
| 1 Attack the limiting factor | The grader was the binding stage this morning and is fixed. Now the edge: control -0.050 SOL a trade on 499 (PF 0.43), all 21 forks negative, the least bad -0.034. Nothing in the exits, holds or sizes changes the sign of a negative entry | Same stage. Whole, -0.025 on 171 (PF 0.31). Its four rules forked one at a time onto RI-04's control all lose: L1 meta gate -0.049, L2 narrative class -0.042, L4 free trade -0.056, L5b slow exit -0.051 |
| 2 Reality is the only grader | Graded at the chain read it fills at; the replay agrees with the counted book (-0.045 on 1157). Still unmeasured: the slot a signed tx lands in and its tip. That fill can only be worse than the first mark, so it cannot turn the book positive | Breached: every constant was measured on the tape of 10-23..27 and the verdict reads 10-25..28, three of four days the tuning tape. Only 10-28 is held out: -0.025 on 15 trades, no verdict |
| 3 Bits per day | 40,613 launches scored in three days; the news match leaves 499 entries, and matched launches lose more than unmatched (-0.050 vs -0.035, interval below zero). The match is the one entry signal and it costs | 171 entries over four days; the meta gate read "live" at 457 of 499 control entries, so it filters almost nothing on this tape |
| 4 Parallel forks from one context | 21 forks on one feed, now 25 with RI-05's rules, all marked on the same tape at the same fill | Was scored by its own script on its own window (4 days against the population's 3). Its rules are now also forks in the population; `ops/five_replay.py` keeps the whole loop |
| 5 Promote on a held-out bench | The rule as written would have made a losing fork a candidate (ten forks "beat" the losing control two of three days). A candidate must now also be positive on each of those days | Its bench was not held out (rule 2). Judged from 10-28 on; nothing before counts |
| 6 One rung at a time | One changed variable per fork, kept | RI-05 changes ten rules at once against RI-04; as a contract it skips rungs. As a hypothesis scorer that is fine; as a candidate it cannot be, so its rules go up one at a time through the population |
| 7 The human keeps the objective, the machine the discipline | The contract said the count runs to 200 closes; it has run 1157. The engine is also the tape, so capping the count without stopping the paths needs a code change and a restart, which has crashed before. The operator's call, written as option C | Nothing counted; nothing to keep |

## The three questions

1. **The one thing limiting us:** the edge at the attainable fill. No entry rule tested in either contract, whole or forked, is
   positive on the tape; every exit fork of a negative entry is negative. The number: the best of 25 forks is -0.034 SOL a trade.
2. **What reality rewards as opposed to the tape:** the fill a signed transaction lands at, one to three slots after the chain read,
   plus its tip. The first mark is the nearest proxy and both books lose there, so the real fill can only make them lose more. The
   tape and reality do not part in a way that could rescue either book.
3. **The smallest sequence of bets:** 0 (done, free): RI-05's rules as single forks, bench requires positive. 1 (free): forward days
   of the same population; a fork becomes a candidate only positive and beating the control three held-out days running. 2 (about
   0.3 SOL, gated on 1): 20 real 0.01 SOL buys to measure the landed fill, only once a fork is positive at the first mark. 3 (gated
   on 2): 40 real closes at 0.1 SOL. Nothing sizes up before reality has graded the bet before it.

## What changed today under the ruling

- `ops/population.py`: RI-05's L1, L2, L4 and L5b as one-variable forks on the control; a candidate must be positive as well as beat
  the control; the hypothesis line keys off the control's name. Tests in `tests/test_population.py` (8 pass).
- RI-05's verdict is read only on days after 10-27. `ops/five_replay.py` is unchanged; its by-day table carries the held-out days.
- Step 1 real buys are deferred behind the gate `rich-fork-positive-at-first-mark`. Capping RI-04's count (option C) is the operator's.
- RI-04's contract, constants and KILL verdict are untouched. No capital moves.
