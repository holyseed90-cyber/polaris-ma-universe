    p = success / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return centre - half, centre + half


def bh_adjust(p_values: Iterable[float]) -> np.ndarray:
    p = np.asarray(list(p_values), dtype=float)
    out = np.full(len(p), np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    if len(valid) == 0:
        return out
    order = valid[np.argsort(p[valid])]
    ranked = p[order] * len(order) / np.arange(1, len(order) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out[order] = np.minimum(ranked, 1.0)
    return out


def max_drawdown_pct(returns_pct: pd.Series) -> float:
    if returns_pct.empty:
        return np.nan
    equity = (1 + returns_pct.fillna(0) / 100).cumprod()
    peak = equity.cummax()
    return float(((equity / peak) - 1).min() * 100)


def profit_factor(values: pd.Series) -> float:
    values = values.dropna().astype(float)
    gp = values[values > 0].sum()
    gl = -values[values <= 0].sum()
    return float(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan)


def metrics(frame: pd.DataFrame, cost_bps: int = MAIN_COST) -> dict:
    if frame.empty:
        return {"n": 0}
    col = f"net_{cost_bps}bps_pct"
    values = frame[col].astype(float)
    targets = frame.outcome.eq("target")
    n = len(frame)
    success = int(targets.sum())
    lo, hi = wilson(success, n)
    return {
        "n": int(n),
        "target_rate": float(targets.mean()),
        "target_wilson_low": float(lo),
        "target_wilson_high": float(hi),
        "positive_rate": float((values > 0).mean()),
        "mean_net_pct": float(values.mean()),
        "median_net_pct": float(values.median()),
        "profit_factor": profit_factor(values),
        "max_drawdown_pct": max_drawdown_pct(values),
        "stop_rate": float(frame.outcome.isin(["stop", "ambiguous_as_stop"]).mean()),
        "time_exit_rate": float(frame.outcome.eq("time_exit").mean()),
    }


def causal_structure(x: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """Causal pivot/structure state; a pivot is usable only after right bars close."""
    n = len(x)
    highs = x.high.to_numpy(float)
    lows = x.low.to_numpy(float)
    closes = x.close.to_numpy(float)
    atr = x.atr14.to_numpy(float)
    state = np.full(n, "mixed", dtype=object)
    last_high = np.full(n, np.nan)
    last_low = np.full(n, np.nan)
    bull_break = np.zeros(n, bool)
    bear_break = np.zeros(n, bool)
    bull_choch = np.zeros(n, bool)
    bear_choch = np.zeros(n, bool)
    bull_retest = np.zeros(n, bool)
    bear_retest = np.zeros(n, bool)
    high_pivots: list[tuple[int, float]] = []
    low_pivots: list[tuple[int, float]] = []
    last_bull_level = np.nan
    last_bull_bar = -10_000
    last_bear_level = np.nan
    last_bear_bar = -10_000
    prev_state = "mixed"
    for i in range(n):
        pivot_i = i - right
        if pivot_i >= left:
            lo_i = pivot_i - left
            hi_i = i + 1
            if highs[pivot_i] >= np.nanmax(highs[lo_i:hi_i]):
