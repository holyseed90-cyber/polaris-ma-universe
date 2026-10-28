    return (t >= utc(start)) & (t < utc(end))


def choose_config(events: pd.DataFrame, cache: dict, tf: str, side: str, fold: dict) -> tuple[str, pd.DataFrame]:
    base = events[(events.timeframe == tf) & (events.side == side)][["event_id", "signal_time"]]
    rows: list[dict] = []
    min_train = {"1h": 120, "4h": 50, "12h": 20, "1d": 8}[tf]
    min_val = {"1h": 40, "4h": 20, "12h": 8, "1d": 4}[tf]
    for key, sim in cache.items():
        if key[0] != tf or key[1] != side or sim.empty:
            continue
        z = base.merge(sim[["event_id", "net_pct"]], on="event_id", how="inner")
        tr = z[period_mask(z.signal_time, fold["train_start"], fold["train_end"])]
        va = z[period_mask(z.signal_time, fold["validation_start"], fold["validation_end"])]
        if len(tr) < min_train or len(va) < min_val:
            continue
        tr_lcb, va_lcb = mean_lcb(tr.net_pct), mean_lcb(va.net_pct)
        objective = min(tr_lcb, va_lcb) + 0.15 * min(float(tr.net_pct.mean()), float(va.net_pct.mean()))
        rows.append({
            "config_id": key[2], "train_n": len(tr), "validation_n": len(va),
            "train_mean": tr.net_pct.mean(), "validation_mean": va.net_pct.mean(),
            "train_lcb": tr_lcb, "validation_lcb": va_lcb,
            "train_pf": safe_pf(tr.net_pct), "validation_pf": safe_pf(va.net_pct),
            "objective": objective,
        })
    table = pd.DataFrame(rows)
    if table.empty:
        default = f"T1_S1_H{p3.TIMEFRAMES[tf]['horizon']}"
        return default, table
    eligible = table[(table.train_mean > 0) & (table.validation_mean > 0) & (table.train_pf >= 1) & (table.validation_pf >= 1)]
    chosen = (eligible if not eligible.empty else table).sort_values(["objective", "validation_n"], ascending=False).iloc[0]
    return str(chosen.config_id), table.sort_values("objective", ascending=False)


@dataclass
class WOEModel:
    global_log_odds: float
    contributions: dict[str, dict[str, float]]
    scale: float = 0.60

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        score = np.full(len(frame), self.global_log_odds, dtype=float)
        for feature, mapping in self.contributions.items():
            score += frame[feature].astype(str).map(mapping).fillna(0.0).to_numpy() * self.scale
        return np.asarray(sigmoid(score), dtype=float)


def fit_woe(frame: pd.DataFrame, label_col: str = "positive") -> WOEModel:
    y = frame[label_col].astype(int)
    wins, losses = int(y.sum()), int(len(y) - y.sum())
    global_log = math.log((wins + 2.0) / (losses + 2.0))
    contrib: dict[str, dict[str, float]] = {}
    for feature in FEATURES:
        mapping: dict[str, float] = {}
        for value, g in frame.groupby(feature, dropna=False):
            n = len(g)
            w = int(g[label_col].sum())
            l = n - w
            local = math.log((w + 2.0) / (l + 2.0))
            shrink = n / (n + 50.0)
            mapping[str(value)] = float(np.clip(shrink * (local - global_log), -0.90, 0.90))
        contrib[feature] = mapping
    return WOEModel(global_log, contrib)


def threshold_candidates(pred: np.ndarray) -> list[float]:
    fixed = [0.50, 0.525, 0.55, 0.575, 0.60, 0.625, 0.65, 0.675, 0.70, 0.725, 0.75]
    quantiles = [float(x) for x in np.quantile(pred, [0.50, 0.60, 0.70, 0.80, 0.90]) if np.isfinite(x)] if len(pred) else []
    return sorted(set(round(x, 4) for x in fixed + quantiles if 0.48 <= x <= 0.85))


def choose_threshold(validation: pd.DataFrame, pred: np.ndarray, tf: str) -> tuple[float, pd.DataFrame]:
    z = validation.copy()
    z["prob"] = pred
    min_n = {"1h": 30, "4h": 16, "12h": 7, "1d": 3}[tf]
    rows = []
    for threshold in threshold_candidates(pred):
        selected = z[z.prob >= threshold]
        if len(selected) < min_n:
            continue
        m = metrics(selected)
        lcb = mean_lcb(selected.net_pct)
        objective = lcb + 0.10 * m["mean_net_pct"] + 0.002 * min(m["n"], 100) + 0.01 * m["max_drawdown_pct"]
        rows.append({"threshold": threshold, **m, "lcb": lcb, "objective": objective})
    table = pd.DataFrame(rows)
    if table.empty:
        return 0.50, table
    eligible = table[(table.mean_net_pct > 0) & (table.profit_factor >= 1)]
    chosen = (eligible if not eligible.empty else table).sort_values(["objective", "n"], ascending=False).iloc[0]
    return float(chosen.threshold), table.sort_values("objective", ascending=False)


def attach_simulation(events: pd.DataFrame, sim: pd.DataFrame) -> pd.DataFrame:
    cols = ["event_id", "exit_time", "outcome", "holding_bars", "net_pct", "config_id"]
    z = events.merge(sim[cols], on="event_id", how="inner")
    z["positive"] = (z.net_pct > 0).astype(int)
    return z


def fold_score(events: pd.DataFrame, cache: dict, tf: str, side: str, fold: dict) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config_id, config_table = choose_config(events, cache, tf, side, fold)
    sim = cache.get((tf, side, config_id), pd.DataFrame())
    if sim.empty:
        return pd.DataFrame(), {}, config_table, pd.DataFrame(), pd.DataFrame()
    z = attach_simulation(events[(events.timeframe == tf) & (events.side == side)], sim)
    train = z[period_mask(z.signal_time, fold["train_start"], fold["train_end"])].copy()
    validation = z[period_mask(z.signal_time, fold["validation_start"], fold["validation_end"])].copy()
    test = z[period_mask(z.signal_time, fold["test_start"], fold["test_end"])].copy()
    if len(train) < 20 or validation.empty or test.empty:
        return pd.DataFrame(), {}, config_table, pd.DataFrame(), pd.DataFrame()
