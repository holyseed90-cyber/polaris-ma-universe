# BTC Candlestick Master Research — Phase 2

## Purpose

This phase tests **2–5 candle sequences**, removes overlapping events, evaluates target-before-stop ordering in ATR units, and verifies whether location and completed higher-timeframe context improve out-of-sample performance.

## Guardrails

- Direction is chosen from 2018–2022 training data only.
- Validation (2023–2024) and untouched test (2025–present) must retain the same directional edge.
- Events closer than the ranking horizon are de-duplicated.
- If target and stop are both crossed within one OHLC bar, the event is marked ambiguous rather than guessed.
- Higher-timeframe context becomes available only after its candle has closed.

## Data

- 1h: 76,052 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T23:00:00+00:00
- 4h: 19,028 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T20:00:00+00:00
- 12h: 6,347 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T12:00:00+00:00
- 1d: 3,174 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T00:00:00+00:00

## Consistent sequence candidates

No exact 2–5 candle sequence passed the conservative train/validation/test gates.

## Interpretation

This is a useful negative result: literal candle-shape memorization is too brittle. Phase 3 must replace exact token matching with similarity clustering and combine candle flow with wave structure, support/resistance flips, liquidity sweeps, FVG/order-block definitions, session behavior, and walk-forward transaction-cost testing before any TradingView signal is promoted.
