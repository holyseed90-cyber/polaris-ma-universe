

def dedupe_positions(pos: np.ndarray, min_gap: int) -> np.ndarray:
    if len(pos) == 0:
        return pos
    kept = [int(pos[0])]
    for p in pos[1:]:
        if int(p) - kept[-1] >= min_gap:
            kept.append(int(p))
    return np.asarray(kept, dtype=int)


def kill_zone_kst(ts: pd.Timestamp) -> str:
    kst = ts.tz_convert("Asia/Seoul")
    h = kst.hour + kst.minute / 60
    if 8 <= h < 11:
        return "asia_kz"
    if 16 <= h < 19:
        return "london_kz"
    if 21 <= h < 24:
        return "newyork_kz"
    return "other"


def full_session_kst(ts: pd.Timestamp) -> str:
    h = ts.tz_convert("Asia/Seoul").hour
    # Overlapping sessions are encoded explicitly instead of forcing a false single label.
    active: list[str] = []
    if 9 <= h < 18:
        active.append("asia")
    if h >= 17 or h < 2:
        active.append("london")
    if h >= 22 or h < 7:
        active.append("newyork")
    return "+".join(active) if active else "off_session"


def simulate_rule(x: pd.DataFrame, mask: pd.Series, side: str, tf: str, venue: str, rule: str) -> pd.DataFrame:
    horizon = TIMEFRAMES[tf]["horizon"]
    positions = dedupe_positions(np.flatnonzero(mask.fillna(False).to_numpy()), horizon)
    rows: list[dict] = []
    for i in positions:
        if i + 1 + horizon >= len(x) or not np.isfinite(x.atr14.iloc[i]):
            continue
        entry_i = i + 1
        entry = float(x.open.iloc[entry_i])
        atr = float(x.atr14.iloc[i])
        if not np.isfinite(entry) or entry <= 0 or atr <= 0:
            continue
        target = entry + atr if side == "long" else entry - atr
        stop = entry - atr if side == "long" else entry + atr
        outcome = "time_exit"
        exit_price = float(x.close.iloc[entry_i + horizon])
        exit_i = entry_i + horizon
        for j in range(entry_i, entry_i + horizon + 1):
            hi, lo = float(x.high.iloc[j]), float(x.low.iloc[j])
            hit_target = hi >= target if side == "long" else lo <= target
            hit_stop = lo <= stop if side == "long" else hi >= stop
            if hit_target and hit_stop:
                # Conservative OHLC assumption: when intrabar order is unknown, stop wins.
                outcome, exit_price, exit_i = "ambiguous_as_stop", stop, j
                break
            if hit_stop:
                outcome, exit_price, exit_i = "stop", stop, j
                break
            if hit_target:
                outcome, exit_price, exit_i = "target", target, j
                break
        gross = ((exit_price / entry - 1) if side == "long" else (entry / exit_price - 1)) * 100
        signal_time = x.signal_time.iloc[i]
        kst = signal_time.tz_convert("Asia/Seoul")
        row = {
            "venue": venue, "timeframe": tf, "rule": rule, "side": side,
            "signal_time": signal_time, "entry_time": x.index[entry_i], "exit_time": x.index[exit_i],
            "entry": entry, "exit": exit_price, "atr_at_signal": atr,
            "atr_pct_at_signal": atr / float(x.close.iloc[i]) * 100,
            "outcome": outcome, "gross_return_pct": gross,
            "holding_bars": int(exit_i - entry_i + 1),
            "split": split_label(signal_time),
            "kill_zone": kill_zone_kst(signal_time),
            "full_session": full_session_kst(signal_time),
            "weekday_kst": kst.day_name(),
            "hour_kst": int(kst.hour),
        }
        for cost in COST_BPS:
            row[f"net_{cost}bps_pct"] = gross - cost / 100
        rows.append(row)
    return pd.DataFrame(rows)


def max_losing_streak(values: pd.Series) -> int:
    best = current = 0
    for v in values:
        if v <= 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def max_drawdown_pct(returns_pct: pd.Series) -> float:
    if returns_pct.empty:
        return np.nan
    equity = (1 + returns_pct.fillna(0) / 100).cumprod()
    peak = equity.cummax()
    dd = (equity / peak - 1) * 100
    return float(dd.min())


def trade_metrics(z: pd.DataFrame, cost: int) -> dict:
    col = f"net_{cost}bps_pct"
    if z.empty:
        return {"n": 0}
    vals = z.sort_values("signal_time")[col].astype(float)
    wins = vals[vals > 0]
    losses = vals[vals <= 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "n": int(len(vals)),
        "win_rate": float((vals > 0).mean()),
        "mean_net_pct": float(vals.mean()),
        "median_net_pct": float(vals.median()),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else np.inf,
        "max_drawdown_pct": max_drawdown_pct(vals),
        "max_losing_streak": max_losing_streak(vals),
        "target_rate": float((z.outcome == "target").mean()),
        "stop_rate": float(z.outcome.isin(["stop", "ambiguous_as_stop"]).mean()),
        "median_holding_bars": float(z.holding_bars.median()),
    }


def summarize_trades(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if trades.empty:
        return pd.DataFrame()
    group_cols = ["venue", "timeframe", "rule", "side", "split"]
    for keys, z in trades.groupby(group_cols, dropna=False):
        base = dict(zip(group_cols, keys))
        for cost in COST_BPS:
            rows.append({**base, "cost_bps": cost, **trade_metrics(z, cost)})
    return pd.DataFrame(rows)


def summarize_sessions(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if trades.empty:
        return pd.DataFrame()
    zall = trades[trades.split == "test"].copy()
    for dim in ["kill_zone", "weekday_kst"]:
        group_cols = ["venue", "timeframe", "rule", "side", dim]
        for keys, z in zall.groupby(group_cols, dropna=False):
            rows.append({
                **dict(zip(group_cols, keys)), "dimension": dim,
                "cost_bps": 20, **trade_metrics(z, 20),
            })
    return pd.DataFrame(rows)


def summarize_ladders(ladders: pd.DataFrame) -> pd.DataFrame:
    if ladders.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    cols = ["venue", "timeframe", "short_ma", "long_ma", "direction", "gap_bin", "split"]
    for keys, z in ladders.groupby(cols, dropna=False):
        decided = z[z.outcome.isin(["target", "cancel"])]
        n = len(decided)
        wins = int((decided.outcome == "target").sum())
        p = wins / n if n else np.nan
        if n:
            zscore = 1.96
            den = 1 + zscore * zscore / n
            centre = (p + zscore * zscore / (2 * n)) / den
            half = zscore * math.sqrt((p * (1 - p) + zscore * zscore / (4 * n)) / n) / den
            lo, hi = centre - half, centre + half
        else:
            lo = hi = np.nan
        rows.append({
            **dict(zip(cols, keys)), "events": len(z), "decided": n,
            "target_first": wins, "target_rate": p,
            "wilson_low": lo, "wilson_high": hi,
            "median_gap_atr": float(z.gap_atr.median()) if len(z) else np.nan,
            "median_bars": float(decided.bars.median()) if n else np.nan,
        })
    return pd.DataFrame(rows)
