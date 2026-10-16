"""Two frozen style-risk stability refinements; no weight/threshold search."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source15-20261012'
SOURCE='quant/2022年度精选策略/98.复现东方证券研报--特质波动率因子研究.txt'
SPECS=[{'key':k,'name':n,'source_paths':[SOURCE],'formula':f,'gated':False,
 'fidelity':'causal refinement of source model residual risk and source-derived partial explained variance; fixed equal ranks'}
 for k,n,f in [('style_stable_equalrank','风格解释力×低特质风险等权','rank(1-IVOL_FF3^2/IVOL_CAPM^2)+rank(-IVOL_FF3)'),
 ('style_stable_rankproduct','风格解释力×低特质风险乘积','rank(1-IVOL_FF3^2/IVOL_CAPM^2)*rank(-IVOL_FF3)')]]
def main():
 calendar,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 explained=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source14-20261012/signal_panels.pkl')['panels']['ff3_explained_high'].to_numpy()
 low=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source12-20261012/signal_panels.pkl')['panels']['fixed_ff3_ivol120'].to_numpy()
 a,b=q.rank(explained),q.rank(low);vals=[a+b,a*b];checks=[]
 for stop in [31,77]:
  aa,bb=q.rank(explained[:stop]),q.rank(low[:stop])
  for x,y in zip(vals,[aa+bb,aa*bb]):np.testing.assert_allclose(x[:stop],y,equal_nan=True)
  checks.append({'test':'prefix_rank_composite','stop':stop,'passed':True})
 run(OUT,SPECS,vals,calendar,stocks,f,checks,{'proxy':'inherits source12/14 model field/formation contracts',
  'selection':'follow-up after raw style risk survived; counted as2additional exploratory recipes',
  'mechanism':'require explainable style component and limit remaining stock-specific volatility',
  'weights':'equalrank sum or rankproduct fixed; no coefficient tuning'})
if __name__=='__main__':main()
