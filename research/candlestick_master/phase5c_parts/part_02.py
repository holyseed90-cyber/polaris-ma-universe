 = vwma > vwma.shift(3)

    ema12 = x.close.ewm(span=12, adjust=False, min_periods=26).mean()
    ema26 = x.close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    z["macd"] = macd
    z["macd_signal"] = macd_signal
    z["macd_hist"] = macd - macd_signal
    ll14, hh14 = x.low.rolling(14).min(), x.high.rolling(14).max()
    k = 100 * (x.close - ll14) / (hh14 - ll14).replace(0, np.nan)
    d = k.rolling(3).mean()
    z["stoch_k"] = k
    z["stoch_d"] = d
    tr_sum = true_range(x).rolling(14).sum()
    z["chop14"] = 100 * np.log10(tr_sum / (hh14 - ll14).replace(0, np.nan)) / np.log10(14)
    z["supertrend_state"] = supertrend_state(x)
    z["psar_state"] = psar_state(x)
    return z


def side_indicator_flags(row: pd.Series, side: str, prefix: str = "") -> dict[str, bool]:
    long_side = side == "long"
    get = lambda name, default=np.nan: row.get(f"{prefix}{name}", default)
    bull = long_side
    flags = {
        "i_ichi_cloud": bool(get("ichi_bull_cloud", False) if bull else get("ichi_bear_cloud", False)),
        "i_ichi_full": bool(get("ichi_bull_full", False) if bull else get("ichi_bear_full", False)),
        "i_ichi_kijun": bool(get("ichi_bull_kijun", False) if bull else get("ichi_bear_kijun", False)),
        "i_ichi_break_recent": bool(get("ichi_bull_break_recent", False) if bull else get("ichi_bear_break_recent", False)),
        "i_dmi_align": bool(get("dmi_bull", False) if bull else get("dmi_bear", False)),
        "i_adx20": bool((get("adx14", np.nan) >= 20) and (get("dmi_bull", False) if bull else get("dmi_bear", False))),
        "i_adx25_rising": bool((get("adx14", np.nan) >= 25) and get("adx_rising", False) and (get("dmi_bull", False) if bull else get("dmi_bear", False))),
        "i_bb_trend": bool((get("bb_pctb", np.nan) >= 0.55 and get("bb_width_rising", False)) if bull else (get("bb_pctb", np.nan) <= 0.45 and get("bb_width_rising", False))),
        "i_bb_squeeze_release": bool(get("bb_bull_release", False) if bull else get("bb_bear_release", False)),
        "i_chop_trend": bool(get("chop14", np.nan) < 50),
        "i_cmf05": bool(get("cmf20", np.nan) >= 0.05 if bull else get("cmf20", np.nan) <= -0.05),
        "i_cmf_rising": bool((get("cmf20", np.nan) > 0 and get("cmf_rising", False)) if bull else (get("cmf20", np.nan) < 0 and not get("cmf_rising", True))),
        "i_obv_slope": bool(get("obv_norm10", np.nan) > 0.05 if bull else get("obv_norm10", np.nan) < -0.05),
        "i_mfi_align": bool(50 <= get("mfi14", np.nan) <= 85 if bull else 15 <= get("mfi14", np.nan) <= 50),
        "i_vwma_align": bool((get("close", np.nan) > get("vwma20", np.nan) and get("vwma_rising", False)) if bull else (get("close", np.nan) < get("vwma20", np.nan) and not get("vwma_rising", True))),
        "i_supertrend": bool(get("supertrend_state", 0) > 0 if bull else get("supertrend_state", 0) < 0),
        "i_psar": bool(get("psar_state", 0) > 0 if bull else get("psar_state", 0) < 0),
        "i_macd": bool((get("macd", np.nan) > get("macd_signal", np.nan) and get("macd_hist", np.nan) > 0) if bull else (get("macd", np.nan) < get("macd_signal", np.nan) and get("macd_hist", np.nan) < 0)),
        "i_stoch": bool((get("stoch_k", np.nan) > get("stoch_d", np.nan) and get("stoch_k", np.nan) < 85) if bull else (get("stoch_k", np.nan) < get("stoch_d", np.nan) and get("stoch_k", np.nan) > 15)),
    }
    return flags


def add_indicator_features(events: pd.DataFrame, frames: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    out_parts = []
    for tf in ["4h", "1d"]:
        e = events[events.timeframe == tf].copy()
        primary = frames[PRIMARY][tf].copy()
        spot = frames[SPOT][tf].copy()
        ip = indicator_frame(primary)
        ip["close"] = primary.close.to_numpy()
        isp = indicator_frame(spot)
        isp["close"] = spot.close.to_numpy()
        ip = ip.reset_index(drop=True).set_index("signal_time")
        isp = isp.reset_index(drop=True).set_index("signal_time").add_prefix("spot_")
        rows = []
        for r in e.itertuples(index=False):
            ts = pd.Timestamp(r.signal_time)
            if ts not in ip.index:
                continue
            pr = ip.loc[ts]
            if isinstance(pr, pd.DataFrame):
                pr = pr.iloc[-1]
            merged = dict(r._asdict())
            merged.update(side_indicator_flags(pr, r.side))
            if ts in isp.index:
                sr = isp.loc[ts]
                if isinstance(sr, pd.DataFrame):
                    sr = sr.iloc[-1]
                sf = side_indicator_flags(sr, r.side, prefix="spot_")
                merged["i_spot_ichi"] = sf["i_ichi_full"]
                merged["i_spot_dmi"] = sf["i_adx20"]
              