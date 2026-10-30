#!/usr/bin/env python3
"""Upbit KRW universe, completed 1-hour SMA(112/224/448/896) crossover audit.
No prices or candles are synthesized. This is a cross-sectional scan, not a forecast.
"""
import csv, gzip, json, math, os, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT=Path("upbit_screen")
OUT.mkdir(exist_ok=True)
UTC=timezone.utc
KST=timezone(timedelta(hours=9))
started=datetime.now(UTC)
cutoff=started.replace(minute=0,second=0,microsecond=0)
cutoff_text=cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
next_at=[time.monotonic()]
lock=threading.Lock()
stats={"calls":0,"retried":0}
stats_lock=threading.Lock()
errors=[]

def fetch_json(url):
    last=""
    for attempt in range(7):
        with lock:
            t=max(time.monotonic(),next_at[0])
            next_at[0]=t+0.165
        time.sleep(max(0,t-time.monotonic()))
        with stats_lock:
            stats["calls"]+=1
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"Mozilla/5.0 (compatible; public-market-research/1.0)",
                "Accept":"application/json"
            })
            with urllib.request.urlopen(req,timeout=24) as response:
                return json.loads(response.read())
        except Exception as ex:
            last=str(ex)
            with stats_lock: stats["retried"]+=1
            time.sleep(min(9,1.4*(attempt+1)))
    raise RuntimeError(last)

def api(path,params):
    return fetch_json("https://api.upbit.com"+path+"?"+urllib.parse.urlencode(params))

def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z","+00:00")).replace(tzinfo=UTC) if "+" not in value and not value.endswith("Z") else datetime.fromisoformat(value.replace("Z","+00:00"))

def sma(prefix,i,n):
    if i<n-1: return None
    return (prefix[i+1]-prefix[i+1-n])/n

def cross_state(rows):
    closes=[float(r["trade_price"]) for r in rows]
    p=[0.0]
    for v in closes: p.append(p[-1]+v)
    n=len(closes)
    if n<896: return None
    def gap(i,a,b):
        x,y=sma(p,i,a),sma(p,i,b)
        return (x/y-1.0)*100 if (x is not None and y is not None and y!=0) else None
    now=n-1
    gap_a=gap(now,112,224); gap_b=gap(now,448,896)
    a24=gap(now-24,112,224) if now>=24 else None
    b24=gap(now-24,448,896) if now>=24 else None
    a72=gap(now-72,112,224) if now>=72 else None
    b72=gap(now-72,448,896) if now>=72 else None
    changes={"112_224":(gap_a-a24 if a24 is not None else None),
             "448_896":(gap_b-b24 if b24 is not None else None)}
    def event(a,b):
        golden=[];dead=[]
        for i in range(max(b, n-169),n):
            prior=gap(i-1,a,b); current=gap(i,a,b)
            if prior is None or current is None:continue
            if prior<=0 and current>0: golden.append(rows[i]["candle_date_time_utc"])
            if prior>=0 and current<0: dead.append(rows[i]["candle_date_time_utc"])
        return golden,dead
    ag,ad=event(112,224)
    bg,bd=event(448,896)
    recent_a=bool(ag) and (cutoff-parse_utc(ag[-1])).total_seconds()<=7*86400
    recent_b=bool(bg) and (cutoff-parse_utc(bg[-1])).total_seconds()<=7*86400
    near_a=gap_a is not None and -0.5<=gap_a<=0 and changes["112_224"] is not None and changes["112_224"]>0.005
    near_b=gap_b is not None and -0.5<=gap_b<=0 and changes["448_896"] is not None and changes["448_896"]>0.001
    watch_a=gap_a is not None and -1<=gap_a<0 and changes["112_224"] is not None and changes["112_224"]>0
    watch_b=gap_b is not None and -1<=gap_b<0 and changes["448_896"] is not None and changes["448_896"]>0
    def _slope(period):
        x=sma(p,now,period)
        old=sma(p,now-24,period)
        return ((x/old)-1)*100 if old else None
    onehour_times=[parse_utc(r["candle_date_time_utc"]) for r in rows[-169:]]
    missing_recent=sum(max(0,int((b-a).total_seconds()/3600)-1) for a,b in zip(onehour_times,onehour_times[1:]))
    return {
        "last_completed_candle_open_utc":rows[-1]["candle_date_time_utc"],
        "last_close":closes[-1],
        "rows":n,
        "gap_112_224_pct":gap_a,
        "gap_448_896_pct":gap_b,
        "gap_112_224_change24_pp":changes["112_224"],
        "gap_448_896_change24_pp":changes["448_896"],
        "gap_112_224_change72_pp":(gap_a-a72 if a72 is not None else None),
        "gap_448_896_change72_pp":(gap_b-b72 if b72 is not None else None),
        "sma112":sma(p,now,112),"sma224":sma(p,now,224),
        "sma448":sma(p,now,448),"sma896":sma(p,now,896),
        "slope24_ma112_pct":_slope(112),
        "slope24_ma224_pct":_slope(224),
        "slope24_ma448_pct":_slope(448),
        "slope24_ma896_pct":_slope(896),
        "last_golden_112_224_utc":ag[-1] if ag else None,
        "last_golden_448_896_utc":bg[-1] if bg else None,
        "last_dead_112_224_utc":ad[-1] if ad else None,
        "last_dead_448_896_utc":bd[-1] if bd else None,
        "recent_112_224":recent_a,
        "recent_448_896":recent_b,
        "near_112_224":near_a,
        "near_448_896":near_b,
        "watch_112_224":watch_a,
        "watch_448_896":watch_b,
        "missing_hours_in_recent_168_candle_intervals":missing_recent,
        "candle_acc_trade_price":rows[-1].get("candle_acc_trade_price"),
        "candle_acc_trade_volume":rows[-1].get("candle_acc_trade_volume")
    }

def fetch_market(m):
    market=m["market"]
    all_rows={}
    to=cutoff_text
    try:
        for page in range(6):
            arr=api("/v1/candles/minutes/60",{"market":market,"to":to,"count":200})
            if not isinstance(arr,list) or not arr:break
            for r in arr:
                key=r["candle_date_time_utc"]
                if parse_utc(key)+timedelta(hours=1)<=cutoff:
                    all_rows[key]=r
            earliest=min(r["candle_date_time_utc"] for r in arr)
            to=earliest+"Z"
            if len(arr)<200 or len(all_rows)>=1195:break
        rows=[all_rows[x] for x in sorted(all_rows)]
        if not rows:
            return {"market":market,"korean_name":m["korean_name"],"status":"no_candles"},None
        res={
            "market":market, "korean_name":m["korean_name"],"english_name":m.get("english_name",""),
            "status":"ok"
        }
        latest=parse_utc(rows[-1]["candle_date_time_utc"])+timedelta(hours=1)
        res["last_completed_kst"]=latest.astimezone(KST).isoformat()
        res["age_hours"]=(cutoff-latest).total_seconds()/3600
        res["observed_1h_candles"]=len(rows)
        res["last_price_from_completed_candle"]=rows[-1]["trade_price"]
        out=cross_state(rows)
        if out is None:
            res["status"]="short_history_under_896"
        else:
            res.update(out)
            if res["age_hours"]>6:
                res["status"]="stale_candles"
        raw=[{"utc":r["candle_date_time_utc"],"close":r["trade_price"],
              "open":r["opening_price"],"high":r["high_price"],"low":r["low_price"],"volume":r["candle_acc_trade_volume"]}
              for r in rows]
        return res,raw
    except Exception as exc:
        return {"market":market,"korean_name":m["korean_name"],"status":"error","error":str(exc)},None

def krw(x):return f"{x:,.0f}" if x>=100 else f"{x:,.8f}"

def main():
    markets=[m for m in api("/v1/market/all",{"isDetails":"false"}) if m["market"].startswith("KRW-")]
    ticker={}
    for i in range(0,len(markets),40):
        try:
            for t in api("/v1/ticker",{"markets":",".join(m["market"] for m in markets[i:i+40])}):
                ticker[t["market"]]=t
        except Exception as exc:
            errors.append({"source":"ticker","chunk":i,"error":str(exc)})
    results=[]
    rawpath=OUT/"upbit_1h_bars.jsonl.gz"
    with gzip.open(rawpath,"wt",encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=7) as pool:
            futures=[pool.submit(fetch_market,m) for m in markets]
            for j,fu in enumerate(as_completed(futures),1):
                row,raw=fu.result()
                t=ticker.get(row["market"],{})
                row["ticker_price"]=t.get("trade_price")
                row["ticker_trade_value_24h_krw"]=t.get("acc_trade_price_24h")
                row["ticker_change24_pct"]=(t.get("signed_change_rate") or 0)*100 if t else None
                results.append(row)
                if raw is not None:f.write(json.dumps({"market":row["market"],"bars":raw},ensure_ascii=False)+"\n")
                if j%40==0:print(f"completed={j}/{len(markets)}",flush=True)
    valid=[r for r in results if r["status"]=="ok"]
    def priority(r):
        return (int(r["recent_112_224"])*3+int(r["recent_448_896"])*4+
                int(r["near_112_224"])*2+int(r["near_448_896"])*3+
                int(r["watch_112_224"])+int(r["watch_448_896"]))
    for r in valid:
        r["signal_priority"]=priority(r)
        r["strong_liquidity"]=float(r["ticker_trade_value_24h_krw"] or 0)>=1e8
    selected=[r for r in valid if r["signal_priority"]>0]
    selected.sort(key=lambda r:(-r["signal_priority"],-int(r["strong_liquidity"]),-float(r["ticker_trade_value_24h_krw"] or 0)))
    results.sort(key=lambda r:r["market"])
    def csvout(path,values):
        keys=sorted(set().union(*(x.keys() for x in values))) if values else []
        with open(OUT/path,"w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(values)
    csvout("all_markets.csv",results)
    csvout("candidates.csv",selected)
    meta={
        "started_utc":started.isoformat(),
        "completed_utc":datetime.now(UTC).isoformat(),
        "cutoff_completed_hour_utc":cutoff.isoformat(),
        "cutoff_kst":cutoff.astimezone(KST).isoformat(),
        "source_market":"Upbit official KRW markets via api.upbit.com",
        "timeframe":"1 hour, native Upbit 60 minute OHLCV",
        "universe_size":len(markets),
        "analyzed_full_896":len(valid),
        "candidates":len(selected),
        "short_history":sum(r["status"]=="short_history_under_896" for r in results),
        "stale":sum(r["status"]=="stale_candles" for r in results),
        "errors":sum(r["status"]=="error" for r in results),
        "requests":stats,
        "near_definition":"Both SMA available, negative gap no worse than -0.5%, gap narrowed during preceding 24 completed 1h bars",
        "watch_definition":"Negative gap no worse than -1%, narrowed during 24 completed hours",
        "recent_definition":"Bullish cross within last 168 elapsed hours, using only closed 1h candles",
        "confidence_note":"Crosses and proximity are observed arithmetic conditions, NOT validated bullish probabilities",
        "source_urls":[
            "https://api.upbit.com/v1/market/all?isDetails=false",
            "https://api.upbit.com/v1/candles/minutes/60?market=KRW-PEPE&count=200",
            "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
        ]
    }
    (OUT/"manifest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"errors.json").write_text(json.dumps([r for r in results if r["status"]!="ok"]+errors,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"top_candidates.json").write_text(json.dumps(selected[:70],ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# 업비트 KRW 1시간봉 장기 SMA 골든크로스 스크리닝",
           "",f"조회 마감시각 KST: {meta['cutoff_kst']}",
           f"KRW 종목수 {len(markets)}, 896개 이상 유효 종목 {len(valid)}, 관련 후보 {len(selected)}",
           "", "조건: 최근 7일 상향 교차 또는 이평 간격 0.5% 이내이고 최근 24시간 간격 축소",
           "아래 가격은 업비트 KRW 시장의 마지막 완성 1시간봉 종가이며 매수 추천이나 검증된 승률이 아닙니다.",
           "",
           "|종목|112/224 차이%|448/896 차이%|최근 112/224|최근 448/896|근접112|근접448|24h 거래대금 억원|",
           "|---|---:|---:|---|---|---|---|---:|"]
    for r in selected[:70]:
        liq=float(r["ticker_trade_value_24h_krw"] or 0)/1e8
        a=r["last_golden_112_224_utc"] or "-"
        b=r["last_golden_448_896_utc"] or "-"
        lines.append(f"|{r['korean_name']} ({r['market']})|{r['gap_112_224_pct']:.3f}|{r['gap_448_896_pct']:.3f}|{a if r['recent_112_224'] else '-'}|{b if r['recent_448_896'] else '-'}|{r['near_112_224']}|{r['near_448_896']}|{liq:.1f}|")
    (OUT/"REPORT_KO.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"cutoff_kst":meta["cutoff_kst"],"count":len(markets),"full_history":len(valid),"candidates":len(selected),
                      "errors":meta["errors"],"first_candidates":[
                        {"market":r["market"],"name":r["korean_name"],"gap112":r["gap_112_224_pct"],
                        "gap448":r["gap_448_896_pct"],"priority":r["signal_priority"]} for r in selected[:25]
                        ]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
