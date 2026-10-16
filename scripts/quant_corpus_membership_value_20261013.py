"""Common full-A support tests of promising membership filters against size control."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
A='quant/2024年度精选策略1/18.微盘股研究.txt'
B='quant/2024年度精选策略1/37.【择时模块实际效果】--论坛随便选了个策略加装.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013'
SPECS=[
 spec('membership144_size_control','同支持集纯市值对照',A,'rank(-totalMV)',
 'known SIZE control; fullA support and benchmark identical to two NEWmembership adapters; not newalpha.'),
 spec('membership144_positivePB_priority','正PB资格优先小盘同基准',A,'2*I(PB>0)+rank(-totalMV); missingPB outsidegate but size fallbackretained',
 'proxy NEW lexicographic fullA adapter: positivePBeligible beforeothers, withinbothgroups smalltotalMV. Topdecile alwaysfullAwidth; if insufficienteligible fillsoutside bysize. Not source100/120portfolio; canonicalfactor_validbenchmark shared withcontrol. Uses original136priorPITselector; no officialpool/Comb claim.'),
 spec('membership144_lowretained_positiveEPS_priority','低留存正EPS资格同基准',B,'2*I(lowest10%validretainedPS AND EPS>0)+rank(-totalMV)',
 'proxy NEW fullA lexicographicadapter to inspect membershipincrement NOT inferfrom pure-size residual degeneracy. Uses frozen140selector, vendorretainedps/eps unverifiedproxy; missingfinancial outsidegate, no alpha-imputation, fallbacksize. Source250/125day/circMV/otherunionlegs/risknot reproduced. No independentOOS orplatformpool claim.')]

def make_scores(cap,pb_membership,ret_membership):
 base=q.rank(np.where(cap>0,-cap,np.nan));return [base,2*pb_membership+base,2*ret_membership+base]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='2preselectedsourcefilters plusSIZEcontrol,fullA lexicographic rank, no thresholdtuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 selectors=[];provenance=[]
 for num,key in [(136,'micro18_positivePB_literal'),(140,'union37_bottom10_retainedps_small_partial')]:
  root=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{num}-20261013';assert(root/'audit_complete.json').exists()
  saved=pd.read_pickle(root/'signal_panels.pkl');assert saved['dates'].equals(grid) and saved['stocks'].equals(stocks)
  selectors.append(np.isfinite(saved['panels'][key].to_numpy()));provenance.append(dict(source=str(root.relative_to(q.ROOT)),key=key,rawPIT_replay='verification.json'))
 vals=make_scores(f['cap'][pos],*selectors);checks=[]
 for n in [35,79]:
  cut=make_scores(f['cap'][pos[:n]],*[v[:n] for v in selectors])
  for sp,a,b in zip(SPECS,vals,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True);checks.append(dict(key=sp['key'],test='prefix_CSonly_mapping_upstreamrawPIT_verified',passed=True))
 for mask,v in zip(selectors,vals[1:]):
  for i in range(len(grid)):
   good=np.isfinite(vals[0][i]);inside=mask[i]&good;outside=~mask[i]&good
   if inside.any() and outside.any():assert np.min(v[i,inside])>np.max(v[i,outside])
   np.testing.assert_array_equal(np.isfinite(v[i]),good)
 checks.append(dict(test='same_fullA_support_allperiods_and_strictmembership_priority',passed=True));q.dump(OUT/'upstream_verified_selectors.json',provenance)
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='fullA membershipincrement diagnostics, no formalpoolComb',benchmark_warning='common fullA support unlike source qualificationonly outputs'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f)
 results=pd.read_csv(OUT/'results.csv');base=results[results.key.eq(SPECS[0]['key'])];deltas=[]
 for _,r in results[~results.key.eq(SPECS[0]['key'])].iterrows():
  b=base[(base.window==r.window)&(base.form==r.form)].iloc[0];d=dict(key=r.key,window=r.window,form=r.form)
  for k in ['net_excess_pct','gross_excess_pct','turnover_pct','held_daily_max_drawdown_pct']:d['delta_'+k]=r[k]-b[k] if b.periods and r.periods else np.nan
  deltas.append(d)
 pd.DataFrame(deltas).to_csv(OUT/'matched_size_control_deltas.csv',index=False)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED144',flush=True)
if __name__=='__main__':main()
