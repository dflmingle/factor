"""Fixed second local cohort: accounting improvement versus price response.

Exploratory after the first accounting cohort. No fresh platform requests.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import simultaneous_residual
from quant_corpus_correlations_20261012 import rho_details,saved_grid
import quant_corpus_accounting_completion_20261014 as first

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-accounting-interactions-20261014'
DEFS=[
 ('revenue_surprise_unpriced60','收入惊喜减60日涨幅','rank(seasonal_revenue_sue3)-rank(RET60)',first.SUE),
 ('deducted_profit_improve_unpriced60','扣非盈利改善减60日涨幅','rank(deducted_profit_yoy_asset_change)-rank(RET60)',first.PROFIT),
 ('revenue_surprise_reversal20_product','收入惊喜×20日反转','rank(seasonal_revenue_sue3)*rank(-RET20)',first.SUE),
 ('deducted_profit_improve_reversal20_product','扣非改善×20日反转','rank(deducted_profit_yoy_asset_change)*rank(-RET20)',first.PROFIT),
 ('revenue_surprise_cash_yield_rank','收入惊喜加现金增量估值','rank(seasonal_revenue_sue3)+rank(cash_equivalent_increase_ttm_yield)',first.CASH),
 ('margin_stability_reversal20_rank','单季毛利稳定加20日反转','rank(quarter_margin_stability8)+rank(-RET20)',first.MARGIN)]
SPECS=[dict(key=k,name=n,formula=formula,source_paths=[source,first.SUE] if source!=first.SUE else [source],
            fidelity='proxy: NEW interaction adaptation; source accounting mechanism combined with daily price response, original trading strategy not reproduced',
            gated=False,source_execution_reproduced=False) for k,n,formula,source in DEFS]

def interactions(p,ret60,rev20):
 r=q.rank(p['coherent_seasonal_revenue_sue3']);e=q.rank(p['quarter_deducted_roa_yoy_change'])
 c=q.rank(p['cash_equivalent_increase_ttm_yield']);m=q.rank(p['quarter_margin_stability8'])
 rv=q.rank(rev20);ret=q.rank(ret60)
 return [r-ret,e-ret,r*rv,e*rv,r+c,m+rv]

def save_evaluation(dest,key,form,score,grid,pos,stocks,f,rows,**extra):
 for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
  a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],f)
  a.update(key=key,form=form,window=win,**extra);rows.append(a)
  folder=dest/win;folder.mkdir(exist_ok=True)
  q.dump(folder/f'{key}.{form}.json',a)
  p.to_csv(folder/f'{key}.{form}.periods.csv',index=False)
  d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)

def main():
 OUT.mkdir(exist_ok=True);q.dump(OUT/'frozen_plan.json',dict(specs=SPECS,platform_compute=0,
   exploratory='second local cohort after accounting batch; all tests retained; no untouched OOS'))
 calendar,stocks,f=q.load_market();q.dates_all=calendar
 dates=calendar[(calendar>='20210907')&(calendar<='20260907')]
 dailypos=calendar.get_indexer(dates);grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid);ix=dates.get_indexer(grid)
 panels=pd.read_pickle(first.OUT/'daily_scores.pkl')
 ret60=(q.ratio(f['close'],q.delay(f['close'],60))-1)[dailypos]
 rev=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[dailypos]
 vals=interactions(panels,ret60,rev);checks=[]
 for stop in [401,901]:
  for a,b in zip(vals,interactions({k:v[:stop] for k,v in panels.items()},ret60[:stop],rev[:stop])):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True)
  checks.append(dict(test='prefix_rank_interaction_recompute',stop=stop,passed=True))
 run(OUT,SPECS,[v[ix] for v in vals],calendar,stocks,f,checks,
     dict(proxy='accounting/price interaction; fixed weights/windows; no universe qualification',first_cohort=str(first.OUT.relative_to(q.ROOT))),
     residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 oldout=q.OUT
 try:q.OUT=OUT;saved_grid()
 finally:q.OUT=oldout
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
 controls=[-f['cap'][pos],rev[ix],-iv[pos]]
 allpanels={**{k:v[ix] for k,v in panels.items()},**{s['key']:v[ix] for s,v in zip(SPECS,vals)}}
 rows=[];residuals={}
 for key,x in allpanels.items():
  residuals[key]=simultaneous_residual(x,controls)
  save_evaluation(OUT,key,'size_reversal_IVOL_residual',residuals[key],grid,pos,stocks,f,rows)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'incremental_information.csv',index=False)
 # Saved old five-seat diagnostic: do not infer official pool scores.
 POOL=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']
 frame,_,_,_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
 old=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
 base=[]
 for key in POOL:
  x=frame[['date','instrument']].copy();x['date']=pd.to_datetime(x.date);x['value']=old['scores'][key].to_numpy()
  base.append(x.pivot(index='date',columns='instrument',values='value').reindex(index=grid,columns=stocks).to_numpy(dtype=np.float32))
 selected=['coherent_seasonal_revenue_sue3','quarter_deducted_roa_yoy_change','cash_equivalent_increase_ttm_yield',*[s['key'] for s in SPECS]]
 poolrows=[]
 for key in selected:
  candidate=allpanels[key];common=np.isfinite(candidate)&np.isfinite(np.stack(base)).all(axis=0)
  legs=[q.zscore(np.where(common,v,np.nan)) for v in base];cz=q.zscore(np.where(common,candidate,np.nan))
  scores={'base_shared_support':sum(legs)/5,'add6':(sum(legs)+cz)/6,'swap_SIZE':(sum(legs)-legs[0]+cz)/5}
  for scenario,score in scores.items():
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],f)
    sn=simultaneous_residual(score[mask],[controls[0][mask],controls[1][mask]])
    na,_,_=q.evaluate(sn,grid[mask],stocks,pos[mask],f)
    a.update(candidate=key,scenario=scenario,window=win,corr_size=rho_details(score[mask],controls[0][mask])['rho'],
      size_reversal_residual_net=na.get('net_excess_pct'));poolrows.append(a)
    dest=OUT/'pool';dest.mkdir(exist_ok=True)
    p.to_csv(dest/f'{key}.{scenario}.{win}.periods.csv',index=False)
  print('POOL',key,flush=True)
 pd.DataFrame(poolrows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'shared_support_pool_scenarios.csv',index=False)
 # Primary daily correlations, exact intersection for each pair.
 dailycontrols={'B01|SIZE':-f['cap'][dailypos],'N01|REV20':rev,'IVOL120|known':-iv[dailypos],
  'B08|BM_proxy':q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)[dailypos]/(f['cap'][dailypos]*10000)}
 cr=[]
 for s,v in zip(SPECS,vals):
  for anchor,y in dailycontrols.items():cr.append(dict(candidate=s['key'],anchor=anchor,scope='every_trading_day_cross_sectional_Spearman',**rho_details(v,y)))
 pd.DataFrame(cr).to_csv(OUT/'daily_anchor_correlations.csv',index=False)
 # Causal market regimes fixed from observable prices, descriptive only.
 dailyret=q.ratio(f['close'],q.delay(f['close']))-1
 market=np.nanmean(np.where(f['cap']>0,dailyret,np.nan),axis=1)
 index=np.cumprod(1+np.nan_to_num(market));trend=index/q.delay(index,120)-1
 vol=pd.Series(market).rolling(60).std();highvol=(vol>vol.rolling(252,min_periods=252).median()).to_numpy()
 regimes=np.where(trend[pos]>=0,'up','down');vr=np.where(highvol[pos],'highvol','lowvol')
 state=[]
 for key in selected:
  _,p,_=q.evaluate(allpanels[key],grid,stocks,pos,f)
  if p.empty:continue
  p['regime']=[regimes[grid.get_loc(d)]+'_'+vr[grid.get_loc(d)] for d in pd.to_datetime(p.date)]
  for name,g in p.groupby('regime'):
   state.append(dict(key=key,regime=name,periods=len(g),gross_excess_pct=g.gross_excess.mean()*2520,
     annual_cost_pct=g.turnover.mean()*.006*2520,net_excess_pct=(g.gross_excess.mean()-g.turnover.mean()*.006)*2520,
     rank_ic=g.rank_ic.mean(),interpretation='post-hoc conditional diagnostic; no deployable regime winner claim'))
 pd.DataFrame(state).to_csv(OUT/'observable_regime_diagnostics.csv',index=False)
 q.dump(OUT/'audit_complete.json',dict(completed=True,hypotheses=6,platform_compute_spent=0,
   pool_scope='legacy stored five seats on shared support, no live equivalence/official DeltaComb',
   regimes='causal market RET120 sign x STD60 above trailing252 median; conditional retrospective diagnostic',oos=False))
 print('INTERACTIONS_COMPLETE',flush=True)

if __name__=='__main__':main()
