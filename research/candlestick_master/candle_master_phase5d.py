#!/usr/bin/env python3
"""Phase 5D — BTC derivatives / order-flow / volume-profile increment audit.

The script consumes frozen Phase 5B/5C event tables and official Binance Vision
archives. It never uses information timestamped after an event close. It mines
filters on train+validation only and reports untouched next-calendar-year tests.
"""
from __future__ import annotations

import concurrent.futures as cf
import io
import itertools
import json
import math
import os
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests
from scipy import stats

OUT = Path("research/candlestick_master/output_phase5d")
CACHE = Path("research/candlestick_master/.phase5d_cache")
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

BINANCE = "https://data.binance.vision/data"
SYMBOL = "BTCUSDT"
START = pd.Timestamp("2020-01-01", tz="UTC")
END = pd.Timestamp("2026-09-10", tz="UTC")

FOLDS = [
    dict(name="WF2023", train_start="2020-01-01", train_end="2022-01-01", val_start="2022-01-01", val_end="2023-01-01", test_start="2023-01-01", test_end="2024-01-01"),
    dict(name="WF2024", train_start="2020-01-01", train_end="2023-01-01", val_start="2023-01-01", val_end="2024-01-01", test_start="2024-01-01", test_end="2025-01-01"),
    dict(name="WF2025", train_start="2020-01-01", train_end="2024-01-01", val_start="2024-01-01", val_end="2025-01-01", test_start="2025-01-01", test_end="2026-01-01"),
    dict(name="WF2026", train_start="2020-01-01", train_end="2025-01-01", val_start="2025-01-01", val_end="2026-01-01", test_start="2026-01-01", test_end="2026-09-10"),
]

PROMOTION_CONFIGS = {
    "4h": ["P05_S10_H6", "P075_S10_H8", "P10_S10_H8"],
    "1d": ["P05_S10_H3", "P075_S10_H5", "P10_S10_H7"],
}
DIAGNOSTIC_CONFIGS = {
    "4h": ["P05_S125_H6"],
    "1d": ["P05_S125_H3"],
}

KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
METRIC_COLS = ["create_time", "symbol", "sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "polaris-candlestick-research/5D"})


def utc(x: str | pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def month_labels(start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    cur = pd.Timestamp(start.year, start.month, 1)
    stop = pd.Timestamp((end - pd.Timedelta(days=1)).year, (end - pd.Timedelta(days=1)).month, 1)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%Y-%m"))
        cur += pd.offsets.MonthBegin(1)
    return out


def day_labels(start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start.tz_localize(None), (end - pd.Timedelta(days=1)).tz_localize(None), freq="D")]


def request_bytes(url: str, retries: int = 4) -> bytes | None:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except Exception:
            if attempt + 1 == retries:
                return None
            time.sleep(0.5 * (2 ** attempt))
    return None


def read_zip_csv(content: bytes, names: list[str] | None = None) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        member = zf.namelist()[0]
        raw = zf.read(member)
    first = raw.splitlines()[0].decode("utf-8", errors="ignore") if raw else ""
    has_header = any(ch.isalpha() for ch in first)
    return pd.read_csv(io.BytesIO(raw), header=0 if has_header else None, names=None if has_header else names)


def parallel_fetch(labels: list[str], url_fn, parser_fn, workers: int = 20) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    missing: list[str] = []

    def one(label: str):
        data = request_bytes(url_fn(label))
        if data is None:
            return label, None
        try:
            return label, parser_fn(data)
        except Exception:
            return label, None

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for label, frame in ex.map(one, labels):
            if frame is None or frame.empty:
                missing.append(label)
            else:
                frames.append(frame)
    if not frames:
        return pd.DataFrame(), missing
    return pd.concat(frames, ignore_index=True), missing


def infer_epoch(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    med = float(v.dropna().abs().median()) if v.notna().any() else 0
    unit = "us" if med > 1e14 else ("ms" if med > 1e11 else "s")
    return pd.to_datetime(v, unit=unit, utc=True, errors="coerce")


def load_monthly_klines(market: str, interval: str) -> tuple[pd.DataFrame, list[str]]:
    labels = month_labels(START, END)
    def url(label: str) -> str:
        root = "spot" if market == "spot" else "futures/um"
        return f"{BINANCE}/{root}/monthly/klines/{SYMBOL}/{interval}/{SYMBOL}-{interval}-{label}.zip"
    def parse(data: bytes) -> pd.DataFrame:
        x = read_zip_csv(data, KLINE_COLS)
        x.columns = [str(c).strip().lower() for c in x.columns]
        if "open_time" not in x.columns:
            x.columns = KLINE_COLS[:len(x.columns)]
        return x
    x, missing = parallel_fetch(labels, url, parse, workers=12)
    if x.empty:
        return x, missing
    x["open_time"] = infer_epoch(x["open_time"])
    for c in KLINE_COLS[1:]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.dropna(subset=["open_time", "close"]).drop_duplicates("open_time").sort_values("open_time")
    delta = pd.Timedelta(hours=1) if interval == "1h" else pd.Timedelta(minutes=5)
    x["signal_time"] = x["open_time"] + delta
    return x.reset_index(drop=True), missing


def load_funding() -> tuple[pd.DataFrame, list[str]]:
    labels = month_labels(START, END)
    def url(label: str) -> str:
        return f"{BINANCE}/futures/um/monthly/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{label}.zip"
    def parse(data: bytes) -> pd.DataFrame:
        return read_zip_csv(data, ["calc_time", "funding_interval_hours", "last_funding_rate"])
    x, missing = parallel_fetch(labels, url, parse, workers=12)
    if x.empty:
        return x, missing
    x.columns = [str(c).strip().lower() for c in x.columns]
    x["calc_time"] = infer_epoch(x["calc_time"])
    x["last_funding_rate"] = pd.to_numeric(x["last_funding_rate"], errors="coerce")
    x["funding_interval_hours"] = pd.to_numeric(x.get("funding_interval_hours", 8), errors="coerce").fillna(8)
    return x.dropna(subset=["calc_time", "last_funding_rate"]).drop_duplicates("calc_time").sort_values("calc_time").reset_index(drop=True), missing


def load_metrics() -> tuple[pd.DataFrame, list[str]]:
    labels = day_labels(START, END)
    def url(label: str) -> str:
        return f"{BINANCE}/futures/um/daily/metrics/{SYMBOL}/{SYMBOL}-metrics-{label}.zip"
    def parse(data: bytes) -> pd.DataFrame:
        return read_zip_csv(data, METRIC_COLS)
    x, missing = parallel_fetch(labels, url, parse, workers=28)
    if x.empty:
        return x, missing
    x.columns = [str(c).strip().lower() for c in x.columns]
    x["create_time"] = pd.to_datetime(x["create_time"], utc=True, errors="coerce")
    for c in METRIC_COLS[2:]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    return x.dropna(subset=["create_time"]).drop_duplicates("create_time", keep="last").sort_values("create_time").reset_index(drop=True), missing


def rolling_z(s: pd.Series, n: int, min_n: int | None = None) -> pd.Series:
    min_n = min_n or max(10, n // 4)
    m = s.rolling(n, min_periods=min_n).mean()
    sd = s.rolling(n, min_periods=min_n).std(ddof=0).replace(0, np.nan)
    return (s - m) / sd


def build_hourly_derivatives(perp: pd.DataFrame, spot: pd.DataFrame, metrics: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    p = perp.set_index("signal_time").sort_index().copy()
    s = spot.set_index("signal_time").sort_index().copy()
    h = pd.DataFrame(index=p.index)
    h["perp_close"] = p.close
    h["spot_close"] = s.close.reindex(h.index)
    h["basis_bps_d"] = (h.perp_close / h.spot_close - 1) * 10000
    h["basis_chg_4h"] = h.basis_bps_d.diff(4)
    h["basis_chg_24h"] = h.basis_bps_d.diff(24)
    h["basis_z_30d"] = rolling_z(h.basis_bps_d, 24 * 30)
    h["price_ret_4h"] = h.perp_close.pct_change(4)
    h["price_ret_24h"] = h.perp_close.pct_change(24)

    for prefix, frame in [("fut", p), ("spot", s)]:
        qv = pd.to_numeric(frame.quote_volume, errors="coerce")
        tb = pd.to_numeric(frame.taker_buy_quote_volume, errors="coerce")
        signed = 2 * tb - qv
        for n in [4, 24, 72]:
            denom = qv.rolling(n, min_periods=max(2, n // 2)).sum().replace(0, np.nan)
            h[f"{prefix}_cvd_{n}h"] = signed.rolling(n, min_periods=max(2, n // 2)).sum() / denom
    h["cvd_div_4h"] = h.spot_cvd_4h - h.fut_cvd_4h
    h["cvd_div_24h"] = h.spot_cvd_24h - h.fut_cvd_24h

    m = metrics.copy().set_index("create_time").sort_index()
    mh = m.resample("1h", label="right", closed="left").last()
    mh = mh.reindex(h.index, method="ffill")
    h["oi_value"] = mh.sum_open_interest_value
    h["oi_contracts"] = mh.sum_open_interest
    h["oi_chg_4h"] = np.log(h.oi_value / h.oi_value.shift(4))
    h["oi_chg_24h"] = np.log(h.oi_value / h.oi_value.shift(24))
    h["oi_z_30d"] = rolling_z(np.log(h.oi_value.replace(0, np.nan)), 24 * 30)
    h["top_account_ratio"] = mh.count_toptrader_long_short_ratio
    h["top_position_ratio"] = mh.sum_toptrader_long_short_ratio
    h["global_account_ratio"] = mh.count_long_short_ratio
    h["taker_ratio"] = mh.sum_taker_long_short_vol_ratio
    h["taker_log_4h"] = np.log(h.taker_ratio.replace(0, np.nan)).rolling(4, min_periods=2).mean()
    h["taker_log_24h"] = np.log(h.taker_ratio.replace(0, np.nan)).rolling(24, min_periods=8).mean()

    f = funding.copy().set_index("calc_time").sort_index()
    f["funding_24h"] = f.last_funding_rate.rolling(3, min_periods=1).sum()
    f["funding_72h"] = f.last_funding_rate.rolling(9, min_periods=3).sum()
    f["funding_z_90"] = rolling_z(f.last_funding_rate, 90, 20)
    ff = f[["last_funding_rate", "funding_24h", "funding_72h", "funding_z_90"]].reindex(h.index, method="ffill")
    h = h.join(ff)
    h.index.name = "signal_time"
    return h.reset_index()


def value_area(hist: np.ndarray, edges: np.ndarray, fraction: float = 0.70) -> tuple[float, float, float]:
    if hist.sum() <= 0:
        return np.nan, np.nan, np.nan
    poc = int(np.argmax(hist))
    chosen = {poc}
    total = float(hist[poc])
    left, right = poc - 1, poc + 1
    target = float(hist.sum()) * fraction
    while total < target and (left >= 0 or right < len(hist)):
        lv = hist[left] if left >= 0 else -1
        rv = hist[right] if right < len(hist) else -1
        if rv >= lv:
            chosen.add(right); total += max(0, float(rv)); right += 1
        else:
            chosen.add(left); total += max(0, float(lv)); left -= 1
    lo, hi = min(chosen), max(chosen)
    poc_price = (edges[poc] + edges[poc + 1]) / 2
    return poc_price, float(edges[lo]), float(edges[hi + 1])


def volume_profile_features(events: pd.DataFrame, five: pd.DataFrame) -> pd.DataFrame:
    x = five.sort_values("signal_time").reset_index(drop=True)
    times = x.signal_time.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
    typical = ((x.high + x.low + x.close) / 3).to_numpy(float)
    weights = pd.to_numeric(x.quote_volume, errors="coerce").fillna(0).to_numpy(float)
    lows = x.low.to_numpy(float)
    highs = x.high.to_numpy(float)
    rows = []
    for r in events[["event_id", "timeframe", "signal_time", "atr_pct"]].itertuples(index=False):
        ts = np.datetime64(pd.Timestamp(r.signal_time).tz_convert("UTC").tz_localize(None))
        days = 7 if r.timeframe == "4h" else 30
        start = ts - np.timedelta64(days, "D")
        a = int(np.searchsorted(times, start, side="left"))
        b = int(np.searchsorted(times, ts, side="right"))
        if b - a < (500 if r.timeframe == "4h" else 2000):
            rows.append({"event_id": r.event_id}); continue
        lo, hi = float(np.nanmin(lows[a:b])), float(np.nanmax(highs[a:b]))
        if not np.isfinite(lo + hi) or hi <= lo:
            rows.append({"event_id": r.event_id}); continue
        hist, edges = np.histogram(typical[a:b], bins=80, range=(lo, hi), weights=weights[a:b])
        poc, val, vah = value_area(hist, edges)
        close = float(x.close.iloc[b - 1])
        atr = close * float(r.atr_pct) / 100 if np.isfinite(r.atr_pct) else np.nan
        rows.append({"event_id": r.event_id, "vp_poc": poc, "vp_val": val, "vp_vah": vah, "vp_close_above_poc": close > poc, "vp_close_above_vah": close > vah, "vp_close_below_poc": close < poc, "vp_close_below_val": close < val, "vp_inside_value": val <= close <= vah, "vp_poc_dist_atr": (close - poc) / atr if atr and np.isfinite(atr) else np.nan, "vp_value_width_atr": (vah - val) / atr if atr and np.isfinite(atr) else np.nan})
    return pd.DataFrame(rows)


def merge_event_features(events: pd.DataFrame, hourly: pd.DataFrame, vp: pd.DataFrame) -> pd.DataFrame:
    e = events.copy(); e["signal_time"] = pd.to_datetime(e.signal_time, utc=True)
    h = hourly.copy().sort_values("signal_time"); h["signal_time"] = pd.to_datetime(h.signal_time, utc=True)
    e = pd.merge_asof(e.sort_values("signal_time"), h, on="signal_time", direction="backward", allow_exact_matches=True)
    return e.merge(vp, on="event_id", how="left")


def add_side_flags(e: pd.DataFrame) -> pd.DataFrame:
    x = e.copy(); long = x.side.eq("long"); short = ~long
    x["d_oi_trend_confirm"] = (long & (x.price_ret_4h > 0) & (x.oi_chg_4h > 0)) | (short & (x.price_ret_4h < 0) & (x.oi_chg_4h > 0))
    x["d_oi_24h_confirm"] = (long & (x.price_ret_24h > 0) & (x.oi_chg_24h > 0)) | (short & (x.price_ret_24h < 0) & (x.oi_chg_24h > 0))
    x["d_oi_deleverage_reversal"] = (long & (x.price_ret_4h < 0) & (x.oi_chg_4h < 0)) | (short & (x.price_ret_4h > 0) & (x.oi_chg_4h < 0))
    x["d_oi_not_crowded"] = x.oi_z_30d < 1.5
    x["d_oi_extreme_flush"] = x.oi_z_30d < -1.0
    x["d_funding_contrarian"] = (long & (x.last_funding_rate <= 0)) | (short & (x.last_funding_rate >= 0))
    x["d_funding_24h_contrarian"] = (long & (x.funding_24h <= 0)) | (short & (x.funding_24h >= 0))
    x["d_funding_not_extreme"] = x.funding_z_90.abs() < 1.5
    x["d_funding_extreme_against"] = (long & (x.funding_z_90 <= -1.0)) | (short & (x.funding_z_90 >= 1.0))
    x["d_basis_contrarian"] = (long & (x.basis_bps_d <= 0)) | (short & (x.basis_bps_d >= 0))
    x["d_basis_not_extreme"] = x.basis_z_30d.abs() < 1.5
    x["d_basis_change_align"] = (long & (x.basis_chg_4h > 0)) | (short & (x.basis_chg_4h < 0))
    x["d_fut_cvd_4h_align"] = (long & (x.fut_cvd_4h > 0)) | (short & (x.fut_cvd_4h < 0))
    x["d_fut_cvd_24h_align"] = (long & (x.fut_cvd_24h > 0)) | (short & (x.fut_cvd_24h < 0))
    x["d_spot_cvd_4h_align"] = (long & (x.spot_cvd_4h > 0)) | (short & (x.spot_cvd_4h < 0))
    x["d_spot_cvd_24h_align"] = (long & (x.spot_cvd_24h > 0)) | (short & (x.spot_cvd_24h < 0))
    x["d_both_cvd_4h_align"] = x.d_fut_cvd_4h_align & x.d_spot_cvd_4h_align
    x["d_spot_leads_4h"] = (long & (x.spot_cvd_4h > x.fut_cvd_4h) & (x.spot_cvd_4h > 0)) | (short & (x.spot_cvd_4h < x.fut_cvd_4h) & (x.spot_cvd_4h < 0))
    x["d_spot_leads_24h"] = (long & (x.spot_cvd_24h > x.fut_cvd_24h) & (x.spot_cvd_24h > 0)) | (short & (x.spot_cvd_24h < x.fut_cvd_24h) & (x.spot_cvd_24h < 0))
    x["d_taker_align_4h"] = (long & (x.taker_log_4h > 0)) | (short & (x.taker_log_4h < 0))
    x["d_taker_align_24h"] = (long & (x.taker_log_24h > 0)) | (short & (x.taker_log_24h < 0))
    x["d_crowd_contrarian"] = (long & (x.global_account_ratio < 1)) | (short & (x.global_account_ratio > 1))
    x["d_top_position_align"] = (long & (x.top_position_ratio > 1)) | (short & (x.top_position_ratio < 1))
    x["d_top_vs_crowd_divergence"] = (long & (x.top_position_ratio > 1) & (x.global_account_ratio < 1)) | (short & (x.top_position_ratio < 1) & (x.global_account_ratio > 1))
    x["d_vp_side_poc"] = (long & x.vp_close_above_poc.fillna(False)) | (short & x.vp_close_below_poc.fillna(False))
    x["d_vp_value_break"] = (long & x.vp_close_above_vah.fillna(False)) | (short & x.vp_close_below_val.fillna(False))
    x["d_vp_poc_near"] = x.vp_poc_dist_atr.abs() <= 1.0
    x["d_vp_not_wide"] = x.vp_value_width_atr <= 6.0
    cols = [c for c in x.columns if c.startswith("d_")]
    x[cols] = x[cols].fillna(False).astype(bool)
    return x

FAMILIES = {
    "oi": ["d_oi_trend_confirm", "d_oi_24h_confirm", "d_oi_deleverage_reversal", "d_oi_not_crowded", "d_oi_extreme_flush"],
    "funding": ["d_funding_contrarian", "d_funding_24h_contrarian", "d_funding_not_extreme", "d_funding_extreme_against"],
    "basis": ["d_basis_contrarian", "d_basis_not_extreme", "d_basis_change_align"],
    "cvd": ["d_fut_cvd_4h_align", "d_fut_cvd_24h_align", "d_spot_cvd_4h_align", "d_spot_cvd_24h_align", "d_both_cvd_4h_align", "d_spot_leads_4h", "d_spot_leads_24h"],
    "participant": ["d_taker_align_4h", "d_taker_align_24h", "d_crowd_contrarian", "d_top_position_align", "d_top_vs_crowd_divergence"],
    "volume_profile": ["d_vp_side_poc", "d_vp_value_break", "d_vp_poc_near", "d_vp_not_wide"],
    "legacy_dmi_vwma": ["i_dmi_align", "i_adx20", "i_adx25_rising", "i_vwma_align"],
}
FEATURE_FAMILY = {f: fam for fam, fs in FAMILIES.items() for f in fs}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0: return np.nan, np.nan
    p = k / n; den = 1 + z*z/n; mid = (p + z*z/(2*n))/den
    half = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return mid-half, mid+half


def profit_factor(v: pd.Series) -> float:
    pos = float(v[v > 0].sum()); neg = float(-v[v < 0].sum())
    return np.inf if neg == 0 and pos > 0 else (pos/neg if neg > 0 else np.nan)


def metrics(z: pd.DataFrame, cost: int = 50) -> dict:
    if z.empty: return {"n": 0}
    net = pd.to_numeric(z[f"net_{cost}bps_pct"], errors="coerce").dropna()
    if net.empty: return {"n": 0}
    hit = z.loc[net.index, "outcome"].eq("target"); lo, hi = wilson(int(hit.sum()), len(hit))
    return dict(n=len(net), rate=float(hit.mean()), wilson_low=lo, wilson_high=hi, mean=float(net.mean()), median=float(net.median()), pf=profit_factor(net), positive=float((net>0).mean()))


def p_lift(filtered: pd.DataFrame, base: pd.DataFrame) -> float:
    if filtered.empty or base.empty: return np.nan
    a, n1 = int(filtered.outcome.eq("target").sum()), len(filtered); b, n0 = int(base.outcome.eq("target").sum()), len(base)
    pool = (a+b)/(n1+n0); se = math.sqrt(max(1e-15, pool*(1-pool)*(1/n1+1/n0)))
    return float(stats.norm.sf((a/n1-b/n0)/se))


def bh(pvals: Iterable[float]) -> np.ndarray:
    p = np.asarray(list(pvals), float); n=len(p)
    if n == 0: return p
    order=np.argsort(np.nan_to_num(p,nan=1.0)); ranked=p[order]; adj=np.ones(n); run=1.0
    for i in range(n-1,-1,-1): run=min(run,(ranked[i] if np.isfinite(ranked[i]) else 1.0)*n/(i+1)); adj[i]=min(1.0,run)
    out=np.empty(n); out[order]=adj; return out


def mask_period(s: pd.Series, start: str, end: str) -> pd.Series:
    t=pd.to_datetime(s,utc=True); return (t>=utc(start))&(t<utc(end))


def base_patterns(df: pd.DataFrame, side: str) -> list[str]:
    out=[]
    for c in df.columns:
        if not c.startswith("b_"): continue
        if side=="long" and any(k in c for k in ["bull","low_sweep","spring"]): out.append(c)
        if side=="short" and any(k in c for k in ["bear","high_sweep","upthrust"]): out.append(c)
    return sorted(out)


def select_rules(train: pd.DataFrame, val: pd.DataFrame, base_col: str, tf: str) -> tuple[list[tuple[str,...]], pd.DataFrame]:
    min_tr=45 if tf=="4h" else 14; min_va=14 if tf=="4h" else 5
    bt=train[train[base_col]]; bv=val[val[base_col]]
    if len(bt)<min_tr or len(bv)<min_va: return [],pd.DataFrame()
    mbt,mbv=metrics(bt),metrics(bv); rows=[]; shortlist=[]
    for f,fam in FEATURE_FAMILY.items():
        tr=bt[bt[f]]; va=bv[bv[f]]
        if len(tr)<min_tr or len(va)<min_va: continue
        mt,mv=metrics(tr),metrics(va)
        rows.append(dict(base_pattern=base_col,rule=f,families=fam,count=1,train_n=mt["n"],train_rate=mt["rate"],train_mean50=mt["mean"],train_pf50=mt["pf"],val_n=mv["n"],val_rate=mv["rate"],val_mean50=mv["mean"],val_pf50=mv["pf"],train_lift=mt["rate"]-mbt["rate"],val_lift=mv["rate"]-mbv["rate"],p=p_lift(va,bv),base_train_rate=mbt["rate"],base_val_rate=mbv["rate"]))
        if mt["mean"]>0 and mv["mean"]>0 and mt["rate"]>=mbt["rate"]+0.03 and mv["rate"]>=mbv["rate"]+0.03:
            shortlist.append((min(mt["rate"]-mbt["rate"],mv["rate"]-mbv["rate"])+0.03*min(mt["mean"],mv["mean"]),f))
    selected_single=[]
    for fam in FAMILIES:
        fs=sorted([(sc,f) for sc,f in shortlist if FEATURE_FAMILY[f]==fam],reverse=True)[:2]
        selected_single.extend([f for _,f in fs])
    candidates=[(f,) for f in selected_single]
    for a,b in itertools.combinations(selected_single,2):
        if FEATURE_FAMILY[a]==FEATURE_FAMILY[b]: continue
        tr=bt[bt[a]&bt[b]]; va=bv[bv[a]&bv[b]]
        if len(tr)<min_tr or len(va)<min_va: continue
        mt,mv=metrics(tr),metrics(va)
        rows.append(dict(base_pattern=base_col,rule=f"{a} & {b}",families=f"{FEATURE_FAMILY[a]}+{FEATURE_FAMILY[b]}",count=2,train_n=mt["n"],train_rate=mt["rate"],train_mean50=mt["mean"],train_pf50=mt["pf"],val_n=mv["n"],val_rate=mv["rate"],val_mean50=mv["mean"],val_pf50=mv["pf"],train_lift=mt["rate"]-mbt["rate"],val_lift=mv["rate"]-mbv["rate"],p=p_lift(va,bv),base_train_rate=mbt["rate"],base_val_rate=mbv["rate"]))
        if mt["mean"]>0 and mv["mean"]>0 and mt["rate"]>=mbt["rate"]+0.05 and mv["rate"]>=mbv["rate"]+0.05: candidates.append((a,b))
    audit=pd.DataFrame(rows)
    if not audit.empty:
        audit["bh_q_within_base"] = bh(audit.p.fillna(1))
        valid=set(audit[(audit.val_mean50>0)&(audit.val_pf50>=1.0)&(audit.val_lift>=0.03)].rule)
        candidates=[r for r in candidates if " & ".join(r) in valid or r[0] in valid]
        audit=audit.sort_values(["val_lift","val_n"],ascending=[False,False])
    uniq=[]; seen=set()
    for r in candidates:
        if r not in seen: seen.add(r); uniq.append(r)
    return uniq[:8],audit


def walkforward(data: pd.DataFrame, diagnostic: bool=False) -> tuple[pd.DataFrame,pd.DataFrame]:
    configs=DIAGNOSTIC_CONFIGS if diagnostic else PROMOTION_CONFIGS
    selected=[]; audits=[]
    for fold in FOLDS:
        for tf,cfgs in configs.items():
            for side in ["long","short"]:
                pats=base_patterns(data[data.timeframe==tf],side)
                for cfg in cfgs:
                    z=data[(data.timeframe==tf)&(data.side==side)&(data.config_id==cfg)&data.valid].copy()
                    if z.empty: continue
                    tr=z[mask_period(z.signal_time,fold["train_start"],fold["train_end"])]
                    va=z[mask_period(z.signal_time,fold["val_start"],fold["val_end"])]
                    te=z[mask_period(z.signal_time,fold["test_start"],fold["test_end"])]
                    for pat in pats:
                        rules,audit=select_rules(tr,va,pat,tf)
                        if not audit.empty:
                            audit.insert(0,"fold",fold["name"]); audit.insert(1,"timeframe",tf); audit.insert(2,"side",side); audit.insert(3,"config_id",cfg); audit.insert(4,"diagnostic",diagnostic); audits.append(audit)
                        base_te=te[te[pat]]; mb=metrics(base_te)
                        for rule in rules:
                            m=pd.Series(True,index=te.index)
                            for f in rule: m &= te[f]
                            chosen=te[te[pat]&m]
                            if chosen.empty: continue
                            mm=metrics(chosen)
                            for _,row in chosen.iterrows():
                                d=row.to_dict(); d.update(dict(fold=fold["name"],base_pattern=pat,derivative_rule=" & ".join(rule),families="+".join(sorted({FEATURE_FAMILY[f] for f in rule})),filter_count=len(rule),diagnostic=diagnostic,base_test_n=mb.get("n",0),base_test_rate=mb.get("rate",np.nan),rule_test_n=mm.get("n",0),rule_test_rate=mm.get("rate",np.nan),rule_test_wilson_low=mm.get("wilson_low",np.nan),rule_test_mean50=mm.get("mean",np.nan),rule_test_pf50=mm.get("pf",np.nan)))
                                selected.append(d)
    return pd.DataFrame(selected), pd.concat(audits,ignore_index=True) if audits else pd.DataFrame()


def aggregate(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty: return pd.DataFrame()
    key=["timeframe","side","config_id","base_pattern","derivative_rule","families","diagnostic"]
    rows=[]
    for keys,g in selected.groupby(key,dropna=False):
        g=g.sort_values("signal_time").drop_duplicates(["event_id","config_id","derivative_rule"])
        m30,m50=metrics(g,30),metrics(g,50); years=[]
        for y,yy in g.groupby(pd.to_datetime(g.signal_time,utc=True).dt.year): years.append({"year":int(y),**metrics(yy,50)})
        active=[y for y in years if y.get("n",0)>0]
        base=float(np.average(g.base_test_rate.fillna(0),weights=np.maximum(g.base_test_n,1)))
        rows.append({**dict(zip(key,keys)),"n":m50.get("n",0),"target_rate":m50.get("rate",np.nan),"wilson_low":m50.get("wilson_low",np.nan),"wilson_high":m50.get("wilson_high",np.nan),"mean30":m30.get("mean",np.nan),"pf30":m30.get("pf",np.nan),"mean50":m50.get("mean",np.nan),"pf50":m50.get("pf",np.nan),"base_rate":base,"lift":m50.get("rate",np.nan)-base,"active_years":len(active),"min_year_rate":min((y.get("rate",np.nan) for y in active),default=np.nan),"min_year_mean50":min((y.get("mean",np.nan) for y in active),default=np.nan),"years_json":json.dumps(years,ensure_ascii=False)})
    out=pd.DataFrame(rows)
    if not out.empty:
        out["pass_75_gate"]=(~out.diagnostic)&(out.n>=np.where(out.timeframe.eq("4h"),30,15))&(out.target_rate>=0.75)&(out.wilson_low>=0.60)&(out.mean50>0)&(out.pf50>=1.50)&(out.active_years>=2)&(out.min_year_mean50>0)
        out=out.sort_values(["pass_75_gate","target_rate","n","mean50"],ascending=[False,False,False,False])
    return out


def family_summary(rules: pd.DataFrame) -> pd.DataFrame:
    if rules.empty: return pd.DataFrame()
    rows=[]
    for fam in FAMILIES:
        z=rules[(~rules.diagnostic)&rules.families.str.contains(fam,regex=False,na=False)]
        if z.empty: continue
        rows.append(dict(family=fam,rule_count=len(z),test_n=int(z.n.sum()),median_rate=float(z.target_rate.median()),median_lift=float(z.lift.median()),positive_lift_share=float((z.lift>0).mean()),positive_mean50_share=float((z.mean50>0).mean()),median_mean50=float(z.mean50.median()),best_rate_n15=float(z.loc[z.n>=15,"target_rate"].max()) if (z.n>=15).any() else np.nan))
    return pd.DataFrame(rows).sort_values(["positive_mean50_share","median_lift"],ascending=False)


def report(rules: pd.DataFrame, fam: pd.DataFrame, coverage: dict) -> None:
    lines=["# BTC Phase 5D — Derivatives, Order Flow and Volume Profile Audit","","## Data integrity","",f"- Official Binance Vision metrics files loaded: {coverage['metrics_files']:,}; missing: {coverage['metrics_missing']:,}",f"- Funding monthly files loaded: {coverage['funding_files']:,}; missing: {coverage['funding_missing']:,}",f"- Perpetual 1h monthly files loaded: {coverage['perp1h_files']:,}; spot 1h: {coverage['spot1h_files']:,}",f"- Perpetual 5m monthly files loaded for volume-profile approximation: {coverage['perp5m_files']:,}","- Binance public historical liquidation snapshots were not used because the official archive is currently unavailable/retired. No proxy is labeled as actual liquidation data.","- POC/VAH/VAL are 5-minute typical-price, quote-volume approximations—not tick-accurate exchange volume profiles.","","## 75% promotion gate","","A rule must have ≥30 independent 4h events or ≥15 daily events, target-hit rate ≥75%, Wilson lower bound ≥60%, positive 50-bps net expectancy, PF ≥1.5, and positive 50-bps expectancy in at least two test years.",""]
    passed=rules[rules.pass_75_gate] if not rules.empty else pd.DataFrame()
    lines.append("**No rule passed every 75% gate.**" if passed.empty else passed.head(20).to_markdown(index=False,floatfmt=".4f"))
    lines += ["","## Best non-diagnostic rules","",rules[~rules.diagnostic].head(30).to_markdown(index=False,floatfmt=".4f") if not rules.empty else "No selected rules.","","## Family summary","",fam.to_markdown(index=False,floatfmt=".4f") if not fam.empty else "No family summary.","","## Interpretation","","Derivative filters are accepted only when they improve a pre-existing candle/structure signal in training and validation and then survive an untouched next-calendar-year test. High historical hit rate without positive 50-bps expectancy is rejected."]
    (OUT/"phase5d_report.md").write_text("\n".join(lines),encoding="utf-8")


def main() -> None:
    input5b=Path("inputs/phase5b"); input5c=Path("inputs/phase5c")
    events=pd.read_csv(input5c/"indicator_event_features.csv"); outcomes=pd.read_csv(input5b/"perp_event_outcomes.csv")
    events["signal_time"]=pd.to_datetime(events.signal_time,utc=True); outcomes["signal_time"]=pd.to_datetime(outcomes.signal_time,utc=True)
    perp1h,miss_p1=load_monthly_klines("perp","1h"); spot1h,miss_s1=load_monthly_klines("spot","1h"); perp5m,miss_p5=load_monthly_klines("perp","5m"); funding,miss_f=load_funding(); metrics5m,miss_m=load_metrics()
    hourly=build_hourly_derivatives(perp1h,spot1h,metrics5m,funding); vp=volume_profile_features(events,perp5m); enriched=add_side_flags(merge_event_features(events,hourly,vp))
    keep=["event_id","timeframe","side","signal_time"]+[c for c in enriched.columns if c.startswith(("b_","d_","i_"))]
    data=outcomes.merge(enriched[keep],on=["event_id","timeframe","side","signal_time"],how="left")
    bools=[c for c in data.columns if c.startswith(("b_","d_","i_"))]; data[bools]=data[bools].fillna(False).astype(bool)
    selected,audit=walkforward(data,False); selected_d,audit_d=walkforward(data,True)
    all_sel=pd.concat([selected,selected_d],ignore_index=True) if not selected_d.empty else selected; all_audit=pd.concat([audit,audit_d],ignore_index=True) if not audit_d.empty else audit
    rules=aggregate(all_sel); fam=family_summary(rules)
    if not all_audit.empty: all_audit["global_bh_q"]=bh(all_audit.p.fillna(1))
    months=len(month_labels(START,END)); days=len(day_labels(START,END)); coverage=dict(metrics_files=days-len(miss_m),metrics_missing=len(miss_m),funding_files=months-len(miss_f),funding_missing=len(miss_f),perp1h_files=months-len(miss_p1),spot1h_files=months-len(miss_s1),perp5m_files=months-len(miss_p5))
    enriched.to_csv(OUT/"phase5d_event_features.csv",index=False); selected.to_csv(OUT/"phase5d_selected_test_events.csv",index=False); rules.to_csv(OUT/"phase5d_rule_summary.csv",index=False); fam.to_csv(OUT/"phase5d_family_summary.csv",index=False); all_audit.to_csv(OUT/"phase5d_rule_audit.csv",index=False); pd.DataFrame([coverage]).to_csv(OUT/"phase5d_data_coverage.csv",index=False); report(rules,fam,coverage)
    meta={"phase":"5D","generated_utc":pd.Timestamp.now(tz="UTC").isoformat(),"event_rows":len(events),"outcome_rows":len(outcomes),"enriched_rows":len(enriched),"selected_test_rows":len(selected),"rule_rows":len(rules),"passed_75_gate":int(rules.pass_75_gate.sum()) if not rules.empty else 0,"coverage":coverage}
    (OUT/"phase5d_metadata.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding="utf-8"); print(json.dumps(meta,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
