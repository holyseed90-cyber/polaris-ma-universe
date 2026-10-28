x=False, floatfmt=".4f") if not families.empty else "No family summary.",
        "",
        "## Best non-diagnostic indicator-augmented rules",
        "",
        best[["timeframe", "side", "config_id", "base_pattern", "indicator_rule", "n", "target_rate", "wilson_low", "target_rate_lift", "mean30", "mean50", "pf50", "active_years", "promotion_pass"]].to_markdown(index=False, floatfmt=".4f") if not best.empty else "None.",
        "",
        "## Strictly promoted rules",
        "",
        promoted.to_markdown(index=False, floatfmt=".4f") if not promoted.empty else "None.",
        "",
        "## Diagnostic 90% rows",
        "",
        diag90[["timeframe", "side", "config_id", "base_pattern", "indicator_rule", "n", "target_rate", "wilson_low", "mean30", "mean50", "pf50", "active_years"]].head(30).to_markdown(index=False, floatfmt=".4f") if not diag90.empty else "None.",
        "",
        "## Strong indicator redundancy pairs",
        "",
        redundancy.head(30).to_markdown(index=False, floatfmt=".4f") if not redundancy.empty else "None above |phi| 0.55.",
        "",
        "## Pair-rule ablation",
        "",
        ablation.head(30).to_markdown(index=False, floatfmt=".4f") if not ablation.empty else "No comparable pair/single rows.",
        "",
        "## Interpretation",
        "",
        "An indicator is retained only when it adds next-year lift after 50-bps costs and remains useful across years.  A familiar chart appearance or a high in-sample win rate is not enough.",
        "",
        "## Progress",
        "",
        f"- Historical research completed: {metadata['progress_completed_pct']}%",
        f"- Remaining frozen forward audit: {metadata['progress_remaining_pct']}%",
    ]
    (OUT / "phase5c_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    venues, status = p5.p3.load_venues()
    frames = p5.build_frames(venues)
    events, _ = p5.build_event_table(frames)
    events = add_indicator_features(events, frames)
    outcomes = p5.build_outcomes(events, frames[PRIMARY])
    data = events.merge(outcomes, on=["event_id", "timeframe", "side", "signal_time"], how="inner")

    selected, audit = evaluate_walkforward(data, diagnostic=False)
    selected_diag, audit_diag = evaluate_walkforward(data, diagnostic=True)
    all_selected = pd.concat([selected, selected_diag], ignore_index=True) if not selected.empty or not selected_diag.empty else pd.DataFrame()
    all_audit = pd.concat([audit, audit_diag], ignore_index=True) if not audit.empty or not audit_diag.empty else pd.DataFrame()
    rules = aggregate_rules(all_selected)
    families = family_summary(rules)
    redundancy = indicator_redundancy(events)
    ablation = ablation_table(rules)

    events.to_csv(OUT / "indicator_event_features.csv", index=False)
    all_audit.to_csv(OUT / "indicator_rule_audit.csv", index=False)
    all_selected.to_csv(OUT / "indicator_selected_test_events.csv", index=False)
    rules.to_csv(OUT / "indicator_rule_summary.csv", index=False)
    families.to_csv(OUT / "indicator_family_summary.csv", index=False)
    redundancy.to_csv(OUT / "indicator_redundancy.csv", index=False)
    ablation.to_csv(OUT / "indicator_ablation.csv", index=False)
    pd.DataFrame(status).to_csv(OUT / "data_status.csv", index=False)

    metadata = {
        "phase": "5C",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "primary_venue": PRIMARY,
        "event_rows": int(len(events)),
        "outcome_rows": int(len(outcomes)),
        "audit_rows": int(len(all_audit)),
        "selected_test_rows": int(len(all_selected)),
        "rule_rows": int(len(rules)),
        "promoted_rules": int(rules.promotion_pass.sum()) if not rules.empty else 0,
        "indicator_families": list(FAMILY_MAP),
        "progress_completed_pct": 97,
        "progress_remaining_pct": 3,
    }
    (OUT / "phase5c_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(metadata, rules, families, redundancy, ablation)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
