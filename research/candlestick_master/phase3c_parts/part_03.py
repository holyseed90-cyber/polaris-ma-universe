

def three_split_table(summary: pd.DataFrame, keys: list[str], value_cols: list[str]) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    rows = []
    for key, z in summary.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        p = z.set_index("split")
        if not all(s in p.index for s in SPLITS):
            continue
        rec = dict(zip(keys, key))
        for split in SPLITS:
            for col in value_cols:
                rec[f"{split}_{col}"] = p.loc[split, col]
        rows.append(rec)
    return pd.DataFrame(rows)


def make_report(
    frames: dict[str, pd.DataFrame], distance: pd.DataFrame, decay: pd.DataFrame,
    curvature: pd.DataFrame, migration: pd.DataFrame, long_body: pd.DataFrame,
) -> None:
    lines = [
        "# BTC Candlestick Master — Phase 3C",
        "",
        "## Scope",
        "",
        "ATR-distance-conditioned next-MA ladders, first/second/third independent MA-contact defense, linear-regression slope acceleration and curvature, support migration, and 3× average-body follow-through structure.",
        "",
        "## Source discipline",
        "",
        "The Bondweb curriculum and the uploaded technical-analysis atlas are hypothesis sources only. Results below come from BTCUSDT with 2018–2022 training, 2023–2024 validation, and 2025–present untouched test periods.",
        "",
        "## Data",
        "",
    ]
    for tf, x in frames.items():
        lines.append(f"- {tf}: {len(x):,} bars, {x.index.min().isoformat()} → {x.index.max().isoformat()}")

    lines += ["", "## Next-MA target probability by ATR distance", ""]
    if distance.empty:
        lines.append("No distance rows.")
    else:
        good = distance[(distance.train_n >= 20) & (distance.validation_n >= 8) & (distance.test_n >= 8)].copy()
        cols = ["timeframe", "short_ma", "long_ma", "direction", "gap_bin", "train_n", "validation_n", "test_n", "train_rate", "validation_rate", "test_rate", "min_rate"]
        lines.append(good.head(40)[cols].to_markdown(index=False, floatfmt=".3f") if len(good) else "No distance bin had enough samples in all three splits.")

    lines += ["", "## First versus repeated independent MA defense", ""]
    if decay.empty:
        lines.append("No touch-decay rows.")
    else:
        enough = decay[(decay.n1 >= 8) & (decay.n3 >= 8)].copy()
        cols = ["timeframe", "ma", "mode", "n1", "rate1", "mfe1", "n2", "rate2", "mfe2", "n3", "rate3", "mfe3", "rate_change_1_to_3", "mfe_change_1_to_3"]
        lines.append(enough.head(40)[cols].to_markdown(index=False, floatfmt=".3f") if len(enough) else "No row had at least eight decided first- and third-touch events.")

    lines += ["", "## Does MA flattening weaken first-touch defense?", ""]
    if curvature.empty:
        lines.append("No curvature-comparison rows.")
    else:
        enough = curvature[(curvature.with_n >= 8) & (curvature.flat_n >= 8)].copy()
        cols = ["timeframe", "ma", "mode", "measure", "with_n", "with_rate", "flat_n", "flat_rate", "flattening_minus_with"]
        lines.append(enough.head(40)[cols].to_markdown(index=False, floatfmt=".3f") if len(enough) else "No row had enough samples in both curvature states.")

    lines += ["", "## Support migration", ""]
    if migration.empty:
        lines.append("No migration rows.")
    else:
        good = migration[(migration.train_decided >= 15) & (migration.validation_decided >= 6) & (migration.test_decided >= 6)].copy()
        cols = ["timeframe", "migration", "train_decided", "validation_decided", "test_decided", "train_target_rate", "validation_target_rate", "test_target_rate"]
        lines.append(good[cols].to_markdown(index=False, floatfmt=".3f") if len(good) else "No migration state had enough independent events in all splits.")

    lines += ["", "## 3× average-body candle confirmation", ""]
    if long_body.empty:
        lines.append("No long-body rows.")
    else:
        good = long_body[(long_body.train_n >= 15) & (long_body.validation_n >= 6) & (long_body.test_n >= 6)].copy()
        cols = ["timeframe", "category", "direction", "train_n", "validation_n", "test_n", "train_win_rate", "validation_win_rate", "test_win_rate", "test_median_signed_ret"]
        lines.append(good.head(40)[cols].to_markdown(index=False, floatfmt=".3f") if len(good) else "No confirmation category had enough samples in all splits.")

    lines += ["", "## Mechanical claim audit", ""]
    audits = []
    if not distance.empty:
        d = distance[(distance.train_n >= 15) & (distance.validation_n >= 6) & (distance.test_n >= 6)]
        audits.append(("Next-MA probability is strongest when MA gap is small", int(len(d)), float((d[d.gap_bin.isin(["lt1", "1to2"])].test_rate.mean() - d[d.gap_bin.isin(["3to4", "ge4"])].test_rate.mean()) if len(d) else np.nan)))
    if not decay.empty:
        q = decay[(decay.n1 >= 8) & (decay.n3 >= 8)]
        audits.append(("Repeated support/resistance contact weakens defense", int(len(q)), float((q.rate_change_1_to_3 < 0).mean()) if len(q) else np.nan))
    if not curvature.empty:
        q = curvature[(curvature.with_n >= 8) & (curvature.flat_n >= 8)]
        audits.append(("Flattening/against-trend curvature weakens first-touch defense", int(len(q)), float((q.flattening_minus_with < 0).mean()) if len(q) else np.nan))
    if not migration.empty:
        q = migration
        short = q[q.migration == "shorter"].test_target_rate.mean()
        long = q[q.migration == "longer"].test_target_rate.mean()
        audits.append(("Support migrating from longer to shorter MA signals strengthening", int(len(q)), float(short - long) if np.isfinite(short) and np.isfinite(long) else np.nan))
    audit_df = pd.DataFrame(audits, columns=["claim", "evidence_rows", "support_metric"])
    lines.append(audit_df.to_markdown(index=False, floatfmt=".3f") if len(audit_df) else "No claim audit available.")

    lines += [
        "", "## Interpretation", "",
        "- The target ladder must be conditioned on ATR distance; the MA name alone is insufficient.",
        "- Repeated-touch counts are separated into support defense and resistance rejection; they are never treated as universally bullish.",
        "- LR slope acceleration and second-difference curvature are compared separately because visual 'flattening' has multiple mathematical definitions.",
        "- A 3× body candle is not a signal by itself; the next candle's relation to the prior midpoint, high and low is the tested event.",
        "- Phase 3D must add cross-venue replication, current-data extension, costs, session behavior and composite-rule walk-forward testing.",
    ]
    (OUT / "phase3c_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    frames = build_frames()
    ladder_raw_all, ladder_summary_all = [], []
    touch_raw_all, touch_summary_all = [], []
    migration_raw_all, migration_summary_all = [], []
    long_raw_all, long_summary_all = [], []

    for tf, x in frames.items():
        lr, ls = ma_ladder_by_distance(tf, x)
        tr, ts = touch_defense_study(tf, x)
        mr, ms = support_migration_study(tf, x)
        br, bs = long_body_confirmation_study(tf, x)
        if not lr.empty: ladder_raw_all.append(lr)
        if not ls.empty: ladder_summary_all.append(ls)
        if not tr.empty: touch_raw_all.append(tr)
        if not ts.empty: touch_summary_all.append(ts)
        if not mr.empty: migration_raw_all.append(mr)
        if not ms.empty: migration_summary_all.append(ms)
        if not br.empty: long_raw_all.append(br)
        if not bs.empty: long_summary_all.append(bs)

    ladder_raw = pd.concat(ladder_raw_all, ignore_index=True) if ladder_raw_all else pd.DataFrame()
    ladder_summary = pd.concat(ladder_summary_all, ignore_index=True) if ladder_summary_all else pd.DataFrame()
    touch_raw = pd.concat(touch_raw_all, ignore_index=True) if touch_raw_all else pd.DataFrame()
    touch_summary = pd.concat(touch_summary_all, ignore_index=True) if touch_summary_all else pd.DataFrame()
    migration_raw = pd.concat(migration_raw_all, ignore_index=True) if migration_raw_all else pd.DataFrame()
    migration_summary = pd.concat(migration_summary_all, ignore_index=True) if migration_summary_all else pd.DataFrame()
    long_raw = pd.concat(long_raw_all, ignore_index=True) if long_raw_all else pd.DataFrame()
    long_summary = pd.concat(long_summary_all, ignore_index=True) if long_summary_all else pd.DataFrame()

    distance = distance_consistency(ladder_summary)
    decay = touch_decay_table(touch_summary)
    curvature = curvature_audit(touch_summary)
    migration = three_split_table(migration_summary, ["timeframe", "migration"], ["decided", "target_rate"])
    long_body = three_split_table(long_summary, ["timeframe", "category", "direction"], ["n", "win_rate", "median_signed_ret", "median_mfe_atr", "median_mae_atr"])

    ladder_raw.to_csv(OUT / "ladder_raw.csv", index=False)
    ladder_summary.to_csv(OUT / "ladder_by_atr_distance.csv", index=False)
    distance.to_csv(OUT / "ladder_distance_consistency.csv", index=False)
    touch_raw.to_csv(OUT / "touch_defense_raw.csv", index=False)
    touch_summary.to_csv(OUT / "touch_defense_summary.csv", index=False)
    decay.to_csv(OUT / "touch_decay_test.csv", index=False)
    curvature.to_csv(OUT / "curvature_audit_test.csv", index=False)
    migration_raw.to_csv(OUT / "support_migration_raw.csv", index=False)
    migration.to_csv(OUT / "support_migration_three_split.csv", index=False)
    long_raw.to_csv(OUT / "long_body_confirmation_raw.csv", index=False)
    long_body.to_csv(OUT / "long_body_confirmation_three_split.csv", index=False)
    make_report(frames, distance, decay, curvature, migration, long_body)

    metadata = {
        "phase": "3C",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "bars": {tf: int(len(x)) for tf, x in frames.items()},
        "ladder_events": int(len(ladder_raw)),
        "touch_events": int(len(touch_raw)),
        "migration_events": int(len(migration_raw)),
        "long_body_confirmation_events": int(len(long_raw)),
        "progress_completed_pct": 63,
        "progress_remaining_pct": 37,
    }
    (OUT / "phase3c_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
