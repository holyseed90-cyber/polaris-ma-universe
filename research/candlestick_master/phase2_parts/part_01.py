    gain = diff.clip(lower=0)
    loss = (-diff).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(100.0).where(avg_gain.notna())


def wilder_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]), (df["high"] - prev).abs(), (df["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def cut_label(s: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(s, bins=bins, labels=labels, include_lowest=True, right=False).astype("string")


def enrich(df: pd.DataFrame, period_hours: int) -> pd.DataFrame:
    x = df.copy()
    rng = (x.high - x.low).replace(0, np.nan)
    body = (x.close - x.open).abs()
    top = x[["open", "close"]].max(axis=1)
    bottom = x[["open", "close"]].min(axis=1)
    x["body_ratio"] = (body / rng).clip(0, 1).fillna(0)
    x["upper_ratio"] = ((x.high - top) / rng).clip(0, 1).fillna(0)
    x["lower_ratio"] = ((bottom - x.low) / rng).clip(0, 1).fillna(0)
    x["close_location"] = ((x.close - x.low) / rng).clip(0, 1).fillna(0.5)
    x["atr14"] = wilder_atr(x)
    x["atr_pct"] = x.atr14 / x.close * 100
    x["rsi14"] = wilder_rsi(x.close)
    x["range_atr"] = rng / x.atr14
    x["atr_relative"] = x.atr_pct / x.atr_pct.rolling(100, min_periods=30).median()

    for p in MA_PERIODS:
        x[f"ma{p}"] = x.close.rolling(p, min_periods=p).mean()
        x[f"ma{p}_slope5"] = (x[f"ma{p}"] / x[f"ma{p}"].shift(5) - 1) * 100
        x[f"ma{p}_slope20"] = (x[f"ma{p}"] / x[f"ma{p}"].shift(20) - 1) * 100

    above = pd.concat([(x.close > x[f"ma{p}"]).rename(str(p)) for p in MA_PERIODS], axis=1)
    rising = pd.concat([(x[f"ma{p}_slope20"] > 0).rename(str(p)) for p in MA_PERIODS], axis=1)
    x["above_count"] = above.sum(axis=1)
    x["rising_count"] = rising.sum(axis=1)
    x["trend_regime"] = np.select(
        [(x.above_count >= 7) & (x.rising_count >= 6), (x.above_count <= 1) & (x.rising_count <= 2)],
        ["broad_bull", "broad_bear"], default="mixed",
    )
    x["long_state"] = np.select(
        [
            (x.ma224 > x.ma448) & (x.ma448 > x.ma896),
            (x.ma224 < x.ma448) & (x.ma448 < x.ma896),
        ],
        ["long_bull_stack", "long_bear_stack"], default="long_mixed",
    )
    x["rsi_bin"] = cut_label(x.rsi14, [-np.inf, 30, 40, 50, 60, 70, np.inf], ["r0", "r1", "r2", "r3", "r4", "r5"])
    x["atr_state"] = cut_label(x.atr_relative, [-np.inf, 0.8, 1.2, np.inf], ["vlow", "vnormal", "vhigh"])
    x["ma_location"] = cut_label(x.above_count.astype(float), [-np.inf, 2, 4, 6, np.inf], ["below01", "below23", "middle45", "above68"])

    prev_high = x.high.shift(1)
    prev_low = x.low.shift(1)
    x["inside"] = (x.high < prev_high) & (x.low > prev_low)
    x["outside"] = (x.high > prev_high) & (x.low < prev_low)
    hi20 = x.high.shift(1).rolling(20, min_periods=20).max()
    lo20 = x.low.shift(1).rolling(20, min_periods=20).min()
    x["high_sweep20"] = (x.high > hi20) & (x.close < hi20)
    x["low_sweep20"] = (x.low < lo20) & (x.close > lo20)
    x["breakout20"] = x.close > hi20
    x["breakdown20"] = x.close < lo20

    direction = np.where(x.body_ratio < 0.08, "N", np.where(x.close > x.open, "U", "D"))
    body_bin = pd.cut(x.body_ratio, [-np.inf, .10, .30, .60, np.inf], labels=["t", "s", "m", "l"], right=False).astype("string")
    upper_bin = pd.cut(x.upper_ratio, [-np.inf, .15, .40, np.inf], labels=["u0", "u1", "u2"], right=False).astype("string")
    lower_bin = pd.cut(x.lower_ratio, [-np.inf, .15, .40, np.inf], labels=["l0", "l1", "l2"], right=False).astype("string")
    close_bin = pd.cut(x.close_location, [-np.inf, .33, .67, np.inf], labels=["c0", "c1", "c2"], right=False).astype("string")
    range_bin = pd.cut(x.range_atr, [-np.inf, .70, 1.40, np.inf], labels=["q", "n", "e"], right=False).astype("string")
    event = np.select(
        [x.low_sweep20, x.high_sweep20, x.breakout20, x.breakdown20, x.outside & (x.close > x.open), x.outside & (x.close < x.open), x.inside],
        ["LS", "HS", "BO", "BD", "OU", "OD", "IN"], default="X",
    )
    x["shape_token"] = pd.Series(direction, index=x.index, dtype="string") + body_bin + upper_bin + lower_bin + close_bin + range_bin
    x["flow_token"] = x.shape_token + ":" + pd.Series(event, index=x.index, dtype="string")
    x["signal_time"] = x.index + pd.to_timedelta(period_hours, unit="h")
    return x


def add_forward_metrics(df: pd.DataFrame, horizons: Iterable[int]) -> pd.DataFrame:
    x = df.copy()
    for h in horizons:
        x[f"ret_{h}"] = (x.close.shift(-h) / x.close - 1) * 100
        future_high = pd.concat([x.high.shift(-k) for k in range(1, h + 1)], axis=1).max(axis=1)
        future_low = pd.concat([x.low.shift(-k) for k in range(1, h + 1)], axis=1).min(axis=1)
        x[f"mfe_{h}_atr"] = (future_high - x.close) / x.atr14
        x[f"mae_{h}_atr"] = (future_low - x.close) / x.atr14
    return x


