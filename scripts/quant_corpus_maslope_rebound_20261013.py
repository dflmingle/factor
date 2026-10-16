"""Fixed source MA20 no-intercept slope and disclosed daily rebound helpers."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/50.新策略，一种新思路，超额376%！.txt'
B='quant/2024年度精选策略2/33.胜率88.9%之君正集团策略-大阳分歧反包.txt'
C='quant/2024年度精选策略2/37.三阳三阴战法.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source125-20261013'
SPECS=[
 spec('growth50_ma20_slope_nointercept_prior','二十点均线首点归零无截距斜率',A,'round(100*dot(arange20,prior20MA20-firstMA20)/sum(arange20**2),1)',
 'proxy NEW ranking of original eligibility slope>=-2 for nonholdings, literal40priorprices rolling20 iloc20: gives20MA20points. Priceunit source retained, not normalized regression with intercept. Original4growthforecast fields/turnovervolatility/circMV/EPS and monthlyholdings absent; PEG result overwritten by next turnover filter on ms_list.'),
 spec('rebound33_bigyang_wick_oldhigh_margin','反包源码大阳上影老高点余量',B,'min(.976-prevC/prevH,prevC/prev2C-1,prevC/prevO-1.08,prevC/MAX150C_ending_tminus10-1.2)',
 'proxy NEW continuous margin of actual previousday price shape; exact150bars end t-10 (t-9..t-1 ninebars excluded). Missing previous4bars C>.98*actualhigh_limit qualification/ST, listing1080 calculatedunused. No fabricated10percent limit or original0955tick/fills.'),
 spec('rebound33_price_shape_partial','反包价形交集上影余量',B,'-(prevH-prevC)/prevH WHERE literal rebound33 price shape',
 'proxy NEW within-shape ranking, original has no economicrank. Omitted prior4limitbar restriction, ST and realtime+6percent/current>prevH/O>.96prevC; canonical10day not intraday state.'),
 spec('rebound33_buy6_open96_margin','反包前高六点开盘约束余量',B,'min(C/prevH-1,C/prevC-1.06,O/prevC-.96)',
 'proxy NEW completedclose extension of original before0955 tickbuy guard; misses exact intradaysequence and bigyang/fourlimit context. Continuous standalone helper only.'),
 spec('candle37_threeup_threeother_event','最近三阳前段三根非阳事件',C,'lag1(I(lastC>lastO AND SUM3(C>=O)==3 AND SUM6(C>O)==3))',
 'proxy sourceactual>=3 includesdoji, >6countsstrict. Name three-yin does not imply strict allfirst3bear: recentdoji permit different pattern. Original30bar earlierpeak/380baroldpeak/multilimit counts/range/valley and minute threshold omitted; binaryties audited, no whole strategyclaim.')]
SPECS[2]['gated']=True

def values(f,pos):
 c=f['close'].astype(float);h=f['high'].astype(float);o=f['open'].astype(float)
 ma=pd.DataFrame(c).rolling(20).mean().to_numpy();out=[np.full((len(pos),c.shape[1]),np.nan) for _ in SPECS];xx=np.arange(20);den=xx@xx
 for i,t in enumerate(pos):
  a=ma[t-20:t];s=np.sum((a-a[0])*xx[:,None],axis=0)/den*100
  out[0][i]=np.array([round(float(z),1) if np.isfinite(z) else np.nan for z in s])
  old=np.max(c[t-159:t-9],axis=0)
  terms=np.stack([.976-c[t-1]/h[t-1],c[t-1]/c[t-2]-1,c[t-1]/o[t-1]-1.08,c[t-1]/old-1.2]);margin=np.min(terms,axis=0)
  out[1][i]=margin;out[2][i]=np.where(margin>0,-(h[t-1]-c[t-1])/h[t-1],np.nan)
  out[3][i]=np.minimum.reduce([c[t]/h[t-1]-1,c[t]/c[t-1]-1.06,o[t]/c[t-1]-.96])
  valid=np.isfinite(c[t-6:t]).all(axis=0)&np.isfinite(o[t-6:t]).all(axis=0)
  event=(c[t-1]>o[t-1])&((c[t-3:t]>=o[t-3:t]).sum(axis=0)==3)&((c[t-6:t]>o[t-6:t]).sum(axis=0)==3)
  out[4][i]=np.where(valid,event.astype(float),np.nan)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='fixedsource40/20nointercept round1,150endingt-10,.976/1.08/1.2,6/96,3/6literal')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for s,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=s['key'],test='rawdaily_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   a=sf['close'][t-40:t,j].astype(float)
   if np.isfinite(a).all():
    arr=pd.Series(a).rolling(20).mean().iloc[20:].to_numpy();xx=np.arange(len(arr));ref=round(float(np.linalg.lstsq(xx[:,None],arr-arr[0],rcond=None)[0][0])*100,1)
    np.testing.assert_allclose(full[0][i,j],ref)
   a=sf['close'][t-6:t,j];b=sf['open'][t-6:t,j]
   if np.isfinite(a).all() and np.isfinite(b).all():
    ref=float(a[-1]>b[-1] and sum(a[-3:]>=b[-3:])==3 and sum(a>b)==3);np.testing.assert_allclose(full[4][i,j],ref)
 checks.append(dict(test='independent40price_rolling20_iloc20_lstsq_and_literal_doji_boundaries',passed=True))
 q.dump(OUT/'source_evidence.json',{s:read_text(q.ROOT/s) for s in [A,B,C]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='sourcehelpers and disclosed NEW stockranking, not original strategy'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED125',flush=True)
if __name__=='__main__':main()
