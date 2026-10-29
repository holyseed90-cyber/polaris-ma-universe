"""Public market-data collection only. No credentials, accounts, orders, or strategy tuning."""
from __future__ import annotations
import csv, gzip, hashlib, io, json, time, zipfile
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen, Request

OUT = Path('research/polaris_v16/raw')
OUT.mkdir(parents=True, exist_ok=True)
END = date(2026, 10, 28)
MARKETS = [('NEARUSDT','spot',2020,10), ('AKTUSDT','futures/um',2024,11), ('ONDOUSDT','futures/um',2024,1)]
FIELDS = ['open_time','open','high','low','close','volume','close_time','quote_volume','trades','taker_buy_base','taker_buy_quote','ignore']

def fetch(url):
    last = None
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers={'User-Agent':'Polaris-public-data-audit/1.6'}), timeout=25) as r:
                return r.read()
        except Exception as exc:
            last = exc
            if attempt == 0: time.sleep(0.3)
    raise last

def tasks():
    out=[]
    for symbol,market,y,m in MARKETS:
        while (y,m) < (2026,10):
            stamp=f'{y:04d}-{m:02d}'
            url=f'https://data.binance.vision/data/{market}/monthly/klines/{symbol}/1d/{symbol}-1d-{stamp}.zip'
            out.append((symbol,market,url))
            m+=1
            if m==13: y,m=y+1,1
        for d in range(1,29):
            stamp=f'2026-10-{d:02d}'
            url=f'https://data.binance.vision/data/{market}/daily/klines/{symbol}/1d/{symbol}-1d-{stamp}.zip'
            out.append((symbol,market,url))
    return out

def one(task):
    symbol,market,url=task
    rec={'symbol':symbol,'market':market,'url':url,'fetched_at_utc':datetime.now(timezone.utc).isoformat()}
    try:
        raw=fetch(url); check=fetch(url+'.CHECKSUM')
        actual=hashlib.sha256(raw).hexdigest(); expected=check.decode().split()[0]
        if actual.lower()!=expected.lower(): raise ValueError('CHECKSUM mismatch')
        folder=OUT/'archive'/symbol; folder.mkdir(parents=True,exist_ok=True)
        name=url.rsplit('/',1)[1]
        (folder/name).write_bytes(raw); (folder/(name+'.CHECKSUM')).write_bytes(check)
        rows=[]
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=[n for n in z.namelist() if n.endswith('.csv')]
            if len(names)!=1: raise ValueError('Unexpected CSV member count')
            for row in csv.reader(io.StringIO(z.read(names[0]).decode('utf-8-sig'))):
                if not row: continue
                try: ts=int(row[0])
                except ValueError: continue
                if len(row)!=12: raise ValueError('Unexpected column count')
                unit='us' if ts>10**14 else 'ms'
                row[0]=str(ts//1000 if unit=='us' else ts)
                ct=int(row[6]); row[6]=str(ct//1000 if ct>10**14 else ct)
                rows.append(row)
        rec.update(status='ok',sha256=actual,rows=len(rows),file=str(folder/name))
        return rec,rows
    except Exception as exc:
        rec.update(status='error',error=repr(exc))
        return rec,[]

manifest=[]; bysymbol={s:[] for s,*_ in MARKETS}
with ThreadPoolExecutor(max_workers=8) as pool:
    for rec,rows in pool.map(one,tasks()):
        manifest.append(rec); bysymbol[rec['symbol']].extend(rows)
coverage=[]
for symbol,market,*_ in MARKETS:
    rows=sorted(bysymbol[symbol],key=lambda r:int(r[0]))
    rows=[r for r in rows if datetime.fromtimestamp(int(r[0])/1000,timezone.utc).date()<=END]
    times=[int(r[0]) for r in rows]
    duplicates=len(times)-len(set(times))
    bad=[]
    for r in rows:
        o,h,l,c,v=map(float,r[1:6])
        if min(o,h,l,c)<=0 or l>min(o,c) or h<max(o,c) or h<l or v<0: bad.append(r[0])
    missing=[]
    if times:
        present=set(times)
        missing=[t for t in range(times[0],times[-1]+1,86400000) if t not in present]
    path=OUT/f'{symbol}_{market.replace("/","_")}_1d.csv.gz'
    with gzip.open(path,'wt',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(FIELDS);w.writerows(rows)
    coverage.append({'symbol':symbol,'market':market,'bars':len(rows),'first_open_ms':times[0] if times else None,'last_open_ms':times[-1] if times else None,'duplicates':duplicates,'bad_ohlc':bad,'missing_open_ms':missing,'data_file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'first_trading_day_may_be_partial':True})
(OUT/'download_manifest.json').write_text(json.dumps(manifest,indent=2))
(OUT/'coverage.json').write_text(json.dumps(coverage,indent=2))
print(json.dumps(coverage,indent=2))
if any(r['status']!='ok' for r in manifest):
    raise SystemExit('One or more archives unavailable; retained partial data and failure manifest. Do not fill gaps.')
if any(r['duplicates'] or r['bad_ohlc'] or r['missing_open_ms'] for r in coverage):
    raise SystemExit('Coverage audit failed; do not use uninterrupted rolling indicators across gaps.')
