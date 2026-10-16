"""Direct five-seat pool test of attribution-guided exposure allocation.

Unlike the earlier FFN proxy, this script starts from the saved incumbent
five-seat score panels, builds the equal-zscore composite used by the local
pool reconstruction, and applies lagged net-Sharpe marginal attribution to
the five seat exposures. No platform call is made.
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/literature/economic-explanation-ml-portfolios-20261016/direct_pool'
SEAT=ROOT/'research_reports/platform_alignment/ab-batch-20260929/seat_panels_rebuilt.pkl'
SEATS=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']
COST=.003; PAPER_COST=.0005; ETA=.5; LAM_MIN=0.; LAM_MAX=3.; N_TRAIN=24; N_VALID=12; BLOCK=12

def load():
    x=pickle.loads(SEAT.read_bytes()); sf=x['signal_frame'][['date','instrument']].copy(); sf['date']=pd.to_datetime(sf['date'])
    dates=pd.DatetimeIndex(x['dates']); stocks=pd.Index(sorted(sf.instrument.unique()))
    score=x['scores'].copy(); panels={}
    for k in SEATS:
        panels[k]=sf.assign(v=score[k].to_numpy()).pivot(index='date',columns='instrument',values='v').reindex(index=dates,columns=stocks).to_numpy(float)
    ret=x['returns'].copy(); ret['date']=pd.to_datetime(ret['date'])
    y=ret.pivot(index='date',columns='instrument',values='forward_return').reindex(index=dates,columns=stocks).to_numpy(float)
    return dates,stocks,panels,y

def zscore(a):
    out=np.full_like(a,np.nan,float)
    for i,row in enumerate(a):
        ok=np.isfinite(row); s=np.nanstd(row)
        if ok.sum()>100 and s>1e-12: out[i,ok]=(row[ok]-np.nanmean(row))/s
    return out

def composite(z,lambdas):
    # Missing seat values are ignored per date/name and the score is averaged
    # over available seats, so a missing accounting field cannot become a
    # mechanical short/long signal.
    a=z*lambdas[None,None,:]
    # Match the incumbent pool reconstruction: fixed five-seat denominator;
    # missing components are skipped but do not renormalise the score.
    return np.nansum(a,axis=2)/len(lambdas)

def path(score,y,idx,prev=None,cost=COST):
    rows=[]; prev=set() if prev is None else prev
    for i in idx:
        mask=np.isfinite(score[i])&np.isfinite(y[i]); ids=np.flatnonzero(mask)
        if len(ids)<200: continue
        n=max(int(len(ids)*.1),1); order=ids[np.argsort(-score[i,ids])[:n]]; selected=set(order.tolist())
        turn=np.nan if not prev else 1-len(selected&prev)/len(selected)
        held=float(np.mean(y[i,order])); bench=float(np.mean(y[i,ids])); gross=held-bench; net=gross-(0 if not np.isfinite(turn) else cost*turn)
        rows.append(dict(index=int(i),date=str(i),held=held,benchmark=bench,gross=gross,net=net,turnover=turn,selected=selected))
        prev=selected
    return pd.DataFrame(rows),prev

def sharpe(r):
    r=np.asarray(r,float); return float(np.sqrt(25.2)*r.mean()/r.std(ddof=1)) if len(r)>1 and r.std(ddof=1)>0 else np.nan

def metrics(d):
    r=d.net.to_numpy(float); g=d.gross.to_numpy(float); t=d.turnover.to_numpy(float); nav=np.cumprod(1+r)
    years=len(d)*10/252.0
    held_ann=float(np.prod(1+d.held.to_numpy(float))**(1/years)-1)
    bench_ann=float(np.prod(1+d.benchmark.to_numpy(float))**(1/years)-1)
    gross_ann=held_ann-bench_ann
    turn_mean=float(np.nanmean(t)); net_ann=gross_ann-turn_mean*(252/10)*COST
    paper_net_ann=gross_ann-turn_mean*(252/10)*PAPER_COST
    return dict(periods=len(d),sharpe_net=sharpe(r),sharpe_gross=sharpe(g),net_annual_pct=net_ann*100,gross_annual_pct=gross_ann*100,turnover_pct=turn_mean*100,maxdd_pct=float(-np.min(nav/np.maximum.accumulate(nav)-1)),paper_cost_net_annual_pct=paper_net_ann*100)

def main():
    OUT.mkdir(parents=True,exist_ok=True); dates,stocks,raw,y=load()
    zparts=[]
    for k in SEATS:
        df=pd.DataFrame(raw[k],index=dates,columns=stocks)
        zparts.append(df.sub(df.mean(axis=1),axis=0).div(df.std(axis=1,ddof=0),axis=0).to_numpy())
    z=np.stack(zparts,axis=2)
    base_score=composite(z,np.ones(len(SEATS))); full,_=path(base_score,y,np.arange(len(dates)))
    results=[]; attrs=[]; lambdas=[]; test_start=N_TRAIN+N_VALID
    # full 120-period direct reconstruction for comparison with the existing pool ledger
    m=metrics(full.drop(columns=['selected'])); m.update(candidate='direct_pool_full120',variant='baseline'); results.append(m)
    state=np.ones(len(SEATS)); variants={v:[] for v in ['baseline','unstabilised','stabilised']}
    plan={'seats':SEATS,'dates':[str(dates[0]),str(dates[-1])],'full_periods':len(dates),'oos_periods':len(dates)-test_start,'train_periods':N_TRAIN,'validation_periods':N_VALID,'block_periods':BLOCK,'eta':ETA,'cost':COST,'paper_cost':PAPER_COST,'method':'direct equal-zscore five-seat pool; leave-one-seat-out net-Sharpe attribution; lagged one validation block','platform_compute_spent':0}
    (OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    for ts in range(test_start,len(dates)-BLOCK+1,BLOCK):
        va=np.arange(ts-N_VALID,ts); te=np.arange(ts,ts+BLOCK)
        vr,_=path(base_score,y,va); base_sr=sharpe(vr.net)
        phi=np.zeros(len(SEATS))
        for j in range(len(SEATS)):
            lam=np.ones(len(SEATS)); lam[j]=0.; ab,_=path(composite(z,lam),y,va); phi[j]=base_sr-sharpe(ab.net)
        sd=np.nanstd(phi); step=np.ones(len(SEATS)) if not np.isfinite(sd) or sd<1e-12 else 1+ETA*np.tanh(phi/sd)
        unst=np.clip(step,LAM_MIN,LAM_MAX); stab=np.clip(state*unst,LAM_MIN,LAM_MAX)
        for variant,lam in [('baseline',np.ones(len(SEATS))),('unstabilised',unst),('stabilised',stab)]:
            d,_=path(composite(z,lam),y,te); d=d.drop(columns=['selected']); d['block']=ts; variants[variant].append(d)
            if variant=='stabilised': state=stab.copy()
        attrs.append({'test_start':str(dates[ts]),**{SEATS[j]:float(phi[j]) for j in range(len(SEATS))}})
        lambdas.append({'test_start':str(dates[ts]),**{f'lambda_{SEATS[j]}':float(unst[j]) for j in range(len(SEATS))},**{f'state_{SEATS[j]}':float(stab[j]) for j in range(len(SEATS))}})
    for variant,parts in variants.items():
        d=pd.concat(parts,ignore_index=True); d.to_csv(OUT/f'{variant}.periods.csv',index=False); m=metrics(d); m.update(candidate='direct_pool_oos84',variant=variant); results.append(m)
    result=pd.DataFrame(results); result.to_csv(OUT/'results.csv',index=False); pd.DataFrame(attrs).to_csv(OUT/'validation_attributions.csv',index=False); pd.DataFrame(lambdas).to_csv(OUT/'lambda_log.csv',index=False)
    (OUT/'verification.json').write_text(json.dumps({'completed':True,'platform_compute_spent':0,'finite':bool(np.isfinite(result.select_dtypes('number')).all().all()),'causal':'validation attribution precedes each test block','baseline_full120_periods':len(full),'oos_periods':sum(len(x) for x in variants['baseline'])},ensure_ascii=False,indent=2)+'\n')
    print(result.to_string(index=False))

if __name__=='__main__': main()
