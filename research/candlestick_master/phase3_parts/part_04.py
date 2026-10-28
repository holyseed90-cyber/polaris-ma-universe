        "low_sweep20":"bullish","high_sweep20":"bearish","bull_retest_hold":"bullish","bear_retest_hold":"bearish",
        "bull_retest_fail":"bearish","bear_retest_fail":"bullish","bull_fvg":"bullish","bear_fvg":"bearish",
        "bull_expansion":"bullish","bear_expansion":"bearish",
    }
    for p in [112,224,448,896]:
        events[f"ma{p}_bull_defense"]="bullish";events[f"ma{p}_bear_reject"]="bearish"
    return events


def evaluate(tf:str,df:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    h=TF_CONFIG[tf]["horizon"]; rows=[]; fp=[]; contexts=[]
    cats=event_catalog(df)
    for event,direction in cats.items():
        allpos=np.flatnonzero(df[event].fillna(False).to_numpy())
        rec={"timeframe":tf,"event":event,"direction":direction,"horizon_bars":h}
        for split,(start,end) in SPLITS.items():
            mask=((df.signal_time.iloc[allpos]>=start)&(df.signal_time.iloc[allpos]<end)).to_numpy(); pos=allpos[mask]
            m=score_event(df,pos,h,direction)
            for k,v in m.items():rec[f"{split}_{k}"]=v
            for mult in [.5,1.,1.5,2.]:
                r=first_passage(df,pos,h,direction,mult);fp.append({"timeframe":tf,"event":event,"direction":direction,"split":split,"horizon_bars":h,"atr_multiple":mult,**r})
        rec["survives"] = bool(rec.get("train_n",0)>=20 and rec.get("validation_n",0)>=8 and rec.get("test_n",0)>=TF_CONFIG[tf]["min_test"] and min(rec.get("train_win_rate",0),rec.get("validation_win_rate",0),rec.get("test_win_rate",0))>=.52 and min(rec.get("train_median_signed_ret",-999),rec.get("validation_median_signed_ret",-999),rec.get("test_median_signed_ret",-999))>0)
        rows.append(rec)
        # Context refinement is evaluated without choosing direction from test.
        for ctx in ["trend_regime","long_state","rsi_state"]:
            values=df.loc[df[event].fillna(False),ctx].dropna().astype(str).unique()
            for val in values:
                posall=np.flatnonzero((df[event].fillna(False)&(df[ctx].astype(str)==val)).to_numpy()); cr={"timeframe":tf,"event":event,"direction":direction,"context":ctx,"value":val,"horizon_bars":h}
                for split,(start,end) in SPLITS.items():
                    mask=((df.signal_time.iloc[posall]>=start)&(df.signal_time.iloc[posall]<end)).to_numpy();m=score_event(df,posall[mask],h,direction)
                    for k,v in m.items():cr[f"{split}_{k}"]=v
                if cr.get("test_n",0)>=max(5,TF_CONFIG[tf]["min_test"]//2):contexts.append(cr)
    return pd.DataFrame(rows),pd.DataFrame(fp),pd.DataFrame(contexts)


def build_report(frames:dict[str,pd.DataFrame],events:pd.DataFrame,fp:pd.DataFrame,contexts:pd.DataFrame)->None:
    lines=["# BTC Candlestick Master — Phase 3A","","## Scope","","Confirmed-pivot market structure, SFP/Spring/Upthrust, BoS/CHoCH, first retest, 20-bar liquidity sweeps, FVG creation, contraction→expansion, and independent 112/224/448/896 MA wave touches.","","## Source-derived hypotheses","","The uploaded technical-analysis atlas treats support/resistance flips, market structure (BoS/CHoCH), Spring/Upthrust, liquidity, FVG, order blocks and contraction/expansion as distinct price-action concepts. Phase 3A tests the objectively codable subset; order-block and Wyckoff phase models remain for Phase 3B.","","## Data"]
    for tf,d in frames.items():lines.append(f"- {tf}: {len(d):,} bars, {d.index.min().isoformat()} → {d.index.max().isoformat()}")
    lines += ["","## Events surviving all three splits",""]
    good=events[events.survives].copy()
    if good.empty:lines.append("No base event passed every conservative survival gate.")
    else:
        cols=["timeframe","event","direction","train_n","validation_n","test_n","train_win_rate","validation_win_rate","test_win_rate","test_median_signed_ret","test_median_mfe_atr","test_median_mae_atr"]
        lines.append(good[cols].sort_values(["test_win_rate","test_n"],ascending=False).to_markdown(index=False,floatfmt=".3f"))
    lines += ["","## Best test first-passage rows (1 ATR)",""]
    q=fp[(fp.split=="test")&(fp.atr_multiple==1.0)&((fp.target_first+fp.stop_first)>=8)].sort_values(["decided_win_rate","target_first"],ascending=False).head(30)
    lines.append(q[["timeframe","event","direction","events","target_first","stop_first","ambiguous","no_hit","decided_win_rate","wilson_low","wilson_high"]].to_markdown(index=False,floatfmt=".3f") if not q.empty else "No row had eight decided events.")
    lines += ["","## Stable context refinements",""]
    if contexts.empty:lines.append("No context rows generated.")
    else:
        c=contexts.copy();c["min_win"]=c[["train_win_rate","validation_win_rate","test_win_rate"]].min(axis=1);c["min_ret"]=c[["train_median_signed_ret","validation_median_signed_ret","test_median_signed_ret"]].min(axis=1)
        c=c[(c.min_win>=.52)&(c.min_ret>0)].sort_values(["min_win","test_n"],ascending=False).head(30)
        cols=["timeframe","event","direction","context","value","train_n","validation_n","test_n","train_win_rate","validation_win_rate","test_win_rate","test_median_signed_ret"]
        lines.append(c[cols].to_markdown(index=False,floatfmt=".3f") if not c.empty else "No context refinement passed the consistency filter.")
    lines += ["","## Interpretation","","A surviving event is a research candidate, not a live signal. Phase 3B must test event sequences (e.g., sweep→CHoCH→retest), FVG fill/reaction, three-tap structures, range phase, order-block/breaker definitions and higher-timeframe confluence. Cross-exchange and after-cost testing remain mandatory."]
    (OUT/"phase3a_report.md").write_text("\n".join(lines),encoding="utf-8")


def main():
    hourly=normalize_source(download_source());raws={"1h":hourly}
    for tf,c in TF_CONFIG.items():
        if tf!="1h":raws[tf]=resample_ohlcv(hourly,c["rule"])
    frames={}; er=[]; fr=[]; cr=[]
    for tf,raw in raws.items():
        cfg=TF_CONFIG[tf];d=enrich(raw,cfg["hours"],cfg["pivot"]);d=detect_structure_events(d);d=add_retests(d,max_wait=max(4,12//cfg["hours"] if cfg["hours"]<=12 else 4));d=add_ma_wave_touches(d);d=add_forward_metrics(d,cfg["horizon"]);frames[tf]=d
        e,f,c=evaluate(tf,d);er.append(e);fr.append(f);cr.append(c)
    events=pd.concat(er,ignore_index=True);fp=pd.concat(fr,ignore_index=True);contexts=pd.concat(cr,ignore_index=True)
    events.to_csv(OUT/"phase3a_events.csv",index=False);fp.to_csv(OUT/"phase3a_first_passage.csv",index=False);contexts.to_csv(OUT/"phase3a_contexts.csv",index=False)
    build_report(frames,events,fp,contexts)
    meta={"source":SOURCE_URL,"generated_utc":pd.Timestamp.now(tz="UTC").isoformat(),"phase":"3A","bars":{k:int(len(v)) for k,v in frames.items()},"event_rows":int(len(events)),"survivors":int(events.survives.sum()),"first_passage_rows":int(len(fp)),"context_rows":int(len(contexts))}
    (OUT/"phase3a_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8");print(json.dumps(meta,indent=2))

if __name__=="__main__":main()
