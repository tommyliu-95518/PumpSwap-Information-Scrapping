Milestone Plan
## Milestone 1 — Core MVP (Single Token, Stateless)

Goal: Prove feasibility end-to-end for one token.

Deliverables

Input: token mint (CA)

Fetch recent transactions touching the mint

Detect token balance changes

Compute:

Token age

Rolling volume (1m/5m/15m/1h)

Output JSON result

Success Criteria

Correct volumes update over time

Age increases correctly

No external APIs used

## Milestone 2 — PumpSwap Swap Detection

Goal: Filter only real PumpSwap trades.

Deliverables

Identify PumpSwap program IDs

Detect PumpSwap swaps via:

instruction program IDs

transaction logs

known account patterns

Ignore transfers, burns, airdrops

Success Criteria

Volume matches PumpSwap UI behavior

False positives removed

## Milestone 3 — Price & Market Cap Calculation

Goal: Turn raw swaps into financial metrics.

Deliverables

Extract quote asset delta (SOL or USDC)

Calculate last trade price

Read SPL Mint supply

Compute:

price

market cap (SOL)

(Optional) USD mcap via Pyth oracle

Success Criteria

Price matches last on-chain trade

MCap scales correctly with supply

## Milestone 4 — Token Metadata & Identity

Goal: Human-readable token data.

Deliverables

Decode Metaplex Token Metadata PDA

Fetch:

token name

symbol

Handle missing / malformed metadata safely

Success Criteria

Correct names for standard Pump tokens

Graceful fallback for missing metadata

## Milestone 5 — Persistence & Aggregation

Goal: Make analytics efficient and scalable.

Deliverables

Store parsed swaps in local DB

Avoid re-processing same transactions

Fast aggregation queries for volumes

Success Criteria

Instant metric calculation

No repeated RPC backfills

## Milestone 6 — Real-Time Indexer

Goal: Live analytics.

Deliverables

WebSocket subscription to PumpSwap programs

Real-time trade ingestion

Rolling window updates in memory

Success Criteria

Metrics update within seconds of trades

Stable under sustained activity

## Milestone 7 — Multi-Token Support (Optional)

Goal: Platform-level readiness.

Deliverables

Track many tokens simultaneously

Token discovery via PumpSwap events

Unified analytics output

Success Criteria

Multiple tokens tracked without data collision

Consistent metrics across tokens

Final Outcome

A fully on-chain PumpSwap analytics engine capable of powering:

dashboards

bots

alerts

trading tools

research platforms

If you want, next I can:

turn this into a GitHub README

shorten it for a resume / portfolio

or map each milestone directly to code modules (what file does what).