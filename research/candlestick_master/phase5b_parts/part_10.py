        min_year_mean = min((y.get("mean_net_pct", np.nan) for y in active_years), default=np.nan)
        strict = (
            not bool(r.diagnostic_only)
            and r.c30_n >= (30 if r.timeframe == "4h" else 15)
            and r.c30_target_rate >= 0.90
            and r.c30_target_wilson_low >= 0.75
            and r.c50_mean_net_pct > 0
            and r.c50_profit_factor >= 1.50
            and len(active_years) >= 2
            and min_year_target >= 0.70
            and min_year_mean > 0
        )
        sparse_90 = r.c30_n >= 5 and r.c30_target_rate >= 0.90
        rows.append({
            **r._asdict(),
            "active_years": len(active_years),
            "min_year_target_rate": min_year_target,
            "min_year_mean_net_pct": min_year_mean,
            "aplus_pass": strict,
            "sparse_observed_90": sparse_90 and not strict,
        })
    return pd.DataFrame(rows).sort_values(["aplus_pass", "c30_target_rate", "c30_n"], ascending=[False, False, False])


def support_precision_table(gate: pd.DataFrame) -> pd.DataFrame:
    if gate.empty:
        return pd.DataFrame()
    rows = []
    for minimum in [5, 10, 15, 20, 30, 50, 100]:
        z = gate[(gate.c30_n >= minimum) & ~gate.diagnostic_only]
        if z.empty:
            rows.append({"minimum_rule_test_n": minimum, "qualifying_rules": 0})
            continue
        best = z.sort_values(["c30_target_rate", "c30_n"], ascending=False).iloc[0]
        rows.append({
            "minimum_rule_test_n": minimum,
            "qualifying_rules": len(z),
            "best_target_rate": best.c30_target_rate,
            "best_wilson_low": best.c30_target_wilson_low,
            "best_n": best.c30_n,
            "best_mean_net_30bps": best.c30_mean_net_pct,
            "best_mean_net_50bps": best.c50_mean_net_pct,
            "best_timeframe": best.timeframe,
            "best_side": best.side,
            "best_config_id": best.config_id,
            "best_conditions": best.rule_conditions,
        })
    return pd.DataFrame(rows)


def write_report(metadata: dict, portfolio: pd.DataFrame, gate: pd.DataFrame, support_table: pd.DataFrame, audits: pd.DataFrame) -> None:
    pm20, pm30, pm50 = metrics(portfolio, 20), metrics(portfolio, 30), metrics(portfolio, 50)
    boot = block_bootstrap(portfolio, 30, iterations=10000) if not portfolio.empty else {}
    pass_rows = gate[gate.aplus_pass] if not gate.empty else pd.DataFrame()
    sparse_rows = gate[gate.sparse_observed_90] if not gate.empty else pd.DataFrame()
    lines = [
        "# BTC Candlestick Master — Phase 5B Precision Audit",
        "",
        "## Decision",
        "",
        ("At least one historical rule passed the strict A+ gate." if not pass_rows.empty else "No historical rule passed the strict 90% A+ promotion gate."),
        "",
        "The result is deliberately conservative. Binance perpetual is the execution venue; Binance spot, Coinbase and Bitstamp are causal confirmation only. A 90% observed rate with a tiny sample is listed separately and is never promoted.",
        "",
        "## Research design",
        "",
        "- Base timeframes: 4h and 1d only.",
        "- 1h is excluded from direction generation.",
        "- Entry: next Binance-perpetual bar open.",
        "- Same-bar target and stop: stop.",
        "- Main selection cost: 30 bps round trip; stress: 20 and 50 bps.",
        "- Pre-registered target/stop/holding configurations; no final-test tuning.",
        "- Expanding walk-forward: train, one-year validation, following-year test.",
        "- Candidate conjunctions generated from training only.",
        "- Validation p-values adjusted with Benjamini-Hochberg correction.",
        "- Strict portfolio removes overlapping positions.",
        "",
        "## Strict portfolio",
        "",
        pd.DataFrame([{"cost_bps": 20, **pm20}, {"cost_bps": 30, **pm30}, {"cost_bps": 50, **pm50}]).to_markdown(index=False, floatfmt=".4f") if not portfolio.empty else "No non-diagnostic rule survived into the strict portfolio.",
        "",
        "### Monthly block bootstrap at 30 bps",
        "",
        pd.DataFrame([boot]).to_markdown(index=False, floatfmt=".4f") if boot else "No bootstrap result.",
        "",
        "## Precision versus sample-size frontier",
        "",
        support_table.to_markdown(index=False, floatfmt=".4f") if not support_table.empty else "No frontier rows.",
