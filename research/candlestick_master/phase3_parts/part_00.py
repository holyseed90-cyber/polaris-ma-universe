#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 3A: market structure and liquidity.

Research questions:
- Do confirmed pivot sweeps (SFP/Spring/Upthrust) carry out-of-sample edge?
- Does BoS/CHoCH plus retest improve directional expectancy?
- Which MA zones (112/224/448/896) act as independent wave-touch support/resistance?
- Do FVG creation/fill and range contraction→expansion improve timing?

All signals use only data available at the signal candle close. Confirmed pivots become
available only after `right` candles have closed. Higher-timeframe candles are never used
before close. Results are split into train/validation/test and overlapping events are
removed before scoring.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

SOURCE_URL = (
    "https://raw.githubusercontent.com/alessiostomeo/"
    "btc-cycle-data/main/binance/1h/BTCUSDT_binance_hourly_2018-2026.csv.gz"
)
ROOT = Path("research/candlestick_master")
OUT = ROOT / "output_phase3"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = ROOT / ".cache/BTCUSDT_binance_hourly_2018-2026.csv.gz"

MA_PERIODS = [5, 10, 20, 60, 112, 224, 448, 896]
TF_CONFIG = {
    "1h": {"rule": None, "hours": 1, "horizon": 24, "pivot": 3, "min_test": 25},
    "4h": {"rule": "4h", "hours": 4, "horizon": 12, "pivot": 3, "min_test": 12},
    "12h": {"rule": "12h", "hours": 12, "horizon": 6, "pivot": 2, "min_test": 8},
    "1d": {"rule": "1D", "hours": 24, "horizon": 7, "pivot": 2, "min_test": 6},
}
SPLITS = {
    "train": (pd.Timestamp("2018-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
    "validation": (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")),
    "test": (pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}
RNG = np.random.default_rng(20261029)


def download_source() -> Path:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists() and CACHE.stat().st_size > 1_000_000:
        return CACHE
    with requests.get(SOURCE_URL, timeout=180, stream=True) as r:
        r.raise_for_status()
        with CACHE.open("wb") as fh:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    return CACHE


def normalize_source(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, compression="gzip")
    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    aliases = {
        "date_time": "timestamp", "datetime": "timestamp", "date": "timestamp",
        "time": "timestamp", "open_time": "timestamp", "unix": "timestamp",
        "vol": "volume", "volume_btc": "volume", "volume_(btc)": "volume",
    }
    raw = raw.rename(columns={k: v for k, v in aliases.items() if k in raw.columns})
    if "timestamp" not in raw.columns:
        raw = raw.rename(columns={raw.columns[0]: "timestamp"})
    ts = raw["timestamp"]
    if pd.api.types.is_numeric_dtype(ts):
