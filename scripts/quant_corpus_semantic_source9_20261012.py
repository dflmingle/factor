"""Frozen equal-rank adaptations of source low idio risk with quality/value legs."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012'
LOW='quant/2024年度精选策略2/67.三因子策略年化21%简单多因子策略框架.txt'
VALUE='quant/2023年度精选策略/24.ROE+PB模型的优化.txt'
QUALITY='quant/聚宽2025年精选/24大容量低回撤价值投资-排除小市值因子.txt'
ROA='quant/2023年度精选策略/79.过滤两个因子，12年15倍的roa选股500指数增强.txt'
SPECS=[{'key':key,'name':name,'formula':formula,'source_paths':sources,
 'fidelity':'research adaptation from source legs; equal ranks frozen, not original strategy','gated':False}
 for key,name,formula,sources in [
 ('idio_bm_rank','低特质波动×账面价值','rank(-IVOL120)+rank(BM)',[LOW,VALUE]),
 ('idio_ep_rank','低特质波动×盈利估值','rank(-IVOL120)+rank(EP_TTM)',[LOW,QUALITY]),
 ('idio_roe_rank','低特质波动×季度盈利质量','rank(-IVOL120)+rank(qROE)',[LOW,VALUE]),
 ('idio_quality_value_rank','低特质波动×质量价值','rank(-IVOL120)+rank(ROIC)+rank(grossmargin)+rank(-PS_TTM)',[LOW,QUALITY]),
 ('idio_reversal_product','低特质波动×20日反转','rank(-IVOL120)*rank(-return20)',[LOW,ROA]),
 ('idio_roa_turn_bias_rank','盈利×低风险×换手×乖离','rank(-IVOL120)+rank(ROA)+rank(-turnCV20)+rank(-BIAS10)',[LOW,ROA])]]

def ivol(f):
 r=q.ratio(f['close'],q.delay(f['close']))-1
 m=pd.DataFrame(np.where(f['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
 mf=pd.DataFrame(np.broadcast_to(m[:,None],r.shape))
 cov=pd.DataFrame(r).rolling(120).cov(mf).to_numpy()
 return np.sqrt(np.maximum(q.rolling(r,120,'var')-q.ratio(cov**2,mf.rolling(120).var().to_numpy()),0))

def build(fin,f,pos,iv):
 def g(ep,col):return fin[f'{ep}.{col}.q0']
 cap=f['cap'][pos];mv=cap*10000
 def rank(x):return q.rank(np.where((cap>0)&np.isfinite(x),x,np.nan))
 low=rank(-iv[pos]);bm=q.ratio(g('balancesheet','total_hldr_eqy_exc_min_int'),mv)
 bm=rank(np.where(bm>0,bm,np.nan));ep=rank(q.ratio(g('income','n_income_ttm'),mv))
 roe=rank(g('fina_indicator','q_roe'));roic=rank(g('fina_indicator','roic'))
 gp=rank(g('fina_indicator','grossprofit_margin'));rv=g('income','revenue_ttm')
 ps=rank(-q.ratio(mv,np.where(rv>0,rv,np.nan)))
 reversal=rank(-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos])
 cv=q.ratio(q.rolling(f['turnover'],20,'std'),q.rolling(f['turnover'],20))[pos]
 bias=(q.ratio(f['close'],q.rolling(f['close'],10))-1)[pos]
 return [low+bm,low+ep,low+roe,low+roic+gp+ps,low*reversal,
  low+rank(g('fina_indicator','roa'))+rank(-cv)+rank(-bias)]

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 fin=q.financial_snapshot(grid,stocks)
 fin.update(pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source6-20261012/financial_signal_snapshots.pkl'))
 iv=ivol(f);vals=build(fin,f,pos,iv);checks=[]
 old=pd.read_pickle(q.OUT/'signal_panels.pkl')['panels']['capm_residual_vol120_low'].to_numpy()
 new=np.where(f['cap'][pos]>0,-iv[pos],np.nan)
 np.testing.assert_allclose(new,old,equal_nan=True,rtol=1e-4,atol=1e-6)
 checks.append({'test':'IVOL_saved_atom_grid_consistency','passed':True})
 for stop in [31,77]:
  cut=build({k:v[:stop] for k,v in fin.items()},f,pos[:stop],iv)
  for s,a,b in zip(SPECS,vals,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6)
   checks.append({'test':'prefix_signal_build','key':s['key'],'stop':stop,'passed':True})
 ids=np.flatnonzero(np.isfinite(f['close'][-700:]).all(axis=0))[:6]
 small={k:v[:,ids] for k,v in f.items()};alliv=ivol(small)
 for stop in [1500,len(calendar)-31]:
  np.testing.assert_allclose(alliv[:stop],ivol({k:v[:stop] for k,v in small.items()}),equal_nan=True,atol=1e-6,rtol=1e-5)
 checks.append({'test':'CAPM_prefix_recompute','passed':True})
 run(OUT,SPECS,vals,calendar,stocks,f,checks,{'scope':'refinement of previously found low IVOL; no claim of new cluster',
  'proxy':'CAPM equalweight fullA residual volatility120, PIT financial TTM fields',
  'weights':'equal cross-sectional ranks; no size term; no weight optimization'})
 pd.to_pickle(iv,OUT/'ivol_daily.pkl')
if __name__=='__main__':main()
