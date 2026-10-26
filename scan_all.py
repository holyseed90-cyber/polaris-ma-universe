#!/usr/bin/env python3
from __future__ import annotations

import json, time, math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UPBIT_MARKETS = "https://api.upbit.com/v1/market/all"
CDC_BASE = "https://api.crypto.com/exchange/v1"
MA = [5,10,20,60,112,224,448,896]
MAX_DAILY_BARS = 1000
OUT = Path("data")
OUT.mkdir(exist_ok=True)

def session():
    s = requests.Session()
    retry = Retry(
        total=6, connect=6, read=6, status=6, backoff_factor=0.8,
        status_forcelist=[408,429,500,502,503,504],
        allowed_methods=["GET"], raise_on_status=False
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"Accept":"application/json","User-Agent":"polaris-ma-universe/1.0"})
    return s
S = session()

def get_json(url, params=None):
    r = S.get(url, params=params or {}, timeout=45)
    r.raise_for_status()
    return r.json()

def upbit_krw_bases():
    rows = get_json(UPBIT_MARKETS, {"is_details":"false"})
    out = {}
    for r in rows:
        m = str(r.get("market",""))
        if m.startswith("KRW-"):
            base = m.split("-",1)[1].upper()
            out[base] = {
                "upbit_market": m,
                "korean_name": r.get("korean_name"),
                "english_name": r.get("english_name"),
            }
    return out

def cdc_spot_pairs():
    payload = get_json(f"{CDC_BASE}/public/get-instruments")
    if int(payload.get("code",-1)) != 0:
        raise RuntimeError(payload)
    rows = payload.get("result",{}).get("data",[])
    pairs = {}
    for r in rows:
        sym = str(r.get("symbol",""))
        base = str(r.get("base_ccy","")).upper()
        quote = str(r.get("quote_ccy","")).upper()
        inst_type = str(r.get("inst_type","")).upper()
        product_type = str(r.get("product_type","")).upper()
        tradable = bool(r.get("tradable", True))
        derivative = (
            "PERPETUAL" in inst_type or "FUTURE" in inst_type or "OPTION" in inst_type
            or "-PERP" in sym or product_type in {"PERPETUAL","FUTURES","OPTIONS"}
        )
        if not tradable or derivative or not base:
            continue
        if quote not in {"USD","USDT"}:
            continue
        pairs.setdefault(base, {})[quote] = sym
    return pairs

def choose_pair(base, pairs):
    q = pairs.get(base,{})
    if "USD" in q:
        return q["USD"], "USD"
    if "USDT" in q:
        return q["USDT"], "USDT"
    return None, None

def cdc_daily(symbol, max_bars=MAX_DAILY_BARS):
    rows_by_t = {}
    end_ts = int(time.time()*1000)
    prev_min = None
    while len(rows_by_t) < max_bars:
        count = min(300, max_bars-len(rows_by_t)+10)
        p = get_json(
            f"{CDC_BASE}/public/get-candlestick",
            {"instrument_name":symbol,"timeframe":"1D","count":count,"end_ts":end_ts}
        )
        if int(p.get("code",-1)) != 0:
            raise RuntimeError(p)
        rows = p.get("result",{}).get("data",[])
        if not rows:
            break
        ts = []
        for r in rows:
            t=int(r["t"]); ts.append(t)
            rows_by_t[t] = {
                "timestamp_ms":t, "open":float(r["o"]), "high":float(r["h"]),
                "low":float(r["l"]), "close":float(r["c"])
            }
        mn=min(ts)
        if prev_min is not None and mn >= prev_min:
            break
        prev_min=mn; end_ts=mn-1
        time.sleep(0.06)
    if not rows_by_t:
        return pd.DataFrame()
    df=pd.DataFrame([rows_by_t[k] for k in sorted(rows_by_t)])
    # 현재 진행 중 UTC 일봉 제거
    now=pd.Timestamp.now(tz="UTC")
    df["date_time_utc"]=pd.to_datetime(df["timestamp_ms"],unit="ms",utc=True)
    today=now.normalize()
    df=df[df["date_time_utc"] < today].copy()
    return df.tail(max_bars).reset_index(drop=True)

def add_ma(df):
    out=df.copy()
    for p in MA:
        out[f"ma{p}"]=out["close"].rolling(p,min_periods=p).mean()
    return out

def chg(series,bars):
    s=series.dropna()
    if len(s)<=bars: return None
    a=float(s.iloc[-1-bars]); b=float(s.iloc[-1])
    return None if a==0 else (b/a-1)*100

def latest_turn(series, dates):
    d=series.diff()
    up=(d>0)&(d.shift(1)<=0)
    down=(d<0)&(d.shift(1)>=0)
    ui=up[up.fillna(False)].index
    di=down[down.fillna(False)].index
    return {
        "last_up_turn": None if len(ui)==0 else dates.loc[ui[-1]].isoformat(),
        "last_down_turn": None if len(di)==0 else dates.loc[di[-1]].isoformat(),
    }

def crosses(df, lookback=300):
    ev=[]
    start=max(1,len(df)-lookback)
    for i,a in enumerate(MA):
        for b in MA[i+1:]:
            A=df[f"ma{a}"]; B=df[f"ma{b}"]
            valid=A.notna()&B.notna()
            diff=A-B
            g=valid&(diff>0)&(diff.shift(1)<=0)
            d=valid&(diff<0)&(diff.shift(1)>=0)
            for idx in df.index[g & (df.index>=start)]:
                ev.append({"date":df.loc[idx,"date_time_utc"].isoformat(),"short":a,"long":b,"type":"golden","bars_ago":int(len(df)-1-idx)})
            for idx in df.index[d & (df.index>=start)]:
                ev.append({"date":df.loc[idx,"date_time_utc"].isoformat(),"short":a,"long":b,"type":"dead","bars_ago":int(len(df)-1-idx)})
    return sorted(ev,key=lambda x:x["date"])

def exact_touch_runs(df,p,lookback=600):
    col=f"ma{p}"
    valid=df[col].notna()
    touch=valid&(df["low"]<=df[col])&(df["high"]>=df[col])
    idx=[int(i) for i in df.index[touch & (df.index>=max(0,len(df)-lookback))]]
    runs=[]
    for i in idx:
        if not runs or i != runs[-1][-1]+1:
            runs.append([i])
        else:
            runs[-1].append(i)
    return [{
        "start":df.loc[r[0],"date_time_utc"].isoformat(),
        "end":df.loc[r[-1],"date_time_utc"].isoformat(),
        "touch_candles":len(r)
    } for r in runs]

def pair_gap(df,a,b):
    A=df[f"ma{a}"]; B=df[f"ma{b}"]
    v=pd.DataFrame({"a":A,"b":B}).dropna()
    if v.empty:return None
    g=(v["a"]/v["b"]-1)*100
    return {
        "signed_gap_pct":float(g.iloc[-1]),
        "gap_change_5bars_pp":None if len(g)<=5 else float(g.iloc[-1]-g.iloc[-6]),
        "gap_change_20bars_pp":None if len(g)<=20 else float(g.iloc[-1]-g.iloc[-21]),
    }

def analyze(base,meta,symbol,quote,raw):
    df=add_ma(raw)
    last=df.iloc[-1]
    vals={}
    movement={}
    for p in MA:
        v=last[f"ma{p}"]
        vals[str(p)]=None if pd.isna(v) else float(v)
        movement[str(p)]={
            "change_5bars_pct":chg(df[f"ma{p}"],5),
            "change_20bars_pct":chg(df[f"ma{p}"],20),
            **latest_turn(df[f"ma{p}"],df["date_time_utc"])
        }
    order=[f"MA{p}" for p in sorted(
        [p for p in MA if vals[str(p)] is not None],
        key=lambda x:vals[str(x)], reverse=True
    )]
    ev=crosses(df)
    key_pairs=[(5,10),(10,20),(20,60),(60,112),(112,224),(224,448),(448,896)]
    gaps={f"{a}-{b}":pair_gap(df,a,b) for a,b in key_pairs}
    price_vs={}
    for p in MA:
        m=vals[str(p)]
        price_vs[str(p)]=None if m in (None,0) else (float(last["close"])/m-1)*100
    return {
        "ticker":base, **meta, "crypto_symbol":symbol, "quote":quote,
        "bars":int(len(df)),
        "first_date":df.iloc[0]["date_time_utc"].isoformat(),
        "last_complete_date":df.iloc[-1]["date_time_utc"].isoformat(),
        "close":float(last["close"]),
        "ma_values":vals,
        "ma_order_high_to_low":order,
        "ma_movement":movement,
        "adjacent_gaps":gaps,
        "price_vs_ma_pct":price_vs,
        "recent_crosses":ev,
        "cross_density":{
            str(w):{
                "golden":sum(x["type"]=="golden" and x["bars_ago"]<=w for x in ev),
                "dead":sum(x["type"]=="dead" and x["bars_ago"]<=w for x in ev),
            } for w in [30,60,120,240]
        },
        "ma224_exact_touch_runs": exact_touch_runs(df,224),
        "ma448_exact_touch_runs": exact_touch_runs(df,448),
        "ma896_exact_touch_runs": exact_touch_runs(df,896),
    }, df

up=upbit_krw_bases()
cdc=cdc_spot_pairs()
intersection=[]
excluded=[]
for base,meta in sorted(up.items()):
    sym,quote=choose_pair(base,cdc)
    if sym:
        intersection.append((base,meta,sym,quote))
    else:
        excluded.append({"ticker":base,**meta,"reason":"Crypto.com USD/USDT 현물 없음"})

results=[]
errors=[]
for n,(base,meta,sym,quote) in enumerate(intersection,1):
    try:
        print(f"[{n}/{len(intersection)}] {base} {sym}")
        raw=cdc_daily(sym)
        if raw.empty:
            raise RuntimeError("일봉 없음")
        result,df=analyze(base,meta,sym,quote,raw)
        results.append(result)
        # 개별 CSV도 저장
        export=df.copy()
        export["date_time_utc"]=export["date_time_utc"].astype(str)
        export.to_csv(OUT/f"{base}_{quote}_1D_MA.csv",index=False)
    except Exception as e:
        errors.append({"ticker":base,"crypto_symbol":sym,"error":f"{type(e).__name__}: {e}"})

payload={
    "generated_at_utc":datetime.now(timezone.utc).isoformat(),
    "universe_definition":"Upbit KRW listed ∩ Crypto.com tradable spot USD/USDT (USD preferred)",
    "ma_periods":MA,
    "analysis":"moving averages only; price used only relative to MAs/touches",
    "upbit_krw_count":len(up),
    "intersection_count":len(intersection),
    "success_count":len(results),
    "error_count":len(errors),
    "excluded_count":len(excluded),
    "results":results,
    "errors":errors,
    "excluded":excluded,
}
(OUT/"polaris_universe_latest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

# 빠른 요약표
rows=[]
for r in results:
    rows.append({
        "ticker":r["ticker"],
        "quote":r["quote"],
        "bars":r["bars"],
        "has_224":r["ma_values"]["224"] is not None,
        "has_448":r["ma_values"]["448"] is not None,
        "has_896":r["ma_values"]["896"] is not None,
        "MA224_20bar_pct":r["ma_movement"]["224"]["change_20bars_pct"],
        "MA448_20bar_pct":r["ma_movement"]["448"]["change_20bars_pct"],
        "MA896_20bar_pct":r["ma_movement"]["896"]["change_20bars_pct"],
        "price_vs_448_pct":r["price_vs_ma_pct"]["448"],
        "touch_runs_448":len(r["ma448_exact_touch_runs"]),
        "golden_60":r["cross_density"]["60"]["golden"],
        "dead_60":r["cross_density"]["60"]["dead"],
        "order":" > ".join(r["ma_order_high_to_low"]),
    })
pd.DataFrame(rows).to_csv(OUT/"polaris_universe_quick_summary.csv",index=False)

print("\nDONE")
print("Upbit KRW:",len(up))
print("Crypto.com 교집합:",len(intersection))
print("성공:",len(results),"오류:",len(errors),"제외:",len(excluded))
