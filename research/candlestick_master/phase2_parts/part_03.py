            # until the candidate has already been selected and ranked.
            if int(record.get("validation_n", 0) or 0) < cfg["min_test"]:
                continue
            if float(record.get("validation_median_signed_ret", -999)) <= 0:
                continue
            if float(record.get("validation_win_rate", 0)) < 0.52:
                continue
            record["selection_score"] = float(
                min(record["train_win_rate"], record["validation_win_rate"])
                * math.log1p(record["validation_n"])
                * min(record["train_median_signed_ret"], record["validation_median_signed_ret"])
            )
            test_n = int(record.get("test_n", 0) or 0)
            record["test_survives"] = bool(
                test_n >= cfg["min_test"]
                and float(record.get("test_median_signed_ret", -999)) > 0
                and float(record.get("test_win_rate", 0)) >= 0.52
            )
            rows.append(record)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["selection_score", "validation_n"], ascending=[False, False]).reset_index(drop=True)
    return out, sequence_series


def first_passage(df: pd.DataFrame, positions: np.ndarray, horizon: int, direction: str, multiple: float) -> dict:
    pos = dedupe_positions(np.sort(positions), horizon)
    target_first = stop_first = no_hit = ambiguous = 0
    outcomes: list[int] = []
    for i in pos:
        if i + horizon >= len(df) or not np.isfinite(df.atr14.iloc[i]):
            continue
        entry = float(df.close.iloc[i])
        atr = float(df.atr14.iloc[i])
        if direction == "bullish":
            target = entry + multiple * atr
            stop = entry - multiple * atr
        else:
            target = entry - multiple * atr
            stop = entry + multiple * atr
        result = 0
        for j in range(i + 1, i + horizon + 1):
            hi, lo = float(df.high.iloc[j]), float(df.low.iloc[j])
            if direction == "bullish":
                hit_t, hit_s = hi >= target, lo <= stop
            else:
                hit_t, hit_s = lo <= target, hi >= stop
            if hit_t and hit_s:
                ambiguous += 1
                result = 2
                break
            if hit_t:
                target_first += 1
                outcomes.append(1)
                result = 1
                break
            if hit_s:
                stop_first += 1
                outcomes.append(0)
                result = -1
                break
        if result == 0:
            no_hit += 1
    n_decided = target_first + stop_first
    if n_decided:
        ci = wilson_ci(target_first, n_decided)
        win = target_first / n_decided
        # Bootstrap over independent, de-duplicated events.
        arr = np.asarray(outcomes, dtype=float)
        if len(arr) >= 8:
            boot = np.asarray([RNG.choice(arr, size=len(arr), replace=True).mean() for _ in range(400)])
            b_lo, b_hi = np.quantile(boot, [0.025, 0.975])
        else:
            b_lo = b_hi = np.nan
    else:
        win = np.nan
        ci = (np.nan, np.nan)
        b_lo = b_hi = np.nan
    return {
        "events": int(len(pos)), "target_first": target_first, "stop_first": stop_first,
        "ambiguous": ambiguous, "no_hit": no_hit, "decided_win_rate": win,
        "wilson_low": ci[0], "wilson_high": ci[1], "bootstrap_low": b_lo, "bootstrap_high": b_hi,
    }


def evaluate_first_passage(tf: str, df: pd.DataFrame, candidates: pd.DataFrame, seq_map: dict[str, pd.Series], max_candidates: int = 80) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    rows = []
    h = TF_RULES[tf]["rank_h"]
    for _, c in candidates.head(max_candidates).iterrows():
        key = f"{c.token_type}_{int(c.length)}"
        seq = seq_map[key]
        all_pos = np.flatnonzero(seq.eq(c.sequence).fillna(False).to_numpy())
        for split, (start, end) in SPLITS.items():
            mask = ((df.signal_time.iloc[all_pos] >= start) & (df.signal_time.iloc[all_pos] < end)).to_numpy()
            pos = all_pos[mask]
            for mult in [0.5, 1.0, 1.5, 2.0]:
                r = first_passage(df, pos, h, c.direction, mult)
                rows.append({
