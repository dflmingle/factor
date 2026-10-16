"""Source83 actual Boll60 squeeze and asymmetric MACD/TRIX signal clauses."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2023年度精选策略/83.韶华研究之一，布林突破+均线金叉，四年五倍.txt'
ETF='quant/2021年度精选策略/25.基本不耍六毛的ETF轮动策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source76-20261013'
SPECS=[
 spec('boll60_squeeze_breakout_margin','六十日窄布林突破余量',SOURCE,
 'min(1-(4*populationSTD60(C)/MA60(C))/.1,C/(MA60(C)+2*populationSTD60(C))-1)',
 'proxy: continuous source Boll60 width<=.1 and C>=upper conjunction; vendor BB warmup unavailable, rolling populationSTD. FullA qfq atom; CYF/top10floatowners/index-state/execution omitted explicitly'),
 spec('boll60_macdtrix_event_qualified','窄布林MACD或TRIX源码事件',SOURCE,
 'C/(MA60+2STD60)-1 on width<=.1, C>=upper, MACD signal1 OR TRIX signal1; EMA12/26/9 and TRIX12/MA9',
 'proxy: qualification stock atom, sparse-event benchmark; EMA pandas causal warmup not vendor-identical. Source TRIX pre-cross clause is impossible (TRIX<=MA but MA-TRIX<=-.03), retained literally. Full source portfolio history/10day dedup/listing/ST/industry/index-state omitted'),
 spec('etf13_momentum_ma13_stockproxy','十三条历史价格动量均线约束',ETF,
 'C/lag13C-1 on C/lag13C-1>=.001 and C/lag1MA13(C)-1>=0',
 'proxy: stock dailyclose replaces current11:30 ETF price; prior13dailycloses retained separately from current price. Indexvolume emotiongate and ETF/LOF/monthly liquidity/moneyfund allocation unavailable, omitted; not original ETF strategy return')]
for sp in SPECS[1:]:sp['gated']=True

def details(f):
 c=f['close'].astype(float);frame=pd.DataFrame(c)
 def ema(x,n):return pd.DataFrame(x).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy()
 ma=q.rolling(c,60);std=frame.rolling(60).std(ddof=0).to_numpy();upper=ma+2*std;width=q.ratio(4*std,ma)
 dif=ema(c,12)-ema(c,26);dea=ema(dif,9);md=dea-dif;oldmd=q.delay(md)
 triple=ema(ema(ema(c,12),12),12);trix=100*(q.ratio(triple,q.delay(triple))-1);matrix=q.rolling(trix,9);td=matrix-trix;oldtd=q.delay(td)
 macd=((dif<=dea)&(md<oldmd)&(md<=.05))|((dif>=dea)&(q.delay(dif)<=q.delay(dea)))
 trixsignal=((trix<=matrix)&(td<oldtd)&(td<=-.03))|((trix>=matrix)&(q.delay(trix)<=q.delay(matrix)))
 valid=np.isfinite(np.stack([width,upper,dif,dea,oldmd,trix,matrix,oldtd])).all(axis=0)
 breakout=q.ratio(c,upper)-1; margin=np.minimum(1-width/.1,breakout)
 event=np.where(valid&(width<=.1)&(c>=upper)&(macd|trixsignal),breakout,np.nan)
 mom=q.ratio(c,q.delay(c,13))-1;bias=q.ratio(c,q.delay(q.rolling(c,13)))-1
 etf=np.where((mom>=.001)&(bias>=0),mom,np.nan)
 return [margin,event,etf],dict(width=width,upper=upper,dif=dif,dea=dea,md=md,trix=trix,matrix=matrix,td=td,valid=valid)

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='actual available technical clauses fixed before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:256] for k,v in f.items()};whole,d=details(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut,_=details({k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6,rtol=1e-6)
   checks.append(dict(key=sp['key'],test='daily_price_prefix_recompute',stop=stop,nonempty=int(np.isfinite(b).sum()),passed=True))
 checked=0
 for t in [1200,1800,len(cal)-1]:
  for j in range(256):
   if not d['valid'][t,j]:continue
   dif,dea,md,trix,matrix,td=[d[k][t,j] for k in ['dif','dea','md','trix','matrix','td']]
   mflag=0
   if dif<=dea and md<d['md'][t-1,j] and md<=.05:mflag=1
   elif dif>=dea and d['dif'][t-1,j]<=d['dea'][t-1,j]:mflag=1
   elif dif<=dea and d['dif'][t-1,j]>=d['dea'][t-1,j]:mflag=-1
   tflag=0
   if trix<=matrix and td<d['td'][t-1,j] and td<=-.03:tflag=1
   elif trix>=matrix and d['trix'][t-1,j]<=d['matrix'][t-1,j]:tflag=1
   elif trix<=matrix and d['trix'][t-1,j]>=d['matrix'][t-1,j]:tflag=-1
   ok=d['width'][t,j]<=.1 and small['close'][t,j]>=d['upper'][t,j] and (mflag==1 or tflag==1)
   assert np.isfinite(whole[1][t,j])==ok
   c=small['close'][t-59:t+1,j].astype(float)
   np.testing.assert_allclose(d['width'][t,j],4*c.std(ddof=0)/c.mean(),atol=1e-7)
   literal=small['close'][t,j]/small['close'][t-13,j]-1
   bias=small['close'][t,j]/small['close'][t-13:t,j].mean()-1
   if np.isfinite(literal) and np.isfinite(bias):
    np.testing.assert_allclose(whole[2][t,j],literal if literal>=.001 and bias>=0 else np.nan,equal_nan=True,atol=1e-7)
   checked+=1
 checks.append(dict(test='independent_scalar_original_branch_priority_Boll_populationSTD_and_prior13closes',observations=checked,passed=True))
 vals,_=details(f);vals=[v[pos] for v in vals]
 q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='explicit stock adaptations and event qualification; not original portfolios',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED76',flush=True)

if __name__=='__main__':main()
