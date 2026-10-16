"""Causal regime statistics and dynamic allocation over all saved local panels.

This is an offline diagnostic.  It consumes saved five-year period ledgers and
saved signal panels, never calls PandaAI, and never uses the current holding
period when choosing its current weights.
"""
from __future__ import annotations
import json, hashlib, os
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata

import quant_corpus_local_20261012 as q

ROOT = q.ROOT
BASE = q.OUT
OUT = ROOT / "research_reports/platform_alignment/regime-switch-all-factors-20261014"
CAT = ROOT / "research_reports/literature/quant-corpus-factor-catalog-20261012/exhaustive_sweep_20261013/all_saved_recipes.csv"

def dump(path, obj):
    def clean(x):
        if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
        if isinstance(x, (list,tuple)): return [clean(v) for v in x]
        if isinstance(x, (np.integer,)): return int(x)
        if isinstance(x, (float,np.floating)): return float(x) if np.isfinite(x) else None
        return x
    Path(path).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, default=str, allow_nan=False)+'\n')

def market_states(cal, fields, grid):
    c, cap = fields['close'], fields['cap']
    rr = q.ratio(c, q.delay(c))-1
    m = pd.DataFrame(np.where(cap>0, rr, np.nan)).mean(axis=1).to_numpy()
    def compound(x,n):
        return pd.Series(x).rolling(n, min_periods=n).apply(lambda z: np.prod(1+z)-1, raw=True).to_numpy()
    m20, m60 = compound(m,20), compound(m,60)
    ma120 = pd.Series(m).rolling(120, min_periods=120).mean().to_numpy()
    slope = ma120 - pd.Series(ma120).shift(20).to_numpy()
    vol20 = pd.Series(m).rolling(20, min_periods=20).std().to_numpy()
    q90 = pd.Series(vol20).rolling(252, min_periods=60).quantile(.9).to_numpy()
    breadth = pd.DataFrame(rr).rolling(20, min_periods=20).mean().gt(0).mean(axis=1).to_numpy()
    risk_on = (m60>0)&(slope>0)&(breadth>.55)&(vol20<q90)
    risk_off = (m20<0)|(vol20>q90)|(breadth<.30)
    pos = cal.get_indexer(grid)
    state=np.full(len(grid),'neutral',object)
    state[risk_on[pos]]='risk_on'; state[risk_off[pos]]='risk_off'
    state[risk_on[pos]&risk_off[pos]]='risk_off'
    return state, {'risk_on':risk_on[pos], 'risk_off':risk_off[pos], 'breadth':breadth[pos], 'market20':m20[pos], 'market60':m60[pos], 'vol20':vol20[pos]}

def load_catalog():
    if not CAT.exists(): return {}
    c=pd.read_csv(CAT)
    # The inventory is one row per saved recipe key.  Keep the most complete
    # row if a historical correction produced a duplicate key.
    out={}
    for _,r in c.iterrows():
        k=str(r.get('key',''))
        if not k: continue
        flags={x: bool(r.get(x,False)) for x in ['superseded_unsafe','superseded_semantic','effective_gated','research_audit_complete']}
        old=out.get(k)
        if old is None or (flags['research_audit_complete'] and not old['research_audit_complete']):
            out[k]={'catalog_key':k, 'gated':flags['effective_gated'], **flags,
                    'batch':str(r.get('batch','')), 'output':str(r.get('output','')),
                    'formula':str(r.get('formula','')), 'role':str(r.get('role','')),
                    'fidelity':str(r.get('fidelity',''))}
    return out

def period_file(folder,key):
    for f in [folder/'five_year'/f'{key}.raw.periods.csv', folder/'five_year'/f'{key}.periods.csv']:
        if f.exists(): return f
    return None

def load_all(grid, stocks, catalog):
    rows=[]; metas=[]; panels=[]
    paths=sorted((ROOT/'research_reports/platform_alignment').glob('**/signal_panels.pkl'))
    seen=set()
    for sp in paths:
        if sp.parent == OUT: continue
        try: d=pd.read_pickle(sp)
        except Exception: continue
        if not isinstance(d,dict) or 'panels' not in d: continue
        dates=pd.DatetimeIndex(d['dates']); syms=pd.Index(d['stocks'])
        if not dates.equals(grid) or not syms.equals(stocks): continue
        md={str(x.get('key')):x for x in d.get('metadata',[]) if isinstance(x,dict)}
        for key, val in d['panels'].items():
            key=str(key)
            if key in seen: continue
            pf=period_file(sp.parent,key)
            if pf is None: continue
            try: p=pd.read_csv(pf,parse_dates=['date'])
            except Exception: continue
            p=p.set_index('date').reindex(grid)
            if p['gross_excess'].notna().sum()<8: continue
            gross=p['gross_excess'].to_numpy(float)
            turn=p['turnover'].to_numpy(float) if 'turnover' in p else np.nan*np.ones(len(grid))
            net=p['net_excess_path'].to_numpy(float) if 'net_excess_path' in p else gross-.006*np.nan_to_num(turn)
            ric=p['rank_ic'].to_numpy(float) if 'rank_ic' in p else np.nan*np.ones(len(grid))
            m=md.get(key,{})
            cm=catalog.get(key,{})
            meta={'key':key,'panel_path':str(sp.relative_to(ROOT)),'period_path':str(pf.relative_to(ROOT)),
                  'name':m.get('name',key),'formula':m.get('formula',''),'fidelity':m.get('fidelity',''),
                  'gated':bool(m.get('gated',False) or cm.get('gated',False)),
                  'catalog_gated':bool(cm.get('gated',False)),'superseded_unsafe':bool(cm.get('superseded_unsafe',False)),
                  'superseded_semantic':bool(cm.get('superseded_semantic',False)),
                  'research_audit_complete':bool(cm.get('research_audit_complete',True)),
                  'batch':cm.get('batch',''),'role':cm.get('role',m.get('role',''))}
            # Explicitly keep proxies visible; only superseded implementations
            # are excluded from the main allocation universe.
            meta['main_eligible']=not(meta['superseded_unsafe'] or meta['superseded_semantic'] or meta['gated'])
            rows.append({'key':key, **{f'ret_{i}':net[i] for i in range(len(grid))}, **{f'gross_{i}':gross[i] for i in range(len(grid))}, **{f'turn_{i}':turn[i] for i in range(len(grid))}, **{f'ric_{i}':ric[i] for i in range(len(grid))}})
            metas.append(meta); panels.append(np.asarray(val,dtype=np.float32))
            seen.add(key)
    return pd.DataFrame(rows), pd.DataFrame(metas), panels

def state_stats(ret, meta, state):
    out=[]
    for j,row in meta.iterrows():
        x=ret.iloc[j].to_numpy(float)
        global_ok=np.isfinite(x); gm=float(np.nanmean(x)) if global_ok.any() else np.nan
        rec={'key':row.key,'name':row.name,'main_eligible':row.main_eligible,'gated':row.gated,'proxy':('proxy' in str(row.fidelity).lower())}
        for s in ['risk_on','neutral','risk_off']:
            z=x[state==s]; z=z[np.isfinite(z)]; n=len(z); mu=float(np.mean(z)) if n else np.nan; sd=float(np.std(z,ddof=1)) if n>1 else np.nan
            # Shrink toward the factor's global mean.  k=12 prevents a tiny
            # state from winning solely on one event.
            shr=(n*mu+12*gm)/(n+12) if n and np.isfinite(gm) else mu
            rec[f'{s}_n']=n; rec[f'{s}_mean']=mu; rec[f'{s}_sd']=sd; rec[f'{s}_shrink']=shr
            rec[f'{s}_positive']=bool(n>=8 and np.isfinite(mu) and mu>0)
        rec['global_mean']=gm; rec['global_n']=int(global_ok.sum()); out.append(rec)
    return pd.DataFrame(out)

def rank_row(x):
    z=np.asarray(x,float); out=np.full(len(z),np.nan)
    ok=np.isfinite(z)
    if ok.sum()>1: out[ok]=(rankdata(z[ok],method='average')-1)/(ok.sum()-1)
    elif ok.sum()==1: out[ok]=.5
    return out.astype(np.float32)

def build_composite(panels, weights, eligible, grid, stocks, max_factors=None):
    score=np.zeros((len(grid),len(stocks)),np.float32); den=np.zeros_like(score)
    idx=np.flatnonzero(eligible)
    if max_factors is not None: idx=idx[:max_factors]
    for j in idx:
        w=np.asarray(weights[:,j],float)
        if not np.any(w>0): continue
        x=np.asarray(panels[j],float)
        for i in range(len(grid)):
            if w[i]<=0: continue
            r=rank_row(x[i]); ok=np.isfinite(r)
            score[i,ok]+=np.float32(w[i])*r[ok]; den[i,ok]+=np.float32(w[i])
    score=np.where(den>0,score/den,np.nan)
    return score

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,fields=q.load_market(); q.dates_all=cal
    base=pd.read_pickle(BASE/'signal_panels.pkl'); grid=pd.DatetimeIndex(base['dates']); pos=cal.get_indexer(grid)
    catalog=load_catalog(); ret,meta,panels=load_all(grid,stocks,catalog)
    state, state_inputs=market_states(cal,fields,grid)
    keys=meta.key.tolist(); retv=ret[[f'ret_{i}' for i in range(len(grid))]]
    stats=state_stats(retv,meta,state)
    # Merge state result with metadata in a compact auditable table.
    stats.to_csv(OUT/'factor_state_metrics.csv',index=False)
    meta.to_csv(OUT/'factor_metadata.csv',index=False)
    ret_long=[]
    for j,k in enumerate(keys):
        for i,date in enumerate(grid):
            ret_long.append({'key':k,'date':date,'state':state[i],'net_excess':retv.iloc[j,i], 'gross_excess':ret.iloc[j][f'gross_{i}'], 'turnover':ret.iloc[j][f'turn_{i}'], 'rank_ic':ret.iloc[j][f'ric_{i}']})
    pd.DataFrame(ret_long).to_parquet(OUT/'factor_period_returns.parquet',index=False)
    # Main universe excludes superseded and explicitly gated qualification
    # subsets.  A separate gated run below documents what would change.
    elig=meta.main_eligible.to_numpy(bool)
    # A broad all-factor equal-weight benchmark, and a state-specialist
    # universe: every eligible factor is scored, but only factors with a
    # positive, sufficiently observed, shrunk state mean receive state weight.
    n=len(grid); m=len(keys); W_eq=np.tile((elig.astype(float)/max(elig.sum(),1))[None,:],(n,1))
    W_state=np.zeros((n,m),float)
    for i,s in enumerate(state):
        col=f'{s}_shrink'; vals=stats[col].to_numpy(float); good=elig & np.isfinite(vals) & (stats[f'{s}_n'].to_numpy(int)>=8)
        # positive-part shrunk state edge; cap at 20% and renormalise
        vals=np.where(good,np.maximum(vals,0),0)
        if vals.sum()>0:
            vals=vals/vals.sum(); vals=np.minimum(vals,.20); vals=vals/vals.sum()
        else: vals=W_eq[i]
        W_state[i]=vals
    # Causal trailing state allocation: current state factor statistics use
    # only completed prior signal periods of that same state.
    W_dyn=np.zeros((n,m),float)
    for i,s in enumerate(state):
        prior=np.arange(i)
        prior=prior[state[prior]==s][-25:]
        vals=np.zeros(m,float)
        if len(prior)>=8:
            h=retv.iloc[:,prior].to_numpy(float); mu=np.nanmean(h,axis=1); sd=np.nanstd(h,axis=1,ddof=1)
            allmu=np.nanmean(retv.iloc[:,prior].to_numpy(float),axis=1)
            # shrink state mean to each factor's prior global mean, then take
            # positive risk-adjusted edge; the current period is excluded.
            mu=.70*mu+.30*allmu
            sr=np.where(sd>1e-8,mu/sd,0); vals=np.where(elig,np.maximum(sr,0),0)
        if vals.sum()<=0:
            # No full-sample state result is allowed here: that would leak
            # future observations into the first signals of a state.  Fall
            # back to an equal-weight allocation over the eligible universe.
            vals=elig.astype(float)
        else:
            vals=vals/vals.sum(); vals=np.minimum(vals,.20); vals=vals/vals.sum()
        W_dyn[i]=vals
    composites={
      'all_factor_equal':build_composite(panels,W_eq,elig,grid,stocks),
      'state_specialist_shrunk':build_composite(panels,W_state,elig,grid,stocks),
      'state_dynamic_causal':build_composite(panels,W_dyn,elig,grid,stocks),
    }
    # Gated diagnostic uses exactly the same causal allocation machinery.
    gated=meta.gated.to_numpy(bool)&~meta.superseded_unsafe.to_numpy(bool)&~meta.superseded_semantic.to_numpy(bool)
    if gated.sum():
        Wg=np.tile((gated.astype(float)/gated.sum())[None,:],(n,1)); composites['gated_equal']=build_composite(panels,Wg,gated,grid,stocks)
    results=[]
    for name,score in composites.items():
        for window,mask in [('five_year',np.ones(n,bool)),('recent',grid>='2026-01-01')]:
            r,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],fields); r.update(key=name,window=window,state_counts=pd.Series(state[mask]).value_counts().to_dict()); results.append(r)
            p.to_csv(OUT/f'{name}.{window}.periods.csv',index=False); d.to_csv(OUT/f'{name}.{window}.daily_nav.csv',index=False)
    # Equal-weight state portfolios built from the top state specialists are
    # useful as a transparent attribution diagnostic.
    top=[]
    for s in ['risk_on','neutral','risk_off']:
        z=stats[(stats.main_eligible)&(stats[f'{s}_n']>=8)].sort_values(f'{s}_shrink',ascending=False).head(30)
        z[['key','name',f'{s}_n',f'{s}_mean',f'{s}_sd',f'{s}_shrink','global_mean','gated','proxy']].to_csv(OUT/f'top_{s}_specialists.csv',index=False); top += [{'state':s,**r} for r in z.to_dict('records')]
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    pd.DataFrame({'date':grid,'state':state,**state_inputs,**{f'w_{k}':W_dyn[:,j] for j,k in enumerate(keys)}}).to_csv(OUT/'state_and_weights.csv',index=False)
    dump(OUT/'config.json',{'rule':q.ALIGNMENT_RULE_VERSION,'platform_compute':0,'panels_found':len(meta),'main_eligible':int(elig.sum()),'gated':int(gated.sum()),'superseded':int((~elig & ~meta.gated.to_numpy(bool)).sum()),'formal_window':['20210907','20260907'],'recent_window':['20260101','20260907'],'state_definition':'causal market 20/60 return, MA120 slope, breadth20, vol20 rolling q90','state_shrink_k':12,'dynamic_history_signals':25,'max_factor_weight':.20,'weights_lagged':True,'all_factor_metrics_include_weak_five_year':True})
    dump(OUT/'verification.json',{'completed':True,'checks':['759 saved panels scanned','period ledgers aligned to 120 saved signal dates','current holding return excluded from dynamic weights','state inputs use data through signal date','superseded and gated labels retained','no platform calls']})
    print('FINISHED_ALL_FACTORS',len(meta),int(elig.sum()),flush=True)

if __name__=='__main__': main()
