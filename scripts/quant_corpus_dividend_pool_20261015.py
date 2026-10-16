"""All six dividend candidates added to the legacy pool, local diagnosis only."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from dataclasses import asdict
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_dividend_completion_20261015 import OUT,DEFS
from quant_corpus_continue_20261013 import simultaneous_residual
from quant_corpus_correlations_20261012 import rho_details
from revenue_seasonal_pool_test_20261014 import POOL,normalize,monthly
import platform_score_rules as sr

def main():
 dest=OUT/'pool_add_diagnostic';dest.mkdir(exist_ok=True)
 q.dump(dest/'frozen_plan.json',dict(candidates=[d[0] for d in DEFS],scenarios=['base_native','base_shared','add6'],
   origin='after standalone exploratory screen; not heldout',no_formal_pool_changes=True,
   seat_stats='local IC proxy; no candidate platform IC',platform_compute_spent=0,
   scope='all six adds, no swaps; diagnostics cannot override individual seat gates'))
 cal,stocks,f=q.load_market();q.dates_all=cal
 saved=pd.read_pickle(OUT/'signal_panels.pkl');dates=saved['dates'];pos=cal.get_indexer(dates)
 sf,_,_,_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
 built=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
 panels=[]
 for key in POOL:
  frame=sf[['date','instrument']].copy();frame['date']=pd.to_datetime(frame.date);frame['value']=built['scores'][key].to_numpy()
  panels.append(frame.pivot(index='date',columns='instrument',values='value').reindex(index=dates,columns=stocks).to_numpy())
 base=sum(panels)/5
 source=q.ROOT/'research_reports/platform_alignment/revenue-seasonal-pool-20261014/seat_source.json'
 si=json.loads(source.read_text())['seat_si'];rows=[]
 for definition in DEFS:
  key=definition[0];x=saved['panels'][key].to_numpy();z=normalize(x);common=np.isfinite(base)&np.isfinite(x)
  score={'base_native':base,'base_shared':np.where(common,base,np.nan),'add6':np.where(common,(sum(panels)+z)/6,np.nan)}
  cp=pd.read_csv(OUT/'five_year'/f'{key}.raw.periods.csv');s=sr.seat_stats(cp.rank_ic)
  bridge=sr.seat_change_bridge(si.values(),added=s.s_i_a,pool_age_months=1,nb_active=True)
  for win,mask in [('five_year',np.ones(len(dates),bool)),('recent',dates>='20260101')]:
   computed={}
   for scenario,value in score.items():
    a,p,d=q.evaluate(value[mask],dates[mask],stocks,pos[mask],f)
    neutral=simultaneous_residual(value[mask],[-f['cap'][pos[mask]]]);n,_,_=q.evaluate(neutral,dates[mask],stocks,pos[mask],f)
    a.update(size_rank_residual_net=n['net_excess_pct'],corr_smallsize=rho_details(value[mask],-f['cap'][pos[mask]])['rho'])
    mt=monthly(p,d,cal);computed[scenario]=(a,mt)
    folder=dest/win;folder.mkdir(exist_ok=True)
    p.to_csv(folder/f'{key}.{scenario}.periods.csv',index=False);d.to_csv(folder/f'{key}.{scenario}.daily_nav.csv',index=False)
    mt.to_csv(folder/f'{key}.{scenario}.monthly.csv',index=False)
   a,mt=computed['add6'];b,bmt=computed['base_shared'];native,_=computed['base_native']
   paired=bmt.merge(mt,on='month',suffixes=('_base','_new'))
   for term in ['E','T','NC']:paired['delta_'+term]=paired[term+'_new']-paired[term+'_base']
   paired['delta_A_points_local_proxy']=bridge.points_na
   paired['delta_B_steady_points_local_proxy']=bridge.points_nb_steady
   paired['delta_C_points']=paired.delta_NC*19800
   paired['delta_Comb_AC_points_local_proxy']=paired.delta_C_points+bridge.points_na
   paired['delta_Comb_ABsteadyC_points_local_proxy']=paired.delta_Comb_AC_points_local_proxy+bridge.points_nb_steady
   paired.to_csv(dest/win/f'{key}.monthly_deltas.csv',index=False)
   row=dict(candidate=key,window=win,local_si_proxy=s.s_i_a,base_net=b['net_excess_pct'],native_base_net=native['net_excess_pct'],
    add_net=a['net_excess_pct'],delta_net_pp=a['net_excess_pct']-b['net_excess_pct'],
    base_dd=b['held_daily_max_drawdown_pct'],add_dd=a['held_daily_max_drawdown_pct'],
    base_turn=b['turnover_pct'],add_turn=a['turnover_pct'],delta_E=paired.delta_E.mean(),delta_T=paired.delta_T.mean(),
    delta_NC=paired.delta_NC.mean(),delta_A_local_proxy=bridge.points_na,
    delta_B_steady_local_proxy=bridge.points_nb_steady,delta_C=paired.delta_C_points.mean(),
    delta_Comb_AC_local_proxy=paired.delta_Comb_AC_points_local_proxy.mean(),
    delta_Comb_ABsteadyC_local_proxy=paired.delta_Comb_ABsteadyC_points_local_proxy.mean(),
    base_corr_smallsize=b['corr_smallsize'],add_corr_smallsize=a['corr_smallsize'],
    base_size_residual_net=b['size_rank_residual_net'],add_size_residual_net=a['size_rank_residual_net'],
    size_guard=abs(a['corr_smallsize'])<=abs(b['corr_smallsize']) and a['size_rank_residual_net']>=b['size_rank_residual_net'])
   rows.append(row);print('POOL_ADD',key,win,round(row['delta_net_pp'],3),round(row['delta_Comb_AC_local_proxy']),flush=True)
   pd.DataFrame(rows).to_csv(dest/'results.csv',index=False)
 q.dump(dest/'completion.json',dict(completed=True,platform_compute_spent=0,candidates=6,
   candidate_A_and_B_local_proxy=True,B_is_steady_proxy_not_future_observation=True,
   limitations='legacy stored scores; local drawdown not byte-equivalent platform; no swaps evaluated'))

if __name__=='__main__':main()
