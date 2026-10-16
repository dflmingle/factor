"""Daily old-anchor and fixed shared-support pool diagnostics for weak new cash legs."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_continue_20261013 import simultaneous_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-cashdebt-incrementality-20261013'
SOURCE=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source67-20261013'
FIELDS={'ocf_netdebt_reported_high':'ocf_to_netdebt','ocf_debt_reported_high':'ocf_to_debt'}
POOL=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']

def main():
 OUT.mkdir(exist_ok=True);plan=dict(candidates=FIELDS,pool=POOL,scenarios=['baseline_same_support','add6',*['swap_'+p for p in POOL]],selection='both modest cashdebt positive triple-residuals; all fixed seat-add/replace scenarios, exploratory; no weightoptimization',platform_compute=0,rule=q.ALIGNMENT_RULE_VERSION)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'completion.json').exists():return
 cal,stocks,f=q.load_market();q.dates_all=cal;grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=(cal>='20210907')&(cal<='20260907');dc=-f['cap'][dates];c=f['close'];r=q.ratio(c,q.delay(c))-1
 oldout=q.OUT
 try:
  q.OUT=OUT;daily={k:q.daily_pit_field('fina_indicator',col,cal,stocks) for k,col in FIELDS.items()}
 finally:q.OUT=oldout
 for key,x in daily.items():
  x[~(f['cap']>0)]=np.nan;df=pd.read_pickle(SOURCE/'signal_panels.pkl')['panels'][key]
  np.testing.assert_allclose(x[pos],df.to_numpy(),equal_nan=True,atol=1e-6,rtol=1e-6)
 q.dump(OUT/'verification.json',dict(daily_PIT_equals_saved_signal_grid=True,daily_history='announcement replay from20180101; no backfill',prefix_PIT_verification_source=str(SOURCE.relative_to(q.ROOT)/'verification.json')))
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',cal,stocks);roe=q.daily_pit_field('fina_indicator','roe',cal,stocks)
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
 def sample(x):return np.where(f['cap'][dates]>0,x[dates],np.nan)
 anchors={'B01|SIZE':dc,'N01|REV20':sample(-(q.ratio(c,q.delay(c,20))-1)),'B03|REV40':sample(-(q.ratio(c,q.delay(c,40))-1)),
  'B08|BM_latest_proxy':sample(q.ratio(eq,f['cap']*10000)),'N27|ROE_latest_proxy':sample(roe),
  'known|LOW_IVOL120':sample(-iv),'N08|TURN_STD21':sample(-q.rolling(f['turnover'],21,'std')),
  'B02|TURN_BIAS21_504':sample(1-q.ratio(q.rolling(f['turnover'],21),q.rolling(f['turnover'],504))),
  'B04|DD120':sample(1-q.ratio(c,q.rolling(c,120,'max'))),'N09|MAX21':sample(-q.rolling(r,21,'max')),
  'N16|SKEW60':sample(-q.rolling(r,60,'skew')),
  'unassigned|H03_impact60_proxy':sample(q.ratio(q.rolling(q.ratio(f['high']-f['low'],q.delay(c)+1e-6),60,'sum'),q.rolling(f['amount'],60,'sum')+1)),
  'composite|weightedREV21':sample(-q.ratio(q.rolling(f['turnover']*r,21,'sum'),q.rolling(f['turnover'],21,'sum')))}
 rows=[]
 for key,x in daily.items():
  for label,y in anchors.items():rows.append(dict(candidate=key,anchor=label,scope='daily_cross_sectional_spearman_mean',**rho_details(x[dates],y)))
  print('CASHDEBT_DAILY_CORR',key,flush=True)
 df=pd.DataFrame(rows);df.to_csv(OUT/'daily_correlations.csv',index=False);df.assign(absrho=df.rho.abs()).sort_values('absrho',ascending=False).groupby('candidate').head(3).to_csv(OUT/'nearest_other_top3_daily.csv',index=False)
 frame,*_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl');old=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl');legs=[]
 for key in POOL:
  data=frame[['date','instrument']].copy();data['date']=pd.to_datetime(data.date);data['value']=old['scores'][key].to_numpy();legs.append(data.pivot(index='date',columns='instrument',values='value').reindex(index=grid,columns=stocks).to_numpy())
 stats=[];cap=f['cap'][pos];rev=-(q.ratio(c,q.delay(c,20))-1)[pos]
 for key,x in daily.items():
  for form,value in [('raw',x[pos]),('triple_residual',simultaneous_residual(x[pos],[-cap,rev,-iv[pos]]))]:
   good=np.isfinite(value)&np.isfinite(np.stack(legs)).all(axis=0)&(cap>0);z=[q.zscore(np.where(good,a,np.nan)) for a in legs];new=q.zscore(np.where(good,value,np.nan));base=sum(z)/5
   cases={'baseline_same_support':base,'add6':(sum(z)+new)/6};cases.update({'swap_'+name:(sum(z)-z[i]+new)/5 for i,name in enumerate(POOL)})
   for case,score in cases.items():
    for win,use in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
     a,periods,nav=q.evaluate(score[use],grid[use],stocks,pos[use],f);a.update(candidate=key,form=form,scenario=case,window=win,scope='legacy_saved_seats_shared_support_exploratory_not_current_rule_pool_reproduction')
     stats.append(a);dest=OUT/win;dest.mkdir(exist_ok=True);stem=f'{key}.{form}.{case}';periods.to_csv(dest/(stem+'.periods.csv'),index=False);nav.to_csv(dest/(stem+'.daily_nav.csv'),index=False)
   print('CASHDEBT_POOL',key,form,flush=True)
 table=pd.DataFrame(stats).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore');base=table[table.scenario.eq('baseline_same_support')][['candidate','form','window','net_excess_pct','held_daily_max_drawdown_pct','turnover_pct']]
 table=table.merge(base,on=['candidate','form','window'],suffixes=('','_base'))
 for col in ['net_excess_pct','held_daily_max_drawdown_pct','turnover_pct']:table['delta_'+col]=table[col]-table[col+'_base']
 table.to_csv(OUT/'pool_scenarios.csv',index=False)
 q.dump(OUT/'config.json',dict(rule=q.ALIGNMENT_RULE_VERSION,legacy_pool_signal_origin='qualitygate3 storedscores; provenance not certified under current financialfix/qualitygate4',diagnostic_only=True,sharedsupport=True,aggregation='equal-CSz perdate, restricted before scaling',dailyanchors=len(anchors),covered_daily_dates=int(dates.sum()),incomplete_master_cluster_coverage=True,no_official_Comb_or_rank_inference=True,no_untouched_OOS=True,platform_compute=0))
 q.dump(OUT/'completion.json',dict(completed=True,pool_diagnostic_rows=len(table),platform_compute=0));print('FINISHED_CASHDEBT_INCREMENT',flush=True)
if __name__=='__main__':main()
