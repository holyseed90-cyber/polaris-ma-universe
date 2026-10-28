    x["next_ma_gap_short"] = below_dist.min(axis=1)

    # A compact directional bias used only as a context feature.
    x["bull_bias_score"] = (
        ((x.above_count >= 5) & x.ma8_available).astype(int)
        + ((x.rising_count8 >= 5) & x.ma8_available).astype(int)
        + x.structure_state.eq("bull").astype(int)
        + (x.long_bull_stack & x.long4_available).astype(int)
    )
    x["bear_bias_score"] = (
        ((x.above_count <= 3) & x.ma8_available).astype(int)
        + ((x.rising_count8 <= 3) & x.ma8_available).astype(int)
        + x.structure_state.eq("bear").astype(int)
        + (x.long_bear_stack & x.long4_available).astype(int)
    )
    return x


def base_masks(x: pd.DataFrame, tf: str) -> dict[str, tuple[pd.Series, str]]:
    base = p3.build_rules(x, tf)
    keep = {
        "low_sweep_rsi30_40", "high_sweep_rsi60_70",
        "spring_confirm", "upthrust_confirm",
        "bull_3x_upper_half_hold", "bear_3x_lower_half_hold",
        "bull_3x_break_high", "bear_3x_break_low",
    }
    out = {name: value for name, value in base.items() if name in keep}
    out.update({
        "bull_sr_flip_retest": (x.bull_sr_flip_retest, "long"),
        "bear_sr_flip_retest": (x.bear_sr_flip_retest, "short"),
        "bull_choch_retest": (x.bull_structure_retest & (x.bull_choch.shift(1).rolling(5, min_periods=1).max().fillna(0).astype(bool)), "long"),
        "bear_choch_retest": (x.bear_structure_retest & (x.bear_choch.shift(1).rolling(5, min_periods=1).max().fillna(0).astype(bool)), "short"),
        "bull_fvg_rejection": (x.bull_fvg_rejection, "long"),
        "bear_fvg_rejection": (x.bear_fvg_rejection, "short"),
        "bull_ma_rejection": (x.bull_ma_rejection, "long"),
        "bear_ma_rejection": (x.bear_ma_rejection, "short"),
        "bull_ob_retest": (x.bull_ob_retest, "long"),
        "bear_ob_retest": (x.bear_ob_retest, "short"),
        "bull_compression_expansion": (x.bull_compression_expansion, "long"),
        "bear_compression_expansion": (x.bear_compression_expansion, "short"),
        "bull_three_tap_break": (x.bull_three_tap_break, "long"),
        "bear_three_tap_break": (x.bear_three_tap_break, "short"),
    })
    return {k: (v[0].fillna(False).astype(bool), v[1]) for k, v in out.items()}


def completed_context(base: pd.DataFrame, higher: pd.DataFrame, prefix: str, columns: list[str]) -> pd.DataFrame:
    # Resetting an unnamed DatetimeIndex can produce either ``index`` or the
    # original source label depending on pandas/resampling provenance.  Rename
    # the first reset column explicitly so repeated context merges remain stable.
    left = base.reset_index()
    left = left.rename(columns={left.columns[0]: "bar_open"}).sort_values("signal_time")
    right = higher.reset_index()
    right = right.rename(columns={right.columns[0]: "htf_bar_open"}).sort_values("signal_time")
    right = right[["signal_time"] + columns].rename(columns={"signal_time": "available_time", **{c: f"{prefix}_{c}" for c in columns}})
    merged = pd.merge_asof(left, right.sort_values("available_time"), left_on="signal_time", right_on="available_time", direction="backward")
    if "bar_open" not in merged.columns:
        raise RuntimeError(f"completed_context lost bar_open; columns={merged.columns.tolist()[:12]}")
    merged = merged.drop(columns=["available_time"]).set_index("bar_open")
    return merged


def build_frames(venues: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.DataFrame]]:
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    for venue, hourly in venues.items():
        tf_frames: dict[str, pd.DataFrame] = {}
        for tf, info in {**TF_INFO, "12h": CONTEXT_TFS["12h"]}.items():
            raw = p3.resample_ohlcv(hourly, info["rule"])
            tf_frames[tf] = enrich_precision(raw, info["hours"], info["pivot_right"])
        # Attach completed 12h and daily context to 4h.
        context_cols = ["bull_bias_score", "bear_bias_score", "structure_state", "above_count", "rising_count8", "long_bull_stack", "long_bear_stack", "rsi14", "atr_relative"]
        four = completed_context(tf_frames["4h"], tf_frames["12h"], "h12", context_cols)
        four = completed_context(four, tf_frames["1d"], "d1", context_cols)
        tf_frames["4h"] = four
        frames[venue] = tf_frames
    return frames


def side_context_flags(row: pd.Series, side: str, tf: str) -> dict[str, bool]:
    long_side = side == "long"
    prefix = "bull" if long_side else "bear"
    next_gap = row.get("next_ma_gap_long" if long_side else "next_ma_gap_short", np.nan)
    rsi = row.get("rsi14", np.nan)
    ma8_available = bool(row.get("ma8_available", False))
    long4_available = bool(row.get("long4_available", False))
    flags = {
        "f_self_structure": row.get("structure_state") == ("bull" if long_side else "bear"),
        "f_structure_break": bool(row.get(f"{prefix}_structure_break", False) or row.get(f"{prefix}_choch", False)),
