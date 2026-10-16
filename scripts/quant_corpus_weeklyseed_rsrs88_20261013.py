"""Weekly RSRS append semantics, with explicit reproducible warmup seed proxy."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2021年度精选策略/88.基于动量因子的ETF轮动加上RSRS择时.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source131-20261013'
SPECS=[
 spec('etf88_logtrend15_prior','十五价点对数趋势拟合度',SRC,'expm1(250*OLS15(logC).slope)*R2 endingt-1',
 'proxy literal15pricepoints=14intervals, priorcompletedclose. Fixed7INDEX ranking adapted fullAstocks rather ETFprice; originalweeklyWednesday,top2withrankbuffer andindexRSRS gate omitted, knowntrendfamily variation.'),
 spec('etf88_logtrend15_positive_partial','十五价点趋势正分约束',SRC,'priorLogtrend15 WHERE score>0',
 'proxy literal positive score gate; fullA qualified factor_valid benchmark; no newfamilyclaim, fixedINDEX-to-ETFmapping andtop2 omitted.'),
 spec('etf88_weeklyseed_rsrs_nonsell_trend15','周度追加RSRS与十五点趋势约束',SRC,'hold weeklyWednesday trend15>0 WHERE NOT(Z(last600 beta weeklyappend)*currentbeta*R2<-.7 AND priorMA20<priorMA20lag3)',
 'proxy NEW fullA adaptation. RSRS source appends only on Wednesday, not dailyrolling600; initialize599dailybetas from prior618bars dropping latest then appendcurrent, populationSTD, right-skew beta multiplier. Exactinitial backteststart unknown: seed first calendarWednesday with618priorwarmupbars, declared seed proxy; subsequent finite600state/weeklyscorecache causal. Top2 holdbuffer positionindex>3, sevenindices/ETF/fills absent. Newlisting missing seed retained missing, not imputeddailyhistory.')]
SPECS[1]['gated']=SPECS[2]['gated']=True

def weekly(f,cal):
 h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));cov=h.rolling(18).cov(l,ddof=0);vl=l.rolling(18).var(ddof=0);vh=h.rolling(18).var(ddof=0)
 beta=(cov/vl).to_numpy();r2=(cov**2/(vl*vh)).to_numpy();c=f['close'].astype(float);ma=pd.DataFrame(c).rolling(20).mean().to_numpy()
 marks=np.flatnonzero((cal.weekday==2)&(np.arange(len(cal))>=618));out=np.full(c.shape,np.nan);scores=[];history=None
 for t in marks:
  if history is None:history=list(beta[t-601:t-2].copy())
  history.append(beta[t-1].copy());history=history[-600:];a=np.stack(history)
  with np.errstate(divide='ignore',invalid='ignore'):rs=(a[-1]-a.mean(axis=0))/a.std(axis=0,ddof=0)*beta[t-1]*r2[t-1]
  trend=trend_at(c,np.array([t-1]),15)[0];good=np.isfinite(rs)&np.isfinite(ma[t-4])&(trend>0)&~((rs<-.7)&(ma[t-1]<ma[t-4]))
  out[t]=np.where(good,trend,np.nan);scores.append((t,rs))
 # Carry the last weekly snapshot including its NaNs. ffill would wrongly
 # resurrect an old qualifying score after a Wednesday sale/invalid result.
 last=None
 for t in range(len(cal)):
  if t in marks:last=out[t].copy()
  if last is not None:out[t]=last
 return out,scores,beta,r2

def values(f,cal,pos):
 tr=trend_at(f['close'].astype(float),pos-1,15);w,*_=weekly(f,cal)
 return [tr,np.where(tr>0,tr,np.nan),w[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source15/18/600/.7/gap3,weeklyWednesday with first618bar seed proxy fixedbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:32] for k,v in f.items()};full=values(sf,cal,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},cal[:stop],pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawOHLC_prefix_and_weeklystate_seed_replay',passed=True))
 w,scores,beta,r2=weekly(sf,cal);t0=scores[0][0];hist=list(beta[t0-601:t0-2]);tested=0
 for t,rs in scores[:80]:
  hist.append(beta[t-1]);sample=np.array(hist[-600:]);ref=(sample[-1]-sample.mean(axis=0))/sample.std(axis=0)*beta[t-1]*r2[t-1]
  np.testing.assert_allclose(rs,ref,equal_nan=True,atol=1e-8)
  for j in range(8):
   ll=sf['low'][t-18:t,j].astype(float);hh=sf['high'][t-18:t,j].astype(float)
   if np.isfinite(ll).all() and np.isfinite(hh).all() and ll.std()>0:
    np.testing.assert_allclose(beta[t-1,j],np.polyfit(ll,hh,1)[0],atol=1e-7,rtol=1e-7);tested+=1
 checks.append(dict(test='independent_literal599dailyseed_plus_weeklyappend_list_and_prior18polyfit',observations=tested,seed_date=str(cal[t0]),passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,values(f,cal,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='fullAstock adapter and explicitlychosen seeddate, not originalweeklyholdingstrategy'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED131',flush=True)
if __name__=='__main__':main()
