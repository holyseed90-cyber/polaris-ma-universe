

def split_mask(x: pd.DataFrame, split: str) -> np.ndarray:
    start, end = SPLITS[split]
    return ((x.signal_time >= start) & (x.signal_time < end)).to_numpy()


def dedupe_positions(pos: np.ndarray, gap: int) -> np.ndarray:
    if len(pos) == 0:
        return pos
    kept = [int(pos[0])]
    for p in pos[1:]:
        if int(p) - kept[-1] >= gap:
            kept.append(int(p))
    return np.asarray(kept, dtype=int)


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return np.nan, np.nan
    p = wins / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return centre - half, centre + half


def event_metric(x: pd.DataFrame, positions: np.ndarray, h: int, direction: str) -> dict:
    pos = dedupe_positions(np.sort(positions), h)
    if not len(pos):
        return {"n": 0}
    ret = x.iloc[pos][f"ret_{h}"].dropna()
    pos = pos[:len(ret)] if len(ret) != len(pos) else pos
    if ret.empty:
        return {"n": 0}
    signed = ret if direction == "bullish" else -ret
    wins = int((signed > 0).sum())
    lo, hi = wilson(wins, len(signed))
    mfe = x.iloc[pos][f"mfe_{h}"] if direction == "bullish" else -x.iloc[pos][f"mae_{h}"]
    mae = x.iloc[pos][f"mae_{h}"] if direction == "bullish" else -x.iloc[pos][f"mfe_{h}"]
    return {
        "n": int(len(signed)),
        "win_rate": float((signed > 0).mean()),
        "win_ci_low": float(lo),
        "win_ci_high": float(hi),
        "median_signed_ret": float(signed.median()),
        "mean_signed_ret": float(signed.mean()),
        "median_mfe_atr": float(mfe.median()),
        "median_mae_atr": float(mae.median()),
    }


def first_passage(x: pd.DataFrame, positions: np.ndarray, horizon: int, direction: str, mult: float = 1.0) -> dict:
    pos = dedupe_positions(np.sort(positions), horizon)
    target_first = stop_first = ambiguous = no_hit = 0
    for i in pos:
        if i + horizon >= len(x) or not np.isfinite(x.atr14.iloc[i]):
            continue
        entry, atr = float(x.close.iloc[i]), float(x.atr14.iloc[i])
        t = entry + mult * atr if direction == "bullish" else entry - mult * atr
        s = entry - mult * atr if direction == "bullish" else entry + mult * atr
        decided = False
        for j in range(i + 1, i + horizon + 1):
            hi, lo = float(x.high.iloc[j]), float(x.low.iloc[j])
            hit_t = hi >= t if direction == "bullish" else lo <= t
            hit_s = lo <= s if direction == "bullish" else hi >= s
            if hit_t and hit_s:
                ambiguous += 1
                decided = True
                break
            if hit_t:
                target_first += 1
                decided = True
                break
            if hit_s:
                stop_first += 1
                decided = True
                break
        if not decided:
            no_hit += 1
    n = target_first + stop_first
    lo, hi = wilson(target_first, n)
    return {
        "events": int(len(pos)), "target_first": target_first, "stop_first": stop_first,
        "ambiguous": ambiguous, "no_hit": no_hit,
        "decided_win_rate": target_first / n if n else np.nan,
        "wilson_low": lo, "wilson_high": hi,
    }


def evaluate_events(tf: str, x: pd.DataFrame, events: dict[str, tuple[pd.Series, str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    h = TF[tf]["ret_h"]
    perf_rows, fp_rows = [], []
    for name, (mask, direction) in events.items():
        all_pos = np.flatnonzero(mask.fillna(False).to_numpy())
        rec = {"timeframe": tf, "event": name, "direction": direction, "horizon_bars": h}
        for split in SPLITS:
            pos = all_pos[split_mask(x, split)[all_pos]]
            m = event_metric(x, pos, h, direction)
            for k, v in m.items():
                rec[f"{split}_{k}"] = v
            fp = first_passage(x, pos, h, direction, 1.0)
            fp_rows.append({"timeframe": tf, "event": name, "direction": direction, "split": split, "horizon_bars": h, **fp})
        perf_rows.append(rec)
    return pd.DataFrame(perf_rows), pd.DataFrame(fp_rows)


def ladder_first_passage(x: pd.DataFrame, short: int, long: int, direction: str, horizon: int) -> pd.DataFrame:
    rows = []
    if direction == "down":
        prior_above = (x.close.shift(1) > x[f"ma{short}"].shift(1)).rolling(10, min_periods=10).sum() >= 8
        signal = prior_above & (x.close < x[f"ma{short}"]) & (x.close.shift(1) >= x[f"ma{short}"].shift(1)) & (x[f"ma{short}_s20"] > 0)
    else:
        prior_below = (x.close.shift(1) < x[f"ma{short}"].shift(1)).rolling(10, min_periods=10).sum() >= 8
        signal = prior_below & (x.close > x[f"ma{short}"]) & (x.close.shift(1) <= x[f"ma{short}"].shift(1)) & (x[f"ma{short}_s20"] < 0)
    pos = np.flatnonzero(signal.fillna(False).to_numpy())
    for i in pos:
        if i + horizon >= len(x):
            continue
        outcome, bars = "no_hit", horizon
        for j in range(i + 1, i + horizon + 1):
            if not np.isfinite(x[f"ma{long}"].iloc[j]) or not np.isfinite(x[f"ma{short}"].iloc[j]):
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
                outcome, bars = "target_next_ma", j - i
                break
            if cancel:
                outcome, bars = "reclaim_short_ma", j - i
                break
        rows.append({
            "signal_time": x.signal_time.iloc[i], "short_ma": short, "long_ma": long,
            "direction": direction, "outcome": outcome, "bars": bars,
            "short_slope20": x[f"ma{short}_s20"].iloc[i], "short_acc": x[f"ma{short}_acc"].iloc[i],
            "gap_atr": abs(x[f"ma{short}"].iloc[i] - x[f"ma{long}"].iloc[i]) / x.atr14.iloc[i],
            "rsi14": x.rsi14.iloc[i],
        })
    return pd.DataFrame(rows)


def summarize_ladders(tf: str, x: pd.DataFrame) -> pd.DataFrame:
    rows = []
    pairs = [(14, 28), (28, 56), (112, 224), (224, 448), (448, 896)]
    for a, b in pairs:
        for direction in ["down", "up"]:
            raw = ladder_first_passage(x, a, b, direction, TF[tf]["ladder_h"])
            if raw.empty:
                continue
            for split, (start, end) in SPLITS.items():
                z = raw[(raw.signal_time >= start) & (raw.signal_time < end)]
                for subgroup, zz in [
                    ("all", z),
                    ("slope_decelerating", z[z.short_acc < 0] if direction == "down" else z[z.short_acc > 0]),
                    ("slope_not_decelerating", z[z.short_acc >= 0] if direction == "down" else z[z.short_acc <= 0]),
                ]:
                    decided = zz[zz.outcome.isin(["target_next_ma", "reclaim_short_ma"])]
                    n = len(decided)
                    wins = int((decided.outcome == "target_next_ma").sum())
                    lo, hi = wilson(wins, n)
                    rows.append({
                        "timeframe": tf, "short_ma": a, "long_ma": b, "direction": direction,
                        "split": split, "subgroup": subgroup, "events": len(zz), "decided": n,
                        "target_first": wins, "target_first_rate": wins / n if n else np.nan,
                        "wilson_low": lo, "wilson_high": hi,
                        "median_bars": float(decided.bars.median()) if n else np.nan,
                        "median_gap_atr": float(zz.gap_atr.median()) if len(zz) else np.nan,
                    })
    return pd.DataFrame(rows)
