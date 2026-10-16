"""Fixed factor-model risk variants and source covariance/value stability legs."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_source10_20261012 import one,SOURCE
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source12-20261012'
COV='quant/2023年度精选策略/91.致敬市场--4 解析细节.txt'
VAL='quant/2024年度精选策略2/49.修改成一创版本.txt'
SPECS=[{'key':key,'name':name,'source_paths':src,'formula':formula,'gated':False,
 'fidelity':'fixed fullA risk model/value adaptation; source runtime, original pools and neutralization not reproduced'}
 for key,name,src,formula in [
 ('fixed_ff3_ivol120','三因子低特质波动120',[SOURCE],'-STD(OLS residual(RM,SMB,HML),120)'),
 ('fixed_ff5_ivol120','五因子低特质波动120',[SOURCE],'-STD(OLS residual(RM,SMB,HML,RMW,CMA),120)'),
 ('market_cov240_low','低市场收益协方差240',[COV],'-COV(return_stock,return_fullA,240)'),
 ('cov240_bm_rank','低系统风险×账面价值',[COV],'rank(-COV240)+rank(BM)'),
 ('turncv_bm_rank','换手相对波动×账面价值',[VAL],'rank(-STD20(turn)/MEAN20(turn))+rank(BM); value leg replaces PEG explicitly')]]
def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks);ta=q.daily_pit_field('balancesheet','total_assets',calendar,stocks)
 ff=[np.full((len(pos),len(stocks)),np.nan,np.float32) for _ in range(2)]
 for i,t in enumerate(pos):
  results=one(f,eq,roe,ta,t,window=120)
  ff[0][i]=results[1];ff[1][i]=results[2]
 r=q.ratio(f['close'],q.delay(f['close']))-1;m=pd.DataFrame(np.where(f['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
 cov=pd.DataFrame(r).rolling(240).cov(pd.DataFrame(np.broadcast_to(m[:,None],r.shape))).to_numpy()
 bm=q.ratio(eq[pos],f['cap'][pos]*10000);bm=np.where(bm>0,bm,np.nan)
 cv=q.ratio(q.rolling(f['turnover'],20,'std'),q.rolling(f['turnover'],20))[pos]
 vals=ff+[-cov[pos],q.rank(-cov[pos])+q.rank(bm),q.rank(-cv)+q.rank(bm)]
 checks=[]
 for i in [31,77]:
  t=pos[i];stop=t+1
  cut=one({k:v[:stop] for k,v in f.items()},eq[:stop],roe[:stop],ta[:stop],t,window=120)
  for j in range(2):np.testing.assert_allclose(ff[j][i],cut[j+1],equal_nan=True,atol=1e-6)
  checks.append({'test':'FF3_FF5_prefix_recompute','passed':True,'signal':str(grid[i])})
 run(OUT,SPECS,vals,calendar,stocks,f,checks,{'proxy':'total_mv, fullA market vs source index, reported PIT ROE/BM',
  'risk_window':'120 fixed from existing low-IVOL implementation;504 already tested separately; no window optimization',
  'formation':'t-120 fixed cap weighted thirds; annual asset lag252, common accounting coverage',
  'weights':'equal ranks; no smallcap sorting'})
if __name__=='__main__':main()
