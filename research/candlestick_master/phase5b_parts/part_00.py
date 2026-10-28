#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 5B precision-rule research.

Purpose
-------
Search for genuinely rare, high-precision BTC swing signals without manufacturing a
90% win rate.  Binance perpetual is the execution/outcome venue; Binance spot and
independent USD venues are used only as causal confirmation.  The script implements
source-derived hypotheses (market structure, Spring/Upthrust, S/R flip, FVG,
rejection blocks, order-block retests, range contraction/expansion, moving-average
location/spacing) as explicit, auditable rules and then subjects them to nested
walk-forward, cost stress, multiple-testing correction and block bootstrap.

The output is research evidence, not a promise of future returns.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
P3_PATH = ROOT / "candle_master_phase3d.py"
spec = importlib.util.spec_from_file_location("phase3d", P3_PATH)
p3 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(p3)

OUT = ROOT / "output_phase5b"
OUT.mkdir(parents=True, exist_ok=True)

PRIMARY = "binance_perp"
SPOT = "binance_spot"
TF_INFO = {
    "4h": {"rule": "4h", "hours": 4, "pivot_right": 3},
    "1d": {"rule": "1D", "hours": 24, "pivot_right": 2},
}
CONTEXT_TFS = {
    "12h": {"rule": "12h", "hours": 12, "pivot_right": 2},
    "1d": {"rule": "1D", "hours": 24, "pivot_right": 2},
}
# Pre-registered precision configurations.  Quarter-ATR targets are included only
# to measure the win-rate ceiling and must still pass 50-bps expectancy/PF gates.
CONFIGS = {
    "4h": [
        {"config_id": "P025_S10_H6", "target": 0.25, "stop": 1.00, "hold": 6},
        {"config_id": "P025_S125_H6", "target": 0.25, "stop": 1.25, "hold": 6},
        {"config_id": "P05_S10_H6", "target": 0.50, "stop": 1.00, "hold": 6},
        {"config_id": "P05_S125_H6", "target": 0.50, "stop": 1.25, "hold": 6},
        {"config_id": "P075_S10_H8", "target": 0.75, "stop": 1.00, "hold": 8},
        {"config_id": "P10_S10_H8", "target": 1.00, "stop": 1.00, "hold": 8},
    ],
    "1d": [
        {"config_id": "P025_S10_H3", "target": 0.25, "stop": 1.00, "hold": 3},
        {"config_id": "P025_S125_H3", "target": 0.25, "stop": 1.25, "hold": 3},
        {"config_id": "P05_S10_H3", "target": 0.50, "stop": 1.00, "hold": 3},
        {"config_id": "P05_S125_H3", "target": 0.50, "stop": 1.25, "hold": 3},
        {"config_id": "P075_S10_H5", "target": 0.75, "stop": 1.00, "hold": 5},
        {"config_id": "P10_S10_H7", "target": 1.00, "stop": 1.00, "hold": 7},
    ],
}
COST_BPS = [20, 30, 50]
MAIN_COST = 30
FOLDS = [
    {"fold": "WF2023", "train_start": "2020-01-01", "train_end": "2022-01-01", "validation_start": "2022-01-01", "validation_end": "2023-01-01", "test_start": "2023-01-01", "test_end": "2024-01-01"},
    {"fold": "WF2024", "train_start": "2020-01-01", "train_end": "2023-01-01", "validation_start": "2023-01-01", "validation_end": "2024-01-01", "test_start": "2024-01-01", "test_end": "2025-01-01"},
    {"fold": "WF2025", "train_start": "2020-01-01", "train_end": "2024-01-01", "validation_start": "2024-01-01", "validation_end": "2025-01-01", "test_start": "2025-01-01", "test_end": "2026-01-01"},
    {"fold": "WF2026", "train_start": "2020-01-01", "train_end": "2025-01-01", "validation_start": "2025-01-01", "validation_end": "2026-01-01", "test_start": "2026-01-01", "test_end": "2027-01-01"},
]
RNG = np.random.default_rng(20261029)


def utc(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def safe_div(a: pd.Series | np.ndarray | float, b: pd.Series | np.ndarray | float):
    return np.divide(a, b, out=np.full_like(np.asarray(a, dtype=float), np.nan), where=np.asarray(b) != 0)


def wilson(success: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
