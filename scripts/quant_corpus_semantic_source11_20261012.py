"""R&D and margin-stability source adaptations, frozen before outcomes."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source11-20261012'
RD='quant/2020年度精选策略/03 机器学习多因子策略.txt'
MS='quant/2023年度精选策略/78.EPS+MS因子的大盘蓝筹策略.txt'
LOW='quant/2024年度精选策略2/67.三因子策略年化21%简单多因子策略框架.txt'
SPECS=[{'key':key,'name':name,'source_paths':sources,'formula':formula,'gated':False,
 'fidelity':'fixed equal-rank source-mechanism adaptation; margin stability six-reported-quarter proxy, not exact vendor field'}
 for key,name,formula,sources in [
 ('idio_rd_assets_rank','低特质波动×研发强度','rank(-IVOL120)+rank(PIT_rd_exp/assets)',[RD,LOW]),
 ('idio_rd_market_rank','低特质波动×研发估值','rank(-IVOL120)+rank(PIT_rd_exp/total_mv)',[RD,LOW]),
 ('margin_stable_eps_rank','毛利稳定×每股盈利','rank(-std(GPM_q0..5)/mean(GPM_q0..5))+rank(EPS_TTM)',[MS]),
 ('idio_margin_stable_rank','低特质波动×毛利稳定','rank(-IVOL120)+rank(-std(GPM_q0..5)/mean(GPM_q0..5))',[LOW,MS])]]
def build(fin,cap,iv):
 def g(ep,col,i=0):return fin[f'{ep}.{col}.q{i}']
 def rank(x):return q.rank(np.where((cap>0)&np.isfinite(x),x,np.nan))
 low=rank(-iv);rd=g('fina_indicator','rd_exp');assets=g('balancesheet','total_assets')
 margins=np.stack([g('fina_indicator','grossprofit_margin',i) for i in range(6)])
 mean=margins.mean(axis=0)
 stability=-q.ratio(margins.std(axis=0,ddof=1),np.where(mean>0,mean,np.nan))
 eps=q.ratio(g('income','n_income_attr_p_ttm'),g('balancesheet','total_share')*10000)
 return [low+rank(q.ratio(rd,assets)),low+rank(q.ratio(rd,cap*10000)),rank(stability)+rank(eps),low+rank(stability)]
def main():
 calendar,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 fin=q.financial_snapshot(grid,stocks);iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')[pos]
 vals=build(fin,f['cap'][pos],iv);checks=[]
 for stop in [31,77]:
  cut=build({k:v[:stop] for k,v in fin.items()},f['cap'][pos[:stop]],iv[:stop])
  for s,a,b in zip(SPECS,vals,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6)
   checks.append({'key':s['key'],'test':'prefix_recompute','passed':True})
 run(OUT,SPECS,vals,calendar,stocks,f,checks,{'proxy':'rd_exp proxy for source capitalized development expenditure; reported YTD GPM six-quarter stability proxy',
  'source_omissions':'final largecap ranking, source index, hard EPS/stability gates, ML prediction and timing',
  'weights':'fixed equal ranks, no tuning','scope':'new combinations, no automatic new-cluster claim'})
if __name__=='__main__':main()
