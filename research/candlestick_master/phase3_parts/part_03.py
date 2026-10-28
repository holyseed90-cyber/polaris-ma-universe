    return y


def add_ma_wave_touches(x: pd.DataFrame, ma_periods=(112,224,448,896), zone_atr=.25, excursion_atr=1.0) -> pd.DataFrame:
    """Independent MA touches require an excursion away before another touch counts."""
    y=x.copy()
    for p in ma_periods:
        touch=np.zeros(len(y),dtype=bool); side=np.zeros(len(y),dtype=np.int8)
        armed=True; last_side=0
        ma=y[f"ma{p}"].to_numpy(); atr=y.atr14.to_numpy(); hi=y.high.to_numpy(); lo=y.low.to_numpy(); cl=y.close.to_numpy()
        for i in range(len(y)):
            if not np.isfinite(ma[i]) or not np.isfinite(atr[i]): continue
            dist=(cl[i]-ma[i])/atr[i]
            if not armed and abs(dist)>=excursion_atr: armed=True
            in_zone=(lo[i] <= ma[i]+zone_atr*atr[i]) and (hi[i] >= ma[i]-zone_atr*atr[i])
            if armed and in_zone:
                touch[i]=True
                side[i]=1 if cl[i]>=ma[i] else -1
                last_side=side[i]; armed=False
        y[f"ma{p}_wave_touch"]=touch
        y[f"ma{p}_touch_side"]=side
        y[f"ma{p}_bull_defense"]=touch & (side==1) & (y.close_location>=.55)
        y[f"ma{p}_bear_reject"]=touch & (side==-1) & (y.close_location<=.45)
    return y


def add_forward_metrics(x: pd.DataFrame, horizon: int) -> pd.DataFrame:
    y=x.copy(); y[f"ret_{horizon}"]=(y.close.shift(-horizon)/y.close-1)*100
    fh=pd.concat([y.high.shift(-k) for k in range(1,horizon+1)],axis=1).max(axis=1)
    fl=pd.concat([y.low.shift(-k) for k in range(1,horizon+1)],axis=1).min(axis=1)
    y[f"mfe_{horizon}_atr"]=(fh-y.close)/y.atr14; y[f"mae_{horizon}_atr"]=(fl-y.close)/y.atr14
    return y


def dedupe(pos: np.ndarray, horizon: int) -> np.ndarray:
    if len(pos)==0:return pos
    keep=[int(pos[0])]
    for p in pos[1:]:
        if int(p)-keep[-1]>=horizon:keep.append(int(p))
    return np.asarray(keep,dtype=int)


def wilson(k:int,n:int,z=1.96):
    if n==0:return (np.nan,np.nan)
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return c-h,c+h


def score_event(df:pd.DataFrame,pos:np.ndarray,horizon:int,direction:str)->dict:
    pos=dedupe(np.sort(pos),horizon); vals=df.iloc[pos][f"ret_{horizon}"].dropna()
    if vals.empty:return {"n":0}
    signed=vals if direction=="bullish" else -vals; k=int((signed>0).sum()); lo,hi=wilson(k,len(signed))
    return {"n":int(len(signed)),"median_signed_ret":float(signed.median()),"mean_signed_ret":float(signed.mean()),"win_rate":float((signed>0).mean()),"wilson_low":float(lo),"wilson_high":float(hi),"median_mfe_atr":float((df.iloc[pos][f"mfe_{horizon}_atr"] if direction=="bullish" else -df.iloc[pos][f"mae_{horizon}_atr"]).median()),"median_mae_atr":float((df.iloc[pos][f"mae_{horizon}_atr"] if direction=="bullish" else -df.iloc[pos][f"mfe_{horizon}_atr"]).median())}


def first_passage(df:pd.DataFrame,pos:np.ndarray,horizon:int,direction:str,mult=1.0)->dict:
    pos=dedupe(np.sort(pos),horizon); t=s=a=n=0
    for i in pos:
        if i+horizon>=len(df) or not np.isfinite(df.atr14.iloc[i]):continue
        entry=float(df.close.iloc[i]); atr=float(df.atr14.iloc[i]); target=entry+(mult*atr if direction=="bullish" else -mult*atr); stop=entry-(mult*atr if direction=="bullish" else -mult*atr)
        result=0
        for j in range(i+1,i+horizon+1):
            hi=float(df.high.iloc[j]);lo=float(df.low.iloc[j]); ht=(hi>=target if direction=="bullish" else lo<=target); hs=(lo<=stop if direction=="bullish" else hi>=stop)
            if ht and hs:a+=1;result=2;break
            if ht:t+=1;result=1;break
            if hs:s+=1;result=-1;break
        if result==0:n+=1
    decided=t+s; w=t/decided if decided else np.nan; lo,hi=wilson(t,decided) if decided else (np.nan,np.nan)
    return {"events":int(len(pos)),"target_first":t,"stop_first":s,"ambiguous":a,"no_hit":n,"decided_win_rate":w,"wilson_low":lo,"wilson_high":hi}


def event_catalog(df:pd.DataFrame)->dict[str,str]:
    events={
        "bull_sfp":"bullish","bear_sfp":"bearish","bull_spring":"bullish","bear_upthrust":"bearish",
        "bull_bos":"bullish","bear_bos":"bearish","bull_choch":"bullish","bear_choch":"bearish",
