    bear_sr = []
    for lag in range(1, 5):
        level_h = prior_hi20.shift(lag)
        level_l = prior_lo20.shift(lag)
        bull_sr.append(bull_breakout.shift(lag).fillna(False) & (x.low <= level_h + 0.25 * x.atr14) & (x.close > level_h))
        bear_sr.append(bear_breakdown.shift(lag).fillna(False) & (x.high >= level_l - 0.25 * x.atr14) & (x.close < level_l))
    x["bull_sr_flip_retest"] = recent_shift_any(bull_sr)
    x["bear_sr_flip_retest"] = recent_shift_any(bear_sr)

    # Fair value gap creation and later midpoint rejection, using only completed bars.
    bull_fvg_created = x.low > x.high.shift(2) + 0.05 * x.atr14
    bear_fvg_created = x.high < x.low.shift(2) - 0.05 * x.atr14
    bull_fvg_retests = []
    bear_fvg_retests = []
    for lag in range(1, 7):
        bull_lower = x.high.shift(lag + 2)
        bull_upper = x.low.shift(lag)
        bull_mid = (bull_lower + bull_upper) / 2
        bull_fvg_retests.append(
            bull_fvg_created.shift(lag).fillna(False)
            & (x.low <= bull_upper)
            & (x.close >= bull_mid)
            & (x.close > bull_lower)
        )
        bear_upper = x.low.shift(lag + 2)
        bear_lower = x.high.shift(lag)
        bear_mid = (bear_upper + bear_lower) / 2
        bear_fvg_retests.append(
            bear_fvg_created.shift(lag).fillna(False)
            & (x.high >= bear_lower)
            & (x.close <= bear_mid)
            & (x.close < bear_upper)
        )
    x["bull_fvg_rejection"] = recent_shift_any(bull_fvg_retests)
    x["bear_fvg_rejection"] = recent_shift_any(bear_fvg_retests)

    # Rejection block at a long moving average or confirmed swing point.
    ma_distance = pd.concat([((x.close - x[f"ma{p}"]).abs() / x.atr14) for p in [112, 224, 448, 896]], axis=1).min(axis=1)
    swing_low_dist = (x.close - x.last_swing_low).abs() / x.atr14
    swing_high_dist = (x.close - x.last_swing_high).abs() / x.atr14
    x["bull_ma_rejection"] = (x.lower_ratio >= 0.45) & (x.close_location >= 0.65) & ((ma_distance <= 0.35) | (swing_low_dist <= 0.35))
    x["bear_ma_rejection"] = (x.upper_ratio >= 0.45) & (x.close_location <= 0.35) & ((ma_distance <= 0.35) | (swing_high_dist <= 0.35))

    # Last opposite candle before displacement, followed by a causal retest.
    bull_disp = (x.close > x.open) & (body >= 1.25 * x.atr14) & (x.close > x.high.shift(1))
    bear_disp = (x.close < x.open) & (body >= 1.25 * x.atr14) & (x.close < x.low.shift(1))
    bull_ob = []
    bear_ob = []
    for lag in range(1, 9):
        ob_open = x.open.shift(lag + 1)
        ob_close = x.close.shift(lag + 1)
        ob_low = x.low.shift(lag + 1)
        ob_high = x.high.shift(lag + 1)
        bull_ob.append(
            bull_disp.shift(lag).fillna(False)
            & (ob_close < ob_open)
            & (x.low <= ob_open)
            & (x.close > (ob_open + ob_close) / 2)
            & (x.close > ob_low)
        )
        bear_ob.append(
            bear_disp.shift(lag).fillna(False)
            & (ob_close > ob_open)
            & (x.high >= ob_open)
            & (x.close < (ob_open + ob_close) / 2)
            & (x.close < ob_high)
        )
    x["bull_ob_retest"] = recent_shift_any(bull_ob)
    x["bear_ob_retest"] = recent_shift_any(bear_ob)

    # Range contraction and expansion.
    prior_compressed = x.range_atr.shift(1).rolling(6, min_periods=6).mean() < 0.75
    x["bull_compression_expansion"] = prior_compressed & (x.range_atr >= 1.25) & (x.close_location >= 0.75) & (x.close > x.open)
    x["bear_compression_expansion"] = prior_compressed & (x.range_atr >= 1.25) & (x.close_location <= 0.25) & (x.close < x.open)

    # Approximate three-tap structure with a confirmed break away from repeated range edge.
    rolling_low = x.low.rolling(20, min_periods=20).min()
    rolling_high = x.high.rolling(20, min_periods=20).max()
    low_touch = ((x.low - rolling_low).abs() <= 0.25 * x.atr14).astype(int)
    high_touch = ((x.high - rolling_high).abs() <= 0.25 * x.atr14).astype(int)
    x["bull_three_tap_break"] = (low_touch.rolling(20, min_periods=20).sum() >= 3) & (x.close > x.high.shift(1)) & (x.close_location >= 0.70)
    x["bear_three_tap_break"] = (high_touch.rolling(20, min_periods=20).sum() >= 3) & (x.close < x.low.shift(1)) & (x.close_location <= 0.30)

    # Side-specific next long MA distance.
    ma_cols = ["ma112", "ma224", "ma448", "ma896"]
    above_dist = pd.concat([((x[c] - x.close) / x.atr14).where(x[c] > x.close) for c in ma_cols], axis=1)
    below_dist = pd.concat([((x.close - x[c]) / x.atr14).where(x[c] < x.close) for c in ma_cols], axis=1)
    x["next_ma_gap_long"] = above_dist.min(axis=1)
