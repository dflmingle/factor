#!/usr/bin/env python3
"""Causality and accounting checks independent of strategy return outcomes."""
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details
from scipy.stats import spearmanr


def verify():
    q.OUT.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(10612);n,m=365,128
    close=(10*np.exp(np.cumsum(rng.normal(0,.01,(n,m)),axis=0))).astype(np.float32)
    open_=(close*np.exp(rng.normal(0,.005,(n,m)))).astype(np.float32)
    volume=rng.uniform(10000,30000,(n,m)).astype(np.float32)
    fields={'close':close,'open':open_,'high':np.maximum(close,open_)*1.01,'low':np.minimum(close,open_)*.99,
            'volume':volume,'turnover':rng.uniform(.1,5,(n,m)).astype(np.float32),'cap':rng.uniform(1e5,2e5,(n,m)).astype(np.float32),'raw_close':close,'amount':volume*close/10}
    pos=np.array([260,280])
    full={meta['key']:v for gen in [q.recipes,q.additional_market_recipes] for meta,v in gen(fields,pos)}
    cut={meta['key']:v for gen in [q.recipes,q.additional_market_recipes] for meta,v in gen({k:v[:281] for k,v in fields.items()},pos)}
    for key in full:
        np.testing.assert_allclose(full[key],cut[key],atol=1e-6,rtol=1e-6,equal_nan=True,err_msg=key)
    results={'market_truncation_candidates':len(full),'market_truncation_passed':True}
    dummy_fin={'balancesheet.money_cap.q0':np.ones((2,m)), 'balancesheet.total_cur_liab.q0':np.ones((2,m))}
    extra_full=dict((meta['key'],v) for meta,v in q.supplemental_recipes(dummy_fin,fields,pos))
    extra_cut=dict((meta['key'],v) for meta,v in q.supplemental_recipes(dummy_fin,{k:v[:281] for k,v in fields.items()},pos))
    for key in ['sharpe20_atom','sharpe120_atom']:
        np.testing.assert_allclose(extra_full[key],extra_cut[key],atol=1e-6,rtol=1e-6,equal_nan=True)
    results['supplemental_sharpe_truncation_passed']=True
    # Independently verify vectorized daily intersection ranks across chunk
    # boundaries, with ties, constant rows, missing values and small samples.
    a=rng.integers(-4,5,(260,145)).astype(float);b=rng.integers(-4,5,(260,145)).astype(float)
    a[rng.random(a.shape)<.05]=np.nan;b[rng.random(b.shape)<.05]=np.nan
    a[0]=1;a[1,:70]=np.nan;b[2]=np.nan
    expected=[];counts=[]
    for x,y in zip(a,b):
        good=np.isfinite(x)&np.isfinite(y)
        if good.sum()<100 or np.ptp(x[good])==0 or np.ptp(y[good])==0:continue
        expected.append(spearmanr(x[good],y[good]).statistic);counts.append(good.sum())
    actual=rho_details(a,b)
    np.testing.assert_allclose(actual['rho'],np.mean(expected),atol=1e-12)
    assert actual['observations']==len(expected)
    np.testing.assert_allclose(actual['mean_common_stocks'],np.mean(counts))
    results['vectorized_spearman_missing_ties_passed']=True
    saved_out=q.OUT;saved_loader=q.pit_tables
    try:
        with tempfile.TemporaryDirectory(dir=saved_out,prefix='verify-pit-') as temp:
            q.OUT=Path(temp)
            dates=pd.DatetimeIndex(['2020-01-01','2020-02-01','2020-03-01']);stocks=pd.Index(['000001.SZ'])
            rows=[('2018-10-30','2018-09-30',70),('2019-03-15','2018-12-31',100),('2019-04-15','2019-03-31',10),('2019-08-15','2019-06-30',30),('2019-10-30','2019-09-30',60),('2020-02-15','2018-12-31',110)]
            def tables(extra=()):
                result={}
                for endpoint,col in [('fina_indicator','roe'),('balancesheet','total_assets'),('income','revenue'),('cashflow','n_cashflow_act')]:
                    f=pd.DataFrame(list(rows)+list(extra),columns=['ann_date','end_date',col])
                    f['ann_date']=pd.to_datetime(f.ann_date);f['end_date']=pd.to_datetime(f.end_date);f['instrument']='000001.SZ';f['update_flag']=0
                    result[endpoint]=f
                return result
            q.pit_tables=lambda:tables()
            a=q.financial_snapshot(dates,stocks)
            np.testing.assert_allclose(a['income.revenue.q0'].ravel(),[60,60,60])
            np.testing.assert_allclose(a['income.revenue_ttm.q0'].ravel(),[90,90,100])
            (q.OUT/'financial_signal_snapshots.pkl').unlink()
            q.pit_tables=lambda:tables([('2020-04-15','2019-12-31',200)])
            b=q.financial_snapshot(dates,stocks)
            for key in a:np.testing.assert_allclose(a[key],b[key],equal_nan=True,err_msg=key)
            (q.OUT/'financial_signal_snapshots.pkl').unlink()
            incomplete=tables()
            for endpoint in ['income','cashflow']:
                incomplete[endpoint]=incomplete[endpoint][incomplete[endpoint].end_date.ne(pd.Timestamp('2019-06-30'))]
            q.pit_tables=lambda:incomplete
            missing=q.financial_snapshot(dates,stocks)
            assert np.isnan(missing['income.revenue_ttm.q0']).all()
            results.update({'financial_future_append_passed':True,'old_revision_does_not_replace_current_quarter':True,'TTM_contiguous_quarters_required':True})
    finally:q.OUT=saved_out;q.pit_tables=saved_loader
    # Check evaluator label, grouping, retained membership and cost with a
    # deterministic rising-price panel. Compare with independently known values.
    calendar=pd.date_range('2022-01-01',periods=24,freq='B');q.dates_all=calendar
    symbols=pd.Index([f'{i:06d}.SZ' for i in range(100)])
    prices=np.broadcast_to((1.01**np.arange(24))[:,None],(24,100)).astype(np.float32)
    cap=np.ones_like(prices);signals=np.broadcast_to(np.arange(100),(2,100)).astype(np.float32)
    summary,periods,nav=q.evaluate(signals,calendar[[0,10]],symbols,np.array([0,10]),{'close':prices,'cap':cap})
    np.testing.assert_allclose(periods.group_return,(1.01**10)-1,atol=2e-7)
    assert periods.iloc[0].entry_date==calendar[1] and periods.iloc[0].exit_date==calendar[11]
    assert periods.iloc[1].turnover==0 and abs(summary['net_excess_pct'])<1e-4
    assert summary['held_daily_max_drawdown_pct']==0
    # Reverse holdings, giving 100% turnover and one roundtrip debit .006.
    changed=np.vstack([np.arange(100),np.arange(100)[::-1]]).astype(np.float32)
    summary,periods,nav=q.evaluate(changed,calendar[[0,10]],symbols,np.array([0,10]),{'close':prices,'cap':cap})
    assert periods.iloc[1].turnover==1
    np.testing.assert_allclose(summary['net_excess_pct'],-15.12,atol=1e-4)
    results.update({'label1_accounting_passed':True,'ten_groups_and_turnover_passed':True,'one_way_003_cost_passed':True,'daily_nav_initial_value_and_drawdown_passed':True})
    q.dump(saved_out/'verification.json',results)
    print(results)

if __name__=='__main__':verify()
