#!/usr/bin/env python3
"""Causal completed-horizon calibration of SJM states, a local paper extension."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
import shu_mulvey_sjm_bl_20261014 as model
import shu_mulvey_long_base_20261014 as study
import regime_long_base_replay_20261014 as replay
import regime_long_history_data_20261014 as data

OUT=q.ROOT/'research_reports/platform_alignment/shu-mulvey-forward-views-20261014'

def calibrate(meta,candidates,ledger,grid):
    V=np.full((len(grid),len(meta)),np.nan);quality=V.copy();audit=[]
    for j,r in meta.iterrows():
        p=ledger[r.record_id].set_index('date').reindex(grid);ex=pd.DatetimeIndex(p.exit_date);ret=p.net_excess_path.to_numpy(float)
        chosen=1;half=None;paths=[]
        # Each hypothetical parameter owns a causal, frozen prediction path.
        for forecast,state,fw,cut in candidates[j]:
            v=np.full(len(grid),np.nan)
            for i,date in enumerate(grid):
                if not np.isfinite(forecast[i]):continue
                hist=np.flatnonzero((ex<date)&np.isfinite(ret))[-151:]
                same=hist[(state[hist]==state[i])&np.isfinite(forecast[hist])]
                if len(same)<12:continue
                global_mean=ret[hist].mean();weight=len(same)/(len(same)+20)
                v[i]=(weight*ret[same].mean()+(1-weight)*global_mean)/10
            paths.append(v)
        for i,date in enumerate(grid):
            hist=np.flatnonzero((ex<date)&np.isfinite(ret))[-151:]
            season=(date.year,(date.month-1)//6)
            if season!=half:
                half=season;scores=[]
                for v in paths:
                    ids=hist[np.isfinite(v[hist])]
                    if len(ids)<50:scores.append(np.nan);continue
                    b=np.clip(v[ids]*252/.05,-1,1);rr=b*ret[ids]-.006*np.r_[0.,abs(np.diff(b))]
                    scores.append(rr.mean()/rr.std(ddof=1) if rr.std(ddof=1)>1e-8 else np.nan)
                if np.isfinite(scores).any():chosen=int(np.nanargmax(scores))
            V[i,j]=paths[chosen][i];ids=hist[np.isfinite(paths[chosen][hist])]
            if len(ids)>=50:
                b=np.clip(paths[chosen][ids]*252/.05,-1,1);rr=b*ret[ids]-.006*np.r_[0.,abs(np.diff(b))];sd=rr.std(ddof=1)
                if sd>1e-8:quality[i,j]=rr.mean()/sd
            if np.isfinite(V[i,j]):
                state=candidates[j][chosen][1];same=hist[(state[hist]==state[i])&np.isfinite(candidates[j][chosen][0][hist])]
                audit.append(dict(date=date,key=r.key,parameter=chosen,forecast_daily=V[i,j],calibration_max_exit=ex[hist[-1]],completed_calibration_periods=len(hist),completed_same_state_periods=len(same),validation_completed_periods=len(ids)))
    return V,quality,pd.DataFrame(audit)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,fields=pd.read_pickle(data.training_market_path());q.dates_all=cal
    meta=pd.read_csv(study.OUT/'factor_metadata.csv');cache=pd.read_pickle(study.OUT/'long/models.pkl');candidates=cache['candidates'];assert cache['keys']==meta.key.tolist()
    obj=pd.read_pickle(replay.OUT/f'{meta.iloc[0].key}.history.pkl');grid=obj['dates'];formal=pd.read_pickle(replay.BASE/'signal_panels.pkl')['dates'];fi=grid.get_indexer(formal);pos=cal.get_indexer(formal)
    ledger={r.record_id:pd.read_csv(q.ROOT/r.period_path,parse_dates=['date','entry_date','exit_date']) for _,r in meta.iterrows()}
    panels=[pd.read_pickle(replay.OUT/f'{r.key}.history.pkl')['values'][fi] for _,r in meta.iterrows()]
    daily,asset,active,bench,valid,market,environment=model.make_daily(meta,ledger,cal,fields,grid)
    V,Q,audit=calibrate(meta,candidates,ledger,grid);audit.to_csv(OUT/'view_audit.csv',index=False);assert (pd.to_datetime(audit.calibration_max_exit)<pd.to_datetime(audit.date)).all()
    sf,*_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl');stored=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl');z=[]
    for key in ['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']:
        frame=sf[['date','instrument']].copy();frame['value']=stored['scores'][key].to_numpy();frame.date=pd.to_datetime(frame.date);z.append(q.zscore(frame.pivot(index='date',columns='instrument',values='value').reindex(index=formal,columns=stocks).to_numpy(np.float32)))
    core=sum(z)/5;scores={'ARCHIVED_MINGLE':core};weights={}
    for key,te,pen in [('FORWARD_TE2',.02,0.),('FORWARD_TE4',.04,0.),('FORWARD_TE2_TURN',.02,.003)]:
        w,log=model.allocate(V[fi],Q[fi],asset,active,market,daily,formal,meta,te,pen);weights[key]=w
        assert np.allclose(w.sum(axis=1),1.) and w.max()<=.2+1e-7
        scores[key]=model.composite(panels,w);scores[key+'_POOL20']=.8*q.zscore(core)+.2*q.zscore(scores[key]);log.to_csv(OUT/f'{key}.allocation_audit.csv',index=False);pd.DataFrame(w,index=formal,columns=meta.key).to_parquet(OUT/f'{key}.weights.parquet')
    results=[]
    for key,score in scores.items():
        for win,mask in [('five_year',np.ones(len(formal),bool)),('recent',formal>='2026-01-01')]:
            r,p,d=q.evaluate(score[mask],formal[mask],stocks,pos[mask],fields);r.update(key=key,window=win);r.pop('years',None);r.pop('group_arithmetic_annual_pct',None);results.append(r);p.to_csv(OUT/f'{key}.{win}.periods.csv',index=False);d.to_csv(OUT/f'{key}.{win}.daily_nav.csv',index=False)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    stop=int(fi[75]);mutated={k:v.copy() for k,v in ledger.items()};cutoff=grid[stop]
    for p in mutated.values():p.loc[p.exit_date>=cutoff,'net_excess_path']=123.
    vr,qr,ar=calibrate(meta,candidates,mutated,grid[:stop+1]);np.testing.assert_allclose(vr,V[:stop+1],equal_nan=True);np.testing.assert_allclose(qr,Q[:stop+1],equal_nan=True)
    t=int(daily.searchsorted(cutoff,side='right'));keep=fi[fi<=stop]
    wc,_=model.allocate(vr[keep],qr[keep],asset[:t],active[:t],market[:t],daily[:t],formal[:len(keep)],meta,.02,.003);np.testing.assert_allclose(wc,weights['FORWARD_TE2_TURN'][:len(keep)],atol=1e-8)
    q.dump(OUT/'verification.json',dict(completed=True,completed_label_date_check=True,future_unmatured_label_mutation=True,truncated_allocation=True,weights_normalized_and_capped=True,platform_calls=0))
    q.dump(OUT/'protocol.json',dict(version=q.ALIGNMENT_RULE_VERSION+'-shu-forward-views-v1',factors=len(meta),paper_extension='SJM states unchanged; views learn next cycle10 label1 active net return from completed states, rather than fitted same-day means',history_completed_periods=151,min_same_state=12,shrink_pseudocount=20,min_validation_predictions=50,parameter_update='semiannual; causal stored calibrations only',training_models='reuse long2016..3024days authorSJM',configs=3,one_way_cost=.003,formal_window=['20210907','20260907'],limitations=['exploratory extension after observing prior failures','state labels drift across monthly refits','local proxy not official submission or livepool','all592 not completed']))
    print(pd.DataFrame(results)[['key','window','net_excess_pct','turnover_pct','held_daily_max_drawdown_pct']].to_string(index=False),flush=True)

if __name__=='__main__':main()
