# BTC Candlestick Master — Phase 3D

## Scope

Cross-venue replication, Binance spot-versus-perpetual comparison, current-data extension, next-bar entry, 1-ATR target/stop, conservative same-bar ambiguity, 0/10/20/30 bps round-trip cost scenarios, KST kill-zone and weekday stability.

The technical-analysis atlas defines separate Asia, London and New York sessions and kill zones. This phase treats those time windows as hypotheses rather than proof and tests them on each venue independently.

## Data acquisition

| venue         | status   |   bars | start                     | end                       |   missing_hours |
|:--------------|:---------|-------:|:--------------------------|:--------------------------|----------------:|
| binance_spot  | ok       |  77208 | 2018-01-01T00:00:00+00:00 | 2026-10-27T23:00:00+00:00 |             163 |
| binance_perp  | ok       |  59808 | 2020-01-01T00:00:00+00:00 | 2026-10-27T23:00:00+00:00 |               0 |
| coinbase_spot | ok       |  77305 | 2018-01-01T00:00:00+00:00 | 2026-10-28T17:00:00+00:00 |              41 |
| bitstamp_spot | ok       |  77345 | 2018-01-01T00:00:00+00:00 | 2026-10-28T16:00:00+00:00 |               0 |

## Cross-venue test-period consistency after 20 bps costs

| timeframe   | rule                    | side   |   venues_tested |   venues_positive |   positive_fraction |   weighted_n |   weighted_win_rate |   weighted_mean_net_pct |   worst_venue_mean_net_pct |   best_venue_mean_net_pct | positive_venues                                       |
|:------------|:------------------------|:-------|----------------:|------------------:|--------------------:|-------------:|--------------------:|------------------------:|---------------------------:|--------------------------:|:------------------------------------------------------|
| 1d          | bear_3x_lower_half_hold | short  |               4 |                 4 |               1.000 |           60 |               0.600 |                   0.217 |                      0.204 |                     0.226 | binance_perp,binance_spot,bitstamp_spot,coinbase_spot |
| 4h          | spring_confirm          | long   |               4 |                 4 |               1.000 |          107 |               0.579 |                   0.154 |                      0.104 |                     0.252 | binance_perp,binance_spot,bitstamp_spot,coinbase_spot |
| 4h          | upthrust_confirm        | short  |               4 |                 4 |               1.000 |          130 |               0.600 |                   0.099 |                      0.051 |                     0.143 | binance_perp,binance_spot,bitstamp_spot,coinbase_spot |
| 12h         | spring_broad_bear       | long   |               4 |                 4 |               1.000 |           54 |               0.519 |                   0.077 |                      0.002 |                     0.158 | binance_perp,binance_spot,bitstamp_spot,coinbase_spot |
| 12h         | high_sweep_broad_bull   | short  |               4 |                 3 |               0.750 |          102 |               0.588 |                   0.087 |                     -0.012 |                     0.160 | binance_spot,bitstamp_spot,coinbase_spot              |
| 12h         | low_sweep_rsi30_40      | long   |               4 |                 2 |               0.500 |           97 |               0.557 |                  -0.023 |                     -0.219 |                     0.122 | binance_perp,binance_spot                             |
| 12h         | upthrust_broad_bull     | short  |               4 |                 1 |               0.250 |           66 |               0.500 |                  -0.099 |                     -0.249 |                     0.064 | bitstamp_spot                                         |
| 4h          | bear_3x_break_low       | short  |               4 |                 0 |               0.000 |          181 |               0.503 |                  -0.047 |                     -0.061 |                    -0.024 |                                                       |
| 1h          | upthrust_broad_bull     | short  |               4 |                 0 |               0.000 |          559 |               0.547 |                  -0.102 |                     -0.115 |                    -0.089 |                                                       |
| 4h          | upthrust_broad_bull     | short  |               4 |                 0 |               0.000 |          196 |               0.495 |                  -0.114 |                     -0.123 |                    -0.095 |                                                       |
| 12h         | bear_3x_lower_half_hold | short  |               4 |                 0 |               0.000 |          114 |               0.544 |                  -0.119 |                     -0.194 |                    -0.043 |                                                       |
| 1h          | upthrust_confirm        | short  |               4 |                 0 |               0.000 |          452 |               0.533 |                  -0.120 |                     -0.139 |                    -0.096 |                                                       |
| 4h          | bear_3x_lower_half_hold | short  |               4 |                 0 |               0.000 |          459 |               0.473 |                  -0.125 |                     -0.137 |                    -0.109 |                                                       |
| 1h          | high_sweep_rsi60_70     | short  |               4 |                 0 |               0.000 |          740 |               0.503 |                  -0.150 |                     -0.180 |                    -0.128 |                                                       |
| 1h          | high_sweep_broad_bull   | short  |               4 |                 0 |               0.000 |          888 |               0.510 |                  -0.150 |                     -0.174 |                    -0.133 |                                                       |
| 12h         | spring_confirm          | long   |               4 |                 0 |               0.000 |           41 |               0.488 |                  -0.162 |                     -0.292 |                    -0.112 |                                                       |
| 4h          | bull_3x_break_high      | long   |               4 |                 0 |               0.000 |          166 |               0.524 |                  -0.166 |                     -0.190 |                    -0.141 |                                                       |
| 12h         | bear_3x_break_low       | short  |               4 |                 0 |               0.000 |           52 |               0.538 |                  -0.168 |                     -0.176 |                    -0.162 |                                                       |
| 1h          | low_sweep_broad_bear    | long   |               4 |                 0 |               0.000 |          886 |               0.491 |                  -0.214 |                     -0.229 |                    -0.198 |                                                       |
| 1h          | spring_broad_bear       | long   |               4 |                 0 |               0.000 |          598 |               0.493 |                  -0.223 |                     -0.232 |                    -0.211 |                                                       |
| 4h          | high_sweep_broad_bull   | short  |               4 |                 0 |               0.000 |          350 |               0.477 |                  -0.242 |                     -0.257 |                    -0.236 |                                                       |
| 1d          | bull_3x_upper_half_hold | long   |               4 |                 0 |               0.000 |           68 |               0.471 |                  -0.253 |                     -0.255 |                    -0.250 |                                                       |
| 1h          | low_sweep_rsi30_40      | long   |               4 |                 0 |               0.000 |          692 |               0.457 |                  -0.258 |                     -0.288 |                    -0.236 |                                                       |
| 4h          | bull_3x_upper_half_hold | long   |               4 |                 0 |               0.000 |          371 |               0.482 |                  -0.263 |                     -0.298 |                    -0.249 |                                                       |
| 1h          | spring_confirm          | long   |               4 |                 0 |               0.000 |          432 |               0.465 |                  -0.269 |                     -0.330 |                    -0.240 |                                                       |
| 4h          | high_sweep_rsi60_70     | short  |               4 |                 0 |               0.000 |          238 |               0.462 |                  -0.269 |                     -0.315 |                    -0.220 |                                                       |
| 4h          | low_sweep_broad_bear    | long   |               4 |                 0 |               0.000 |          335 |               0.427 |                  -0.295 |                     -0.310 |                    -0.279 |                                                       |
| 12h         | upthrust_confirm        | short  |               4 |                 0 |               0.000 |           43 |               0.419 |                  -0.307 |                     -0.550 |                    -0.162 |                                                       |
| 12h         | low_sweep_broad_bear    | long   |               4 |                 0 |               0.000 |          117 |               0.496 |                  -0.356 |                     -0.437 |                    -0.192 |                                                       |
| 12h         | high_sweep_rsi60_70     | short  |               4 |                 0 |               0.000 |           72 |               0.486 |                  -0.379 |                     -0.489 |                    -0.333 |                                                       |
| 12h         | bull_3x_upper_half_hold | long   |               4 |                 0 |               0.000 |          109 |               0.486 |                  -0.463 |                     -0.570 |                    -0.400 |                                                       |
| 4h          | low_sweep_rsi30_40      | long   |               4 |                 0 |               0.000 |          243 |               0.391 |                  -0.471 |                     -0.539 |                    -0.413 |                                                       |
| 4h          | spring_broad_bear       | long   |               4 |                 0 |               0.000 |          196 |               0.347 |                  -0.475 |                     -0.498 |                    -0.458 |                                                       |
| 1d          | low_sweep_rsi30_40      | long   |               4 |                 0 |               0.000 |           42 |               0.429 |                  -0.951 |                     -1.098 |                    -0.813 |                                                       |
| 1d          | high_sweep_broad_bull   | short  |               4 |                 0 |               0.000 |           48 |               0.292 |                  -1.095 |                     -1.278 |                    -0.912 |                                                       |
| 1d          | low_sweep_broad_bear    | long   |               4 |                 0 |               0.000 |           40 |               0.300 |                  -1.849 |                     -1.866 |                    -1.840 |                                                       |

A rule is not promoted merely because its weighted result is positive. The worst venue, sample size, all three historical splits, profit factor and drawdown must also be acceptable.

## Venue-level rules positive in train, validation and untouched test after 20 bps

| venue        | timeframe   | rule                    | side   |   n_train |   n_validation |   n_test |   mean_net_pct_train |   mean_net_pct_validation |   mean_net_pct_test |   win_rate_test |   profit_factor_test |   max_drawdown_pct_test |   min_split_mean |
|:-------------|:------------|:------------------------|:-------|----------:|---------------:|---------:|---------------------:|--------------------------:|--------------------:|----------------:|---------------------:|------------------------:|-----------------:|
| binance_perp | 12h         | low_sweep_rsi30_40      | long   |        34 |             24 |       24 |                0.151 |                     0.175 |               0.122 |           0.583 |                1.119 |                 -14.467 |            0.122 |
| binance_spot | 1d          | bear_3x_lower_half_hold | short  |        39 |             16 |       15 |                0.846 |                     0.048 |               0.204 |           0.600 |                1.124 |                  -9.944 |            0.048 |
| binance_perp | 1d          | bear_3x_lower_half_hold | short  |        25 |             16 |       15 |                1.539 |                     0.047 |               0.217 |           0.600 |                1.131 |                 -10.008 |            0.047 |

## Next-MA ladder replication by venue and ATR gap

| timeframe   |   short_ma |   long_ma | direction   | gap_bin   |   venues_tested |   decided |   weighted_target_rate |   minimum_venue_rate |   maximum_venue_rate |   venues_ge_60pct |
|:------------|-----------:|----------:|:------------|:----------|----------------:|----------:|-----------------------:|---------------------:|---------------------:|------------------:|
| 1h          |        112 |       224 | down        | lt1       |               4 |        51 |                  0.961 |                0.909 |                1.000 |                 4 |
| 4h          |        112 |       224 | up          | 1to2      |               4 |        36 |                  0.889 |                0.889 |                0.889 |                 4 |
| 1h          |        112 |       224 | up          | lt1       |               4 |        46 |                  0.870 |                0.833 |                0.909 |                 4 |
| 1h          |        112 |       224 | up          | 1to2      |               4 |        36 |                  0.861 |                0.800 |                1.000 |                 4 |
| 1h          |        224 |       448 | up          | 1to2      |               4 |        44 |                  0.818 |                0.818 |                0.818 |                 4 |
| 1h          |        224 |       448 | down        | lt1       |               4 |        33 |                  0.818 |                0.750 |                0.889 |                 4 |
| 1h          |        112 |       224 | up          | 3to4      |               4 |        37 |                  0.649 |                0.600 |                0.700 |                 4 |
| 1h          |        112 |       224 | up          | 2to3      |               4 |        42 |                  0.643 |                0.545 |                0.700 |                 3 |
| 1h          |        112 |       224 | down        | 2to3      |               4 |        51 |                  0.608 |                0.571 |                0.636 |                 3 |
| 1h          |        448 |       896 | down        | ge4       |               4 |        59 |                  0.593 |                0.571 |                0.600 |                 3 |
| 1h          |        224 |       448 | up          | ge4       |               4 |        64 |                  0.500 |                0.500 |                0.500 |                 0 |
| 4h          |        224 |       448 | up          | ge4       |               4 |        45 |                  0.467 |                0.455 |                0.500 |                 0 |
| 1h          |        112 |       224 | up          | ge4       |               4 |        62 |                  0.435 |                0.429 |                0.438 |                 0 |
| 4h          |        224 |       448 | down        | ge4       |               4 |        37 |                  0.405 |                0.333 |                0.444 |                 0 |
| 1h          |        112 |       224 | down        | 3to4      |               4 |        40 |                  0.400 |                0.400 |                0.400 |                 0 |
| 1h          |        224 |       448 | down        | ge4       |               4 |        70 |                  0.371 |                0.353 |                0.389 |                 0 |
| 1h          |        448 |       896 | up          | ge4       |               4 |        59 |                  0.322 |                0.286 |                0.333 |                 0 |
| 1h          |        112 |       224 | down        | ge4       |               4 |        52 |                  0.308 |                0.286 |                0.333 |                 0 |
| 1h          |        224 |       448 | down        | 2to3      |               3 |        26 |                  0.615 |                0.600 |                0.625 |                 3 |
| 4h          |        112 |       224 | up          | lt1       |               2 |        18 |                  0.889 |                0.889 |                0.889 |                 2 |
| 1h          |        224 |       448 | down        | 1to2      |               1 |         9 |                  0.667 |                0.667 |                0.667 |                 1 |
| 1h          |        224 |       448 | up          | 3to4      |               1 |         8 |                  0.625 |                0.625 |                0.625 |                 1 |

The ladder statistic is a path probability, not a trade win rate. It asks whether the next MA was touched before price reclaimed the broken short MA.

## KST kill-zone results after 20 bps

| timeframe   | rule                    | side   | kill_zone   |   venues_tested |   venues_positive |   n |   weighted_win_rate |   weighted_mean_net_pct |
|:------------|:------------------------|:-------|:------------|----------------:|------------------:|----:|--------------------:|------------------------:|
| 4h          | spring_confirm          | long   | other       |               4 |                 4 |  67 |               0.731 |                   0.452 |
| 4h          | bear_3x_lower_half_hold | short  | newyork_kz  |               4 |                 4 |  35 |               0.800 |                   0.365 |
| 4h          | bear_3x_lower_half_hold | short  | asia_kz     |               4 |                 4 |  75 |               0.573 |                   0.285 |
| 1h          | high_sweep_rsi60_70     | short  | asia_kz     |               4 |                 4 |  64 |               0.766 |                   0.278 |
| 12h         | high_sweep_broad_bull   | short  | newyork_kz  |               4 |                 4 |  62 |               0.629 |                   0.256 |
| 4h          | high_sweep_rsi60_70     | short  | asia_kz     |               4 |                 4 |  48 |               0.667 |                   0.247 |
| 1d          | bear_3x_lower_half_hold | short  | asia_kz     |               4 |                 4 |  60 |               0.600 |                   0.217 |
| 12h         | upthrust_broad_bull     | short  | newyork_kz  |               4 |                 4 |  40 |               0.625 |                   0.216 |
| 4h          | high_sweep_broad_bull   | short  | asia_kz     |               4 |                 4 |  61 |               0.607 |                   0.099 |
| 4h          | bear_3x_break_low       | short  | other       |               4 |                 4 | 117 |               0.504 |                   0.086 |
| 4h          | upthrust_broad_bull     | short  | asia_kz     |               4 |                 4 |  41 |               0.585 |                   0.046 |
| 12h         | low_sweep_broad_bear    | long   | newyork_kz  |               4 |                 3 |  45 |               0.622 |                   0.146 |
| 12h         | low_sweep_rsi30_40      | long   | newyork_kz  |               4 |                 3 |  45 |               0.622 |                   0.108 |
| 1h          | upthrust_broad_bull     | short  | london_kz   |               4 |                 3 |  54 |               0.741 |                   0.029 |
| 4h          | spring_broad_bear       | long   | newyork_kz  |               4 |                 3 |  33 |               0.485 |                   0.016 |
| 4h          | upthrust_broad_bull     | short  | other       |               4 |                 3 | 117 |               0.513 |                   0.006 |
| 12h         | low_sweep_rsi30_40      | long   | asia_kz     |               4 |                 2 |  52 |               0.500 |                  -0.137 |
| 12h         | upthrust_confirm        | short  | asia_kz     |               2 |                 1 |  16 |               0.500 |                  -0.003 |
| 4h          | upthrust_confirm        | short  | other       |               4 |                 1 |  69 |               0.536 |                  -0.054 |
| 1h          | upthrust_broad_bull     | short  | asia_kz     |               4 |                 1 |  49 |               0.449 |                  -0.055 |
| 12h         | high_sweep_rsi60_70     | short  | newyork_kz  |               4 |                 1 |  38 |               0.553 |                  -0.085 |
| 4h          | low_sweep_broad_bear    | long   | newyork_kz  |               4 |                 1 |  50 |               0.440 |                  -0.085 |
| 12h         | high_sweep_broad_bull   | short  | asia_kz     |               4 |                 1 |  40 |               0.525 |                  -0.175 |
| 1h          | upthrust_confirm        | short  | other       |               4 |                 0 | 284 |               0.570 |                  -0.059 |
| 1h          | upthrust_confirm        | short  | newyork_kz  |               4 |                 0 |  53 |               0.623 |                  -0.064 |
| 4h          | bull_3x_upper_half_hold | long   | other       |               4 |                 0 | 228 |               0.553 |                  -0.073 |
| 1h          | low_sweep_broad_bear    | long   | asia_kz     |               4 |                 0 |  93 |               0.538 |                  -0.080 |
| 1h          | high_sweep_broad_bull   | short  | asia_kz     |               4 |                 0 |  91 |               0.495 |                  -0.088 |
| 4h          | bull_3x_break_high      | long   | other       |               4 |                 0 | 112 |               0.554 |                  -0.093 |
| 1h          | upthrust_broad_bull     | short  | other       |               4 |                 0 | 380 |               0.553 |                  -0.107 |
| 1h          | high_sweep_broad_bull   | short  | london_kz   |               4 |                 0 | 108 |               0.602 |                  -0.109 |
| 1h          | high_sweep_broad_bull   | short  | newyork_kz  |               4 |                 0 | 140 |               0.507 |                  -0.115 |
| 4h          | low_sweep_broad_bear    | long   | other       |               4 |                 0 | 179 |               0.492 |                  -0.116 |
| 4h          | spring_broad_bear       | long   | asia_kz     |               4 |                 0 |  51 |               0.529 |                  -0.135 |
| 1h          | high_sweep_rsi60_70     | short  | newyork_kz  |               4 |                 0 | 110 |               0.473 |                  -0.163 |
| 1h          | high_sweep_rsi60_70     | short  | other       |               4 |                 0 | 480 |               0.502 |                  -0.163 |
| 1h          | spring_broad_bear       | long   | other       |               4 |                 0 | 422 |               0.538 |                  -0.176 |
| 1h          | high_sweep_broad_bull   | short  | other       |               4 |                 0 | 549 |               0.495 |                  -0.178 |
| 1h          | upthrust_broad_bull     | short  | newyork_kz  |               4 |                 0 |  76 |               0.447 |                  -0.200 |
| 1h          | low_sweep_broad_bear    | long   | other       |               4 |                 0 | 653 |               0.518 |                  -0.200 |

## Binance spot-versus-perpetual candle comparison

| metric                       |     value |
|:-----------------------------|----------:|
| common_hours                 | 59777.000 |
| median_basis_bps             |    -3.766 |
| p95_abs_basis_bps            |    10.549 |
| median_spot_range_pct        |     0.628 |
| median_perp_range_pct        |     0.639 |
| p95_perp_to_spot_range_ratio |     1.113 |

## Binance spot-versus-perpetual signal agreement

| rule                  |   spot_signals |   perp_signals |   exact_jaccard |   spot_matched_within_1h |
|:----------------------|---------------:|---------------:|----------------:|-------------------------:|
| spring_broad_bear     |            952 |            743 |           0.714 |                    0.744 |
| spring_confirm        |            484 |            386 |           0.703 |                    0.744 |
| upthrust_broad_bull   |           1062 |            849 |           0.687 |                    0.738 |
| low_sweep_rsi30_40    |           1503 |           1212 |           0.679 |                    0.749 |
| upthrust_confirm      |            511 |            384 |           0.676 |                    0.706 |
| low_sweep_broad_bear  |           2282 |           1812 |           0.674 |                    0.740 |
| high_sweep_rsi60_70   |           1573 |           1266 |           0.665 |                    0.744 |
| high_sweep_broad_bull |           2551 |           2063 |           0.661 |                    0.746 |

## Research interpretation

- A candle rule that works on Binance but fails on Coinbase/Bitstamp is treated as venue-specific, not universal.
- Perpetual-futures wick behavior is not silently substituted for spot behavior.
- Costs are deducted from every trade, including time exits.
- The next-bar open is used for entry; the signal candle close is never used as a fill price.
- If both target and stop occur inside the same OHLC candle, the result is conservatively recorded as a stop.
- Kill-zone superiority must appear across venues, not only in a pooled Binance sample.

## Next phase

Phase 4 will build an interpretable composite score from only cross-venue-surviving components, run rolling walk-forward threshold selection, test several target/stop ratios and maximum holding periods, and create a non-repainting Pine prototype. It will remain a research indicator until paper-trading audit results are available.

## Progress

- Completed: 72%
- Remaining: 28%