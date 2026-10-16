"""Further falsification of the two retained weak accounting mechanisms."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from dataclasses import asdict
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import simultaneous_residual
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_accounting_interactions_20261014 import save_evaluation
from platform_score_rules import seat_stats

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-accounting-selected-audit-20261014'
BASE=q.ROOT/'research_reports/platform_alignment/quant-corpus-accounting-completion-20261014'
INTER=q.ROOT/'research_reports/platform_alignment/quant-corpus-accounting-interactions-20261014'
KEYS=['coherent_seasonal_revenue_sue3','quarter_deducted_roa_yoy_change']

def main():
 OUT.mkdir(exist_ok=True);cal,stocks,f=q.load_market();q.dates_all=cal
 saved=pd.read_pickle(BASE/'signal_panels.pkl');grid=saved['dates'];pos=cal.get_indexer(grid)
 old=pd.read_pickle(q.OUT/'signal_panels.pkl')['panels'];iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
 controls=[-f['cap'][pos],-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos],-iv[pos]]
 quality=[old[k].reindex(index=grid,columns=stocks).to_numpy() for k in ['roe','book_market','growth_profit']]
 rows=[];correlations=[]
 for key in KEYS:
  x=saved['panels'][key].to_numpy()
  for form,c in [('size_rev_IVOL_ROE_BM_residual',controls+quality[:2]),
                 ('size_rev_IVOL_ROE_BM_profitgrowth_residual',controls+quality)]:
   res=simultaneous_residual(x,c);save_evaluation(OUT,key,form,res,grid,pos,stocks,f,rows)
  for name,v in zip(['ROE','BM','profit_growth'],quality):correlations.append(dict(candidate=key,anchor=name,scope='saved_signal_dates',**rho_details(x,v)))
 # Verify old seasonal raw recipe is exactly the same research mechanism.
 legacy=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source13-20261012/signal_panels.pkl')['panels']['revenue_seasonal_sue12']
 previous=legacy.reindex(index=grid,columns=stocks).to_numpy();current=saved['panels'][KEYS[0]].to_numpy()
 common=np.isfinite(previous)&np.isfinite(current);diff=np.abs(previous[common]-current[common])
 q.dump(OUT/'verification.json',dict(old_seasonal_formula_same=True,no_new_raw_mechanism_claim=True,
   byte_equal=False,old_float32_YTD_differencing_new_float64=True,
   finite_mask_equal=bool(np.array_equal(np.isfinite(previous),np.isfinite(current))),
   value_max_absolute_difference=float(diff.max()),mean_absolute_difference=float(diff.mean()),
   exact_intersection_rank_agreement=rho_details(current,previous)))
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
 pd.DataFrame(correlations).to_csv(OUT/'quality_control_correlations.csv',index=False)
 # Paired gross/cost diagnosis and autocorrelation-aware exploratory bounds.
 boot=[];rng=np.random.default_rng(20261014)
 for key in KEYS:
  for win in ['five_year','recent']:
   root=INTER/'pool'
   a=pd.read_csv(root/f'{key}.base_shared_support.{win}.periods.csv')
   b=pd.read_csv(root/f'{key}.add6.{win}.periods.csv')
   assert a.date.tolist()==b.date.tolist()
   delta=b.net_excess_path.to_numpy()-a.net_excess_path.to_numpy();n=len(delta)
   block=6;starts=rng.integers(0,n,size=(4000,int(np.ceil(n/block))))
   ids=((starts[:,:,None]+np.arange(block))%n).reshape(4000,-1)[:,:n]
   draws=delta[ids].mean(axis=1)*2520
   boot.append(dict(candidate=key,window=win,periods=n,paired_path_delta_annual_pct=delta.mean()*2520,
     mean_delta_gross_pct=(b.gross_excess.mean()-a.gross_excess.mean())*2520,
     turnover_delta_pp=(b.turnover.mean()-a.turnover.mean())*100,
     circular_block6_bootstrap_low95_pct=np.quantile(draws,.025),high95_pct=np.quantile(draws,.975),
     exploratory_post_selection=True,no_corrected_significance_claim=True))
 pd.DataFrame(boot).to_csv(OUT/'paired_pool_uncertainty.csv',index=False)
 seats=[]
 for key in KEYS:
  for form,root in [('raw',BASE),('size_reversal_IVOL_residual',INTER)]:
   p=pd.read_csv(root/'five_year'/f'{key}.{form}.periods.csv')
   stats=seat_stats(p.rank_ic.to_numpy());seats.append(dict(key=key,form=form,**asdict(stats)))
 q.dump(OUT/'local_seat_proxy.json',seats)
 q.dump(OUT/'config.json',dict(rule=q.ALIGNMENT_RULE_VERSION+'-accounting-selected-arithmetic-fullA',
   purpose='extra ROE/BM/profit-growth controls and paired pool uncertainty; not OOS or platform',
   platform_compute_spent=0,pool_scope='saved legacy five seats only',selected_after_14_local_tests=True))
 print(pd.DataFrame(rows)[['key','form','window','net_excess_pct']].to_string(index=False),flush=True)
 print('SELECTED_AUDIT_COMPLETE',flush=True)

if __name__=='__main__':main()
