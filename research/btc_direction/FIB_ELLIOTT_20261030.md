# BTC Fibonacci / Elliott research — 2026-10-30

## Status and provenance
Retrospective research and conditional scenarios, not a validated trading signal. Binance BTCUSDT spot quote 78,538.52 at approximately 2026-10-30 07:09:04 UTC / 16:09 KST. Latest completed 30m and1h close16:00KST;4h13:00;8h and daily09:00. The daily candle is UTC10/29. Current UTC10/30 daily,13–17KST4h and09–17KST8h were incomplete and excluded. Coinbase BTCUSD78,362.36 and BitstampBTCUSD78,375.93 at approximately the same time were cross-checks, not replacements for the BinanceUSDT pair.

Public-data collection run41018300129, artifact12960114052 on branch research/btc-fibonacci-elliott-20261030. Fresh API overlaps were checked against prior normalized data:30m996,1h997,4h/8h/daily999 each, matching OHLC and volume within aggregation floating-point tolerances. Final normalized counts30m154507,1h77244,4h19287,8h9630,daily3361. Gaps are not filled; indicators reset across discontinuities. Main,PHASE5B/5C rules, ledgers and automations unchanged.

## Theory and limits
Reviewed primary public rules from EWI Waveopedia (impulse,diagonal,zigzag,flat,triangle,combinations,alternation,channeling,truncation,Fibonacci), official NEoWave descriptions and Fibonacci Pinball's original public explanation. This is not a claim to have read all books or implemented all recursive wave rules. Price-only automated skeletons are explicitly not a full Elliott/NEoWave parser. Publisher claims of70% are not imported as BTC probabilities.

## Current linear Fibonacci calculations
Recent4h declineH81971.00→L76500.11; rebound L+r(H-L):23.6%=77791.24;38.2%=78589.99;50%=79235.56;61.8%=79881.12;78.6%=80800.23. H was inUTC10/29 16–20 and L inUTC10/30 00–04. Both are observed completed-bar extremes but NOT yet confirmed as pivots with3subsequent source bars. Earliest high confirmation17KST10/30;low01KST10/31, conditional on no replacing extreme.
Wider4h84898→76500.11 rebound38.2%=79708.10;50%=80699.06;61.8%=81690.01.
Daily recent rise74967.97(9/15UTC)→87395.67(9/21UTC), pullback H-r(H-L):38.2%=82648.29;50%=81181.82;61.8%=79715.35;78.6%=77627.50.
Daily major rise57800.19(7/1UTC)→87395.67:23.6%=80411.14;38.2%=76090.20;50%=72597.93;61.8%=69105.66;78.6%=64133.62.
Scale sensitivity: major daily38.2% in log-space is about74627.30 rather than76090.20. Recent4h38.2% log78545.51 vs linear78589.99. Linear is the fixed primary definition;50% is a conventional midpoint.

## Wave hypotheses and rejection
Illustrative localABC:84898→79220.74→81971→76500.11. A5677.26, B retracement48.443%,C/A0.96365. C=A target76293.74;1.272A74749.53;1.618A72785.19. Current low is206.37 above equality, about0.19 current4hATR. A/B/C labels are hypotheses; full5–3–5 not confirmed.
Manual lower-timeframe A skeleton84898→84057.59→84377.21→80939.54→82033.84→79220.74. C skeleton81971→80592→80954.65→78297.05→79811.23→76500.11. Every price was matched to actual30mhigh/low. Both pass the necessary price constraints of2notbeyondorigin,3beyond1,3notshortest,4not1overlap,nontruncated5. C1/3/5 lengths1379/2657.60/3311.12. Recursive subdivisions and the fullBcorrective form remain unvalidated. These are post-observation diagnostics, not newly backtested rules.
Rejected daily forced impulse87395.67→82563→87220→79800→84898→76500.11:wave4high84898 overlaps wave1territory above82563. Do not rescue it by silently calling it a diagonal.

## Exact snapshot indicators
Daily SMA5=80109.962,SMA20=81701.728,SMA60=81453.276,SMA112=74833.644,SMA224=72727.225,RSI14=36.037,ATR14=2114.57(2.711%).4hSMA20=80388.554,SMA60=81165.733,SMA448=80100.378,RSI14=37.121,ATR14=1103.213(1.410%),relativevolume3.353.1hSMA20=79374.926,SMA60=80320.469.8hSMA20=80514.113. Moving averages move; these are snapshot values.

## Conditional price paths, NOT70% forecasts
Local rebound hypothesis:hold76500.11 and reclaim78589.99→79235.56→79708–79881. The latter combines wider4h.382,dailyrecent.618,recent4h.618 and is not independent evidence three times over. Upper recovery cluster80100–80514,then80800,81165–81182,81690–81971. Each higher-timeframe recovery must be confirmed on completed bars.
A new low below76500.11 invalidates the EXACT hypothesis that Cendedthere. Rejection around79708–79881 followed by loss77627–77791 shifts attention to76500. Completed4h below76294–76090 with failedreclaim makes74750–74970 then72598–72785 the next downside observation zones. These are conditional reference prices, not inevitable targets. A price above81971 invalidates the precise bearish1–2 count whose wave1originis81971, not every possible larger bearishcount.

## Incremental historical audit
8240baseline rule/horizon cells (prior7442 plus798daily) with9additional Fibonacci/price-skeleton filters produce82400cells,247200three-splitrows.74160areadditionalfilteredcells,NOTindependenttrades. Confirmed pivots need3barsleft/right,availableonlyatrighthandthirdclose;chain updates only from confirmation,neverhistoricalrewrite. Endage<=60sourcebars,width>=ATR. Prefixinvariance tests passed for4h/daily. A separate fixedk3/k5 basic-signal sensitivity has192rows.
Train2019–2022 n>=30,hit>=65%,net50>0;validation2023–2024 n>=20,hit>=70%,net50>0;audit2025–2026-10-27 same20/70/net50. Nextbaropen tofixedendclose;excludeoutcomescrossinggaps/splitends;nonoverlapwithinrule. Cost0.30/0.50percentagepointstress;notactualfuturesfunding/borrow/leverage/TPbeforeSL. Oldhistoryhasalreadybeenexposed;thisisnotgenuineforwardtesting.
Train+validation selected0;allhistoricalgates0;currentqualified0. Audit-onlynewfiltercellswithn>=20andhit>=70%=118,allinactiveatlatestcompletedbars. Do not select these after seeing the audit.
Examples24hdirection:
30msweepreclaim+4hconfirmedup-leg61.8%proximity:train40/72=55.6%,validation28/51=54.9%,audit25/34=73.5%,auditnet50+0.548%. Unfiltered audit168/340=49.4%,net50−0.553%.
4hbearishshortMAstack+dailyconfirmeddown-leg38.2–61.8%bounce:25/51=49.0%,19/33=57.6%,19/26=73.1%,auditnet50+0.243%.Unfiltered136/267=50.9%,net50−0.387%.
1h60cross+takerconfirmation+4h.382–.618:37/89=41.6%,22/40=55.0%,26/35=74.3%,auditnet50+0.302%.
Selected subsets and thousands of tests entail selectionbias;Wilson intervals are descriptive,notmultiple-testadjusted. Currentmanualcounts are distinct from automaticconfirmed-pivotcohorts;theirprobabilitiescannotbeinterchanged.

## Preserved outputs
Conversation report BTC_피보나치_엘리어트_결합연구_20261030.md;73-file package BTC_피보나치_엘리어트_연구패키지_20261030.zip,38600030bytes,SHA256f3b1133b54e5fa8040d02e891e6bd5534cfb4217f2b8df397ba48846a159f4ca. Includes normalizedinputs,newAPIresponses,allfailed/successfulcells,codes,sourceaudit,charts.Nofonts,pickleorcredentialsdistributed.
