

def forward_event_metric(x: pd.DataFrame, pos: np.ndarray, direction: str, h: int) -> dict:
    pos = dedupe_positions(np.sort(pos), h)
    pos = pos[pos + h < len(x)]
    if len(pos) == 0:
        return {"n": 0}
    ret = x.iloc[pos][f"ret_{h}"].astype(float)
    signed = ret if direction == "bullish" else -ret
    wins = int((signed > 0).sum())
    lo, hi = wilson(wins, len(signed))
    mfe = x.iloc[pos][f"mfe_{h}"] if direction == "bullish" else -x.iloc[pos][f"mae_{h}"]
    mae = x.iloc[pos][f"mae_{h}"] if direction == "bullish" else -x.iloc[pos][f"mfe_{h}"]
    return {
        "n": len(pos), "win_rate": float((signed > 0).mean()),
        "wilson_low": lo, "wilson_high": hi,
        "median_signed_ret": float(signed.median()),
        "mean_signed_ret": float(signed.mean()),
        "median_mfe_atr": float(mfe.median()),
        "median_mae_atr": float(mae.median()),
    }


def long_body_confirmation_study(tf: str, x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    h = TF[tf]["ret_h"]
    prev_bull = (x.bull & (x.body_multiple >= 3.0)).shift(1).fillna(False)
    prev_bear = (x.bear & (x.body_multiple >= 3.0)).shift(1).fillna(False)
    prev_mid = (x.open.shift(1) + x.close.shift(1)) / 2
    prev_high, prev_low = x.high.shift(1), x.low.shift(1)
    category = pd.Series(pd.NA, index=x.index, dtype="string")
    direction = pd.Series(pd.NA, index=x.index, dtype="string")

    category.loc[prev_bull & (x.close > prev_high)] = "bull_break_high"
    direction.loc[prev_bull & (x.close > prev_high)] = "bullish"
    m = prev_bull & category.isna() & (x.low > prev_mid) & (x.close > prev_mid)
    category.loc[m], direction.loc[m] = "bull_upper_half_hold", "bullish"
    m = prev_bull & category.isna() & (x.low <= prev_mid) & (x.close > prev_mid)
    category.loc[m], direction.loc[m] = "bull_midpoint_reclaim", "bullish"
    m = prev_bull & category.isna() & (x.close <= prev_mid)
    category.loc[m], direction.loc[m] = "bull_midpoint_fail", "bearish"

    category.loc[prev_bear & (x.close < prev_low)] = "bear_break_low"
    direction.loc[prev_bear & (x.close < prev_low)] = "bearish"
    m = prev_bear & category.isna() & (x.high < prev_mid) & (x.close < prev_mid)
    category.loc[m], direction.loc[m] = "bear_lower_half_hold", "bearish"
    m = prev_bear & category.isna() & (x.high >= prev_mid) & (x.close < prev_mid)
    category.loc[m], direction.loc[m] = "bear_midpoint_reject", "bearish"
    m = prev_bear & category.isna() & (x.close >= prev_mid)
    category.loc[m], direction.loc[m] = "bear_midpoint_fail", "bullish"

    rows = []
    for i in np.flatnonzero(category.notna().to_numpy()):
        rows.append({
            "timeframe": tf, "signal_time": x.signal_time.iloc[i],
            "category": category.iloc[i], "direction": direction.iloc[i],
            "rsi14": x.rsi14.iloc[i], "atr_pct": x.atr_pct.iloc[i],
            "above_polaris": x.above_polaris.iloc[i],
            "polaris_long_bull": bool(x.polaris_long_bull.iloc[i]),
            "polaris_long_bear": bool(x.polaris_long_bear.iloc[i]),
        })
    raw = pd.DataFrame(rows)
    if raw.empty:
        return raw, pd.DataFrame()
    raw["split"] = raw.signal_time.map(split_name)
    summary = []
    for (category_name, direction_name), base in raw.groupby(["category", "direction"]):
        base_idx = x.signal_time.isin(base.signal_time)
        positions_all = np.flatnonzero(base_idx.to_numpy())
        for split in SPLITS:
            start, end = SPLITS[split]
            positions = positions_all[
                ((x.signal_time.iloc[positions_all] >= start) & (x.signal_time.iloc[positions_all] < end)).to_numpy()
            ]
            metric = forward_event_metric(x, positions, direction_name, h)
            summary.append({
                "timeframe": tf, "category": category_name, "direction": direction_name,
                "split": split, "horizon_bars": h, **metric,
            })
    return raw, pd.DataFrame(summary)


def distance_consistency(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if summary.empty:
        return pd.DataFrame()
    for key, z in summary.groupby(["timeframe", "short_ma", "long_ma", "direction", "gap_bin"]):
        piv = z.set_index("split")
        if not all(s in piv.index for s in SPLITS):
            continue
        rates = [piv.loc[s, "target_rate"] for s in SPLITS]
        ns = [piv.loc[s, "decided"] for s in SPLITS]
        rows.append({
            "timeframe": key[0], "short_ma": key[1], "long_ma": key[2],
            "direction": key[3], "gap_bin": key[4],
            "train_n": ns[0], "validation_n": ns[1], "test_n": ns[2],
            "train_rate": rates[0], "validation_rate": rates[1], "test_rate": rates[2],
            "min_rate": np.nanmin(rates) if np.isfinite(rates).any() else np.nan,
        })
    out = pd.DataFrame(rows)
    return out.sort_values(["min_rate", "test_n"], ascending=False) if not out.empty else out


def touch_decay_table(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[(summary.context_name == "all") & (summary.split == "test")].copy()
    rows = []
    for (tf, ma, mode), z in base.groupby(["timeframe", "ma", "mode"]):
        p = z.set_index("ordinal")
        if not all(o in p.index for o in [1, 2, 3]):
            continue
        rows.append({
            "timeframe": tf, "ma": ma, "mode": mode,
            "n1": p.loc[1, "decided"], "rate1": p.loc[1, "defense_rate"], "mfe1": p.loc[1, "median_mfe_atr"],
            "n2": p.loc[2, "decided"], "rate2": p.loc[2, "defense_rate"], "mfe2": p.loc[2, "median_mfe_atr"],
            "n3": p.loc[3, "decided"], "rate3": p.loc[3, "defense_rate"], "mfe3": p.loc[3, "median_mfe_atr"],
            "rate_change_1_to_3": p.loc[3, "defense_rate"] - p.loc[1, "defense_rate"],
            "mfe_change_1_to_3": p.loc[3, "median_mfe_atr"] - p.loc[1, "median_mfe_atr"],
        })
    out = pd.DataFrame(rows)
    return out.sort_values("rate_change_1_to_3") if not out.empty else out


def curvature_audit(summary: pd.DataFrame) -> pd.DataFrame:
    z = summary[(summary.split == "test") & (summary.ordinal == 1)].copy()
    rows = []
    for (tf, ma, mode, context_name), g in z[z.context_name.isin(["accel_state", "curve_state"])].groupby(["timeframe", "ma", "mode", "context_name"]):
        p = g.set_index("context_value")
        if "with_trend" not in p.index or "flattening" not in p.index:
            continue
        rows.append({
            "timeframe": tf, "ma": ma, "mode": mode, "measure": context_name,
            "with_n": p.loc["with_trend", "decided"], "with_rate": p.loc["with_trend", "defense_rate"],
            "flat_n": p.loc["flattening", "decided"], "flat_rate": p.loc["flattening", "defense_rate"],
            "flattening_minus_with": p.loc["flattening", "defense_rate"] - p.loc["with_trend", "defense_rate"],
        })
    out = pd.DataFrame(rows)
    return out.sort_values("flattening_minus_with") if not out.empty else out
