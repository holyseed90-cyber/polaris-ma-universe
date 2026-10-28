        q["rule_conditions"] = r.conditions
        q["rule_rank"] = rank
        q["selection_score"] = r.selection_score
        q["validation_target_rate"] = r.validation_target_rate
        q["validation_n"] = r.validation_n
        q["validation_bh_q"] = r.validation_bh_q
        q["diagnostic_only"] = r.diagnostic_only
        selected_test_rows.append(q)
    selected_test = pd.concat(selected_test_rows, ignore_index=True) if selected_test_rows else pd.DataFrame()
    return selected_test, audit


def strict_portfolio(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return selected
    z = selected[~selected.diagnostic_only].copy()
    if z.empty:
        return z
    # If several rules select the same event, keep the strongest validation score.
    z = z.sort_values(["signal_time", "selection_score", "validation_target_rate", "validation_n"], ascending=[True, False, False, False])
    z = z.drop_duplicates(["event_id", "config_id", "fold"], keep="first")
    # Across configurations/rules, allow only one live position at a time.
    kept = []
    busy_until = pd.Timestamp.min.tz_localize("UTC")
    for _, r in z.iterrows():
        st = pd.to_datetime(r.signal_time, utc=True)
        if st < busy_until:
            continue
        same_time = z[z.signal_time == r.signal_time]
        best = same_time.sort_values(["selection_score", "validation_target_rate", "validation_n"], ascending=False).iloc[0]
        if int(best.event_id) != int(r.event_id) or str(best.config_id) != str(r.config_id):
            continue
        kept.append(r)
        busy_until = pd.to_datetime(r.exit_time, utc=True)
    return pd.DataFrame(kept)


def block_bootstrap(frame: pd.DataFrame, cost: int, iterations: int = 10000) -> dict:
    if frame.empty:
        return {}
    z = frame.copy()
    z["month_block"] = pd.to_datetime(z.signal_time, utc=True).dt.to_period("M").astype(str)
    blocks = [g for _, g in z.groupby("month_block")]
    if not blocks:
        return {}
    target_rates = []
    means = []
    for _ in range(iterations):
        sample = pd.concat([blocks[i] for i in RNG.integers(0, len(blocks), len(blocks))], ignore_index=True)
        target_rates.append(float(sample.outcome.eq("target").mean()))
        means.append(float(sample[f"net_{cost}bps_pct"].mean()))
    return {
        "target_rate_boot_low": float(np.quantile(target_rates, 0.025)),
        "target_rate_boot_high": float(np.quantile(target_rates, 0.975)),
        "mean_net_boot_low": float(np.quantile(means, 0.025)),
        "mean_net_boot_high": float(np.quantile(means, 0.975)),
    }


def precision_frontier(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    rows = []
    # Rule-level test performance, with exact rule/config canonicalization.
    for keys, g in selected.groupby(["timeframe", "side", "config_id", "rule_conditions", "diagnostic_only"]):
        m20, m30, m50 = metrics(g, 20), metrics(g, 30), metrics(g, 50)
        years = []
        for year, gy in g.groupby(pd.to_datetime(g.signal_time, utc=True).dt.year):
            years.append({"year": int(year), **metrics(gy, 30)})
        rows.append({
            "timeframe": keys[0], "side": keys[1], "config_id": keys[2],
            "rule_conditions": keys[3], "diagnostic_only": keys[4],
            **{f"c20_{k}": v for k, v in m20.items()},
            **{f"c30_{k}": v for k, v in m30.items()},
            **{f"c50_{k}": v for k, v in m50.items()},
            "years_json": json.dumps(years, ensure_ascii=False),
        })
    return pd.DataFrame(rows).sort_values(["c30_target_rate", "c30_n"], ascending=False)


def aplus_gate(frontier: pd.DataFrame) -> pd.DataFrame:
    if frontier.empty:
        return frontier
    rows = []
    for r in frontier.itertuples(index=False):
        years = json.loads(r.years_json)
        active_years = [y for y in years if y.get("n", 0) >= 3]
        min_year_target = min((y.get("target_rate", np.nan) for y in active_years), default=np.nan)
