           "positive_mean50_share": float((z.mean50 > 0).mean()),
            "median_mean50": float(z.mean50.median()),
            "best_target_rate_n15": float(z.loc[z.n >= 15, "target_rate"].max()) if (z.n >= 15).any() else np.nan,
            "best_wilson_low_n15": float(z.loc[z.n >= 15, "wilson_low"].max()) if (z.n >= 15).any() else np.nan,
        })
    return pd.DataFrame(rows).sort_values(["positive_lift_share", "median_target_lift", "positive_mean50_share"], ascending=False)


def indicator_redundancy(events: pd.DataFrame) -> pd.DataFrame:
    cols = list(FEATURE_TO_FAMILY)
    rows = []
    for tf in ["4h", "1d"]:
        for side in ["long", "short"]:
            z = events[(events.timeframe == tf) & (events.side == side)][cols].astype(float)
            corr = z.corr()
            for i, a in enumerate(cols):
                for b in cols[i + 1:]:
                    val = corr.loc[a, b]
                    if np.isfinite(val) and abs(val) >= 0.55:
                        rows.append({"timeframe": tf, "side": side, "feature_a": a, "family_a": FEATURE_TO_FAMILY[a], "feature_b": b, "family_b": FEATURE_TO_FAMILY[b], "phi_corr": val})
    return pd.DataFrame(rows).sort_values("phi_corr", key=lambda s: s.abs(), ascending=False) if rows else pd.DataFrame()


def ablation_table(rules: pd.DataFrame) -> pd.DataFrame:
    if rules.empty:
        return pd.DataFrame()
    rows = []
    pairs = rules[(rules.indicator_rule.str.contains(" & ", regex=False, na=False)) & (rules.n >= 5)].head(50)
    for r in pairs.itertuples(index=False):
        a, b = r.indicator_rule.split(" & ")
        same = rules[(rules.timeframe == r.timeframe) & (rules.side == r.side) & (rules.config_id == r.config_id) & (rules.base_pattern == r.base_pattern)]
        for removed, kept in [(a, b), (b, a)]:
            single = same[same.indicator_rule == kept]
            if single.empty:
                continue
            s = single.iloc[0]
            rows.append({
                "timeframe": r.timeframe, "side": r.side, "config_id": r.config_id,
                "base_pattern": r.base_pattern, "pair_rule": r.indicator_rule,
                "removed_feature": removed, "kept_rule": kept,
                "pair_n": r.n, "pair_rate": r.target_rate, "pair_mean50": r.mean50,
                "single_n": s.n, "single_rate": s.target_rate, "single_mean50": s.mean50,
                "rate_increment": r.target_rate - s.target_rate,
                "mean50_increment": r.mean50 - s.mean50,
            })
    return pd.DataFrame(rows).sort_values(["rate_increment", "mean50_increment"], ascending=False) if rows else pd.DataFrame()


def write_report(metadata: dict, rules: pd.DataFrame, families: pd.DataFrame, redundancy: pd.DataFrame, ablation: pd.DataFrame) -> None:
    promoted = rules[rules.promotion_pass] if not rules.empty else pd.DataFrame()
    non_diag = rules[~rules.diagnostic_only] if not rules.empty else pd.DataFrame()
    best = non_diag.head(30)
    diag90 = rules[rules.diagnostic_only & (rules.target_rate >= .90)] if not rules.empty else pd.DataFrame()
    lines = [
        "# BTC Candlestick Master — Phase 5C Indicator Increment Audit",
        "",
        "## Decision",
        "",
        ("At least one indicator-augmented rule passed the strict A+ gate." if not promoted.empty else "No added indicator produced a robust 90% A+ rule."),
        "",
        "This phase asks a narrower question: does Ichimoku or another indicator remove losing Phase 5B signals without destroying expectancy and sample size?",
        "",
        "## Indicator families tested",
        "",
        "- Ichimoku 9/26/52: cloud location, full alignment, Kijun direction and recent cloud break.",
        "- DMI/ADX 14: direction alignment, ADX 20 and ADX 25+rising.",
        "- Bollinger/Keltner/Choppiness: trend location and squeeze release.",
        "- Money flow: CMF20, OBV slope, MFI14 and VWMA20.",
        "- Trend-following: SuperTrend 10×3 and PSAR.",
        "- Momentum: MACD 12/26/9 and Stochastic 14/3.",
        "- Same-close Binance spot confirmation for Ichimoku, DMI, CMF and VWMA.",
        "",
        "## Method",
        "",
        "- Binance perpetual remains the execution and outcome venue.",
        "- Only 4h and 1d completed bars generate direction.",
        "- Phase 5B entry, same-bar-stop convention and cost assumptions are unchanged.",
        "- Thresholds are pre-registered; the final test is never used to tune them.",
        "- Single indicators are screened in training, cross-family pairs in validation, and the following year is untouched test.",
        "- Quarter-ATR targets are diagnostic only and cannot pass promotion.",
        "",
        "## Family-level out-of-sample lift",
        "",
        families.to_markdown(inde