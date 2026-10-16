"""Source EMA/ATR helpers and literal multi-MA eligibility, no fake limits."""
import json,sys
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/45.[原创]价值投资+期货对冲V4.0,无惧市场大跌.txt'
B='quant/量化策略/量化策略/龙头追涨策略2026/02涨停板多头策略-25年负-47.txt'
C='quant/量化策略/量化策略/龙头追涨策略2026/02涨停板多头策略-优化版v1.0.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source120-20261013'
SPECS=[
 spec('hedge45_ema5_2_priority_state','对冲源码五二EMA优先级状态',A,'-1 if C<EMA5 else +1 if C>EMA2 else0',
 'proxy stock extension of indexscalar, source11:15currentpartialday -> completedclose, EMA standardrecursive seeded byfirstNmean. PreviousEMA variables calculated but unused; not futures hedge or dividend ranking.'),
 spec('hedge45_lowatr20_50_ratio','对冲源码二十五十ATR收缩比例',A,'-ATR20/ATR50, Wilder true-range seededNmean',
 'proxy NEW continuous dimensionless extension of ATR20-ATR50 sign selecting1.5vs1contractallocation. Vendor ATRnotbyteequivalent, no IC contracts/margin/roll/shortaccount.'),
 spec('hedge45_longatr5_boundary_margin','对冲源码五日高点ATR距离',A,'(C-MAX5(H)t-1)/ATR20(t)',
 'proxy NEW continuous long-stop margin (source exit below MAX5H-5ATR20), no position-gated stop or futures trading claim. Completed bars tclose under nextclose label.'),
 spec('leader02_multima_lowcap_partial','多均线源码资格小市值部分腿',B,'-totalMV(t) where C>MA5>MA10>MA20>MA60 at t-1',
 'proxy actual size ranking conditioned on exact MA eligibility; actualyesterdaylimit omitted, sourcepriorcap adapted signaldaytotalMV. No fake high_limit or minute stop/fill; sourceactual stop10%/profit10%, contrary prose5/15.'),
 spec('leader02_recent3calendar_early_lowcap','多均线三自然日初成小市值',C,'-totalMV(t) where prioralignment AND NOT alignment(at lastsession<=priorDate-3calendarDays) AND prior4RET<.20 AND priorC/MA20<1.10',
 'proxy actualactiveis_recent_multima andcheck_early_stage, NOT golden-cross helper (dormant). 5priceobservations=4intervals; 3calendar days not3sessions; missing actualpriorlimit/ST/IPO90/intraday buys.'),
 spec('leader02_recent_volume19_open_partial','多均线初成十九日均量开盘交集',C,'same recentearlysize where .5<=lag1V/MEAN19V(t-20..t-2)<=3 AND O(t)/C(t-1)<=1.05',
 'proxy literal iloc[-20:-1]19bars, not advertised20; openingknown evaluated aftertclose. Omitted abs(C-high_limit)/high_limit<.001 andcurrentminuteprice<=.98todaylimit; no invented limit thresholds. Actual stop5% andprofit20/25 not header.')]
for sp in SPECS[3:]:sp['gated']=True

def seeded_smooth(x,n,alpha):
 out=np.full(x.shape,np.nan);count=np.zeros(x.shape[1],int);total=np.zeros(x.shape[1]);state=np.full(x.shape[1],np.nan)
 for t,row in enumerate(x):
  good=np.isfinite(row);reset=~good;count[reset]=0;total[reset]=0;state[reset]=np.nan
  initial=good&(count<n);total[initial]+=row[initial];count[initial]+=1
  seed=initial&(count==n);state[seed]=total[seed]/n
  active=good&~initial;state[active]=(1-alpha)*state[active]+alpha*row[active]
  out[t]=state
 return out

def values(f,cal,pos):
 c=f['close'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float);prev=np.vstack([np.full((1,c.shape[1]),np.nan),c[:-1]])
 e5=seeded_smooth(c,5,2/6);e2=seeded_smooth(c,2,2/3)
 state=np.where(np.isfinite(e5)&np.isfinite(e2)&np.isfinite(c),np.where(c<e5,-1,np.where(c>e2,1,0)),np.nan)
 tr=np.maximum(h-l,np.maximum(abs(h-prev),abs(l-prev)))
 a20=seeded_smooth(tr,20,1/20);a50=seeded_smooth(tr,50,1/50)
 ratio=np.divide(-a20,a50,out=np.full_like(c,np.nan),where=a50>0)
 peak=pd.DataFrame(h).rolling(5).max().shift(1).to_numpy();margin=np.divide(c-peak,a20,out=np.full_like(c,np.nan),where=a20>0)
 df=pd.DataFrame(c);ma=[df.rolling(n).mean().to_numpy() for n in [5,10,20,60]]
 align=(c>ma[0])&(ma[0]>ma[1])&(ma[1]>ma[2])&(ma[2]>ma[3]);valid=np.isfinite(c)&np.isfinite(ma[3])
 prior=pos-1;old=cal.get_indexer(cal[prior]-pd.Timedelta(days=3),method='pad');pastvalid=old>=0
 old=np.maximum(old,0)
 ret4=df/df.shift(4)-1;bias=df/pd.DataFrame(ma[2])-1
 early=(ret4.to_numpy()[prior]<.20)&(bias.to_numpy()[prior]<.10)
 recent=align[prior]&~align[old]&valid[prior]&valid[old]&pastvalid[:,None]&early
 cap=f['cap'][pos].astype(float)
 v=pd.DataFrame(f['volume'].astype(float));den=v.rolling(19).mean().shift(1);vr=(v/den.where(den>0)).to_numpy()[prior]
 op=f['open'][pos]/c[prior];volgate=(vr>=.5)&(vr<=3)&(op<=1.05)
 return [state[pos],ratio[pos],margin[pos],np.where(align[prior]&valid[prior],-cap,np.nan),np.where(recent,-cap,np.nan),np.where(recent&volgate,-cap,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literalEMA5/2,ATR20/50,5highboundary,MA5/10/20/60,3calendar,4interval,.20/.10,19vol,.5/3/1.05')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,cal,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},cal[:stop],pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_and_calendar_prefix_replay',passed=True))
 # Independent library agreement checks on complete contiguous histories.
 sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
 import talib
 observations=0
 for j in range(64):
  good=np.isfinite(sf['close'][:,j])&np.isfinite(sf['high'][:,j])&np.isfinite(sf['low'][:,j]);ids=np.flatnonzero(good)
  if not len(ids):continue
  start=ids[0]
  if not good[start:].all():continue
  c=sf['close'][start:,j].astype(float);h=sf['high'][start:,j].astype(float);l=sf['low'][start:,j].astype(float)
  e5=talib.EMA(c,5);e2=talib.EMA(c,2);a20=talib.ATR(h,l,c,20);a50=talib.ATR(h,l,c,50)
  for i in [35,79]:
   t=pos[i]-start
   if t<60:continue
   ref=-1 if c[t]<e5[t] else(1 if c[t]>e2[t] else 0)
   np.testing.assert_allclose(full[0][i,j],ref,atol=1e-8)
   np.testing.assert_allclose(full[1][i,j],-a20[t]/a50[t],atol=1e-8)
   np.testing.assert_allclose(full[2][i,j],(c[t]-h[t-5:t].max())/a20[t],atol=1e-8);observations+=1
 assert observations>0
 checks.append(dict(test='independent_TALib_EMA_ATR_and_prior5bound',observations=observations,passed=True))
 # Three calendar days before Monday selects the preceding Friday.
 testcal=pd.DatetimeIndex(['20260108','20260109','20260112']);assert testcal.get_indexer([pd.Timestamp('20260112')-pd.Timedelta(days=3)],method='pad')[0]==1
 checks.append(dict(test='literal_calendar_not_session_lookback',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]});vals=values(f,cal,pos)
 q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source daily helpers only; no original dividends/index/futures/limits/fills'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED120',flush=True)
if __name__=='__main__':main()
