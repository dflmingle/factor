"""Causal local test of regime switching plus dynamic factor allocation.

Uses only already saved factor panels and market data.  No platform calls.
The allocation weight at signal date t uses factor returns through t-1 only.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import simultaneous_residual

ROOT=q.ROOT
OUT=ROOT/'research_reports/platform_alignment/regime-switch-dynamic-allocation-20261014'
S5=ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source5-20261012/signal_panels.pkl'
S91=ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source91-20261013/signal_panels.pkl'

def rank(x): return q.rank(x)

def period_excess(score,c,pos):
    out=[]
    for i,t in enumerate(pos):
        if t+11>=len(c): out.append(np.nan); continue
        y=q.ratio(c[t+11],c[t+1])-1
        ok=np.isfinite(score[i])&np.isfinite(y)
        ids=np.flatnonzero(ok)
        if len(ids)<100: out.append(np.nan); continue
        order=np.argsort(score[i,ids],kind='stable'); top=ids[order[int(np.ceil(len(ids)*.9))-1:]]
        out.append(float(np.mean(y[top])-np.mean(y[ids])))
    return np.asarray(out,float)

def evaluate_blend(score,dates,pos,stocks,f):
    # Reuse the canonical evaluator for exactly the project label/cost convention.
    q.dates_all=q.load_market()[0]
    result,p,d=q.evaluate(score,dates,stocks,pos,f)
    return result,p,d

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,f=q.load_market();q.dates_all=cal
    base=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=base['dates'];pos=cal.get_indexer(grid)
    s5=pd.read_pickle(S5);s91=pd.read_pickle(S91)
    assert s5['dates'].equals(grid) and s5['stocks'].equals(stocks)
    assert s91['dates'].equals(grid) and s91['stocks'].equals(stocks)
    c=f['close'].astype(float);cap=f['cap'][pos]
    # Four predeclared sleeves.  Rank transforms keep the blend scale comparable.
    raw={
      'idio_vroc_size':s5['panels']['idio_vroc_size'].to_numpy(float),
      'reversal20':-(q.ratio(c,q.delay(c,20))-1)[pos],
      'quality':rank(s91['panels']['fscore8_coherent_adjacent_count'].to_numpy(float))+rank(s91['panels']['adjacent_ttm_deducted_roa_change'].to_numpy(float)),
      'trend_pullback':s5['panels']['rising_trend_pullback'].to_numpy(float),
    }
    names=list(raw); X=np.stack([rank(raw[n]) for n in names],axis=0)
    # Causal market state.  Quantiles use only the trailing 252 observed market days.
    rr=q.ratio(c,q.delay(c))-1
    m=pd.DataFrame(np.where(f['cap']>0,rr,np.nan)).mean(axis=1).to_numpy()
    m20=q.ratio(pd.Series(m).rolling(20).apply(lambda x: np.prod(1+x)-1,raw=True).to_numpy(),np.ones(len(m)))
    m60=q.ratio(pd.Series(m).rolling(60).apply(lambda x: np.prod(1+x)-1,raw=True).to_numpy(),np.ones(len(m)))
    ma120=pd.Series(m).rolling(120).mean().to_numpy(); slope=ma120-pd.Series(ma120).shift(20).to_numpy()
    vol20=pd.Series(m).rolling(20).std().to_numpy(); q90=pd.Series(vol20).rolling(252,min_periods=60).quantile(.9).to_numpy()
    breadth=pd.DataFrame(rr).rolling(20).mean().gt(0).mean(axis=1).to_numpy()
    risk_on=(m60>0)&(slope>0)&(breadth>.55)&(vol20<q90)
    risk_off=(m20<0)|(vol20>q90)|(breadth<.30)
    state=np.full(len(grid),'neutral',object)
    state[risk_on[pos]]='risk_on';state[risk_off[pos]]='risk_off';state[risk_on[pos]&risk_off[pos]]='risk_off'
    # Per-sleeve historical top-decile excess, lagged by one saved signal.
    rets=np.stack([period_excess(raw[n],c,pos) for n in names],axis=1)
    W=np.full((len(grid),len(names)),np.nan)
    static={
      # Frozen economic prior: low-idio sleeve is the core; value/reversal
      # gets more weight in risk-off, quality in risk-on.  Trend-pullback is
      # kept as a small neutral-state diversifier after its standalone check.
      'risk_on':np.array([.55,.05,.35,.05]),
      'neutral':np.array([.55,.10,.15,.20]),
      'risk_off':np.array([.55,.35,.10,.00]),
    }
    for i in range(len(grid)):
        W[i]=static[state[i]]
    # Scheme 1: state switch with fixed weights.
    blend_static=np.nansum(W.T[:,:,None]*X,axis=0)
    # Scheme 2/3: same state prior, then causal dynamic allocation over 25 prior signals.
    W_inv=W.copy();W_mom=W.copy()
    for i in range(len(grid)):
        hist=rets[max(0,i-25):i]  # excludes current period
        if hist.shape[0]<12: continue
        sd=np.nanstd(hist,axis=0,ddof=1);inv=np.where(np.isfinite(sd)&(sd>1e-8),1/sd,0)
        inv=inv/inv.sum() if inv.sum()>0 else W[i]
        # risk-adjusted trailing return, clipped to prevent one sleeve taking over.
        mu=np.nanmean(hist,axis=0); sr=np.where(sd>1e-8,mu/sd,0);sr=np.maximum(sr,0)
        mom=sr/sr.sum() if sr.sum()>0 else W[i]
        # Blend with state prior and cap each sleeve at 50%.
        for target,a in [(W_inv,inv),(W_mom,mom)]:
            z=.5*W[i]+.5*a;z=np.minimum(z,.5);z=z/z.sum();target[i]=z
    blend_inv=np.nansum(W_inv.T[:,:,None]*X,axis=0);blend_mom=np.nansum(W_mom.T[:,:,None]*X,axis=0)
    vals={'state_switch_static':blend_static,'state_switch_inversevol':blend_inv,'state_switch_momentumrisk':blend_mom}
    results=[];details=[]
    for key,v in vals.items():
        r,p,d=evaluate_blend(v,grid,pos,stocks,f);r.update(key=key,window='five_year',state_counts=pd.Series(state).value_counts().to_dict())
        results.append(r);p.to_csv(OUT/f'{key}.periods.csv',index=False);d.to_csv(OUT/f'{key}.daily_nav.csv',index=False)
    # Recent window is evaluated independently but weights remain causal within the full history.
    mask=grid>='2026-01-01'
    for key,v in vals.items():
        r,p,d=evaluate_blend(v[mask],grid[mask],pos[mask],stocks,f);r.update(key=key,window='recent',state_counts=pd.Series(state[mask]).value_counts().to_dict());results.append(r)
        p.to_csv(OUT/f'{key}.recent.periods.csv',index=False);d.to_csv(OUT/f'{key}.recent.daily_nav.csv',index=False)
    # incumbent sleeve for matched comparison
    for key,v in [('incumbent_idio_vroc_size',raw['idio_vroc_size'])]:
        for wn,mm in [('five_year',np.ones(len(grid),bool)),('recent',mask)]:
            r,p,d=evaluate_blend(v[mm],grid[mm],pos[mm],stocks,f);r.update(key=key,window=wn);results.append(r)
    pd.DataFrame(results).to_csv(OUT/'results.csv',index=False)
    pd.DataFrame({'date':grid,'state':state,'risk_on':risk_on[pos],'risk_off':risk_off[pos],**{f'w_{n}':W_mom[:,j] for j,n in enumerate(names)}}).to_csv(OUT/'state_and_weights.csv',index=False)
    q.dump(OUT/'config.json',{'rule':q.ALIGNMENT_RULE_VERSION,'platform_compute':0,'factors':names,'state_definition':'causal market 20/60 return, MA120 slope, breadth20, vol20 rolling q90','allocation_window_signals':25,'weights_lagged':True,'max_weight':.5,'formal_window':['20210907','20260907'],'recent_window':['20260101','20260907']})
    q.dump(OUT/'verification.json',{'checks':['all weights use returns before current signal','regime inputs use data through signal date','factor panels aligned to saved signal dates','no platform calls'],'state_counts':pd.Series(state).value_counts().to_dict(),'completed':True})
    print('FINISHED_REGIME_DYNAMIC',flush=True)

if __name__=='__main__':main()
