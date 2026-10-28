#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 3C.

Precision tests for:
1) next-MA ladder probability by ATR distance,
2) independent touch defense decay,
3) linear-regression MA slope/acceleration/curvature,
4) support migration from longer to shorter averages,
5) 3x-body candle confirmation structure.

The 2011 Bondweb curriculum and the uploaded technical-analysis atlas are treated
as hypothesis sources, not proof.  All results use BTCUSDT data with fixed
train/validation/untouched-test splits and candle-close-only information.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from candle_master_phase3b import (
    TF, SPLITS, ALL_MAS, POLARIS_MAS, download_source, load_hourly, resample,
    enrich, ladder_first_passage, independent_touch_ordinals, dedupe_positions,
    wilson,
)

OUT = Path("research/candlestick_master/output_phase3c")
OUT.mkdir(parents=True, exist_ok=True)

STUDY_MAS = [14, 28, 56, 112, 224, 448, 896]
LADDER_PAIRS = [(14, 28), (28, 56), (112, 224), (224, 448), (448, 896)]
GAP_LABELS = ["lt1", "1to2", "2to3", "3to4", "ge4"]
GAP_BINS = [-np.inf, 1, 2, 3, 4, np.inf]


def build_frames() -> dict[str, pd.DataFrame]:
    hourly = load_hourly(download_source())
    raws = {"1h": hourly}
    for tf, cfg in TF.items():
        if tf != "1h":
            raws[tf] = resample(hourly, cfg["rule"])
    return {tf: add_lr_features(enrich(raw, TF[tf]["hours"])) for tf, raw in raws.items()}


def rolling_lr_slope(series: pd.Series, window: int) -> pd.Series:
    xx = np.arange(window, dtype=float)
    xc = xx - xx.mean()
    den = float(np.dot(xc, xc))
    return series.rolling(window, min_periods=window).apply(lambda y: float(np.dot(y, xc) / den), raw=True)


def add_lr_features(x: pd.DataFrame) -> pd.DataFrame:
    y = x.copy()
    for p in STUDY_MAS:
        for w in (10, 20, 40):
            y[f"ma{p}_lr{w}"] = rolling_lr_slope(y[f"ma{p}"], w) / y.atr14
        y[f"ma{p}_lr_acc5"] = y[f"ma{p}_lr20"] - y[f"ma{p}_lr20"].shift(5)
        y[f"ma{p}_curve5"] = y[f"ma{p}"].diff().diff().rolling(5, min_periods=5).mean() / y.atr14
    return y


def split_name(ts: pd.Timestamp) -> str | None:
    for name, (start, end) in SPLITS.items():
        if start <= ts < end:
            return name
    return None


def summarize_binary(events: pd.DataFrame, outcome_col: str, positive_value: str) -> dict:
    decided = events[events[outcome_col].isin([positive_value, "cancel", "break"])].copy()
    n = len(decided)
    wins = int((decided[outcome_col] == positive_value).sum())
    lo, hi = wilson(wins, n)
    return {
        "events": int(len(events)), "decided": n, "wins": wins,
        "rate": wins / n if n else np.nan, "wilson_low": lo, "wilson_high": hi,
        "median_bars": float(decided.bars.median()) if n and "bars" in decided else np.nan,
    }


def ma_ladder_by_distance(tf: str, x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_rows, summary_rows = [], []
    horizon = TF[tf]["ladder_h"]
    for short, long in LADDER_PAIRS:
        for direction in ("down", "up"):
            z = ladder_first_passage(x, short, long, direction, horizon)
            if z.empty:
                continue
            z["timeframe"] = tf
            z["gap_bin"] = pd.cut(z.gap_atr, GAP_BINS, labels=GAP_LABELS, right=False).astype("string")
            z["rsi_bin"] = pd.cut(z.rsi14, [-np.inf, 30, 40, 50, 60, 70, np.inf], labels=["lt30", "30to40", "40to50", "50to60", "60to70", "ge70"], right=False).astype("string")
            z["split"] = z.signal_time.map(split_name)
            raw_rows.append(z)
            for split in SPLITS:
                zz = z[z.split == split]
                for gap_bin in GAP_LABELS:
                    g = zz[zz.gap_bin == gap_bin]
                    decided = g[g.outcome.isin(["target_next_ma", "reclaim_short_ma"])]
                    n = len(decided)
                    wins = int((decided.outcome == "target_next_ma").sum())
                    lo, hi = wilson(wins, n)
                    summary_rows.append({
                        "timeframe": tf, "short_ma": short, "long_ma": long,
                        "direction": direction, "split": split, "gap_bin": gap_bin,
                        "events": len(g), "decided": n, "target_first": wins,
                        "target_rate": wins / n if n else np.nan,
                        "wilson_low": lo, "wilson_high": hi,
                        "median_bars": float(decided.bars.median()) if n else np.nan,
                        "median_gap_atr": float(g.gap_atr.median()) if len(g) else np.nan,
                    })
    return (
        pd.concat(raw_rows, ignore_index=True) if raw_rows else pd.DataFrame(),
        pd.DataFrame(summary_rows),
    )
