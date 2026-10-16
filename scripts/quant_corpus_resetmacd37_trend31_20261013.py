"""Reset30 fast MACD and source25trend RSRS conditional kernel."""
import json,sys
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
A='quant/2024年度精选策略1/37.【择时模块实际效果】--论坛随便选了个策略加装.txt'
B='quant/2024年度精选策略1/31.动量因子加RSRS择时和ETF轮动每日调仓.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source141-20261013'
SPECS=[
 spec('risk37_reset30_MACD244_scaled','三十价重置快MACD幅度',A,'(TALibEMA2(C30)-TALibEMA4(C30)-TALibEMA4(DIF30))[-1]/Cprior',
 'proxy NEW stock rank of original GLOBAL CSI1000 risk gate; literal30priorprice reset eachcall, not fullhistoryEMA. Actual source uses DIFF-DEA histogram, not prior notesEMA2<EMA4 orCSI500. Normalizedbyprice NEWscale; fullA dailyclose replacement, source3union/holdings not reproduced.'),
 spec('risk37_reset30_MACD244_nonsell','三十价快MACD非清仓',A,'I((reset30 EMA2-EMA4-EMA4(DIF))>=0)',
 'proxy NEW stockbinary of globalCSI1000notnegative gate, tiesaudited; source np.where(NaNhist<0,1,0)wouldallow but missingprice retainedmissing locally, not fabricated buying. Complete sourcecap10 andcooldown commented, no originalportfolio claim.'),
 spec('etf31_trend25_rsrs_ma20_nonsell','二十五价趋势与RSRS三日均线非卖出',B,'unweightedlogtrend25prior WHERE NOT(rsrs18_z600_R2prior<-.7 AND priorMA20<lag4MA20)',
 'proxy eachstockOHLC replacesGLOBALHS300risk,rolling600seed; source RSRSonly z*R2 notbeta, KEEPbuys/adjusts, negative trendallowed (positivefiltercommented). Sameunweighted25atom as109 andRSRSguard111 but jointconditional previouslyuntested. FourETFtop1 andactual fills absent.')]
SPECS[2]['gated']=True

def values(f,pos):
 c=f['close'].astype(float);hist=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  for j in range(c.shape[1]):
   a=c[t-30:t,j]
   if np.isfinite(a).all():
    diff=talib.EMA(a,2)-talib.EMA(a,4);hist[i,j]=(diff-talib.EMA(diff,4))[-1]
 h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));cov=h.rolling(18).cov(l);vl=l.rolling(18).var();vh=h.rolling(18).var();beta=cov/vl
 rs=(((beta-beta.rolling(600).mean())/beta.rolling(600).std(ddof=0))*cov**2/(vl*vh)).shift(1).to_numpy()[pos]
 ma=pd.DataFrame(c).rolling(20).mean().to_numpy();gap=ma[pos-1]-ma[pos-4]
 gate=np.isfinite(rs)&np.isfinite(gap)&~((rs<-.7)&(gap<0))
 return [hist/c[pos-1],np.where(np.isfinite(hist),(hist>=0).astype(float),np.nan),np.where(gate,trend_at(c,pos-1,25),np.nan)]

def refema(a,n):
 out=np.full(len(a),np.nan);first=np.flatnonzero(np.isfinite(a))
 if not len(first):return out
 start=first[0]
 if start+n>len(a):return out
 out[start+n-1]=a[start:start+n].mean()
 for t in range(start+n,len(a)):out[t]=out[t-1]+2/(n+1)*(a[t]-out[t-1])
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literalreset30EMA2/4/4 andjoint25RSRS20gap3 beforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawOHLCprefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   a=sf['close'][t-30:t,j].astype(float)
   if np.isfinite(a).all():
    dif=refema(a,2)-refema(a,4);ref=(dif-refema(dif,4))[-1]/a[-1]
    np.testing.assert_allclose(full[0][i,j],ref,atol=1e-10)
 checks.append(dict(test='independent_SMAseed_recursive_EMA2_4_4_onreset30',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='GLOBAL market gating individualstockadaptation only'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED141',flush=True)
if __name__=='__main__':main()
