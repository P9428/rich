# Decision · The seven rules of the daily operating checklist applied to RI-04 and RI-05 on the same evening, after the grader was fixed (decisions/2026-10-28-ri04-fill-grader). At the attainable fill every book loses: RI-04's control and its 21 forks, RI-05 whole, and RI-05's four rules forked one at a time onto RI-04's control. What is the one binding stage now, and what is the reversible half?

Wednesday 2026-10-28 · asked by operator 2026-10-28 (evening): apply the seven rules to both RI-04 and RI-05 · log root `6673c5a09020747364162174c3a2c0037183484bde7ff74f90698264b158f515` · size 21

## REALITY
Looked at before reasoning: out/population.md 04:35Z and the rerun with RI-05's forks (ops/population.py --fill first-mark, 10-26..10-28): control 499 entries, mean -0.050 SOL, PF 0.43; every fork negative; out/five.md 04:26Z (ops/five_replay.py --days 4): RI-05 at the first mark 171 trades, -0.025 mean, PF 0.31; by day, 10-28 is -0.025 on 15; src/five.py line 39: every constant 'measured on the tape of 2026-10-23..27 before being frozen'; the verdict window 10-25..10-28 overlaps that tape on three of four days; prereg/CONTRACT.md line 135-136: 'A verdict at 40 closes is a verdict on the loop as written; the count keeps running to 200 closes'; journal/paper.jsonl holds 1157 closes; monitor/heartbeat.json 04:41Z: the engine is alive (pid 30076, 22,326 paths written, 1 open); src/duval.py has no mode that keeps the tape without opening paper positions.
- **FACT** · RI-04's counted book is KILL since 16:56Z 10-23 (G1 at the 11th close, G2 at 20:11Z) and stands at -52.3 SOL on 1157 closes at the chain-read fill. The contract set the count to run to 200 closes for the journal's splits; it has run 957 closes past that · _USABLE_
- **FACT** · At the first-mark fill over 10-26..10-28 (40,613 launches, 499 control entries) the control is -0.050 SOL a trade, PF 0.43, and all 21 of RI-04's one-variable forks are negative; the least bad are take +10 % (-0.034, PF 0.56) and entry +10 s (-0.036, PF 0.49). The replay agrees with the counted book (-0.045 on 1157) · _USABLE_
- **FACT** · RI-05 at the first-mark fill is -0.025 SOL a trade on 171, PF 0.31 (10-25..10-28). Its constants were measured on the tape of 10-23..10-27 and frozen; three of its four verdict days are that tape. The one held-out day, 10-28, is -0.025 on 15 trades · _USABLE_
- **FACT** · RI-05's four rules forked one at a time onto RI-04's control at the same fill all lose: L1 the meta gate -0.049 on 457 (the gate read 'live' at 457 of 499 control entries, so it barely discriminates); L2 narrative class only -0.042 on 376; L4 the free trade -0.056 on 499 (PF 0.37: the remainder that rides gives back the take); L5b arrivals-slow exit -0.051 on 499 · _USABLE_
- **FACT** · Matched launches do worse than unmatched at the attainable fill: -0.050 vs -0.035 SOL, the 90 % bootstrap interval on the difference below zero. The headline match, the loop's one named entry signal, costs money on this tape · _USABLE_
- **FACT** · The promotion rule as written (beat the control on three consecutive days with 50 trades a day) would make a losing fork a candidate: ten forks beat the losing control on two of the last three days. No fork is positive on any day · _USABLE_
- **FACT** · Leg RI-04 stands at KILL: G2 drawdown 53.16 SOL · _USABLE_
- **INFERENCE** · The one binding stage, for both contracts, is the edge at the attainable fill: no entry rule in either contract, whole or forked, is positive on the tape, and every exit, size and hold fork of a negative entry is negative. Work on exits, holds, sizes or the grader cannot change the sign; only a different entry can · _USABLE_
- **INFERENCE** · Step 1 of the bet sequence (20 real 0.01 SOL buys to measure the landed fill) buys a bit that cannot change the verdict: a signed transaction lands at or after the first mark on a launch with buyers, so the real fill can only be worse than the first-mark fill, and both books already lose there. The fill bit is worth its 0.3 SOL only once a fork is positive at the first mark · _USABLE_
- **INFERENCE** · RI-05's verdict is read on the tape its constants were tuned on (rule 2: no rule is tuned on the book that judges it; rule 5: the bench is held out). Only days from 10-28 on count for RI-05, and one day of 15 trades is no verdict · _USABLE_
- **INFERENCE** · RI-04 running 957 closes past the contract's own count is a rule-7 breach (the machine keeps the discipline), though not the binding stage: the extra closes cost nothing but paper and the engine is also the tape. Capping the count without stopping the tape needs a change to src/duval.py and an engine restart, which has crashed before · _USABLE_

## OPTIONS

| option | status | do | circle | door |
|---|---|---|---|---|
| A-fork-ri05-and-raise-the-bench | open | The population replays RI-05's rules one at a time on RI-04's control at the attainable fill (four forks, in ops/population.py, tested); a candidate must be positive as well as beat the control; RI-05's own report is read as a verdict only on days after 10-27; the review of both contracts is written to docs/CHECKLIST-2026-10-28.md; step 1 real buys are deferred until a fork is positive at the first mark; no contract, constant or counted trade changes | inside | reversible |
| B-measure-the-real-fill-now | open | Run step 1 of the bet sequence now: 20 real 0.01 SOL buys on matched launches to measure the landed fill against the message and first-mark states | inside | IRREVERSIBLE |
| C-cap-the-count-at-200 | open | Add a count cap to src/duval.py so the book opens no paper position past the contract's 200 closes while the engine keeps marking every launch and writing the paths tape; restart the engine | inside | reversible |

## ASYMMETRY
- **A-fork-ri05-and-raise-the-bench**: up: the next contract, if any, starts from an entry that was positive on a held-out tape, and the bench cannot promote a loser; down: the morning report keeps saying no candidate, and the only tape is the engine's three days
- **B-measure-the-real-fill-now**: up: the fill is measured once and for all; down: about 0.3 SOL and the operator's time spent on a bit that cannot turn a negative book positive
- **C-cap-the-count-at-200**: up: the machine keeps the contract's own discipline and the journal's splits already have 1157 closes; down: a restart of the engine, which has crashed on startup before, and the tape stops if it does

## SURVIVAL
- **A-fork-ri05-and-raise-the-bench** fails if the first-mark fill is itself too pessimistic because the chain read lags real execution by less than one mark; then a fork positive in reality reads negative here. The 588 counted entries that got the message state and still lost (PF 0.71) bound that case
- **B-measure-the-real-fill-now** fails if no fork is positive at the first mark, so there is nothing to run at the measured fill; the bit is bought and shelved
- **C-cap-the-count-at-200** fails if the restart fails unattended and no paths are written until the operator notices; the population and RI-05 lose their input for that time

## INCENTIVES
- Claude first: Claude built the population, RI-05 and the checklist, and a finding that the loop has no edge at any fill ends a week of Claude's own replays with nothing to promote; the temptation runs toward one more fork, one more day, one more grader. The operator: named the loop from Jack Duval's wallet and has watched it lose on paper for five days; the honest reading is that the entry has no edge on this tape and that no paper bit changes that. Nobody is paid: paper only, no capital moves.

## LEVERAGE, OWNERSHIP, COMPOUNDING
- **A-fork-ri05-and-raise-the-bench** leaves: four more forks on the same tape, a bench that cannot promote a loser, and a written review of both contracts under the seven rules (owned)
- **B-measure-the-real-fill-now** leaves: one fill measurement (owned)
- **C-cap-the-count-at-200** leaves: the contract's count honoured (owned)

## SYSTEM EFFECT
- **A-fork-ri05-and-raise-the-bench**: ops/population.py gains four forks and a stricter candidate rule; out/population.md and state/population.json change shape; nothing in src/duval.py, src/five.py or prereg/CONTRACT.md changes
- **B-measure-the-real-fill-now**: real SOL leaves a wallet; the counted book is not touched
- **C-cap-the-count-at-200**: src/duval.py changes and the engine restarts; the counted book stops growing; the tape continues if the restart holds

## THE DOOR
- Reversible, decided now: the four RI-05 forks and the positive-candidate rule in ops/population.py, with tests; the review docs/CHECKLIST-2026-10-28.md and the day's second Record row; RI-05.md pointed at the forks; this decision committed locally; the population rerun
- Irreversible, gated: step 1 real buys (option B) wait for a fork positive at the first mark on a held-out day (gate rich-fork-positive-at-first-mark); capping the count and restarting the engine (option C) is the operator's, because the restart has crashed before and the engine is the tape; a new contract id is a separate ruling; no capital moves; a push to the remote waits for the operator

## RECOMMENDATION
**A-fork-ri05-and-raise-the-bench.** RULED: option A. The binding stage for both contracts is the edge at the attainable fill: no entry in either contract is positive, whole or forked, and every exit fork of a negative entry is negative. Work only there: RI-05's rules are forked one at a time onto the control, a candidate must be positive as well as beat the control, RI-05 is judged only on days after its tuning tape, and no real SOL buys a fill bit until a fork is positive at the first mark. RI-04's contract and verdict stand. Capping the count is a rule-7 item for the operator, not the binding stage. · _USABLE_

## Gates on the irreversible half

| gate | rule | measured | reading | from |
|---|---|---|---|---|
| rich-fork-positive-at-first-mark | best_fork_mean_sol_x10000 >= 1 | -335 | **NO BELIEF** | ops/population.py 10-26..10-28, best fork take +10 % at -0.0335 SOL mean |
| rich-ri05-heldout-pf-x100 | ri05_first_mark_pf_x100_days_after_10_27 >= 100 | 0 | **NO BELIEF** | state/five_replay.json by_day 2026-10-28: -0.025 mean on 15 trades (sum -0.4 SOL) |
| rich-capital-after-s1 | s1_reached >= 1 | 0 | **NO BELIEF** | ops/readout.py verdict KILL |

## Ledger

| claim | layer | label | ruling | m(alive) | m(dead) |
|---|---|---|---|---|---|
| rich-2026-10-28-checklist-both-contracts-F01 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-F02 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-F03 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-F04 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-F05 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-F06 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-I01 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-I02 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-I03 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-I04 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-U01 | L3 | UNKNOWN | **UNVERIFIED** | 0.00 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-M01 | L1 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-opt-A-fork-ri05-and-raise-the-bench | L3 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-opt-B-measure-the-real-fill-now | L3 | HYPOTHESIS | **WEAK** | 0.35 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-opt-C-cap-the-count-at-200 | L3 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-28-checklist-both-contracts-R01 | L4 | INFERENCE | **USABLE** | 0.60 | 0.00 |
