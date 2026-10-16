"""Exact ETF momentum29 and off-by-one13-price kernels adapted to full A."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
TREND='quant/2023年度精选策略/4.8年10倍，回撤小，有滑点！ETF动量简单轮动策略！.txt'
MOM='quant/2024年度精选策略2/16.ETF轮动策略升级-多类别-低回撤.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source100-20261013'
SPECS=[
 spec('etf4_logtrend29_r2_priorclose','ETF四号二十九价点趋势拟合度',TREND,'lag1(expm1(250*OLS29(logC~time).slope)*R2)',
 'proxy: exact source29pricepoints and250annualization, previouscompletedbar delay1; fullAstock extension of3ETF ranking only. Actual indexRSRS18/600*.R2,MA20slope3,holdings and ETFfills not reconstructed; windowvariant of known trend family, not newcluster'),
 spec('etf16_return12_offbyone','ETF十六号名义十三实际十二日动量',MOM,'100*(C/lag12C-1)',
 'proxy: source count14 but [-13] to[-1] is12day gap; afterclose21:00 signal retained, canonical nextclose label1. Crossasset classes, fixedoneperclass and unusedcash not reproduced'),
 spec('etf16_return12_above_ma10','十二日动量正且十日均线正交集',MOM,'100*(C/lag12C-1) where ret12>0 and C>MA10(C)',
 'proxy: exact two positive eligibility filters and source momentum ranking, fullA replaces ETF universe; restricted factor_valid benchmark and original categoryallocation absent')]
SPECS[-1]['gated']=True

def values(f,pos):
 c=f['close'].astype(float);ret=100*(c/q.delay(c,12)-1);ma=pd.DataFrame(c).rolling(10).mean().to_numpy()
 # Source uses attribute_history: completed bars through t-1.
 trend=trend_at(c,pos-1,29)
 return [trend,ret[pos],np.where((ret[pos]>0)&(c[pos]>ma[pos]),ret[pos],np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixed29/250,12daygap,MA10 windows; no tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6);checks.append(dict(key=sp['key'],test='daily_source_bar_timing_prefix',stop=stop,passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   x=small['close'][t-29:t,j].astype(float)
   if np.isfinite(x).all() and x.std()>0:
    y=np.log(x);s,b=np.polyfit(np.arange(29),y,1);r2=1-((y-(s*np.arange(29)+b))**2).sum()/((len(y)-1)*np.var(y,ddof=1))
    np.testing.assert_allclose(whole[0][i,j],np.expm1(250*s)*r2,atol=1e-7,rtol=1e-6)
   x=small['close'][t-13:t+1,j].astype(float)
   if np.isfinite(x).all():np.testing.assert_allclose(whole[1][i,j],100*(x[-1]/x[-13]-1),atol=1e-7)
 checks.append(dict(test='independent_source_polyfit_and_14price_minus13_slice',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [TREND,MOM]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='ETFsource technicalkernels stockextension only'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED100',flush=True)
if __name__=='__main__':main()
