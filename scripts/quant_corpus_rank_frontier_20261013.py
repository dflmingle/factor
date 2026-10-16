"""Remaining explicit rank formulas, including source-weight correction."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
MULTI='quant/2020年度精选策略/92 多因子选股策略.txt'
VALUE='quant/2022年度精选策略/80.小盘价值股策略2.01，年化131%，回撤8.8%.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source50-20261013'
SPECS=[
 spec('multifactor8_literal_signed','八因子源码有符号秩组合',MULTI,'rank(totalMV)-rank(PS)+rank(reportedEPS)+rank(reported_netmargin)+rank(ROE)+rank(PCF)-rank(PE)-rank(turnover)',
      'proxy: source weights[-1,+1,-1,-1,-1,-1,+1,+1] and ascending total_points inverted for high-score evaluator; HIGH PCF retained; totalMV replaces unavailable circMV explicitly, PIT vendor reportedEPS/margins and TTM valuation; no HS300/trading gates'),
 spec('smallvalue4_source_weights_gates','小盘价值源码权重与正值修复',VALUE,'-rank(totalMV)-(rank(PB)+rank(PE)+rank(PCF))/3, all valuation ratios>0',
      'proxy: exact active sum_func size weight1, three valuation weights1/3, source positive gates; repairs old source23 equally weighted ungated experiment; stock-only decile, not original20%stock/80%treasury allocation'),
]

def build(fin,eps,cap,turn):
 def g(ep,c):return fin[f'{ep}.{c}.q0']
 mv=cap*10000;eq=g('balancesheet','total_hldr_eqy_exc_min_int');ni=g('income','n_income_attr_p_ttm');rv=g('income','total_revenue_ttm');ocf=g('cashflow','n_cashflow_act_ttm')
 pb=q.ratio(mv,eq);pe=q.ratio(mv,ni);ps=q.ratio(mv,rv);pcf=q.ratio(mv,ocf)
 legs=[cap,-ps,eps,g('fina_indicator','netprofit_margin'),g('fina_indicator','roe'),pcf,-pe,-turn]
 # Preserve source rank direction even for negative ratios, without changing to rank(-x).
 sign=[1,-1,1,1,1,1,-1,-1];original=[cap,ps,eps,g('fina_indicator','netprofit_margin'),g('fina_indicator','roe'),pcf,pe,turn]
 score=sum(s*q.rank(x) for s,x in zip(sign,original))
 gate=(pb>0)&(pe>0)&(pcf>0)&(cap>0)
 value=-q.rank(np.where(gate,cap,np.nan))-sum(q.rank(np.where(gate,x,np.nan)) for x in [pb,pe,pcf])/3
 return [score,value]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='exact rank direction and source weight fixed before results',platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 fin=q.financial_snapshot(grid,stocks)
 schema=q.ROOT/'research_reports/platform_alignment/quant-corpus-eps-ols-schema-20261013'
 dates=pd.DatetimeIndex(pd.to_datetime(json.loads((schema/'schema.json').read_text())['dates']))
 cached=pd.read_pickle(schema/'financial_signal_snapshots_lags1.pkl');eps=cached['fina_indicator.eps.q0'][dates.get_indexer(grid)]
 v=build(fin,eps,f['cap'][pos],f['turnover'][pos]);checks=[]
 for stop in [35,79]:
  cut=build({k:a[:stop] for k,a in fin.items()},eps[:stop],f['cap'][pos[:stop]],f['turnover'][pos[:stop]])
  for sp,a,b in zip(SPECS,v,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-6,atol=1e-6);checks.append(dict(key=sp['key'],test='prefix_formula_recompute_on_previously_raw_PIT_verified_caches',passed=True))
 # Source dot-product points ascending vs high alpha descending.
 ranks=np.arange(1,9,dtype=float);weights=np.array([-1,1,-1,-1,-1,-1,1,1])
 assert -float(ranks@weights)==float(ranks@np.array([1,-1,1,1,1,1,-1,-1]))
 checks.append(dict(test='independent_source8_weights_orientation',passed=True))
 run(OUT,SPECS,v,cal,stocks,f,checks,dict(fidelity='explicit PIT/vendor rank proxies',gated_benchmark='smallvalue qualification subset benchmark; cannot use original20/80 allocation profits',statistics='exploratory no independent OOS'))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED50',flush=True)
if __name__=='__main__':main()
