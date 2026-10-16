#!/usr/bin/env python3
"""Matched short/long SJM experiment on successfully replayed original atoms."""
from __future__ import annotations
import os
for n in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[n]='1'
import json, argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
import shu_mulvey_sjm_bl_20261014 as model
import regime_long_base_replay_20261014 as replay
import regime_long_history_data_20261014 as data

OUT=q.ROOT/'research_reports/platform_alignment/shu-mulvey-long-base-20261014'

def setup(kind):
    model.MIN_TRAIN_DAYS=2016 if kind=='long' else 252
    model.MAX_TRAIN_DAYS=3024 if kind=='long' else 756
    model.VALIDATION_PERIODS=151 if kind=='long' else 50
    model.MIN_VALIDATION_PERIODS=126 if kind=='long' else 12

def fit(task):
    kind,args=task;setup(kind);return model.fit_predict_one(args)

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--include-market',action='store_true');args=parser.parse_args()
    if args.include_market:OUT=q.ROOT/'research_reports/platform_alignment/shu-mulvey-long-ready-20261014'
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,fields=pd.read_pickle(data.training_market_path());q.dates_all=cal
    allmeta=pd.read_csv(model.OUT/'factor_metadata.csv')
    files={p.name[:-12]:p for p in replay.OUT.glob('*.history.pkl')}
    if args.include_market:
        for name in ['regime-long-market-replay-20261014','regime-long-financial-replay-20261014','regime-long-financial-replay-v2-20261014','regime-long-financial-risk-replay-20261014']:
            folder=q.ROOT/'research_reports/platform_alignment'/name
            files.update({p.name[:-12]:p for p in folder.glob('*.history.pkl')})
    meta=allmeta[allmeta.key.isin(files)].copy().reset_index(drop=True)
    if len(meta)<20:raise ValueError('Insufficient completed original atom replays')
    first=pd.read_pickle(files[meta.iloc[0].key]);grid=first['dates'];panels=[];ledger={}
    for i,r in meta.iterrows():
        obj=pd.read_pickle(files[r.key]);assert obj['dates'].equals(grid) and obj['stocks'].equals(stocks);panels.append(obj['values'])
        p=files[r.key].parent/f'{r.key}.periods.csv';ledger[r.record_id]=pd.read_csv(p,parse_dates=['date','entry_date','exit_date'])
        meta.at[i,'period_path']=str(p.relative_to(q.ROOT))
    meta.to_csv(OUT/'factor_metadata.csv',index=False)
    daily,asset,active,bench,valid,market,environment=model.make_daily(meta,ledger,cal,fields,grid)
    idx=daily.get_indexer(grid);idx=np.where(idx>=0,idx,daily.searchsorted(grid)-1)
    xs=[model.features(active[:,j],market,environment) for j in range(len(meta))]
    formal=pd.read_pickle(replay.BASE/'signal_panels.pkl')['dates'];fi=grid.get_indexer(formal);pos=cal.get_indexer(formal)
    scores={'MATCHED_EQUAL':model.composite([p[fi] for p in panels],np.full((len(formal),len(meta)),1/len(meta)))}
    Wlong={};candlong={};audits={};logs=[]
    for kind in ['short','long']:
        setup(kind);folder=OUT/kind;folder.mkdir(exist_ok=True)
        cache=folder/'models.pkl'
        if cache.exists():
            obj=pd.read_pickle(cache);assert obj['keys']==meta.key.tolist();candidates=obj['candidates'];fits=obj['fits']
        else:
            candidates={};fits=[]
            reusable=q.ROOT/'research_reports/platform_alignment/shu-mulvey-long-base-20261014'/kind/'models.pkl'
            if args.include_market and reusable.exists():
                prior=pd.read_pickle(reusable);mapping={key:j for j,key in enumerate(meta.key)}
                for prior_j,key in enumerate(prior['keys']):
                    if key in mapping:
                        j=mapping[key];candidates[j]=prior['candidates'][prior_j]
                        fits.extend([{**row,'j':j} for row in prior['fits'] if row['j']==prior_j])
                print('REUSED_MATCHED_BASE_MODELS',kind,len(candidates),flush=True)
            tasks=[(kind,(j,xs[j],active[:,j],idx,grid,model.PARAMS)) for j in range(len(meta)) if j not in candidates]
            with ProcessPoolExecutor(max_workers=8) as pool:
                fs=[pool.submit(fit,t) for t in tasks]
                for i,f in enumerate(as_completed(fs),1):
                    j,c,rows=f.result();candidates[j]=c;fits.extend(rows)
                    if i%10==0:print('LONG_STUDY_FITTED',kind,i,'/',len(meta),flush=True)
            pd.to_pickle(dict(keys=meta.key.tolist(),candidates=candidates,fits=fits),cache)
        V,state,params,quality,audit,fw=model.choose_predictions(meta,candidates,daily,active,ledger,grid)
        audit.to_csv(folder/'prediction_audit.csv',index=False);pd.DataFrame(fits).to_csv(folder/'model_fits.csv',index=False)
        assert (pd.to_datetime(audit.last_training_return)<pd.to_datetime(audit.date)).all()
        known=audit.validation_max_exit.notna();assert (pd.to_datetime(audit.loc[known,'validation_max_exit'])<pd.to_datetime(audit.loc[known,'date'])).all()
        audits[kind]=audit
        for name,te,pen in [('TE2',.02,0.),('TE4',.04,0.),('TE2_TURN',.02,.003)]:
            # Prior configuration starts at the first formal signal for both
            # paths. Both use all available past covariance and past views.
            w,log=model.allocate(V[fi],quality[fi],asset,active,market,daily,formal,meta,te,pen)
            assert np.allclose(w.sum(axis=1),1.) and w.max()<=.2+1e-7
            key=kind.upper()+'_'+name;scores[key]=model.composite([p[fi] for p in panels],w)
            log.to_csv(folder/f'{name}.allocation_audit.csv',index=False)
            pd.DataFrame(w,index=formal,columns=meta.key).to_parquet(folder/f'{name}.weights.parquet')
            if kind=='long':Wlong[name]=w
            print('LONG_STUDY_ALLOCATED',key,flush=True)
        if kind=='long':candlong=candidates;Vlong=V;qualitylong=quality
    sf,*_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
    stored=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
    seats=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact'];z=[]
    for key in seats:
        frame=sf[['date','instrument']].copy();frame['value']=stored['scores'][key].to_numpy();frame.date=pd.to_datetime(frame.date)
        x=frame.pivot(index='date',columns='instrument',values='value').reindex(index=formal,columns=stocks).to_numpy(np.float32);z.append(q.zscore(x))
    core=sum(z)/5;scores['ARCHIVED_MINGLE']=core
    for key in list(scores):
        if key.startswith(('LONG_','SHORT_')):scores[key+'_POOL20']=.8*q.zscore(core)+.2*q.zscore(scores[key])
    results=[]
    for key,score in scores.items():
        for window,mask in [('five_year',np.ones(len(formal),bool)),('recent',formal>='2026-01-01')]:
            r,p,d=q.evaluate(score[mask],formal[mask],stocks,pos[mask],fields);r.update(key=key,window=window);r.pop('years',None);r.pop('group_arithmetic_annual_pct',None);results.append(r)
            p.to_csv(OUT/f'{key}.{window}.periods.csv',index=False);d.to_csv(OUT/f'{key}.{window}.daily_nav.csv',index=False)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    specialists=[]
    for _,r in meta.iterrows():
        p=ledger[r.record_id];p=p[p.date.isin(formal)]
        observed=audits['long'][audits['long'].key==r.key][['date','state','forecast_daily','validation_timing_score']]
        joined=p.merge(observed,on='date',how='inner')
        whole=float(p.net_excess_path.mean()*25.2*100) if len(p) else np.nan
        for state,g in joined.groupby('state'):
            specialists.append(dict(key=r.key,state=int(state),formal_periods=len(g),formal_global_net_excess_pct=whole,conditional_net_excess_pct=float(g.net_excess_path.mean()*25.2*100),conditional_positive_fraction=float((g.net_excess_path>0).mean()),mean_forecast_annual_pct=float(g.forecast_daily.mean()*252*100),mean_validation_score=float(g.validation_timing_score.mean()),diagnostic_only=True,global_negative_state_positive=bool(whole<0 and g.net_excess_path.mean()>0),state_semantics='factor-specific active-return cluster; label0 higher fitted return; refit monthly'))
    pd.DataFrame(specialists).to_csv(OUT/'factor_state_specialists_descriptive.csv',index=False)
    setup('long');checks=[]
    for key in ['reversal20','capm_residual_vol120_low','book_market']:
        if key not in set(meta.key):continue
        j=int(meta.index[meta.key==key][0]);stop=int(fi[75]);t=idx[stop];x=xs[j].copy();a=active[:,j].copy();x[t+1:]=123.;a[t+1:]=-.7
        _,new,_=fit(("long",(j,x,a,idx[:stop+1],grid[:stop+1],model.PARAMS)))
        for k in range(len(model.PARAMS)):np.testing.assert_allclose(new[k][0],candlong[j][k][0][:stop+1],equal_nan=True,atol=1e-12)
        checks.append(dict(key=key,test='long_history_future_mutation',passed=True))
    stop=int(fi[75]);t=idx[stop]
    vr,sr,pr,qr,ar,fr=model.choose_predictions(meta,candlong,daily,active,ledger,grid[:stop+1])
    np.testing.assert_allclose(vr,Vlong[:stop+1],equal_nan=True)
    fkeep=fi[fi<=stop]
    w,_=model.allocate(vr[fkeep],qr[fkeep],asset[:t+1],active[:t+1],market[:t+1],daily[:t+1],formal[:len(fkeep)],meta,.02,.003)
    np.testing.assert_allclose(w,Wlong['TE2_TURN'][:len(fkeep)],atol=1e-8)
    checks.append(dict(test='long_history_truncated_parameter_selection_and_allocation',passed=True))
    q.dump(OUT/'protocol.json',dict(version=q.ALIGNMENT_RULE_VERSION+'-shu-long-base-finannquarantine-v1',factors=len(meta),total592_coverage=len(meta)/592,all592_completed=False,training_days=dict(short=[252,756],long=[2016,3024]),validation_completed_periods=dict(short=[12,50],long=[126,151]),full_six_calendar_years_initial_validation='not guaranteed; actual observations recorded; 126 completed timing forecasts required, otherwise default lambda50 and no validation reliability',formal_panels='immutable saved originals',formal_window=['20210907','20260907'],recent_window=['20260101',str(cal.max().date())],actual_last_exit=str(cal[pos[-1]+11].date()),platform_compute=0,limitations=['matched original atom subset; remaining canonical factors pending replay','vendor historical revisions lack original release snapshots','fixed source factors discovered using same formal historical window','bottom-up stock ranks and local factor_valid sleeves differ from paper ETFs','rates downloaded but omitted from this matched comparison to isolate training length']))
    q.dump(OUT/'verification.json',dict(completed=True,causal_date_checks=True,normalized_and_capped=True,future_checks=checks,replayed_factors=len(meta),all592_long_models_completed=False,platform_calls=0))
    print(pd.DataFrame(results)[['key','window','net_excess_pct','turnover_pct','held_daily_max_drawdown_pct']].to_string(index=False),flush=True)

if __name__=='__main__':main()
