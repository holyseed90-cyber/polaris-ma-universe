n):
        sar = sar + af * (ep - sar)
        if bull:
            sar = min(sar, x.low.iloc[i - 1], x.low.iloc[i - 2])
            if x.low.iloc[i] < sar:
                bull = False
                sar = ep
                ep = x.low.iloc[i]
                af = step
            elif x.high.iloc[i] > ep:
                ep = x.high.iloc[i]
                af = min(max_step, af + step)
        else:
            sar = max(sar, x.high.iloc[i - 1], x.high.iloc[i - 2])
            if x.high.iloc[i] > sar:
                bull = True
                sar = ep
                ep = x.high.iloc[i]
                af = step
            elif x.low.iloc[i] < ep:
                ep = x.low.iloc[i]
                af = min(max_step, af + step)
        out.iloc[i] = 1.0 if bull else -1.0
    return out


def indicator_frame(x: pd.DataFrame) -> pd.DataFrame:
    z = pd.DataFrame(index=x.index)
    z["signal_time"] = pd.to_datetime(x.signal_time, utc=True)

    # Ichimoku 9/26/52.  Leading spans are shifted 26 bars so the cloud compared
    # with current price was fully known when that bar closed.
    tenkan = (x.high.rolling(9).max() + x.low.rolling(9).min()) / 2
    kijun = (x.high.rolling(26).max() + x.low.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((x.high.rolling(52).max() + x.low.rolling(52).min()) / 2).shift(26)
    cloud_top = pd.concat([span_a, span_b], axis=1).max(axis=1)
    cloud_bottom = pd.concat([span_a, span_b], axis=1).min(axis=1)
    z["ichi_tenkan"] = tenkan
    z["ichi_kijun"] = kijun
    z["ichi_span_a"] = span_a
    z["ichi_span_b"] = span_b
    z["ichi_cloud_top"] = cloud_top
    z["ichi_cloud_bottom"] = cloud_bottom
    z["ichi_cloud_thickness_atr"] = (cloud_top - cloud_bottom).abs() / x.atr14.replace(0, np.nan)
    z["ichi_bull_cloud"] = (x.close > cloud_top) & (span_a > span_b)
    z["ichi_bear_cloud"] = (x.close < cloud_bottom) & (span_a < span_b)
    z["ichi_bull_full"] = z.ichi_bull_cloud & (tenkan > kijun) & (x.close > tenkan) & (x.close > x.close.shift(26))
    z["ichi_bear_full"] = z.ichi_bear_cloud & (tenkan < kijun) & (x.close < tenkan) & (x.close < x.close.shift(26))
    z["ichi_bull_kijun"] = (x.close > kijun) & (kijun > kijun.shift(3))
    z["ichi_bear_kijun"] = (x.close < kijun) & (kijun < kijun.shift(3))
    bull_break = (x.close > cloud_top) & (x.close.shift(1) <= cloud_top.shift(1))
    bear_break = (x.close < cloud_bottom) & (x.close.shift(1) >= cloud_bottom.shift(1))
    z["ichi_bull_break_recent"] = bull_break.rolling(5, min_periods=1).max().fillna(0).astype(bool)
    z["ichi_bear_break_recent"] = bear_break.rolling(5, min_periods=1).max().fillna(0).astype(bool)

    plus_di, minus_di, adx = dmi(x, 14)
    z["plus_di"] = plus_di
    z["minus_di"] = minus_di
    z["adx14"] = adx
    z["dmi_bull"] = plus_di > minus_di
    z["dmi_bear"] = minus_di > plus_di
    z["adx_rising"] = adx > adx.shift(3)

    mid = x.close.rolling(20).mean()
    std = x.close.rolling(20).std(ddof=0)
    upper, lower = mid + 2 * std, mid - 2 * std
    width = (upper - lower) / mid.replace(0, np.nan)
    pctb = (x.close - lower) / (upper - lower).replace(0, np.nan)
    width_rank = width.rolling(100, min_periods=50).rank(pct=True)
    atr20 = wilder(true_range(x), 20)
    ema20 = x.close.ewm(span=20, adjust=False, min_periods=20).mean()
    kc_upper, kc_lower = ema20 + 1.5 * atr20, ema20 - 1.5 * atr20
    squeeze = (upper < kc_upper) & (lower > kc_lower)
    released = (~squeeze) & squeeze.shift(1).rolling(5, min_periods=1).max().fillna(0).astype(bool)
    z["bb_pctb"] = pctb
    z["bb_width"] = width
    z["bb_width_rank"] = width_rank
    z["bb_width_rising"] = width > width.shift(3)
    z["bb_bull_release"] = released & (x.close > mid) & z.bb_width_rising
    z["bb_bear_release"] = released & (x.close < mid) & z.bb_width_rising

    rng = (x.high - x.low).replace(0, np.nan)
    mf_mult = ((x.close - x.low) - (x.high - x.close)) / rng
    mfv = mf_mult.fillna(0) * x.volume
    cmf = mfv.rolling(20).sum() / x.volume.rolling(20).sum().replace(0, np.nan)
    z["cmf20"] = cmf
    z["cmf_rising"] = cmf > cmf.shift(3)
    signed_vol = np.sign(x.close.diff()).fillna(0) * x.volume
    obv = signed_vol.cumsum()
    obv_norm = (obv - obv.shift(10)) / x.volume.rolling(10).sum().replace(0, np.nan)
    z["obv_norm10"] = obv_norm
    typical = (x.high + x.low + x.close) / 3
    raw_flow = typical * x.volume
    pos_flow = raw_flow.where(typical.diff() > 0, 0.0)
    neg_flow = raw_flow.where(typical.diff() < 0, 0.0).abs()
    mfr = pos_flow.rolling(14).sum() / neg_flow.rolling(14).sum().replace(0, np.nan)
    z["mfi14"] = 100 - 100 / (1 + mfr)
    vwma = (x.close * x.volume).rolling(20).sum() / x.volume.rolling(20).sum().replace(0, np.nan)
    z["vwma20"] = vwma
    z["vwma_rising"]