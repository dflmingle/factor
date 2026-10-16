"""Reviewed EPO lowrisk/momentum translation; repair explicit, no ETF claims."""
import json
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from scipy.linalg import solve
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/量化策略/量化策略/ETF轮动策略2026/06-EPO低相关ETF轮动策略-25年47.txt'
B='quant/量化策略/量化策略/ETF轮动策略2026/05动量最强ETF轮动策略-调优版-25年83.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source113-20261013'
SPECS=[
 spec('epo06_invvar_mom249_composite','逆方差与二百四十九日动量等权',A,'.5*normalize(inv sampleVAR249(simpleRET))+.5*normalize(CSrank(RET249)), endingt-1',
 'proxy NEW fullA extension: original250pricepoints249returns; sampleVAR, average rank; complete250price eligible subset. Source panel=False[close] flattened long frame does not pivot symbol, repaired explicitly. Composite only, not actual ETF allocation/strategy.'),
 spec('epo06_shrink60_cov_composite','六成收缩协方差优化复合信号',A,'positive normalize(inv(.4*cov249+.6*diagcov249)*composite/10)',
 'proxy NEW fullA allocationweights used as ranking, not native ETF strategy. Source simpleEPO(.6), lambda10/clipping retained, repaired date-symbol pivot. Woodbury solves mathematically same matrix without materializing5456square; completehistory subset, qfq. Zero weights ties audited; no historical alpha selection.'),
 spec('weighted25_priorclose_fulla','前收盘二十五点线性加权趋势',B,'expm1(250*slopeW25(logC))*sourceR2W25, endingt-1',
 'proxy: source polyfit uses w² regression, but R2 unsquaredw with unweightedmean. Source29:30 means priorcompletedbar; distinct timing from source67 currentbar weightedtrend, known family only.'),
 spec('weighted25_priorclose_amount20_gate','成交额约束加权趋势',B,'weighted25 endingt-1 where MEAN20(amount)*1000>=1e7',
 'proxy: source1000万元 liquidity threshold, Tushare dailyamount thousandsyuan mapped explicitly; qfqclose and fullAstockextension ETFpool/top2 omitted; skip_paused source means20valid sessions, ours calendar20complete amounts so proxy disclosed.')]
for s in SPECS[:2]+SPECS[3:]:s['gated']=True

def epocore(c):
 r=c[1:]/c[:-1]-1;z=r-r.mean(axis=0);d=(z*z).sum(axis=0)/(len(r)-1)
 valid=np.isfinite(r).all(axis=0)&(d>1e-14);ids=np.flatnonzero(valid);out=np.full((2,c.shape[1]),np.nan)
 if len(ids)<2:return out
 z=z[:,ids];d=d[ids];a=1/d;a/=a.sum();mom=rankdata(c[-1,ids]/c[0,ids]-1,method='average');mom/=mom.sum();s=.5*a+.5*mom
 # C=.6*D + U.T@U, U=sqrt(.4/(n-1))*demeanedreturns.
 u=z*np.sqrt(.4/(len(r)-1));di=1/(.6*d);v=di*s
 middle=np.eye(len(r))+(u*di)@u.T
 sol=v-di*(u.T@solve(middle,u@v,assume_a='pos'))
 w=np.maximum(sol/10,0);w/=w.sum() if w.sum()>0 else np.nan
 out[0,ids]=s;out[1,ids]=w;return out

def values(f,pos):
 c=f['close'].astype(float);out=[np.full((len(pos),c.shape[1]),np.nan) for _ in SPECS];w=np.linspace(1,2,25);ww=w*w;x=np.arange(25);xm=np.sum(ww*x)/ww.sum();xc=x-xm;den=np.sum(ww*xc*xc)
 amt=pd.DataFrame(f['amount'].astype(float)).rolling(20).mean().to_numpy()
 for i,t in enumerate(pos):
  a=c[t-250:t];ids=np.flatnonzero(np.isfinite(a).all(axis=0)&(a>0).all(axis=0)&(f['cap'][t]>0))
  if len(ids)>1:
   p=epocore(a[:,ids]);out[0][i,ids]=p[0];out[1][i,ids]=p[1]
  a=c[t-25:t];good=np.isfinite(a).all(axis=0)&(a>0).all(axis=0);y=np.log(a[:,good]);ym=(ww[:,None]*y).sum(axis=0)/ww.sum();s=(ww[:,None]*xc[:,None]*y).sum(axis=0)/den;b=ym-s*xm
  tot=(w[:,None]*(y-y.mean(axis=0))**2).sum(axis=0);r2=1-(w[:,None]*(y-x[:,None]*s-b)**2).sum(axis=0)/np.where(tot>0,tot,np.nan)
  out[2][i,good]=np.where(tot>0,np.expm1(250*s)*r2,0.);out[3][i]=np.where(amt[t-1]*1000>=1e7,out[2][i],np.nan)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source fixed250/simpleEPO.6 and25/liquidity20 before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_covariance_and_weights',passed=True))
 rng=np.random.default_rng(113);c=np.exp(np.cumsum(rng.normal(0,.02,size=(250,64)),axis=0));p=epocore(c);r=pd.DataFrame(c).pct_change().dropna();cov=r.cov().to_numpy();ref=solve(.4*cov+.6*np.diag(np.diag(cov)),p[0])/10;ref=np.maximum(ref,0);ref/=ref.sum()
 np.testing.assert_allclose(p[1],ref,rtol=1e-8,atol=1e-10);checks.append(dict(test='independent_dense_covariance_solve_vs_woodbury64',passed=True))
 obs=0
 for i in [35,79]:
  for j in range(64):
   t=pos[i];a=small['close'][t-25:t,j].astype(float)
   if np.isfinite(a).all():
    y=np.log(a);x=np.arange(25);w=np.linspace(1,2,25);s,b=np.polyfit(x,y,1,w=w);total=np.sum(w*(y-y.mean())**2);ref=np.expm1(250*s)*(1-np.sum(w*(y-s*x-b)**2)/total) if total>0 else 0.
    np.testing.assert_allclose(whole[2][i,j],ref,atol=1e-8);obs+=1
 checks.append(dict(test='independent_source_numpy_polyfit_squaredw_and_unsquaredR2',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='explicit pivot repair and fullA weights as factor adaptation'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED113',flush=True)
if __name__=='__main__':main()
