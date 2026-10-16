"""Source fixed RSRS/linear momentum variants; no execution of corpus code."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2023年度精选策略/7.ETF动量轮动RSRS择时-魔改3小优化.txt'
B='quant/2023年度精选策略/15.动量ETF轮动RSRS择时-升级.txt'
C='quant/2023年度精选策略/29.价值成长轮动策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source111-20261013'
BASE='proxy: fullAstock extension of index/ETF kernel, completed priorclose, label1; no ETF holdings/execution. RSRS rolling600 seed proxy retains source18 slope/R2/populationSTD, initial skipped slope not recovered. Known family variant, not new cluster.'
SPECS=[
 spec('etf7_linear20_firstprice_slope','二十价点首价归一线性斜率',A,'OLS20(C/C_first).slope endingt-1',BASE+' Source uses raw normalized price, NOT logtrend/R2; source rank returns [code,score] pair passed to orders, execution defect disclosed.'),
 spec('etf7_rsrs_nonsell_no_ma','RSRS单门非卖出分支',A,'I(rsrs18_z600_r2>=-.7)',BASE+' MA30/gap5 fetched but unused; BUY and KEEP both adjust, no persistent hysteresis.'),
 spec('etf15_rsrs_nonsell_ma20gap3','三日均线RSRS非卖出分支',B,'I(NOT(rsrs18_z600_r2<-.7 AND lag1MA20<lag4MA20))',BASE+' Exact ANDsell; KEEP adjusts; separate from gap5 source108.'),
 spec('valuegrowth29_logtrend30_priorclose','价值成长轮动三十价点趋势',C,'expm1(250*OLS30(logC).slope)*R2 endingt-1',BASE+' Value/growth membership, vendor margin_stability and PIT floatcap missing; only displayed trend kernel.')]

def values(f,pos):
 c=f['close'].astype(float);x=np.arange(20)-9.5;out=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  a=c[t-20:t];out[i]=(x[:,None]*(a/a[0])).sum(axis=0)/(x*x).sum()
 h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));cov=h.rolling(18).cov(l);vl=l.rolling(18).var();vh=h.rolling(18).var();beta=cov/vl
 rs=(((beta-beta.rolling(600).mean())/beta.rolling(600).std(ddof=0))*cov**2/(vl*vh)).shift(1).to_numpy()
 ma=pd.DataFrame(c).rolling(20).mean().to_numpy();gap=q.delay(ma)-q.delay(ma,4)
 b=np.where(np.isfinite(rs),(rs>=-.7).astype(float),np.nan)
 d=np.where(np.isfinite(rs)&np.isfinite(gap),(~((rs<-.7)&(gap<0))).astype(float),np.nan)
 return [out,b[pos],d[pos],trend_at(c,pos-1,30)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source fixed four formulas, no outcome tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:32] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawOHLC_priorbar_prefix',passed=True))
 count=0
 for i in [35,79]:
  for j in range(32):
   t=pos[i];a=small['close'][t-20:t,j].astype(float)
   if np.isfinite(a).all():
    np.testing.assert_allclose(whole[0][i,j],np.polyfit(np.arange(20),a/a[0],1)[0],rtol=1e-7,atol=1e-8);count+=1
 checks.append(dict(test='independent_literal_normalized20_polyfit',observations=count,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED111',flush=True)
if __name__=='__main__':main()
