        "- If target and stop are both crossed within one OHLC bar, the event is marked ambiguous rather than guessed.",
        "- Higher-timeframe context becomes available only after its candle has closed.",
        "",
        "## Data",
        "",
    ]
    for tf, df in frames.items():
        lines.append(f"- {tf}: {len(df):,} bars, {df.index.min().isoformat()} → {df.index.max().isoformat()}")
    lines += ["", "## Consistent sequence candidates", ""]
    if candidates.empty:
        lines.append("No sequence passed all train/validation/test gates.")
    else:
        display_cols = ["timeframe", "token_type", "length", "direction", "validation_n", "test_n", "train_win_rate", "validation_win_rate", "test_win_rate", "test_median_signed_ret", "selection_score", "test_survives", "sequence"]
        lines.append(candidates.head(30)[display_cols].to_markdown(index=False, floatfmt=".3f"))
    lines += ["", "## First-passage summary", ""]
    if passage.empty:
        lines.append("No first-passage rows generated.")
    else:
        best = passage[(passage.split == "test") & (passage.atr_multiple == 1.0) & (passage.target_first + passage.stop_first >= 8)].copy()
        best = best.sort_values(["decided_win_rate", "target_first"], ascending=False).head(25)
        cols = ["timeframe", "length", "direction", "events", "target_first", "stop_first", "ambiguous", "no_hit", "decided_win_rate", "wilson_low", "wilson_high", "sequence"]
        lines.append(best[cols].to_markdown(index=False, floatfmt=".3f") if not best.empty else "No test candidate had at least eight decided 1-ATR events.")
    lines += ["", "## Best same-timeframe context refinements", ""]
    if contexts.empty:
        lines.append("No context refinements generated.")
    else:
        good = contexts[(contexts.train_win_rate >= .52) & (contexts.validation_win_rate >= .52) & (contexts.test_win_rate >= .52) & (contexts.min_split_return > 0)].head(25)
        cols = ["timeframe", "length", "direction", "context_name", "context_value", "test_n", "train_win_rate", "validation_win_rate", "test_win_rate", "test_median_signed_ret", "sequence"]
        lines.append(good[cols].to_markdown(index=False, floatfmt=".3f") if not good.empty else "No context row passed the conservative consistency filter.")
    lines += ["", "## Best completed higher-timeframe refinements for 1h sequences", ""]
    if mtf.empty:
        lines.append("No multi-timeframe refinements generated.")
    else:
        good = mtf[(mtf.train_win_rate >= .52) & (mtf.validation_win_rate >= .52) & (mtf.test_win_rate >= .52) & (mtf.min_split_return > 0)].head(25)
        cols = ["length", "direction", "htf_context", "htf_value", "test_n", "train_win_rate", "validation_win_rate", "test_win_rate", "test_median_signed_ret", "sequence"]
        lines.append(good[cols].to_markdown(index=False, floatfmt=".3f") if not good.empty else "No MTF row passed the conservative consistency filter.")
    lines += [
        "", "## Interpretation", "",
        "These are research candidates, not trading signals. Phase 3 must add wave structure, support/resistance flips, liquidity sweeps, FVG/order-block definitions, session behavior, and walk-forward transaction-cost testing before any TradingView signal is promoted.",
    ]
    (OUT / "phase2_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    path = download_source()
    hourly = normalize_source(path)
    frames_raw = {"1h": hourly}
    for tf, cfg in TF_RULES.items():
        if tf != "1h":
            frames_raw[tf] = resample_ohlcv(hourly, cfg["rule"])
    frames: dict[str, pd.DataFrame] = {}
    all_candidates = []
    all_passage = []
    all_contexts = []
    seq_maps: dict[str, dict[str, pd.Series]] = {}
    for tf, raw in frames_raw.items():
        frame = enrich(raw, TF_RULES[tf]["period_hours"])
        frame = add_forward_metrics(frame, TF_RULES[tf]["horizons"])
        frames[tf] = frame
        coarse, coarse_map = mine_sequences(tf, frame, "shape_token", [2, 3, 4, 5])
        fine, fine_map = mine_sequences(tf, frame, "flow_token", [2, 3, 4])
        cand = pd.concat([coarse, fine], ignore_index=True) if not coarse.empty or not fine.empty else pd.DataFrame()
        if not cand.empty:
            cand = cand.sort_values(["selection_score", "validation_n"], ascending=False).reset_index(drop=True)
            all_candidates.append(cand)
        seq_map = {**coarse_map, **fine_map}
        seq_maps[tf] = seq_map
        passage = evaluate_first_passage(tf, frame, cand, seq_map)
        contexts = context_refinement(tf, frame, cand, seq_map)
        if not passage.empty:
            all_passage.append(passage)
        if not contexts.empty:
            all_contexts.append(contexts)

    candidates = pd.concat(all_candidates, ignore_index=True).sort_values(["selection_score", "validation_n"], ascending=False) if all_candidates else pd.DataFrame()
    passage = pd.concat(all_passage, ignore_index=True) if all_passage else pd.DataFrame()
    contexts = pd.concat(all_contexts, ignore_index=True) if all_contexts else pd.DataFrame()
    mtf_frame = add_completed_htf_context(frames)
    # Re-align sequence series to the MTF frame's hourly index.
    mtf = multi_tf_refinement(frames["1h"], mtf_frame, candidates[candidates.timeframe == "1h"] if not candidates.empty else pd.DataFrame(), seq_maps.get("1h", {}))

    candidates.to_csv(OUT / "sequence_candidates.csv", index=False)
    passage.to_csv(OUT / "sequence_first_passage.csv", index=False)
    contexts.to_csv(OUT / "sequence_context_refinement.csv", index=False)
    mtf.to_csv(OUT / "sequence_mtf_refinement.csv", index=False)
    report(frames, candidates, passage, contexts, mtf)
    metadata = {
        "source_url": SOURCE_URL,
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "phase": 2,
        "bars": {tf: int(len(df)) for tf, df in frames.items()},
        "candidate_rows": int(len(candidates)),
        "first_passage_rows": int(len(passage)),
        "context_rows": int(len(contexts)),
        "mtf_rows": int(len(mtf)),
        "sequence_lengths": {"shape_token": [2, 3, 4, 5], "flow_token": [2, 3, 4]},
        "splits": {k: [str(v[0]), str(v[1])] for k, v in SPLITS.items()},
    }
    (OUT / "phase2_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
