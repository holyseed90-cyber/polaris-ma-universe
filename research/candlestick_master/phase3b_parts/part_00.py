#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 3B

Tests objective hypotheses extracted from the 2011 Bondweb/동양종합금융증권
technical-analysis curriculum.  The source is treated as a hypothesis generator;
all conclusions come from BTCUSDT data with train/validation/test separation.
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
OUT = Path("research/candlestick_master/output_phase3b")
OUT.mkdir(parents=True, exist_ok=True)

OLD_MAS = [3, 7, 14, 28, 56]
POLARIS_MAS = [5, 10, 20, 60, 112, 224, 448, 896]
ALL_MAS = sorted(set(OLD_MAS + POLARIS_MAS))
TF = {
    "1h": {"rule": None, "hours": 1, "ret_h": 24, "ladder_h": 168, "touch_sep": 8},
    "4h": {"rule": "4h", "hours": 4, "ret_h": 6, "ladder_h": 42, "touch_sep": 4},
    "12h": {"rule": "12h", "hours": 12, "ret_h": 6, "ladder_h": 14, "touch_sep": 3},
    "1d": {"rule": "1D", "hours": 24, "ret_h": 7, "ladder_h": 14, "touch_sep": 3},
}
SPLITS = {
    "train": (pd.Timestamp("2018-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
    "validation": (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")),
    "test": (pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}


def download_source() -> Path:
    cache = Path("research/candlestick_master/.cache/BTCUSDT_binance_hourly_2018-2026.csv.gz")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 1_000_000:
        return cache
    with requests.get(SOURCE_URL, timeout=180, stream=True) as r:
        r.raise_for_status()
        with cache.open("wb") as fh:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    return cache


def load_hourly(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, compression="gzip")
    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    aliases = {"date_time": "timestamp", "datetime": "timestamp", "date": "timestamp", "time": "timestamp", "open_time": "timestamp", "unix": "timestamp", "vol": "volume", "volume_btc": "volume", "volume_(btc)": "volume"}
    raw = raw.rename(columns={k: v for k, v in aliases.items() if k in raw.columns})
    if "timestamp" not in raw.columns:
        raw = raw.rename(columns={raw.columns[0]: "timestamp"})
    ts = raw.timestamp
    if pd.api.types.is_numeric_dtype(ts):
        med = float(pd.to_numeric(ts, errors="coerce").dropna().median())
        raw["timestamp"] = pd.to_datetime(ts, unit="ms" if med > 1e10 else "s", utc=True, errors="coerce")
    else:
        raw["timestamp"] = pd.to_datetime(ts, utc=True, errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        if c not in raw.columns:
            raw[c] = 0.0 if c == "volume" else np.nan
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    x = raw[["timestamp", "open", "high", "low", "close", "volume"]].dropna(subset=["timestamp", "open", "high", "low", "close"])
    return x.drop_duplicates("timestamp", keep="last").sort_values("timestamp").set_index("timestamp").loc["2018-01-01":]


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, origin="epoch", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open", "high", "low", "close"])


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    g, l = d.clip(lower=0), (-d).clip(lower=0)
    ag = g.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    al = l.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + ag / al.replace(0, np.nan))


def atr_wilder(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df.close.shift(1)
    tr = pd.concat([(df.high - df.low), (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def enrich(df: pd.DataFrame, hours: int) -> pd.DataFrame:
    x = df.copy()
    x["signal_time"] = x.index + pd.to_timedelta(hours, unit="h")
    x["atr14"] = atr_wilder(x)
    x["atr_pct"] = x.atr14 / x.close * 100
    x["rsi14"] = rsi_wilder(x.close)
    x["body"] = (x.close - x.open).abs()
    x["range"] = x.high - x.low
    x["body_avg14_prior"] = x.body.shift(1).rolling(14, min_periods=14).mean()
    x["body_multiple"] = x.body / x.body_avg14_prior.replace(0, np.nan)
    x["upper_wick"] = x.high - x[["open", "close"]].max(axis=1)
    x["lower_wick"] = x[["open", "close"]].min(axis=1) - x.low
    x["close_loc"] = (x.close - x.low) / x.range.replace(0, np.nan)
    x["bull"] = x.close > x.open
    x["bear"] = x.close < x.open
    for p in ALL_MAS:
        ma = x.close.rolling(p, min_periods=p).mean()
        x[f"ma{p}"] = ma
        x[f"ma{p}_s5"] = (ma / ma.shift(5) - 1) * 100
        x[f"ma{p}_s20"] = (ma / ma.shift(20) - 1) * 100
        x[f"ma{p}_acc"] = x[f"ma{p}_s5"] - x[f"ma{p}_s5"].shift(5)
        x[f"d_ma{p}_atr"] = (x.close - ma) / x.atr14
    x["old_spread_atr"] = (x[[f"ma{p}" for p in OLD_MAS]].max(axis=1) - x[[f"ma{p}" for p in OLD_MAS]].min(axis=1)) / x.atr14
    x["polaris_spread_atr"] = (x[[f"ma{p}" for p in POLARIS_MAS]].max(axis=1) - x[[f"ma{p}" for p in POLARIS_MAS]].min(axis=1)) / x.atr14
    x["above_old"] = pd.concat([(x.close > x[f"ma{p}"]) for p in OLD_MAS], axis=1).sum(axis=1)
    x["above_polaris"] = pd.concat([(x.close > x[f"ma{p}"]) for p in POLARIS_MAS], axis=1).sum(axis=1)
    x["old_bull_stack"] = (x.ma3 > x.ma7) & (x.ma7 > x.ma14) & (x.ma14 > x.ma28) & (x.ma28 > x.ma56)
    x["old_bear_stack"] = (x.ma3 < x.ma7) & (x.ma7 < x.ma14) & (x.ma14 < x.ma28) & (x.ma28 < x.ma56)
    x["polaris_long_bull"] = (x.ma224 > x.ma448) & (x.ma448 > x.ma896)
    x["polaris_long_bear"] = (x.ma224 < x.ma448) & (x.ma448 < x.ma896)
    h = TF[[k for k, v in TF.items() if v["hours"] == hours][0]]["ret_h"]
    x[f"ret_{h}"] = (x.close.shift(-h) / x.close - 1) * 100
    future_hi = pd.concat([x.high.shift(-i) for i in range(1, h + 1)], axis=1).max(axis=1)
    future_lo = pd.concat([x.low.shift(-i) for i in range(1, h + 1)], axis=1).min(axis=1)
    x[f"mfe_{h}"] = (future_hi - x.close) / x.atr14
    x[f"mae_{h}"] = (future_lo - x.close) / x.atr14
    return x
