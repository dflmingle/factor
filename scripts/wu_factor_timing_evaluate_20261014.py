#!/usr/bin/env python3
"""Daily fixed-monthly-holdings timing ledgers; cost and next-close sensitivity."""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import numpy as np
import pandas as pd
from wu_factor_timing_inputs_20261014 import ROOT, OUT, dump, sha

def drawdown(r):
    wealth = np.r_[1., np.cumprod(1 + r)]
    return float(-np.min(wealth / np.maximum.accumulate(wealth) - 1))

def daily_ledger(bundle, key, wing, forecasts, rule, delayed, cost):
    daily = (bundle['delayed_daily_returns'] if delayed else bundle['daily_returns'])[key]
    prior = dict((bundle['previous_delayed_holdings'] if delayed else bundle['previous_holdings'])[key])
    holdings = dict(bundle['holdings'][key]); cal = bundle['calendar']; dates = bundle['dates']
    pred = forecasts.set_index('target_month').prediction.to_dict()
    records = []; previous_exposure = 0.; leg_to_equity = np.ones(2)
    # Do not fabricate performance before the first available OOS signal.
    started = False
    for i in range(len(dates)-1):
        signal = dates[i]; target = str(dates[i+1].to_period('M'))
        if signal not in holdings or target not in pred: continue
        forecast = float(pred[target])
        exposure = 1. if rule == 'buy_hold' else float(forecast >= 0) if rule == 'long_cash' else 1. if forecast >= 0 else -1.
        lo = cal.get_loc(signal) + 1 + int(delayed)
        hi = min(cal.get_loc(dates[i+1]) + 1 + int(delayed),len(cal))
        if hi <= lo: continue
        d = daily.iloc[lo:hi]
        if not np.isfinite(d[[1,10]].to_numpy()).all(): raise ValueError('Missing path')
        w = holdings[signal]; old = prior[signal] if started else np.zeros_like(w)
        # Portfolio weights drift relative to each leg NAV. The previous
        # fixed-month investment equity changes by the combined LS payoff.
        # Convert leg drift back to investor-equity units before computing
        # actual purchases/sales, including direction switches.
        if wing == 'LS':
            new = exposure * (w[1]-w[0])
            old_target = previous_exposure * (old[1]*leg_to_equity[1]-old[0]*leg_to_equity[0])
        else:
            leg = 1 if wing == 'L' else 0
            new = exposure*w[leg]; old_target = previous_exposure*old[leg]*leg_to_equity[leg]
        traded = float(np.abs(new-old_target).sum())
        fee = cost*traded
        legs = np.cumprod(1+d[[1,10]].to_numpy(),axis=0)
        payoff = legs[:,1]-legs[:,0] if wing=='LS' else legs[:,1 if wing=='L' else 0]-1
        gross_value = 1+exposure*payoff
        net_value = gross_value-fee
        if np.any(net_value <= 0): raise ValueError('Insolvent strategy')
        realized = net_value/np.r_[1.,net_value[:-1]]-1
        gross_return = gross_value/np.r_[1.,gross_value[:-1]]-1
        for j,(date,r,g) in enumerate(zip(d.index,realized,gross_return)):
            records.append(dict(date=date, signal_date=signal, target_month=target,
                 exposure=exposure, prediction=forecast, gross_return=g, net_return=r,
                 one_way_traded_notional=traded if j==0 else 0., cost=fee if j==0 else 0.))
        leg_to_equity=legs[-1]/net_value[-1]
        previous_exposure=exposure; started=True
    return pd.DataFrame(records).set_index('date') if records else pd.DataFrame()

def summarize(d):
    if not len(d):return dict(n=0)
    r=d.net_return.to_numpy(); g=d.gross_return.to_numpy()
    ann=252*r.mean(); vol=np.std(r,ddof=1)*np.sqrt(252)
    return dict(n=len(d), first=str(d.index.min().date()),last=str(d.index.max().date()),
         annual_arithmetic_pct=float(ann*100), annual_gross_arithmetic_pct=float(252*g.mean()*100),
         compound_total_pct=float((np.prod(1+r)-1)*100),
         cagr_pct=float((np.prod(1+r)**(252/len(r))-1)*100),
         annual_vol_pct=float(vol*100), sharpe=float(ann/vol) if vol else np.nan,
         max_drawdown_pct=drawdown(r)*100, annual_traded_notional_pct=float(d.one_way_traded_notional.sum()*252/len(d)*100),
         negative_signal_fraction=float((d.exposure<0).mean()),
         cash_fraction=float((d.exposure==0).mean()))

def main():
    b=pd.read_pickle(OUT/'inputs.pkl');(OUT/'ledgers').mkdir(exist_ok=True)
    frames=[]
    for prefix in ('regression','cluster'):
        p=OUT/f'{prefix}_forecasts.csv'
        if p.exists():frames.append(pd.read_csv(p))
    f=pd.concat(frames,ignore_index=True);rows=[];pairs=[];cached={};cache_key=None;done=0
    for group,dd in f.groupby(['key','wing','family','model']):
        key,wing,family,model=group
        # All factors' forecasts assessed statistically; exhaustive portfolio
        # strategies below cover 24 LS targets and three reversal targets.
        if wing!='LS' and key!='reversal_onemonthreturn':continue
        if cache_key!=(key,wing):cached={};cache_key=(key,wing)
        ordered=dd.sort_values('target_month')
        for delayed in (False,True):
            for cost in (0.,.003):
                baseline=None
                for rule in (('buy_hold','sign_flip','long_cash') if key=='reversal_onemonthreturn' else ('buy_hold','sign_flip')):
                    signals=(np.ones(len(ordered)) if rule=='buy_hold' else
                             (ordered.prediction.to_numpy()>=0).astype(float) if rule=='long_cash' else
                             np.where(ordered.prediction.to_numpy()>=0,1.,-1.))
                    ck=(delayed,cost,tuple(ordered.target_month),tuple(signals))
                    if ck not in cached:cached[ck]=daily_ledger(b,key,wing,dd,rule,delayed,cost)
                    d=cached[ck]
                    if not len(d):continue
                    if baseline is None:baseline=d
                    common=dict(key=key,wing=wing,family=family,model=model,rule=rule,delayed=delayed,one_way_cost=cost)
                    if key=='reversal_onemonthreturn':
                        d=d.copy();d['prediction']=d.target_month.map(dd.set_index('target_month').prediction)
                        d.to_csv(OUT/'ledgers'/f'{key}.{wing}.{family}.{model}.{rule}.delay{int(delayed)}.fee{cost:.3f}.csv')
                    for window,lo,hi in [('paper_overlap','20000101','20211231'),
                        ('five_year','20210907','20260907'),('recent','20260101','20260907')]:
                        sub=d.loc[lo:hi];stats=summarize(sub)
                        rows.append(dict(**common,window=window,**stats))
                        if rule=='buy_hold' or not len(sub):continue
                        base=baseline.reindex(sub.index)
                        active=sub.net_return-base.net_return
                        pairs.append(dict(**common,window=window,n=len(sub),
                            annual_improvement_pp=float(active.mean()*252*100),
                            daily_active_ir=float(active.mean()/active.std()*np.sqrt(252)) if active.std()>0 else np.nan,
                            maxdd_change_pp=float(drawdown(sub.net_return.to_numpy())*100-drawdown(base.net_return.to_numpy())*100)))
        done+=1
        if done%36==0:print('WU_STRATEGY_JOBS',done,'of',len(f.groupby(['key','wing','family','model'])),key,flush=True)
    pd.DataFrame(rows).to_csv(OUT/'strategy_results.csv',index=False)
    pd.DataFrame(pairs).to_csv(OUT/'strategy_vs_buy_hold.csv',index=False)
    dump(OUT/'strategy_protocol.json',dict(input_sha256=sha(OUT/'inputs.pkl'),
        target='month-start capital; fixed selected monthly holdings; LS one long plus one short',
        return_path='1+exposure*(long_relative-short_relative); no daily rebalancing of LS legs',
        fees='0 or 0.30% one-way x absolute difference of stock signed weights, drift-aware within separate legs',
        limits=['no short borrow costs, limits or hard-to-borrow constraints; hypothetical LS is not platform implementable',
                'next-close sensitivity shifts portfolio execution and payoff one trading day; predictions unchanged',
                'paper risk-free treasury series unavailable; L/S wings use raw price returns instead of original excess returns',
                'CH-3 alpha not reproduced without original CH-3 validation'],
        formal_window=['20210907','20260907'],recent_window=['20260101','20260907'],
        platform_alignment_result=False,platform_compute_spent=0))
    print('WU_STRATEGIES_COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()
