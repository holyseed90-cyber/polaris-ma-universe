        med = float(pd.to_numeric(ts, errors="coerce").dropna().median())
        raw["timestamp"] = pd.to_datetime(ts, unit="ms" if med > 10_000_000_000 else "s", utc=True, errors="coerce")
    else:
        raw["timestamp"] = pd.to_datetime(ts, utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in raw.columns:
            if col == "volume": raw[col] = 0.0
            else: raise ValueError(f"Missing {col}: {raw.columns.tolist()}")
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    out = raw[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").set_index("timestamp")
    return out.loc[out.index >= pd.Timestamp("2018-01-01", tz="UTC")]


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, origin="epoch", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open", "high", "low", "close"])


def wilder_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df.close.shift(1)
    tr = pd.concat([(df.high-df.low), (df.high-prev).abs(), (df.low-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()


def wilder_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff(); gain = diff.clip(lower=0); loss = (-diff).clip(lower=0)
    ag = gain.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    al = loss.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100/(1+rs)).where(ag.notna())


def confirmed_pivots(df: pd.DataFrame, left: int, right: int) -> pd.DataFrame:
    """Mark pivots only on their confirmation bar; no future leak at signal time."""
    x = df.copy()
    win = left + right + 1
    raw_ph = x.high.eq(x.high.rolling(win, center=True, min_periods=win).max())
    raw_pl = x.low.eq(x.low.rolling(win, center=True, min_periods=win).min())
    # Values become knowable `right` bars later.
    x["pivot_high_confirmed"] = x.high.where(raw_ph).shift(right)
    x["pivot_low_confirmed"] = x.low.where(raw_pl).shift(right)
    x["pivot_high_origin_time"] = pd.Series(x.index.where(raw_ph), index=x.index).shift(right)
    x["pivot_low_origin_time"] = pd.Series(x.index.where(raw_pl), index=x.index).shift(right)
    x["last_pivot_high"] = x.pivot_high_confirmed.ffill()
    x["last_pivot_low"] = x.pivot_low_confirmed.ffill()
    x["prev_pivot_high"] = x.pivot_high_confirmed.where(x.pivot_high_confirmed.notna()).ffill().shift(1)
    x["prev_pivot_low"] = x.pivot_low_confirmed.where(x.pivot_low_confirmed.notna()).ffill().shift(1)
    return x


def enrich(df: pd.DataFrame, hours: int, pivot: int) -> pd.DataFrame:
    x = confirmed_pivots(df, pivot, pivot)
    x["atr14"] = wilder_atr(x)
    x["atr_pct"] = x.atr14 / x.close * 100
    x["rsi14"] = wilder_rsi(x.close)
    rng = (x.high-x.low).replace(0, np.nan)
    body = (x.close-x.open).abs(); top = x[["open","close"]].max(axis=1); bot=x[["open","close"]].min(axis=1)
    x["body_ratio"] = (body/rng).fillna(0).clip(0,1)
    x["upper_ratio"] = ((x.high-top)/rng).fillna(0).clip(0,1)
    x["lower_ratio"] = ((bot-x.low)/rng).fillna(0).clip(0,1)
    x["close_location"] = ((x.close-x.low)/rng).fillna(.5).clip(0,1)
    x["range_atr"] = rng/x.atr14
    x["volume_z"] = (x.volume - x.volume.rolling(100, min_periods=30).mean()) / x.volume.rolling(100, min_periods=30).std().replace(0,np.nan)
    for p in MA_PERIODS:
        x[f"ma{p}"] = x.close.rolling(p, min_periods=p).mean()
        x[f"ma{p}_slope20"] = (x[f"ma{p}"]/x[f"ma{p}"].shift(20)-1)*100
    above = pd.concat([(x.close>x[f"ma{p}"]).rename(str(p)) for p in MA_PERIODS], axis=1)
    rising = pd.concat([(x[f"ma{p}_slope20"]>0).rename(str(p)) for p in MA_PERIODS], axis=1)
    x["above_count"] = above.sum(axis=1); x["rising_count"] = rising.sum(axis=1)
    x["trend_regime"] = np.select(
        [(x.above_count>=7)&(x.rising_count>=6), (x.above_count<=1)&(x.rising_count<=2)],
        ["broad_bull","broad_bear"], default="mixed")
    x["long_state"] = np.select(
