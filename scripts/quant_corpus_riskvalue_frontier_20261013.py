"""Literal price-level correlation and inverse regression orientation, plus value."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
CORR='quant/2022年度精选策略/92.黄金避险有效？量化实测黄金资产真实收益.txt'
BETA='quant/2022年度精选策略/39.个股择时有效？因子选股+双均线择时效果初步尝试.txt'
OP='quant/2021年度精选策略/8.因子分析 营业利润TTM.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source55-20261013'
SPECS=[
 spec('market_price_corr90_high','九十日价格水平高市场相关',CORR,'corr90(stock_close,market_close), HIGH preferred',
 'proxy: literal source compares PRICE LEVELS, not returns, and sorts DESC not ASC; causal fullAeqweight qfq market close replaces HS300; ROE/PBtop100 gate omitted'),
 spec('market_on_stock_beta252','市场对个股反向回归斜率',BETA,'cov252(stock_ret,market_ret)/var252(stock_ret)',
 'proxy: dormant helper get_df_beta regresses rm_rf ~ ri_rf and prefers HIGH, not ordinary CAPM stock_on_market beta; allAeqweight qfq market replacesZZ800; 4%constant rf irrelevant to intercept slope, no ST/pause/index filtering'),
 spec('value_ratio_z3_source','源码三估值截面标准分',BETA,'-(CSz(PB)+CSz(PE)+CSz(PS))/3',
 'proxy: active get_df_value exact zscore equalweights, source does not require ratiospositive; PIT parentNI_TTM/equity/totalrevenue_TTM and total_mv replace vendorvaluation; fullA replacesZZ800, individualMA5/60 position management omitted'),
 spec('operatingprofit_ttm_logsize_residual','营业利润TTM对数市值残差',OP,'CSz(residual(winsorize_CS2.5/97.5percentile(operate_profit_TTM) ~ const+log(total_mv)))',
 'proxy: source preprocessing size/industry neutralization adapted to size-only because historical industry dummies unavailable; no industrymedian missingfill or industry result selection; no implied exact vendor operating_profit_TTM equivalence'),
]

def rolling_corr(x,y,n):
 a=pd.DataFrame(x);b=pd.Series(y)
 # Matched full windows; pandas population-vs-sample conventions cancel.
 return a.rolling(n).corr(b).to_numpy(dtype=np.float32)

def risk_values(f):
 c=f['close'].astype(float);r=q.ratio(c,q.delay(c))-1
 mr=np.nanmean(np.where(f['cap']>0,r,np.nan),axis=1);mr[~np.isfinite(mr)]=np.nan
 m=np.full(len(c),np.nan);m[0]=1
 for t in range(1,len(c)):m[t]=m[t-1]*(1+mr[t]) if np.isfinite(mr[t]) else m[t-1]
 corr=rolling_corr(c,m,90)
 cov=pd.DataFrame(r).rolling(252).cov(pd.Series(mr)).to_numpy(dtype=np.float32)
 beta=q.ratio(cov,q.rolling(r,252,'var'))
 return corr,beta

def financial_values(fin,cap):
 mv=cap*10000;eq=fin['balancesheet.total_hldr_eqy_exc_min_int.q0'];ni=fin['income.n_income_attr_p_ttm.q0'];rv=fin['income.total_revenue_ttm.q0']
 value=-sum(q.zscore(q.ratio(mv,a)) for a in [eq,ni,rv])/3
 op=fin['income.operate_profit_ttm.q0'];out=np.full(op.shape,np.nan)
 for i in range(len(op)):
  good=np.isfinite(op[i])&(cap[i]>0)
  if good.sum()<100:continue
  y=op[i,good].astype(float);lo,hi=np.quantile(y,[.025,.975]);y=np.clip(y,lo,hi)
  x=np.column_stack([np.ones(good.sum()),np.log(cap[i,good])]);res=y-x@np.linalg.lstsq(x,y,rcond=None)[0]
  if res.std()>1e-7:out[i,good]=(res-res.mean())/res.std(ddof=1)
 return value,out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='literal source directions frozen before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks)
 small={k:v[:,:16] for k,v in f.items()};risk=risk_values(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=risk_values({k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS[:2],risk,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-6,atol=1e-6);checks.append(dict(key=sp['key'],test='daily_prefix_market_index_and_feature_recompute',stop=stop,passed=True))
 # Independent covariance orientation: source y=market, x=stock.
 rr=q.ratio(small['close'],q.delay(small['close']))-1;mr=np.nanmean(np.where(small['cap']>0,rr,np.nan),axis=1)
 for j in range(16):
  xx=rr[-252:,j];yy=mr[-252:];good=np.isfinite(xx)&np.isfinite(yy)
  if good.all() and xx.std()>1e-8:np.testing.assert_allclose(risk[1][-1,j],np.linalg.lstsq(np.column_stack([np.ones(252),xx]),yy,rcond=None)[0][1],rtol=1e-5,atol=1e-6)
  elif good.all():assert not np.isfinite(risk[1][-1,j])
 checks.append(dict(key=SPECS[1]['key'],test='independent_market_on_stock_OLS_orientation',passed=True))
 fv=financial_values(fin,f['cap'][pos])
 for n in [35,79]:
  cut=financial_values({k:v[:n] for k,v in fin.items()},f['cap'][pos[:n]])
  for sp,a,b in zip(SPECS[2:],fv,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-6,atol=1e-6);checks.append(dict(key=sp['key'],test='prefix_formula_previously_raw_PIT_verified_base_financial_cache',passed=True))
 fullrisk=risk_values(f)
 run(OUT,SPECS,[fullrisk[0][pos],fullrisk[1][pos],*fv],cal,stocks,f,checks,dict(statistics='exploratory no independent OOS',fidelity='allA full source atoms with explicitly missingindustry/market proxies',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED55',flush=True)
if __name__=='__main__':main()
