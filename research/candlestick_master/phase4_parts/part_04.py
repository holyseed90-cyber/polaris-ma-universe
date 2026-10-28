    model = fit_woe(train)
    validation["prob"] = model.predict(validation)
    threshold, threshold_table = choose_threshold(validation, validation.prob.to_numpy(), tf)
    test["prob"] = model.predict(test)
    test["selected"] = test.prob >= threshold
    baseline = metrics(test)
    selected = metrics(test[test.selected])
    brier = float(np.mean((test.prob - test.positive) ** 2))
    result = {
        "fold": fold["fold"], "timeframe": tf, "side": side,
        "config_id": config_id, "threshold": threshold,
        "train_n": len(train), "validation_n": len(validation), "test_n": len(test),
        "test_brier": brier,
        **{f"baseline_{k}": v for k, v in baseline.items()},
        **{f"selected_{k}": v for k, v in selected.items()},
    }
    test["fold"] = fold["fold"]
    test["threshold"] = threshold
    return test, result, config_table.assign(fold=fold["fold"], timeframe=tf, side=side), threshold_table.assign(fold=fold["fold"], timeframe=tf, side=side, config_id=config_id)


def calibration_table(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    z = scored.copy()
    z["score_tier"] = pd.cut(z.prob, [0, .50, .55, .60, .65, .70, .75, 1.01], labels=["lt50", "50_55", "55_60", "60_65", "65_70", "70_75", "ge75"], right=False)
    rows = []
    for keys, g in z.groupby(["timeframe", "side", "score_tier"], observed=True):
        m = metrics(g)
        pval = stats.ttest_1samp(g.net_pct, popmean=0, alternative="greater", nan_policy="omit").pvalue if len(g) >= 3 else np.nan
        rows.append({"timeframe": keys[0], "side": keys[1], "score_tier": str(keys[2]), "mean_probability": g.prob.mean(), "actual_positive_rate": g.positive.mean(), "p_value": pval, **m})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["bh_q_value"] = benjamini_hochberg(out.p_value)
    return out


def strict_portfolio(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    selected = scored[scored.selected].copy().sort_values(["venue", "signal_time", "prob"], ascending=[True, True, False])
    kept = []
    for venue, z in selected.groupby("venue"):
        busy_until = pd.Timestamp.min.tz_localize("UTC")
        for _, r in z.iterrows():
            st = pd.to_datetime(r.signal_time, utc=True)
            if st < busy_until:
                continue
            same_time = z[z.signal_time == r.signal_time]
            best = same_time.sort_values("prob", ascending=False).iloc[0]
            if int(best.event_id) != int(r.event_id):
                continue
            kept.append(r)
            busy_until = pd.to_datetime(r.exit_time, utc=True)
    return pd.DataFrame(kept)


def yearly_walkforward_summary(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if scored.empty:
        return pd.DataFrame()
    for keys, g in scored.groupby(["fold", "timeframe", "side"]):
        base = metrics(g)
        sel = metrics(g[g.selected])
        rows.append({"fold": keys[0], "timeframe": keys[1], "side": keys[2], **{f"baseline_{k}": v for k, v in base.items()}, **{f"selected_{k}": v for k, v in sel.items()}})
    return pd.DataFrame(rows)


def top_contributions(models: list[dict]) -> pd.DataFrame:
    rows = []
    for m in models:
        model: WOEModel = m["model"]
        for feature, mapping in model.contributions.items():
            for value, contribution in mapping.items():
                rows.append({"fold": m["fold"], "timeframe": m["timeframe"], "side": m["side"], "feature": feature, "value": value, "contribution": contribution})
    return pd.DataFrame(rows)


def report(metadata: dict, fold_summary: pd.DataFrame, calibration: pd.DataFrame, portfolio: pd.DataFrame, configs: pd.DataFrame, thresholds: pd.DataFrame) -> None:
    lines = [
        "# BTC Candlestick Master — Phase 4",
        "",
        "## Scope",
        "",
        "Interpretable Weight-of-Evidence composite score, expanding nested walk-forward selection, target/stop/holding grid, next-bar entry, 20 bps round-trip costs, cross-venue confirmation, higher-timeframe context, MA target distance, calibration and false-discovery audit.",
        "",
        "## Leakage controls",
        "",
        "- Each fold selects target/stop/holding parameters using its training and immediately prior validation period only.",
        "- Score contributions are fitted on the fold training period only.",
        "- The probability threshold is selected on the fold validation period only.",
        "- The following calendar year is then evaluated without re-fitting.",
        "- Signal features use completed candles only; entry is the next bar open.",
        "- Same-bar target/stop ambiguity is treated as a stop.",
        "- 20 bps round-trip cost is deducted from every trade.",
        "",
        "## Fold results",
        "",
        fold_summary.to_markdown(index=False, floatfmt=".3f") if not fold_summary.empty else "No fold results.",
        "",
        "## Score calibration and BH multiple-testing audit",
        "",
        calibration.sort_values(["bh_q_value", "mean_net_pct"], ascending=[True, False]).head(50).to_markdown(index=False, floatfmt=".3f") if not calibration.empty else "No calibration rows.",
        "",
        "## Strict no-overlap portfolio",
        "",
    ]
    if portfolio.empty:
        lines.append("No portfolio trades.")
    else:
