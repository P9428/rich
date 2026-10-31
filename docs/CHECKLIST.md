# The daily operating checklist

Seven rules (from Musk, Noam Brown and the Dwarkesh panel, 2026-10-27) and the three questions added 2026-10-28. The morning
`/rich` command runs them after the readout, before anything is proposed. A review that does not name one binding stage is not a
review.

1. **Attack the limiting factor, nothing else.** Musk says it a hundred times. Brown says RSI is bottlenecked by experiments, not
   intelligence. The panel says progress stalls wherever the model is weakest. Rule: every review names the one binding stage and
   works only there.
2. **Reality is the only grader.** Musk: physics is law, RL against reality. Brown: honest evaluation or the grader gets hacked. The
   panel: the judge gets reward-hacked, sim-to-real is the gap. Rule: marks come from the chain, fills pay their own impact, and no
   rule is ever tuned on the book that judges it.
3. **Bits per day is the currency.** The panel: RL learns one bit per episode, and the frontier's signal does not exist in the data
   lying around, you must build the environment. Brown: 130 billion tokens in 88 hours. Rule: 40 closes is 40 bits. The launch stream
   is 29,000 launches a day. Score all of them.
4. **Parallel agents, fork from one context, spin down the losers.** Brown's 10,000 agents and forked context. Musk's 10,000 Optimus
   doing self-play in an academy. The panel's millions of instances. Rule: one feed, a population of paper books, each a one-variable
   fork of the contract, all marked against the same tape.
5. **Promote only on a held-out bench, else discard.** The panel's Cursor rule: redeploy every five hours if it beats the bench, throw
   it away if not. Musk's weekly review plotting points to see if they converge. Rule: a variant becomes a candidate only after beating
   the control on consecutive forward days.
6. **Climb one rung at a time.** The panel: fifth-grade to college math gave no signal, successive rungs did. Musk: build a little fab
   first, ride the S-curve. Rule: one changed variable per contract.
7. **The human keeps the objective; the machine keeps the discipline.** The panel: alignment's last job is specifying what we want.
   Musk: hire for traits, add domain knowledge. Brown: agents are exceptional and jagged. Rule: the paragraph and the gates are the
   operator's; the machine's edge over Jack is that it never sizes up, never averages down, never comes back bigger after a red day.

## The three questions (answered every morning, in writing, before any proposal)

1. **What is the one thing limiting us right now?** One stage, named, with the number that shows it binds. Rate, edge, exits, count,
   grader, or environment. If the answer is "several", the review is not finished.
2. **What does reality actually reward, as opposed to the tape or the backtest?** Say where the tape and reality part: the fill a
   transaction lands at, the slot it lands in, the fees and tips it pays, the dumps between two marks. Any book graded only on the tape
   is a hypothesis.
3. **What is the smallest sequence of bets that lets reality grade early and cheaply?** Ordered, each with its cost in SOL and the bit
   it buys. The first bet is usually free (a replay at the honest fill). The first real bet measures the fill, not the edge. No bet is
   sized up until reality has graded the one before it.

## Record

| day | Q1 the one thing | Q2 reality vs tape | Q3 the sequence |
|---|---|---|---|
| 2026-10-28 | the grader: every replay filled at the message's reserves, the counted book at the chain read; fixed (decisions/2026-10-28-ri04-fill-grader). Step 0 done 04:35Z: all 21 forks scored at the first-mark fill over 10-26..10-28 (498 control entries, mean -0.050 SOL, PF 0.43, agreeing with the counted book's -0.045); no fork is positive, the best is entry +10 s at -0.036 and take +10 % at -0.034; news hurts (matched -0.050 vs unmatched -0.035, 90 % interval below 0). The population task had been dead since 10-25 on a torn path line; reader made tolerant | the fill a signed tx lands at, 1-3 slots after the read; the tape's first mark (1.3 s) is the nearest proxy; 175 of 478 stops booked below -10 % because the dump came between two marks | 0: population at the first-mark fill (free). 1: 20 real 0.01 SOL buys to measure landed fill vs message vs first mark (about 0.3 SOL). 2: only if a fork is positive at the measured fill, 40 real closes at 0.1 SOL. 3: 1.5 SOL only after S1 at real fills |
| 2026-10-28 (evening, both contracts; docs/CHECKLIST-2026-10-28.md) | the edge at the attainable fill: no entry in RI-04 or RI-05 is positive, whole or forked; best of 25 forks -0.034 SOL a trade; RI-05's four rules on the control all lose (L1 -0.049, L2 -0.042, L4 -0.056, L5b -0.051); RI-05 was judged on its tuning tape, held-out day 10-28 is -0.025 on 15 | the landed slot and tip of a signed tx, which can only be worse than the first mark; both books lose there, so reality cannot rescue either | 0 done (RI-05 forks, bench requires positive). 1 free: forward held-out days. 2 DONE the same night at five buys (operator's call, -0.00168 SOL): the fill lands at the first-mark state within 2.5 points, 2-3 slots after the read; the fee floor is 3.52 % a round trip not 2.1 %; the exit lands ±12-19 points from its mark on a live curve. 3 gated on a positive fork: 40 closes at 0.1 SOL. Count cap on RI-04 is the operator's (option C) |
| 2026-10-29 (morning, both contracts; docs/CHECKLIST-2026-10-29.md) | the environment: the machine crashed twice on 10-28 (kernel-power 41 at 09:59 and 19:44 Central, three times in six days), delivered 17 of 24 h of tape, then none from 16:43Z to 05:47Z (13 h dark, 7 h of it with the engine alive but blind on dead DNS); the crash damage (3 NUL state files, 10 NUL or torn journal lines) failed the journal 286 ticks and crashed the readout; repaired 05:50Z, engine restarted, loaders made self-healing (src/common.py). The edge stands underneath: 25 forks all negative over 3 days, best take +10 % at -0.0187; 10-28 the first positive day (control +0.0188 on 154, counted book +4.4 SOL), a draw not a signal; RI-05 held-out 10-28 -0.0324 on 44 | uptime: a heartbeat is not a feed (7.3 h alive and logging nothing) and a home machine is not a host; the fill question is closed (within 2.5 points of the first mark, fee floor 3.52 %) | 0 done free: tape restored, damage quarantined, loaders self-healing. 1 free (operator, needs a restart): feed-aware heartbeat so a blind engine restarts in 10 min. 2 free in SOL (operator, a day): the engine on the VPS. 3 free: three clean held-out days. 4 gated on a fork positive all three: 40 real closes at 0.1 SOL. Ruled decisions/2026-10-29-checklist-tape-outage |
| 2026-10-31 (morning, both contracts; docs/CHECKLIST-2026-10-31.md) | the sensor's link: the VPS logged 24 of 24 h on 10-30 (12,259 launches) and 7 of 7 on 10-31 while the home tape had 6 of 24 and 2 of 7, and the academy read none of the VPS tape for 12 h (a bare `bash` resolved to WSL's: rc 127, then a hang on its scp prompt); two academy loops ran at once and tore the state files; the home round gate stalled at "grew by -14596". All three fixed on branch review-2026-10-31 with tests, the pull verified from the task's environment, the VPS tape scored (round 2, 421 cells on 26,677 launches: 0 positive on fit, 0 eligible), the home round fired (round 11). Underneath: the edge, every cell negative on the first full day of tape | SOL net of the fill: -0.00168 over five legs, unchanged. The dashboard graded hours, rounds and a heartbeat while 24 h of bits sat unread and the guard restarted a blind engine four times without a launch; a full day of tape moved the factor from SENSOR to SEARCH and the edge nowhere (target +0.128 SOL a trade, best cell -0.056) | 0 done free: link, lock, gate, VPS round. 1 free (operator, minutes): merge, stop the duplicate loop, restart. 2 free (operator's ruling): the cut-over, its held-out day now on file; re-measure the residual from the VPS first. 3 free: two more held-out VPS days. 4 gated on 3: 12 legs at 0.01 SOL. Ruled decisions/2026-10-31-review-vps-tape-link |
