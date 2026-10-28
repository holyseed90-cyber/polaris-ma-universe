                if not high_pivots or high_pivots[-1][0] != pivot_i:
                    high_pivots.append((pivot_i, highs[pivot_i]))
            if lows[pivot_i] <= np.nanmin(lows[lo_i:hi_i]):
                if not low_pivots or low_pivots[-1][0] != pivot_i:
                    low_pivots.append((pivot_i, lows[pivot_i]))
        lh = high_pivots[-1][1] if high_pivots else np.nan
        ll = low_pivots[-1][1] if low_pivots else np.nan
        last_high[i], last_low[i] = lh, ll
        if len(high_pivots) >= 2 and len(low_pivots) >= 2:
            hh = high_pivots[-1][1] > high_pivots[-2][1]
            hl = low_pivots[-1][1] > low_pivots[-2][1]
            lower_h = high_pivots[-1][1] < high_pivots[-2][1]
            lower_l = low_pivots[-1][1] < low_pivots[-2][1]
            current_state = "bull" if hh and hl else ("bear" if lower_h and lower_l else "mixed")
        else:
            current_state = "mixed"
        state[i] = current_state
        if i > 0 and np.isfinite(lh):
            bull_break[i] = closes[i] > lh and closes[i - 1] <= lh
            if bull_break[i]:
                bull_choch[i] = prev_state == "bear"
                last_bull_level, last_bull_bar = lh, i
        if i > 0 and np.isfinite(ll):
            bear_break[i] = closes[i] < ll and closes[i - 1] >= ll
            if bear_break[i]:
                bear_choch[i] = prev_state == "bull"
                last_bear_level, last_bear_bar = ll, i
        if i > last_bull_bar and i - last_bull_bar <= 4 and np.isfinite(last_bull_level) and np.isfinite(atr[i]):
            bull_retest[i] = lows[i] <= last_bull_level + 0.25 * atr[i] and closes[i] > last_bull_level
        if i > last_bear_bar and i - last_bear_bar <= 4 and np.isfinite(last_bear_level) and np.isfinite(atr[i]):
            bear_retest[i] = highs[i] >= last_bear_level - 0.25 * atr[i] and closes[i] < last_bear_level
        prev_state = current_state
    return pd.DataFrame({
        "structure_state": state,
        "last_swing_high": last_high,
        "last_swing_low": last_low,
        "bull_structure_break": bull_break,
        "bear_structure_break": bear_break,
        "bull_choch": bull_choch,
        "bear_choch": bear_choch,
        "bull_structure_retest": bull_retest,
        "bear_structure_retest": bear_retest,
    }, index=x.index)


def recent_shift_any(conditions: list[pd.Series]) -> pd.Series:
    out = pd.Series(False, index=conditions[0].index)
    for c in conditions:
        out |= c.fillna(False)
    return out


def enrich_precision(raw: pd.DataFrame, hours: int, pivot_right: int) -> pd.DataFrame:
    x = p3.enrich(raw, hours).copy()
    rng = (x.high - x.low).replace(0, np.nan)
    body = (x.close - x.open).abs()
    top = x[["open", "close"]].max(axis=1)
    bottom = x[["open", "close"]].min(axis=1)
    x["body_ratio"] = (body / rng).clip(0, 1).fillna(0)
    x["upper_ratio"] = ((x.high - top) / rng).clip(0, 1).fillna(0)
    x["lower_ratio"] = ((bottom - x.low) / rng).clip(0, 1).fillna(0)
    x["close_location"] = ((x.close - x.low) / rng).clip(0, 1).fillna(0.5)
    x["range_atr"] = rng / x.atr14
    x["atr_relative"] = x.atr_pct / x.atr_pct.rolling(100, min_periods=30).median()
    x["volume_relative"] = x.volume / x.volume.rolling(20, min_periods=10).median().replace(0, np.nan)
    for p in [5, 10, 20, 60, 112, 224, 448, 896]:
        x[f"ma{p}_s5"] = (x[f"ma{p}"] / x[f"ma{p}"].shift(5) - 1) * 100
        x[f"ma{p}_accel"] = x[f"ma{p}_s5"] - x[f"ma{p}_s5"].shift(5)
    ma8_cols = [f"ma{p}" for p in [5, 10, 20, 60, 112, 224, 448, 896]]
    slope8_cols = [f"ma{p}_s20" for p in [5, 10, 20, 60, 112, 224, 448, 896]]
    x["ma8_available"] = x[ma8_cols + slope8_cols].notna().all(axis=1)
    x["long4_available"] = x[["ma112", "ma224", "ma448", "ma896"]].notna().all(axis=1)
    slopes = pd.concat([(x[f"ma{p}_s20"] > 0).rename(str(p)) for p in [5, 10, 20, 60, 112, 224, 448, 896]], axis=1)
    x["rising_count8"] = slopes.sum(axis=1).where(x.ma8_available)
    long_mas = x[["ma112", "ma224", "ma448", "ma896"]]
    x["long_ma_spread_atr"] = ((long_mas.max(axis=1) - long_mas.min(axis=1)) / x.atr14).where(x.long4_available)
    x["long_ma_compressed"] = (x.long_ma_spread_atr < 1.5) & x.long4_available

    # Causal market structure.
    structure = causal_structure(x, left=3, right=pivot_right)
    x = pd.concat([x, structure], axis=1)

    # S/R flip and retest: breakout/breakdown in one of the previous four bars.
    prior_hi20 = x.high.shift(1).rolling(20, min_periods=20).max()
    prior_lo20 = x.low.shift(1).rolling(20, min_periods=20).min()
    bull_breakout = x.close > prior_hi20 + 0.05 * x.atr14
    bear_breakdown = x.close < prior_lo20 - 0.05 * x.atr14
    bull_sr = []
