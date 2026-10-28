#!/usr/bin/env python3
"""BTC Candlestick Master — Phase 3D.

Cross-venue, spot/perpetual, session, transaction-cost and live-data extension
for rules that survived earlier phases.  Data is downloaded from official
exchange endpoints or Binance's official public data archive.
"""
from __future__ import annotations

import io
import json
import math
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import requests

OUT = Path("research/candlestick_master/output_phase3d")
OUT.mkdir(parents=True, exist_ok=True)
CACHE = Path("research/candlestick_master/.cache/phase3d")
CACHE.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("2018-01-01", tz="UTC")
NOW = pd.Timestamp.now(tz="UTC").floor("h")
MAS = [5, 10, 14, 20, 28, 56, 60, 112, 224, 448, 896]
TIMEFRAMES = {
    "1h": {"rule": None, "hours": 1, "horizon": 24},
    "4h": {"rule": "4h", "hours": 4, "horizon": 6},
    "12h": {"rule": "12h", "hours": 12, "horizon": 6},
    "1d": {"rule": "1D", "hours": 24, "horizon": 7},
}
SPLITS = {
    "train": (pd.Timestamp("2018-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
    "validation": (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")),
    "test": (pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}
COST_BPS = [0, 10, 20, 30]
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "BTC-Candlestick-Research/1.0"})


def get_with_retry(url: str, params: dict | None = None, timeout: int = 60, attempts: int = 6) -> requests.Response:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                time.sleep(min(20, 1.5 ** attempt))
                continue
            if r.status_code in (404, 451):
                return r
            r.raise_for_status()
            return r
        except Exception as exc:  # network retry only
            last = exc
            time.sleep(min(20, 1.5 ** attempt))
    raise RuntimeError(f"GET failed after {attempts} attempts: {url}; {last}")


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["open", "high", "low", "close", "volume"]
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("OHLCV frame index must be DatetimeIndex")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    out = df[cols].replace([np.inf, -np.inf], np.nan).dropna(subset=["open", "high", "low", "close"])
    out["volume"] = out.volume.fillna(0.0)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out[(out.high >= out[["open", "close", "low"]].max(axis=1)) & (out.low <= out[["open", "close", "high"]].min(axis=1))]
    return out.loc[out.index >= START]


def parse_binance_zip(content: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = pd.read_csv(zf.open(name), header=None)
    if raw.shape[1] < 6:
        raise ValueError("Unexpected Binance archive layout")
    ts = pd.to_numeric(raw.iloc[:, 0], errors="coerce")
    unit = "us" if ts.dropna().median() > 1e14 else "ms"
    idx = pd.to_datetime(ts, unit=unit, utc=True, errors="coerce")
    out = pd.DataFrame(
        {
            "open": raw.iloc[:, 1].to_numpy(),
            "high": raw.iloc[:, 2].to_numpy(),
            "low": raw.iloc[:, 3].to_numpy(),
            "close": raw.iloc[:, 4].to_numpy(),
            "volume": raw.iloc[:, 5].to_numpy(),
        },
        index=idx,
    )
    return normalize(out)


def fetch_binance_vision(kind: str) -> pd.DataFrame:
    if kind not in {"spot", "perp"}:
        raise ValueError(kind)
    start = pd.Timestamp("2018-01-01", tz="UTC") if kind == "spot" else pd.Timestamp("2019-09-01", tz="UTC")
    stem = "spot" if kind == "spot" else "futures/um"
    frames: list[pd.DataFrame] = []
    current_month = NOW.to_period("M").start_time.tz_localize("UTC")
    month = start.to_period("M")
    last_complete = (current_month - pd.Timedelta(days=1)).to_period("M")
    while month <= last_complete:
        ym = f"{month.year:04d}-{month.month:02d}"
        url = f"https://data.binance.vision/data/{stem}/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-{ym}.zip"
        r = get_with_retry(url)
        if r.status_code == 200:
            frames.append(parse_binance_zip(r.content))
        month += 1
    day = current_month
    yesterday = NOW.normalize() - pd.Timedelta(days=1)
    while day <= yesterday:
        ds = day.strftime("%Y-%m-%d")
        url = f"https://data.binance.vision/data/{stem}/daily/klines/BTCUSDT/1h/BTCUSDT-1h-{ds}.zip"
        r = get_with_retry(url)
        if r.status_code == 200:
            frames.append(parse_binance_zip(r.content))
        day += pd.Timedelta(days=1)
    if not frames:
        raise RuntimeError(f"No Binance {kind} archives downloaded")
    return normalize(pd.concat(frames))


def fetch_coinbase() -> pd.DataFrame:
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    frames: list[pd.DataFrame] = []
    start = START
    while start < NOW:
        end = min(start + pd.Timedelta(hours=299), NOW)
        params = {
            "granularity": 3600,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
        }
        r = get_with_retry(url, params=params)
        data = r.json()
        if isinstance(data, list) and data:
            raw = pd.DataFrame(data, columns=["time", "low", "high", "open", "close", "volume"])
            raw.index = pd.to_datetime(raw.pop("time"), unit="s", utc=True)
            frames.append(normalize(raw))
        start = end + pd.Timedelta(hours=1)
        time.sleep(0.08)
    if not frames:
        raise RuntimeError("No Coinbase candles downloaded")
    return normalize(pd.concat(frames))


def fetch_bitstamp() -> pd.DataFrame:
    url = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
    frames: list[pd.DataFrame] = []
    start = START
    while start < NOW:
        end = min(start + pd.Timedelta(hours=999), NOW)
        params = {
            "step": 3600,
            "limit": 1000,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "exclude_current_candle": "true",
        }
        r = get_with_retry(url, params=params)
        payload = r.json()
        rows = payload.get("data", {}).get("ohlc", [])
        if rows:
            raw = pd.DataFrame(rows)
            raw.index = pd.to_datetime(pd.to_numeric(raw.pop("timestamp"), errors="coerce"), unit="s", utc=True)
            frames.append(normalize(raw.rename(columns={"volume": "volume"})))
        start = end + pd.Timedelta(hours=1)
        time.sleep(0.03)
    if not frames:
        raise RuntimeError("No Bitstamp candles downloaded")
    return normalize(pd.concat(frames))


def load_venues() -> tuple[dict[str, pd.DataFrame], list[dict]]:
    loaders: dict[str, Callable[[], pd.DataFrame]] = {
        "binance_spot": lambda: fetch_binance_vision("spot"),
        "binance_perp": lambda: fetch_binance_vision("perp"),
        "coinbase_spot": fetch_coinbase,
        "bitstamp_spot": fetch_bitstamp,
    }
    venues: dict[str, pd.DataFrame] = {}
    status: list[dict] = []
    for name, loader in loaders.items():
        try:
            df = loader()
            venues[name] = df
            expected = pd.date_range(df.index.min(), df.index.max(), freq="1h", tz="UTC")
            missing = len(expected.difference(df.index))
            status.append({
                "venue": name, "status": "ok", "bars": len(df),
                "start": df.index.min().isoformat(), "end": df.index.max().isoformat(),
                "missing_hours": missing,
            })
        except Exception as exc:
            status.append({"venue": name, "status": "failed", "error": repr(exc)})
    if len(venues) < 2:
        raise RuntimeError(f"Fewer than two venues available: {status}")
    return venues, status
