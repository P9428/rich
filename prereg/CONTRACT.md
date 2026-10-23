# rich — contract RI-04 (the Duval loop, paper only)

Frozen 2026-10-23. Supersedes RI-03 (`prereg/RI-03.md`, the named-person sensor; its book is `journal/paper.RI-03.jsonl`, 4 closes,
never counted here), RI-02 and RI-01. Every rule below is fixed before the first counted trade. Changes require a new contract id
and a fresh paper count. No order is ever placed by this repo. Ruled in `decisions/2026-10-23-ri04-duval-loop.md`.

## What RI-04 is

The operator stopped the named-person sensor on 2026-10-23 and named the next strategy from the behavioral model of Jack Duval's
wallet (`out/jd_wallet/REPORT.md`, 17,270 closed positions, 2025-04-22 to 2026-10-23):

> He decides on freshness and narrative, not price: fresh launch, matches the hour's news, under $10K, in within 30 seconds
> with 1-2 SOL, out within a minute.

The numbers the paragraph leaves open are his own medians: winners +20 % and losers −19 %, both reached in about a minute;
62 % of his entries under 30 s old; median entry market cap $8.4K; median overlap of open positions 1, p90 4.

## Hypothesis

A fresh pump.fun launch whose name is taken from a headline of the last hour, bought under $10K market cap within 30 seconds of
creation and sold within a minute, has positive expectancy after fees and the book's own price impact. The wallet that ran this loop
made +1,055 SOL on 10,316 positions over nine months before it stopped running it (sizing up, averaging down, holding losers).

## Feeds

| Feed | Source | Latency | Status |
|---|---|---|---|
| `pump` | PumpPortal `subscribeNewToken` websocket: mint, name, symbol, bonding curve key, virtual reserves at creation | push, ~1 s | live, keyless |
| `news` | Google News RSS: top stories plus WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SPORTS, SCIENCE, HEALTH | 60 s poll | live, keyless |
| `sol_usd` | DexScreener wrapped-SOL price | 60 s poll | live, keyless |

X trends and X search are not observable (the key answers 402); if his narratives come from there and not from the headlines,
the news feed is the gap, logged as a known one and not approximated.

## The hour's news

A title published within the last 60 minutes contributes its proper nouns: capitalised words of 4+ letters, all-caps words of 3+
letters, and adjacent pairs of them. A stop list removes sentence starters, weekdays, months, outlet names and generic news and
market words (`src/duval.py STOP_WORDS`). The term set is rebuilt every minute and saved to `state/news.json`.

### Amendment 0 (2026-10-23 15:10Z, before the first counted trade; the engine had seen 10 launches and matched none)

The first fetch showed the top and section feeds carry titles that are hours old: 8 titles and 21 terms inside the hour, half of them
sentence openers ("Beyond", "Uncovering"). Google News search with `when:1h` returns about 100 titles each, all inside the hour.
The news feed is therefore six `when:1h` searches (news, breaking, world, crypto/bitcoin/solana/memecoin, celebrity/viral/trending,
elon/trump/musk) plus the top and section feeds, all still filtered to the last 60 minutes; and a title's first word counts on its own
only when it also appears capitalised mid-title somewhere in the window (or is all caps). The 60-minute window, the match rule and
every other rule are unchanged. No trade had been counted.

### Amendment 1 (2026-10-23 15:15Z, before the first counted trade)

Amendment 0's feed produced three entries in its first minute, all wrong in ways the rules above did not foresee: the terms "boss",
"real" and "ground" matched (Title Case headlines make every word look like a name), and two launches whose mints do not end in
`pump` showed a +2047 % "take" one mark after entry because their on-chain curve carries 722 virtual SOL while the feed's message said
30: the fill was computed on the message and the mark on the chain. Those three rows live in `journal/paper.RI-04-amend0.jsonl` and
are never counted; the book and `journal/paper.jsonl` start again from here. Three rules added, none of them an exit or a size:

- the mint must end in `pump` (a pump.fun mint); others are screen fails
- the curve is read on chain at decision and the fill is computed on those reserves; if the account is unreadable, complete, or its
  virtual SOL is outside 0.5-2x the feed's figure, the launch is a screen fail ("non-standard curve")
- in a Title Case headline a word counts as a name only if it also appears capitalised mid-title in a sentence-case headline of
  the window (or is all caps); a stop list of common English words applies to every headline

## Entry (all at the create message, measured on the curve state it carries)

- the launch's name carries a term as a whole word, or its symbol equals a term, or a term of 6+ letters or a pair runs inside the name
- pool is plain `pump`; mayhem-mode launches are logged and skipped
- market cap on the curve (virtual SOL / virtual tokens × 1e9 × SOL/USD) < $10,000
- decision inside 30 s of the message (the message is the earliest observable moment; the create transaction's block time is
  fetched after entry and recorded on the close as `created`, so age at entry is a measured number, not a rule)
- size 1.5 SOL (the midpoint of "1-2 SOL"); the fill is the curve's constant product on its virtual reserves after the 1 % pump fee
  and a 0.001 SOL transaction fee, so the entry price carries the book's own impact
- at most 3 open; one entry per mint, ever (no re-entry)

Every launch is written to `journal/launches.jsonl` (one line, with its matched terms). Only news-matched launches are events in
`journal/events.jsonl`; the ones over $10K or outside the pool rule are screen fails there, so the pass rate is the share of
news-matched launches that were cheap enough.

## Exit (whole position, at the curve's own sell price after fees, marked every 2 s from the bonding-curve account over RPC)

- take at +20 %
- stop at −20 %, booked at the mark (a mark below −20 % books what the mark says)
- time at 60 s after entry, whatever the mark
- if the curve reports complete (migrated) before any of the above, the position closes at the last mark as `complete`

The mark is what selling the whole position into the curve would return after fees, so the book pays impact on both sides.
There is no partial take, no trail and no 24 h clock: the paragraph says out within a minute.

## Loss-first gates (checked daily by `ops/readout.py`; bars scale with the size, 1.5 × the 1 SOL bars of RI-03)

| Gate | Rule |
|---|---|
| G1 | 10 consecutive losers → **KILL** |
| G2 | realised drawdown > 12 SOL → **KILL** |
| G3 | after 40 closed trades, win rate < 25 % → **KILL** |
| G4 | after 40 closed trades, mean net ≤ 0 → **KILL** |
| S1 | after 40 closed trades, mean net > 0 and mean loss < 0.45 SOL and G1–G4 clear → **SURVIVES ON PAPER** |

Give-up date 2026-11-30 if S1 is not reached. No capital is proposed before S1. A verdict at 40 closes is a verdict on the loop as
written; the count keeps running to 200 closes so the journal can split it by age at entry, matched term and market cap.

## The Foresight Journal (unchanged from RI-03, Amendment 3)

Forecasts are written before the first counted trade: the market forecasts first (`mk_touches` here means news-matched launches a
day, `mk_pass_rate` the share under $10K), then the leg forecasts resting on them. Every screened launch is shadowed for 24 h under
RI-03's exits by `ops/journal.py tick` as before, never counted. Lessons become rules only in a later contract id.

## Known answer

`tests/test_known_answer.py` pins RI-01..03's resolver and gates and still runs; nothing in it counts here. The RI-04 engine is
`src/duval.py`; its curve arithmetic is checked in `tests/test_duval.py`.
