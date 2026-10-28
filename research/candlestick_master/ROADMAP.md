# BTC Candlestick Master Research Roadmap

## Goal

Build a non-repainting, data-auditable BTC swing framework that combines candle geometry and sequences with completed higher-timeframe context, Polaris moving-average structure (5/10/20/60/112/224/448/896), RSI14, ATR14%, market structure, liquidity and risk controls.

## Non-negotiable research rules

1. Signals may use only information available at candle close.
2. Incomplete higher-timeframe candles are never used.
3. Direction is learned on 2018-2022 only; 2023-2024 validates; 2025-present is untouched test.
4. Overlapping signals are de-duplicated before calculating confidence.
5. Same-bar target and stop hits are ambiguous, never guessed.
6. A candidate must report sample size, confidence interval, MFE, MAE and target-before-stop probability.
7. No strategy is promoted solely because its historical win rate is high; expectancy, drawdown, costs and regime stability also matter.

## Phase 1 — Completed

- 1h source data and 4h/12h/1d reconstruction
- 39 traditional and price-action candle labels
- Candle geometry, MA location/slope, RSI, ATR and higher-timeframe context
- Train/validation/test split
- Base pattern and context performance

## Phase 2 — Active

- 2-5 candle sequence mining
- Coarse geometry tokens and fine flow/liquidity tokens
- Event de-duplication
- ATR first-passage: 0.5/1.0/1.5/2.0 ATR target versus stop
- Wilson and bootstrap confidence intervals
- Completed 4h/12h/1d context for 1h sequences
- Candidate selection on train+validation only; test used only for final survival

## Phase 3 — Planned

- 6-8 candle sequence clustering rather than exact memorization
- Pivot-based HH/HL/LH/LL, BoS and CHoCH
- SFP, Spring, Upthrust and three-tap structures
- Support/resistance flip and retest success/failure
- FVG, BPR, order block, breaker block and rejection block
- Wave-touch detection around 112/224/448/896 using ATR zones
- Wyckoff accumulation/distribution phase hypotheses
- Classical patterns: H&S, inverse H&S, double/triple top/bottom, Adam & Eve, triangles, wedges, flags and cup-and-handle

## Phase 4 — Planned

- Cross-exchange verification: Binance spot/perpetual plus an independent USD venue
- Missing-data reconciliation and live data extension
- Session and weekday stability
- Regime walk-forward testing
- Fees, slippage and realistic entry-at-next-bar assumptions
- Sensitivity tests for every threshold
- False-discovery control and multiple-testing correction

## Phase 5 — Planned

- Compact, interpretable scoring engine
- LONG / SHORT / WAIT plus large-move risk
- Explicit confirmation, invalidation and target prices
- Non-repainting Pine Script implementation
- Daily 09:15 KST TradingView panel and alerts
- Paper-trading audit log before any live-use claim

## Promotion gate for a live rule

A rule is eligible only when it has:

- consistent direction in train, validation and untouched test;
- adequate independent sample count;
- positive after-cost expectancy;
- acceptable maximum adverse excursion and drawdown;
- stability across nearby parameter values and at least two venues;
- no look-ahead, repainting or discretionary relabeling.
