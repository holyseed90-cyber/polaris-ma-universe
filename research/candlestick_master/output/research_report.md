# BTC Candlestick Master Research — Phase 1

## Scope

- Source: Binance BTCUSDT hourly OHLCV
- Period: 2018-01-01T00:00:00+00:00 → 2026-09-09T23:00:00+00:00
- Raw 1h bars: 76,052
- Reconstructed timeframes: 1h, 4h, 12h, 1d
- Signals use only information available at candle close; higher-timeframe context becomes available only after that higher-timeframe candle closes.
- Split: 2018–2022 train, 2023–2024 validation, 2025–present untouched test.

## Pattern language

Traditional candlestick names are treated as labels, not truths. Each pattern is encoded from body/range/wick geometry and then tested by location, market regime, RSI, ATR, session, and higher-timeframe context.

## Data quality

- Missing hourly timestamps: 124
- Duplicate timestamps: 0

## Top out-of-sample candidates

| timeframe   | source_label   | direction   |   n |   ranking_horizon |   edge_score |
|:------------|:---------------|:------------|----:|------------------:|-------------:|
| 1d          | 상승 아웃사이드 바     | bullish     |  23 |                14 |        3.290 |
| 1d          | 트위저 바닥         | bullish     |  33 |                14 |        1.952 |
| 4h          | 흑삼병            | bearish     |  27 |                24 |        1.890 |
| 1d          | 유성형            | bearish     |  16 |                14 |        1.326 |
| 4h          | 잠자리형 도지        | bullish     |  35 |                24 |        1.211 |
| 12h         | 역망치형           | bullish     |  27 |                12 |        1.164 |
| 12h         | 교수형            | bearish     |  41 |                12 |        1.091 |
| 1d          | 석별형            | bearish     |  20 |                14 |        0.897 |
| 1h          | 하락 삼법형         | bearish     |  10 |                72 |        0.522 |
| 12h         | 하락 잉태 확인형      | bearish     |  14 |                12 |        0.436 |
| 12h         | 장대음봉           | bearish     |  31 |                12 |        0.365 |
| 1h          | 20봉 고점 유동성 스윕  | bearish     | 439 |                72 |        0.352 |
| 1d          | 20봉 고점 유동성 스윕  | bearish     |  18 |                14 |        0.337 |
| 1h          | 유성형            | bearish     | 474 |                72 |        0.273 |
| 12h         | 20봉 저점 종가 이탈   | bearish     |  57 |                12 |        0.240 |
| 1h          | 20봉 저점 유동성 스윕  | bullish     | 418 |                72 |        0.239 |
| 1d          | 장대음봉           | bearish     |  15 |                14 |        0.210 |
| 12h         | 하락 잉태형         | bearish     | 101 |                12 |        0.210 |
| 1d          | 20봉 저점 종가 이탈   | bearish     |  26 |                14 |        0.209 |
| 12h         | 흑삼병            | bearish     |  12 |                12 |        0.186 |
| 12h         | 망치형            | bullish     |  41 |                12 |        0.175 |
| 4h          | 망치형            | bullish     | 145 |                24 |        0.161 |
| 4h          | 석별형            | bearish     | 108 |                24 |        0.139 |
| 1d          | 팽이형            | neutral     | 141 |                14 |        0.129 |
| 1d          | 망치형            | bullish     |  15 |                14 |        0.114 |

## Interpretation rules

1. A pattern is not promoted unless it survives validation and test periods.
2. Location is evaluated independently: moving-average regime, RSI, ATR, liquidity sweep, and higher-timeframe direction.
3. Overlapping candles are not treated as independent proof; final inference must use event de-duplication and bootstrap confidence intervals in Phase 2.
4. Future work: wave-touch detection, sequence mining (2–8 candles), first-passage target/stop ordering, cluster-based analog search, and non-repainting TradingView rules.

## Generated files

- `pattern_performance.csv`: base pattern performance by timeframe and time split
- `pattern_context_performance.csv`: pattern × location/regime/RSI/ATR/session
- `mtf_pattern_performance.csv`: 1h patterns conditioned on completed 4h/12h/1d regimes
- `latest_state.json`: latest complete multi-timeframe candle state
- `data_quality.json`: source continuity and resampling metadata