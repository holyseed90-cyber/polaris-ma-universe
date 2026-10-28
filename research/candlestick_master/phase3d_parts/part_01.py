

def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return normalize(
        df.resample(rule, origin="epoch", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
    )


def wilder_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df.close.shift(1)
    tr = pd.concat([(df.high - df.low), (df.high - prev).abs(), (df.low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def wilder_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    gain = d.clip(lower=0)
    loss = (-d).clip(lower=0)
    ag = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    al = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + ag / al.replace(0, np.nan))


def enrich(df: pd.DataFrame, hours: int) -> pd.DataFrame:
    x = df.copy()
    x["signal_time"] = x.index + pd.to_timedelta(hours, unit="h")
    x["atr14"] = wilder_atr(x)
    x["rsi14"] = wilder_rsi(x.close)
    x["atr_pct"] = x.atr14 / x.close * 100
    x["body"] = (x.close - x.open).abs()
    x["body_avg14_prior"] = x.body.shift(1).rolling(14, min_periods=14).mean()
    x["body_multiple"] = x.body / x.body_avg14_prior.replace(0, np.nan)
    for p in MAS:
        x[f"ma{p}"] = x.close.rolling(p, min_periods=p).mean()
        x[f"ma{p}_s20"] = (x[f"ma{p}"] / x[f"ma{p}"].shift(20) - 1) * 100
    x["above_count"] = pd.concat([(x.close > x[f"ma{p}"]) for p in [5, 10, 20, 60, 112, 224, 448, 896]], axis=1).sum(axis=1)
    x["long_bull_stack"] = (x.ma224 > x.ma448) & (x.ma448 > x.ma896)
    x["long_bear_stack"] = (x.ma224 < x.ma448) & (x.ma448 < x.ma896)
    hi20 = x.high.shift(1).rolling(20, min_periods=20).max()
    lo20 = x.low.shift(1).rolling(20, min_periods=20).min()
    x["low_sweep20"] = (x.low < lo20) & (x.close > lo20)
    x["high_sweep20"] = (x.high > hi20) & (x.close < hi20)
    x["bull_spring"] = x.low_sweep20 & (x.close > x.open) & ((x.close - x.low) >= 0.55 * (x.high - x.low))
    x["bear_upthrust"] = x.high_sweep20 & (x.close < x.open) & ((x.high - x.close) >= 0.55 * (x.high - x.low))
    return x


def build_rules(x: pd.DataFrame, tf: str) -> dict[str, tuple[pd.Series, str]]:
    rules: dict[str, tuple[pd.Series, str]] = {}
    rules["low_sweep_rsi30_40"] = (x.low_sweep20 & x.rsi14.between(30, 40, inclusive="left"), "long")
    rules["high_sweep_rsi60_70"] = (x.high_sweep20 & x.rsi14.between(60, 70, inclusive="left"), "short")
    rules["low_sweep_broad_bear"] = (x.low_sweep20 & (x.above_count <= 2), "long")
    rules["high_sweep_broad_bull"] = (x.high_sweep20 & (x.above_count >= 6), "short")
    rules["spring_broad_bear"] = (x.bull_spring & (x.above_count <= 2), "long")
    rules["upthrust_broad_bull"] = (x.bear_upthrust & (x.above_count >= 6), "short")
    rules["spring_confirm"] = (x.bull_spring.shift(1).fillna(False) & (x.close > x.high.shift(1)), "long")
    rules["upthrust_confirm"] = (x.bear_upthrust.shift(1).fillna(False) & (x.close < x.low.shift(1)), "short")
    if tf in {"4h", "12h", "1d"}:
        prior_bull_3x = (x.close.shift(1) > x.open.shift(1)) & (x.body_multiple.shift(1) >= 3.0)
        prior_bear_3x = (x.close.shift(1) < x.open.shift(1)) & (x.body_multiple.shift(1) >= 3.0)
        prior_mid = (x.open.shift(1) + x.close.shift(1)) / 2
        rules["bull_3x_break_high"] = (prior_bull_3x & (x.close > x.high.shift(1)), "long")
        rules["bear_3x_break_low"] = (prior_bear_3x & (x.close < x.low.shift(1)), "short")
        rules["bull_3x_upper_half_hold"] = (prior_bull_3x & (x.close > prior_mid), "long")
        rules["bear_3x_lower_half_hold"] = (prior_bear_3x & (x.close < prior_mid), "short")
    return rules


def split_label(ts: pd.Timestamp) -> str | None:
    for name, (start, end) in SPLITS.items():
        if start <= ts < end:
            return name
    return None


def gap_bin(v: float) -> str:
    if not np.isfinite(v):
        return "na"
    if v < 1:
        return "lt1"
    if v < 2:
        return "1to2"
    if v < 3:
        return "2to3"
    if v < 4:
        return "3to4"
    return "ge4"


def ladder_events(x: pd.DataFrame, tf: str) -> pd.DataFrame:
    horizon = {"1h": 168, "4h": 42, "12h": 14, "1d": 14}[tf]
    rows: list[dict] = []
    for short, long in [(112, 224), (224, 448), (448, 896)]:
        for direction in ["down", "up"]:
            if direction == "down":
                prior = (x.close.shift(1) > x[f"ma{short}"].shift(1)).rolling(10, min_periods=10).sum() >= 8
                signal = prior & (x.close < x[f"ma{short}"]) & (x.close.shift(1) >= x[f"ma{short}"].shift(1))
            else:
                prior = (x.close.shift(1) < x[f"ma{short}"].shift(1)).rolling(10, min_periods=10).sum() >= 8
                signal = prior & (x.close > x[f"ma{short}"]) & (x.close.shift(1) <= x[f"ma{short}"].shift(1))
            positions = np.flatnonzero(signal.fillna(False).to_numpy())
            last_kept = -10_000
            for i in positions:
                if i - last_kept < horizon or i + horizon >= len(x) or not np.isfinite(x.atr14.iloc[i]):
                    continue
                last_kept = i
                outcome, bars = "no_hit", horizon
                for j in range(i + 1, i + horizon + 1):
                    if not np.isfinite(x[f"ma{long}"].iloc[j]):
                        continue
                    if direction == "down":
                        target = x.low.iloc[j] <= x[f"ma{long}"].iloc[j] + 0.10 * x.atr14.iloc[j]
                        cancel = x.close.iloc[j] > x[f"ma{short}"].iloc[j] + 0.10 * x.atr14.iloc[j]
                    else:
                        target = x.high.iloc[j] >= x[f"ma{long}"].iloc[j] - 0.10 * x.atr14.iloc[j]
                        cancel = x.close.iloc[j] < x[f"ma{short}"].iloc[j] - 0.10 * x.atr14.iloc[j]
                    if target and cancel:
                        outcome, bars = "ambiguous", j - i
                        break
                    if target:
                        outcome, bars = "target", j - i
                        break
                    if cancel:
                        outcome, bars = "cancel", j - i
                        break
                g = abs(x[f"ma{short}"].iloc[i] - x[f"ma{long}"].iloc[i]) / x.atr14.iloc[i]
                rows.append({
                    "signal_time": x.signal_time.iloc[i], "timeframe": tf,
                    "short_ma": short, "long_ma": long, "direction": direction,
                    "gap_atr": float(g), "gap_bin": gap_bin(float(g)),
                    "outcome": outcome, "bars": bars,
                })
    return pd.DataFrame(rows)
