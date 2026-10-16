"""Source19-day momentum band and ETF recovery gates, daily fullA proxies."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/58Debug-输出信息-多标的版ETF策略(ETF复现之三）.txt'
B='quant/聚宽2025年精选/22带上止损的核心资产轮动才更安心，低回撤，高收益率.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source109-20261013'
SPECS=[
 spec('etf58_exact19_band5_20_ma5_20','名义二十实际十九日动量双边带',A,'lag1(RET19) where .05<lag1RET19<.20 AND lag1MA5>lag1MA20',
 'proxy: source20 completedcloses firsttolast is19intervals, MA5 last5 ofsame20; fixed open signal. FullAstockextension, source duplicate512100 ETF and top2buy/top4retention/orderstate absent; qualifiedfactor_valid benchmark'),
 spec('etf22_unweighted_logtrend25_priorclose','核心轮动二十五价点无权拟合',B,'expm1(250*OLS25(logC).slope)*R2, endingt-1',
 'proxy: exactsource unweighted25point regression, distinct from weighted25/endpoint29/dualtrend kernels; knownfamilyvariant only. FullAextension of4ETFtop1, no sourceETFfills'),
 spec('etf22_reentry_ma4_qualified','四价点均线恢复资格',B,'trend25 where C_t-1>=MA4(C)_t-1',
 'proxy NEW qualifiedstockextension: source sel_worth condition only gates reentry into lastETF when alreadyflat; applies toscoreforresearch, originaletf_pre andholdlist state absent; label1; qualifiedbenchmark'),
 spec('etf22_no_loss4pct_qualified','前一日未跌四个点资格',B,'trend25 where C_t-1/C_t-2>.96',
 'proxy NEW qualifiedstockextension: source hold_worth only exits existingposition, not original entryfilter; assignment to everystockexplicit. Actualstrictgreater .96, source100barpeak ratiosprinted but not used; qualifiedbenchmark')]
for i in [0,2,3]:SPECS[i]['gated']=True

def values(f,pos):
 c=f['close'].astype(float);r=c[pos-1]/c[pos-20]-1;ma={n:pd.DataFrame(c).rolling(n).mean().to_numpy()[pos-1] for n in [4,5,20]};trend=trend_at(c,pos-1,25)
 return [np.where((r>.05)&(r<.2)&(ma[5]>ma[20]),r,np.nan),trend,
  np.where(c[pos-1]>=ma[4],trend,np.nan),np.where(c[pos-1]/c[pos-2]>.96,trend,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixed bands/horizons and2 partialstate extensions before returns')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='completedbar_daily_prefix',stop=stop,passed=True))
 for i in [35,79]:
  for j in range(64):
   t=pos[i];x=small['close'][t-20:t,j].astype(float);r=x[-1]/x[0]-1;ref=r if x[-5:].mean()>x.mean() and .05<r<.2 else np.nan
   np.testing.assert_allclose(whole[0][i,j],ref,equal_nan=True,atol=1e-8)
   x=small['close'][t-25:t,j].astype(float)
   if np.isfinite(x).all() and x.std()>0:
    y=np.log(x);s,b=np.polyfit(np.arange(25),y,1);r2=1-((y-s*np.arange(25)-b)**2).sum()/((len(y)-1)*y.var(ddof=1));ref=np.expm1(250*s)*r2
    np.testing.assert_allclose(whole[1][i,j],ref,rtol=1e-6,atol=1e-7)
 checks.append(dict(test='independent20prices_19intervals_band_and_np_polyfit25',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='stockextension ofETF kernels; recoverygates partialproxies'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED109',flush=True)
if __name__=='__main__':main()
