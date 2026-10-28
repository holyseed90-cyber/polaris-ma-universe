

def touch_first_passage(x: pd.DataFrame, i: int, p: int, mode: str, horizon: int) -> dict:
    if i + horizon >= len(x) or not np.isfinite(x.atr14.iloc[i]):
        return {"outcome": "invalid", "bars": np.nan, "mfe_atr": np.nan, "mae_atr": np.nan}
    entry, atr0 = float(x.close.iloc[i]), float(x.atr14.iloc[i])
    fav, adv = 0.0, 0.0
    for j in range(i + 1, i + horizon + 1):
        hi, lo = float(x.high.iloc[j]), float(x.low.iloc[j])
        ma, atr = float(x[f"ma{p}"].iloc[j]), float(x.atr14.iloc[j])
        if not all(np.isfinite(v) for v in (ma, atr)):
            continue
        if mode == "bull":
            fav = max(fav, (hi - entry) / atr0)
            adv = min(adv, (lo - entry) / atr0)
            target = hi >= entry + atr0
            broken = x.close.iloc[j] <= ma - 0.50 * atr
        else:
            fav = max(fav, (entry - lo) / atr0)
            adv = min(adv, (entry - hi) / atr0)
            target = lo <= entry - atr0
            broken = x.close.iloc[j] >= ma + 0.50 * atr
        if target and broken:
            return {"outcome": "ambiguous", "bars": j - i, "mfe_atr": fav, "mae_atr": adv}
        if target:
            return {"outcome": "defense", "bars": j - i, "mfe_atr": fav, "mae_atr": adv}
        if broken:
            return {"outcome": "break", "bars": j - i, "mfe_atr": fav, "mae_atr": adv}
    return {"outcome": "no_hit", "bars": horizon, "mfe_atr": fav, "mae_atr": adv}


def touch_defense_study(tf: str, x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon, sep = TF[tf]["ret_h"], TF[tf]["touch_sep"]
    raw_rows, summary_rows = [], []
    for p in STUDY_MAS:
        for mode in ("bull", "bear"):
            ords = independent_touch_ordinals(x, p, mode, sep)
            for i in np.flatnonzero(ords.gt(0).to_numpy()):
                ordinal = int(ords.iloc[i])
                result = touch_first_passage(x, i, p, mode, horizon)
                accel = float(x[f"ma{p}_lr_acc5"].iloc[i])
                curve = float(x[f"ma{p}_curve5"].iloc[i])
                if mode == "bull":
                    accel_state = "with_trend" if accel >= 0 else "flattening"
                    curve_state = "with_trend" if curve >= 0 else "flattening"
                else:
                    accel_state = "with_trend" if accel <= 0 else "flattening"
                    curve_state = "with_trend" if curve <= 0 else "flattening"
                raw_rows.append({
                    "timeframe": tf, "signal_time": x.signal_time.iloc[i], "ma": p,
                    "mode": mode, "ordinal": 1 if ordinal == 1 else 2 if ordinal == 2 else 3,
                    "lr20_atr_per_bar": x[f"ma{p}_lr20"].iloc[i],
                    "lr_acc5": accel, "curve5": curve,
                    "accel_state": accel_state, "curve_state": curve_state,
                    "rsi14": x.rsi14.iloc[i], **result,
                })
    raw = pd.DataFrame(raw_rows)
    if raw.empty:
        return raw, pd.DataFrame()
    raw["split"] = raw.signal_time.map(split_name)
    for split in SPLITS:
        z = raw[raw.split == split]
        for (p, mode, ordinal), base in z.groupby(["ma", "mode", "ordinal"]):
            for context_name, context_value, g in [
                ("all", "all", base),
                ("accel_state", "with_trend", base[base.accel_state == "with_trend"]),
                ("accel_state", "flattening", base[base.accel_state == "flattening"]),
                ("curve_state", "with_trend", base[base.curve_state == "with_trend"]),
                ("curve_state", "flattening", base[base.curve_state == "flattening"]),
            ]:
                decided = g[g.outcome.isin(["defense", "break"])]
                n = len(decided)
                wins = int((decided.outcome == "defense").sum())
                lo, hi = wilson(wins, n)
                summary_rows.append({
                    "timeframe": tf, "split": split, "ma": p, "mode": mode,
                    "ordinal": ordinal, "context_name": context_name,
                    "context_value": context_value, "events": len(g), "decided": n,
                    "defense_first": wins, "defense_rate": wins / n if n else np.nan,
                    "wilson_low": lo, "wilson_high": hi,
                    "median_mfe_atr": float(g.mfe_atr.median()) if len(g) else np.nan,
                    "median_mae_atr": float(g.mae_atr.median()) if len(g) else np.nan,
                    "median_bars": float(decided.bars.median()) if n else np.nan,
                })
    return raw, pd.DataFrame(summary_rows)


def price_first_passage(x: pd.DataFrame, i: int, direction: str, horizon: int, mult: float = 1.0) -> dict:
    if i + horizon >= len(x) or not np.isfinite(x.atr14.iloc[i]):
        return {"outcome": "invalid", "bars": np.nan}
    entry, atr = float(x.close.iloc[i]), float(x.atr14.iloc[i])
    for j in range(i + 1, i + horizon + 1):
        hi, lo = float(x.high.iloc[j]), float(x.low.iloc[j])
        if direction == "bullish":
            hit_t, hit_s = hi >= entry + mult * atr, lo <= entry - mult * atr
        else:
            hit_t, hit_s = lo <= entry - mult * atr, hi >= entry + mult * atr
        if hit_t and hit_s:
            return {"outcome": "ambiguous", "bars": j - i}
        if hit_t:
            return {"outcome": "target", "bars": j - i}
        if hit_s:
            return {"outcome": "stop", "bars": j - i}
    return {"outcome": "no_hit", "bars": horizon}


def support_migration_study(tf: str, x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = [14, 28, 56, 112, 224, 448]
    sep, horizon = TF[tf]["touch_sep"], TF[tf]["ret_h"]
    contacts = []
    for p in periods:
        ords = independent_touch_ordinals(x, p, "bull", sep)
        for i in np.flatnonzero(ords.gt(0).to_numpy()):
            contacts.append((i, p))
    if not contacts:
        return pd.DataFrame(), pd.DataFrame()
    # When one candle touches several compressed averages, the longest average is
    # the deepest support reached and is retained as the event label.
    by_i: dict[int, int] = {}
    for i, p in contacts:
        by_i[i] = max(by_i.get(i, 0), p)
    ordered = sorted(by_i.items())
    rows = []
    previous: tuple[int, int] | None = None
    episode_gap = max(20, 6 * horizon)
    for i, p in ordered:
        if previous is None or i - previous[0] > episode_gap:
            previous = (i, p)
            continue
        prev_i, prev_p = previous
        migration = "shorter" if p < prev_p else "longer" if p > prev_p else "same"
        result = price_first_passage(x, i, "bullish", horizon, 1.0)
        rows.append({
            "timeframe": tf, "signal_time": x.signal_time.iloc[i],
            "previous_ma": prev_p, "current_ma": p, "migration": migration,
            "bars_since_prior": i - prev_i, "rsi14": x.rsi14.iloc[i],
            "long_bull_stack": bool(x.polaris_long_bull.iloc[i]), **result,
        })
        previous = (i, p)
    raw = pd.DataFrame(rows)
    if raw.empty:
        return raw, pd.DataFrame()
    raw["split"] = raw.signal_time.map(split_name)
    summary = []
    for split in SPLITS:
        z = raw[raw.split == split]
        for migration, g in z.groupby("migration"):
            decided = g[g.outcome.isin(["target", "stop"])]
            n = len(decided)
            wins = int((decided.outcome == "target").sum())
            lo, hi = wilson(wins, n)
            summary.append({
                "timeframe": tf, "split": split, "migration": migration,
                "events": len(g), "decided": n, "target_first": wins,
                "target_rate": wins / n if n else np.nan,
                "wilson_low": lo, "wilson_high": hi,
                "median_bars": float(decided.bars.median()) if n else np.nan,
            })
    return raw, pd.DataFrame(summary)
