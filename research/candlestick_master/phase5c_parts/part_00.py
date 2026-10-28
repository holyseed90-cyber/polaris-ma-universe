#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 5C indicator-increment audit.

Goal
----
Measure whether indicator families not already central to the Phase 5B engine
(Ichimoku, DMI/ADX, Bollinger/Keltner volatility state, money-flow/volume,
SuperTrend/PSAR, MACD/Stochastic) improve *out-of-sample* target-hit rate and
net expectancy after costs.  The study uses Binance perpetual as the execution
venue, Binance spot as same-close confirmation, and preserves the Phase 5B
no-look-ahead entry/outcome rules.

This is an indicator ablation study, not a promise of trading performance.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
P5_PATH = ROOT / "candle_master_phase5b.py"
spec = importlib.util.spec_from_file_location("phase5b", P5_PATH)
p5 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(p5)

OUT = ROOT / "output_phase5c"
OUT.mkdir(parents=True, exist_ok=True)
PRIMARY = p5.PRIMARY
SPOT = p5.SPOT
RNG = np.random.default_rng(20261029)
MAIN_COST = 30
STRESS_COST = 50

# Promotion configurations exclude quarter-ATR diagnostic targets.  Quarter-ATR
# rows are still reported separately as a win-rate ceiling diagnostic.
PROMOTION_CONFIGS = {
    "4h": ["P05_S10_H6", "P075_S10_H8", "P10_S10_H8"],
    "1d": ["P05_S10_H3", "P075_S10_H5", "P10_S10_H7"],
}
DIAGNOSTIC_CONFIGS = {"4h": ["P025_S10_H6"], "1d": ["P025_S10_H3"]}

FAMILY_MAP = {
    "ichimoku": ["i_ichi_cloud", "i_ichi_full", "i_ichi_kijun", "i_ichi_break_recent"],
    "dmi_adx": ["i_dmi_align", "i_adx20", "i_adx25_rising"],
    "volatility": ["i_bb_trend", "i_bb_squeeze_release", "i_chop_trend"],
    "money_flow": ["i_cmf05", "i_cmf_rising", "i_obv_slope", "i_mfi_align", "i_vwma_align"],
    "trend_follow": ["i_supertrend", "i_psar"],
    "momentum": ["i_macd", "i_stoch"],
    "spot_confirmation": ["i_spot_ichi", "i_spot_dmi", "i_spot_cmf", "i_spot_vwma"],
}
FEATURE_TO_FAMILY = {feature: family for family, features in FAMILY_MAP.items() for feature in features}


def utc(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def wilder(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def true_range(x: pd.DataFrame) -> pd.Series:
    prev = x.close.shift(1)
    return pd.concat([(x.high - x.low), (x.high - prev).abs(), (x.low - prev).abs()], axis=1).max(axis=1)


def dmi(x: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = x.high.diff()
    down = -x.low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=x.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=x.index)
    atr = wilder(true_range(x), n)
    plus_di = 100 * wilder(plus_dm, n) / atr.replace(0, np.nan)
    minus_di = 100 * wilder(minus_dm, n) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = wilder(dx, n)
    return plus_di, minus_di, adx


def supertrend_state(x: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.Series:
    atr = wilder(true_range(x), n)
    hl2 = (x.high + x.low) / 2
    basic_upper = hl2 + mult * atr
    basic_lower = hl2 - mult * atr
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    state = pd.Series(index=x.index, dtype="float64")
    if len(x) == 0:
        return state
    state.iloc[0] = 1.0
    for i in range(1, len(x)):
        pu = final_upper.iloc[i - 1]
        pl = final_lower.iloc[i - 1]
        final_upper.iloc[i] = basic_upper.iloc[i] if (basic_upper.iloc[i] < pu or x.close.iloc[i - 1] > pu) else pu
        final_lower.iloc[i] = basic_lower.iloc[i] if (basic_lower.iloc[i] > pl or x.close.iloc[i - 1] < pl) else pl
        prev_state = state.iloc[i - 1]
        if prev_state > 0 and x.close.iloc[i] < final_lower.iloc[i]:
            state.iloc[i] = -1.0
        elif prev_state < 0 and x.close.iloc[i] > final_upper.iloc[i]:
            state.iloc[i] = 1.0
        else:
            state.iloc[i] = prev_state
    return state


def psar_state(x: pd.DataFrame, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    n = len(x)
    out = pd.Series(index=x.index, dtype="float64")
    if n < 3:
        return out
    bull = bool(x.close.iloc[1] >= x.close.iloc[0])
    af = step
    ep = x.high.iloc[:2].max() if bull else x.low.iloc[:2].min()
    sar = x.low.iloc[:2].min() if bull else x.high.iloc[:2].max()
    out.iloc[:2] = 1.0 if bull else -1.0
    for i in range(2, 