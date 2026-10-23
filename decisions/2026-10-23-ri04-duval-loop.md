# Decision · The operator stopped the named-person sensor (RI-03) and named the next strategy to paper-trade: Jack Duval's loop, 'fresh launch, matches the hour's news, under $10K, in within 30 seconds with 1-2 SOL, out within a minute'. The paragraph fixes the entry; the exit, the size, the book depth and the news source need numbers before anything counts. Which numbers?

Friday 2026-10-23 · asked by operator 2026-10-23: 'stop whatever rich was running up until now. This is the new strategy we need to paper trade: [the one-paragraph model]' · log root `9997e353b98f459945bb3143213466a73bef28f3e2ae91f4a152df7c1c7d7d76` · size 17

## REALITY
Looked at before reasoning: out/jd_wallet/positions_named.json, all 17,270 closed positions of BAr5c..XJPh (2025-04-22 .. 2026-10-23), phase_out.txt: 62 % of entries within 30 s of pair creation, median entry mcap $8.4K, median hold 51 s, winners' median +20 % at 35 s, losers' median -19 % at 79 s (edge era), size under 2 SOL 57-69 % win and +2,825 SOL, over 5 SOL 30 % win and -3,833 SOL, overlapping open positions median 1 and p90 4; PumpPortal wss://pumpportal.fun/api/data subscribeNewToken, probed 2026-10-23 14:20Z: keyless, 4 launches in 25 s, each with mint, name, symbol, bondingCurveKey and the curve's virtual reserves; subscribeTokenTrade refused without a funded key; RPC getMultipleAccounts on three bondingCurveKeys, 1.06 s round trip: 166-byte accounts decode to virtual and real reserves and the complete flag, so a mark is the curve itself, not DexScreener; Google News RSS top and section feeds: 38 and 68 items in 0.2-0.5 s, pubDate per item, keyless; X search is dormant (402s on the key) and Truth Social carries one roster, not the hour's news; src/paper.py, ops/readout.py, ops/journal.py: the gates and metrics read journal/paper.jsonl close rows (net_sol) and journal/events.jsonl screen rows; a new engine that writes those shapes keeps the readout, the Foresight Journal and the morning command working unchanged; monitor/guard.log and sensor-stderr.log: src/sensor.py has been crash-looping every 5 minutes on blank state files; no live sensor existed when the operator said stop; did not look: how many launches per day match the hour's headlines under $10K (the rate that decides whether 40 closes come in days or weeks); what the first outside buyer's timing is relative to the create message.
- **FACT** · In the wallet's edge era (May 2025 - Feb 2026) scalps under 2 SOL held under 60 s won 61 % and made +486 SOL on 3,894 positions; the same wallet's positions over 5 SOL or with 4+ buys won 42 % and made +130 SOL on 2,954 · _USABLE_
- **FACT** · His winners' median return is +20 % and his losers' median is -19 %, both reached in about a minute; 62 % of entries are under 30 s old and the median entry market cap is $8.4K · _USABLE_
- **FACT** · The launch feed is keyless and carries the curve reserves at creation; marks can be read from the curve account over public RPC in about a second; trade-by-trade data needs a paid key · _USABLE_
- **FACT** · A 1.5 SOL buy on a fresh curve (30 SOL virtual) moves the price about 5 %, so the book's own impact costs roughly a tenth of a round trip; a mark that ignores it flatters every close · _USABLE_
- **FACT** · The readout gates were written for 1 SOL (G2 8 SOL drawdown, S1 mean loss under 0.3 SOL); at 1.5 SOL with a -20 % exit the typical loss is about 0.36 SOL before impact · _USABLE_
- **FACT** · Leg RI-04 stands at INSUFFICIENT: 0/40 closed trades · _USABLE_
- **INFERENCE** · An exit at +20 % / -20 % / 60 s is the wallet's own median win, median loss and median hold; any other exit tests a loop he did not run · _USABLE_
- **INFERENCE** · Entering at detection (age about 1 s, before any outside buyer) is earlier than most of his entries (median age 14 s); the book will sometimes be the first buyer after the dev. The paragraph says 'within 30 seconds', so detection-time entry is inside the rule, and the 'created' stamp on each close lets the journal measure whether age at entry matters · _USABLE_
- **INFERENCE** · Honest fills (curve math both sides, 1 % pump fee, 0.001 SOL tx fee a side) make the paper book worse than his tape, not better; a loop that survives them is more likely to survive a real tip and a slow landing · _USABLE_

## OPTIONS

| option | status | do | circle | door |
|---|---|---|---|---|
| A-literal-loop | open | Freeze RI-04 as the paragraph reads, with the wallet's own medians as the exit: PumpPortal launch feed; a launch is in play when its name or symbol carries a proper noun from a headline published in the last 60 minutes (Google News top and section feeds, refreshed every minute); enter at detection if the curve market cap is under $10K and the pool is plain pump; size 1.5 SOL; out whole at +20 %, -20 % or 60 s, whichever comes first, at the curve's own sell price after fees; at most 3 open, one entry per mint ever; gates G1-G4 and S1 scaled to the size (G2 12 SOL, S1 mean loss under 0.45 SOL); give-up 2026-11-30 | inside | reversible |
| B-wait-for-first-buyer | open | Same as A, but enter only after the curve shows a buy that is not the dev's, and still inside 30 s of the create message | inside | reversible |
| C-ri03-exits | open | Keep RI-03's exits (-10 % stop booked -15 %, 15-minute stale cut, half at +100 %, 30 % trail, 24 h) on top of the new entry | inside | reversible |

## ASYMMETRY
- **A-literal-loop**: up: every counted trade is his loop at his numbers with worse fills than his; down: the rate is unknown (U01) and the first-buyer entry is earlier than his median (I02)
- **B-wait-for-first-buyer**: up: closer to his median age at entry and skips launches nobody touches; down: needs a 1 s poll of every matched curve for 30 s, and the paragraph does not say it
- **C-ri03-exits**: up: the gates and the paper module are reused as they are; down: contradicts 'out within a minute' and his -19 % loser median

## SURVIVAL
- **A-literal-loop** fails if news-matched launches under $10K are so rare that 40 closes do not arrive by the give-up date, or so common that the book is full and the count is a sample of the queue, not the rule
- **B-wait-for-first-buyer** fails if the extra poll doubles RPC load for a rule the operator did not state, and the count then measures a filter rather than his loop
- **C-ri03-exits** fails if the count rules on a hold he never used and the verdict says nothing about his loop

## INCENTIVES
- Claude first: Claude wrote the one-paragraph model an hour ago, so building it as written protects that paragraph, and a looser copy of RI-03's exits would protect the older code; either answer flatters Claude's own work and only the wallet's numbers can choose. The operator: wants a leg that counts quickly and a loop that is his own, which pushes toward entering at detection and sizing at the top of the 1-2 SOL range. Nobody is paid: this is paper.

## LEVERAGE, OWNERSHIP, COMPOUNDING
- **A-literal-loop** leaves: a counted paper leg of the Duval loop with honest fills, a launches file with every launch and its headline match for the next contract to mine, and a journal that can say whether age at entry, term, or size is the variable (owned)
- **B-wait-for-first-buyer** leaves: a filtered count (owned)
- **C-ri03-exits** leaves: nothing new (owned)

## SYSTEM EFFECT
- **A-literal-loop**: the readout, the Foresight Journal, the morning command and the guard keep running on the same files; only the sensor module changes
- **B-wait-for-first-buyer**: a rule added before the first lesson, which the journal loop says to leave to the next contract
- **C-ri03-exits**: the new leg inherits an exit the operator just retired

## THE DOOR
- Reversible, decided now: RI-04 on paper: the engine, the contract text, the guard pointed at it, the forecasts (market first, then the leg), a local commit so the forecasts carry a timestamp
- Irreversible, gated: capital stays gated on S1 as the contract says; a push to the remote waits for the operator; forecasts once written are never edited; the retired RI-03 book and contract are archived, not deleted

## RECOMMENDATION
**A-literal-loop.** RULED: option A. Paper-trade the paragraph as written with the wallet's own medians as the exit and honest curve fills, at most 3 open, 1.5 SOL. The rate (U01) and the first-buyer question (I02) are the first forecasts the leg writes, not rules it adds. · _USABLE_

## Gates on the irreversible half

| gate | rule | measured | reading | from |
|---|---|---|---|---|
| rich-capital-after-s1 | s1_reached >= 1 | 0 | **NO BELIEF** | ops/readout.py verdict SURVIVES ON PAPER |
| rich-ri04-rate-known | matched_launches_per_day >= 10 | 0 | **NO BELIEF** | journal/events.jsonl: news-matched launches per day; below 10 a day the leg cannot reach 40 closes in a week and the news window, not the exit, is the constraint |

## Ledger

| claim | layer | label | ruling | m(alive) | m(dead) |
|---|---|---|---|---|---|
| rich-2026-10-23-ri04-duval-loop-F01 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-F02 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-F03 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-F04 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-F05 | L0 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-I01 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-I02 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-I03 | L1 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-U01 | L3 | UNKNOWN | **UNVERIFIED** | 0.00 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-U02 | L3 | UNKNOWN | **UNVERIFIED** | 0.00 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-M01 | L1 | FACT | **USABLE** | 0.95 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-opt-A-literal-loop | L3 | INFERENCE | **USABLE** | 0.60 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-opt-B-wait-for-first-buyer | L3 | HYPOTHESIS | **WEAK** | 0.35 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-opt-C-ri03-exits | L3 | HYPOTHESIS | **WEAK** | 0.35 | 0.00 |
| rich-2026-10-23-ri04-duval-loop-R01 | L4 | INFERENCE | **USABLE** | 0.60 | 0.00 |
