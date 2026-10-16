"""Literal mixed endpoint slope / OLS intercept from source25; daily proxy."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec, audit, simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text

SRC='quant/2024年度精选策略2/25.年初至今4倍，极致的Day Trading，56.8%胜率.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source154-20261013'
COMMON=('proxy: source100 120-minute closes replaced100 completed daily qfq closes; fullA replaces '
        'historical concept membership and 30..1000 billion-yuan cap gate. Source uses endpoint slope '
        '(logC[-1-D]-logC[-29-D])/29 but OLS intercept on global x=0..99, then absolute pseudoR2. '
        'This is NOT source79 fixed-first-price intercept nor a conventional OLS trend. Require100 '
        'complete daily observations; source short-history branch/dropped-bar compression omitted. '
        '09:31 fills, top5 then1, named-index gates, limits and 15% holding stop not reconstructed. ')
SPECS=[
 spec('day25_mixedendpoint_OLSintercept100_daily','混合端点斜率OLS截距日线代理',SRC,
      'expm1(250*endpointSlope29)*abs(1-SSE(endpointSlope29*x+OLSintercept29)/SST29), x in last100 globalindices',COMMON),
 spec('day25_negativechanges_lt2_daily','五评分负变化少于两次日线代理',SRC,
      'I(sum(score_D<score_Dplus1 for D=0..3)<2)',COMMON+' Exact four adjacent differences, NOT necessarily consecutive declining sessions. RSRS14/600 and MA7/10 are computed but inactive in BUY/SELL.'),
 spec('day25_mixedendpoint_joint_lt2_daily','混合端点评分联合变化门日线代理',SRC,
      'mixedEndpointScore_D0 WHERE count4negativeChanges<2',COMMON+' Source-fixed active entry joint; perstock rather original top1 trading-path adapter, qualified factor_valid benchmark.')]
SPECS[-1]['gated']=True

@njit(cache=True)
def allscores(c,pos):
 out=np.full((len(pos),c.shape[1],5),np.nan)
 denx=2030.0 # sum((0..28-14)^2)
 for i,t in enumerate(pos):
  for j in range(c.shape[1]):
   hist=c[t-100:t,j]
   if len(hist)!=100 or not np.all(np.isfinite(hist)) or np.any(hist<=0):continue
   y=np.log(hist)
   for d in range(5):
    start=71-d;end=100-d;a=y[start:end]
    mean=np.mean(a);ols=0.0
    for k in range(29):ols+=(k-14)*a[k]
    ols/=denx;intercept=mean-ols*(start+14)
    slope=(a[-1]-a[0])/29;sse=0.0;sst=0.0
    for k in range(29):
     sse+=(a[k]-(slope*(start+k)+intercept))**2
     sst+=(a[k]-mean)**2
    if sst>1e-15:out[i,j,d]=np.expm1(250*slope)*abs(1-sse/sst)
 return out

def values(f,pos):
 scores=allscores(f['close'].astype(float),pos);valid=np.isfinite(scores).all(axis=2)
 count=(scores[:,:,:4]<scores[:,:,1:]).sum(axis=2);allow=count<2
 return [scores[:,:,0],np.where(valid,allow.astype(float),np.nan),np.where(valid&allow,scores[:,:,0],np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,
  selection='source-fixed globalindex100,endpointgap28div29,OLSintercept,4changes,strictcount<2')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-7)
   checks.append(dict(key=sp['key'],test='completedbar_rawprice_prefix',passed=True))
 whole=allscores(sf['close'].astype(float),pos);observations=0
 for i in [35,79]:
  for j in range(64):
   y=np.log(sf['close'][pos[i]-100:pos[i],j].astype(float));x=np.arange(100)
   if not np.isfinite(y).all():continue
   for d in range(5):
    a=y[71-d:100-d];xx=x[71-d:100-d];s=(a[-1]-a[0])/29
    _,b=np.polyfit(xx,a,1);sst=28*np.var(a,ddof=1)
    ref=np.expm1(250*s)*abs(1-((a-(s*xx+b))**2).sum()/sst) if sst>1e-15 else np.nan
    np.testing.assert_allclose(whole[i,j,d],ref,equal_nan=True,atol=1e-6,rtol=1e-7);observations+=1
 assert observations>0
 toy=np.array([[5,4,3,2,1],[1,5,2,6,3],[5,5,4,4,3]],float)
 np.testing.assert_array_equal((toy[:,:4]<toy[:,1:]).sum(axis=1)<2,[True,False,True])
 checks.append(dict(test='independent_literal_globalx_numpy_polyfit_intercept_and_diff_axis_minus1',observations=observations,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED154',flush=True)
if __name__=='__main__':main()
