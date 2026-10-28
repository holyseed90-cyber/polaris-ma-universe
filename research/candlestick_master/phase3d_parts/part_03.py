

def analyze_venue(name: str, hourly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    all_trades: list[pd.DataFrame] = []
    all_ladders: list[pd.DataFrame] = []
    frames: dict[str, pd.DataFrame] = {}
    for tf, cfg in TIMEFRAMES.items():
        raw = hourly if tf == "1h" else resample_ohlcv(hourly, cfg["rule"])
        x = enrich(raw, cfg["hours"])
        frames[tf] = x
        for rule, (mask, side) in build_rules(x, tf).items():
            t = simulate_rule(x, mask, side, tf, name, rule)
            if not t.empty:
                all_trades.append(t)
        ladd = ladder_events(x, tf)
        if not ladd.empty:
            ladd.insert(0, "venue", name)
            ladd["split"] = ladd.signal_time.map(split_label)
            all_ladders.append(ladd)
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    ladders = pd.concat(all_ladders, ignore_index=True) if all_ladders else pd.DataFrame()
    return trades, ladders, frames


def three_split_stability(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    z = summary[summary.cost_bps == 20].copy()
    idx = ["venue", "timeframe", "rule", "side"]
    metrics = ["n", "win_rate", "mean_net_pct", "profit_factor", "max_drawdown_pct"]
    wide = z.pivot_table(index=idx, columns="split", values=metrics, aggfunc="first")
    wide.columns = [f"{m}_{s}" for m, s in wide.columns]
    wide = wide.reset_index()
    needed = [f"n_{s}" for s in SPLITS] + [f"mean_net_pct_{s}" for s in SPLITS]
    for col in needed:
        if col not in wide:
            wide[col] = np.nan
    wide["all_splits_positive"] = (
        (wide.n_train >= 20) & (wide.n_validation >= 10) & (wide.n_test >= 10)
        & (wide.mean_net_pct_train > 0) & (wide.mean_net_pct_validation > 0) & (wide.mean_net_pct_test > 0)
    )
    wide["min_split_mean"] = wide[["mean_net_pct_train", "mean_net_pct_validation", "mean_net_pct_test"]].min(axis=1)
    return wide.sort_values(["all_splits_positive", "min_split_mean", "n_test"], ascending=[False, False, False])


def cross_venue_consistency(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    z = summary[(summary.cost_bps == 20) & (summary.split == "test") & (summary.n >= 10)].copy()
    rows: list[dict] = []
    for keys, g in z.groupby(["timeframe", "rule", "side"]):
        pos = g.mean_net_pct > 0
        rows.append({
            "timeframe": keys[0], "rule": keys[1], "side": keys[2],
            "venues_tested": int(len(g)), "venues_positive": int(pos.sum()),
            "positive_fraction": float(pos.mean()),
            "weighted_n": int(g.n.sum()),
            "weighted_win_rate": float(np.average(g.win_rate, weights=g.n)),
            "weighted_mean_net_pct": float(np.average(g.mean_net_pct, weights=g.n)),
            "worst_venue_mean_net_pct": float(g.mean_net_pct.min()),
            "best_venue_mean_net_pct": float(g.mean_net_pct.max()),
            "positive_venues": ",".join(g.loc[pos, "venue"].tolist()),
        })
    return pd.DataFrame(rows).sort_values(
        ["positive_fraction", "venues_positive", "weighted_mean_net_pct", "weighted_n"],
        ascending=[False, False, False, False],
    )


def ladder_cross_venue(ladder_summary: pd.DataFrame) -> pd.DataFrame:
    if ladder_summary.empty:
        return pd.DataFrame()
    z = ladder_summary[(ladder_summary.split == "test") & (ladder_summary.decided >= 8)].copy()
    rows: list[dict] = []
    group = ["timeframe", "short_ma", "long_ma", "direction", "gap_bin"]
    for keys, g in z.groupby(group):
        rows.append({
            **dict(zip(group, keys)),
            "venues_tested": len(g),
            "decided": int(g.decided.sum()),
            "weighted_target_rate": float(np.average(g.target_rate, weights=g.decided)),
            "minimum_venue_rate": float(g.target_rate.min()),
            "maximum_venue_rate": float(g.target_rate.max()),
            "venues_ge_60pct": int((g.target_rate >= 0.60).sum()),
        })
    return pd.DataFrame(rows).sort_values(
        ["venues_tested", "weighted_target_rate", "decided"], ascending=[False, False, False]
    )


def spot_perp_comparison(frames: dict[str, dict[str, pd.DataFrame]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "binance_spot" not in frames or "binance_perp" not in frames:
        return pd.DataFrame(), pd.DataFrame()
    spot = frames["binance_spot"]["1h"]
    perp = frames["binance_perp"]["1h"]
    common = spot.index.intersection(perp.index)
    s, p = spot.loc[common], perp.loc[common]
    range_s = (s.high - s.low) / s.close * 100
    range_p = (p.high - p.low) / p.close * 100
    price_rows = pd.DataFrame(
        {
            "metric": [
                "common_hours", "median_basis_bps", "p95_abs_basis_bps",
                "median_spot_range_pct", "median_perp_range_pct", "p95_perp_to_spot_range_ratio",
            ],
            "value": [
                len(common),
                float(((p.close / s.close - 1) * 10000).median()),
                float(((p.close / s.close - 1).abs() * 10000).quantile(0.95)),
                float(range_s.median()), float(range_p.median()),
                float((range_p / range_s.replace(0, np.nan)).quantile(0.95)),
            ],
        }
    )
    agree_rows: list[dict] = []
    srules = build_rules(spot, "1h")
    prules = build_rules(perp, "1h")
    for rule in sorted(set(srules) & set(prules)):
        st = set(spot.index[srules[rule][0].fillna(False)])
        pt = set(perp.index[prules[rule][0].fillna(False)])
        union = st | pt
        exact = len(st & pt) / len(union) if union else np.nan
        expanded_p = pt | {t + pd.Timedelta(hours=1) for t in pt} | {t - pd.Timedelta(hours=1) for t in pt}
        near = len(st & expanded_p) / len(st) if st else np.nan
        agree_rows.append({
            "rule": rule, "spot_signals": len(st), "perp_signals": len(pt),
            "exact_jaccard": exact, "spot_matched_within_1h": near,
        })
    return price_rows, pd.DataFrame(agree_rows)


def session_cross_venue(session_summary: pd.DataFrame) -> pd.DataFrame:
    if session_summary.empty:
        return pd.DataFrame()
    z = session_summary[(session_summary.dimension == "kill_zone") & (session_summary.n >= 8)].copy()
    rows: list[dict] = []
    for keys, g in z.groupby(["timeframe", "rule", "side", "kill_zone"]):
        rows.append({
            "timeframe": keys[0], "rule": keys[1], "side": keys[2], "kill_zone": keys[3],
            "venues_tested": len(g), "venues_positive": int((g.mean_net_pct > 0).sum()),
            "n": int(g.n.sum()),
            "weighted_win_rate": float(np.average(g.win_rate, weights=g.n)),
            "weighted_mean_net_pct": float(np.average(g.mean_net_pct, weights=g.n)),
        })
    return pd.DataFrame(rows).sort_values(
        ["venues_positive", "weighted_mean_net_pct", "n"], ascending=[False, False, False]
    )
