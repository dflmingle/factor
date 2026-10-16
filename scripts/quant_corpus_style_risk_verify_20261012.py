"""Daily prior-anchor correlations and frozen-window falsification for style risk."""
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_source10_20261012 import one
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-style-risk-validation-20261012'

def style(f,eq,roe,ta,positions,window=120):
 out=np.full((len(positions),f['close'].shape[1]),np.nan,np.float32)
 for i,t in enumerate(positions):
  result=one(f,eq,roe,ta,t,window=window)
  out[i]=1-q.ratio(result[1]**2,np.where(result[0]**2>1e-12,result[0]**2,np.nan))
  out[i,~(f['cap'][t]>0)]=np.nan
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market();q.dates_all=calendar
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks);ta=q.daily_pit_field('balancesheet','total_assets',calendar,stocks)
 days=np.flatnonzero((calendar>='20210907')&(calendar<='20260907'))
 cache=OUT/'daily_style.pkl'
 if cache.exists():x=pd.read_pickle(cache)
 else:
  x=style(f,eq,roe,ta,days);pd.to_pickle(x,cache)
 known=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source14-20261012/signal_panels.pkl')['panels']['ff3_explained_high'].to_numpy()
 ix=calendar[days].get_indexer(grid);np.testing.assert_allclose(x[ix],known,equal_nan=True,atol=1e-6,rtol=1e-5)
 c=f['close'];cap=f['cap'];turn=f['turnover'];v=f['volume'];r=q.ratio(c,q.delay(c))-1
 def sub(z):return np.where(cap[days]>0,z[days],np.nan)
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
 anchors={
  'B01|SIZE-ONLY':sub(-cap),'B02|TURN-BIAS21/504':sub(1-q.ratio(q.rolling(turn,21),q.rolling(turn,504))),
  'B03|RET40':sub(-(q.ratio(c,q.delay(c,40))-1)),
  'B04|DD120':sub(1-q.ratio(c,q.rolling(c,120,'max'))),
  'B05|CHIP250':sub(q.ratio(q.ratio(q.rolling(v*(f['open']+c)/2,250,'sum'),q.rolling(v,250,'sum')),c)-1),
  'B08|BM_latest_proxy':sub(q.ratio(eq,cap*10000)),
  'B09|DD60':sub(1-q.ratio(c,q.rolling(c,60,'max'))),
  'N01|REV20':sub(-(q.ratio(c,q.delay(c,20))-1)),
  'N08|TURN_STD21':sub(-q.rolling(turn,21,'std')),'N09|MAX21':sub(-q.rolling(r,21,'max')),
  'N16|SKEW60':sub(-q.rolling(r,60,'skew')),'N27|ROE_latest_proxy':sub(roe),
  'known|LOW_IVOL120':sub(-iv),
  'unassigned|H03-IMPACT60':sub(q.ratio(q.rolling(q.ratio(f['high']-f['low'],q.delay(c)+1e-6),60,'sum'),q.rolling(f['amount'],60,'sum')+1)),
  'composite|WEIGHTED-REV21':sub(-q.ratio(q.rolling(turn*r,21,'sum'),q.rolling(turn,21,'sum')))}
 correlations=[]
 res=dual_residual(x,sub(-cap),anchors['N01|REV20'])
 for form,xx in [('raw',x),('size_reversal_rank_residual',res)]:
  for name,y in anchors.items():
   correlations.append({'candidate':'ff3_explained_high','form':form,'anchor':name,'scope':'every_trading_day_cross_sectional_spearman_mean',**rho_details(xx,y)})
 df=pd.DataFrame(correlations);df.to_csv(OUT/'daily_old_anchor_correlations.csv',index=False)
 df.assign(abs_rho=df.rho.abs()).sort_values('abs_rho',ascending=False).groupby('form').head(3).to_csv(OUT/'nearest_daily_top3.csv',index=False)
 checks=[{'test':'daily_full_grid_matches_frozen_signals','passed':True}]
 # Window sensitivity is a falsification, not a new selection contest.
 sensitivities=[]
 for n in [60,120,252]:
  score=known if n==120 else style(f,eq,roe,ta,pos,window=n)
  for form,v in [('raw',score),('size_reversal_rank_residual',dual_residual(score,-cap[pos],anchors['N01|REV20'][ix]))]:
   for win,wm in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(v[wm],grid[wm],stocks,pos[wm],f);a.update(window=win,form=form,risk_lookback=n)
    sensitivities.append(a);dest=OUT/f'window{n}'/win;dest.mkdir(parents=True,exist_ok=True)
    q.dump(dest/f'{form}.json',a);p.to_csv(dest/f'{form}.periods.csv',index=False)
  # Truncation of original daily arrays must preserve source-derived history.
  t=pos[77];cut=style({k:v[:t+1] for k,v in f.items()},eq[:t+1],roe[:t+1],ta[:t+1],np.array([t]),window=n)
  np.testing.assert_allclose(score[77],cut[0],equal_nan=True,rtol=1e-5,atol=1e-6)
  checks.append({'test':'source_model_and_ratio_full_daily_truncation','lookback':n,'passed':True})
 pd.DataFrame(sensitivities).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'window_sensitivity.csv',index=False)
 q.dump(OUT/'verification.json',checks)
 # Period-label inference is exploratory: preserve multiplicity and dependency caveats.
 periods=pd.read_csv(OUT/'window120/five_year/raw.periods.csv');n=len(periods)
 t,p=ttest_1samp(periods.rank_ic,0)
 net=periods.net_excess_path.to_numpy();rng=np.random.default_rng(10612)
 means=[]
 # Fixed circular moving-block bootstrap, 12 periods per block,2000 draws.
 for _ in range(2000):
  starts=rng.integers(0,n,int(np.ceil(n/12)))
  indexes=np.concatenate([(np.arange(12)+s)%n for s in starts])[:n]
  means.append(np.mean(net[indexes])*25.2*100)
 q.dump(OUT/'inference.json',{'rankic_t_stat':float(t),'rankic_iid_p_value':float(p),
  'net_excess_block_bootstrap95_pct':list(np.quantile(means,[.025,.975])),
  'lookbacks_added_as_sensitivity':2,'bootstrap_blocks_periods':12,'bootstrap_draws':2000,
  'warning':'selected after many correlated hypotheses; no independent OOS; iid t-p not selection-adjusted; CI descriptive only',
  'stress_cost_net_one_way_050_pct':float(periods.gross_excess.mean()*25.2*100-periods.turnover.mean()*.01*25.2*100)})
 q.dump(OUT/'completion.json',{'completed':True,'daily_days':len(days),'anchors':len(anchors),
  'base_candidate':'ff3_explained_high','diagnostic_windows':[60,120,252],'platform_compute_spent':0})
if __name__=='__main__':main()
