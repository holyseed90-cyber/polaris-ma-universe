        "f_sr_flip": bool(row.get(f"{prefix}_sr_flip_retest", False)),
        "f_fvg_hold": bool(row.get(f"{prefix}_fvg_rejection", False)),
        "f_ma_rejection": bool(row.get(f"{prefix}_ma_rejection", False)),
        "f_ob_retest": bool(row.get(f"{prefix}_ob_retest", False)),
        "f_compression_expansion": bool(row.get(f"{prefix}_compression_expansion", False)),
        "f_three_tap": bool(row.get(f"{prefix}_three_tap_break", False)),
        "f_full_ma_history": ma8_available and long4_available,
        "f_above_strong": bool(ma8_available and (row.get("above_count", 0) >= 6 if long_side else row.get("above_count", 8) <= 2)),
        "f_slope_strong": bool(ma8_available and (row.get("rising_count8", 0) >= 6 if long_side else row.get("rising_count8", 8) <= 2)),
        "f_long_stack": bool(long4_available and (row.get("long_bull_stack", False) if long_side else row.get("long_bear_stack", False))),
        "f_long_ma_compressed": bool(long4_available and row.get("long_ma_compressed", False)),
        "f_next_gap_lt1": bool(np.isfinite(next_gap) and next_gap < 1.0),
        "f_next_gap_lt2": bool(np.isfinite(next_gap) and next_gap < 2.0),
        "f_rsi_reversal_zone": bool(30 <= rsi < 55 if long_side else 45 < rsi <= 70),
        "f_atr_normal": bool(0.75 <= row.get("atr_relative", np.nan) <= 1.35),
        "f_atr_expanding": bool(row.get("atr_relative", 0) > 1.10),
        "f_volume_expanding": bool(row.get("volume_relative", 0) >= 1.20),
        "f_body_confirm": bool(row.get("close_location", 0) >= 0.70 if long_side else row.get("close_location", 1) <= 0.30),
    }
    if tf == "4h":
        flags.update({
            "f_h12_align": bool(row.get("h12_bull_bias_score", 0) >= 2 if long_side else row.get("h12_bear_bias_score", 0) >= 2),
            "f_d1_align": bool(row.get("d1_bull_bias_score", 0) >= 2 if long_side else row.get("d1_bear_bias_score", 0) >= 2),
            "f_d1_structure": row.get("d1_structure_state") == ("bull" if long_side else "bear"),
        })
    else:
        flags.update({"f_h12_align": False, "f_d1_align": True, "f_d1_structure": flags["f_self_structure"]})
    return flags


def kst_zone(ts: pd.Timestamp) -> str:
    return p3.kill_zone_kst(ts)


def build_event_table(frames: dict[str, dict[str, pd.DataFrame]]) -> tuple[pd.DataFrame, dict[str, dict[str, dict[str, tuple[pd.Series, str]]]]]:
    masks: dict[str, dict[str, dict[str, tuple[pd.Series, str]]]] = {}
    for venue, tf_frames in frames.items():
        masks[venue] = {tf: base_masks(tf_frames[tf], tf) for tf in TF_INFO}

    rows: list[dict] = []
    primary_frames = frames[PRIMARY]
    for tf in TF_INFO:
        x = primary_frames[tf]
        primary_masks = masks[PRIMARY][tf]
        spot_x = frames[SPOT][tf]
        # Signal-time indexed lookup tables for all venues.
        venue_signal_frames = {
            venue: frame[tf].reset_index().set_index("signal_time")
            for venue, frame in frames.items()
        }
        venue_mask_frames: dict[str, pd.DataFrame] = {}
        for venue in frames:
            mdf = pd.DataFrame(index=frames[venue][tf].signal_time)
            for name, (mask, side) in masks[venue][tf].items():
                mdf[name] = mask.to_numpy(bool)
            venue_mask_frames[venue] = mdf

        for side in ["long", "short"]:
            names = [name for name, (_, s) in primary_masks.items() if s == side]
            if not names:
                continue
            mask_matrix = pd.concat([primary_masks[name][0].rename(name) for name in names], axis=1)
            any_mask = mask_matrix.any(axis=1)
            for i in np.flatnonzero(any_mask.to_numpy()):
                signal_time = pd.Timestamp(x.signal_time.iloc[i])
                active = [name for name in names if bool(mask_matrix[name].iloc[i])]
                row = x.iloc[i]
                event = {
                    "venue": PRIMARY,
                    "timeframe": tf,
                    "side": side,
                    "signal_time": signal_time,
                    "bar_index": int(i),
                    "entry_time": x.index[i + 1] if i + 1 < len(x) else pd.NaT,
                    "active_patterns": ",".join(sorted(active)),
                    "base_count": len(active),
                    "rsi14": float(row.rsi14) if np.isfinite(row.rsi14) else np.nan,
                    "atr_pct": float(row.atr_pct) if np.isfinite(row.atr_pct) else np.nan,
                    "next_ma_gap": float(row.get("next_ma_gap_long" if side == "long" else "next_ma_gap_short", np.nan)),
                    "kill_zone": kst_zone(signal_time),
                    "year": signal_time.year,
                    "month": signal_time.to_period("M").strftime("%Y-%m"),
                }
                for name in sorted({n for m in masks.values() for d in m.values() for n in d}):
                    event[f"b_{name}"] = name in active
                event.update(side_context_flags(row, side, tf))

                # Exact causal confirmation from spot and independent venues at the same close.
