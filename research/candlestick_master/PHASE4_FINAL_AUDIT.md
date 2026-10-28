# BTC Candlestick Master — Phase 4 Final Audit

## Decision

The current composite score **does not pass the promotion gate for live TradingView LONG/SHORT signals**. It improves some subgroups, especially selected 4h long and sparse 1d setups, but the strict no-overlap portfolio remains negative after costs and no score tier survives the multiple-testing audit at q < 0.05.

This is a research rejection, not a claim that candlestick or moving-average information has no value. It means the present combination and calibration are not yet robust enough for live use.

## Source discipline

The uploaded technical-analysis atlas and the Bondweb curriculum were used only to generate hypotheses: candlestick confirmation, market structure, Spring/Upthrust, moving-average location and spacing, sessions/Kill Zones, and multi-factor confluence. All promotion decisions below come from BTC data, not from the source diagrams.

## Final Phase 4 design

- Venues loaded: Binance spot, Binance perpetual, Coinbase spot, Bitstamp spot.
- Cross-venue signal rows: 41,767.
- Canonical outcome venue: Binance spot.
- Canonical model event rows: 11,041.
- Other venues are used only as strictly causal same-time or already-observed confirmation; later signals are never used.
- Target grid: 0.75, 1.0, 1.5, 2.0 ATR.
- Stop grid: 0.75, 1.0, 1.25 ATR.
- Holding-period grid: three alternatives for each of 1h, 4h, 12h and 1d.
- Total cached target/stop/holding configurations: 288.
- Entry: next bar open.
- Round-trip cost: 20 bps per trade.
- Same-bar target and stop: counted as stop.
- Overlapping live positions: removed in the strict portfolio.

### Nested expanding walk-forward

For every test year:

1. Target/stop/holding configuration is selected using an inner validation year contained entirely inside the training period.
2. Score contributions are then fitted on the full outer training period.
3. Score threshold is selected on a separate outer validation year.
4. The following calendar year is tested without re-fitting.

The four untouched annual tests are 2023, 2024, 2025 and the available portion of 2026.

## Sample counts

- Walk-forward scored test events: 4,968.
- Validation-threshold-selected events: 1,747.
- Strict no-overlap portfolio events: 932.
- Score-factor contribution rows: 1,325.

## Strict no-overlap result

| Metric | Result |
|---|---:|
| Trades | 932 |
| Win rate | 52.47% |
| Win-rate 95% Wilson interval | 49.26%–55.66% |
| Mean net return per trade | -0.0320% |
| Median net return per trade | +0.1513% |
| Profit factor | 0.9543 |
| Maximum drawdown | -47.25% |
| Maximum losing streak | 6 |
| One-sided t-test p-value for mean > 0 | 0.706 |
| Monthly block-bootstrap 95% interval for mean trade | -0.156% to +0.096% |

The positive median with a negative mean shows that many small wins are offset by fewer larger losses. A 52% win rate is therefore not sufficient.

## Annual strict-portfolio stability

| Test year | Trades | Win rate | Mean net/trade | Sum of trade returns |
|---|---:|---:|---:|---:|
| 2023 | 211 | 51.18% | -0.0727% | -15.34% |
| 2024 | 246 | 58.94% | +0.0083% | +2.04% |
| 2025 | 225 | 49.33% | -0.0561% | -12.63% |
| 2026 partial | 250 | 50.00% | -0.0156% | -3.91% |

There is no stable positive annual sequence. 2024 is only marginally positive, while 2023, 2025 and 2026 are negative.

## Walk-forward cells

There are 32 timeframe × side × test-year cells.

- Selected mean return was positive in 9 of 32 cells.
- Selection improved mean return versus the unfiltered baseline in 16 of 32 cells.
- Only 5 cells had both at least 20 selected events and a positive selected mean.
- The chosen target/stop/holding configuration was not stable across years, another sign of regime dependence.

## Aggregate selected performance by timeframe and side

| Timeframe | Side | Selected n | Win rate | Mean net/trade | Profit factor | Decision |
|---|---|---:|---:|---:|---:|---|
| 1h | Long | 358 | 41.3% | -0.210% | 0.642 | Reject |
| 1h | Short | 431 | 51.5% | -0.105% | 0.733 | Reject |
| 4h | Long | 238 | 52.1% | +0.173% | 1.245 | Research candidate only |
| 4h | Short | 234 | 57.7% | -0.125% | 0.790 | Reject |
| 12h | Long | 149 | 43.0% | -0.412% | 0.665 | Reject |
| 12h | Short | 208 | 55.3% | -0.300% | 0.757 | Reject |
| 1d | Long | 58 | 60.3% | +1.309% | 1.868 | Sparse/unstable candidate |
| 1d | Short | 71 | 60.6% | +0.077% | 1.047 | Too weak |

### 4h long regime decay

The 4h-long score is positive in aggregate, but its annual selected means are:

- 2023: +0.242% on 144 events.
- 2024: +0.925% on 21 events.
- 2025: -0.078% on 61 events.
- 2026: -0.698% on 12 events.

It worked in 2023–2024 and deteriorated in 2025–2026, so it cannot be treated as a stationary rule.

### 1d long sparsity

The 1d-long aggregate is attractive, but yearly selected samples are 25, 3, 26 and 4. One year contains three losing trades and the strongest years have very small samples. It is not ready for promotion.

## Multiple-testing and calibration audit

No score tier survives Benjamini–Hochberg correction at q < 0.05.

The best nominal tier was 1d-long score 55–60:

- n = 8.
- Mean net return = +2.479%.
- Profit factor = 9.31.
- Raw p = 0.0051.
- BH-adjusted q = 0.2082.

The raw result looks strong, but eight trades are insufficient after accounting for the many tested score tiers.

## Surviving pattern hypotheses, not live rules

These pooled selected subsets remain worth forward study:

- 1d bullish 3×-body upper-half hold: n 26, mean +1.437%, PF 2.13; yearly samples remain sparse and inconsistent.
- 4h low sweep with RSI 30–40: n 35, mean +0.409%, PF 1.82; most evidence is concentrated in 2023.
- 4h confirmed Upthrust short: n 16, mean +0.212%, PF 1.82; evidence is concentrated in a small number of years.
- 1d bearish 3×-body lower-half hold: n 17, mean +0.185%, PF 1.12; too weak and sparse.

## What was falsified in Phase 4

- More conditions do not automatically create a better system.
- A higher in-sample score does not guarantee a positive next-year expectancy.
- Win rate alone is misleading; the strict portfolio won 52.47% but lost money.
- Broad 1h candle signals remain too noisy after costs.
- A single expanding-history model is not stationary enough across 2023–2026.
- Cross-venue agreement is useful as context, but it does not rescue a weak base setup by itself.

## Phase 5 requirements

1. Remove all 1h and 12h families that failed the walk-forward gate.
2. Rebuild only the 4h-long and sparse 1d candidate families with rolling 12/24-month regime models rather than a single expanding-history model.
3. Add clustered/month-block inference directly to the promotion gate.
4. Stress costs at 20, 30 and 50 bps and add realistic position sizing.
5. Build separate Binance spot and perpetual models; do not mix their outcomes.
6. Require positive expectancy in consecutive forward windows, not merely pooled data.
7. Begin a truly unseen paper-trading audit after the research freeze date.
8. Create Pine Script only after those gates pass; until then the correct TradingView output is WAIT, not LONG/SHORT.

## Progress

- Completed: 83%.
- Remaining: 17%.
