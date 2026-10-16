"""Actual quakecat low-log weights; canonical daily proxy of intraday inputs."""
import json,ast
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2021年度精选策略/13.7年40倍，模拟超过两年，年化高回撤低.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source92-20261013'
SPECS=[
 spec('quakecat_lowlog_price8_vol4_reversal10','低价量和六十日反转源码权重',SRC,
 '-8log(qfqC)-4log(SUM5V)-10log(C/lag60C)',
 'proxy: source weights[5,5,8,4,10]; explicitly remove two size terms to examine remaining information; daily close replaces currentminute, SUM5V replaces rolling1200minuteV, qfq pricelevel replaces source realprice. Daily signal enters label1, not source14:50trade. No original floatcap100/PB/ST/listing/index/bwlist/holdbuffer'),
 spec('quakecat_lowlog_full_size_proxy','五腿实际权重全A代理',SRC,
 '-10log(total_mv)-8log(qfqC)-4log(SUM5V)-10log(C/lag60C)',
 'proxy: full source5weights; both totalMV and missingfloatMV mapped total_mv explicitly, not exact original5field formula; allA replaces source100smallfloatcap qualification, intraday inputs as separate daily proxies. No index or execution reconstruction; size/style audit required')]

def values(f):
 c=f['close'].astype(float);v=q.rolling(f['volume'],5,'sum');r=q.ratio(c,q.delay(c,60))
 with np.errstate(divide='ignore',invalid='ignore'):
  non=-8*np.log(c)-4*np.log(v)-10*np.log(r);full=non-10*np.log(f['cap'])
 return [non,full]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixed exactweights before outcomes; two size-control forms not parameter search')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:256] for k,v in f.items()};whole=values(sf);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in sf.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='raw_daily_prefix_recompute',stop=stop,passed=True))
 tree=ast.parse(read_text(q.ROOT/SRC));weights=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='weights' for t in n.targets));assert ast.literal_eval(weights.value)==[5,5,8,4,10]
 # Constants log(min_field) cannot affect the stock ordering.
 a=np.array([[2.,4.,3.,8.,.7],[5.,3.,7.,2.,1.4],[4.,6.,1.,4.,.9]])
 w=np.array([5,5,8,4,10]);literal=(np.log(a.min(axis=0)/a)*w).sum(axis=1);ours=-(np.log(a)*w).sum(axis=1)
 np.testing.assert_array_equal(np.argsort(literal),np.argsort(ours));checks.append(dict(test='independent_literal_log_min_ratios_order_and_AST_weights',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,[x[pos] for x in values(f)],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='intraday dailyproxy and unavailablefloatcap explicitly disclosed',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED92',flush=True)
if __name__=='__main__':main()
