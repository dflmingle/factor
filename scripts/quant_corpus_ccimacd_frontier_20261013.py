"""Distinct5/15/7 fortybar MACD source and CCI DOWN-cross, with source gates."""
import json,sys
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
MACD='quant/2022年度精选策略/83.穿越十年牛熊：沪深300成分股配合macd的价投择时策略.txt'
CCI='quant/2023年度精选策略/88.韶华研究之二，顺势而为，年化140.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source73-20261013'
SPECS=[spec('macd5_15_7_source40_qualified','MACD五十五七源码四十条合格低值',MACD,
 '-100*(SUM15(hist)-abs(SUM5(hist))) on SUM15hist>0,COUNT(hist[-15:-5]>0)>4,SUM5hist>0,msig>2;hist=TA-Lib MACD(40close,5,15,7)',
 'proxy: exact stock macdSignal40 resets retained, actual stockselection msig>2 THEN ascending order, PE queried but unused. Source globalindex msig0 gate andHS300/3stockportfolio omitted; fullA qualified benchmark; absolutepricehist source units, missingclose remainsNaN'),
 spec('cci14_downcross_margin','CCI十四下穿负一百余量',CCI,
 'min(lag1CCI14+100,-CCI14-100)/100',
 'proxy: continuous source strict DOWN-cross(CCIprev>-100,CCInow<-100), TA-Lib typicalpriceCCI14 dailyclose implementation; source industry/CYF/valuation gates omitted and continuous scores replaceevent'),
 spec('cci14_downcross_range100_qualified','CCI下穿负百高振幅源码合格部分',CCI,
 'MAX100(high)/MIN100(low) on CCIprev>-100,CCInow<-100,C<300,PE>=0,PB>=1,C/lag99C>=.73',
 'proxy: exact available source dailyprice/financial gates and raw range100 ranking; fullA replacesHS300, industry list/industryrange/CYF thresholds missing explicitly omitted; retained stock source range without industry normalization, not complete strategy')]
SPECS[0]['gated']=True;SPECS[2]['gated']=True

def macd(c,pos):
 out=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  for j in range(c.shape[1]):
   y=c[t-39:t+1,j].astype(float)
   if not np.isfinite(y).all():continue
   hist=talib.MACD(y,fastperiod=5,slowperiod=15,signalperiod=7)[-1]
   total=np.sum(hist[-15:]);recent=np.sum(hist[-5:]);msig=100*(total-abs(recent))
   if total>0 and np.sum(hist[-15:-5]>0)>4 and recent>0 and msig>2:out[i,j]=-msig
 return out

def cci_daily(f):
 out=np.full(f['close'].shape,np.nan)
 for j in range(out.shape[1]):
  h,l,c=[f[k][:,j].astype(float) for k in ['high','low','close']];good=np.isfinite(h)&np.isfinite(l)&np.isfinite(c);edges=np.flatnonzero(np.diff(np.r_[False,good,False]))
  for a,b in zip(edges[::2],edges[1::2]):
   if b-a>=14:out[a:b,j]=talib.CCI(h[a:b],l[a:b],c[a:b],timeperiod=14)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source directions resets and exact available gates fixed beforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks);c=f['close'];small={k:v[:,:256] for k,v in f.items()};ci=cci_daily(small);m=macd(small['close'],pos);checks=[]
 for stop in [1200,len(cal)-31]:
  use=pos<stop;cut=cci_daily({k:v[:stop] for k,v in small.items()});np.testing.assert_allclose(ci[:stop],cut,equal_nan=True,atol=1e-8);np.testing.assert_allclose(m[use],macd(small['close'][:stop],pos[use]),equal_nan=True,atol=1e-8)
  checks.append(dict(test='price_prefix_and_MACD40_reset_source_recompute',passed=True,stop=stop,finite_events=int(np.isfinite(m[use]).sum())))
 for t in pos[::31]:
  for j in range(16):
   hist=(small['high'][t-13:t+1,j].astype(float)+small['low'][t-13:t+1,j]+small['close'][t-13:t+1,j])/3
   if np.isfinite(hist).all():
    den=.015*np.mean(np.abs(hist-hist.mean()));ref=(hist[-1]-hist.mean())/den if den>0 else 0
    np.testing.assert_allclose(ci[t,j],ref,rtol=1e-6,atol=1e-6)
 checks.append(dict(test='independent_CCI_typicalprice_meanabsolute_deviation',passed=True))
 ci=cci_daily(f);last=q.delay(ci);margin=np.minimum(last+100,-ci-100)/100;range100=q.ratio(q.rolling(f['high'],100,'max'),q.rolling(f['low'],100,'min'))
 cap=f['cap'][pos]*10000;pe=q.ratio(cap,fin['income.n_income_attr_p_ttm.q0']);pb=q.ratio(cap,fin['balancesheet.total_hldr_eqy_exc_min_int.q0'])
 good=(last[pos]>-100)&(ci[pos]<-100)&(c[pos]<300)&(pe>=0)&(pb>=1)&((q.ratio(c,q.delay(c,99)))[pos]>=.73)
 vals=[macd(c,pos),margin[pos],np.where(good,range100[pos],np.nan)];q.dump(OUT/'qualification_coverage.json',{s['key']:np.isfinite(v).sum(axis=1).tolist() for s,v in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source available dailykernel/gates with explicit omissions',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED73',flush=True)
if __name__=='__main__':main()
