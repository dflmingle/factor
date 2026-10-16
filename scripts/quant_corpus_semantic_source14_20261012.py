"""Separate style risk explained by the source FF models from absolute volatility."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_source10_20261012 import one,SOURCE
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source14-20261012'
SPECS=[{'key':f'{model}_explained_{side}','name':f'{model.upper()}风格解释比例{side}',
 'formula':f'{sign}*(1-(IVOL_{model}/IVOL_CAPM)^2), fixed120',
 'source_paths':[SOURCE],'gated':False,'fidelity':'variance decomposition research adaptation of source CAPM/FF3/FF5; both directions fixed'}
 for model in ['ff3','ff5'] for side,sign in [('high',1),('low',-1)]]
def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks);ta=q.daily_pit_field('balancesheet','total_assets',calendar,stocks)
 raw=[np.full((len(pos),len(stocks)),np.nan,np.float32) for _ in range(3)]
 for i,t in enumerate(pos):
  result=one(f,eq,roe,ta,t,window=120)
  for j in range(3):raw[j][i]=result[j]
 vals=[]
 for i in [1,2]:
  explained=1-q.ratio(raw[i]**2,np.where(raw[0]**2>1e-12,raw[0]**2,np.nan))
  vals.extend([explained,-explained])
 known=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source12-20261012/signal_panels.pkl')['panels']
 for j,k in enumerate(['fixed_ff3_ivol120','fixed_ff5_ivol120']):
  active=np.where(f['cap'][pos]>0,raw[j+1],np.nan)
  np.testing.assert_allclose(active,known[k],equal_nan=True,rtol=1e-5,atol=1e-6)
 finite=np.isfinite(vals[0]);assert np.all(vals[0][finite]>=-1e-5) and np.all(vals[0][finite]<=1+1e-5)
 run(OUT,SPECS,vals,calendar,stocks,f,[{'test':'prior_frozen_model_consistency_and_nested_variance_bounds','passed':True}],
  {'proxy':'source fixed start cap-weighted factor portfolios, total_mv, reported PIT accounting fields',
   'economic_test':'style-explained proportion vs unexplained risk; ratio removes absolute volatility scale',
   'directions':'source defines residual risk only; decomposition both signs counted as independent exploratory specifications',
   'window':'120 frozen; no scale/threshold optimization'})
if __name__=='__main__':main()
