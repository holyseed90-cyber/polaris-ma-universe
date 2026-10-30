# BTC multi-timeframe extension — 2026-10-30

Actual research completed, not a future plan. Binance BTCUSDT spot snapshot 2026-10-30 05:33:20 UTC / 14:33:20 KST: ticker 78732.88. Do not reuse this as a live price.

## Inputs
Official 30m monthly files 2018-01 through 2026-09 (105) plus October API. 111 total archive checksums verified including six native 1h/8h audit months. 154504 completed 30m bars, 77242 complete 1h aggregates, 19287 complete 4h aggregates, 9630 complete 8h aggregates; 3361 official daily bars. Missing lower-timeframe bars were not fabricated; incomplete aggregates excluded; indicators restart after gaps. Native sample checks pass but are same-venue, not independent exchange validation. 8h uses UTC 00/08/16 alignment, no optimized offset.

## Frozen retrospective design
Protocol SHA256 30c167ed9264ed0f6057c6059e53997f24a1deab727c045fb059f622ea68f25b. 19 prior triggers x13 filters x2 sides, plus four chronological multi-timeframe sequences. Forecast horizons4/8/24/48h for30m/1h/4h and8/24/48h for8h. 7442 rule-timeframe-horizon cells,22326 split rows, not independent discoveries. Train2019-2022, selection2023-2024, audit2025 through2026-10-27. Next-open entry; fixed future close; no overlapping holding windows within rule; purge split-boundary outcomes. Gates train n30/hit65%, selection n20/hit70%, audit n20/hit70%, mean after0.50pp roundtrip cost positive in all three. Also record0.30pp costs. Counts alone do not establish true probability70%. Retrospective exposed history, not genuine forward validation. No TP/SL execution model and no actual futures funding/liquidation model.

## Results
Zero candidates passed train+selection gates; zero promoted. Seven audit-only combinations had n>=20 and direction>=70%, all inactive on latest completed respective bars. They are diagnostic, not independently validated predictions:
-30m RSI14 falls below70 from>=70, last complete8h close below8hMA20 andMA60 with declining60, last3 30m taker-volume imbalance<0:4h short direction train11/27=40.7%,selection12/25=48.0%,audit20/25=80.0%;audit mean after0.50pp costs -0.0221%. No live70% claim.
-1h close crosses below448 while remaining above rising60:24h short train20/40=50%,selection10/24=41.7%,audit22/30=73.3%;audit mean net50 +0.5457%.
-1h20-bar low breakdown while above rising60:48h short train16/43=37.2%,selection9/27=33.3%,audit20/26=76.9%.
-8h RSI14 falls below70:48h short train34/67=50.7%,selection15/38=39.5%,audit15/21=71.4%;audit mean net50 +0.6411%.
Other3 audit-only rules and full failed results are retained in the delivered research package. Several rules share events; do not call them independent evidence.

## Snapshot interpretation
Latest completed30m14:30KST close78686.35,RSI49.41,MA20 78364.21,volume0.369x. Latest1h14:00 close78280.01,RSI39.83,MA20 79539.25,MA60 80385.90. Latest4h13:00 close78235.15,RSI37.12,MA20 80388.55. Latest8h09:00 close77991.89,RSI37.34,MA20 80514.11,MA60 81822.09. Short recovery is not higher-timeframe reversal;09-17KST8h candle is incomplete.

Post-screen descriptive current-state cohort (not selection):30m close>MA20,completed1h/4h/8h closes<respectiveMA20,daily close<dailyMA20 andMA60. 2023 through2026-10-27 non-overlap:24h up125/236=53.0%;48h up81/162=50.0%;48h low-5%26/162,high+5%22/162. This is not a calibrated current probability.

## Preservation
Collector isolated branch research/btc-multiframe-20261030,run41009044367,artifact12956772367 (30-day expiry). Full raw archives,code,protocol,all7442 comparisons,events,yearly tables,QA delivered as BTC_30분_1시간_8시간_연구패키지_20261030.zip. Local report BTC_30분_1시간_8시간_추가검증_20261030.md. main and PHASE5B/5C frozen rules/ledgers unchanged.

Future briefings must refresh prices and completed30m/1h/4h/8h/daily inputs. Use only upper bars with close time<=signal close. Report conflicting timeframes and give concrete recovery/failure prices, but never reinterpret missing70% evidence as a sideways forecast or manufacture target/stop/horizon to reach70%.
