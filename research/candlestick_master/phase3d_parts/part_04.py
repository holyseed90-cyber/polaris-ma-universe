

def markdown_table(df: pd.DataFrame, cols: list[str], n: int = 30) -> str:
    if df.empty:
        return "No qualifying rows."
    existing = [c for c in cols if c in df.columns]
    return df.head(n)[existing].to_markdown(index=False, floatfmt=".3f")


def create_report(
    status: pd.DataFrame,
    summary: pd.DataFrame,
    stable: pd.DataFrame,
    cross: pd.DataFrame,
    ladders: pd.DataFrame,
    ladder_cross: pd.DataFrame,
    sessions: pd.DataFrame,
    session_cross: pd.DataFrame,
    price_compare: pd.DataFrame,
    signal_compare: pd.DataFrame,
) -> None:
    lines = [
        "# BTC Candlestick Master — Phase 3D",
        "",
        "## Scope",
        "",
        "Cross-venue replication, Binance spot-versus-perpetual comparison, current-data extension, next-bar entry, 1-ATR target/stop, conservative same-bar ambiguity, 0/10/20/30 bps round-trip cost scenarios, KST kill-zone and weekday stability.",
        "",
        "The technical-analysis atlas defines separate Asia, London and New York sessions and kill zones. This phase treats those time windows as hypotheses rather than proof and tests them on each venue independently.",
        "",
        "## Data acquisition",
        "",
        markdown_table(status, ["venue", "status", "bars", "start", "end", "missing_hours", "error"], 10),
        "",
        "## Cross-venue test-period consistency after 20 bps costs",
        "",
        markdown_table(
            cross,
            ["timeframe", "rule", "side", "venues_tested", "venues_positive", "positive_fraction", "weighted_n", "weighted_win_rate", "weighted_mean_net_pct", "worst_venue_mean_net_pct", "best_venue_mean_net_pct", "positive_venues"],
            40,
        ),
        "",
        "A rule is not promoted merely because its weighted result is positive. The worst venue, sample size, all three historical splits, profit factor and drawdown must also be acceptable.",
        "",
        "## Venue-level rules positive in train, validation and untouched test after 20 bps",
        "",
        markdown_table(
            stable[stable.all_splits_positive] if not stable.empty else stable,
            ["venue", "timeframe", "rule", "side", "n_train", "n_validation", "n_test", "mean_net_pct_train", "mean_net_pct_validation", "mean_net_pct_test", "win_rate_test", "profit_factor_test", "max_drawdown_pct_test", "min_split_mean"],
            40,
        ),
        "",
        "## Next-MA ladder replication by venue and ATR gap",
        "",
        markdown_table(
            ladder_cross,
            ["timeframe", "short_ma", "long_ma", "direction", "gap_bin", "venues_tested", "decided", "weighted_target_rate", "minimum_venue_rate", "maximum_venue_rate", "venues_ge_60pct"],
            50,
        ),
        "",
        "The ladder statistic is a path probability, not a trade win rate. It asks whether the next MA was touched before price reclaimed the broken short MA.",
        "",
        "## KST kill-zone results after 20 bps",
        "",
        markdown_table(
            session_cross,
            ["timeframe", "rule", "side", "kill_zone", "venues_tested", "venues_positive", "n", "weighted_win_rate", "weighted_mean_net_pct"],
            40,
        ),
        "",
        "## Binance spot-versus-perpetual candle comparison",
        "",
        markdown_table(price_compare, ["metric", "value"], 20),
        "",
        "## Binance spot-versus-perpetual signal agreement",
        "",
        markdown_table(signal_compare.sort_values("exact_jaccard", ascending=False) if not signal_compare.empty else signal_compare, ["rule", "spot_signals", "perp_signals", "exact_jaccard", "spot_matched_within_1h"], 30),
        "",
        "## Research interpretation",
        "",
        "- A candle rule that works on Binance but fails on Coinbase/Bitstamp is treated as venue-specific, not universal.",
        "- Perpetual-futures wick behavior is not silently substituted for spot behavior.",
        "- Costs are deducted from every trade, including time exits.",
        "- The next-bar open is used for entry; the signal candle close is never used as a fill price.",
        "- If both target and stop occur inside the same OHLC candle, the result is conservatively recorded as a stop.",
        "- Kill-zone superiority must appear across venues, not only in a pooled Binance sample.",
        "",
        "## Next phase",
        "",
        "Phase 4 will build an interpretable composite score from only cross-venue-surviving components, run rolling walk-forward threshold selection, test several target/stop ratios and maximum holding periods, and create a non-repainting Pine prototype. It will remain a research indicator until paper-trading audit results are available.",
        "",
        "## Progress",
        "",
        "- Completed: 72%",
        "- Remaining: 28%",
    ]
    (OUT / "phase3d_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    venues, status_rows = load_venues()
    status = pd.DataFrame(status_rows)
    all_trades: list[pd.DataFrame] = []
    all_ladders: list[pd.DataFrame] = []
    all_frames: dict[str, dict[str, pd.DataFrame]] = {}
    for venue, hourly in venues.items():
        trades, ladders, frames = analyze_venue(venue, hourly)
        all_frames[venue] = frames
        if not trades.empty:
            all_trades.append(trades)
        if not ladders.empty:
            all_ladders.append(ladders)
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    ladders = pd.concat(all_ladders, ignore_index=True) if all_ladders else pd.DataFrame()
    summary = summarize_trades(trades)
    sessions = summarize_sessions(trades)
    ladder_summary = summarize_ladders(ladders)
    stable = three_split_stability(summary)
    cross = cross_venue_consistency(summary)
    ladder_cross = ladder_cross_venue(ladder_summary)
    session_cross = session_cross_venue(sessions)
    price_compare, signal_compare = spot_perp_comparison(all_frames)

    status.to_csv(OUT / "data_status.csv", index=False)
    trades.to_csv(OUT / "trade_ledger.csv", index=False)
    summary.to_csv(OUT / "trade_summary_costs.csv", index=False)
    stable.to_csv(OUT / "three_split_stability.csv", index=False)
    cross.to_csv(OUT / "cross_venue_consistency.csv", index=False)
    sessions.to_csv(OUT / "session_weekday_performance.csv", index=False)
    session_cross.to_csv(OUT / "session_cross_venue.csv", index=False)
    ladders.to_csv(OUT / "ladder_events.csv", index=False)
    ladder_summary.to_csv(OUT / "ladder_summary.csv", index=False)
    ladder_cross.to_csv(OUT / "ladder_cross_venue.csv", index=False)
    price_compare.to_csv(OUT / "binance_spot_perp_price_comparison.csv", index=False)
    signal_compare.to_csv(OUT / "binance_spot_perp_signal_agreement.csv", index=False)
    create_report(status, summary, stable, cross, ladder_summary, ladder_cross, sessions, session_cross, price_compare, signal_compare)

    metadata = {
        "phase": "3D",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "venues_requested": 4,
        "venues_loaded": len(venues),
        "venue_bars": {name: int(len(df)) for name, df in venues.items()},
        "venue_latest": {name: df.index.max().isoformat() for name, df in venues.items()},
        "trade_rows": int(len(trades)),
        "ladder_rows": int(len(ladders)),
        "cross_venue_rows": int(len(cross)),
        "three_split_positive_rows": int(stable.all_splits_positive.sum()) if not stable.empty else 0,
        "progress_completed_pct": 72,
        "progress_remaining_pct": 28,
    }
    (OUT / "phase3d_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
