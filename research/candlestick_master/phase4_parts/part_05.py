        pm = metrics(portfolio)
        lines.append(pd.DataFrame([pm]).to_markdown(index=False, floatfmt=".3f"))
    lines += [
        "",
        "## Interpretation",
        "",
        "A higher score does not mean certainty. It means that several independently defined pieces of evidence—pattern, location, volatility, session, higher timeframe, next-MA distance and cross-venue agreement—were historically more favorable in the training window. The score is retained only when the next validation year supports its use.",
        "",
        "## Progress",
        "",
        f"- Completed: {metadata['progress_completed_pct']}%",
        f"- Remaining: {metadata['progress_remaining_pct']}%",
    ]
    (OUT / "phase4_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    venues, status = p3.load_venues()
    all_frames: dict[str, dict[str, pd.DataFrame]] = {}
    event_parts = []
    for venue, hourly in venues.items():
        frames = resampled_frames(hourly)
        all_frames[venue] = frames
        event_parts.append(build_events_for_venue(venue, frames))
    events = add_consensus(pd.concat(event_parts, ignore_index=True))
    cache = config_grid(events, all_frames)

    scored_parts: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    config_tables: list[pd.DataFrame] = []
    threshold_tables: list[pd.DataFrame] = []
    contribution_tables: list[pd.DataFrame] = []
    for fold in FOLDS:
        for tf in p3.TIMEFRAMES:
            for side in ["long", "short"]:
                scored, result, ctable, ttable, contributions = fold_score(events, cache, tf, side, fold)
                if not scored.empty:
                    scored_parts.append(scored)
                if result:
                    fold_rows.append(result)
                if not ctable.empty:
                    config_tables.append(ctable)
                if not ttable.empty:
                    threshold_tables.append(ttable)
                if not contributions.empty:
                    contribution_tables.append(contributions)

    scored = pd.concat(scored_parts, ignore_index=True) if scored_parts else pd.DataFrame()
    fold_summary = pd.DataFrame(fold_rows)
    configs = pd.concat(config_tables, ignore_index=True) if config_tables else pd.DataFrame()
    thresholds = pd.concat(threshold_tables, ignore_index=True) if threshold_tables else pd.DataFrame()
    contributions = pd.concat(contribution_tables, ignore_index=True) if contribution_tables else pd.DataFrame()
    calibration = calibration_table(scored)
    portfolio = strict_portfolio(scored)
    portfolio_metrics = pd.DataFrame([metrics(portfolio)]) if not portfolio.empty else pd.DataFrame()

    events.to_csv(OUT / "event_feature_table.csv", index=False)
    scored.to_csv(OUT / "walkforward_scored_events.csv", index=False)
    fold_summary.to_csv(OUT / "walkforward_fold_summary.csv", index=False)
    configs.to_csv(OUT / "config_selection_audit.csv", index=False)
    thresholds.to_csv(OUT / "threshold_selection_audit.csv", index=False)
    contributions.to_csv(OUT / "score_contributions.csv", index=False)
    calibration.to_csv(OUT / "score_calibration_bh.csv", index=False)
    portfolio.to_csv(OUT / "strict_no_overlap_portfolio.csv", index=False)
    portfolio_metrics.to_csv(OUT / "strict_no_overlap_metrics.csv", index=False)
    pd.DataFrame(status).to_csv(OUT / "data_status.csv", index=False)

    metadata = {
        "phase": "4",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "venues_loaded": len(venues),
        "event_rows": int(len(events)),
        "configs_cached": int(len(cache)),
        "walkforward_scored_rows": int(len(scored)),
        "selected_rows": int(scored.selected.sum()) if not scored.empty else 0,
        "portfolio_rows": int(len(portfolio)),
        "contribution_rows": int(len(contributions)),
        "folds": [f["fold"] for f in FOLDS],
        "progress_completed_pct": 83,
        "progress_remaining_pct": 17,
    }
    (OUT / "phase4_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    report(metadata, fold_summary, calibration, portfolio, configs, thresholds)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
