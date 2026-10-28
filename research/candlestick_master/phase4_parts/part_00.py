#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 4.

Interpretable composite score, nested expanding-window walk-forward selection,
multiple target/stop/holding grids, score calibration, multiple-testing audit,
and strict no-overlap portfolio checks.

This module imports Phase 3D's official-exchange data loaders and causal feature
builders.  Every event feature is known at signal-candle close; entries use the
next bar open.  No incomplete higher-timeframe candle is used.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

import candle_master_phase3d as p3

OUT = Path("research/candlestick_master/output_phase4")
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = [0.75, 1.0, 1.5, 2.0]
STOPS = [0.75, 1.0, 1.25]
HOLD_GRID = {
    "1h": [12, 24, 48],
    "4h": [3, 6, 12],
    "12h": [3, 6, 10],
    "1d": [3, 7, 14],
}
FOLDS = [
    {"fold": "WF2023", "train_start": "2018-01-01", "train_end": "2022-01-01", "validation_start": "2022-01-01", "validation_end": "2023-01-01", "test_start": "2023-01-01", "test_end": "2024-01-01"},
    {"fold": "WF2024", "train_start": "2018-01-01", "train_end": "2023-01-01", "validation_start": "2023-01-01", "validation_end": "2024-01-01", "test_start": "2024-01-01", "test_end": "2025-01-01"},
    {"fold": "WF2025", "train_start": "2018-01-01", "train_end": "2024-01-01", "validation_start": "2024-01-01", "validation_end": "2025-01-01", "test_start": "2025-01-01", "test_end": "2026-01-01"},
    {"fold": "WF2026", "train_start": "2018-01-01", "train_end": "2025-01-01", "validation_start": "2025-01-01", "validation_end": "2026-01-01", "test_start": "2026-01-01", "test_end": "2027-01-01"},
]
FEATURES = [
    "rule", "kill_zone", "rsi_bin", "atr_state", "above_bin",
    "slope_bin", "long_state", "target_gap_bin", "consensus_bin",
    "htf_align_bin",
]
COST_BPS = 20
RNG = np.random.default_rng(20261029)


def utc(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def categorical_bin(value: float, cuts: list[float], labels: list[str]) -> str:
    if not np.isfinite(value):
        return "na"
    for cut, label in zip(cuts, labels):
        if value < cut:
            return label
    return labels[-1]


def rsi_bin(value: float) -> str:
    return categorical_bin(value, [30, 40, 50, 60, 70, np.inf], ["lt30", "30_40", "40_50", "50_60", "60_70", "ge70"])


def above_bin(value: float) -> str:
    return categorical_bin(value, [2, 4, 6, np.inf], ["0_1", "2_3", "4_5", "6_8"])


def count_bin(value: float) -> str:
    return categorical_bin(value, [2, 3, 4, np.inf], ["one", "two", "three", "four"])


def target_gap_bin(value: float) -> str:
    return categorical_bin(value, [1, 2, 3, 4, np.inf], ["lt1", "1to2", "2to3", "3to4", "ge4"])


def atr_state(value: float) -> str:
    return categorical_bin(value, [0.80, 1.20, np.inf], ["low", "normal", "high"])


def slope_bin(value: float) -> str:
    return categorical_bin(value, [2, 4, 6, np.inf], ["weak", "mixed", "strong", "all"])


def safe_pf(values: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna()
    gp = float(v[v > 0].sum())
    gl = float(-v[v <= 0].sum())
    return gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan)


def max_drawdown(values: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if v.empty:
        return np.nan
    eq = (1 + v / 100).cumprod()
    return float((eq / eq.cummax() - 1).min() * 100)


def metrics(z: pd.DataFrame, col: str = "net_pct") -> dict:
    if z.empty:
        return {"n": 0, "win_rate": np.nan, "mean_net_pct": np.nan, "median_net_pct": np.nan, "profit_factor": np.nan, "max_drawdown_pct": np.nan, "max_losing_streak": 0}
