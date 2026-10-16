#!/usr/bin/env python3
"""Paper extension: fixed incumbent prior and causal pool turnover guard."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import quant_corpus_local_20261012 as q
import shu_mulvey_sjm_bl_20261014 as model
import shu_mulvey_long_base_20261014 as study
import shu_mulvey_forward_views_20261014 as forward
import regime_long_base_replay_20261014 as replay
import regime_long_history_data_20261014 as data

OUT=q.ROOT/'research_reports/platform_alignment/shu-mulvey-incumbent-prior-20261014'

def allocate(V,Q,asset,core_asset,core_periods,daily,formal,panels,core,cap,te,pen):
    n,m=V.shape;W=np.zeros((n,m));scores=np.full_like(core,np.nan);logs=[];prev=np.zeros(m);previous_held=None
    ranks=[q.zscore(q.rank(x)) for x in panels]
    def score(i,w):
        value=(1-w.sum())*core[i].copy()
        for j in np.flatnonzero(w>1e-10):value+=w[j]*np.nan_to_num(ranks[j][i],nan=0.)
        return value
    def held(i,x):
        ids=np.flatnonzero(np.isfinite(x)&(cap[i]>0));order=np.argsort(x[ids],kind='stable');g=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
        return set(ids[order[g==10]])
    def turnover(target):return 0. if previous_held is None else 1-len(previous_held&target)/len(target)
    for i,date in enumerate(formal):
        t=int(daily.searchsorted(date));start=max(0,t-756);hist=core_periods[core_periods.exit_date<date].tail(50)
        ids=np.flatnonzero(np.isfinite(V[i])&(np.isfinite(asset[start:t]).sum(axis=0)>=252))
        w=np.zeros(m);predicted_te=0.;core_mu=np.nan
        if len(hist)>=12 and np.isfinite(core_asset[start:t]).sum()>=126 and len(ids)>=5:
            ew=np.power(.5,np.arange(len(hist)-1,-1,-1)/12);ew/=ew.sum();core_mu=float(ew@hist.net_excess_path.to_numpy()/10)
            C=np.corrcoef(np.nan_to_num(asset[max(0,t-504):t],nan=0.),rowvar=False);priority=np.nan_to_num(Q[i],nan=0.)+.01*(V[i]-core_mu)*252
            selected=[]
            for j in ids[np.argsort(-priority[ids],kind='stable')]:
                if selected and np.max(abs(C[j,selected]))>.9:continue
                selected.append(int(j))
                if len(selected)==24:break
            ids=np.array(selected);k=len(ids)
            # Use only dates with an observed incumbent return. Before its
            # history exists, the portfolio remains exactly the incumbent.
            known=np.isfinite(core_asset[start:t]);R=np.column_stack([asset[start:t,ids],core_asset[start:t]])[known]
            S=model.ew_cov(R);b=np.r_[np.zeros(k),1.];Pi=model.DELTA*S@b;P=np.column_stack([np.eye(k),-np.ones(k)]);views=V[i,ids]-core_mu;variance=np.maximum(np.diag(P@S@P.T),1e-9)
            old=np.r_[prev[ids],1-prev[ids].sum()]
            def solve(confidence):
                post=Pi+S@P.T@np.linalg.solve(P@S@P.T+np.diag(variance*confidence),views-P@Pi)
                def objective(z):return 252*(model.DELTA/2*z@S@z-post@z)+pen*np.sqrt((z-old)**2+1e-8).sum()
                result=minimize(objective,b,method='SLSQP',bounds=[(0,.2)]*k+[(.8,1.)],constraints=[{'type':'eq','fun':lambda z:z.sum()-1}],options={'ftol':1e-10,'maxiter':150})
                z=result.x if result.success else b;err=np.sqrt(max((z-b)@S@(z-b)*252,0.));return z,err
            low,high=-4.,6.;z,predicted_te=solve(10**high)
            for _ in range(15):
                mid=(low+high)/2;candidate,err=solve(10**mid)
                if err<=te+1e-8:z,predicted_te=candidate,err;high=mid
                else:low=mid
            w[ids]=z[:-1]
        # Label-independent current holdings define the adjustment budget.
        # Max 2pp additional replacement versus today's incumbent target,
        # both measured from the same previous actual research holdings.
        base_target=held(i,core[i]);base_turn=turnover(base_target);scale=1.
        target=held(i,score(i,w));turn=turnover(target)
        while turn>base_turn+.02+1e-12 and scale>1e-6:
            scale*=.5;target=held(i,score(i,w*scale));turn=turnover(target)
        w*=scale;W[i]=w;scores[i]=score(i,w);previous_held=target;prev=w.copy()
        logs.append(dict(date=date,core_weight=1-w.sum(),factor_weight_sum=w.sum(),predicted_te_before_turnover_scale=predicted_te,turnover_scale=scale,estimated_stock_turnover=turn,incumbent_target_turnover_from_same_previous_holdings=base_turn,additional_turnover=turn-base_turn,core_forecast_daily=core_mu,core_calibration_last_exit=hist.exit_date.max() if len(hist) else pd.NaT,covariance_last_date=daily[t-1] if t else pd.NaT))
    return W,scores,pd.DataFrame(logs)

def main():
    OUT.mkdir(parents=True,exist_ok=True);cal,stocks,fields=pd.read_pickle(data.training_market_path());q.dates_all=cal
    meta=pd.read_csv(study.OUT/'factor_metadata.csv');candidates=pd.read_pickle(study.OUT/'long/models.pkl')['candidates'];obj=pd.read_pickle(replay.OUT/f'{meta.iloc[0].key}.history.pkl');grid=obj['dates'];formal=pd.read_pickle(replay.BASE/'signal_panels.pkl')['dates'];fi=grid.get_indexer(formal);pos=cal.get_indexer(formal)
    ledgers={r.record_id:pd.read_csv(q.ROOT/r.period_path,parse_dates=['date','entry_date','exit_date']) for _,r in meta.iterrows()};panels=[pd.read_pickle(replay.OUT/f'{r.key}.history.pkl')['values'][fi] for _,r in meta.iterrows()]
    daily,asset,active,bench,valid,market,environment=model.make_daily(meta,ledgers,cal,fields,grid);V,Q,view_audit=forward.calibrate(meta,candidates,ledgers,grid);view_audit.to_csv(OUT/'view_audit.csv',index=False)
    sf,*_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl');saved=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl');z=[]
    for key in ['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']:
        frame=sf[['date','instrument']].copy();frame['value']=saved['scores'][key].to_numpy();frame.date=pd.to_datetime(frame.date);z.append(q.zscore(frame.pivot(index='date',columns='instrument',values='value').reindex(index=formal,columns=stocks).to_numpy(np.float32)))
    core=q.zscore(sum(z)/5)
    core_periods=pd.read_csv(study.OUT/'ARCHIVED_MINGLE.five_year.periods.csv',parse_dates=['date','entry_date','exit_date']);nav=pd.read_csv(study.OUT/'ARCHIVED_MINGLE.five_year.daily_nav.csv',parse_dates=['date']).set_index('date');core_asset=nav.nav.pct_change(fill_method=None).reindex(daily).to_numpy()
    scores={'ARCHIVED_MINGLE':core};weights={};logs={};results=[]
    for key,te,pen in [('CORE_TE2',.02,0.),('CORE_TE4',.04,0.),('CORE_TE2_TURN',.02,.003)]:
        w,x,log=allocate(V[fi],Q[fi],asset,core_asset,core_periods,daily,formal,panels,core,fields['cap'][pos],te,pen);weights[key]=w;scores[key]=x;logs[key]=log
        assert w.min()>=-1e-8 and w.sum(axis=1).max()<=.20+1e-7 and log.additional_turnover.max()<=.02+1e-7
        assert (pd.to_datetime(log.core_calibration_last_exit.dropna())<pd.to_datetime(log.loc[log.core_calibration_last_exit.notna(),'date'])).all()
        log.to_csv(OUT/f'{key}.allocation_audit.csv',index=False);pd.DataFrame(w,index=formal,columns=meta.key).to_parquet(OUT/f'{key}.weights.parquet')
    for key,x in scores.items():
        for win,mask in [('five_year',np.ones(len(formal),bool)),('recent',formal>='2026-01-01')]:
            r,p,d=q.evaluate(x[mask],formal[mask],stocks,pos[mask],fields);r.update(key=key,window=win,size_rank_rho=q.spearman_mean(x[mask],-fields['cap'][pos[mask]]));r.pop('years',None);r.pop('group_arithmetic_annual_pct',None);results.append(r);p.to_csv(OUT/f'{key}.{win}.periods.csv',index=False);d.to_csv(OUT/f'{key}.{win}.daily_nav.csv',index=False)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    stop=76;end=int(daily.searchsorted(formal[stop-1],side='right'));w,x,log=allocate(V[fi[:stop]],Q[fi[:stop]],asset[:end],core_asset[:end],core_periods[core_periods.date<=formal[stop-1]],daily[:end],formal[:stop],[p[:stop] for p in panels],core[:stop],fields['cap'][pos[:stop]],.02,.003)
    np.testing.assert_allclose(w,weights['CORE_TE2_TURN'][:stop],atol=1e-8);np.testing.assert_allclose(x,scores['CORE_TE2_TURN'][:stop],equal_nan=True,atol=1e-7)
    q.dump(OUT/'verification.json',dict(completed=True,truncated_weights_and_scores=True,core_completed_label_checks=True,core_weight_at_least80pct=True,additional_stock_turnover_budget_2pp=True,platform_calls=0))
    q.dump(OUT/'protocol.json',dict(version=q.ALIGNMENT_RULE_VERSION+'-incumbent-prior-v1',paper_extension='incumbent fixed benchmark replaces all-factor EW prior; completed-horizon calibrated factor-minus-incumbent views',factor_count=len(meta),core='archived mingle local proxy',core_forecast='last50 completed periods, EW halflife12 periods, min12',covariance='last756daily, min126 observed core days; diagonal shrink25%; halflife126',max_factor_total_weight=.20,max_incremental_stock_replacement=.02,turnover_guard='compare candidate and current incumbent target from same previous research holdings; not an absolute cap or official monthly pool turnover',label='t+1->t+11',one_way_cost=.003,configs=3,limitations=['adaptation proposed after failed aggregate prior','factor_valid benchmarks differ between some factor sleeves','raw five-year data already explored','no platform confirmation or live pool modification']))
    print(pd.DataFrame(results)[['key','window','net_excess_pct','turnover_pct','held_daily_max_drawdown_pct','size_rank_rho']].to_string(index=False),flush=True)

if __name__=='__main__':main()
