"""Correct source30x5day reversal; active medical price dispersion atom."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2023年度精选策略/66.基于动量和反转效应的沪深300成分股策略.txt'
MEDICAL='quant/2022年度精选策略/95.医疗行业多因子模型及单行业多因子测试代码模板.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source69-20261013'
SPECS=[spec('reversal135_skip5_source','跳五日跨一三五日源码反转',SOURCE,
 '-(lag5(close)/lag140(close)-1)',
 'proxy: active30bars of5d close uses index[-2]/index[1], 27five-day gaps=135tradingdays, assuming latestbar ends signalday. Exact vendor5dbar alignment unverified. FullA replacesHS300,10day refresh replaces source30 six-day weeks reset(~180day); inactive14bar momentum not counted'),
 spec('medical_price_std20_low','医疗模板二十日价格离散度低',MEDICAL,'-sampleSTD20(qfqClose)',
 'proxy: active g.factor std_1m is price STD on last20closes, not return volatility. FullA replacesmedical; economic low direction frozen, source12month rollingIC weighting requiresmissing IC.csv so NOT reproduced')]

def values(c):return [-(q.ratio(q.delay(c,5),q.delay(c,140))-1),-q.rolling(c,20,'std')]
def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source actual slices and low priceSTD fixed before evaluation')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small=f['close'][:,:256].astype(float);whole=values(small);checks=[]
 for stop in [1200,len(cal)-31]:
  for a,b in zip(whole,values(small[:stop])):np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6)
  checks.append(dict(test='price_prefix_recompute',stop=stop,passed=True))
 for t in pos[::31]:
  bars=small[t-145:t+1:5]
  assert len(bars)==30
  ref=-(bars[-2]/bars[1]-1)
  np.testing.assert_allclose(whole[0][t],ref,equal_nan=True,atol=1e-6)
  np.testing.assert_allclose(whole[1][t],-np.std(small[t-19:t+1],axis=0,ddof=1),equal_nan=True,atol=1e-6)
 checks.append(dict(test='independent_literal30bars5d_and_priceSTD20',passed=True))
 vals=[x[pos] for x in values(f['close'].astype(float))]
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source price atoms; vendor5dbar alignment proxy',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED69',flush=True)
if __name__=='__main__':main()
