"""Primary daily correlation audit for the survivor equal-rank stability score."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_source10_20261012 import one
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-style-stability-validation-20261012'
def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market();q.dates_all=calendar
 days=np.flatnonzero((calendar>='20210907')&(calendar<='20260907'))
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid);ix=calendar[days].get_indexer(grid)
 style=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-style-risk-validation-20261012/daily_style.pkl')
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks);ta=q.daily_pit_field('balancesheet','total_assets',calendar,stocks)
 cache=OUT/'low_ff3_daily.pkl'
 if cache.exists():low=pd.read_pickle(cache)
 else:
  low=np.full_like(style,np.nan)
  for i,t in enumerate(days):
   low[i]=one(f,eq,roe,ta,t,window=120)[1];low[i,~(f['cap'][t]>0)]=np.nan
  pd.to_pickle(low,cache)
 low=np.where(f['cap'][days]>0,low,np.nan)
 score=q.rank(style)+q.rank(low)
 saved=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source15-20261012/signal_panels.pkl')['panels']['style_stable_equalrank'].to_numpy()
 np.testing.assert_allclose(score[ix],saved,equal_nan=True,atol=1e-6)
 c=f['close'];cap=f['cap'];turn=f['turnover'];r=q.ratio(c,q.delay(c))-1
 def sub(z):return np.where(cap[days]>0,z[days],np.nan)
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
 anchors={'B01|SIZE-ONLY':sub(-cap),'B02|TURN-BIAS21/504':sub(1-q.ratio(q.rolling(turn,21),q.rolling(turn,504))),
 'B03|RET40':sub(-(q.ratio(c,q.delay(c,40))-1)),'B04|DD120':sub(1-q.ratio(c,q.rolling(c,120,'max'))),
 'B08|BM_latest_proxy':sub(q.ratio(eq,cap*10000)),'B09|DD60':sub(1-q.ratio(c,q.rolling(c,60,'max'))),
 'N01|REV20':sub(-(q.ratio(c,q.delay(c,20))-1)),'N08|TURN_STD21':sub(-q.rolling(turn,21,'std')),
 'N09|MAX21':sub(-q.rolling(r,21,'max')),'N16|SKEW60':sub(-q.rolling(r,60,'skew')),
 'N27|ROE_latest_proxy':sub(roe),'known|LOW_IVOL120':sub(-iv),
 'known|LOW_FF3_IVOL120':low,'new|FF3_STYLE_RATIO120':style,
 'unassigned|H03-IMPACT60':sub(q.ratio(q.rolling(q.ratio(f['high']-f['low'],q.delay(c)+1e-6),60,'sum'),q.rolling(f['amount'],60,'sum')+1))}
 res=dual_residual(score,anchors['B01|SIZE-ONLY'],anchors['N01|REV20']);rows=[]
 for form,x in [('raw',score),('size_reversal_rank_residual',res)]:
  for name,y in anchors.items():rows.append({'candidate':'style_stable_equalrank','form':form,'anchor':name,
   'scope':'every_trading_day_cross_sectional_spearman_mean',**rho_details(x,y)})
 df=pd.DataFrame(rows);df.to_csv(OUT/'daily_old_anchor_correlations.csv',index=False)
 df.assign(abs_rho=df.rho.abs()).sort_values('abs_rho',ascending=False).groupby('form').head(3).to_csv(OUT/'nearest_daily_top3.csv',index=False)
 q.dump(OUT/'verification.json',[{'test':'daily_rebuild_equals_frozen_signal_grid','passed':True},
  {'test':'causality','passed':True,'evidence':'source12/14 full-array truncation and source15 per-date composite truncation'}])
 q.dump(OUT/'completion.json',{'completed':True,'daily_days':len(days),'anchors':len(anchors),'platform_compute_spent':0,
  'scope':'daily anchors subset;54stored-grid references supplementary; incomplete master universe, new cluster not certified'})
if __name__=='__main__':main()
