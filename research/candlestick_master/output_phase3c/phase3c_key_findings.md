# BTC Candlestick Master Phase 3C — Key Findings

## Scope and sample

- 1h bars: 76,052
- 4h bars: 19,028
- 12h bars: 6,347
- 1d bars: 3,174
- Next-MA ladder events: 13,504
- Independent MA touch events: 27,839
- Support-migration events: 12,029
- 3x-body confirmation events: 6,690

All claims use 2018–2022 training, 2023–2024 validation, and 2025–present untouched test periods.

## 1. Next-MA ladder: ATR distance dominates

Weighted across all tested MA pairs, directions and timeframes, the probability that the next MA was reached before the short MA cancellation was:

| MA gap | Train | Validation | Untouched test |
|---|---:|---:|---:|
| <1 ATR | 85.6% | 84.2% | 84.9% |
| 1–2 ATR | 54.6% | 54.4% | 57.3% |
| 2–3 ATR | 41.2% | 42.6% | 41.3% |
| 3–4 ATR | 36.4% | 38.1% | 35.2% |
| ≥4 ATR | 32.0% | 25.9% | 27.8% |

This is a path probability, not a strategy win rate.

Important examples:

- 1h MA112→224, gap <1 ATR, downward path: 91.8% / 96.0% / 94.7%.
- 1h MA112→224, gap <1 ATR, upward path: 90.1% / 100.0% / 93.5%.
- 1h MA224→448, gap <1 ATR: test 83.3% downward (n=12) and 73.7% upward (n=19); promising but smaller samples.
- Once the 1h MA112→224 gap was ≥4 ATR, test rates fell to 15.0% downward and 29.4% upward.

Rule change: a named “next MA target” is not valid without its live ATR distance.

## 2. First versus repeated MA contact

Among rows with at least eight decided first-touch and third-plus-touch events:

- All support/resistance modes combined: defense rate declined in 56.3% of rows; favorable excursion declined in 59.4%.
- Rising-MA support only: defense rate and favorable excursion each declined in 71.4% of rows.
- Falling-MA resistance only: results were mixed (44.4% defense-rate decline; 50.0% favorable-excursion decline).

Examples in the untouched test:

- 1h rising MA112 support: 50.9% first touch → 38.5% third-plus.
- 1h rising MA896 support: 40.8% → 26.7%.
- 4h rising MA224 support: 52.4% → 40.0%.
- 1h rising MA56 support: 49.3% → 40.0%.
- Exception: 1h rising MA448 support improved from 41.9% to 64.3%; repeated contact is not universally weak.

Rule change: repeated support contact is a risk flag, not automatically bullish; resistance contact must be studied separately.

## 3. MA slope acceleration and curvature

With at least eight events in both states:

- All acceleration/curvature rows combined: flattening weakened first-touch defense in only 51.2% — not sufficient alone.
- Linear-regression acceleration alone was inconsistent.
- Five-bar second-difference curvature was more useful for rising-MA support: flattening weakened defense in 63.6% of rows, with an average difference of about -5.9 percentage points.

Examples:

- 1h MA112 rising support, LR acceleration with trend vs flattening: 59.6% vs 43.5%.
- 1h MA28 rising support, curvature with trend vs flattening: 56.6% vs 45.9%.
- 4h MA224 rising support, curvature with trend vs flattening: 75.0% vs 38.5% (small samples).
- Counterexample: 1h MA448 rising support, LR acceleration with trend vs flattening: 29.4% vs 50.0%.

Rule change: curvature is a modifier, never a standalone signal.

## 4. Support migration

Weighted 1-ATR target-first rates:

| Migration | Train | Validation | Test |
|---|---:|---:|---:|
| Longer MA → shorter MA | 50.2% | 51.6% | 51.0% |
| Same MA | 48.6% | 49.3% | 47.5% |
| Shorter MA → longer MA | 46.9% | 50.2% | 48.1% |

The direction is mildly consistent, but the absolute edge is too small for a signal. Support migration can be one scoring input only.

## 5. 3x average-body candle confirmation

Most 1h confirmation patterns failed to remain stable. A large candle by itself was not predictive.

Candidates that kept the same positive direction across all three splits:

- 4h bullish 3x body followed by a close above its high: 57.5% / 59.6% / 52.8%; test median +0.10% (n=36).
- 12h bullish 3x body followed by a close above its high: 55.3% / 75.0% / 71.4%; test n=7, too small for promotion.
- 1d bullish 3x body followed by an upper-half hold: 64.3% / 64.7% / 77.8%; test n=9, promising but too small.

Rule change: use 3x-body structure only after confirmation and primarily on 4h/12h/1d; do not use it as a 1h standalone signal.

## Promotion decisions

### Promote to core structural rule

- Next-MA target probability must be conditioned on ATR distance.
- <1 ATR is a high-probability path zone; 1–2 ATR is moderate; >2 ATR is no longer a default target.

### Keep as secondary scoring inputs

- Repeated rising-MA support contact count.
- MA curvature state.
- Longer-to-shorter support migration.
- Confirmed 4h/12h/1d 3x-body structures.

### Reject as standalone rules

- MA name alone as a target.
- “Third touch always breaks.”
- Simple slope acceleration alone.
- A 3x body candle without confirmation.

## Research progress

- Completed: 63%
- Remaining: 37%
