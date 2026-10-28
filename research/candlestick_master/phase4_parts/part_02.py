                    "rsi14": float(x.rsi14.iloc[i]),
                    "atr_pct": float(x.atr_pct.iloc[i]),
                    "atr_relative": float(x.atr_relative.iloc[i]),
                    "above_count": int(x.above_count.iloc[i]),
                    "side_slope_count": int(side_slope),
                    "long_state": long_state,
                    "target_gap_atr": gap,
                    "body_multiple": float(x.body_multiple.iloc[i]) if np.isfinite(x.body_multiple.iloc[i]) else np.nan,
                    "kill_zone": p3.kill_zone_kst(signal_time),
                    "weekday_kst": signal_time.tz_convert("Asia/Seoul").day_name(),
                    "hour_kst": int(signal_time.tz_convert("Asia/Seoul").hour),
                    "htf_align_value": htf_value,
                    "htf_align_bin": htf_label,
                    "rsi_bin": rsi_bin(float(x.rsi14.iloc[i])),
                    "atr_state": atr_state(float(x.atr_relative.iloc[i])),
                    "above_bin": above_bin(float(x.above_count.iloc[i])),
                    "slope_bin": slope_bin(side_slope),
                    "target_gap_bin": target_gap_bin(gap),
                })
    return pd.DataFrame(rows)


def add_consensus(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    e = events.copy()
    exact = e.groupby(["timeframe", "rule", "side", "signal_time"])["venue"].transform("nunique")
    e["consensus_exact"] = exact.astype(int)
    e["consensus_near"] = 1
    for keys, idx in e.groupby(["timeframe", "rule", "side"]).groups.items():
        positions = np.asarray(list(idx), dtype=int)
        z = e.loc[positions].copy()
        hours = p3.TIMEFRAMES[keys[0]]["hours"]
        times = z.signal_time.astype("int64").to_numpy()
        venues = z.venue.astype(str).to_numpy()
        tol = int(pd.Timedelta(hours=hours).value)
        by_venue = {
            venue: np.sort(times[venues == venue])
            for venue in np.unique(venues)
        }
        out = np.ones(len(z), dtype=int)
        for k, t in enumerate(times):
            count = 0
            for arr in by_venue.values():
                # Causal agreement only: a same/previous venue signal may be used,
                # but a signal occurring after the current signal is never counted.
                left = np.searchsorted(arr, t - tol, side="left")
                right = np.searchsorted(arr, t, side="right")
                count += int(right > left)
            out[k] = count
        e.loc[positions, "consensus_near"] = out
    e["consensus_bin"] = e.consensus_near.map(count_bin)
    e["event_id"] = np.arange(len(e), dtype=int)
    return e


def simulate_one(x: pd.DataFrame, i: int, side: str, target_mult: float, stop_mult: float, max_hold: int) -> dict:
    if i + 1 + max_hold >= len(x):
        return {"valid": False}
    entry_i = i + 1
    entry = float(x.open.iloc[entry_i])
    atr = float(x.atr14.iloc[i])
    if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr) or atr <= 0:
        return {"valid": False}
    target = entry + target_mult * atr if side == "long" else entry - target_mult * atr
    stop = entry - stop_mult * atr if side == "long" else entry + stop_mult * atr
    outcome = "time_exit"
    exit_i = entry_i + max_hold
    exit_price = float(x.close.iloc[exit_i])
    for j in range(entry_i, entry_i + max_hold + 1):
        hi, lo = float(x.high.iloc[j]), float(x.low.iloc[j])
        hit_t = hi >= target if side == "long" else lo <= target
        hit_s = lo <= stop if side == "long" else hi >= stop
        if hit_t and hit_s:
            outcome, exit_i, exit_price = "ambiguous_as_stop", j, stop
            break
        if hit_s:
            outcome, exit_i, exit_price = "stop", j, stop
            break
        if hit_t:
            outcome, exit_i, exit_price = "target", j, target
            break
    gross = ((exit_price / entry - 1) if side == "long" else (entry / exit_price - 1)) * 100
    return {
        "valid": True, "entry": entry, "exit": exit_price,
        "exit_time": x.index[exit_i], "outcome": outcome,
        "holding_bars": int(exit_i - entry_i + 1),
        "gross_pct": gross, "net_pct": gross - COST_BPS / 100,
    }


def simulate_config(events: pd.DataFrame, all_frames: dict[str, dict[str, pd.DataFrame]], tf: str, side: str, target_mult: float, stop_mult: float, max_hold: int) -> pd.DataFrame:
    z = events[(events.timeframe == tf) & (events.side == side)].copy()
    rows: list[dict] = []
    for r in z.itertuples(index=False):
        result = simulate_one(all_frames[r.venue][tf], int(r.bar_index), side, target_mult, stop_mult, max_hold)
        if result.get("valid"):
            rows.append({"event_id": int(r.event_id), **result})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["config_id"] = f"T{target_mult:g}_S{stop_mult:g}_H{max_hold}"
    return out


def config_grid(all_events: pd.DataFrame, all_frames: dict[str, dict[str, pd.DataFrame]]) -> dict[tuple[str, str, str], pd.DataFrame]:
    cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    for tf in p3.TIMEFRAMES:
        for side in ["long", "short"]:
            if all_events[(all_events.timeframe == tf) & (all_events.side == side)].empty:
                continue
            for target in TARGETS:
                for stop in STOPS:
                    for hold in HOLD_GRID[tf]:
                        out = simulate_config(all_events, all_frames, tf, side, target, stop, hold)
                        cache[(tf, side, f"T{target:g}_S{stop:g}_H{hold}")] = out
    return cache


def period_mask(times: pd.Series, start: str, end: str) -> pd.Series:
    t = pd.to_datetime(times, utc=True)
