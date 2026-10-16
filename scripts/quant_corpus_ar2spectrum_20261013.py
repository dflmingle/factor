"""Reviewed MESA AR2 mathematics; explicit800 DAILYbar research extension.
The source four-week minute differences sampled every6minutes are unavailable.
"""
import json
import numpy as np
import pandas as pd
from numba import njit
from statsmodels.tsa.ar_model import AutoReg
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2021年度精选策略/83.识别趋势震荡之神器 MESA最大熵谱分析（一）：滤波器建立.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source105-20261013'
COMMON='proxy NEWresearch extension: source Filter needs actual4CALweeks of MINUTEfirstdifferences sampled every6, unavailable. Replace with800DAILYfirstdifferences (nominal20tradingdays*40samples), entirelydifferent timehorizon; NOT source fullfilter or source performance. Preserve AutoReg2 defaultintercept, source spectrum1000frequencygrid and offbyonefrequency conversion idx/2000. Signal uses priorcompletedclose, no model/horizon tuning; no claim independentOOS.'
SPECS=[
 spec('mesa83_ar2_800daily_lowfrequency','AR二阶价格差分低主频',SRC,'-argmax_source1000SpectrumGrid(phi1,phi2)/2000; AR2 fittedpast800dailypricechanges',COMMON+' Rank -frequency keeps index0finite instead of dropping infinite sourceperiodT; source has no stockranking, highandlow direction are fixed controls.'),
 spec('mesa83_ar2_800daily_highfrequency_control','AR二阶价格差分高主频对照',SRC,'+argmax_source1000SpectrumGrid(phi1,phi2)/2000',COMMON+' Directioncontrol only, no newcluster count for opposite direction.'),
 spec('mesa83_ar2_800daily_forecast','AR二阶价格差分因果一步预测',SRC,'(intercept+phi1*lastPriceDiff+phi2*prevPriceDiff)/lastClose',COMMON+' NEW directional extension of fittedAR2; source outputsperiodONLY, not forecastalpha. Normalization by currentknownclose, not全样本个股标准化.')]

@njit(cache=True)
def frequency(a,b):
 if a==b:return 0.
 # Exact discrete grid maximum via quadratic denominator extrema.
 candidates=np.array([0,999,0,0,0],dtype=np.int64)
 if b<0:
  u=-a*(1-b)/(4*b);u=max(-1.,min(1.,u));idx=int(np.arccos(u)/np.pi*999)
  candidates[2]=max(0,idx-1);candidates[3]=idx;candidates[4]=min(999,idx+1)
 best=np.inf;bestidx=0
 for k in candidates:
  angle=np.pi*k/999;den=1+a*a+b*b-2*a*(1-b)*np.cos(angle)-2*b*np.cos(2*angle)
  if den<best or (den==best and k<bestidx):best=den;bestidx=k
 return bestidx/2000.

def values(c,pos):
 out=[np.full((len(pos),c.shape[1]),np.nan) for _ in SPECS]
 for i,t in enumerate(pos):
  hist=c[t-801:t].astype(float);ok=np.isfinite(hist).all(axis=0)&(hist>0).all(axis=0);ids=np.flatnonzero(ok)
  if not len(ids):continue
  d=np.diff(hist[:,ids],axis=0);y=d[2:];x1=d[1:-1];x2=d[:-2];ym=y.mean(axis=0);m1=x1.mean(axis=0);m2=x2.mean(axis=0)
  yc=y-ym;a=x1-m1;b=x2-m2;v1=(a*a).sum(axis=0);v2=(b*b).sum(axis=0);cv=(a*b).sum(axis=0);c1=(a*yc).sum(axis=0);c2=(b*yc).sum(axis=0);det=v1*v2-cv*cv
  valid=(v1>0)&(v2>0)&(det>1e-12*v1*v2);p1=np.full(len(ids),np.nan);p2=p1.copy();p1[valid]=(c1*v2-c2*cv)[valid]/det[valid];p2[valid]=(c2*v1-c1*cv)[valid]/det[valid]
  intercept=ym-p1*m1-p2*m2;forecast=(intercept+p1*d[-1]+p2*d[-2])/hist[-1,ids]
  freq=np.array([frequency(float(a0),float(b0)) if valid[k] else np.nan for k,(a0,b0) in enumerate(zip(p1,p2))])
  for target,x in zip(out,[-freq,freq,forecast]):target[i,ids]=x
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='AR2 structure fromsource,800daily explicitNEWbarcount extension andthreefixeddiagnostics; noAIC/horizon/sign search')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64];whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values(small[:stop],pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-8,atol=1e-8);checks.append(dict(key=sp['key'],test='daily800window_causal_fit_prefix',stop=stop,passed=True))
 rng=np.random.default_rng(10583);tested=0
 for _ in range(100):
  a,b=rng.uniform(-1,1,2);sigma=np.std([a,b]);fg=np.linspace(0,.5,1000);density=(2*sigma)/(np.abs(1-a*np.exp(-2j*np.pi*fg)-b*np.exp(-4j*np.pi*fg))**2);idx=list(density).index(max(density))
  assert frequency(float(a),float(b))==idx/2000;tested+=1
 for i in [35,79]:
  for j in range(12):
   hist=small[pos[i]-801:pos[i],j].astype(float)
   if not np.isfinite(hist).all():continue
   d=np.diff(hist);fit=AutoReg(d,lags=2,trend='c',old_names=False).fit();pred=fit.predict(start=len(d),end=len(d))[0]/hist[-1]
   np.testing.assert_allclose(whole[2][i,j],pred,rtol=1e-7,atol=1e-10)
 checks.append(dict(test='independent_statsmodels_AutoReg2_and_literal1000complexSpectrum',frequency_cases=tested,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 vals=values(f['close'],pos);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='NEWdaily research extension, originalminute model NOTreproduced'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED105',flush=True)
if __name__=='__main__':main()
