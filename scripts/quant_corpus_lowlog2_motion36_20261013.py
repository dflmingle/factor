"""Source-fixed alternative log weights and motion/RSRS exits; offline only."""
import argparse,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/2.“7年40倍”策略扩容到50只.txt'
B='quant/聚宽2025年精选/36快过年了。不想呆在小市值的，可以拿这个策略躲一躲.txt'
BASE='proxy fullAstock adaptation of fourETF/globalHS300 kernel, completedbar, no ETFportfolio claim. Holding score*1.04, 60minuteMA20 intradayexit and source [code,score,adr] tuple passed to security iterators not implemented. RSRS rolling600 seed proxy, no initial skipped-slope claim. '
SPECS145=[
 spec('lowlog2_sizefree_weights1682','五腿打分第二组去市值量价',A,'-1.6log(C)-.8log(lag1SUM5V)-2log(C/lag60C)',
 'proxy NEW size-free partial of literal weights[1,1,1.6,.8,2], distinct from source32[2,1,1,4,4]. Minima constants cancel ordering; prior1200minuteV replaced prior5dailyV and currentminuteprice by completedqfqC. Original PB/inc_return/revenuegrowth/netprofitgrowth gates and smallest100selection not reproduced; not whole strategy.'),
 spec('lowlog2_totalmv_weights1682_proxy','五腿打分第二组总市值代理',A,'-2log(total_mv)-1.6log(C)-.8log(lag1SUM5V)-2log(C/lag60C)',
 'proxy NEW literal weights with both original totalMV/circMV mapped explicitly to total_mv for canonical diagnostic. Same daily/minute substitutions, no qualification or holdings claim. Not a true nonlinear_size field or independent cluster.'),
 spec('motion36_bias90_20_nonaccelerating','乖离动量排除快速加速',B,'bias90_normalized_OLS20*10000 WHERE diff1(score)<=19 AND ret1<=.048',
 BASE+'Exact signed change>19 (not abs), lastreturn>4.8percent exits. Original applies exit to selectedETF; NEW perstock qualification diagnostic. Source ETF bias kernel already tested83; only jointmotiongate new.')]
SPECS145[-1]['gated']=True
SPECS146=[
 spec('motion36_rsrs_slope8_nonsell','RSRS八点斜率联合非卖出',B,'I(rsrs18_z600_R2>-.68 AND NOT(OLS8(rsrs).slope<0 AND rsrs>0))',
 BASE+'Exact strict>-.68; positiveRSRSwithnegative8slopeSELL takes priority. No MA guard. Binary ties audited.'),
 spec('motion36_bias_joint_rsrs_motion','乖离动量与RSRS和加速联合',B,'bias90_normalized_OLS20*10000 WHERE diff1score<=19 AND ret1<=.048 AND rsrs>-.68 AND NOT(slope8rsrs<0 AND rsrs>0)',
 BASE+'Literal joint two exits and RSRS guard; NEW eachstock adaptation of original globalgate and topETF exit, qualification benchmark disclosed.')]
SPECS146[-1]['gated']=True

def bias_series(c):
 d=pd.DataFrame(c);b=(d/d.rolling(90).mean()).to_numpy();x=np.arange(20)-9.5
 # Rolling covariance is algebraically OLS numerator; divide by first bias.
 score=np.full(c.shape,np.nan)
 for k in range(19,len(c)):
  a=b[k-19:k+1];score[k]=(x[:,None]*a).sum(axis=0)/(x*x).sum()/a[0]*10000
 return score

def rsrs_series(f):
 h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float))
 cv=h.rolling(18).cov(l,ddof=0);vl=l.rolling(18).var(ddof=0);vh=h.rolling(18).var(ddof=0)
 beta=cv/vl;z=(beta-beta.rolling(600).mean())/beta.rolling(600).std(ddof=0)
 rs=(z*cv**2/(vl*vh)).replace([np.inf,-np.inf],np.nan).to_numpy()
 slope=np.full(rs.shape,np.nan);x=np.arange(8)-3.5
 for k in range(7,len(rs)):slope[k]=(x[:,None]*rs[k-7:k+1]).sum(axis=0)/(x*x).sum()
 return rs,slope

def rsrs_allow(rs,slope):
 return np.isfinite(rs)&np.isfinite(slope)&(rs>-.68)&~((slope<0)&(rs>0))

def values(f,pos,batch):
 c=f['close'].astype(float);score=bias_series(c);ret=c[pos]/c[pos-1]-1
 motion=np.isfinite(score[pos])&np.isfinite(score[pos-1])&np.isfinite(ret)&(score[pos]-score[pos-1]<=19)&(ret<=.048)
 if batch==145:
  v=pd.DataFrame(f['volume'].astype(float)).rolling(5).sum().shift(1).to_numpy()[pos]
  with np.errstate(divide='ignore',invalid='ignore'):
   part=-1.6*np.log(c[pos])-.8*np.log(v)-2*np.log(c[pos]/c[pos-60]);whole=part-2*np.log(f['cap'][pos])
  return [part,whole,np.where(motion,score[pos],np.nan)]
 rs,sl=rsrs_series(f);allow=rsrs_allow(rs[pos],sl[pos]);valid=np.isfinite(rs[pos])&np.isfinite(sl[pos])
 return [np.where(valid,allow.astype(float),np.nan),np.where(allow&motion,score[pos],np.nan)]

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',type=int,choices=[145,146],required=True);batch=p.parse_args().batch
 specs=SPECS145 if batch==145 else SPECS146;out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{batch}-20261013';out.mkdir(exist_ok=True)
 plan=dict(specs=specs,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='actualsourceweights/gatesbeforeoutcomes; no tuning')
 fp=out/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (out/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:32] for k,v in f.items()};full=values(sf,pos,batch);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n],batch)
  for sp,a,b in zip(specs,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 score=bias_series(sf['close'].astype(float))
 for i in [35,79]:
  t=pos[i]
  for j in range(32):
   a=pd.Series(sf['close'][t-108:t+1,j].astype(float));b=(a/a.rolling(90).mean()).iloc[-20:].to_numpy()
   if np.isfinite(b).all():np.testing.assert_allclose(score[t,j],np.polyfit(np.arange(20),b/b[0],1)[0]*10000,atol=1e-7)
 checks.append(dict(test='independent_literal_bias90_last20_polyfit',passed=True))
 if batch==145:
  toy=np.array([[2,5,10,30,1.2],[3,4,8,40,.9]],float);w=np.array([1,1,1.6,.8,2])
  original=(np.log(toy.min(axis=0)/toy)*w).sum(axis=1);ranker=-np.log(toy)@w
  np.testing.assert_allclose(original[0]-original[1],ranker[0]-ranker[1],atol=1e-10)
  checks.append(dict(test='literal_source_log_min_constants_cancel',passed=True))
 else:
  rr=np.array([-.68,-.679,0.,.5,.5,np.nan]);ss=np.array([1.,1.,-1.,-1.,0.,1.]);np.testing.assert_array_equal(rsrs_allow(rr,ss),[False,True,True,False,True,False])
  rs,sl=rsrs_series(sf)
  for i in [35,79]:
   t=pos[i]
   for j in range(8):
    slopes=[];r2last=np.nan
    for end in range(t-599,t+1):
     lo=sf['low'][end-17:end+1,j].astype(float);hi=sf['high'][end-17:end+1,j].astype(float)
     if not np.isfinite(lo).all() or not np.isfinite(hi).all() or lo.std()==0:slopes.append(np.nan);continue
     slopes.append(np.polyfit(lo,hi,1)[0]);r2last=np.corrcoef(lo,hi)[0,1]**2
    slopes=np.array(slopes)
    if np.isfinite(slopes).all():np.testing.assert_allclose(rs[t,j],(slopes[-1]-slopes.mean())/slopes.std()*r2last,atol=1e-5)
    if np.isfinite(rs[t-7:t+1,j]).all():np.testing.assert_allclose(sl[t,j],np.polyfit(np.arange(8),rs[t-7:t+1,j],1)[0],atol=1e-8)
  checks.append(dict(test='independent600_OLS18_popstd_R2_and8slope_strict_branch',passed=True))
 q.dump(out/'source_evidence.json',{src:read_text(q.ROOT/src) for src in sorted(set(s['source_paths'][0] for s in specs))})
 run(out,specs,values(f,pos,batch),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='sourcefixed mathemathics independently implemented, daily/stock proxies explicit'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 if batch==146:tie_diagnostic(out,cal,stocks,f)
 audit(out,cal,stocks,f);q.dump(out/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED',batch,flush=True)
if __name__=='__main__':main()
