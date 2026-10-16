"""Credit bargaining power, cash quality, low-risk quality: fixed source adaptations."""
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source7-20261012'
FIELDS={'balancesheet':['acct_payable','adv_receipts','prepayment'],
 'cashflow':['n_cashflow_act','c_pay_acq_const_fiolta','stot_out_inv_act']}
PATHS=[
 'quant/2021年度精选策略/10.多因子选股.txt',
 'quant/2024年度精选策略1/39.大资金优质股策略，总收益1217%！无小市值因子！.txt',
 'quant/2024年度精选策略2/90.大师策略——柯林·麦克连成长价值优势投资法.txt',
 'quant/2023年度精选策略/79.过滤两个因子，12年15倍的roa选股500指数增强.txt',
 'quant/聚宽2025年精选/23大盘择时，逻辑简单.txt',
 'quant/2023年度精选策略/65.PB-POE+双均线--加入jq以来第一个成功的交易策略 一.txt']

def spec(key,name,src,formula,gated=False):
 return {'key':key,'name':name,'source_paths':[PATHS[i] for i in src],'formula':formula,
 'fidelity':'fullA_atom_or_equalrank_adaptation_PIT_proxy; original execution/universe omitted','gated':gated}
SPECS=[
 spec('credit_aparp','供应链议价能力APARP',[0],'(acct_payable+adv_receipts)/(accounts_receiv+prepayment), denominator>0'),
 spec('credit_margin_rank','供应链议价×毛利质量',[0],'rank(APARP)+rank(grossprofit_margin)'),
 spec('fcf_capex_roe_rank','自由现金流×ROE',[1,2],'rank((TTM_CFO-TTM_capex)/total_mv)+rank(qROE)'),
 spec('fcf_invest_roe_size_neutral','投资现金流口径×ROE中性化',[1],'sum(zscore(logcap residual of winsor5_93(FCF_invest_yield,qROE))); industry neutralization omitted'),
 spec('roa_turncv_bias_rank','盈利×换手稳定×短期乖离',[3],'rank(ROA)+rank(-STD20(turn)/MEAN20(turn))+rank(1-C/MA10)'),
 spec('roa_turncv_bias_gate','低换手波动低乖离池内ROA',[3],'ROA in lower50% turn_CV then lower50% BIAS10',True),
 spec('bm_roa_lowbeta_rank','低估值×盈利×低市场风险',[4],'rank(BM)+rank(ROA)+rank(-CAPM_beta252_equalweight_fullA)'),
 spec('roe_minus_pb','ROE减PB',[5],'qROE-PB; positive book equity')]

def build(fin,f,pos,beta):
 def g(ep,col,i=0):return fin[f'{ep}.{col}.q{i}']
 cap=f['cap'][pos];mv=cap*10000
 denom=g('balancesheet','accounts_receiv')+g('balancesheet','prepayment')
 ap=q.ratio(g('balancesheet','acct_payable')+g('balancesheet','adv_receipts'),np.where(denom>0,denom,np.nan))
 gp=g('fina_indicator','grossprofit_margin');roe=g('fina_indicator','q_roe');roa=g('fina_indicator','roa')
 ocf=g('cashflow','n_cashflow_act_ttm');capex=g('cashflow','c_pay_acq_const_fiolta_ttm')
 yield1=q.ratio(ocf-capex,mv);yield2=q.ratio(ocf-g('cashflow','stot_out_inv_act_ttm'),mv)
 neutral=np.zeros_like(cap)
 for term in [yield2,roe]:
  z=pd.DataFrame(np.where(cap>0,term,np.nan));z=z.clip(lower=z.quantile(.05,axis=1),upper=z.quantile(.93,axis=1),axis=0).to_numpy()
  res=np.full_like(z,np.nan)
  for i in range(len(z)):
   ok=np.isfinite(z[i])&(cap[i]>0)
   if ok.sum()<100:continue
   design=np.column_stack([np.ones(ok.sum()),np.log(cap[i,ok])]);y=z[i,ok]
   res[i,ok]=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
  neutral+=q.zscore(res)
 cv=q.ratio(q.rolling(f['turnover'],20,'std'),q.rolling(f['turnover'],20))[pos]
 bias=(q.ratio(f['close'],q.rolling(f['close'],10))-1)[pos]
 lowcv=q.rank(np.where(cap>0,cv,np.nan))<=.5
 lowbias=q.rank(np.where(lowcv,bias,np.nan))<=.5
 bm=q.ratio(g('balancesheet','total_hldr_eqy_exc_min_int'),mv);bm=np.where(bm>0,bm,np.nan)
 return [ap,q.rank(ap)+q.rank(gp),q.rank(yield1)+q.rank(roe),neutral,
  q.rank(roa)+q.rank(-cv)+q.rank(-bias),np.where(lowcv&lowbias,roa,np.nan),
  q.rank(bm)+q.rank(roa)+q.rank(-beta[pos]),roe-q.ratio(np.ones_like(bm),bm)]

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market()
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 fin=q.financial_snapshot(grid,stocks)
 fin.update(pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source6-20261012/financial_signal_snapshots.pkl'))
 oldout,oldfields=q.OUT,q.FIN_FIELDS
 cache_out=OUT/'corrected_fields';cache_out.mkdir(exist_ok=True)
 try:q.OUT=cache_out;q.FIN_FIELDS=FIELDS;fin.update(q.financial_snapshot(grid,stocks))
 finally:q.OUT=oldout;q.FIN_FIELDS=oldfields
 r=q.ratio(f['close'],q.delay(f['close']))-1
 m=pd.DataFrame(np.where(f['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
 mf=pd.DataFrame(np.broadcast_to(m[:,None],r.shape))
 beta=q.ratio(pd.DataFrame(r).rolling(252).cov(mf).to_numpy(),mf.rolling(252).var().to_numpy())
 vals=build(fin,f,pos,beta);checks=[]
 for stop in [31,77,len(grid)-9]:
  cut=build({k:v[:stop] for k,v in fin.items()},f,pos[:stop],beta)
  for s,a,b in zip(SPECS,vals,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-5,rtol=1e-5)
   checks.append({'key':s['key'],'test':'prefix_signal_recompute','passed':True,'stop':stop})
 # Causal market inputs recomputed on a stock subset to test rolling boundaries.
 ids=np.flatnonzero(np.isfinite(f['close'][-600:]).all(axis=0))[:5]
 for stop in [1500,len(calendar)-32]:
  for n in [10,20]:
   field='close' if n==10 else 'turnover'
   np.testing.assert_allclose(q.rolling(f[field][:,ids],n)[:stop],q.rolling(f[field][:stop,ids],n),equal_nan=True)
 checks.append({'test':'rolling_input_truncation','passed':True})
 expected=(fin['balancesheet.acct_payable.q0']+fin['balancesheet.adv_receipts.q0'])/(fin['balancesheet.accounts_receiv.q0']+fin['balancesheet.prepayment.q0'])
 valid=np.isfinite(vals[0]);np.testing.assert_allclose(vals[0][valid],expected[valid],rtol=1e-5)
 checks.append({'test':'independent_APARP_definition','passed':True})
 run(OUT,SPECS,vals,calendar,stocks,f,checks,{'proxy':'reported Tushare fields; quarterly ROE, beta252 fullA proxy not HS300; turn_CV20 proxy',
  'source_omissions':'industry neutralization, original index pools, hard financial/macro/trading gates; no dividend',
  'FCF':'two explicit distinct definitions; no missing capex treated as zero','gated_benchmark':'gate candidate not fullA-comparable'})
if __name__=='__main__':main()
