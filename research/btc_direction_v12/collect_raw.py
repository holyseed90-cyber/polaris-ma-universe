"""Collect only public Binance spot BTCUSDT data. No credentials or trading.
Fixed requested end: 2026-10-28 UTC. Keep all errors and original ZIP/checksum bytes.
This is data recovery, not a prediction or strategy optimization.
"""
from __future__ import annotations
import concurrent.futures as cf
import hashlib
import io
import json
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

ROOT = Path('research/btc_direction_v12/output')
RAW = ROOT / 'archive'
RAW.mkdir(parents=True, exist_ok=True)
CUTOFF = pd.Timestamp('2026-10-29T00:00:00Z')
COLS = ['open_time','open','high','low','close','volume','close_time','quote_volume','trades','taker_buy_base','taker_buy_quote','ignore']

def fetch(task):
    interval, frequency, stamp = task
    name = f'BTCUSDT-{interval}-{stamp}.zip'
    url = f'https://data.binance.vision/data/spot/{frequency}/klines/BTCUSDT/{interval}/{name}'
    record = {'url':url,'interval':interval,'stamp':stamp,'frequency':frequency,'requested_at_utc':datetime.now(timezone.utc).isoformat()}
    try:
        r = requests.get(url, timeout=35)
        record['http_status'] = r.status_code
        if r.status_code != 200:
            record['error'] = r.text[:250]
            return record, None
        c = requests.get(url+'.CHECKSUM', timeout=35)
        c.raise_for_status()
        expected = c.text.split()[0].lower()
        actual = hashlib.sha256(r.content).hexdigest()
        record.update(sha256=actual, expected_sha256=expected, checksum_ok=(actual==expected), bytes=len(r.content))
        if actual != expected:
            raise ValueError('checksum mismatch')
        (RAW/name).write_bytes(r.content)
        (RAW/(name+'.CHECKSUM')).write_bytes(c.content)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            members = [n for n in z.namelist() if n.endswith('.csv')]
            if len(members) != 1: raise ValueError('unexpected archive members')
            df = pd.read_csv(z.open(members[0]), header=None, names=COLS)
        for col in COLS: df[col] = pd.to_numeric(df[col], errors='raise')
        op = df['open_time'].astype('int64')
        cl = df['close_time'].astype('int64')
        unit = 'us' if int(op.median()) > 10**14 else 'ms'
        df['open_time'] = pd.to_datetime(op, unit=unit, utc=True)
        df['reported_close_time'] = pd.to_datetime(cl, unit=unit, utc=True)
        duration = pd.Timedelta(days=1) if interval=='1d' else pd.Timedelta(hours=4)
        df['available_at'] = df['open_time'] + duration
        df['source_archive'] = name
        df = df[df['available_at'] <= CUTOFF].copy()
        record.update(rows=len(df),timestamp_unit=unit,start=str(df.open_time.min()),end=str(df.open_time.max()))
        return record, df
    except Exception as e:
        record['error'] = repr(e)
        return record, None

months = pd.period_range('2017-08','2026-09',freq='M')
days = pd.date_range('2026-10-01','2026-10-28',freq='D')
tasks = [(tf,'monthly',str(m)) for tf in ['1d','4h'] for m in months]
tasks += [(tf,'daily',d.strftime('%Y-%m-%d')) for tf in ['1d','4h'] for d in days]
logs=[]
frames={'1d':[],'4h':[]}
with cf.ThreadPoolExecutor(max_workers=4) as pool:
    for i,(log,df) in enumerate(pool.map(fetch,tasks),1):
        logs.append(log)
        if df is not None: frames[log['interval']].append(df)
        if i%20==0: print(f'{i}/{len(tasks)} files; accepted={sum(x.get("checksum_ok",False) for x in logs)}', flush=True)
(ROOT/'download_manifest.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2))
quality={}
for tf,parts in frames.items():
    if not parts:
        quality[tf]={'status':'no_data'}
        continue
    df=pd.concat(parts,ignore_index=True).sort_values('open_time').reset_index(drop=True)
    duplicates=df[df.open_time.duplicated(keep=False)]
    if len(duplicates): duplicates.to_csv(ROOT/f'{tf}_duplicates.csv',index=False)
    # Never silently overwrite conflicting records.
    if len(duplicates): raise ValueError(f'{tf}: duplicate timestamps')
    invalid=(df.low>df[['open','close']].min(axis=1)) | (df.high<df[['open','close']].max(axis=1)) | (df.low>df.high) | (df[['open','high','low','close']]<=0).any(axis=1) | (df.volume<0)
    if invalid.any():
        df.loc[invalid].to_csv(ROOT/f'{tf}_invalid.csv',index=False)
        raise ValueError(f'{tf}: invalid OHLCV')
    freq='1D' if tf=='1d' else '4h'
    expected=pd.date_range(df.open_time.min(),df.open_time.max(),freq=freq)
    missing=expected.difference(pd.DatetimeIndex(df.open_time))
    pd.DataFrame({'missing_open_time':missing}).to_csv(ROOT/f'{tf}_missing.csv',index=False)
    out=ROOT/f'BTCUSDT_spot_{tf}.csv.gz'
    df.to_csv(out,index=False,compression='gzip')
    quality[tf]={'status':'ok_with_gaps' if len(missing) else 'ok','rows':len(df),'start':str(df.open_time.min()),'end':str(df.open_time.max()),'missing_bars':len(missing),'duplicates':len(duplicates),'invalid_ohlcv':int(invalid.sum()),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
quality.update(requested_cutoff_exclusive=str(CUTOFF),venue='Binance spot BTCUSDT',no_splicing=True,no_imputation=True,accepted_archives=sum(x.get('checksum_ok',False) for x in logs),failed_archives=sum('error' in x for x in logs),retrieved_at_utc=datetime.now(timezone.utc).isoformat())
(ROOT/'data_quality.json').write_text(json.dumps(quality,indent=2))
shutil.copy(__file__,ROOT/'collector_used.py')
print(json.dumps(quality,indent=2),flush=True)
if any(quality.get(tf,{}).get('rows',0)==0 for tf in ['1d','4h']):
    raise RuntimeError('One or more required streams unavailable; inspect manifest, do not fabricate rows.')
