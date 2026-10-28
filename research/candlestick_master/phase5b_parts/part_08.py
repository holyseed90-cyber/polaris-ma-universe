            if m.get("n", 0) < min_train:
                continue
            # Depth one is retained for extension even when weak; deeper levels need an edge.
            if depth > 1 and (m["target_rate"] < baseline + 0.07 or m["mean_net_pct"] <= 0):
                continue
            quality = m["target_wilson_low"] + 0.10 * max(m["mean_net_pct"], -1) + 0.01 * math.log1p(m["n"])
            candidates[conditions] = quality
            scored.append((quality, conditions))
        scored.sort(reverse=True)
        beam = [c for _, c in scored[:120]]
        if depth == 3 or not beam:
            break
        next_level: set[tuple[str, ...]] = set()
        for conditions in beam:
            for feature in context_cols:
                if feature in conditions:
                    continue
                new = tuple(sorted((*conditions, feature)))
                if new not in seen:
                    seen.add(new)
                    next_level.add(new)
        current = list(next_level)
    return list(candidates)


def select_rules_for_fold(merged: pd.DataFrame, fold: dict, tf: str, side: str, config_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = merged[(merged.timeframe == tf) & (merged.side == side) & (merged.config_id == config_id)].copy()
    train = z[period_mask(z.signal_time, fold["train_start"], fold["train_end"])].copy()
    validation = z[period_mask(z.signal_time, fold["validation_start"], fold["validation_end"])].copy()
    test = z[period_mask(z.signal_time, fold["test_start"], fold["test_end"])].copy()
    if train.empty or validation.empty or test.empty:
        return pd.DataFrame(), pd.DataFrame()
    candidates = beam_candidates(train, tf, side)
    baseline_train = float(train.outcome.eq("target").mean())
    baseline_val = float(validation.outcome.eq("target").mean())
    rows = []
    min_val = 9 if tf == "4h" else 3
    for conditions in candidates:
        mt = score_rule(train, rule_mask(train, conditions), MAIN_COST)
        mv = score_rule(validation, rule_mask(validation, conditions), MAIN_COST)
        if mv.get("n", 0) < min_val:
            continue
        success = int(round(mv["target_rate"] * mv["n"]))
        p = candidate_p_value(success, mv["n"], baseline_val)
        rows.append({
            "fold": fold["fold"], "timeframe": tf, "side": side, "config_id": config_id,
            "conditions": " & ".join(conditions), "condition_count": len(conditions),
            "train_baseline_target_rate": baseline_train,
            "validation_baseline_target_rate": baseline_val,
            **{f"train_{k}": v for k, v in mt.items()},
            **{f"validation_{k}": v for k, v in mv.items()},
            "validation_p_value": p,
        })
    audit = pd.DataFrame(rows)
    if audit.empty:
        return pd.DataFrame(), audit
    audit["validation_bh_q"] = bh_adjust(audit.validation_p_value)
    audit["selection_score"] = (
        audit[["train_target_wilson_low", "validation_target_wilson_low"]].min(axis=1)
        + 0.12 * audit[["train_mean_net_pct", "validation_mean_net_pct"]].min(axis=1)
        + 0.01 * np.log1p(audit.validation_n)
        - 0.015 * (audit.condition_count - 1)
    )
    # Selection is deliberately strict but does not demand 90%; final test decides that.
    eligible = audit[
        (audit.train_target_rate >= 0.72)
        & (audit.validation_target_rate >= 0.70)
        & (audit.train_mean_net_pct > 0)
        & (audit.validation_mean_net_pct > 0)
        & (audit.validation_profit_factor >= 1.15)
        & (audit.validation_bh_q <= 0.25)
    ].copy()
    if eligible.empty:
        # Preserve a small diagnostic shortlist; it is not promoted.
        eligible = audit.sort_values(["selection_score", "validation_n"], ascending=False).head(2).copy()
        eligible["diagnostic_only"] = True
    else:
        eligible = eligible.sort_values(["selection_score", "validation_n"], ascending=False).head(5).copy()
        eligible["diagnostic_only"] = False

    selected_test_rows = []
    for rank, r in enumerate(eligible.itertuples(index=False), start=1):
        conditions = tuple(str(r.conditions).split(" & "))
        mask = rule_mask(test, conditions)
        q = test.loc[mask].copy()
        if q.empty:
            continue
        q["fold"] = fold["fold"]
