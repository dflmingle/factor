#!/usr/bin/env python3
"""Resumable Tushare historical extension in an isolated research data tree.

Credentials come only from env or a mode-0600 file outside the repository.
Neither existing qfq snapshots nor the formal alignment configuration change.
"""
from __future__ import annotations
import argparse, hashlib, json, os, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import tushare as ts
import tushare_financial_cache as finance
import quant_corpus_local_20261012 as q

ROOT=q.ROOT
OUT=ROOT/'research_reports/platform_alignment/regime-long-history-20261014'
DATA=q.CACHE/'regime_long_history_20060101_v1'
STATE=threading.local();LOCK=threading.Lock();NEXT=0.
MIN_INTERVAL=.27

def credential():
    val=os.environ.get('TUSHARE_TOKEN','').strip()
    if not val:
        p=Path.home()/'.config/factor-research/tushare.token'
        if p.exists():val=p.read_text().strip()
    if not val:raise RuntimeError('Tushare credential missing')
    return val

def slot():
    global NEXT
    with LOCK:
        wait=NEXT-time.monotonic()
        if wait>0:time.sleep(wait)
        NEXT=time.monotonic()+MIN_INTERVAL

def query(api,**args):
    token=credential()
    if not hasattr(STATE,'client'):STATE.client=ts.pro_api(token)
    for attempt in range(5):
        slot()
        try:return STATE.client.query(api,**args)
        except Exception as e:
            msg=str(e).replace(token,'<redacted>')[:300]
            if '权限' in msg or 'permission' in msg.lower():raise RuntimeError(f'{api}: {msg}')
            if attempt==4:raise RuntimeError(f'{api}: {msg}')
            time.sleep(min(10,2**attempt))

def save(frame,path,metadata):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.parquet.tmp');frame.to_parquet(tmp,index=False);tmp.replace(path)
    metadata.update(rows=len(frame),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),status='complete')
    path.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')

def ready(path):return path.exists() and path.with_suffix('.json').exists()

def task(api,args,path):
    if ready(path):return {'api':api,'path':str(path),'reused':True,'rows':None}
    x=query(api,**args)
    # Tushare's per-call limit must never silently cut a whole market day.
    if api=='stk_factor' and len(x)>=10000:raise RuntimeError('stk_factor result may be truncated')
    if api=='daily_basic' and len(x)>=6000:raise RuntimeError('daily_basic result may be truncated')
    if api in ['stk_factor','daily_basic'] and x.empty:raise RuntimeError(f'{api} unexpectedly empty for {args}')
    save(x,path,{'api':api,'parameters':args,'retrieved_utc':pd.Timestamp.now(tz='UTC').isoformat()})
    return {'api':api,'path':str(path),'reused':False,'rows':len(x)}

def fetch_fin(period,endpoint):
    api=finance.ENDPOINTS[endpoint]['api'];path=DATA/'financial_full_a'/endpoint/f'period_{period}.parquet'
    if ready(path):return {'api':api,'period':period,'reused':True}
    frames=[];offset=0
    while True:
        x=query(api,period=period,limit=5000,offset=offset)
        frames.append(x)
        if len(x)<5000:break
        offset+=len(x)
        if offset>150000:raise RuntimeError(f'pagination exceeded reasonable bound: {api} {period}')
    x=pd.concat(frames,ignore_index=True)
    save(x,path,{'api':api,'period':period,'pagination_rows':offset,'retrieved_utc':pd.Timestamp.now(tz='UTC').isoformat()})
    return {'api':api,'period':period,'rows':len(x),'reused':False}

def main():
    OUT.mkdir(parents=True,exist_ok=True);DATA.mkdir(parents=True,exist_ok=True)
    # Resolve endpoint access once. No tokens appear in the stored metadata.
    diagnostics=[]
    for api,args in [('trade_cal',dict(exchange='SSE',start_date='20060101',end_date='20060131')),('stk_factor',dict(ts_code='000001.SZ',start_date='20060101',end_date='20060301')),('daily_basic',dict(trade_date='20060104')),('fina_indicator_vip',dict(period='20060331',limit=5000)),('yc_cb',dict(ts_code='1001.CB',start_date='20060101',end_date='20060131')),('shibor',dict(start_date='20060101',end_date='20061231'))]:
        try:x=query(api,**args);diagnostics.append({'api':api,'available':True,'rows':len(x)})
        except RuntimeError as e:diagnostics.append({'api':api,'available':False,'reason':str(e)})
    (OUT/'endpoint_permissions.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+'\n')
    print('PERMISSIONS',diagnostics,flush=True)
    frames=[]
    for year in range(2006,2027):
        path=DATA/'trade_calendar'/f'{year}.parquet'
        if not ready(path):task('trade_cal',dict(exchange='SSE',start_date=f'{year}0101',end_date=f'{year}1231'),path)
        x=pd.read_parquet(path);frames.append(x)
    cal=pd.concat(frames,ignore_index=True);d=pd.to_datetime(cal.cal_date.astype(str));dates=sorted(d[(cal.is_open==1)&(d<'2018-01-01')].unique())
    jobs=[]
    for date in dates:
        date=pd.Timestamp(date).strftime('%Y%m%d')
        jobs.extend([('stk_factor',dict(trade_date=date),DATA/'stk_factor'/f'{date}.parquet'),('daily_basic',dict(trade_date=date),DATA/'daily_basic'/f'{date}.parquet')])
    # Three overlap anchors validate per-symbol qfq scaling against immutable
    # saved snapshots, instead of mixing providers' rebasing dates silently.
    for date in ['20180102','20180629','20181228']:
        jobs.append(('stk_factor',dict(trade_date=date),DATA/'qfq_overlap_anchors'/f'{date}.parquet'))
    for symbol in ['000001.SH','000300.SH','000905.SH','399001.SZ','399006.SZ']:
        for year in range(2006,2027):
            jobs.append(('index_daily',dict(ts_code=symbol,start_date=f'{year}0101',end_date=min(f'{year}1231','20261014')),DATA/'index_daily'/symbol/f'{year}.parquet'))
    for year in range(2006,2027):jobs.append(('shibor',dict(start_date=f'{year}0101',end_date=min(f'{year}1231','20261014')),DATA/'shibor'/f'{year}.parquet'))
    (OUT/'download_plan.json').write_text(json.dumps({'data_root':str(DATA.relative_to(ROOT)),'history_start':'20060101','formal_window_unchanged':['20210907','20260907'],'preserve_existing_snapshots':True,'api_jobs':len(jobs),'pre2018_trading_days':len(dates),'financial_periods':48,'financial_endpoints':list(finance.ENDPOINTS),'financial_pagination':True,'query_rate_interval_seconds':MIN_INTERVAL,'credential_in_repository':False},ensure_ascii=False,indent=2)+'\n')
    print('PLAN',len(jobs),'queries before finance',len(dates),'historical dates',flush=True)
    done=[];errors=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(task,*job):job for job in jobs}
        for i,f in enumerate(as_completed(futures),1):
            try:done.append(f.result())
            except Exception as e:
                api,args,path=futures[f];errors.append({'api':api,'parameters':args,'path':str(path.relative_to(ROOT)),'error':str(e)})
            if i%100==0:
                print('PRICE_PROGRESS',i,'/',len(jobs),'failures',len(errors),flush=True)
                (OUT/'download_progress.json').write_text(json.dumps({'stage':'price_and_environment','done':i,'total':len(jobs),'failures':errors,'completed':False},ensure_ascii=False,indent=2)+'\n')
    periods=pd.period_range('2006Q1','2017Q4',freq='Q')
    fj=[(p.end_time.strftime('%Y%m%d'),api) for p in periods for api in finance.ENDPOINTS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(fetch_fin,*job):job for job in fj}
        for i,f in enumerate(as_completed(fs),1):
            try:done.append(f.result())
            except Exception as e:errors.append({'financial_job':fs[f],'error':str(e)})
            if i%20==0:print('FINANCIAL_PROGRESS',i,'/',len(fj),'failures',len(errors),flush=True)
    (OUT/'download_errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n')
    (OUT/'download_progress.json').write_text(json.dumps({'stage':'finished','price_jobs':len(jobs),'financial_jobs':len(fj),'completed':not errors,'failures':errors,'historical_trading_days':len(dates)},ensure_ascii=False,indent=2)+'\n')
    print('DOWNLOAD_FINISHED',len(done),'failures',len(errors),flush=True)
    if errors:raise RuntimeError('Historical download incomplete; see redacted error ledger')

if __name__=='__main__':main()
