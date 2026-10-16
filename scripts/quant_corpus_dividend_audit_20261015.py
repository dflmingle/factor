"""Causal, tie, multiplicity and old-cluster audit of the fixed dividend cohort."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
from dataclasses import asdict
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
import quant_corpus_local_20261012 as q
from quant_corpus_dividend_completion_20261015 import OUT, DEFS, CONTROL_DEFS, values, replay_one, income_ttm
from quant_corpus_correlations_20261012 import saved_grid
from platform_score_rules import seat_stats

def interval(x,seed=20261015,annual=1):
 x=np.asarray(x,float);x=x[np.isfinite(x)];rng=np.random.default_rng(seed)
 # Circular six-period moving-block bootstrap; descriptive and not OOS.
 starts=rng.integers(0,len(x),size=(4000,int(np.ceil(len(x)/6))))
 ids=((starts[:,:,None]+np.arange(6))%len(x)).reshape(4000,-1)[:,:len(x)]
 means=x[ids].mean(axis=1)*annual
 return np.quantile(means,[.025,.975]).tolist()

def main():
 assert json.loads((OUT/'completion.json').read_text())['completed']
 cal,stocks,f=q.load_market();q.dates_all=cal
 saved=pd.read_pickle(OUT/'signal_panels.pkl');dates=saved['dates'];pos=cal.get_indexer(dates)
 prior=q.OUT
 try:q.OUT=OUT;saved_grid()
 finally:q.OUT=prior
 rows=[]
 result=pd.read_csv(OUT/'results.csv')
 for row in result.to_dict('records'):
  p=pd.read_csv(OUT/row['window']/f"{row['key']}.{row['form']}.periods.csv")
  stats=seat_stats(p.rank_ic)
  row.update(local_s_i_proxy=stats.s_i_a,ic_nominal_t_p=float(ttest_1samp(p.rank_ic,0).pvalue),
   net_block6_ci_low=interval(p.net_excess_path,annual=252/10*100)[0],
   net_block6_ci_high=interval(p.net_excess_path,annual=252/10*100)[1])
  row['local_seat_gate']=row['net_excess_pct']>=15 and row['local_s_i_proxy']>=.035 and row['turnover_pct']<=40
  rows.append(row)
 pd.DataFrame(rows).to_csv(OUT/'audited_results.csv',index=False)
 pairs=[('dividend36_peg_pb_small_priority','control36_without_dividend'),
  ('dividend26_peg_price_small_priority','control26_without_dividend'),
  ('dividend85_cheap_value_priority','control85_without_dividend')]
 pairrows=[]
 for cand,control in pairs:
  for win in ['five_year','recent']:
   for form in ['raw','size_rev_ivol_residual']:
    a=pd.read_csv(OUT/win/f'{cand}.{form}.periods.csv');b=pd.read_csv(OUT/win/f'{control}.{form}.periods.csv')
    assert a.date.equals(b.date) and np.array_equal(a.n,b.n)
    paired=a.merge(b,on='date',suffixes=('_candidate','_control'))
    diff=paired.net_excess_path_candidate-paired.net_excess_path_control
    ci=interval(diff,annual=25.2*100)
    ar=result[(result.key==cand)&(result.window==win)&(result.form==form)].iloc[0]
    br=result[(result.key==control)&(result.window==win)&(result.form==form)].iloc[0]
    pairrows.append(dict(candidate=cand,control=control,window=win,form=form,periods=len(paired),
      same_support=True,delta_net_pp=ar.net_excess_pct-br.net_excess_pct,
      paired_block6_ci_low=ci[0],paired_block6_ci_high=ci[1],
      delta_turn_pp=ar.turnover_pct-br.turnover_pct,
      delta_dd_pp=ar.held_daily_max_drawdown_pct-br.held_daily_max_drawdown_pct,
      net_period_convention='first entry no fee; headline annual cost excludes first NaN turnover'))
 pd.DataFrame(pairrows).to_csv(OUT/'matched_dividend_ablation.csv',index=False)
 # A fixed random permutation changes only exact ties, never economically
 # distinct ranks. This is a sensitivity, not a new candidate or fitted rule.
 ties=[]
 for key in ['registered_dividend_yield365','dividend_three_year_floor']:
  x=saved['panels'][key].to_numpy()
  for seed in [918273,20261015]:
   rng=np.random.default_rng(seed);reordered=np.full_like(x,np.nan)
   for i in range(len(x)):
    ids=np.flatnonzero(np.isfinite(x[i]));permutation=ids[rng.permutation(len(ids))]
    order=permutation[np.argsort(x[i,permutation],kind='stable')]
    reordered[i,order]=np.arange(len(order))
   for win,mask in [('five_year',np.ones(len(dates),bool)),('recent',dates>='20260101')]:
    a,p,d=q.evaluate(reordered[mask],dates[mask],stocks,pos[mask],f)
    ties.append(dict(key=key,seed=seed,window=win,scope='exact-tie-only permutation',**a))
 pd.DataFrame(ties).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'tie_sensitivity.csv',index=False)
 # Prefix check on cached daily inputs recomputes all cross-sectional ranks
 # using the full universe, not a narrow stock slice.
 daily=pd.read_pickle(OUT/'daily_scores.pkl');dp=cal.get_indexer(daily['dates'])
 cap=f['cap'][dp];eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',cal,stocks)[dp]
 ttm=pd.read_pickle(OUT/'daily_parent_income_ttm.pkl');growth=q.daily_pit_field('fina_indicator','netprofit_yoy',cal,stocks)[dp]
 pe=q.ratio(cap*10000,ttm);pb=q.ratio(cap*10000,eq)
 checks=[]
 # Literal hand-calculated cash example checks a one-day registration
 # boundary, fiscal blocks and an unknown cash event independently.
 ns=lambda s:pd.Timestamp(s).value
 r=replay_one(np.array([ns('2020-05-01'),ns('2021-05-01'),ns('2022-05-01')]),
   np.array([ns('2020-05-10'),ns('2021-05-10'),ns('2022-05-10')]),
   pd.PeriodIndex(['2019Q4','2020Q4','2021Q4'],freq='Q').asi8,np.array([100.,200.,np.nan]),
   np.array([ns('2021-04-30'),ns('2022-04-30')]),pd.PeriodIndex(['2021Q1','2022Q1'],freq='Q').asi8,
   np.array([ns('2021-05-09'),ns('2021-05-10'),ns('2022-05-10')]))
 np.testing.assert_allclose(r[:,0],[100,200,100,0]);np.testing.assert_allclose(r[:,1],[200,200,100,0])
 assert np.isnan(r[0,2]) and np.isnan(r[1,2]) and r[2,2]==200
 checks.append(dict(test='hand_calculated_registration_boundary_and_unknown_cash',passed=True))
 previous=q.FIN_FIELDS
 try:q.FIN_FIELDS={'income':['n_income_attr_p']};inc=q.pit_tables()['income']
 finally:q.FIN_FIELDS=previous
 ids=stocks.get_indexer(['600036.SH','000001.SZ','600519.SH']);ids=ids[ids>=0]
 for n in [300,800]:
  subset=inc[inc.ann_date.le(daily['dates'][n-1])&inc.instrument.isin(stocks[ids])]
  recomputed=income_ttm(subset,daily['dates'][:n],stocks[ids])
  np.testing.assert_allclose(recomputed,ttm[:n,ids],equal_nan=True,atol=1e-3,rtol=1e-6)
  checks.append(dict(test='parent_income_raw_filing_cutoff_replay',rows=n,symbols=len(ids),passed=True))
 for n in [300,800]:
  replay,_=values(daily['cash'][:,:n],cap[:n],pe[:n],pb[:n],growth[:n],f['raw_close'][dp[:n]])
  for sp,x in zip(DEFS+CONTROL_DEFS,replay):
   np.testing.assert_allclose(x,daily['panels'][sp[0]][:n],equal_nan=True,rtol=1e-6,atol=1e-6)
  checks.append(dict(test='full_universe_prefix_cross_sectional_recompute',rows=n,passed=True))
 q.dump(OUT/'followup_audit.json',dict(completed=True,prefix_checks=checks,
   hypotheses=6,transforms_including_raw_and_residual=12,nominal_bonferroni_alpha=.05/12,
   larger_prior_search_not_accounted_by_12=True,untouched_oos=False,
   bootstrap='4000 circular moving blocks, length6, seed20261015; descriptive only',
   bootstrap_headline_difference='bootstrap uses per-period path first fee=0; headline cost mean excludes first NaN turnover',
   cluster_scope='primary daily five anchors plus 54 old saved-grid references; incomplete master coverage',
   platform_compute_spent=0))
 print('DIVIDEND_AUDIT_DONE',flush=True)

if __name__=='__main__':main()
