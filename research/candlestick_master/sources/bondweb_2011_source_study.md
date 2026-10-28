# Bondweb 2011 Technical Analysis Source Study

## Source identity

- Original URL: `https://www.bondweb.co.kr/data/menu01/2011051313445601.pdf`
- Title: **기술적 분석 집중관리 프로그램**
- Author shown in the document: Technical Analyst 정인지, 동양종합금융증권 리서치센터 투자전략팀
- PDF metadata: created 2011-05-12, modified 2011-05-13, 152 pages
- Scope: technical-analysis overview, moving averages, candlesticks, chart patterns, volume/gaps, indicators, Ichimoku and Elliott wave

This source is a hypothesis source, not ground truth. Every claim below must be tested on BTC without silently importing conclusions from Korean equities.

## Central framework

The source treats price as the visible result of liquidity and investor psychology and treats the moving average as the compressed path of prior trading prices. It makes five central claims:

1. MA direction represents trend; MA slope represents trend strength.
2. Price/MA distance represents extension and mean-reversion pressure.
3. The whole MA structure—direction, spacing, order, convergence and expansion—is more important than one crossover.
4. Support/resistance is a zone, not an exact price, and prior confirmation strengthens it.
5. A candle pattern has meaning only when interpreted at support/resistance, with MA structure and confirmation.

## Source MA hierarchy

The source prefers **3, 7, 14, 28 and 56 simple moving averages**.

- 3: very short trend and strong-trend trailing line
- 7: short-trend confirmation after 3 breaks
- 14: key regime/dividing line
- 28: confirmation line for 14 and for 56
- 56: long-trend last line / major support-resistance

It explains 14→28→56 as a doubling hierarchy. The stated rationale is that when price reaches the next doubled MA, the previous MA often loses slope and therefore loses independent meaning. This is directly comparable with the Polaris hierarchy 112→224→448→896.

## Objective claims selected for BTC testing

### MA direction and slope

- MA direction is trend; slope is trend strength.
- Slope deceleration often precedes an actual price break.
- A steep rising long MA can recover after a temporary close below it.
- A falling long MA can remain resistance even after all MAs converge.

### First touch and repeated touch

- The first approach to a rising 14 MA in an uptrend often provides strong support.
- Repeated approaches near the same price weaken support.
- Long MAs are rarely broken cleanly on the first approach.
- Temporary penetration depth can measure weakening support before final failure.

### Sequential MA ladder

- Failure at one MA and failure to make a new high increases the chance of movement to the next longer MA.
- A 14 break should be confirmed by 28; a 28 failure raises the chance of reaching 56.
- In the Polaris hierarchy this becomes 112→224→448→896.

### Spacing, convergence and expansion

- Stable spacing between rising 28 and 56 implies trend continuation.
- Widening caused by differing slopes can increase eventual correction depth.
- Full convergence means overhead inventory has been worked off and directional movement becomes easier.
- Convergence followed by expansion is the preferred trend-start structure.

### Support migration

- A trend strengthens when the dominant support migrates from a longer MA to progressively shorter MAs.
- Strong adjustment means long MAs rise during sideways price action, lifting the support floor.

### Long-body candles

- A long candle is defined as a body at least three times the average body length.
- A sudden long candle late in an established trend can be a reversal clue.
- At support/resistance, a long candle with little/no wick can continue in the break direction.
- Holding the candle midpoint and the 14 MA is important confirmation.

### Candle patterns with location and confirmation

- Doji/spinning top: indecision; more important at support/resistance.
- Hammer/hanging man: similar shape, different meaning by location.
- Hammer/hanging-man reliability rises when followed by a 14-MA reclaim or break.
- Engulfing/harami and morning/evening star are reversal hypotheses only at meaningful zones.
- Rising three methods requires the pullback candles to remain above the first long candle's lower boundary.
- Five consecutive bullish/bearish candles have opposite meaning at the beginning versus the end of a trend.

### Volume and gaps

- Volume tends to increase at important support/resistance where buyers and sellers conflict.
- A support break with rising volume raises continuation risk.
- A reversal candle after an extended decline plus volume expansion can mark a low.
- Breakaway, continuation and exhaustion gaps must be classified by location, not shape alone.

### Oscillators

- RSI overbought/oversold alone is unreliable in strong trends.
- A move from an extreme back to neutral can whipsaw; acceptance/failed reversal matters.
- Divergence and oscillator trend-line breaks may lead price but can be early.
- DMI/ADX is used to distinguish directional strength from a range.

## Relationship to the current research

This source strengthens several findings already observed in BTC:

- exact candle-shape memorization is brittle;
- location and completed higher-timeframe context matter more;
- RSI 70 in a broad bullish MA regime can be momentum, not an automatic short;
- sequential MA targets, slope, convergence and retest behavior are more informative than a single golden cross;
- repeated MA touches must be separated into independent waves.

## Phase 3B test plan

1. Compare first, second and third-or-later independent touches of 14/28/56 and 112/224/448/896.
2. Measure defense strength after each touch: MFE, MAE, 1-ATR target-before-stop and eventual break rate.
3. Test sequential ladder transitions: 14 break→28, 28 break→56, 112 break→224, 224 break→448, 448 break→896.
4. Test whether MA slope deceleration precedes breaks.
5. Test stable spacing, widening, compression and post-compression expansion.
6. Test support migration from long to short MAs.
7. Test 3× average-body candles by trend location, MA zone, midpoint hold and 14-MA confirmation.
8. Test hammer/hanging-man, doji, engulfing, harami, star and five-candle runs only with location/confirmation.
9. Keep 2018–2022 train, 2023–2024 validation and 2025–present untouched test separation.
10. Report negative results and wide confidence intervals rather than promoting weak patterns.
