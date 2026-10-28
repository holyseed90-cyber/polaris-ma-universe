    v = pd.to_numeric(z.sort_values("signal_time")[col], errors="coerce").dropna()
    streak = best = 0
    for x in v:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    return {
        "n": int(len(v)),
        "win_rate": float((v > 0).mean()),
        "mean_net_pct": float(v.mean()),
        "median_net_pct": float(v.median()),
        "profit_factor": safe_pf(v),
        "max_drawdown_pct": max_drawdown(v),
        "max_losing_streak": int(best),
    }


def mean_lcb(values: pd.Series, z: float = 1.2815515655446004) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if len(v) < 2:
        return -np.inf
    return float(v.mean() - z * v.std(ddof=1) / math.sqrt(len(v)))


def benjamini_hochberg(pvalues: pd.Series) -> pd.Series:
    p = pd.to_numeric(pvalues, errors="coerce")
    valid = p.dropna().clip(0, 1)
    if valid.empty:
        return pd.Series(np.nan, index=p.index)
    order = valid.sort_values().index
    m = len(valid)
    raw = np.array([valid.loc[i] * m / rank for rank, i in enumerate(order, start=1)], dtype=float)
    adj = np.minimum.accumulate(raw[::-1])[::-1]
    out = pd.Series(np.nan, index=p.index, dtype=float)
    out.loc[order] = np.clip(adj, 0, 1)
    return out


def resampled_frames(hourly: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for tf, cfg in p3.TIMEFRAMES.items():
        raw = hourly if tf == "1h" else p3.resample_ohlcv(hourly, cfg["rule"])
        x = p3.enrich(raw, cfg["hours"])
        x["atr_relative"] = x.atr_pct / x.atr_pct.shift(1).rolling(250, min_periods=80).median()
        slope_cols = [f"ma{m}_s20" for m in [20, 60, 112, 224, 448, 896]]
        x["rising_ma_count"] = (x[slope_cols] > 0).sum(axis=1)
        x["falling_ma_count"] = (x[slope_cols] < 0).sum(axis=1)
        x["long_spread_atr"] = (x[["ma112", "ma224", "ma448", "ma896"]].max(axis=1) - x[["ma112", "ma224", "ma448", "ma896"]].min(axis=1)) / x.atr14
        frames[tf] = x
    return frames


def nearest_target_gap(x: pd.DataFrame, i: int, side: str) -> float:
    close = float(x.close.iloc[i])
    atr = float(x.atr14.iloc[i])
    if not np.isfinite(atr) or atr <= 0:
        return np.nan
    vals = [float(x[f"ma{m}"].iloc[i]) for m in [112, 224, 448, 896] if np.isfinite(x[f"ma{m}"].iloc[i])]
    if side == "long":
        diffs = [(v - close) / atr for v in vals if v > close]
    else:
        diffs = [(close - v) / atr for v in vals if v < close]
    return float(min(diffs)) if diffs else np.nan


def htf_context(frames: dict[str, pd.DataFrame], tf: str, signal_time: pd.Timestamp, side: str) -> tuple[float, str]:
    order = ["1h", "4h", "12h", "1d"]
    higher = order[order.index(tf) + 1:]
    if not higher:
        return 0.0, "none"
    scores: list[float] = []
    for htf in higher:
        x = frames[htf]
        available = x.signal_time
        j = int(available.searchsorted(signal_time, side="right") - 1)
        if j < 0:
            continue
        above = float(x.above_count.iloc[j])
        slope = float(x.rising_ma_count.iloc[j] if side == "long" else x.falling_ma_count.iloc[j])
        directional_above = (above - 4) / 4 if side == "long" else (4 - above) / 4
        scores.append(0.6 * directional_above + 0.4 * ((slope - 3) / 3))
    if not scores:
        return 0.0, "none"
    value = float(np.mean(scores))
    label = "aligned" if value >= 0.25 else "opposed" if value <= -0.25 else "mixed"
    return value, label


def build_events_for_venue(venue: str, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict] = []
    for tf, x in frames.items():
        min_gap = p3.TIMEFRAMES[tf]["horizon"]
        rules = p3.build_rules(x, tf)
        for rule, (mask, side) in rules.items():
            positions = p3.dedupe_positions(np.flatnonzero(mask.fillna(False).to_numpy()), min_gap)
            for i in positions:
                if i + 1 >= len(x) or not np.isfinite(x.atr14.iloc[i]):
                    continue
                signal_time = x.signal_time.iloc[i]
                htf_value, htf_label = htf_context(frames, tf, signal_time, side)
                long_state = "mixed"
                if bool(x.long_bull_stack.iloc[i]):
                    long_state = "bull"
                elif bool(x.long_bear_stack.iloc[i]):
                    long_state = "bear"
                side_slope = float(x.rising_ma_count.iloc[i] if side == "long" else x.falling_ma_count.iloc[i])
                gap = nearest_target_gap(x, i, side)
                rows.append({
                    "venue": venue, "timeframe": tf, "rule": rule, "side": side,
                    "signal_time": signal_time, "bar_index": int(i),
                    "entry_time": x.index[i + 1],
