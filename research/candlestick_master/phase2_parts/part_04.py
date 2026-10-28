                    "timeframe": tf, "token_type": c.token_type, "length": int(c.length),
                    "sequence": c.sequence, "direction": c.direction, "split": split,
                    "horizon_bars": h, "atr_multiple": mult, **r,
                })
    return pd.DataFrame(rows)


def context_refinement(tf: str, df: pd.DataFrame, candidates: pd.DataFrame, seq_map: dict[str, pd.Series], max_candidates: int = 50) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    h = TF_RULES[tf]["rank_h"]
    contexts = ["trend_regime", "long_state", "rsi_bin", "atr_state", "ma_location"]
    rows = []
    for _, c in candidates.head(max_candidates).iterrows():
        seq = seq_map[f"{c.token_type}_{int(c.length)}"]
        for context in contexts:
            values = df.loc[seq.eq(c.sequence).fillna(False), context].dropna().astype(str).value_counts()
            for value, _ in values.items():
                base_pos = np.flatnonzero((seq.eq(c.sequence).fillna(False) & (df[context].astype(str) == value)).to_numpy())
                rec = {
                    "timeframe": tf, "token_type": c.token_type, "length": int(c.length),
                    "sequence": c.sequence, "direction": c.direction, "context_name": context,
                    "context_value": value, "horizon_bars": h,
                }
                for split, (start, end) in SPLITS.items():
                    mask = ((df.signal_time.iloc[base_pos] >= start) & (df.signal_time.iloc[base_pos] < end)).to_numpy()
                    m = metric_row(df, base_pos[mask], h, c.direction)
                    for k, v in m.items():
                        rec[f"{split}_{k}"] = v
                if int(rec.get("test_n", 0) or 0) >= max(5, TF_RULES[tf]["min_test"] // 2):
                    rows.append(rec)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["min_split_win"] = out[["train_win_rate", "validation_win_rate", "test_win_rate"]].min(axis=1)
        out["min_split_return"] = out[["train_median_signed_ret", "validation_median_signed_ret", "test_median_signed_ret"]].min(axis=1)
        out = out.sort_values(["min_split_win", "min_split_return", "test_n"], ascending=False)
    return out


def add_completed_htf_context(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = frames["1h"].copy().reset_index().rename(columns={"timestamp": "bar_open"})
    if "bar_open" not in base.columns:
        base = base.rename(columns={base.columns[0]: "bar_open"})
    base["signal_time"] = base["bar_open"] + pd.Timedelta(hours=1)
    cols = ["trend_regime", "long_state", "rsi_bin", "atr_state", "ma_location"]
    for tf in ["4h", "12h", "1d"]:
        h = TF_RULES[tf]["period_hours"]
        right = frames[tf][cols].copy().reset_index()
        right = right.rename(columns={right.columns[0]: "bar_open"})
        right["available_time"] = right["bar_open"] + pd.to_timedelta(h, unit="h")
        right = right[["available_time"] + cols].rename(columns={c: f"{tf}_{c}" for c in cols})
        base = pd.merge_asof(base.sort_values("signal_time"), right.sort_values("available_time"), left_on="signal_time", right_on="available_time", direction="backward")
        base = base.drop(columns=["available_time"])
    return base.set_index("bar_open")


def multi_tf_refinement(df_1h: pd.DataFrame, mtf: pd.DataFrame, candidates: pd.DataFrame, seq_map: dict[str, pd.Series], max_candidates: int = 40) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    h = TF_RULES["1h"]["rank_h"]
    rows = []
    htf_cols = [c for c in mtf.columns if c.startswith(("4h_", "12h_", "1d_"))]
    for _, c in candidates.head(max_candidates).iterrows():
        seq = seq_map[f"{c.token_type}_{int(c.length)}"]
        for col in htf_cols:
            for value in mtf.loc[seq.eq(c.sequence).fillna(False), col].dropna().astype(str).value_counts().index:
                pos = np.flatnonzero((seq.eq(c.sequence).fillna(False) & (mtf[col].astype(str) == value)).to_numpy())
                rec = {
                    "timeframe": "1h", "token_type": c.token_type, "length": int(c.length),
                    "sequence": c.sequence, "direction": c.direction, "htf_context": col,
                    "htf_value": value, "horizon_bars": h,
                }
                for split, (start, end) in SPLITS.items():
                    mask = ((df_1h.signal_time.iloc[pos] >= start) & (df_1h.signal_time.iloc[pos] < end)).to_numpy()
                    m = metric_row(df_1h, pos[mask], h, c.direction)
                    for k, v in m.items():
                        rec[f"{split}_{k}"] = v
                if int(rec.get("test_n", 0) or 0) >= 7:
                    rows.append(rec)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["min_split_win"] = out[["train_win_rate", "validation_win_rate", "test_win_rate"]].min(axis=1)
        out["min_split_return"] = out[["train_median_signed_ret", "validation_median_signed_ret", "test_median_signed_ret"]].min(axis=1)
        out = out.sort_values(["min_split_win", "min_split_return", "test_n"], ascending=False)
    return out


def report(frames: dict[str, pd.DataFrame], candidates: pd.DataFrame, passage: pd.DataFrame, contexts: pd.DataFrame, mtf: pd.DataFrame) -> None:
    lines = [
        "# BTC Candlestick Master Research — Phase 2",
        "",
        "## Purpose",
        "",
        "This phase tests **2–5 candle sequences**, removes overlapping events, evaluates target-before-stop ordering in ATR units, and verifies whether location and completed higher-timeframe context improve out-of-sample performance.",
        "",
        "## Guardrails",
        "",
        "- Direction is chosen from 2018–2022 training data only.",
        "- Validation (2023–2024) and untouched test (2025–present) must retain the same directional edge.",
        "- Events closer than the ranking horizon are de-duplicated.",
