        "outcome": outcome,
        "holding_bars": int(exit_i - entry_i + 1),
        "gross_pct": gross,
    }
    for cost in COST_BPS:
        result[f"net_{cost}bps_pct"] = gross - cost / 100
    return result


def build_outcomes(events: pd.DataFrame, primary_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict] = []
    for tf, configs in CONFIGS.items():
        x = primary_frames[tf]
        z = events[events.timeframe == tf]
        for cfg in configs:
            for r in z.itertuples(index=False):
                sim = simulate_event(x, r.bar_index, r.side, cfg["target"], cfg["stop"], cfg["hold"])
                if sim.get("valid"):
                    rows.append({
                        "event_id": int(r.event_id), "timeframe": tf, "side": r.side,
                        "signal_time": r.signal_time, "config_id": cfg["config_id"],
                        "target_mult": cfg["target"], "stop_mult": cfg["stop"],
                        "max_hold": cfg["hold"], **sim,
                    })
    return pd.DataFrame(rows)


def period_mask(times: pd.Series, start: str, end: str) -> np.ndarray:
    t = pd.to_datetime(times, utc=True)
    return ((t >= utc(start)) & (t < utc(end))).to_numpy()


def rule_mask(frame: pd.DataFrame, conditions: tuple[str, ...]) -> np.ndarray:
    if not conditions:
        return np.ones(len(frame), dtype=bool)
    out = np.ones(len(frame), dtype=bool)
    for c in conditions:
        out &= frame[c].to_numpy(bool)
    return out


def score_rule(frame: pd.DataFrame, mask: np.ndarray, cost: int = MAIN_COST) -> dict:
    """Fast rule metrics used during mining; path-dependent drawdown is deferred."""
    idx = np.flatnonzero(mask)
    n = len(idx)
    if n == 0:
        return {"n": 0}
    target = frame.outcome.eq("target").to_numpy()[idx]
    values = frame[f"net_{cost}bps_pct"].to_numpy(float)[idx]
    success = int(target.sum())
    lo, hi = wilson(success, n)
    gp = values[values > 0].sum()
    gl = -values[values <= 0].sum()
    pf = float(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan)
    return {
        "n": int(n),
        "target_rate": float(success / n),
        "target_wilson_low": float(lo),
        "target_wilson_high": float(hi),
        "positive_rate": float((values > 0).mean()),
        "mean_net_pct": float(values.mean()),
        "median_net_pct": float(np.median(values)),
        "profit_factor": pf,
        "max_drawdown_pct": np.nan,
        "stop_rate": float(frame.outcome.isin(["stop", "ambiguous_as_stop"]).to_numpy()[idx].mean()),
        "time_exit_rate": float(frame.outcome.eq("time_exit").to_numpy()[idx].mean()),
    }


def candidate_p_value(success: int, n: int, baseline: float) -> float:
    if n <= 0 or not np.isfinite(baseline):
        return np.nan
    return float(stats.binomtest(success, n, p=float(np.clip(baseline, 1e-6, 1 - 1e-6)), alternative="greater").pvalue)


def beam_candidates(train: pd.DataFrame, tf: str, side: str) -> list[tuple[str, ...]]:
    """Generate interpretable conjunctions from training data only."""
    base_cols = [c for c in train.columns if c.startswith("b_") and train[c].any()]
    context_cols = [c for c in train.columns if c.startswith("f_") and train[c].any()]
    min_train = 35 if tf == "4h" else 10
    baseline = float(train.outcome.eq("target").mean())
    candidates: dict[tuple[str, ...], float] = {}
    current: list[tuple[str, ...]] = [(b,) for b in base_cols]
    seen = set(current)
    for depth in range(1, 4):
        scored: list[tuple[float, tuple[str, ...]]] = []
        for conditions in current:
            m = score_rule(train, rule_mask(train, conditions), MAIN_COST)
