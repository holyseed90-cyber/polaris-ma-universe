# BTC Candlestick Master — Phase 3A

## Scope

Confirmed-pivot market structure, SFP/Spring/Upthrust, BoS/CHoCH, first retest, 20-bar liquidity sweeps, FVG creation, contraction→expansion, and independent 112/224/448/896 MA wave touches.

## Source-derived hypotheses

The uploaded technical-analysis atlas treats support/resistance flips, market structure (BoS/CHoCH), Spring/Upthrust, liquidity, FVG, order blocks and contraction/expansion as distinct price-action concepts. Phase 3A tests the objectively codable subset; order-block and Wyckoff phase models remain for Phase 3B.

## Data
- 1h: 76,052 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T23:00:00+00:00
- 4h: 19,028 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T20:00:00+00:00
- 12h: 6,347 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T12:00:00+00:00
- 1d: 3,174 bars, 2018-01-01T00:00:00+00:00 → 2026-09-09T00:00:00+00:00

## Events surviving all three splits

| timeframe   | event            | direction   |   train_n |   validation_n |   test_n |   train_win_rate |   validation_win_rate |   test_win_rate |   test_median_signed_ret |   test_median_mfe_atr |   test_median_mae_atr |
|:------------|:-----------------|:------------|----------:|---------------:|---------:|-----------------:|----------------------:|----------------:|-------------------------:|----------------------:|----------------------:|
| 4h          | bear_retest_fail | bullish     |        67 |             39 |       28 |            0.552 |                 0.641 |           0.571 |                    0.738 |                 1.800 |                -0.945 |
| 1h          | bull_spring      | bullish     |       578 |            231 |      155 |            0.536 |                 0.563 |           0.555 |                    0.140 |                 2.263 |                -1.659 |
| 1h          | bear_retest_fail | bullish     |       390 |            155 |      134 |            0.597 |                 0.568 |           0.552 |                    0.285 |                 2.357 |                -1.786 |
| 4h          | low_sweep20      | bullish     |       280 |            100 |       92 |            0.554 |                 0.610 |           0.533 |                    0.180 |                 1.453 |                -1.531 |
| 1d          | bull_retest_hold | bullish     |        43 |             20 |       19 |            0.535 |                 0.600 |           0.526 |                    0.182 |                 0.898 |                -0.918 |
| 1h          | low_sweep20      | bullish     |       799 |            334 |      286 |            0.567 |                 0.608 |           0.524 |                    0.103 |                 2.222 |                -2.091 |

## Best test first-passage rows (1 ATR)

| timeframe   | event              | direction   |   events |   target_first |   stop_first |   ambiguous |   no_hit |   decided_win_rate |   wilson_low |   wilson_high |
|:------------|:-------------------|:------------|---------:|---------------:|-------------:|------------:|---------:|-------------------:|-------------:|--------------:|
| 4h          | ma448_bull_defense | bullish     |       11 |              8 |            3 |           0 |        0 |              0.727 |        0.434 |         0.903 |
| 12h         | bear_retest_fail   | bullish     |       14 |              8 |            3 |           0 |        3 |              0.727 |        0.434 |         0.903 |
| 1d          | bear_bos           | bearish     |       21 |             12 |            6 |           0 |        3 |              0.667 |        0.437 |         0.837 |
| 4h          | ma448_bear_reject  | bearish     |       18 |             10 |            6 |           2 |        0 |              0.625 |        0.386 |         0.815 |
| 4h          | bull_spring        | bullish     |       54 |             29 |           19 |           2 |        3 |              0.604 |        0.463 |         0.730 |
| 1h          | bear_retest_fail   | bullish     |      135 |             78 |           52 |           1 |        3 |              0.600 |        0.514 |         0.680 |
| 1h          | ma896_bear_reject  | bearish     |       44 |             25 |           18 |           1 |        0 |              0.581 |        0.433 |         0.716 |
| 12h         | bear_bos           | bearish     |       47 |             25 |           18 |           0 |        4 |              0.581 |        0.433 |         0.716 |
| 4h          | bear_retest_fail   | bullish     |       28 |             15 |           11 |           0 |        2 |              0.577 |        0.389 |         0.745 |
| 12h         | bear_fvg           | bearish     |       75 |             39 |           30 |           0 |        6 |              0.565 |        0.448 |         0.676 |
| 12h         | bear_sfp           | bearish     |       39 |             19 |           15 |           0 |        5 |              0.559 |        0.395 |         0.711 |
| 4h          | bull_sfp           | bullish     |       84 |             43 |           34 |           3 |        4 |              0.558 |        0.447 |         0.664 |
| 1h          | ma448_bear_reject  | bearish     |       72 |             39 |           31 |           1 |        0 |              0.557 |        0.441 |         0.668 |
| 4h          | bull_retest_hold   | bullish     |       74 |             40 |           32 |           2 |        0 |              0.556 |        0.441 |         0.665 |
| 4h          | bear_bos           | bearish     |       95 |             49 |           40 |           1 |        5 |              0.551 |        0.447 |         0.650 |
| 12h         | high_sweep20       | bearish     |       40 |             19 |           16 |           0 |        5 |              0.543 |        0.382 |         0.695 |
| 12h         | ma112_bear_reject  | bearish     |       14 |              7 |            6 |           0 |        1 |              0.538 |        0.291 |         0.768 |
| 12h         | bull_sfp           | bullish     |       39 |             18 |           16 |           0 |        5 |              0.529 |        0.367 |         0.685 |
| 1d          | bull_sfp           | bullish     |       20 |              9 |            8 |           0 |        3 |              0.529 |        0.310 |         0.738 |
| 1h          | bear_fvg           | bearish     |      425 |            218 |          196 |           3 |        7 |              0.527 |        0.478 |         0.574 |
| 1h          | ma112_bear_reject  | bearish     |      145 |             74 |           67 |           2 |        1 |              0.525 |        0.443 |         0.605 |
| 1h          | bear_upthrust      | bearish     |      150 |             75 |           68 |           3 |        3 |              0.524 |        0.443 |         0.605 |
| 1h          | high_sweep20       | bearish     |      290 |            149 |          136 |           4 |        0 |              0.523 |        0.465 |         0.580 |
| 1h          | ma112_bull_defense | bullish     |      126 |             64 |           59 |           2 |        1 |              0.520 |        0.433 |         0.607 |
| 1h          | bull_fvg           | bullish     |      435 |            221 |          205 |           4 |        4 |              0.519 |        0.471 |         0.566 |
| 4h          | ma112_bull_defense | bullish     |       34 |             15 |           14 |           3 |        2 |              0.517 |        0.344 |         0.686 |
| 12h         | bull_bos           | bullish     |       48 |             20 |           19 |           1 |        8 |              0.513 |        0.362 |         0.661 |
| 4h          | bull_fvg           | bullish     |      165 |             82 |           78 |           1 |        4 |              0.512 |        0.436 |         0.589 |
| 4h          | bear_fvg           | bearish     |      165 |             77 |           75 |           4 |        9 |              0.507 |        0.428 |         0.585 |
| 1h          | low_sweep20        | bullish     |      287 |            141 |          138 |           2 |        5 |              0.505 |        0.447 |         0.564 |

## Stable context refinements

| timeframe   | event             | direction   | context      | value           |   train_n |   validation_n |   test_n |   train_win_rate |   validation_win_rate |   test_win_rate |   test_median_signed_ret |
|:------------|:------------------|:------------|:-------------|:----------------|----------:|---------------:|---------:|-----------------:|----------------------:|----------------:|-------------------------:|
| 1h          | bear_retest_fail  | bullish     | rsi_state    | 30_40           |        71 |             17 |       27 |            0.648 |                 0.765 |           0.704 |                    0.686 |
| 1h          | bear_retest_fail  | bullish     | long_state   | long_bear_stack |       118 |             28 |       51 |            0.610 |                 0.607 |           0.608 |                    0.428 |
| 4h          | ma224_bear_reject | bearish     | rsi_state    | 50_60           |        15 |              3 |       10 |            0.600 |                 0.667 |           0.600 |                    1.863 |
| 12h         | bull_fvg          | bullish     | rsi_state    | ge70            |        55 |             34 |       10 |            0.636 |                 0.676 |           0.600 |                    0.722 |
| 1h          | bull_spring       | bullish     | trend_regime | broad_bear      |       145 |             50 |       46 |            0.593 |                 0.640 |           0.609 |                    0.214 |
| 4h          | bear_retest_fail  | bullish     | long_state   | long_mixed      |        22 |              9 |        8 |            0.591 |                 1.000 |           0.750 |                    1.797 |
| 1h          | bull_sfp          | bullish     | rsi_state    | 30_40           |       196 |             66 |       66 |            0.587 |                 0.636 |           0.591 |                    0.151 |
| 1h          | ma896_bear_reject | bearish     | long_state   | long_bear_stack |        25 |              8 |       12 |            0.600 |                 0.750 |           0.583 |                    0.331 |
| 4h          | bull_fvg          | bullish     | trend_regime | broad_bear      |        12 |              4 |       10 |            0.583 |                 1.000 |           0.700 |                    1.127 |
| 1h          | bear_retest_fail  | bullish     | rsi_state    | 40_50           |       229 |            102 |       74 |            0.590 |                 0.588 |           0.581 |                    0.431 |
| 1h          | bear_retest_fail  | bullish     | long_state   | long_mixed      |       143 |             49 |       40 |            0.580 |                 0.633 |           0.575 |                    0.369 |
| 4h          | bull_sfp          | bullish     | long_state   | long_mixed      |        75 |             27 |       33 |            0.573 |                 0.741 |           0.576 |                    0.268 |
| 1d          | bull_retest_hold  | bullish     | rsi_state    | 60_70           |        14 |             11 |        7 |            0.571 |                 0.727 |           0.714 |                    0.871 |
| 1d          | bull_fvg          | bullish     | rsi_state    | ge70            |        29 |             14 |        7 |            0.655 |                 0.643 |           0.571 |                    0.478 |
| 1h          | low_sweep20       | bullish     | trend_regime | broad_bear      |       314 |            103 |      110 |            0.602 |                 0.602 |           0.564 |                    0.334 |
| 1h          | low_sweep20       | bullish     | rsi_state    | 30_40           |       444 |            168 |      161 |            0.579 |                 0.601 |           0.559 |                    0.162 |
| 1h          | bear_retest_fail  | bullish     | trend_regime | broad_bear      |        95 |             33 |       27 |            0.674 |                 0.697 |           0.556 |                    0.232 |
| 1d          | bull_retest_hold  | bullish     | long_state   | long_bull_stack |        15 |              9 |       14 |            0.667 |                 0.556 |           0.643 |                    0.721 |
| 1d          | bear_sfp          | bearish     | rsi_state    | 50_60           |        19 |             11 |        9 |            0.632 |                 0.727 |           0.556 |                    0.490 |
| 4h          | bull_sfp          | bullish     | rsi_state    | 30_40           |        62 |             20 |       16 |            0.565 |                 0.550 |           0.688 |                    1.758 |
| 4h          | bear_upthrust     | bearish     | rsi_state    | 60_70           |        26 |             19 |       11 |            0.615 |                 0.579 |           0.545 |                    0.696 |
| 1h          | low_sweep20       | bullish     | long_state   | long_bear_stack |       264 |             74 |      101 |            0.598 |                 0.568 |           0.545 |                    0.111 |
| 4h          | bull_spring       | bullish     | rsi_state    | 40_50           |        81 |             32 |       30 |            0.543 |                 0.625 |           0.600 |                    0.759 |
| 1h          | bull_sfp          | bullish     | long_state   | long_bear_stack |       278 |             71 |      102 |            0.543 |                 0.563 |           0.559 |                    0.146 |
| 1h          | bull_spring       | bullish     | rsi_state    | 30_40           |       140 |             54 |       42 |            0.543 |                 0.611 |           0.667 |                    0.302 |
| 1h          | bear_retest_hold  | bearish     | rsi_state    | 50_60           |        46 |             22 |       24 |            0.543 |                 0.545 |           0.542 |                    0.144 |
| 4h          | low_sweep20       | bullish     | trend_regime | broad_bear      |       113 |             25 |       37 |            0.540 |                 0.640 |           0.541 |                    0.119 |
| 1d          | bear_sfp          | bearish     | trend_regime | mixed           |        36 |             15 |       13 |            0.583 |                 0.733 |           0.538 |                    0.406 |
| 1d          | low_sweep20       | bullish     | rsi_state    | 30_40           |        26 |              5 |       11 |            0.538 |                 0.600 |           0.545 |                    1.261 |
| 1h          | bear_retest_fail  | bullish     | trend_regime | mixed           |       293 |            123 |      103 |            0.577 |                 0.553 |           0.534 |                    0.243 |

## Interpretation

A surviving event is a research candidate, not a live signal. Phase 3B must test event sequences (e.g., sweep→CHoCH→retest), FVG fill/reaction, three-tap structures, range phase, order-block/breaker definitions and higher-timeframe confluence. Cross-exchange and after-cost testing remain mandatory.