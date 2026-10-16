"""Fixed earnings surprise / half-year adjusted-profit value recipes."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source13-20261012'
SUE='quant/2024年度精选策略2/82.可转债知识总结.txt'
CYCLE='quant/2021年度精选策略/26.稳定高回报周期股策略2.txt'
SPECS=[{'key':k,'name':n,'source_paths':[s],'formula':fo,'gated':gate,
 'fidelity':'PIT source accounting atom adaptation, quarterly value ordering causal; source execution/universe removed'}
 for k,n,s,fo,gate in [
 ('revenue_sue12','12季度收入惊喜',SUE,'(single_quarter_revenue0-mean(prior12))/std(prior12)',False),
 ('revenue_seasonal_sue12','季节调整收入惊喜',SUE,'(revenue0-mean(revenue4,8,12))/std(revenue4,8,12); seasonality adaptation',False),
 ('adjusted_profit_value_rank','扣非盈利成长×估值',CYCLE,'rank(sum(q_dtprofit0..3)/mv)+.5rank(sum0..1/sum2..3)+.3rank(sum0..1/sum4..5)',False),
 ('adjusted_profit_value_gate','低PE应收效率内盈利成长',CYCLE,'same score; PE0..20, debt/assets<.9, receivable turnover>6 or<=0',True)]]

def build(fin,cap):
 def f(ep,c,i=0):return fin[f'{ep}.{c}.q{i}']
 # Reported income revenue is YTD: independently isolate each quarter.
 quarters=[]
 reportq=fin['income.__quarter__.q0']
 for i in range(13):
  qn=((reportq-i-1)%4)+1
  quarters.append(np.where(qn==1,f('income','revenue',i),f('income','revenue',i)-f('income','revenue',i+1)))
 prior=np.stack(quarters[1:]);current=quarters[0]
 sue=q.ratio(current-prior.mean(axis=0),prior.std(axis=0,ddof=1))
 seasonal=np.stack([quarters[i] for i in [4,8,12]])
 ss=q.ratio(current-seasonal.mean(axis=0),seasonal.std(axis=0,ddof=1))
 profits=[f('fina_indicator','q_dtprofit',i) for i in range(6)]
 p0=profits[0]+profits[1];p1=profits[2]+profits[3];p2=profits[4]+profits[5]
 ttm=p0+p1;ep=q.ratio(ttm,cap*10000)
 score=q.rank(ep)+.5*q.rank(q.ratio(p0,p1))+.3*q.rank(q.ratio(p0,p2))
 ar=sum(f('balancesheet','accounts_receiv',i)+f('balancesheet','notes_receiv',i)-f('balancesheet','adv_receipts',i) for i in range(4))/4
 art=q.ratio(f('income','revenue_ttm'),ar)
 pe=q.ratio(cap*10000,ttm);lev=q.ratio(f('balancesheet','total_liab'),f('balancesheet','total_assets'))
 gate=(pe>0)&(pe<20)&(lev<.9)&((art>6)|(art<=0))
 return [sue,ss,score,np.where(gate,score,np.nan)]

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,fields=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 fin=q.financial_snapshot(grid,stocks)
 fin.update(pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source7-20261012/corrected_fields/financial_signal_snapshots.pkl'))
 oldout,oldfields=q.OUT,q.FIN_FIELDS
 try:
  q.OUT=OUT;q.FIN_FIELDS={'income':['revenue'],'fina_indicator':['q_dtprofit']}
  fin.update(q.financial_snapshot(grid,stocks,lags=14))
 finally:q.OUT=oldout;q.FIN_FIELDS=oldfields
 fin['income.__quarter__.q0']=q.income_report_quarters(grid,stocks)
 vals=build(fin,fields['cap'][pos]);checks=[]
 for stop in [31,77]:
  cut=build({k:v[:stop] for k,v in fin.items()},fields['cap'][pos[:stop]])
  for a,b in zip(vals,cut):np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-5,atol=1e-5)
  checks.append({'test':'prefix_build','stop':stop,'passed':True})
 run(OUT,SPECS,vals,calendar,stocks,fields,checks,{'proxy':'Tushare q_dtprofit for source adjusted profit; revenue surprise for CB equity ranking extracted to fullA',
  'quarterly':'YTD revenue differenced only across within-year preceding quarter;14contiguous quarterly snapshot lags',
  'source_omissions':'CB premium/bond liquidity, industry/ST/listing-age exclusions, RSRS, source5stock concentration',
  'gated_benchmark':'narrow qualification subset, not directly comparable to whole coverage'})
if __name__=='__main__':main()
