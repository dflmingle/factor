"""Source47 conditional quadratic curvature, dual trend and polynomial RSI tails."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/47多策略整合大E小十年百倍（年化64）.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source103-20261013'
COMMON='proxy: exact reviewed WPETF get_rank PRICE kernel on past25completedcloses, weights exp(linspace(-1,0,25)), smooth5 logconvolution and LAST21 weights retained. Source ETFs->stockextension; latest2sold ETF blacklist, riskssum, subportfolios and other2strategylegs omitted. No claim full multistrategy return. Source RSI uses9 LOGchanges, not Wilder14 or10pricechanges.'
SPECS=[
 spec('wpetf47_curvature_adjusted25','二次曲率条件修正二十五日趋势',SRC,
 'expm1(250*slopeAdjusted25)*R2_25; zero slope aboveMA20 with rawcurve<-.0006 OR smoothcurve<-.0003; boost+.005 belowMA20 with oppositecurves',COMMON),
 spec('wpetf47_dual25_15_conditional','十五日高拟合度条件替代趋势',SRC,
 'replace curvature25score by expm1(250*slope15)*R2_15 iff R2_15>=.8 AND score15>score25',COMMON),
 spec('wpetf47_polyrsi_tail_cap25','九个对数变化RSI五次多项式尾部修正',SRC,
 'dualScore; RSI>95 ->0, RSI<10 -> +poly5(RSI)/8; resulting score>=25 ->0',COMMON+' Sourcepolyfit knots[1,10,...90,99],target[50,2,.1,0,...0,-.1,-2,-50] fixed; no fittedalpha parameters.'),
 spec('wpetf47_positive001_qualified','曲率双趋势尾部修正后正分资格',SRC,
 'finalScore where finalScore>.01',COMMON+' Source positive001 qualification retained; factor_valid subset benchmark; fixedETFtop1 and soldblacklist absent.')]
SPECS[-1]['gated']=True
KNOTS=np.array([1,10,20,30,40,50,60,70,80,90,99])
TARGET=np.array([50,2,.1,0,0,0,0,0,-.1,-2,-50])
POLY=np.polyfit(KNOTS,TARGET,5)
W=np.exp(np.linspace(-1,0,25))
def quad_operator(n,w):
 x=np.arange(n);design=np.column_stack([x*x,x,np.ones(n)])
 return np.linalg.pinv(design*w[:,None])*w[None,:]
Q25=quad_operator(25,W);Q21=quad_operator(21,W[-21:])

def trend(y):
 x=np.arange(len(y));xc=x-x.mean();yc=y-y.mean(axis=0);s=(xc[:,None]*yc).sum(axis=0)/(xc*xc).sum()
 tot=(yc*yc).sum(axis=0);r2=1-((yc-xc[:,None]*s)**2).sum(axis=0)/np.where(tot>0,tot,np.nan)
 return s,r2

def panel(x):
 y=np.log(x);s,r2=trend(y);ss,rr=trend(y[-15:]);curve=(Q25@y)[0]
 smooth=sum(y[k:k+21] for k in range(5))/5;cs=(Q21@smooth)[0];above=x[-1]>x[-20:].mean(axis=0);below=x[-1]<x[-20:].mean(axis=0)
 sadj=np.where(above&((cs<-.0003)|(curve<-.0006)),0,np.where(below&((cs>.0003)|(curve>.0006)),s+.005,s))
 base=np.expm1(250*sadj)*r2;short=np.expm1(250*ss)*rr;dual=np.where((rr>=.8)&(short>base),short,base)
 changes=np.diff(y[-10:],axis=0);gain=np.maximum(changes,0).sum(axis=0);loss=-np.minimum(changes,0).sum(axis=0);loss=np.where(loss==0,1e-6,loss);rsi=100-100/(1+gain/loss)
 final=np.where(rsi>95,0,dual);final=np.where(rsi<10,final+np.polyval(POLY,rsi)/8,final);final=np.where(final>=25,0,final)
 return [base,dual,final,np.where(final>.01,final,np.nan)]

def values(c,pos):
 out=[np.full((len(pos),c.shape[1]),np.nan) for _ in SPECS]
 for i,t in enumerate(pos):
  x=c[t-25:t].astype(float);ok=np.isfinite(x).all(axis=0)&(x>0).all(axis=0)
  if not ok.any():continue
  for a,b in zip(out,panel(x[:,ok])):a[i,ok]=b
 return out

def literal(x):
 y=np.log(x);t=np.arange(25);s,b=np.polyfit(t,y,1);ss,bs=np.polyfit(t[-15:],y[-15:],1);cv=np.polyfit(t,y,2,w=W)[0]
 smooth=np.convolve(y,np.ones(5)/5,mode='valid');cs=np.polyfit(np.arange(len(smooth)),smooth,2,w=W[-len(smooth):])[0]
 sadj=s
 if x[-1]>x[-20:].mean() and (cs<-.0003 or cv<-.0006):sadj=0
 elif x[-1]<x[-20:].mean() and (cs>.0003 or cv>.0006):sadj=s+.005
 r2=1-np.sum((y-(s*t+b))**2)/np.sum((y-y.mean())**2);r2s=1-np.sum((y[-15:]-(ss*t[-15:]+bs))**2)/np.sum((y[-15:]-y[-15:].mean())**2)
 a=np.expm1(250*sadj)*r2;d=a;short=np.expm1(250*ss)*r2s
 if r2s>=.8 and short>d:d=short
 changes=np.diff(y[-10:]);g=changes[changes>0].sum();l=-changes[changes<0].sum()
 if l==0:l=1e-6
 rsi=100-100/(1+g/l);f=d
 if rsi>95:f=0
 if rsi<10:f+=np.polyval(np.polyfit(KNOTS,TARGET,5),rsi)/8
 if f>=25:f=0
 return [a,d,f,f if f>.01 else np.nan]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='exact source thresholds, horizons, polynomialknots frozen; progressive4ablation, no outcome tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64];whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values(small[:stop],pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='priorcompletedprice_prefix_curve_RSI_poly',stop=stop,passed=True))
 rng=np.random.default_rng(10347);obs=0
 for _ in range(100):
  x=np.exp(np.cumsum(rng.normal(0,.015,25)))*20
  np.testing.assert_allclose([a[0] for a in panel(x[:,None])],literal(x),equal_nan=True,rtol=1e-8,atol=1e-8);obs+=1
 checks.append(dict(test='independent_literal_polyfit_convolve_branch_and_RSIninelogchanges',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 vals=values(f['close'],pos);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='reviewed ETFkernel stockextension, no portfolio or missingfinancial claims'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED103',flush=True)
if __name__=='__main__':main()
