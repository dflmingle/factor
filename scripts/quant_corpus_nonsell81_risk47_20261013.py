"""Reviewed no-cross-volume and asymmetric risk state; independent stock proxies."""
import json, sys
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_volume6_maevent_20261013 import volume_state6
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
A='quant/2021年度精选策略/81.无杠杆，稳定盈利的etf轮动，06年开始3000%收益.txt'
B='quant/2021年度精选策略/47.高收益低回撤的小市值策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source133-20261013'
SPECS=[
 spec('etf81_ret13_nonsellNone_qualified','十三日收益允许无反向量穿越',A,'RET13 WHERE RET13>=.001 AND C>=priorMA13 AND volume100run6 != -1 (no-cross None permits)',
 'proxy original worstETF-associated INDEX volume replaced ownstockvolume,11:30 quote replaced completed tclose. No-cross source None!=-1 permits entry; finite100volume required, unavailable vendor exception does NOT fabricate buy. Fixed7ETF/top1/holding/cashETF/execution not reproduced.'),
 spec('etf81_volume100_nonsellNone','百日量状态无六下卖出',A,'I(volume100run6 != -1), finite100volume; implicit no-cross None permits',
 'proxy NEW individualstock binary rank from global source sell trigger. Unlike source124 state>=0, retains finite no-crossing observations. Binarytie sensitivities required; no fixed ETF strategy performance claim.'),
 spec('risk47_asymmetric_ma1000_rsi60_allow','千均线非对称风险状态允许',B,'prior C/MA(min(1000,availablebars)); normal->warning if ratio>2.5 or<.30; warning->normal if .35<=ratio<=.7; allow normal or 47<reset61barRSI60<99',
 'proxy NEW eachstock ranking replacing original HS300 GLOBAL risk gate; prior completed daily bars,2018 initialNORMAL seed not unknown original strategy seed. Source period truncation retained for available contiguous history. RSI computed on61bars RESET, not full-history Wilder; original circMV/index/14:40/orders omitted.')]
SPECS[0]['gated']=True

@njit(cache=True)
def risk_daily(c):
 out=np.full(c.shape,np.nan)
 for j in range(c.shape[1]):
  warning=False;start=0
  for t in range(len(c)):
   if not np.isfinite(c[t,j]):start=t+1;continue
   lo=max(start,t-999);n=t-lo+1
   if n<2:continue
   ma=np.mean(c[lo:t+1,j]);ratio=c[t,j]/ma if ma>0 else -1
   if ratio<=0:continue
   if not warning:
    if ratio>2.5 or ratio<.30:warning=True
   elif .35<=ratio<=.7:warning=False
   if not warning:out[t,j]=1.;continue
   if t-start<60:out[t,j]=0.;continue
   up=0.;down=0.
   for k in range(t-59,t+1):
    diff=c[k,j]-c[k-1,j];up+=max(diff,0.);down+=max(-diff,0.)
   rsi=100*up/(up+down) if up+down>1e-14 else 0.
   out[t,j]=1. if 47<rsi<99 else 0.
 return out

def values(f,pos):
 c=f['close'].astype(float);v=f['volume'].astype(float);s=volume_state6(v,pos)
 finite=np.array([np.isfinite(v[t-100:t]).all(axis=0) for t in pos])
 permit=finite&(s!=-1)
 ret=c[pos]/c[pos-13]-1;ma=pd.DataFrame(c).rolling(13).mean().shift(1).to_numpy()[pos]
 return [np.where(permit&(ret>=.001)&(c[pos]>=ma),ret,np.nan),np.where(finite,permit.astype(float),np.nan),risk_daily(c)[pos-1]]

def verify(f,pos):
 sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='raw_daily_prefix_state_replay',passed=True))
 toy={'close':np.ones((101,1))*10,'volume':np.ones((101,1))}
 a=values(toy,np.array([100]));assert a[1][0,0]==1 and np.isnan(volume_state6(toy['volume'],np.array([100]))[0,0])
 # Independent source state loop and fresh TA-Lib RSI on adversarial paths.
 for h in [np.r_[np.ones(1000)*10,np.ones(70)*35,np.ones(30)*2,np.ones(100)*6], np.linspace(1,200,1300),np.ones(1300)]:
  got=risk_daily(h[:,None])[:,0];warning=False
  for t in range(1,len(h)):
   ratio=h[t]/np.mean(h[max(0,t-999):t+1])
   if not warning:
    if ratio>2.5 or ratio<.30:warning=True
   elif .35<=ratio<=.7:warning=False
   if not warning:ref=1.
   else:ref=float(47<talib.RSI(h[t-60:t+1],timeperiod=60)[-1]<99) if t>=60 else 0.
   np.testing.assert_allclose(got[t],ref)
 checks.append(dict(test='independent_reset_TALib_RSI60_and_asymmetric_transition_and_finiteNone_permits',passed=True))
 return checks

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal finite None and asymmetric gates fixed before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 checks=verify(f,pos);q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='stock adaptations of ETF/globalINDEX gating, not full strategies'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED133',flush=True)
if __name__=='__main__':main()
