# rich — contract RI-01 (named-person sensor, paper only)

Frozen 2026-10-02. Every rule below is fixed before the first live event. Changes require a new contract id and a
fresh paper count. No order is ever placed by this repo.

## Hypothesis

A coin moves by an order of magnitude when a named person publicly touches it. The touch is observable within
seconds (a post, a wallet buy or receipt, a supply gift). Coins that already have breadth (many distinct buyers,
real liquidity, no full-curve dev bundle) are the ones that survive the touch. Buying the touch on breadth-screened
coins, with loss-first exits, has positive expectancy after fees. Source: `~/onchain-savage/report`.

## Feeds (what counts as a touch)

| Feed | Source | Latency | Status |
|---|---|---|---|
| `truth` | truthsocial.com public API, statuses of roster accounts | 20 s poll | live, keyless |
| `wallet` | Solana websocket `logsSubscribe` mentions on roster wallets, tx decoded | ~2 s | live, keyless |
| `gift` | same stream; incoming token transfer to a roster wallet ≥ 1% of supply | ~2 s | live, keyless |
| `profile` | DexScreener latest token profiles / boosts whose social link is a roster handle | 30 s poll | live, keyless |
| `x` | X API v2 user timelines of roster handles (`X_BEARER` env) | 60 s poll | dormant until a key exists |

Follows on X are not observable without the API; they are logged as a known gap, not approximated.
Platform bots (the stonk.fun buyback wallet) are not subscribed: their touches are a flywheel, not a person, and
they flood the public RPC. House tokens are a stonk.fun pools-API question, outside this contract.

## Resolver

From a post: `$TICKER` tokens, base58 mints, and 1–3 word capitalised n-grams. Each is searched on DexScreener
(solana only). A candidate is accepted only if the token **name or symbol equals the phrase exactly**
(case-insensitive), the pair existed **before** the event, and liquidity ≥ `LIQ_FLOOR`. Near-misses are logged
and never traded. From a wallet event the mint is known.

## Breadth screen (all must pass, measured at event time)

- liquidity ≥ $20,000 (`LIQ_FLOOR`)
- pair age ≥ 10 min (never a launch snipe)
- buys in the last hour ≥ 50 (`BUYERS_H1`) and buys ≥ sells in the last hour
- if the mint is a pump.fun token and its curve history is complete (< 1,000 signatures): the create transaction
  deposited < 60 SOL (rejects the full-curve dev bundle cohort, 2.6 % survival)
- market cap ≤ $250M (no SOL/USDC-class assets)

## Paper trade (size 1 SOL, modelled fees 2.5 % round trip)

- entry mark = DexScreener `priceUsd` at the first poll after the screen passes (never earlier)
- hard stop −25 %, booked at −30 % (stops fill one print below: doctrine)
- take half at +100 %; remainder trails with 30 % give-back from peak
- time stop 24 h at mark
- one position per mint; at most 5 open

## Loss-first gates (checked daily by `ops/readout.py`)

| Gate | Rule |
|---|---|
| G1 | 10 consecutive losers → **KILL** |
| G2 | realised drawdown > 8 SOL → **KILL** |
| G3 | after 40 closed trades, win rate < 25 % → **KILL** |
| G4 | after 40 closed trades, mean net ≤ 0 → **KILL** |
| S1 | after 40 closed trades, mean net > 0 and mean loss < 0.3 SOL and G1–G4 clear → **SURVIVES ON PAPER** |

Give-up date 2026-12-31 if S1 is not reached. No capital is proposed before S1.

## Known answer

`tests/test_known_answer.py` pins the resolver and gates on fixtures from the September ledger
(`prereg/KNOWN_ANSWER.json`). Those fixtures are spent: they shape the rules and are never counted as trades.
