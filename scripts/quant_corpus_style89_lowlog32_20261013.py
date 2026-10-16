"""Source fixed LOW89 trend, OHLC50 allocation and five-leg log weight variant."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/27.根据大小盘相对强弱选择合适的板块股票进行交易.txt'
B='quant/2024年度精选策略1/32.非线性市值（非小市值）组合4只.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source126-20261013'
SPECS=[
 spec('style27_loglow89_r2_prior','八十九低价点趋势拟合度',A,'lag1(expm1(250*OLS89(logLOW).slope)*R2)',
 'proxy NEW fullAstock extension of source twoINDEX LOW89style selector, not CLOSE89. ActualPITindex/size-vs-value regime/holdings not reproduced; no newclusterclaim from horizonvariation.'),
 spec('style27_ohlc50_lowz_daily','五十根OHLC均价低标准分',A,'-populationZ50(mean(O,H,L,C))',
 'proxy NEW ranking of source position scalar p=(meancurrentOHLC-MEAN50barmean)/popSTD50. daily include_now fullclose replaces11:15 partialdailybar; no missingdate/extra metadata columns invented, canonicallabel1; NOT original riskpositiontest.'),
 spec('style27_ohlc50_allocation_state','五十根均价仓位状态适配',A,'1.5 if populationZ50<-2 else .5 if Z>2 else1',
 'proxy NEW ranking of source only-on-newposition multiplier, not economic alpha originally; strict +/-2 retained, threewayties audited; positionbase depends rank g.stock_num and remainingcash unimplemented.'),
 spec('nonlinear32_lowlog_price2_volume1_ret1','名义非线性市值剩余量价腿',B,'-2log(qfqC)-log(lag1SUM5V)-log(C/lag60C)',
 'proxy NEW explicit size terms removed to inspect source weights[2,1,1,4,4], minconstants cancel crosssectionorder. Source minutequote and summedprior5volume adapted tclose; actual fixed top70percent largecap and FScore>7 unavailableissue omitted; not entirestrategy or true non_linear_size field.'),
 spec('nonlinear32_lowlog_full_totalmv_proxy','非线性标题五腿总市值代理',B,'-8log(total_mv)-2log(qfqC)-log(lag1SUM5V)-log(C/lag60C)',
 'proxy both totalMV and unavailablecircMV explicitly maptotal_mv, not byteequivalent; pure log linear-combination despite title. Monthlylargest70percent positivefinancial/FScore>7 and minuteinputs omitted; source shrinking4count possibly0divide preserved in evidence notfactor.')]

def values(f,pos):
 c=f['close'].astype(float);mean=sum(f[k].astype(float) for k in ['open','high','low','close'])/4
 df=pd.DataFrame(mean);z=((df-df.rolling(50).mean())/df.rolling(50).std(ddof=0)).to_numpy()[pos]
 state=np.where(np.isfinite(z),np.where(z<-2,1.5,np.where(z>2,.5,1)),np.nan)
 v=pd.DataFrame(f['volume'].astype(float)).rolling(5).sum().shift(1).to_numpy()[pos]
 with np.errstate(divide='ignore',invalid='ignore'):
  non=-2*np.log(c[pos])-np.log(v)-np.log(c[pos]/c[pos-60]);full=non-8*np.log(f['cap'][pos])
 return [trend_at(f['low'].astype(float),pos-1,89),-z,state,non,full]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourcefixedLOW89,OHLC50popstd,+/-2,actual[2,1,1,4,4] beforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for s,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=s['key'],test='rawOHLCvolume_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   arr=np.stack([sf[k][t-49:t+1,j].astype(float) for k in ['high','low','open','close']],axis=1).mean(axis=1)
   if np.isfinite(arr).all() and arr.std()>0:np.testing.assert_allclose(full[1][i,j],-(arr[-1]-arr.mean())/arr.std(),atol=1e-8)
   arr=sf['low'][t-89:t,j].astype(float)
   if np.isfinite(arr).all() and arr.std()>0:
    y=np.log(arr);x=np.arange(89);s,b=np.polyfit(x,y,1);r2=1-((y-s*x-b)**2).sum()/((len(y)-1)*y.var(ddof=1));np.testing.assert_allclose(full[0][i,j],np.expm1(250*s)*r2,atol=1e-7)
 checks.append(dict(test='independent_source_OHLC50_populationZ_and_LOW89_polyfit',passed=True))
 q.dump(OUT/'source_evidence.json',{s:read_text(q.ROOT/s) for s in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='explicit minute/INDEX/fullA/sourcefield proxies'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED126',flush=True)
if __name__=='__main__':main()
