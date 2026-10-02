# rich

A sensor that catches a named person publicly touching a coin, runs the coin through a breadth screen, and
paper-trades the touch under pre-registered loss-first gates. No orders are placed. Contract: `prereg/CONTRACT.md`.

```
src/feeds.py     Truth Social posts · roster-wallet buys/receipts/supply gifts (websocket) · DexScreener profiles · X API (dormant without X_BEARER)
src/resolve.py   words -> mint under the exact-name rule
src/screen.py    breadth gate: liquidity, age, buys/hour, buys>=sells, market cap, no full-curve dev bundle
src/paper.py     1 SOL paper positions: -25 % stop booked -30 %, half at +100 %, 30 % trail, 24 h time stop
src/sensor.py    the loop; heartbeat monitor/heartbeat.json; alerts monitor/alerts.log (+ Telegram when configured)
ops/readout.py   daily gates G1-G4 / S1 -> out/readout.txt
ops/*.ps1        workstation tasks (hidden), mirrors the sibling repos
tests/           known-answer pins from prereg/KNOWN_ANSWER.json
docs/TOLL.md     the fee-on-flow plan
```

Run: `python src/sensor.py` (or register tasks: `powershell -File ops/register_tasks.ps1`).
Optional `.env` keys: `X_BEARER`, `TG_BOT_TOKEN`, `TG_CHAT_ID`, `RICH_RPC`, `RICH_WS`.
Tests: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests` (add `-m "not live"` to skip DexScreener calls).
