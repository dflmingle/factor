"""Unrun completed-bar and eligibility kernels, preserving missing event data."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/12用子账户模拟多策略分仓.txt'
B='quant/2021年度精选策略/50.昨日炸板股策略.txt'
C='quant/2020年度精选策略/10 追三板策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source117-20261013'
SPECS=[
 spec('subportfolio12_dualtrend25_200_priorclose','子账户前收盘短长趋势差',A,'trend25t-1 - trend200t-1/6',
 'proxy known source83currentbar variant, actualattribute_history priorbar. ETF4spreadgate .1..15 and top1 absent, stockextension not originalsubaccountportfolio.'),
 spec('subportfolio12_beta18_20lowerband','子账户十八对二十RSRS余量',A,'beta18(t-1)-MEAN229(beta20 endingt-231..t-3)+2popSTD229(beta20 samehistory)',
 'proxy: exact range(0,len250-21) produces229 historical20point slopes, exclude final2completedends. Requires250price bars and nonconstantlow; original tryexcept returns0 if calculation fails, invalidinput not converted0 here. Naked mean/std rely on originalplatformimports, missing ETF/engine notexecuted.'),
 spec('subportfolio12_dualtrend_rsrsband','子账户趋势差与RSRS下轨交集',A,'dualtrend25_200priorclose where beta18>mean229beta20-2popSTD229beta20',
 'proxy: literalRSRSeligibility on source trend, ETFspread across4ETF not replaced with fullAspread; source maxspreadgate/top1portfolio absent explicitly. Qualifiedbenchmark.'),
 spec('failedlimit50_short_upperwick','炸板源码短上影比例',B,'-(lag1H-max(lag1O,lag1C))/(lag1H-lag1L)',
 'proxy NEW continuousranking of literal <.3 eligibility, no original factor ranking. Does not imply failedlimitmembership; actualhigh_limit, indices/minute breakthrough missing.'),
 spec('failedlimit50_openwick_partial','炸板源码开盘低于前高短上影交集',B,'-upperwick where lag1C>lag1O AND O<lag1H AND upperwick<.3',
 'proxy partialdaily gates only; originalfirstminutes price>=priorhigh/failedlimit/indexMA5/MACD/cache execution absent. Currentopenknownbutformalafterclose/nextclose label, never original9:30 fill.'),
 spec('thirdboard10_moneyvolume_lowprice_partial','三板源码量峰成交额与低价局部交集',C,'-lag1qfqC where lag1V=MAX3(V)t-1 AND amount(t-3)/amount(t-4)>=2 AND lag1amount*1000<=2.2e9',
 'proxy source lowRAWprice sorting replaced qfqprice explicitly, original actualthreeconsecutivelimits/fourthnonlimit,floatMV8..50e8,ST/paused/currentopen>=.94priorclose and7daybuckets missing. Only standalone eligibility+qfq ranking, not threeboard strategy; amountTusharethousandsyuan.')]
for sp in [SPECS[2],SPECS[4],SPECS[5]]:sp['gated']=True

def values(f,pos):
 c=f['close'].astype(float);h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));cov20=h.rolling(20).cov(l);beta20=cov20/l.rolling(20).var()
 beta18=h.rolling(18).cov(l)/l.rolling(18).var()
 # endt-231..t-3 inclusive =229 values, all inside completed250bars.
 hist=beta20.rolling(229);band=(hist.mean()-2*hist.std(ddof=0)).shift(3)
 margin=beta18.shift(1)-band
 dual=trend_at(c,pos-1,25)-trend_at(c,pos-1,200)/6
 mm=margin.to_numpy()[pos];qualified=np.where(mm>0,dual,np.nan)
 op=f['open'].astype(float);high=f['high'].astype(float);low=f['low'].astype(float)
 wick=(high-np.maximum(op,c))/np.where(high>low,high-low,np.nan);wick=q.delay(wick)
 partial=np.where((q.delay(c)>q.delay(op))&(op<q.delay(high))&(wick<.3),-wick,np.nan)
 v=f['volume'].astype(float);a=f['amount'].astype(float)
 gate=(q.delay(v)==q.delay(q.rolling(v,3,'max')))&(q.delay(a,3)/q.delay(a,4)>=2)&(q.delay(a)*1000<=2.2e9)
 third=np.where(gate,-q.delay(c),np.nan)
 return [dual,mm,qualified,-wick[pos],partial[pos],third[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='actual250/229/18/20 slices and literal wick.3 andamount2 gates fixedbeforeoutcome')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:32] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-7);checks.append(dict(key=sp['key'],test='rawdaily_prefix_priorbars',passed=True))
 obs=0
 for i in [35,79]:
  t=pos[i]
  for j in range(32):
   l=small['low'][t-250:t,j].astype(float);h=small['high'][t-250:t,j].astype(float)
   if np.isfinite(l).all() and np.isfinite(h).all() and all(l[k:k+20].std()>0 for k in range(229)):
    betas=[np.polyfit(l[k:k+20],h[k:k+20],1)[0] for k in range(0,len(l)-21)]
    if l[-18:].std()>0:
     ref=np.polyfit(l[-18:],h[-18:],1)[0]-np.mean(betas)+2*np.std(betas)
     np.testing.assert_allclose(whole[1][i,j],ref,atol=2e-6,rtol=1e-6);obs+=1
 checks.append(dict(test='independent_original229_polyfit20_lowerband_and_beta18',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='dailyhelperproxies, missing limit/ETF/intradaymembershipnotfabricated'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED117',flush=True)
if __name__=='__main__':main()
