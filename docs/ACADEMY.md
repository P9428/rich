# The Optimus Academy for RI-04 and RI-05

Built 2026-10-29 on the operator's instruction to apply Batman's design (the Robinhood Chain launch academy, itself the three
Dwarkesh interviews applied) to the two rich contracts and run it all day. Nothing here trades, nothing here changes a contract, and
no cell reaches real size except through a ruling under `decisions/` and the operator's own legs. The arithmetic of the target is on
the page itself, every tick, so the gap between what the tape pays and what the operator needs is a number.

```
python ops/academy.py                 one tick on both tapes (home, then VPS)
python ops/academy.py --loop          every 15 minutes, forever (task "rich - ACADEMY" keeps it alive via ops/academy.ps1)
python ops/academy.py --tape vps      the VPS tape only; --round forces a search round
python ops/fill_probe.py --cell <id> --size 0.01 --dry      a roster cell's rules on the feed, dry
```

Outputs: `out/academy.md` (home tape), `out/academy-vps.md` (VPS tape), `monitor/academy.json` (heartbeat), `monitor/academy.log`.
State: `state/academy/{roster,ladder,state}.json` and `record/` (home), `state/academy/vps/` (VPS).

## The first principle, in rich's terms

A pump.fun launch is a hidden process that answers actions. The tape shows what the curve did to other people's buys; it never
contains the book's own fill until one is placed (the fill probe of 2026-10-28 is the only five bits of that kind on file). So the
tape is the curriculum and a real leg is the verifier. The academy learns at the rate it acts, and everything below is machinery for
buying those bits as cheaply as possible and grading them with code that cannot be charmed.

## Batman's layers mapped one to one

| Batman (Robinhood Chain) | rich (pump.fun) | file |
|---|---|---|
| the sensor at the point of contact, raw bytes first, every pool followed from its first swap | `src/duval.py` marks every launch on chain every 2 s for 180 s and writes `journal/paths/<day>.jsonl`; the VPS copy is the parallel tape | existing |
| the identity layer: scripted vs genuine, a family per pool (template, fee500, organic) | a family per launch from what the tape shows at the first mark: `empty` (nobody bought), `sniped` (outside SOL inside the create's own second: a bundle or a bot, not a stranger), `seeded` (creator bought under 2 SOL), `bundled` (creator bought 2 SOL or more) | `src/academy/record.py` |
| the pinned record with a sha256; a grown record is a new contract | one `.npz` a day keyed by the sha256 of the path file's bytes; today's is rebuilt as it grows, a finished day once | `record.py` |
| the arena: every registered strategy on every launch, fit and held-out; a strategy is a whole cell | vectorised over N launches × 95 marks: universe, entry, exit, size; fills at the first mark at or after the delay (where a signed buy was measured to land), pays the measured 1.76 % + 0.000505 SOL a side, marks with the book's own SOL added back (`duval.mark_value`), exits take → stop → trail → hold | `arena.py`, `cells.py` |
| HL-09's look-ahead rule: no universe key not known at the entry mark | `cells.KNOWN` is the only vocabulary; `validate` refuses anything else (a `peak_pct` key is a test) | `cells.py` |
| the answer term: expected net corrected for p, the pull rate on our own legs per family, prior from the record, ten fills outweigh thousands | the launcher's answer on pump.fun is the dump between the exit mark and the sell: prior per family = the tape's next-mark move after the cell's own exits; posterior = the record as 10 pseudo-fills plus the real sells' gross against their mark (`sell_vs_mark`, read as `ops/fill_probe.recompute` does, rent excluded) | `answer.py` |
| the real legs and the residual | every landed row of `journal/probe.jsonl` paired with the arena's prediction for that exact launch at that size; tolerance 0.05 of size | `residual.py` |
| the ladder: six rungs $2.50 to $100, rung 0 by promotion gates, climb on 12 legs inside tolerance, kill on UCB < 0 or sim wrong by 2× | rungs 0.01, 0.03, 0.1, 0.3, 1.0, 1.5 SOL; rung 0 only by `promote(state, id, ruling_slug)`, never by code; climb on 12 legs at the rung with the residual inside 0.05 and a positive mean; kill when the UCB of the real net (z 1.64) is below zero, or the residual is outside 0.10, or the cell stops being eligible | `rungs.py` |
| the bank: realised USD per unit capital per day from fills only | realised SOL and USD per day from landed probe rows, per unit of the 0.116 SOL funded; the wallet mark is never scored | `bank.py` |
| the strategist on DeepSeek proposing three cells a round, every figure a cited roster row, paced by 50 new launches | the search: the 26 forks, 5 mutations of each of the 20 best fit cells, 300 random cells from the grid, every figure the arena's own; a round only when the record grew by 50 launches; the roster trims to the forks, the eligible and the 40 best | `search.py` |
| the weekly review naming the single limiting factor by a fixed rule | every tick: SENSOR (hours missing today, or no launch for 30 min) → SEARCH (no eligible cell) → RULING (eligible, none promoted) → SIM-TO-REAL (residual outside tolerance at a rung) → GROUP (legs owed at a rung) → CAPITAL (top rung held) | `review.py` |
| the human gate: no order by code not named in a signed contract | `ops/fill_probe.py --cell` runs a cell's rules only dry unless the ladder has the cell on a rung at exactly that size; the ladder gets a cell only from a ruling slug | `ops/fill_probe.py` |

## Eligibility and the hazard of the search

A cell is eligible for rung 0 when all four hold: fit mean > 0 on n ≥ 100; held-out mean > 0 on n ≥ 30 on a strictly later day;
the one-sided 95 % bootstrap lower bound of the held-out mean > 0; the answered mean > 0. The page prints how many cells were
positive on the fit period and how many of those would pass the held-out bound by luck (5 % of them). A lone pass is read against
that number; a pass that survives two more held-out days is the claim worth a ruling.

## Round 1, 2026-10-29 17:09Z (home tape, fit 10-26..10-28, held-out 10-29)

| what | number |
|---|---|
| launches in the record | 51,784 (10-26: 17,714; 10-27: 19,768; 10-28: 12,997; 10-29 to 17Z: 1,305) |
| cells scored / on the roster | 327 / 58 |
| positive on the fit period (n ≥ 100) | 5 |
| of those positive on the held-out day | 0 |
| eligible | 0 (0.25 expected by luck) |
| the control at the measured fees | fit 613 at -0.054 SOL a trade; held-out 23 at -0.036 |
| best fork | take +10 % at -0.045 SOL |
| real legs on file | 5 (10-28), residual mean +0.004 of size, inside tolerance; real -0.00168 vs predicted -0.00186 SOL |
| limiting factor | SENSOR: the laptop's tape is missing 12 of 18 hours today; the VPS tape has 6,543 launches today against 1,317, an earlier first mark (1.10 vs 1.40 s p50) and 1.53× the count over the hours both ran (`out/tape_compare.md`) |

The target in the tape's units: $10,000 in 7 days is 98 SOL, 14 SOL a day. At the counted universe's rate (about 200 entries a
day at 1.5 SOL) that is +0.07 SOL a trade, a 4.6 % net edge above a 3.5 % fee floor, on a tape whose best cell is -0.045. The page
recomputes this line every tick against the best held-out cell; it is the honest distance, and the academy's job is to close it one
measured rung at a time or to say that it cannot.

## What the operator keeps

The paragraph, the gates, the ruling that puts a cell on rung 0, the real legs (`ops/fill_probe.py --cell <id> --size <rung>`),
the VPS cut-over, capital. Forecast 65f222a6421e (2026-10-29) gives 0.15 to an eligible cell by 2026-11-05; a miss owes a lesson.

## 2026-10-31: the link, the lock and the gate (docs/CHECKLIST-2026-10-31.md)

The VPS tape never reached the page from 10-30 18:31Z to 10-31 06:17Z: a bare `bash` in `subprocess.run` resolves through
CreateProcess, which searches System32 before PATH and finds WSL's bash (rc 127 on the repo's Windows path; a ten-minute hang on
its scp's host-key prompt once the path was relative). Two loops started 7 s apart by the task tore the state files for a day, and
the home round gate read "grew by -14596" after a day left the window. Since then: `bash_exe` names Git's bash and the pull runs with
stdin closed, a failing pull prints its reason on the page, `--pull` forces one on a tick; `single_instance` holds
`monitor/academy.lock` and a second loop exits; `due` fires a round when the record shrank; `ops/vps_pull.sh` puts `/usr/bin` on
PATH and runs scp in BatchMode. Verified from PowerShell, the task's environment. The first full held-out day on the VPS tape
(round 2, 421 cells on 26,677 launches) moved the limiting factor from SENSOR to SEARCH: 0 cells positive on fit, 0 eligible.
