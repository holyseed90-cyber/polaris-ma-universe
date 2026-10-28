        "",
        "## Strict A+ rules",
        "",
        pass_rows.head(30).to_markdown(index=False, floatfmt=".4f") if not pass_rows.empty else "None.",
        "",
        "## Observed 90% rules that failed the robustness gate",
        "",
        sparse_rows.head(30).to_markdown(index=False, floatfmt=".4f") if not sparse_rows.empty else "None.",
        "",
        "## Interpretation",
        "",
        "A target hit rate near 90% is accepted only when the sample, Wilson lower bound, annual stability, 50-bps expectancy and profit factor all pass. Otherwise the correct live label remains WAIT.",
        "",
        "## Progress",
        "",
        f"- Completed: {metadata['progress_completed_pct']}%",
        f"- Remaining: {metadata['progress_remaining_pct']}%",
        "",
        "The remaining work is a frozen-rule forward paper audit on genuinely future candles. Historical re-mining cannot substitute for that step.",
    ]
    (OUT / "phase5b_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    venues, status = p3.load_venues()
    required = {PRIMARY, SPOT}
    missing = required - set(venues)
    if missing:
        raise RuntimeError(f"Required venues missing: {sorted(missing)}")
    frames = build_frames(venues)
    events, _ = build_event_table(frames)
    outcomes = build_outcomes(events, frames[PRIMARY])
    merged = events.merge(outcomes, on=["event_id", "timeframe", "side", "signal_time"], how="inner")

    selected_parts = []
    audit_parts = []
    for fold in FOLDS:
        for tf, configs in CONFIGS.items():
            for side in ["long", "short"]:
                for cfg in configs:
                    selected, audit = select_rules_for_fold(merged, fold, tf, side, cfg["config_id"])
                    if not selected.empty:
                        selected_parts.append(selected)
                    if not audit.empty:
                        audit_parts.append(audit)
    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame()
    audit = pd.concat(audit_parts, ignore_index=True) if audit_parts else pd.DataFrame()
    portfolio = strict_portfolio(selected)
    frontier = precision_frontier(selected)
    gate = aplus_gate(frontier)
    support_table = support_precision_table(gate)

    events.to_csv(OUT / "perp_event_features.csv", index=False)
    outcomes.to_csv(OUT / "perp_event_outcomes.csv", index=False)
    audit.to_csv(OUT / "rule_mining_audit.csv", index=False)
    selected.to_csv(OUT / "walkforward_selected_test_events.csv", index=False)
    portfolio.to_csv(OUT / "strict_precision_portfolio.csv", index=False)
    frontier.to_csv(OUT / "rule_precision_frontier.csv", index=False)
    gate.to_csv(OUT / "aplus_gate.csv", index=False)
    support_table.to_csv(OUT / "support_precision_frontier.csv", index=False)
    pd.DataFrame(status).to_csv(OUT / "data_status.csv", index=False)

    aplus_count = int(gate.aplus_pass.sum()) if not gate.empty else 0
    metadata = {
        "phase": "5B",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "primary_venue": PRIMARY,
        "confirmation_venues": sorted(set(venues) - {PRIMARY}),
        "event_rows": int(len(events)),
        "outcome_rows": int(len(outcomes)),
        "candidate_audit_rows": int(len(audit)),
        "selected_test_rows": int(len(selected)),
        "strict_portfolio_rows": int(len(portfolio)),
        "aplus_rules": aplus_count,
        "sparse_observed_90_rules": int(gate.sparse_observed_90.sum()) if not gate.empty else 0,
        "progress_completed_pct": 95,
        "progress_remaining_pct": 5,
    }
    (OUT / "phase5b_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(metadata, portfolio, gate, support_table, audit)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
