#!/usr/bin/env python3
"""Exact daily Spearman for leading market candidates; saved-grid old audit."""
import argparse
import gc
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from scipy.stats import rankdata

SELECTED={'coin_team_eq','amount_low_std20','volume_low_std20','ma120_over_close','cgo100_low','capm_residual_vol120_low','rd_assets','rd_market'}

def rho_details(a,b):
    rs=[];ns=[]
    for start in range(0,len(a),128):
        x=np.asarray(a[start:start+128],float);y=np.asarray(b[start:start+128],float)
        valid=np.isfinite(x)&np.isfinite(y);count=valid.sum(axis=1)
        xr=rankdata(np.where(valid,x,np.nan),axis=1,method='average',nan_policy='omit')
        yr=rankdata(np.where(valid,y,np.nan),axis=1,method='average',nan_policy='omit')
        xm=np.divide(np.nansum(xr,axis=1),count,out=np.zeros(len(x)),where=count>0)
        ym=np.divide(np.nansum(yr,axis=1),count,out=np.zeros(len(x)),where=count>0)
        xr=xr-xm[:,None];yr=yr-ym[:,None]
        den=np.sqrt(np.nansum(xr*xr,axis=1)*np.nansum(yr*yr,axis=1))
        r=np.divide(np.nansum(xr*yr,axis=1),den,out=np.full(len(x),np.nan),where=den>0)
        good=(count>=100)&np.isfinite(r);rs.extend(r[good]);ns.extend(count[good])
    return {'rho':float(np.mean(rs)) if rs else np.nan,'observations':len(rs),'mean_common_stocks':float(np.mean(ns)) if ns else np.nan}

def daily():
    calendar,stocks,fields=q.load_market();positions=np.flatnonzero((calendar>='2021-09-07')&(calendar<='2026-09-07'));dates=calendar[positions]
    selected={}
    for meta,value in q.recipes(fields,positions):
        if meta['key'] in SELECTED:selected[meta['key']]=value
        if meta['key']=='cgo100_low':break
    r=q.ratio(fields['close'],q.delay(fields['close']))-1
    market=pd.DataFrame(np.where(fields['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
    m=np.broadcast_to(market[:,None],r.shape)
    cov=pd.DataFrame(r).rolling(120).cov(pd.DataFrame(m)).to_numpy(dtype=np.float32)
    selected['capm_residual_vol120_low']=(-np.sqrt(np.maximum(q.rolling(r,120,'var')-q.ratio(cov**2,q.rolling(m,120,'var')),0)))[positions]
    rd=q.daily_pit_field('fina_indicator','rd_exp',calendar,stocks)
    ta=q.daily_pit_field('balancesheet','total_assets',calendar,stocks)
    selected['rd_assets']=q.ratio(rd[positions],ta[positions]);selected['rd_market']=q.ratio(rd[positions],fields['cap'][positions]*10000)
    cap=fields['cap'];close=fields['close'];turn=fields['turnover'];v=fields['volume'];r=q.ratio(close,q.delay(close))-1
    def sampled(x):
        x=np.asarray(x,dtype=np.float32);x[~(cap>0)]=np.nan;return x[positions]
    # Exact documented raw market handlers; sign oriented to their conventional
    # alpha legs. Financial and market-model anchors explicitly retain proxies.
    eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
    roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks)
    h03=q.ratio(q.rolling(q.ratio(fields['high']-fields['low'],q.delay(close)+1e-6),60,'sum'),q.rolling(fields['amount'],60,'sum')+1)
    chip=q.ratio(q.ratio(q.rolling(v*(fields['open']+close)/2,250,'sum'),q.rolling(v,250,'sum')),close)-1
    anchors={
        'B01|SIZE-ONLY':sampled(-cap),
        'B02|TURN-BIAS-21/504':sampled(1-q.ratio(q.rolling(turn,21),q.rolling(turn,504))),
        'B03|RET40':sampled(-(q.ratio(close,q.delay(close,40))-1)),
        'B04|DD120':sampled(1-q.ratio(close,q.rolling(close,120,'max'))),
        'B05|CHIP250':sampled(chip),
        'B08|BM_latest_proxy':sampled(q.ratio(eq,cap*10000)),
        'B09|DD60':sampled(1-q.ratio(close,q.rolling(close,60,'max'))),
        'N01|REV20':sampled(-(q.ratio(close,q.delay(close,20))-1)),
        'N08|TURN_STD21':sampled(-q.rolling(turn,21,'std')),
        'N09|MAX21':sampled(-q.rolling(r,21,'max')),
        'N16|SKEW60':sampled(-q.rolling(r,60,'skew')),
        'N27|ROE_latest_proxy':sampled(roe),
        'unassigned|H03-IMPACT60':sampled(h03),
        'composite|WEIGHTED-REV21':sampled(-q.ratio(q.rolling(turn*r,21,'sum'),q.rolling(turn,21,'sum'))),
    }
    saved_check=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=dates.get_indexer(saved_check['dates'])
    for k,x in selected.items():
        xx=x.copy();xx[~(fields['cap'][positions]>0)]=np.nan
        np.testing.assert_allclose(xx[grid],saved_check['panels'][k].reindex(columns=stocks).to_numpy(),rtol=1e-5,atol=1e-6,equal_nan=True,err_msg=k)
        selected[k]=xx
    q.dump(q.OUT/'daily_panel_consistency.json',{'signal_grid_equal':True,'candidates':len(selected)})
    rows=[];seen={}
    for key,x in selected.items():
        # Primary comparison uses every available trading day, not pooled data
        # or only rebalance dates; exact intersection ranks for each pair.
        for anchor,y in anchors.items():
            detail=rho_details(x,y);rows.append({'candidate':key,'anchor':anchor,'scope':'daily_cross_sectional_spearman_mean',**detail})
        print('daily correlation',key,flush=True)
        pd.DataFrame(rows).to_csv(q.OUT/'daily_old_anchor_correlations.csv',index=False)
    # Size and short reversal both enter this diagnostic regression. This
    # prevents a non-linear cap shape left by log-cap regression masquerading
    # as a size-independent signal; it does not prove orthogonality to all risks.
    p=q.dates_all=calendar
    saved=pd.read_pickle(q.OUT/'signal_panels.pkl');signal_dates=saved['dates'];signal_pos=calendar.get_indexer(signal_dates)
    neutral_rows=[]
    sz=-fields['cap'][signal_pos];rv=-(q.ratio(close,q.delay(close,20))-1)[signal_pos]
    for key in SELECTED:
        x=saved['panels'][key].reindex(index=signal_dates,columns=stocks).to_numpy();out=np.full_like(x,np.nan)
        for i in range(len(x)):
            valid=np.isfinite(x[i])&np.isfinite(sz[i])&np.isfinite(rv[i])
            if valid.sum()<100:continue
            y=rankdata(x[i,valid]);a=rankdata(sz[i,valid]);b=rankdata(rv[i,valid]);design=np.column_stack([np.ones(valid.sum()),a,b])
            residual=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
            if np.ptp(residual)>1e-7:out[i,valid]=residual
        for window,mask in [('five_year',np.ones(len(x),bool)),('recent',signal_dates>='2026-01-01')]:
            result,periods,nav=q.evaluate(out[mask],signal_dates[mask],stocks,signal_pos[mask],fields)
            neutral_rows.append({'key':key,'window':window,**result})
            periods.to_csv(q.OUT/window/f'{key}.size_reversal_rank_residual.periods.csv',index=False)
    q.dump(q.OUT/'size_reversal_rank_residual.json',neutral_rows)
    q.dump(q.OUT/'daily_correlation_scope.json',{'selected_candidates':sorted(selected),'anchor_count':len(anchors),'days':len(dates),'start':dates.min(),'end':dates.max(),'exact_intersection_spearman':True,'anchors_incomplete_vs_master':True,'old_field_proxies':['BM_latest','ROE_latest'],'additional_controls_unassigned':['H03','weighted reversal'],'not_a_full_unified_cluster_assignment':True})

def saved_grid(resume=False):
    new=pd.read_pickle(q.OUT/'signal_panels.pkl');dates=new['dates'];stocks=new['stocks']
    frame,_,_,_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
    old=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
    frame=frame[['date','instrument']].copy();frame['date']=pd.to_datetime(frame.date)
    inventory=pd.read_csv(q.ROOT/'research_reports/platform_alignment/factor-cluster-master-20261010/factor_member_inventory.csv')
    old_panels={};members={}
    for meta in old['built']:
        key=meta['key'];data=frame.copy();data['value']=old['scores'][key].to_numpy()
        old_panels[key]=data.pivot(index='date',columns='instrument',values='value').reindex(index=dates,columns=stocks).to_numpy(dtype=np.float32)
        found=inventory[inventory.handler.eq(meta['handler']) & inventory.assigned_cluster.fillna('').str.match(r'^[BN][0-9]+$')]
        clusters=sorted(set(found.assigned_cluster.dropna()))
        members[key]={'cluster':';'.join(clusters) or 'composite_or_unassigned','name':meta.get('name',key),'direction':meta.get('direction'),'old_signal_source':'pool-extended-search-20260922'}
    # Broader old reference audit is explicitly a saved signal-grid diagnostic.
    # It complements, and never replaces, the primary every-day correlations.
    result_path=q.OUT/'old_reference_signal_grid_correlations.csv'
    rows=pd.read_csv(result_path).to_dict('records') if resume and result_path.exists() else []
    completed={k for k in new['panels'] if len({r['old_key'] for r in rows if r['candidate']==k})==len(old_panels)}
    for key,df in new['panels'].items():
        if key in completed:continue
        rows=[r for r in rows if r['candidate']!=key]
        x=df.to_numpy()
        for oldkey,y in old_panels.items():
            detail=rho_details(x,y)
            if np.isfinite(detail['rho']):rows.append({'candidate':key,'old_key':oldkey,**members[oldkey],**detail,'scope':'120_saved_signal_days_only'})
        print('saved-grid correlation',key,flush=True)
        if True:pd.DataFrame(rows).to_csv(q.OUT/'old_reference_signal_grid_correlations.csv',index=False)
    result=pd.DataFrame(rows)
    if result.empty:
        result=pd.DataFrame(columns=['candidate','old_key','cluster','name','direction','old_signal_source','rho','scope'])
    result.to_csv(q.OUT/'old_reference_signal_grid_correlations.csv',index=False)
    nearest=result.assign(abs_rho=result.rho.abs()).sort_values('abs_rho',ascending=False).groupby('candidate',sort=False).head(3)
    nearest.to_csv(q.OUT/'nearest_old_top3_signal_grid.csv',index=False)
    q.dump(q.OUT/'old_reference_coverage.json',{'reference_factors':len(old_panels),'mapped_cluster_labels':sorted(set(c for m in members.values() for c in m['cluster'].split(';'))),'signal_dates':len(dates),'coverage':'incomplete prior clusters, saved signal days, old score signs preserved','do_not_infer_new_cluster_from_missing_anchors':True})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scope',choices=['daily','saved'],required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    daily() if a.scope=='daily' else saved_grid(a.resume)
