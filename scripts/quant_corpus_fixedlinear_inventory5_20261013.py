"""Fixed price/profit/inventory coefficients; explicit canonical qfq adapter."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/5.尝试用机器学习批量生产小盘策略.txt'
B='quant/2024年度精选策略1/23.wywy1995大神机器学习策略年化提升35pt.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source148-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-fixedlinear-inventory5-schema-20261013'
FIELDS={'income':['total_profit','total_cogs'],'fina_indicator':['inv_turn','eps']}
COMMON='proxy canonicalqfqC explicitly replaces forbiddenraw price_no_fq; source literal fixedcoefficients, no normalization/retraining; profitcost=100*totalprofitTTM/positive totalcogsTTM, inventoryturn=reportedTushareinv_turn unverifiedvendorproxy. Prior-dayPIT, fullA. Sourcetop10%/positiveEPS/circMV/250or375listing/ST/weeklyhold/limits/execution not whole reproduced. No modeltraining/OOS provenance disclosed by source. '
SPECS=[
 spec('linear5_qfq_profit_inventory_fixed','固定系数价格利润存货代理',A,'-6.123355346008858e-5*qfqC-.002579342458393642*profitcostTTM-2.194257357346814e-6*reportedInvTurn',COMMON+'Explicit fixedweights otherfamily than source84Price1Y/VOL120.'),
 spec('linear5_profit_inventory_sizefree_extension','固定系数利润存货去价格扩展',A,'-.002579342458393642*profitcostTTM-2.194257357346814e-6*reportedInvTurn',COMMON+'NEWpricelegremoved financialextension, not originalformula.'),
 spec('linear5_positiveEPS_topscore_priority','线性资格同池市值优先诊断',B,'2*I(fixedscore in topfloor(.1*Nfinite) AND reportedEPS>0)+CSrank(-totalMV)',COMMON+'NEWfullAsupport membershippriority; missingfinancial outsidegate. Source23max(top10%,10) equals10% for canonicalvalidN>=100. totalMVreplacescircMV. PureSIZEcomparison source144separate, no factor_valid gatedsubsetmisclaim.')]
SPECS[0]['source_paths'].append(B)

def values(fin,f,pos):
 profit=fin['income.total_profit_ttm.q0'].astype(float);cost=fin['income.total_cogs_ttm.q0'].astype(float)
 pc=100*profit/np.where(cost>0,cost,np.nan);inv=fin['fina_indicator.inv_turn.q0'].astype(float);eps=fin['fina_indicator.eps.q0'].astype(float)
 part=-.002579342458393642*pc-2.194257357346814e-6*inv;score=part-6.123355346008858e-5*f['close'][pos];cap=f['cap'][pos];priority=np.full(score.shape,np.nan)
 for i in range(len(score)):
  allids=np.flatnonzero(np.isfinite(cap[i])&(cap[i]>0));ids=allids[np.isfinite(score[i,allids])];ids=ids[np.argsort(-score[i,ids],kind='stable')][:max(int(.1*len(ids)),10)];ids=ids[eps[i,ids]>0]
  priority[i,allids]=rankdata(-cap[i,allids])/len(allids);priority[i,ids]+=2
 return [score,part,priority]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixedcoefficient, disclosed qfqadapter and removal/comparison beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),stocks=list(stocks),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();ids=np.arange(512);sf={k:v[:,ids] for k,v in f.items()};whole=values({k:v[:,ids] for k,v in fin.items()},sf,pos);checks=[]
  for n in [35,79]:
   q.pit_tables=lambda:{ep:t[(t.ann_date<=dates[n-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
   with tempfile.TemporaryDirectory(prefix='inventorylinear-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(dates[:n],stocks[ids],lags=1);cut=values(cf,{k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawPIT_and_market_prefix_replay',passed=True))
  q.OUT=oldout;q.pit_tables=loader
  for src in [A,B]:
   text=read_text(q.ROOT/src)
   for w in ['-6.123355346008858e-05','-0.002579342458393642','-2.194257357346814e-06']:assert w in text
  checks.append(dict(test='literal_all3coefficients_present_both_reviewed_sources',passed=True))
  q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
  run(OUT,SPECS,values(fin,f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON,diagnostic_unverified_fields=['inv_turn','eps','profitcostTTM']),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f)
  baseline=pd.read_csv(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/results.csv');res=pd.read_csv(OUT/'results.csv');deltas=[]
  for win in ['five_year','recent']:
   a=res[res.key.eq(SPECS[-1]['key'])&res.window.eq(win)&res.form.eq('raw')].iloc[0];b=baseline[baseline.key.eq('membership144_size_control')&baseline.window.eq(win)&baseline.form.eq('raw')].iloc[0]
   deltas.append(dict(window=win,delta_net_excess_pct=a.net_excess_pct-b.net_excess_pct,delta_dd_pct=a.held_daily_max_drawdown_pct-b.held_daily_max_drawdown_pct,delta_turn_pct=a.turnover_pct-b.turnover_pct))
  pd.DataFrame(deltas).to_csv(OUT/'matched_size_control_deltas.csv',index=False)
  q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED148',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
