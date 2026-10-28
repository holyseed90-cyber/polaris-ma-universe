#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 2

Reproducible sequence mining and first-passage validation over Binance BTCUSDT
hourly candles (2018-present).  No future information is used in signal features.

Outputs are written to research/candlestick_master/output_phase2/.
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

SOURCE_URL = (
    "https://raw.githubusercontent.com/alessiostomeo/"
    "btc-cycle-data/main/binance/1h/BTCUSDT_binance_hourly_2018-2026.csv.gz"
)
OUT = Path("research/candlestick_master/output_phase2")
OUT.mkdir(parents=True, exist_ok=True)

MA_PERIODS = [5, 10, 20, 60, 112, 224, 448, 896]
TF_RULES = {
    "1h": {"rule": None, "period_hours": 1, "horizons": [6, 12, 24, 72], "rank_h": 24, "min_train": 70, "min_test": 20},
    "4h": {"rule": "4h", "period_hours": 4, "horizons": [3, 6, 18, 42], "rank_h": 6, "min_train": 35, "min_test": 10},
    "12h": {"rule": "12h", "period_hours": 12, "horizons": [2, 6, 14], "rank_h": 6, "min_train": 22, "min_test": 7},
    "1d": {"rule": "1D", "period_hours": 24, "horizons": [3, 7, 14, 30], "rank_h": 7, "min_train": 14, "min_test": 6},
}
SPLITS = {
    "train": (pd.Timestamp("2018-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
    "validation": (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")),
    "test": (pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}
RNG = np.random.default_rng(20261028)


def download_source() -> Path:
    cache = Path("research/candlestick_master/.cache/BTCUSDT_binance_hourly_2018-2026.csv.gz")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 1_000_000:
        return cache
    with requests.get(SOURCE_URL, timeout=120, stream=True) as response:
        response.raise_for_status()
        with cache.open("wb") as fh:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    return cache


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
        # Some public OHLC files keep the timestamp as the first unnamed column.
        first = raw.columns[0]
        raw = raw.rename(columns={first: "timestamp"})
    ts = raw["timestamp"]
    if pd.api.types.is_numeric_dtype(ts):
        unit = "ms" if float(pd.to_numeric(ts, errors="coerce").dropna().median()) > 10_000_000_000 else "s"
        raw["timestamp"] = pd.to_datetime(ts, unit=unit, utc=True, errors="coerce")
    else:
        raw["timestamp"] = pd.to_datetime(ts, utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in raw.columns:
            if col == "volume":
                raw[col] = 0.0
            else:
                raise ValueError(f"Missing required column: {col}; columns={raw.columns.tolist()}")
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    out = raw[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").set_index("timestamp")
    out = out.loc[out.index >= pd.Timestamp("2018-01-01", tz="UTC")]
    return out


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        df.resample(rule, origin="epoch", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
    )


def wilder_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
