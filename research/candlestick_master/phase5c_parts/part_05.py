                       for feature in rule:
                                filt &= test[feature]
                            chosen = test[test[base_col] & filt].copy()
                            if chosen.empty:
                                continue
                            m30, m50 = metrics(chosen, 30), metrics(chosen, 50)
                            for idx in chosen.index:
                                row = chosen.loc[idx].to_dict()
                                row.update({
                                    "fold": fold["fold"], "base_pattern": base_col,
                                    "indicator_rule": " & ".join(rule),
                                    "indicator_families": "+".join(sorted({FEATURE_TO_FAMILY[x] for x in rule})),
                                    "indicator_count": len(rule), "diagnostic_only": diagnostic,
                                    "base_test_n": base_m30.get("n", 0), "base_test_rate": base_m30.get("target_rate", np.nan),
                                    "base_test_mean30": base_m30.get("mean_net", np.nan), "base_test_mean50": base_m50.get("mean_net", np.nan),
                                    "rule_test_n": m30.get("n", 0), "rule_test_rate": m30.get("target_rate", np.nan),
                                    "rule_test_wilson_low": m30.get("wilson_low", np.nan),
                                    "rule_test_mean30": m30.get("mean_net", np.nan), "rule_test_mean50": m50.get("mean_net", np.nan),
                                    "rule_test_pf50": m50.get("profit_factor", np.nan),
                                })
                                selected_rows.append(row)
    selected = pd.DataFrame(selected_rows)
    audit = pd.concat(audit_rows, ignore_index=True) if audit_rows else pd.DataFrame()
    return selected, audit


def aggregate_rules(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    key = ["timeframe", "side", "config_id", "base_pattern", "indicator_rule", "indicator_families", "diagnostic_only"]
    rows = []
    for keys, g in selected.groupby(key, dropna=False):
        # De-duplicate identical event/config/rule selected in more than one fold.
        g = g.sort_values("signal_time").drop_duplicates(["event_id", "config_id", "indicator_rule"])
        m30, m50 = metrics(g, 30), metrics(g, 50)
        base_rate = float(np.average(g.base_test_rate.fillna(0), weights=np.maximum(g.base_test_n, 1)))
        years = []
        for year, y in g.groupby(pd.to_datetime(g.signal_time, utc=True).dt.year):
            ym = metrics(y, 50)
            years.append({"year": int(year), **ym})
        active_years = [y for y in years if y.get("n", 0) > 0]
        rows.append({
            **dict(zip(key, keys)),
            "n": m30.get("n", 0), "target_rate": m30.get("target_rate", np.nan),
            "wilson_low": m30.get("wilson_low", np.nan), "wilson_high": m30.get("wilson_high", np.nan),
            "mean30": m30.get("mean_net", np.nan), "pf30": m30.get("profit_factor", np.nan),
            "mean50": m50.get("mean_net", np.nan), "pf50": m50.get("profit_factor", np.nan),
            "baseline_rate_weighted": base_rate,
            "target_rate_lift": m30.get("target_rate", np.nan) - base_rate,
            "active_years": len(active_years),
            "min_year_rate": min((y.get("target_rate", np.nan) for y in active_years), default=np.nan),
            "min_year_mean50": min((y.get("mean_net", np.nan) for y in active_years), default=np.nan),
            "years_json": json.dumps(years, ensure_ascii=False),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["promotion_pass"] = (
            ~out.diagnostic_only
            & (out.n >= np.where(out.timeframe.eq("4h"), 30, 15))
            & (out.target_rate >= 0.90)
            & (out.wilson_low >= 0.75)
            & (out.mean50 > 0)
            & (out.pf50 >= 1.50)
            & (out.active_years >= 2)
            & (out.min_year_mean50 > 0)
        )
        out = out.sort_values(["promotion_pass", "target_rate", "n", "mean50"], ascending=[False, False, False, False])
    return out


def family_summary(rules: pd.DataFrame) -> pd.DataFrame:
    if rules.empty:
        return pd.DataFrame()
    rows = []
    for family in FAMILY_MAP:
        z = rules[~rules.diagnostic_only & rules.indicator_families.str.contains(family, regex=False, na=False)]
        if z.empty:
            continue
        rows.append({
            "family": family,
            "rule_count": int(len(z)),
            "total_test_n": int(z.n.sum()),
            "median_target_rate": float(z.target_rate.median()),
            "median_target_lift": float(z.target_rate_lift.median()),
            "positive_lift_share": float((z.target_rate_lift > 0).mean()),
  