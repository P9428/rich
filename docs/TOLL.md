# The toll track

The autopsy's only participants whose return did not depend on being early were the ones collecting a fee on flow:
stonk.fun ($31.1M revenue on $2.67B volume through Sep 14), reward-launch creators (quote-asset fee share), the
points farmers and the paid callers. This file is the plan for the operator to stand on that side. Nothing here is
built until the sensor has run for a week; everything here is sized so a failure costs under $100.

## 1. Tooling toll (first, because it is this repo)

- `src/sensor.py` already posts every screened touch to a Telegram chat when `TG_BOT_TOKEN` and `TG_CHAT_ID` are set
  in `.env`. That stream is the product: named-person touches, resolved to a mint, with the breadth verdict, seconds
  after they happen.
- Step 1: run it privately for 14 days; keep `journal/events.jsonl` as the public proof-of-latency log.
- Step 2: open a free channel that re-posts with a 10-minute delay; the paid channel gets the live feed.
- Step 3: price at $49/month only after the readout shows ≥ 20 resolved touches a week. Payment by Stripe link or
  SOL to a fresh wallet; no custody of anyone's funds.
- Kill: fewer than 20 paying subscribers after 60 days.

## 2. Quote-asset fee share (stonk.fun "Rewards" launches)

- Mechanism: a token launched with Rewards on distributes its trading fees in the quote asset to holders. Holding the
  quote-paired coin that trends collects the toll without a launch.
- Constraint: stonkfun.xyz's terms list US residents as restricted users of the launchpad. Launching is out.
  Holding a reward token bought on Jupiter is an ordinary DEX trade; confirm with counsel before scaling.
- Measure first: the scrape in `~/onchain-savage/data/stonkfun_pools.jsonl` carries `isRewardLaunch`; the
  readout to build is realised fee yield per dollar held across reward launches that reached ≥ $1M.

## 3. Creator fee (pump.fun)

- Mechanism: creator fees on a coin the operator deploys. The corpus says 2.6 % of full-bundle launches survive and
  the ANSEM structure needs a famous person to adopt the coin.
- Not pursued. The expectancy of launching is the expectancy of a lottery ticket plus reputational cost.

## 4. What is explicitly not a toll

Copy-trading named wallets, sniping launches, buying trending lists. All three are the taker side the prior audits
killed and this autopsy re-confirmed.
