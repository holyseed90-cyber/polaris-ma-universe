def split_name(ts: pd.Timestamp) -> str | None:
    for name, (start, end) in SPLITS.items():
        if start <= ts < end:
            return name
    return None


def dedupe_positions(pos: np.ndarray, horizon: int) -> np.ndarray:
    if len(pos) == 0:
        return pos
    kept = [int(pos[0])]
    for p in pos[1:]:
        if int(p) - kept[-1] >= horizon:
            kept.append(int(p))
    return np.asarray(kept, dtype=int)


def wilson_ci(success: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (np.nan, np.nan)
    p = success / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return centre - half, centre + half


def metric_row(df: pd.DataFrame, positions: np.ndarray, horizon: int, direction: str) -> dict:
    pos = dedupe_positions(np.sort(positions), horizon)
    if len(pos) == 0:
        return {"n": 0}
    vals = df.iloc[pos][f"ret_{horizon}"].dropna().astype(float)
    if vals.empty:
        return {"n": 0}
    signed = vals if direction == "bullish" else -vals
    wins = int((signed > 0).sum())
    ci = wilson_ci(wins, len(vals))
    return {
        "n": int(len(vals)),
        "median_signed_ret": float(signed.median()),
        "mean_signed_ret": float(signed.mean()),
        "win_rate": float((signed > 0).mean()),
        "win_ci_low": float(ci[0]),
        "win_ci_high": float(ci[1]),
        "median_mfe_atr": float((df.iloc[pos][f"mfe_{horizon}_atr"] if direction == "bullish" else -df.iloc[pos][f"mae_{horizon}_atr"]).median()),
        "median_mae_atr": float((df.iloc[pos][f"mae_{horizon}_atr"] if direction == "bullish" else -df.iloc[pos][f"mfe_{horizon}_atr"]).median()),
    }


def make_sequences(tokens: pd.Series, length: int) -> pd.Series:
    pieces = [tokens.shift(k) for k in range(length - 1, -1, -1)]
    out = pieces[0].astype("string")
    for p in pieces[1:]:
        out = out + ">" + p.astype("string")
    return out.where(pd.concat(pieces, axis=1).notna().all(axis=1))


def mine_sequences(tf: str, df: pd.DataFrame, token_col: str, lengths: Iterable[int]) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    cfg = TF_RULES[tf]
    h = cfg["rank_h"]
    sequence_series: dict[str, pd.Series] = {}
    rows: list[dict] = []
    for length in lengths:
        seq = make_sequences(df[token_col], length)
        key = f"{token_col}_{length}"
        sequence_series[key] = seq
        train_mask = (df.signal_time >= SPLITS["train"][0]) & (df.signal_time < SPLITS["train"][1]) & seq.notna() & df[f"ret_{h}"].notna()
        counts = seq[train_mask].value_counts()
        eligible = counts[counts >= cfg["min_train"]].index
        for s in eligible:
            base_pos = np.flatnonzero(seq.eq(s).fillna(False).to_numpy())
            # Direction is selected on de-duplicated training data only.
            tr_pos = base_pos[(df.signal_time.iloc[base_pos] >= SPLITS["train"][0]).to_numpy() & (df.signal_time.iloc[base_pos] < SPLITS["train"][1]).to_numpy()]
            tr_pos = dedupe_positions(tr_pos, h)
            if len(tr_pos) < cfg["min_train"] // 2:
                continue
            tr_ret = df.iloc[tr_pos][f"ret_{h}"].dropna()
            if tr_ret.empty:
                continue
            direction = "bullish" if tr_ret.median() > 0 else "bearish"
            train_metric = metric_row(df, tr_pos, h, direction)
            if train_metric.get("n", 0) == 0:
                continue
            # Require an actual training edge before touching validation/test.
            if train_metric["win_rate"] < 0.56 or train_metric["median_signed_ret"] <= 0:
                continue
            record = {
                "timeframe": tf,
                "token_type": token_col,
                "length": length,
                "sequence": str(s),
                "direction": direction,
                "horizon_bars": h,
            }
            for split, (start, end) in SPLITS.items():
                mask = ((df.signal_time.iloc[base_pos] >= start) & (df.signal_time.iloc[base_pos] < end)).to_numpy()
                m = metric_row(df, base_pos[mask], h, direction)
                for k, v in m.items():
                    record[f"{split}_{k}"] = v
            # Candidate selection stops at validation.  The test period remains untouched
