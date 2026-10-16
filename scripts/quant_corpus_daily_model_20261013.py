"""Fixed daily return-model and complete smooth-trend source conditions."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
from quant_corpus_sweep_20261013 import ols_slope
MODEL='quant/2022年度精选策略/22.多因子系列：基于多因子框架的收益预测模型.txt'
TREND='quant/2023年度精选策略/14.2020年 267%年化 13%回撤 上涨趋势策略修改版.txt'
CAPM='quant/2023年度精选策略/11.致敬市场--5 定投ETF之躺平赢.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source48-20261013'
SPECS=[
 spec('turn_share_ewls20_predict','换手股本二因子衰减预测',MODEL,'CS medianMAD1 clipping and zscore(turnover,totalshares), daily no-intercept OLS on nextday known return; weights last20=0.95^age; current feature dot weighted betas',
      'proxy: fullA replaces ST-filtered source; shares=total_mv/raw_close in vendor万股 units; raw close only reconstructs shares, qfq used for all labels; medianMAD1.4826 scale1 preprocessing proxy'),
 spec('smooth_trend120_full_margin','120日平滑趋势完整技术余量',TREND,'min((slope120/intercept120)/.005-1,R2_120/.8-1,1-MAX30(H)/(1.1C),1-VMA7/(1.5VMA180),1-C/500)',
      'proxy: full active conjunction of source slope/R2/drawdown/volume/price constraints, continuous fullA margin; not gated-R2 concentrated execution or HS300 history'),
 spec('capm240_log_alpha','240日对数CAPM历史alpha',CAPM,'24000*(MEAN240(logret)-beta240*MEAN240(fullA_active_equalweight_logret)); beta=cov/market_var',
      'proxy: stocks replace ETF universe and fullA equalweight return replaces source399300 index; alpha stock adaptation, source beta0.9..1.1/delta10/liquidity gates omitted; not platform internal alpha'),
]

def clip_z(x,active):
 a=np.where(active,x,np.nan).astype(float);median=np.nanmedian(a,axis=1)[:,None]
 mad=np.nanmedian(np.abs(a-median),axis=1)[:,None]*1.4826
 return q.zscore(np.clip(a,median-mad,median+mad))

def values(f):
 c=f['close'];active=f['cap']>0
 shares=q.ratio(f['cap'],f['raw_close']);x=np.stack([clip_z(f['turnover'],active),clip_z(shares,active)],axis=-1)
 r=q.ratio(c,q.delay(c))-1;b=np.full((len(c),2),np.nan)
 for t in range(len(c)-1):
  valid=np.isfinite(x[t]).all(axis=1)&np.isfinite(r[t+1])&active[t]&active[t+1]
  if valid.sum()<100:continue
  b[t]=np.linalg.lstsq(x[t,valid],r[t+1,valid],rcond=None)[0]
 # b[t-1] becomes known only at t close; all20coefficients have mature labels.
 history=np.stack([q.delay(b,k) for k in range(1,21)])
 weights=np.array([.95**k for k in range(20)])[:,None,None]
 beta=(history*weights).sum(axis=0)/weights.sum()
 score=np.sum(x*beta[:,None,:],axis=-1)
 n=120;slope=ols_slope(c,n);intercept=q.rolling(c,n)-slope*(n-1)/2
 r2=q.ratio(slope*slope*((n*n-1)/12),q.rolling(c,n,'var')*((n-1)/n))
 trend=np.min(np.stack([q.ratio(q.ratio(slope,intercept),.005)-1,q.ratio(r2,.8)-1,
  1-q.ratio(q.rolling(f['high'],30,'max'),1.1*c),1-q.ratio(q.rolling(f['volume'],7),1.5*q.rolling(f['volume'],180)),1-c/500]),axis=0)
 lr=np.log(q.ratio(c,q.delay(c)))
 market=pd.DataFrame(np.where(active,lr,np.nan)).mean(axis=1).to_numpy()
 m=pd.DataFrame(np.broadcast_to(market[:,None],lr.shape));stock=pd.DataFrame(lr)
 cov=stock.rolling(240).cov(m).to_numpy();beta=q.ratio(cov,m.rolling(240).var().to_numpy())
 alpha=24000*(q.rolling(lr,240)-beta*m.rolling(240).mean().to_numpy())
 return [score,trend,alpha]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='fixed source before outcomes',platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:256] for k,v in f.items()};full=values(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=values({k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-5,atol=1e-5)
   assert np.isfinite(b).any();checks.append(dict(key=sp['key'],test='daily_prefix_reconstruct_and_refit_OLS',stop=stop,passed=True))
 v=values(f)
 run(OUT,SPECS,[a[pos] for a in v],cal,stocks,f,checks,dict(fidelity='explicit source adaptations; no platform validation',statistics='exploratory no independent OOS',causality='OLS beta at feature date tau uses target tau+1, weighted forecast uses only tau<=t-1'))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED48',flush=True)
if __name__=='__main__':main()
