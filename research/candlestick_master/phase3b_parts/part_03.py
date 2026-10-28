

def stable_events(perf: pd.DataFrame) -> pd.DataFrame:
    if perf.empty:
        return perf
    z = perf.copy()
    for c in ["train_n", "validation_n", "test_n"]:
        z[c] = pd.to_numeric(z[c], errors="coerce").fillna(0)
    mask = (
        (z.train_n >= 25) & (z.validation_n >= 8) & (z.test_n >= 8)
        & (z.train_win_rate >= 0.52) & (z.validation_win_rate >= 0.52) & (z.test_win_rate >= 0.52)
        & (z.train_median_signed_ret > 0) & (z.validation_median_signed_ret > 0) & (z.test_median_signed_ret > 0)
    )
    out = z[mask].copy()
    if not out.empty:
        out["min_win"] = out[["train_win_rate", "validation_win_rate", "test_win_rate"]].min(axis=1)
        out["min_ret"] = out[["train_median_signed_ret", "validation_median_signed_ret", "test_median_signed_ret"]].min(axis=1)
        out = out.sort_values(["min_win", "test_n", "min_ret"], ascending=False)
    return out


def touch_deterioration(perf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tf in perf.timeframe.unique():
        for p in [14, 28, 56, 112, 224, 448, 896]:
            for mode, direction in [("bull", "bullish"), ("bear", "bearish")]:
                names = [f"ma{p}_{mode}_touch_1", f"ma{p}_{mode}_touch_2", f"ma{p}_{mode}_touch_3plus"]
                z = perf[(perf.timeframe == tf) & perf.event.isin(names)].copy()
                if len(z) != 3:
                    continue
                z["ordinal"] = z.event.map({names[0]: 1, names[1]: 2, names[2]: 3})
                z = z.sort_values("ordinal")
                row = {"timeframe": tf, "ma": p, "mode": mode, "direction": direction}
                for _, r in z.iterrows():
                    o = int(r.ordinal)
                    row[f"test_n_{o}"] = r.test_n
                    row[f"test_win_{o}"] = r.test_win_rate
                    row[f"test_ret_{o}"] = r.test_median_signed_ret
                    row[f"test_mfe_{o}"] = r.test_median_mfe_atr
                    row[f"test_mae_{o}"] = r.test_median_mae_atr
                if all(pd.notna(row.get(f"test_win_{o}")) for o in [1, 2, 3]):
                    row["win_change_1_to_3"] = row["test_win_3"] - row["test_win_1"]
                    row["ret_change_1_to_3"] = row["test_ret_3"] - row["test_ret_1"]
                rows.append(row)
    return pd.DataFrame(rows)


def source_claim_matrix(perf: pd.DataFrame, touches: pd.DataFrame, ladders: pd.DataFrame) -> pd.DataFrame:
    rows = []
    # Claim 1: repeated touch weakens defense.
    if not touches.empty:
        valid = touches[(touches.test_n_1 >= 8) & (touches.test_n_3 >= 8)].copy()
        if not valid.empty:
            support = valid[valid.mode == "bull"]
            bear = valid[valid.mode == "bear"]
            rows.append({"claim": "Repeated MA touches weaken defense", "evidence_rows": len(valid), "support_fraction": float((valid.win_change_1_to_3 < 0).mean()), "status": "supported" if (valid.win_change_1_to_3 < 0).mean() >= 0.60 else "mixed"})
            rows.append({"claim": "Repeated rising-MA support touches weaken", "evidence_rows": len(support), "support_fraction": float((support.win_change_1_to_3 < 0).mean()) if len(support) else np.nan, "status": "supported" if len(support) and (support.win_change_1_to_3 < 0).mean() >= 0.60 else "mixed"})
    # Claim 2: slope deceleration makes the next-MA ladder more likely.
    if not ladders.empty:
        test = ladders[(ladders.split == "test") & ladders.subgroup.isin(["slope_decelerating", "slope_not_decelerating"])].copy()
        piv = test.pivot_table(index=["timeframe", "short_ma", "long_ma", "direction"], columns="subgroup", values=["target_first_rate", "decided"], aggfunc="first")
        if not piv.empty and ("target_first_rate", "slope_decelerating") in piv.columns and ("target_first_rate", "slope_not_decelerating") in piv.columns:
            d = piv[("target_first_rate", "slope_decelerating")] - piv[("target_first_rate", "slope_not_decelerating")]
            d = d.dropna()
            rows.append({"claim": "MA slope deceleration raises next-MA target probability", "evidence_rows": len(d), "support_fraction": float((d > 0).mean()) if len(d) else np.nan, "status": "supported" if len(d) and (d > 0).mean() >= 0.60 else "mixed"})
    # Claim 3: location/confirmation improves 3x body and hammer signals.
    comparisons = [
        ("long_bull_3x_all", "long_bull_3x_midpoint_hold_confirm", "3x bullish candle improves after midpoint confirmation"),
        ("long_bear_3x_all", "long_bear_3x_midpoint_hold_confirm", "3x bearish candle improves after midpoint confirmation"),
    ]
    for base, confirmed, label in comparisons:
        pairs = []
        for tf in perf.timeframe.unique():
            a = perf[(perf.timeframe == tf) & (perf.event == base)]
            b = perf[(perf.timeframe == tf) & (perf.event == confirmed)]
            if len(a) and len(b) and float(b.test_n.iloc[0]) >= 8:
                pairs.append(float(b.test_win_rate.iloc[0] - a.test_win_rate.iloc[0]))
        rows.append({"claim": label, "evidence_rows": len(pairs), "support_fraction": float(np.mean(np.array(pairs) > 0)) if pairs else np.nan, "status": "supported" if pairs and np.mean(np.array(pairs) > 0) >= 0.60 else "mixed"})
    return pd.DataFrame(rows)


def make_report(frames: dict[str, pd.DataFrame], perf: pd.DataFrame, fp: pd.DataFrame, touches: pd.DataFrame, ladders: pd.DataFrame, claims: pd.DataFrame) -> None:
    stable = stable_events(perf)
    lines = [
        "# BTC Candlestick Master — Phase 3B",
        "",
        "## Source",
        "",
        "This phase tests the objectively codable hypotheses in the 2011 Bondweb/동양종합금융증권 technical-analysis curriculum: 3·7·14·28·56 doubling MAs, slope and slope deceleration, first versus repeated MA touches, sequential next-MA targets, convergence/expansion, stable spacing, 3× average-body candles, MA14 confirmation, hammer/hanging-man location, and five-candle runs.",
        "",
        "The source is not treated as proof. BTC results below use only information available at candle close.",
        "",
        "## Data",
        "",
    ]
    for tf, x in frames.items():
        lines.append(f"- {tf}: {len(x):,} bars, {x.index.min().isoformat()} → {x.index.max().isoformat()}")
    lines += ["", "## Events surviving train, validation and untouched test", ""]
    if stable.empty:
        lines.append("No event passed the conservative consistency gate.")
    else:
        cols = ["timeframe", "event", "direction", "train_n", "validation_n", "test_n", "train_win_rate", "validation_win_rate", "test_win_rate", "test_median_signed_ret", "test_median_mfe_atr", "test_median_mae_atr"]
        lines.append(stable.head(40)[cols].to_markdown(index=False, floatfmt=".3f"))
    lines += ["", "## First versus repeated independent MA touches", ""]
    if touches.empty:
        lines.append("No touch-comparison rows.")
    else:
        good = touches[(touches.test_n_1 >= 8) & (touches.test_n_3 >= 8)].sort_values("win_change_1_to_3")
        cols = ["timeframe", "ma", "mode", "test_n_1", "test_win_1", "test_ret_1", "test_n_2", "test_win_2", "test_ret_2", "test_n_3", "test_win_3", "test_ret_3", "win_change_1_to_3"]
        lines.append(good.head(35)[cols].to_markdown(index=False, floatfmt=".3f") if len(good) else "No row had enough first and third-touch samples.")
    lines += ["", "## Sequential next-MA ladder", ""]
    test_l = ladders[(ladders.split == "test") & (ladders.subgroup == "all") & (ladders.decided >= 8)].sort_values(["target_first_rate", "decided"], ascending=False)
    if test_l.empty:
        lines.append("No ladder row had eight decided test events.")
    else:
        cols = ["timeframe", "short_ma", "long_ma", "direction", "events", "decided", "target_first", "target_first_rate", "wilson_low", "wilson_high", "median_bars", "median_gap_atr"]
        lines.append(test_l[cols].to_markdown(index=False, floatfmt=".3f"))
    lines += ["", "## Source-claim audit", ""]
    lines.append(claims.to_markdown(index=False, floatfmt=".3f") if not claims.empty else "No source claim could be audited.")
    lines += [
        "", "## Interpretation rules", "",
        "- A high test win rate with a tiny sample is not promoted.",
        "- Event-return direction and target-before-stop probability are separate questions.",
        "- A source claim is marked supported only when multiple independent rows agree; otherwise it remains mixed.",
        "- Phase 3C must add walk-forward thresholds, exchange replication, costs and current-data extension before TradingView use.",
    ]
    (OUT / "phase3b_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    hourly = load_hourly(download_source())
    raws = {"1h": hourly}
    for tf, cfg in TF.items():
        if tf != "1h":
            raws[tf] = resample(hourly, cfg["rule"])
    frames, perfs, fps, ladders_all = {}, [], [], []
    for tf, raw in raws.items():
        x = enrich(raw, TF[tf]["hours"])
        events = build_events(x, tf)
        perf, fp = evaluate_events(tf, x, events)
        ladders = summarize_ladders(tf, x)
        frames[tf] = x
        perfs.append(perf)
        fps.append(fp)
        ladders_all.append(ladders)
    perf = pd.concat(perfs, ignore_index=True)
    fp = pd.concat(fps, ignore_index=True)
    ladders = pd.concat(ladders_all, ignore_index=True)
    touches = touch_deterioration(perf)
    claims = source_claim_matrix(perf, touches, ladders)
    stable = stable_events(perf)

    perf.to_csv(OUT / "event_performance.csv", index=False)
    fp.to_csv(OUT / "event_first_passage.csv", index=False)
    touches.to_csv(OUT / "touch_deterioration.csv", index=False)
    ladders.to_csv(OUT / "next_ma_ladder.csv", index=False)
    claims.to_csv(OUT / "source_claim_audit.csv", index=False)
    stable.to_csv(OUT / "stable_events.csv", index=False)
    make_report(frames, perf, fp, touches, ladders, claims)
    metadata = {
        "phase": "3B", "source": "Bondweb 2011 technical-analysis curriculum",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "bars": {tf: len(x) for tf, x in frames.items()},
        "events_tested": int(len(perf)), "stable_events": int(len(stable)),
        "touch_rows": int(len(touches)), "ladder_rows": int(len(ladders)),
        "claim_rows": int(len(claims)),
    }
    (OUT / "phase3b_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
