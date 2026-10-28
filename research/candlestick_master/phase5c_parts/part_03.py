                merged["i_spot_cmf"] = sf["i_cmf05"]
                merged["i_spot_vwma"] = sf["i_vwma_align"]
            else:
                merged.update({"i_spot_ichi": False, "i_spot_dmi": False, "i_spot_cmf": False, "i_spot_vwma": False})
            rows.append(merged)
        out_parts.append(pd.DataFrame(rows))
    out = pd.concat(out_parts, ignore_index=True)
    indicator_cols = [c for c in out.columns if c.startswith("i_")]
    out[indicator_cols] = out[indicator_cols].fillna(False).astype(bool)
    return out


def wilson(success: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
    p = success / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return centre - half, centre + half


def profit_factor(values: pd.Series) -> float:
    pos = float(values[values > 0].sum())
    neg = float(-values[values < 0].sum())
    return np.inf if neg == 0 and pos > 0 else (pos / neg if neg > 0 else np.nan)


def metrics(z: pd.DataFrame, cost: int = 30) -> dict:
    if z.empty:
        return {"n": 0}
    net = pd.to_numeric(z[f"net_{cost}bps_pct"], errors="coerce").dropna()
    if net.empty:
        return {"n": 0}
    target = z.loc[net.index, "outcome"].eq("target")
    lo, hi = wilson(int(target.sum()), len(target))
    return {
        "n": int(len(net)),
        "target_rate": float(target.mean()),
        "wilson_low": float(lo),
        "wilson_high": float(hi),
        "positive_rate": float((net > 0).mean()),
        "mean_net": float(net.mean()),
        "median_net": float(net.median()),
        "profit_factor": float(profit_factor(net)),
    }


def period_mask(s: pd.Series, start: str, end: str) -> pd.Series:
    t = pd.to_datetime(s, utc=True)
    return (t >= utc(start)) & (t < utc(end))


def bh_adjust(pvalues: Iterable[float]) -> np.ndarray:
    p = np.asarray(list(pvalues), dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(np.nan_to_num(p, nan=1.0))
    ranked = p[order]
    adj = np.empty(n, dtype=float)
    running = 1.0
    for i in range(n - 1, -1, -1):
        val = ranked[i] * n / (i + 1) if np.isfinite(ranked[i]) else 1.0
        running = min(running, val)
        adj[i] = min(1.0, running)
    out = np.empty(n, dtype=float)
    out[order] = adj
    return out


def one_sided_lift_p(filtered: pd.DataFrame, baseline: pd.DataFrame) -> float:
    if filtered.empty or baseline.empty:
        return np.nan
    a = int(filtered.outcome.eq("target").sum())
    n1 = len(filtered)
    b = int(baseline.outcome.eq("target").sum())
    n0 = len(baseline)
    p_pool = (a + b) / (n1 + n0)
    se = math.sqrt(max(1e-15, p_pool * (1 - p_pool) * (1 / n1 + 1 / n0)))
    z = (a / n1 - b / n0) / se
    return float(stats.norm.sf(z))


def base_pattern_columns(events: pd.DataFrame, side: str) -> list[str]:
    cols = []
    for c in events.columns:
        if not c.startswith("b_"):
            continue
        if side == "long" and any(k in c for k in ["bull", "low_sweep", "spring"]):
            cols.append(c)
        if side == "short" and any(k in c for k in ["bear", "high_sweep", "upthrust"]):
            cols.append(c)
    return sorted(cols)


def candidate_indicator_rules(train: pd.DataFrame, validation: pd.DataFrame, base_col: str, tf: str) -> tuple[list[tuple[str, ...]], pd.DataFrame]:
    min_train = 40 if tf == "4h" else 12
    min_val = 12 if tf == "4h" else 4
    base_tr = train[train[base_col]]
    base_va = validation[validation[base_col]]
    if len(base_tr) < min_train or len(base_va) < min_val:
        return [], pd.DataFrame()
    base_tr_m, base_va_m = metrics(base_tr), metrics(base_va)
    rows = []
    singles_by_family: dict[str, list[tuple[float, str]]] = {k: [] for k in FAMILY_MAP}
    for feature, family in FEATURE_TO_FAMILY.items():
        tr = base_tr[base_tr[feature]]
        va = base_va[base_va[feature]]
        if len(tr) < min_train or len(va) < min_val:
            continue
        mt, mv = metrics(tr), metrics(va)
        p = one_sided_lift_p(va, base_va)
        row = {
            "base_pattern": base_col, "indicator_rule": feature, "family": family,
            "condition_count": 1, "train_base_n": base_tr_m["n"], "validation_base_n": base_va_m["n"],
            "train_base_rate": base_tr_m["target_rate"], "validation_base_rate": base_va_m["target_rate"],
            "train_n": mt["n"], "train_rate": mt["target_rate"], "train_mean": mt["mean_net"], "train_pf": mt["profit_factor"],
            "validation_n": mv["n"], "validation_rate": mv["target_rate"], "validation_mean": mv["mean_net"], "validation_pf": mv["profit_factor"],
            "train_lift": mt["target_rate"] - base_tr_m["target_rate"],
            "