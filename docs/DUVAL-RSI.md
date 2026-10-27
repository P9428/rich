# The Duval loop as a self-improving system

Three interviews (Noam Brown on multi-agent and RSI; Elon Musk on limiting factors, space compute and Optimus; Beren Millidge, John
Schulman and Charlie O'Neill on RSI, RL and data) applied to contract RI-04. The overlaps are the spec; the build is what the three of
them would build from first principles. Nothing here changes a counted trade; the count is the contract's and only RI changes it.

Full transcripts of the three Dwarkesh Patel episodes: `docs/transcripts/dwarkesh-noam-brown.txt`,
`docs/transcripts/dwarkesh-elon-musk.txt`, `docs/transcripts/dwarkesh-millidge-schulman-oneill.txt`.

## The seven overlaps

| # | Brown | Musk | Millidge / Schulman / O'Neill | Rule for the loop |
|---|---|---|---|---|
| 1 | RSI is bottlenecked by experiments, not intelligence | "I'm constantly addressing the limiting factor" | progress stalls where the model is weakest | every review names one binding stage and works only there |
| 2 | evaluate honestly or the grader is hacked | "reality is the best verifier, physics is law" | the judge gets reward-hacked, sim-to-real is the gap | marks from the chain, fills pay their own impact, no rule tuned on the book that judges it |
| 3 | 130 B tokens in 88 hours | 10 million cars as the flywheel | RL learns one bit an episode; the frontier's signal must be built | 40 closes is 40 bits; 29,000 launches a day is the environment; score all of them |
| 4 | 10,000 agents, fork the context, spin losers down | 10,000 Optimus in an academy doing self-play | millions of instances in parallel | one feed, a population of forked paper books, same tape |
| 5 | measure 64, 128, 256 before claiming 10,000 | weekly review, plot the points, act only when success leaves the set | Cursor: redeploy every 5 h if it beats the bench, else discard | promote a variant only after it beats the control on consecutive forward days |
| 6 | problems too easy teach nothing, too hard give no signal | a little fab first, then ride the S-curve | fifth grade to college gave no signal; rungs did | one changed variable per contract |
| 7 | agents are exceptional and jagged | hire for traits, add domain knowledge | the last human job is specifying the objective | the operator keeps the paragraph and the gates; the machine keeps the discipline Jack lost |

## What was built (2026-10-23, Amendment 2 of RI-04)

- **The environment.** `src/duval.py` now marks every launch on chain every 2 s for 180 s, matched or not, and writes the path to
  `journal/paths/<day>.jsonl` (reserves at each mark, so any rule can be replayed with the exact fill it would have got). This turns
  the leg from one bit a minute into tens of thousands of bits a day, and it gives the hypothesis its control group: unmatched launches.
- **The population.** `ops/population.py` replays the control (the contract as written) and nineteen one-variable forks against the
  same tape: the control group (all launches, unmatched only), the fill-realism forks (entry at the first mark, at +10 s, after the
  first outside buy), the exit forks (take 10/30/50 %, stop 10/30 %, hold 30/120/180 s), the size forks (0.5/1/3 SOL), the cap forks
  ($6K/$20K) and the mint-suffix fork. Each gets the same fees, the same impact, the same marks.
- **The limiting-factor review.** The population names one binding stage in a fixed order: rate (entries a day under 40), edge (control
  mean net at or below zero), exits (stop share over 60 %), else count. That line is the day's work.
- **The promotion rule.** A fork is a candidate only after beating the control on mean net on each of the last three days with at least
  50 trades a day. Candidates are ruled through RI into a new contract id; the script never changes a rule.
- **The hypothesis test.** Matched vs unmatched mean net with a bootstrap interval, so "the hour's news" is tested, not assumed.
- **What the machine will not do**, written as rules it cannot break: size is fixed, no adds, no re-entry, three open at most, the
  stop is the stop. These are the four deviations that turned Jack's +1,055 SOL into -3,625.

## What stays human

The paragraph (the objective), the gates, the deadline, capital. Forecasts are written before outcomes and never edited. A promoted
fork is a new contract id with a fresh count; the old count is never re-scored under new rules. Lessons move beliefs only when the
cause is the model, not the draw.

## The ladder (one rung at a time)

0. RI-04 as written: fixed rules, counted. (now)
1. One promoted fork, if any, as RI-05: the same loop with one variable moved. Only after rung 0 has a verdict or 200 closes.
2. Term weighting: which headline terms carry the edge, from the paths, as a filter, not a size.
3. Entry timing: the first-buyer rule, if its fork earns it.
Each rung needs signal at the previous one: a fork that never beats the control is spun down, not argued for.
