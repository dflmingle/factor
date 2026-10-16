#!/usr/bin/env python3
"""Fetch explicit research fields: VIP defaults omit several required columns."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import tushare_regime_long_history_20261014 as download
import quant_corpus_local_20261012 as q

def fetch(period,endpoint):
    cfg=download.finance.ENDPOINTS[endpoint]
    path=download.DATA/'financial_full_fields_v2'/endpoint/f'period_{period}.parquet'
    if download.ready(path):return
    fields=cfg['fields'];frames=[];offset=0
    while True:
        x=download.query(cfg['api'],period=period,fields=fields,limit=5000,offset=offset);frames.append(x)
        if len(x)<5000:break
        offset+=len(x)
        if offset>150000:raise RuntimeError('Financial pagination exceeded guard')
    frame=pd.concat(frames,ignore_index=True)
    missing=set(q.FIN_FIELDS[endpoint])-set(frame.columns)
    if missing:raise ValueError(f'{endpoint}: requested research fields still absent {sorted(missing)}')
    download.save(frame,path,dict(api=cfg['api'],period=period,fields=fields,pagination_rows=offset,retrieved_utc=pd.Timestamp.now(tz='UTC').isoformat(),explicit_fields_required=True))

def main():
    jobs=[(p.end_time.strftime('%Y%m%d'),e) for p in pd.period_range('2006Q1','2017Q4',freq='Q') for e in download.finance.ENDPOINTS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs=[pool.submit(fetch,*job) for job in jobs]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%25==0:print('FULL_FINANCIAL_FIELDS',i,'/',len(jobs),flush=True)
    print('FULL_FINANCIAL_FIELDS_FINISHED',flush=True)

if __name__=='__main__':main()
