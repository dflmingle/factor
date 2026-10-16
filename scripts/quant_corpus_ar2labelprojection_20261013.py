"""New causal AR2 projection matches label1/cycle10; no original-source claim."""
import json
import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2021年度精选策略/83.识别趋势震荡之神器 MESA最大熵谱分析（一）：滤波器建立.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source106-20261013'
COMMON='NEWresearch extension, NOT source factor: actualsource outputs AR2minute cycle only. Fit800daily firstdifferences with intercept, sourcefourweekminute/subsample6 absent. Priorclose asof t-1, recursively forecast12pricedifferences: skipsteps1..2, compare predictedclose steps2->12 matching close(t+1)->close(t+11). Horizon dictatedbyfixedlabel, not chosenfromreturns. No untouchedOOS; no perstock全样本 scaling.'
SPECS=[
 spec('mesa_ar2_cycle10_label1_projection','AR二阶十日标签对齐累计预测',SRC,
 '(modelClose_step12/modelClose_step2-1), estimatedpriorclose800diff',COMMON),
 spec('mesa_ar2_cycle10_stationary_qualified','AR二阶稳定解十日累计预测',SRC,
 'projection on abs(phi2)<1,phi1+phi2<1,phi2-phi1<1',COMMON+' StandardAR2stationaritygate fixed exante, no stabilitythresholdtuning; qualifiedfactor_valid benchmark.'),
 spec('mesa_ar2_cycle10_residualrisk_scaled','AR十日累计价格预测除滚动残差风险',SRC,
 'sum(modelDiffsteps3..12)/(sampleResidualSTD_last798*sqrt10)',COMMON+' NEWrisknormalization usesONLYtraining800window OLSresidualsampleSTD; simple sqrt10riskproxy ignores autoregressive forecast-error covariance, not claimed true modelIR.')]
SPECS[1]['gated']=True

def values(c,pos):
 out=[np.full((len(pos),c.shape[1]),np.nan) for _ in SPECS]
 for i,t in enumerate(pos):
  h=c[t-801:t].astype(float);ids=np.flatnonzero(np.isfinite(h).all(axis=0)&(h>0).all(axis=0))
  if not len(ids):continue
  d=np.diff(h[:,ids],axis=0);y=d[2:];x1=d[1:-1];x2=d[:-2];ym=y.mean(axis=0);m1=x1.mean(axis=0);m2=x2.mean(axis=0);yc=y-ym;a=x1-m1;b=x2-m2
  v1=(a*a).sum(axis=0);v2=(b*b).sum(axis=0);cv=(a*b).sum(axis=0);c1=(a*yc).sum(axis=0);c2=(b*yc).sum(axis=0);det=v1*v2-cv*cv;good=(v1>0)&(v2>0)&(det>1e-12*v1*v2)
  p1=np.full(len(ids),np.nan);p2=p1.copy();p1[good]=(c1*v2-c2*cv)[good]/det[good];p2[good]=(c2*v1-c1*cv)[good]/det[good];intercept=ym-p1*m1-p2*m2
  last=d[-1];prev=d[-2];close=h[-1,ids].copy();entry=np.full(len(ids),np.nan);profit=np.zeros(len(ids))
  for step in range(1,13):
   new=intercept+p1*last+p2*prev;close+=new;prev,last=last,new
   if step==2:entry=close.copy()
   if step>=3:profit+=new
  projected=np.where((entry>0)&(close>0),close/entry-1,np.nan);stable=(np.abs(p2)<1)&(p1+p2<1)&(p2-p1<1)
  residual=y-intercept-p1*x1-p2*x2;sd=np.std(residual,axis=0,ddof=1)
  scaled=np.where(sd>0,profit/(sd*np.sqrt(10)),np.nan)
  for target,x in zip(out,[projected,np.where(stable,projected,np.nan),scaled]):target[i,ids]=x
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='same800bar AR2, label-dictated3..12 forecaststeps andstandardstationarityconditions; nowindow/signoptimizer')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:64];whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values(small[:stop],pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-8,atol=1e-8);checks.append(dict(key=sp['key'],test='daily800projection_training_and_labelskip_prefix',stop=stop,passed=True))
 obs=0
 for i in [35,79]:
  for j in range(12):
   h=small[pos[i]-801:pos[i],j].astype(float)
   if not np.isfinite(h).all():continue
   fit=AutoReg(np.diff(h),lags=2,trend='c',old_names=False).fit();n=len(np.diff(h));pred=fit.predict(start=n,end=n+11);entry=h[-1]+pred[:2].sum();exit=h[-1]+pred.sum();a0,a1,a2=fit.params
   ref=[exit/entry-1,exit/entry-1 if abs(a2)<1 and a1+a2<1 and a2-a1<1 else np.nan,pred[2:].sum()/(fit.resid.std(ddof=1)*np.sqrt(10))]
   np.testing.assert_allclose([v[i,j] for v in whole],ref,equal_nan=True,atol=1e-7,rtol=1e-6);obs+=1
 checks.append(dict(test='independent_statsmodels_recursive12step_skipfirst2_true_label',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 vals=values(f['close'],pos);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='NEW AR2dailystockprojection, source minute filter NOTreproduced'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED106',flush=True)
if __name__=='__main__':main()
