"""Reported five-period ROE acceleration, separate from old quarterly proxy."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/28.【回顾2】小市值成长股策略更新FROEC-PB-CAP-HL.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source152-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-reportedROE28-schema-20261013'
FIELDS={'fina_indicator':['roe','eps'],'balancesheet':['total_hldr_eqy_exc_min_int']}
COMMON='proxy actual indicator.roe mappedreportedYTDroe, NOT oldsource6q_roe. Fivecontiguousknownreportperiods chronological oldest..latest; JQvendorbasis notbyteverified. positiveEPS andpositivePB lower50% amongfinitevalues, priorPIT, PB=totalMV/parentEquity. Sourceg.industry_controlTruePITindustryexclusions absentexplicitly, circMVreplacedtotalMV, source10holdings/250day/ST/limitcooldown notwhole reproduced. '
SPECS=[
 spec('FROEC28_reported_ROE_delta5','五报告ROE改善原子',A,'4*reportedROE0-sum(reportedROE1..4)',COMMON+'Ungatedsourceorderingatom, same4scaling isrankconstant.'),
 spec('FROEC28_positiveEPS_lowPB_half','正EPS低PB半池报告ROE改善',A,'4*reportedROE0-sum(ROE1..4) within PB>0,EPS>0 lowestfloor(.5*N)PB',COMMON+'Originalconstraint beforetop10%/industry/circMV, factor_validqualifiedbenchmark.'),
 spec('FROEC28_finalmembership_priority','ROE改善资格同池市值优先',A,'2*I(positiveEPS lowPBhalf and highestfloor(.1*NfiveROEvalid)ROEdelta5)+CSrank(-totalMV)',COMMON+'NEWfullAcommon-support qualificationadapter; sourceindustryexceptions absent. Missingfinance outsidegate, pureSIZEsame-support comparison recorded, cannot infer membershipfromresidualdegeneracy.')]
SPECS[1]['gated']=True

def values(fin,cap):
 roes=np.stack([fin[f'fina_indicator.roe.q{k}'].astype(float) for k in range(5)],axis=-1);delta=4*roes[:,:,0]-roes[:,:,1:].sum(axis=-1)
 e=fin['fina_indicator.eps.q0'];eq=fin['balancesheet.total_hldr_eqy_exc_min_int.q0'];pb=cap*10000/eq
 partial=np.full(delta.shape,np.nan);priority=np.full(delta.shape,np.nan)
 for i in range(len(delta)):
  allids=np.flatnonzero(np.isfinite(cap[i])&(cap[i]>0));ids=allids[np.isfinite(pb[i,allids])&(pb[i,allids]>0)&(e[i,allids]>0)];ids=ids[np.argsort(pb[i,ids],kind='stable')][:int(.5*len(ids))]
  ids=ids[np.isfinite(delta[i,ids])];partial[i,ids]=delta[i,ids];top=ids[np.argsort(-delta[i,ids],kind='stable')][:int(.1*len(ids))]
  priority[i,allids]=rankdata(-cap[i,allids])/len(allids);priority[i,top]+=2
 return [delta,partial,priority]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='actualreportedROE notqROE, literalhalf andtop10 andcommon-support adapter beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),stocks=list(stocks),lags=5,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(dates,stocks,lags=5);tables=q.pit_tables();ids=np.arange(512);small={k:v[:,ids] for k,v in fin.items()};cap=f['cap'][pos][:,ids];whole=values(small,cap);checks=[]
  for nn in [35,79]:
   q.pit_tables=lambda:{ep:t[(t.ann_date<=dates[nn-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
   with tempfile.TemporaryDirectory(prefix='ROE28-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cut=values(q.financial_snapshot(dates[:nn],stocks[ids],lags=5),cap[:nn])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:nn],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawreportedROE_EPS_equityPIT_cutoff',passed=True))
  for i in [35,79]:
   for j in range(32):
    a=[float(fin[f'fina_indicator.roe.q{k}'][i,j]) for k in range(4,-1,-1)];np.testing.assert_allclose(whole[0][i,j],4*a[-1]-sum(a[:-1]),equal_nan=True,atol=1e-8)
  checks.append(dict(test='independent_oldesttolatest_source_dataframe_ROE_linearcombination',passed=True))
  q.OUT=oldout;q.pit_tables=loader
  q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
  run(OUT,SPECS,values(fin,f['cap'][pos]),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f)
  baseline=pd.read_csv(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/results.csv');res=pd.read_csv(OUT/'results.csv');rows=[]
  for win in ['five_year','recent']:
   a=res[res.key.eq(SPECS[-1]['key'])&res.window.eq(win)&res.form.eq('raw')].iloc[0];b=baseline[baseline.key.eq('membership144_size_control')&baseline.window.eq(win)&baseline.form.eq('raw')].iloc[0]
   rows.append(dict(window=win,delta_net_excess_pct=a.net_excess_pct-b.net_excess_pct,delta_dd_pct=a.held_daily_max_drawdown_pct-b.held_daily_max_drawdown_pct,delta_turn_pct=a.turnover_pct-b.turnover_pct))
  pd.DataFrame(rows).to_csv(OUT/'matched_size_control_deltas.csv',index=False);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED152',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
