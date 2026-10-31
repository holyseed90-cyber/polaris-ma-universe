#!/usr/bin/env python3
"""Completed-candle BTC Polaris daily audit. Research only, no trading signals.
Data: Binance BTCUSDT SPOT official public 30m/1h/4h/8h/1d REST.
Fetch native OHLCV as of UTC time, no candle generation and no in-progress bar in indicators.
"""
import collections, datetime as dt, gzip, json, math, os, pathlib, time, urllib.error, urllib.parse, urllib.request
D=pathlib.Path("btc_polaris_daily_20261031")
D.mkdir(exist_ok=True)
TFMS={"30m":1800000,"1h":3600000,"4h":14400000,"8h":28800000,"1d":86400000}
SMA=[5,10,20,60,112,224,448,896]
KST=dt.timezone(dt.timedelta(hours=9))
UTC=dt.timezone.utc
def utc(ms):
    return dt.datetime.fromtimestamp(ms/1000,UTC)
def iso(ms):
    return utc(ms).isoformat(timespec="seconds").replace("+00:00","Z")
def kst(ms):
    return utc(ms).astimezone(KST).isoformat(timespec="seconds")
def req(host,path,params=None,timeout=19):
    url=host+path+("?"+urllib.parse.urlencode(params) if params else "")
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 BTC research (noncommercial public read)","Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=timeout) as r:
        j=json.loads(r.read())
        if isinstance(j,dict) and "code" in j and j["code"]<0:raise ValueError(str(j))
        return j
BASES=["https://data-api.binance.vision","https://api.binance.com","https://api1.binance.com","https://api2.binance.com"]
errors=[]
def spot(path,params=None):
    last=""
    for h in BASES:
        for attempt in range(2):
            try:return req(h,path,params),h
            except Exception as e:
                last=str(e);errors.append({"url":h+path,"error":last[:150]})
                time.sleep(.5*(attempt+1))
    raise RuntimeError("Official Binance spot endpoints unavailable: "+last)

def fetch_tf(tf,at_ms):
    # Paginate backward with previous oldest openTime as exclusive endTime. Reject overlaps, gaps.
    allbars={}
    end=at_ms
    src=None
    for page in range(3):
        rows,src=spot("/api/v3/klines",{"symbol":"BTCUSDT","interval":tf,"endTime":end,"limit":1000})
        if not rows:break
        for r in rows:
            if int(r[6])>=at_ms:continue
            t=int(r[0])
            allbars[t]={
                "open_ms":t,"close_ms":int(r[6]),"open":float(r[1]),
                "high":float(r[2]),"low":float(r[3]),"close":float(r[4]),
                "volume":float(r[5]),"quote_volume":float(r[7]),
                "trades":int(r[8]),"taker_buy_volume":float(r[9]),
                "taker_buy_quote":float(r[10]),
            }
        end=int(rows[0][0])-1
        if len(allbars)>=1850:break
    bars=[allbars[t] for t in sorted(allbars)]
    gaps=[]
    for i in range(1,len(bars)):
        diff=bars[i]["open_ms"]-bars[i-1]["open_ms"]
        if diff!=TFMS[tf]:gaps.append({"prev":iso(bars[i-1]["open_ms"]),"next":iso(bars[i]["open_ms"]),"gap_ms":diff})
    for r in bars:
        assert r["high"]>=max(r["open"],r["close"])>=r["low"] and r["high"]>=r["low"]
        assert r["close_ms"]==r["open_ms"]+TFMS[tf]-1,(tf,r)
        if tf=="8h":assert r["open_ms"]%TFMS[tf]==0
    if len(bars)<920:raise RuntimeError(f"{tf} insufficient historical completed bars {len(bars)}")
    # Latest is last fully complete candle even if request happens during an incomplete bar
    assert bars[-1]["close_ms"]<at_ms
    return bars,gaps,src

def mean(vals):return sum(vals)/len(vals) if vals else None
def rolling_sma(a,n):
    out=[None]*len(a);p=0.0
    for i,v in enumerate(a):
        p+=v
        if i>=n:p-=a[i-n]
        if i>=n-1:out[i]=p/n
    return out
def wilder_rsi(bars,n=14):
    c=[r["close"] for r in bars]
    out=[None]*len(c)
    if len(c)<=n:return out
    gains=[max(c[i]-c[i-1],0.) for i in range(1,len(c))]
    losses=[max(c[i-1]-c[i],0.) for i in range(1,len(c))]
    g=sum(gains[:n])/n;l=sum(losses[:n])/n
    for i in range(n,len(c)):
        if i>n:
            g=(g*(n-1)+gains[i-1])/n
            l=(l*(n-1)+losses[i-1])/n
        out[i]=100 if l==0 else 100-100/(1+g/l)
    return out
def wilder_atr(bars,n=14):
    tr=[bars[0]["high"]-bars[0]["low"]]
    for i in range(1,len(bars)):
        r=bars[i]
        tr.append(max(r["high"]-r["low"],abs(r["high"]-bars[i-1]["close"]),abs(r["low"]-bars[i-1]["close"])))
    out=[None]*len(bars)
    if len(bars)<n:return out,tr
    x=sum(tr[:n])/n
    out[n-1]=x
    for i in range(n,len(bars)):
        x=(x*(n-1)+tr[i])/n
        out[i]=x
    return out,tr
def cross(mas,tf,bars):
    found=[]
    start=max(897,len(bars)-170)
    for a,b in zip(SMA,SMA[1:]):
        x=mas[a];y=mas[b]
        latest=None
        for i in range(start,len(bars)):
            if x[i-1] is None or y[i-1] is None:continue
            direction="golden" if x[i-1]<=y[i-1] and x[i]>y[i] else ("dead" if x[i-1]>=y[i-1] and x[i]<y[i] else "")
            if direction:
                latest={"pair":f"{a}/{b}","type":direction,"close_kst":kst(bars[i]["close_ms"]+1),
                        "bars_ago":len(bars)-i-1, "elapsed_hours":round((bars[-1]["close_ms"]-bars[i]["close_ms"])/3600000,2)}
        if latest:found.append(latest)
    return found
def calc(tf,bars,gaps,source,asof_ms):
    assert not gaps, f"Open-time gaps in official {tf} series: "+str(gaps[:3])
    i=len(bars)-1
    cur=bars[-1]; prev=bars[-2]
    closes=[x["close"] for x in bars]
    mas={n:rolling_sma(closes,n) for n in SMA}
    rsis=wilder_rsi(bars)
    atrs,_=wilder_atr(bars)
    avg_prev20=mean([x["volume"] for x in bars[-21:-1]])
    ma_now={str(k):round(mas[k][-1],4) for k in SMA}
    pos={"price_above_ma":[k for k in SMA if cur["close"]>mas[k][-1]],
         "price_below_ma":[k for k in SMA if cur["close"]<mas[k][-1]]}
    ordering=sorted(SMA,key=lambda k:mas[k][-1],reverse=True)
    slopes={}
    for n in SMA:
        arr=mas[n];now=arr[-1]; old=arr[-4]; prevOld=arr[-7]
        s=100*(now/old-1);prevS=100*(old/prevOld-1)
        slopes[str(n)]={
            "slope_pct_last3bars":round(s,4),
            "slope_pct_previous3bars":round(prevS,4),
            "acceleration_pp":round(s-prevS,4),
            "direction":"up" if s>0 else "down" if s<0 else "flat",
            "magnitude":"accelerating" if abs(s)>abs(prevS) else "decelerating" if abs(s)<abs(prevS) else "unchanged"
        }
    gaps_pair={}
    for a,b in zip(SMA,SMA[1:]):
        g0=(mas[a][-1]/mas[b][-1]-1)*100
        g3=(mas[a][-4]/mas[b][-4]-1)*100
        gaps_pair[f"{a}/{b}"]={"gap_pct":round(g0,4),"gap_prior3bars_pct":round(g3,4),
                             "gap_status":"expanding" if abs(g0)>abs(g3) else "compressing",
                             "orientation":"golden" if g0>0 else "dead" if g0<0 else "equal"}
    prior20=bars[-21:-1];prior60=bars[-61:-1]
    last20_high=max(x["high"] for x in prior20)
    last20_low=min(x["low"] for x in prior20)
    last60_high=max(x["high"] for x in prior60)
    last60_low=min(x["low"] for x in prior60)
    rng=cur["high"]-cur["low"]
    close_loc=(cur["close"]-cur["low"])/rng if rng else 0.5
    body=abs(cur["close"]-cur["open"])/rng if rng else 0
    upper=(cur["high"]-max(cur["open"],cur["close"]))/rng if rng else 0
    lower=(min(cur["open"],cur["close"])-cur["low"])/rng if rng else 0
    vol3=sum(x["volume"] for x in bars[-3:])
    taker3=2*sum(x["taker_buy_volume"] for x in bars[-3:])/vol3-1 if vol3 else None
    total20=sum(x["volume"] for x in bars[-20:])
    taker20=2*sum(x["taker_buy_volume"] for x in bars[-20:])/total20-1 if total20 else None
    support=sorted({round(x,2) for x in [*ma_now.values(),last20_low,last60_low,cur["low"]] if x<cur["close"]},reverse=True)
    resistance=sorted({round(x,2) for x in [*ma_now.values(),last20_high,last60_high,cur["high"]] if x>cur["close"]})
    return {
        "symbol":"BTCUSDT","venue":"Binance SPOT","source":source,
        "timeframe":tf,"duration_s":TFMS[tf]/1000,
        "completed_bars":len(bars),"missing_bars_recent":len(gaps),
        "open_utc":iso(cur["open_ms"]),"close_utc":iso(cur["close_ms"]+1),
        "close_kst":kst(cur["close_ms"]+1),
        "open":cur["open"],"high":cur["high"],"low":cur["low"],"close":cur["close"],
        "previous_close":prev["close"],
        "rsi14_wilder":round(rsis[-1],3),"rsi14_previous":round(rsis[-2],3),
        "atr14_wilder":round(atrs[-1],4),
        "atr14_pct":round(atrs[-1]/cur["close"]*100,4),
        "sma":ma_now,"sma_order_high_to_low":ordering,
        **pos,
        "ma_slopes_accel":slopes,
        "adjacent_ma_gaps":gaps_pair,
        "recent_crosses_last_169_bars":cross(mas,tf,bars),
        "last_bar": {
            "body_pct_of_range":round(100*body,2),
            "close_location_pct_of_range":round(100*close_loc,2),
            "upper_wick_pct":round(100*upper,2),
            "lower_wick_pct":round(100*lower,2),
            "relative_volume_prev20":round(cur["volume"]/avg_prev20,3) if avg_prev20 else None,
            "spot_taker_imbalance_lastbar_pct":round(100*(2*cur["taker_buy_volume"]/cur["volume"]-1),2) if cur["volume"] else None,
            "spot_taker_imbalance_last3bars_pct":round(100*taker3,2) if taker3 is not None else None,
            "spot_taker_imbalance_last20bars_pct":round(100*taker20,2) if taker20 is not None else None,
            "quote_volume_usdt":round(cur["quote_volume"],2),
            "low_sweep20_recovered":cur["low"]<last20_low and cur["close"]>last20_low,
            "high_sweep20_failed":cur["high"]>last20_high and cur["close"]<last20_high,
            "close_break_prior20_high":cur["close"]>last20_high,
            "close_break_prior20_low":cur["close"]<last20_low,
        },
        "prior20_high":last20_high,"prior20_low":last20_low,
        "prior60_high":last60_high,"prior60_low":last60_low,
        "nearest_support_levels":support[:9],
        "nearest_resistance_levels":resistance[:9],
        "current_in_progress_candle":{
            "expected_open_utc":iso(cur["close_ms"]+1),
            "expected_close_utc":iso(cur["close_ms"]+1+TFMS[tf]),
            "excluded_from_indicators":True,
        }
    }

def futures_sources():
    v={}
    base=["https://fapi.binance.com","https://fapi1.binance.com"]
    for label,path,params in [
        ("futures_current_oi","/fapi/v1/openInterest",{"symbol":"BTCUSDT"}),
        ("futures_premium_funding","/fapi/v1/premiumIndex",{"symbol":"BTCUSDT"}),
        ("futures_recent_funding_history","/fapi/v1/fundingRate",{"symbol":"BTCUSDT","limit":5}),
        ("futures_ticker_24h","/fapi/v1/ticker/24hr",{"symbol":"BTCUSDT"})
    ]:
        v[label]={"status":"unverified"}
        for url in base:
            try:
                data=req(url,path,params,timeout=8)
                v[label]={"status":"observed_current_only","source":url+path,"data":data}
                break
            except Exception as e:
                v[label]["last_error"]=str(e)[:120]
    return v

def main():
    now=int(time.time()*1000)
    snapshot={"requested_at_utc":iso(now),"requested_at_kst":kst(now),
              "data_kind":"exchange public observed BTCUSDT spot, completed native candles; not forward-verified strategy",
              "timeframes":{},"unavailable":[],"futures":{}}
    try:
        tik,hs=spot("/api/v3/ticker/price",{"symbol":"BTCUSDT"})
        snapshot["spot_ticker"]={"price":float(tik["price"]),"source":hs+"/api/v3/ticker/price",
                                  "observed_at_utc":iso(int(time.time()*1000))}
    except Exception as e:
        snapshot["unavailable"].append({"metric":"spot live ticker","error":str(e)})
    try:
        ticker,src=spot("/api/v3/ticker/24hr",{"symbol":"BTCUSDT"})
        snapshot["spot_24h_ticker"]={"priceChangePercent":ticker.get("priceChangePercent"),
                                     "highPrice":ticker.get("highPrice"),"lowPrice":ticker.get("lowPrice"),
                                     "volume":ticker.get("volume"),"quoteVolume":ticker.get("quoteVolume"),
                                     "source":src+"/api/v3/ticker/24hr"}
    except Exception as e:
        snapshot["unavailable"].append({"metric":"spot24","error":str(e)})
    with gzip.open(D/"official_completed_candles.jsonl.gz","wt",encoding="utf8") as f:
        for tf in TFMS:
            try:
                b,gaps,src=fetch_tf(tf,now)
                snapshot["timeframes"][tf]=calc(tf,b,gaps,src,now)
                f.write(json.dumps({"tf":tf,"source":src,"bars":b},ensure_ascii=False)+"\n")
            except Exception as e:
                snapshot["unavailable"].append({"metric":"official "+tf,"error":str(e)})
            print(f"done {tf}",flush=True)
    snapshot["futures"]=futures_sources()
    snapshot["finished_at_utc"]=iso(int(time.time()*1000))
    snapshot["finished_at_kst"]=kst(int(time.time()*1000))
    snapshot["request_error_history"]=errors[-35:]
    (D/"snapshot.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({
        "requested_at_kst":snapshot["requested_at_kst"],
        "finished_at_kst":snapshot["finished_at_kst"],
        "ticker":snapshot.get("spot_ticker"),"unavailable":snapshot["unavailable"],
        "tf":{k:{"close_kst":v["close_kst"],"close":v["close"],
                 "rsi":v["rsi14_wilder"],"atr_pct":v["atr14_pct"]} for k,v in snapshot["timeframes"].items()},
        "futures":{k:{"status":v["status"],"sample":v.get("data") if k!="futures_recent_funding_history" else "see snapshot"}
                 for k,v in snapshot["futures"].items()}
    },ensure_ascii=False,indent=2))
    if len(snapshot["timeframes"])<5:raise RuntimeError("Critical incomplete: fewer than all five official timeframe series; see snapshot.json")
if __name__=="__main__":main()
