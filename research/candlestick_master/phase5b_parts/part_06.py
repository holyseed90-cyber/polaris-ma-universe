                consensus = 0
                spot_same = False
                for venue, mdf in venue_mask_frames.items():
                    if signal_time not in mdf.index:
                        continue
                    same = any(name in mdf.columns and bool(mdf.at[signal_time, name]) for name in active)
                    consensus += int(same)
                    if venue == SPOT:
                        spot_same = same
                event["f_spot_same_base"] = spot_same
                event["f_consensus_ge2"] = consensus >= 2
                event["f_consensus_ge3"] = consensus >= 3
                event["f_consensus_ge4"] = consensus >= 4
                event["consensus_count"] = consensus

                # Spot directional context at exactly the same completed candle.
                if signal_time in venue_signal_frames[SPOT].index:
                    sr = venue_signal_frames[SPOT].loc[signal_time]
                    if isinstance(sr, pd.DataFrame):
                        sr = sr.iloc[-1]
                    long_side = side == "long"
                    event["f_spot_bias_align"] = bool(sr.get("bull_bias_score", 0) >= 2 if long_side else sr.get("bear_bias_score", 0) >= 2)
                    event["f_spot_structure_align"] = sr.get("structure_state") == ("bull" if long_side else "bear")
                    event["f_spot_ma_align"] = bool(sr.get("above_count", 0) >= 6 if long_side else sr.get("above_count", 8) <= 2)
                    spot_close = float(sr.close)
                    perp_close = float(row.close)
                    basis_bps = (perp_close / spot_close - 1) * 10000 if spot_close else np.nan
                    spot_range = float(sr.high - sr.low)
                    perp_range = float(row.high - row.low)
                    range_ratio = perp_range / spot_range if spot_range > 0 else np.nan
                    event["basis_bps"] = basis_bps
                    event["range_ratio"] = range_ratio
                    event["f_basis_normal"] = bool(np.isfinite(basis_bps) and abs(basis_bps) <= 15)
                    event["f_range_ratio_normal"] = bool(np.isfinite(range_ratio) and 0.75 <= range_ratio <= 1.35)
                else:
                    event.update({
                        "f_spot_bias_align": False, "f_spot_structure_align": False,
                        "f_spot_ma_align": False, "basis_bps": np.nan,
                        "range_ratio": np.nan, "f_basis_normal": False,
                        "f_range_ratio_normal": False,
                    })
                event["f_kz_asia"] = event["kill_zone"] == "asia_kz"
                event["f_kz_london"] = event["kill_zone"] == "london_kz"
                event["f_kz_newyork"] = event["kill_zone"] == "newyork_kz"
                event["f_kz_other"] = event["kill_zone"] == "other"
                rows.append(event)
    events = pd.DataFrame(rows).sort_values(["signal_time", "timeframe", "side"]).reset_index(drop=True)
    events["event_id"] = np.arange(len(events), dtype=int)
    bool_cols = [c for c in events.columns if c.startswith(("b_", "f_"))]
    events[bool_cols] = events[bool_cols].fillna(False).astype(bool)
    return events, masks


def simulate_event(x: pd.DataFrame, bar_index: int, side: str, target_mult: float, stop_mult: float, hold: int) -> dict:
    i = int(bar_index)
    if i + 1 + hold >= len(x) or not np.isfinite(x.atr14.iloc[i]):
        return {"valid": False}
    entry_i = i + 1
    entry = float(x.open.iloc[entry_i])
    atr = float(x.atr14.iloc[i])
    if entry <= 0 or atr <= 0 or not np.isfinite(entry):
        return {"valid": False}
    target = entry + target_mult * atr if side == "long" else entry - target_mult * atr
    stop = entry - stop_mult * atr if side == "long" else entry + stop_mult * atr
    outcome = "time_exit"
    exit_i = entry_i + hold
    exit_price = float(x.close.iloc[exit_i])
    for j in range(entry_i, entry_i + hold + 1):
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
    result = {
        "valid": True,
        "entry": entry,
        "target_price": target,
        "stop_price": stop,
        "exit": exit_price,
        "exit_time": x.index[exit_i],
