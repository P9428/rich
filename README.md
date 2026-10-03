# rich

A sensor that catches a named person publicly touching a coin, runs the coin through a breadth screen, and
paper-trades the touch under pre-registered loss-first gates. No orders are placed. Contract: `prereg/CONTRACT.md`.

```
src/feeds.py     Truth Social posts · roster-wallet buys/receipts/supply gifts (websocket) · DexScreener profiles · X API (dormant without X_BEARER)
src/resolve.py   words -> mint under the exact-name rule
src/screen.py    breadth gate: liquidity, age, buys/hour, buys>=sells, market cap, no full-curve dev bundle
src/paper.py     1 SOL paper positions: -10 % stop booked -15 % or the mark if lower, out at 15 min if not above entry, half at +100 %, 30 % trail, 24 h time stop
src/sensor.py    the loop; only a touch with intent ($ticker or mint in the post, or a signed buy) enters; heartbeat monitor/heartbeat.json; alerts monitor/alerts.log (+ Telegram when configured)
ops/readout.py   daily gates G1-G4 / S1 -> out/readout.txt
ops/journal.py   The Foresight Journal: beliefs, predictions, scores, lessons (forecast/), shadow book of every screened touch -> out/journal.md
ops/digest.py    Rich Foresight digest (24 h / 7 d / 30 d) -> out/foresight.html, republished daily at 06:05 by ops/digest.ps1
ops/decide.py    one decision ruled through RI (the PPG laws and engine) -> decisions/<date>-<slug>.md
ops/*.ps1        workstation tasks (hidden), mirrors the sibling repos
tests/           known-answer pins from prereg/KNOWN_ANSWER.json
docs/TOLL.md     the fee-on-flow plan
```

Run: `python src/sensor.py` (or register tasks: `powershell -File ops/register_tasks.ps1`).
Optional `.env` keys: `X_BEARER`, `TG_BOT_TOKEN`, `TG_CHAT_ID`, `RICH_RPC`, `RICH_WS`.
The Foresight Journal loop (observation only, never trades):

1. Before a leg runs, write what will happen: `python ops/journal.py predict ...` (a claim, a metric, a probability, a deadline, the belief it rests on).
   A second forecaster answers the same question with `predict --like <pred_id> --who <name> --confidence <p>`.
2. `rich - JOURNAL` runs `tick` every 5 minutes: it shadows every screened touch for 24 h under the contract exits (passes and rejects),
   resolves forecasts from `journal/` the moment their metric can speak, and rewrites `out/journal.md`.
3. A forecast that gave under 50 % to what happened owes a lesson: `python ops/journal.py lesson --pred <id> --what ... --why ... --cause model|variance|measurement|question|execution [--belief B1 --p 0.2] [--rule ...]`.
   Only a `model` cause should move a belief; rules are what the next contract inherits.
4. `forecast/*.jsonl` are append-only and hash-chained (`python ops/journal.py verify`). Commit them when written: the commit is the timestamp.

Tests: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` (add `-m "not live"` to skip DexScreener calls).
