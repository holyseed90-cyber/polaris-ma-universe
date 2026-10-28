

def independent_touch_ordinals(x: pd.DataFrame, p: int, mode: str, sep: int) -> pd.Series:
    """Count independent MA contacts inside a directional episode.

    An event must be separated from the prior touch and price must have moved at
    least 0.75 ATR away.  The episode resets after three closes decisively on the
    wrong side or when the MA slope changes sign.
    """
    ma = x[f"ma{p}"].to_numpy(float)
    atr = x.atr14.to_numpy(float)
    low, high, close = x.low.to_numpy(float), x.high.to_numpy(float), x.close.to_numpy(float)
    slope = x[f"ma{p}_s20"].to_numpy(float)
    out = np.zeros(len(x), dtype=int)
    last_touch = -10_000
    count = 0
    wrong = 0
    away = True
    for i in range(1, len(x)):
        if not np.isfinite(ma[i]) or not np.isfinite(atr[i]) or not np.isfinite(slope[i]):
            continue
        if mode == "bull":
            direction_ok = slope[i] > 0
            wrong_side = close[i] < ma[i] - 0.50 * atr[i]
            contact = direction_ok and close[i - 1] > ma[i - 1] - 0.10 * atr[i - 1] and low[i] <= ma[i] + 0.15 * atr[i] and high[i] >= ma[i] - 0.15 * atr[i]
            if last_touch >= 0 and i > last_touch:
                away = away or np.nanmax((high[last_touch + 1:i + 1] - ma[last_touch + 1:i + 1]) / atr[last_touch + 1:i + 1]) >= 0.75
        else:
            direction_ok = slope[i] < 0
            wrong_side = close[i] > ma[i] + 0.50 * atr[i]
            contact = direction_ok and close[i - 1] < ma[i - 1] + 0.10 * atr[i - 1] and high[i] >= ma[i] - 0.15 * atr[i] and low[i] <= ma[i] + 0.15 * atr[i]
            if last_touch >= 0 and i > last_touch:
                away = away or np.nanmax((ma[last_touch + 1:i + 1] - low[last_touch + 1:i + 1]) / atr[last_touch + 1:i + 1]) >= 0.75
        wrong = wrong + 1 if wrong_side else 0
        if not direction_ok or wrong >= 3:
            count, last_touch, away, wrong = 0, -10_000, True, 0
        if contact and i - last_touch >= sep and away:
            count += 1
            out[i] = count
            last_touch, away = i, False
    return pd.Series(out, index=x.index)


def near_any_rising_ma(x: pd.DataFrame, periods: list[int], tolerance: float = 0.30) -> pd.Series:
    flags = []
    for p in periods:
        flags.append((x[f"ma{p}_s20"] > 0) & ((x.low - x[f"ma{p}"]).abs() <= tolerance * x.atr14))
    return pd.concat(flags, axis=1).any(axis=1)


def build_events(x: pd.DataFrame, tf: str) -> dict[str, tuple[pd.Series, str]]:
    cfg = TF[tf]
    e: dict[str, tuple[pd.Series, str]] = {}
    # Independent wave touches: source hierarchy and Polaris hierarchy.
    for p in [14, 28, 56, 112, 224, 448, 896]:
        bull_ord = independent_touch_ordinals(x, p, "bull", cfg["touch_sep"])
        bear_ord = independent_touch_ordinals(x, p, "bear", cfg["touch_sep"])
        x[f"ma{p}_bull_touch_ord"] = bull_ord
        x[f"ma{p}_bear_touch_ord"] = bear_ord
        e[f"ma{p}_bull_touch_1"] = (bull_ord.eq(1), "bullish")
        e[f"ma{p}_bull_touch_2"] = (bull_ord.eq(2), "bullish")
        e[f"ma{p}_bull_touch_3plus"] = (bull_ord.ge(3), "bullish")
        e[f"ma{p}_bear_touch_1"] = (bear_ord.eq(1), "bearish")
        e[f"ma{p}_bear_touch_2"] = (bear_ord.eq(2), "bearish")
        e[f"ma{p}_bear_touch_3plus"] = (bear_ord.ge(3), "bearish")

    # Breaks and reclaims of rising/falling averages; slope acceleration separated.
    for p in [14, 28, 56, 112, 224, 448, 896]:
        cross_dn = (x.close < x[f"ma{p}"]) & (x.close.shift(1) >= x[f"ma{p}"].shift(1)) & (x[f"ma{p}_s20"] > 0)
        cross_up = (x.close > x[f"ma{p}"]) & (x.close.shift(1) <= x[f"ma{p}"].shift(1)) & (x[f"ma{p}_s20"] < 0)
        e[f"ma{p}_rising_break_decel"] = (cross_dn & (x[f"ma{p}_acc"] < 0), "bearish")
        e[f"ma{p}_rising_break_not_decel"] = (cross_dn & (x[f"ma{p}_acc"] >= 0), "bearish")
        e[f"ma{p}_falling_reclaim_decel"] = (cross_up & (x[f"ma{p}_acc"] > 0), "bullish")

    # 3x average-body candles from the source, with location and midpoint confirmation.
    long_bull = x.bull & (x.body_multiple >= 3.0)
    long_bear = x.bear & (x.body_multiple >= 3.0)
    e["long_bull_3x_all"] = (long_bull, "bullish")
    e["long_bear_3x_all"] = (long_bear, "bearish")
    e["long_bull_3x_near_rising_ma"] = (long_bull & near_any_rising_ma(x, [14, 28, 56, 112, 224, 448]), "bullish")
    e["long_bear_3x_near_falling_ma"] = (long_bear & near_any_rising_ma(x.assign(**{f"ma{p}_s20": -x[f"ma{p}_s20"] for p in [14, 28, 56, 112, 224, 448]}), [14, 28, 56, 112, 224, 448]), "bearish")
    prev_mid = (x.open.shift(1) + x.close.shift(1)) / 2
    e["long_bull_3x_midpoint_hold_confirm"] = (long_bull.shift(1).fillna(False) & (x.close > prev_mid), "bullish")
    e["long_bear_3x_midpoint_hold_confirm"] = (long_bear.shift(1).fillna(False) & (x.close < prev_mid), "bearish")
    e["long_bull_3x_ma14_reclaim_confirm"] = (long_bull.shift(1).fillna(False) & (x.close > x.ma14) & (x.close.shift(1) <= x.ma14.shift(1)), "bullish")
    e["long_bear_3x_ma14_break_confirm"] = (long_bear.shift(1).fillna(False) & (x.close < x.ma14) & (x.close.shift(1) >= x.ma14.shift(1)), "bearish")
    e["long_bull_3x_late_bull_stack"] = (long_bull & x.old_bull_stack & (x.rsi14 >= 70), "bearish")
    e["long_bear_3x_late_bear_stack"] = (long_bear & x.old_bear_stack & (x.rsi14 <= 30), "bullish")

    # Hammer / hanging-man share geometry; location and confirmation determine meaning.
    small_body = x.body <= 0.35 * x.range
    lower_tail = x.lower_wick >= 2.0 * x.body.replace(0, np.nan)
    upper_small = x.upper_wick <= 0.50 * x.body.replace(0, np.nan)
    hammer_shape = small_body & lower_tail & upper_small & (x.close_loc >= 0.55)
    e["hammer_confirm_low_regime"] = (hammer_shape.shift(1).fillna(False) & (x.close > x.high.shift(1)) & (x.above_old <= 2), "bullish")
    e["hammer_confirm_ma14_reclaim"] = (hammer_shape.shift(1).fillna(False) & (x.close > x.high.shift(1)) & (x.close > x.ma14), "bullish")
    e["hanging_man_confirm_high_regime"] = (hammer_shape.shift(1).fillna(False) & (x.close < x.low.shift(1)) & (x.above_old >= 4), "bearish")

    doji = x.body <= 0.10 * x.range
    e["doji_at_rising_ma_confirm_up"] = (doji.shift(1).fillna(False) & near_any_rising_ma(x.shift(1), [14, 28, 56]) & (x.close > x.high.shift(1)), "bullish")
    e["doji_at_high_confirm_down"] = (doji.shift(1).fillna(False) & (x.above_old >= 4) & (x.close < x.low.shift(1)), "bearish")

    # Five-candle runs: the source explicitly assigns opposite meanings by location.
    bull5 = x.bull.rolling(5).sum().eq(5)
    bear5 = x.bear.rolling(5).sum().eq(5)
    e["five_bull_in_bear_regime"] = (bull5 & (x.above_old <= 2), "bullish")
    e["five_bull_in_bull_regime"] = (bull5 & (x.above_old >= 4), "bearish")
    e["five_bear_in_bull_regime"] = (bear5 & (x.above_old >= 3), "bearish")
    e["five_bear_in_bear_regime"] = (bear5 & (x.above_old <= 1), "bullish")

    # Convergence -> directional expansion.
    for name, spread, mas in [("old", x.old_spread_atr, OLD_MAS), ("polaris", x.polaris_spread_atr, POLARIS_MAS)]:
        q20 = spread.shift(1).rolling(250, min_periods=100).quantile(0.20)
        compressed = spread.shift(1) <= q20
        top = x[[f"ma{p}" for p in mas]].max(axis=1)
        bottom = x[[f"ma{p}" for p in mas]].min(axis=1)
        e[f"{name}_compression_bull_expansion"] = (compressed & (spread > spread.shift(1) * 1.10) & (x.close > top), "bullish")
        e[f"{name}_compression_bear_expansion"] = (compressed & (spread > spread.shift(1) * 1.10) & (x.close < bottom), "bearish")

    # Stable/widening gaps for doubled MA pairs.
    for a, b in [(14, 28), (28, 56), (112, 224), (224, 448), (448, 896)]:
        gap = (x[f"ma{a}"] - x[f"ma{b}"]) / x.atr14
        delta = gap - gap.shift(20)
        both_up = (x[f"ma{a}_s20"] > 0) & (x[f"ma{b}_s20"] > 0) & (gap > 0)
        both_down = (x[f"ma{a}_s20"] < 0) & (x[f"ma{b}_s20"] < 0) & (gap < 0)
        e[f"ma{a}_{b}_bull_gap_stable"] = (both_up & (delta.abs() <= 0.50), "bullish")
        e[f"ma{a}_{b}_bull_gap_widening"] = (both_up & (delta > 1.00), "bullish")
        e[f"ma{a}_{b}_bear_gap_stable"] = (both_down & (delta.abs() <= 0.50), "bearish")
        e[f"ma{a}_{b}_bear_gap_widening"] = (both_down & (delta < -1.00), "bearish")
    return e
