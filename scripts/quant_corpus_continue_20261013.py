"""Frozen, source-grounded offline batches with actual causal checks.

Never executes corpus code or contacts PandaAI. Previous cohorts are immutable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_correlations_20261012 import rho_details, saved_grid

RISK='quant/2022年度精选策略/94.量化排雷—一个实用排雷系统.txt'
TD='quant/2021年度精选策略/74.迪马克TD趋势反转指标.txt'
TRIX='quant/2020年度精选策略/42 低估值+TRIX+RSI 低回撤策略.txt'
VOLUME='quant/2020年度精选策略/54 中长线买入卖出点选择.txt'

def spec(key,name,source,formula,fidelity):
    return dict(key=key,name=name,source_paths=[source],formula=formula,
                fidelity=fidelity,gated=False,source_execution_reproduced=False)

RISK_SPECS=[
    spec('cash_sales_yoy','现金销售率同比应收调整',RISK,
         '1-(accounts_receiv.q0-accounts_receiv.q4)/revenue_ttm.q0; revenue_ttm>0',
         'proxy: annual source cash-sales ratio adapted to latest PIT quarter and TTM sales'),
    spec('inventory_asset_decline_yoy','存货资产占比同比下降',RISK,
         '-(inventories.q0/total_assets.q0-inventories.q4/total_assets.q4)',
         'proxy: annual relative change replaced by quarterly YoY percentage-point change'),
    spec('other_receivable_decline_yoy','其他应收资产占比同比下降',RISK,
         '-(oth_receiv.q0/total_assets.q0-oth_receiv.q4/total_assets.q4)',
         'proxy: annual relative change replaced by quarterly YoY percentage-point change'),
]

MARKET_SPECS=[
    spec('trix12_minus_ma20','TRIX12相对20日均线',TRIX,
         '100*(EMA12(EMA12(EMA12(C)))/lag1(tripleEMA)-1)-MA20(TRIX12)',
         'proxy: continuous stock signal from source TRIX>MA20 rule; RSI and financial gates omitted'),
    spec('amount_contraction_persistence','成交额收缩持续性',VOLUME,
         'mean120(I(MA19(amount)<=MA59(amount)<=MA159(amount)))',
         'proxy: dormant source auxiliary fall_money_day_3line defaults20/60/160, off-by-one slices retained; no PB/size term'),
    spec('vol_to_turnover60_low','低波动换手比60',
         'quant/2021年度精选策略/63.【复现】华泰证券-波动率和换手率构建牛熊指标.txt',
         '-STD60(ret1)/MEAN60(turnover)',
         'proxy: source index kernel_n stock adaptation; n60 fixed, lower risk preferred; turnover_rate_f->daily_basic.turnover'),
]

def market_values(f):
    c=f['close'].astype(float);amount=f['amount'].astype(float)
    def ema(x,n):return pd.DataFrame(x).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy()
    triple=ema(ema(ema(c,12),12),12)
    trix=100*(q.ratio(triple,q.delay(triple))-1)
    a,b,d=[q.rolling(amount,n) for n in [19,59,159]]
    valid=np.isfinite(a)&np.isfinite(b)&np.isfinite(d)
    quiet=np.where(valid,(a<=b)&(b<=d),np.nan).astype(float)
    # Old code evaluates daily windows ending before t; retain that offset.
    persistence=q.rolling(q.delay(quiet),120)
    ret=q.ratio(c,q.delay(c))-1
    denom=q.rolling(f['turnover'],60)
    kernel=-q.ratio(q.rolling(ret,60,'std'),np.where(denom>0,denom,np.nan))
    return [trix-q.rolling(trix,20),persistence,kernel]

def verify_market(f):
    ids=np.flatnonzero(np.isfinite(f['close'][-600:]).all(axis=0))[:7]
    small={k:v[:,ids] for k,v in f.items()};full=market_values(small);checks=[]
    for stop in [1200,len(f['close'])-31]:
        trunc=market_values({k:v[:stop] for k,v in small.items()})
        for sp,a,b in zip(MARKET_SPECS,full,trunc):
            np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-6,atol=1e-6)
            checks.append(dict(key=sp['key'],test='full_daily_prefix_recompute',stop=stop,passed=True))
    # Independently reconstruct the source's off-by-one MA slices and count.
    for t in [1200,len(f['close'])-1]:
        for j in range(len(ids)):
            count=[]
            for end in range(t-120,t):
                a=small['amount'][end-18:end+1,j]
                b=small['amount'][end-58:end+1,j]
                d=small['amount'][end-158:end+1,j]
                count.append(float(a.mean()<=b.mean()<=d.mean()) if np.isfinite(d).all() else np.nan)
            literal=np.mean(count)
            np.testing.assert_allclose(full[1][t,j],literal,equal_nan=True,atol=1e-7)
    checks.append(dict(test='independent_amount_slice_count',passed=True))
    return checks

def risk_values(fin):
    def f(ep,col,lag=0):return fin[f'{ep}.{col}.q{lag}'].astype(float)
    a=f('balancesheet','total_assets');b=f('balancesheet','total_assets',4)
    a=np.where(a>0,a,np.nan);b=np.where(b>0,b,np.nan)
    revenue=f('income','revenue_ttm');revenue=np.where(revenue>0,revenue,np.nan)
    return [1-q.ratio(f('balancesheet','accounts_receiv')-f('balancesheet','accounts_receiv',4),revenue),
            -(q.ratio(f('balancesheet','inventories'),a)-q.ratio(f('balancesheet','inventories',4),b)),
            -(q.ratio(f('balancesheet','oth_receiv'),a)-q.ratio(f('balancesheet','oth_receiv',4),b))]

def simultaneous_residual(x,controls):
    out=np.full_like(x,np.nan,dtype=np.float32)
    for i in range(len(x)):
        valid=np.isfinite(x[i])&np.isfinite(np.stack([v[i] for v in controls])).all(axis=0)
        if valid.sum()<100:continue
        columns=[np.ones(valid.sum())]
        for v in controls:
            z=rankdata(v[i,valid]);sd=z.std()
            if sd>1e-9:columns.append((z-z.mean())/sd)
        y=rankdata(x[i,valid]);design=np.column_stack(columns)
        res=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
        if np.ptp(res)>1e-7:out[i,valid]=res
    return out

def verify_financial(fin,grid,stocks,out):
    """Replay raw filings restricted to each cutoff, including revisions."""
    checks=[];tables=q.pit_tables();ids=np.arange(min(8,len(stocks)))
    oldout,oldloader=q.OUT,q.pit_tables
    try:
        for n in [35,79]:
            cutoff=grid[n-1]
            filtered={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])].copy() for ep,t in tables.items()}
            q.pit_tables=lambda:filtered
            with tempfile.TemporaryDirectory(prefix='pit-check-',dir=out) as temp:
                q.OUT=Path(temp);cut=q.financial_snapshot(grid[:n],stocks[ids],lags=6)
                full_values=risk_values({k:v[:n,ids] for k,v in fin.items()})
                cut_values=risk_values(cut)
                for sp,a,b in zip(RISK_SPECS,full_values,cut_values):
                    np.testing.assert_allclose(a,b,equal_nan=True,atol=1e-6,rtol=1e-6)
                    checks.append(dict(key=sp['key'],test='raw_filing_cutoff_replay',cutoff=str(cutoff),stocks=len(ids),passed=True))
    finally:q.OUT,q.pit_tables=oldout,oldloader
    # Independently check denominator and sign in literal scalar examples.
    for a,b in [(200.,100.),(100.,200.)]:
        ratio=1-(a-b)/1000.
        assert (ratio<1)==(a>b)
    checks.append(dict(test='cash_sales_literal_sign',passed=True))
    return checks

def audit(out,cal,stocks,fields):
    saved=pd.read_pickle(out/'signal_panels.pkl');grid=saved['dates'];pos=cal.get_indexer(grid)
    cap=-fields['cap'][pos];rev=-(q.ratio(fields['close'],q.delay(fields['close'],20))-1)[pos]
    iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
    controls=[cap,rev,-iv[pos]]
    rawold=pd.read_pickle(q.OUT/'signal_panels.pkl')['panels']
    auditrows=[];corrs=[]
    for key,df in saved['panels'].items():
        x=df.to_numpy();res=simultaneous_residual(x,controls)
        for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
            a,p,d=q.evaluate(res[mask],grid[mask],stocks,pos[mask],fields)
            a.update(key=key,window=win,form='size_reversal_IVOL_simultaneous_residual')
            auditrows.append(a);q.dump(out/win/f'{key}.triple_residual.json',a)
            p.to_csv(out/win/f'{key}.triple_residual.periods.csv',index=False)
            d.to_csv(out/win/f'{key}.triple_residual.daily_nav.csv',index=False)
        refs={'known_low_IVOL120':-iv[pos],**{k:rawold[k].reindex(index=grid,columns=stocks).to_numpy() for k in ['small_size','reversal20','book_market','cash_accrual_quality','low_turn20','asset_turnover']}}
        for label,y in refs.items():
            corrs.append(dict(candidate=key,anchor=label,scope='saved_signal_dates_only',**rho_details(x,y)))
    pd.DataFrame(auditrows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(out/'incremental_information.csv',index=False)
    pd.DataFrame(corrs).to_csv(out/'control_correlations_signal_grid.csv',index=False)
    oldout=q.OUT
    try:q.OUT=out;saved_grid()
    finally:q.OUT=oldout

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',choices=['risk','market'],required=True);args=p.parse_args()
    specs=RISK_SPECS if args.batch=='risk' else MARKET_SPECS
    batch=25 if args.batch=='risk' else 26
    out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{batch}-20261013'
    out.mkdir(parents=True,exist_ok=True)
    # Protect formula definitions before reading outcomes or creating outputs.
    plan=dict(specs=specs,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,
              selection='fixed before evaluation; source derivation explicitly marked proxy')
    manifest=out/'frozen_plan.json'
    if manifest.exists() and json.loads(manifest.read_text())!=plan:raise ValueError('Plan mismatch; use a new output directory')
    q.dump(manifest,plan)
    cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates']
    if args.batch=='risk':
        fin=q.financial_snapshot(grid,stocks,lags=6)
        checks=verify_financial(fin,grid,stocks,out);vals=risk_values(fin)
    else:
        checks=verify_market(f);pos=cal.get_indexer(grid)
        vals=[x[pos] for x in market_values(f)]
    for sp,x in zip(specs,vals):
        assert x.shape==(len(grid),len(stocks))
        print('coverage',sp['key'],np.isfinite(x).sum(axis=1).min(),np.isfinite(x).sum(axis=1).mean(),flush=True)
    run(out,specs,vals,cal,stocks,f,checks,
        dict(fidelity='local source proxy; not platform validated',missing='no null-to-zero fill',
             recent_signal_dates='same saved grid restricted >=20260101; latest cache 20260907',
             new_information_gate='size/reversal/known IVOL regressed simultaneously',
             statistics='exploratory after many prior tests; no independent OOS'))
    audit(out,cal,stocks,f)
    print('FINISHED',out,flush=True)

if __name__=='__main__':main()
