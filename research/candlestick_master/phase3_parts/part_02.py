        [(x.ma224>x.ma448)&(x.ma448>x.ma896), (x.ma224<x.ma448)&(x.ma448<x.ma896)],
        ["long_bull_stack","long_bear_stack"], default="long_mixed")
    x["rsi_state"] = pd.cut(x.rsi14, [-np.inf,30,40,50,60,70,np.inf], labels=["lt30","30_40","40_50","50_60","60_70","ge70"], right=False).astype("string")
    x["signal_time"] = x.index + pd.to_timedelta(hours, unit="h")
    return x


def detect_structure_events(x: pd.DataFrame) -> pd.DataFrame:
    """Event definitions based on already-confirmed swing levels."""
    y = x.copy()
    ph = y.last_pivot_high.shift(1); pl = y.last_pivot_low.shift(1)
    tol = .10 * y.atr14
    # Swing failure / liquidity sweep at confirmed swing levels.
    y["bull_sfp"] = (y.low < pl - tol) & (y.close > pl) & (y.close_location >= .55)
    y["bear_sfp"] = (y.high > ph + tol) & (y.close < ph) & (y.close_location <= .45)
    y["bull_spring"] = y.bull_sfp & (y.lower_ratio >= .35) & (y.range_atr >= .8)
    y["bear_upthrust"] = y.bear_sfp & (y.upper_ratio >= .35) & (y.range_atr >= .8)
    # Close-confirmed structure breaks.
    y["bull_bos"] = (y.close > ph + .05*y.atr14) & (y.close.shift(1) <= ph.shift(1) + .05*y.atr14.shift(1))
    y["bear_bos"] = (y.close < pl - .05*y.atr14) & (y.close.shift(1) >= pl.shift(1) - .05*y.atr14.shift(1))
    # Approximate prevailing swing trend from last two confirmed pivot values.
    last_hi = y.pivot_high_confirmed.ffill(); prev_hi = last_hi.where(y.pivot_high_confirmed.notna()).ffill().shift(1)
    last_lo = y.pivot_low_confirmed.ffill(); prev_lo = last_lo.where(y.pivot_low_confirmed.notna()).ffill().shift(1)
    y["swing_up"] = (last_hi > prev_hi) & (last_lo > prev_lo)
    y["swing_down"] = (last_hi < prev_hi) & (last_lo < prev_lo)
    y["bull_choch"] = y.bull_bos & y.swing_down.shift(1).fillna(False)
    y["bear_choch"] = y.bear_bos & y.swing_up.shift(1).fillna(False)
    # False breakout of rolling 20-bar extremes, independent of pivots.
    h20 = y.high.shift(1).rolling(20, min_periods=20).max(); l20 = y.low.shift(1).rolling(20, min_periods=20).min()
    y["low_sweep20"] = (y.low < l20) & (y.close > l20)
    y["high_sweep20"] = (y.high > h20) & (y.close < h20)
    # Three-candle fair value gaps (known at current close).
    y["bull_fvg"] = y.low > y.high.shift(2)
    y["bear_fvg"] = y.high < y.low.shift(2)
    y["bull_fvg_low"] = y.high.shift(2).where(y.bull_fvg)
    y["bull_fvg_high"] = y.low.where(y.bull_fvg)
    y["bear_fvg_low"] = y.high.where(y.bear_fvg)
    y["bear_fvg_high"] = y.low.shift(2).where(y.bear_fvg)
    # Range contraction followed by expansion.
    range_med = y.range_atr.rolling(50, min_periods=20).median()
    y["contraction"] = y.range_atr.rolling(4).mean() < .65*range_med
    y["bull_expansion"] = y.contraction.shift(1).fillna(False) & (y.range_atr>=1.4) & (y.close_location>=.75) & (y.close>y.open)
    y["bear_expansion"] = y.contraction.shift(1).fillna(False) & (y.range_atr>=1.4) & (y.close_location<=.25) & (y.close<y.open)
    return y


def add_retests(x: pd.DataFrame, max_wait: int = 12) -> pd.DataFrame:
    """Label first retest after each structure break; results are timestamp-local."""
    y=x.copy()
    for side in ["bull","bear"]:
        y[f"{side}_retest_hold"] = False
        y[f"{side}_retest_fail"] = False
    # Loop is acceptable at ~76k rows and gives explicit event semantics.
    close=y.close.to_numpy(); high=y.high.to_numpy(); low=y.low.to_numpy(); atr=y.atr14.to_numpy()
    bull=y.bull_bos.fillna(False).to_numpy(); bear=y.bear_bos.fillna(False).to_numpy()
    ph=y.last_pivot_high.shift(1).to_numpy(); pl=y.last_pivot_low.shift(1).to_numpy()
    brh=np.flatnonzero(bull); brl=np.flatnonzero(bear)
    hold_b=np.zeros(len(y),dtype=bool); fail_b=np.zeros(len(y),dtype=bool); hold_s=np.zeros(len(y),dtype=bool); fail_s=np.zeros(len(y),dtype=bool)
    for i in brh:
        level=ph[i]
        if not np.isfinite(level): continue
        for j in range(i+1,min(len(y),i+max_wait+1)):
            if low[j] <= level + .25*atr[j]:
                if close[j] >= level: hold_b[j]=True
                else: fail_b[j]=True
                break
    for i in brl:
        level=pl[i]
        if not np.isfinite(level): continue
        for j in range(i+1,min(len(y),i+max_wait+1)):
            if high[j] >= level - .25*atr[j]:
                if close[j] <= level: hold_s[j]=True
                else: fail_s[j]=True
                break
    y["bull_retest_hold"]=hold_b; y["bull_retest_fail"]=fail_b; y["bear_retest_hold"]=hold_s; y["bear_retest_fail"]=fail_s
