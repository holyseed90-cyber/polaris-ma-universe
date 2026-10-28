validation_lift": mv["target_rate"] - base_va_m["target_rate"],
            "validation_p": p,
        }
        rows.append(row)
        if mt["target_rate"] >= base_tr_m["target_rate"] + 0.02 and mv["target_rate"] >= base_va_m["target_rate"] + 0.02 and mt["mean_net"] > 0 and mv["mean_net"] > 0:
            score = min(row["train_lift"], row["validation_lift"]) + 0.05 * min(mt["mean_net"], mv["mean_net"])
            singles_by_family[family].append((score, feature))

    shortlist = []
    for family, candidates in singles_by_family.items():
        shortlist.extend([feature for _, feature in sorted(candidates, reverse=True)[:2]])
    selected: list[tuple[str, ...]] = [(f,) for f in shortlist]
    # Cross-family pairs only; cap to avoid combinatorial over-mining.
    for a, b in itertools.combinations(shortlist, 2):
        if FEATURE_TO_FAMILY[a] == FEATURE_TO_FAMILY[b]:
            continue
        tr = base_tr[base_tr[a] & base_tr[b]]
        va = base_va[base_va[a] & base_va[b]]
        if len(tr) < min_train or len(va) < min_val:
            continue
        mt, mv = metrics(tr), metrics(va)
        p = one_sided_lift_p(va, base_va)
        rows.append({
            "base_pattern": base_col, "indicator_rule": f"{a} & {b}",
            "family": f"{FEATURE_TO_FAMILY[a]}+{FEATURE_TO_FAMILY[b]}",
            "condition_count": 2, "train_base_n": base_tr_m["n"], "validation_base_n": base_va_m["n"],
            "train_base_rate": base_tr_m["target_rate"], "validation_base_rate": base_va_m["target_rate"],
            "train_n": mt["n"], "train_rate": mt["target_rate"], "train_mean": mt["mean_net"], "train_pf": mt["profit_factor"],
            "validation_n": mv["n"], "validation_rate": mv["target_rate"], "validation_mean": mv["mean_net"], "validation_pf": mv["profit_factor"],
            "train_lift": mt["target_rate"] - base_tr_m["target_rate"],
            "validation_lift": mv["target_rate"] - base_va_m["target_rate"],
            "validation_p": p,
        })
        if mt["target_rate"] >= base_tr_m["target_rate"] + 0.03 and mv["target_rate"] >= base_va_m["target_rate"] + 0.03 and mt["mean_net"] > 0 and mv["mean_net"] > 0:
            selected.append((a, b))
    audit = pd.DataFrame(rows)
    if not audit.empty:
        audit["validation_bh_q"] = bh_adjust(audit.validation_p.fillna(1.0))
        audit = audit.sort_values(["validation_lift", "validation_n"], ascending=[False, False])
    # Final selection uses validation only; at most six rules per base pattern.
    selected_unique = []
    seen = set()
    for rule in selected:
        if rule in seen:
            continue
        seen.add(rule)
        selected_unique.append(rule)
    if not audit.empty:
        valid_names = set(audit[(audit.validation_mean > 0) & (audit.validation_pf >= 1.0) & (audit.validation_lift >= 0.02)].indicator_rule)
        selected_unique = [r for r in selected_unique if " & ".join(r) in valid_names or r[0] in valid_names]
    return selected_unique[:6], audit


def evaluate_walkforward(data: pd.DataFrame, diagnostic: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_rows = []
    audit_rows = []
    configs_by_tf = DIAGNOSTIC_CONFIGS if diagnostic else PROMOTION_CONFIGS
    for fold in p5.FOLDS:
        for tf, config_ids in configs_by_tf.items():
            for side in ["long", "short"]:
                base_cols = base_pattern_columns(data[data.timeframe == tf], side)
                for config_id in config_ids:
                    z = data[(data.timeframe == tf) & (data.side == side) & (data.config_id == config_id)].copy()
                    if z.empty:
                        continue
                    train = z[period_mask(z.signal_time, fold["train_start"], fold["train_end"])]
                    validation = z[period_mask(z.signal_time, fold["validation_start"], fold["validation_end"])]
                    test = z[period_mask(z.signal_time, fold["test_start"], fold["test_end"])]
                    for base_col in base_cols:
                        rules, audit = candidate_indicator_rules(train, validation, base_col, tf)
                        if not audit.empty:
                            audit.insert(0, "fold", fold["fold"])
                            audit.insert(1, "timeframe", tf)
                            audit.insert(2, "side", side)
                            audit.insert(3, "config_id", config_id)
                            audit.insert(4, "diagnostic_only", diagnostic)
                            audit_rows.append(audit)
                        base_test = test[test[base_col]]
                        base_m30, base_m50 = metrics(base_test, 30), metrics(base_test, 50)
                        for rule in rules:
                            filt = pd.Series(True, index=test.index)
     