"""Correct currency units and distinct pressure100 source59 mathematics."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_sweep_20261013 import tie_diagnostic
A='quant/量化策略/量化策略/首板回调买入策略2026/实10-首板竞价三模式-25年206.7.txt'
B='quant/聚宽2025年精选/59追板策略，今年收益已翻倍，低操作低回撤高收益可实盘.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source160-20261013'
COMMON='proxy completeddaily priorbar t-1 fullA mathematical extension, not actual event/auction/minute/orderhistory. Amount cache thousandyuan converted x1000, volume lots converted x100 for VWAP. Source currency gates in yuan. No untouched OOS. '
SPECS=[
 spec('auction10_weak3ret_body_amount_yuan_margin','弱转强成交额单位修正版',A,'min((.28-RET3)/.28,(C/O-.95)/.05,(1000amount-3e8)/3e8,(19e8-1000amount)/19e8,totalMV/70e8-1) t-1',COMMON+'Corrects source159 wrong amountunit; oldoutputs superseded retained. Fourcloses3intervals; omitted vendorcircMV<=520,VWAP>=.96,auctionvolume3%,openingrelativeactualhigh_limit,101leftpressure,brokenboard andMAstop. NEW continuousmin only, not complete3modeunion.'),
 spec('chase59_pressure100_external105_volume_ratio','百日左压外取一百零五量比',B,'priorV/MAX(priorvolume d+4bars),d=reversehigh100[-3::-1] first>=last high with enumerate(i-1,2),fallback100',COMMON+'Distinct source100H, missinghigh fallback100+5=105V request unbounded by100 (source7/实10 uses101clamped). Skip_paused vendor adapts completecalendar windows. NEW continuous ratio helper; original strict>.9 threshold. No complete firstlimit+past2everlimit exclusions ormoney/cap/auctionfidelity claim.'),
 spec('chase59_pressure_vwap_money_daily_margin','左压均价成交額日线交集余量',B,'min(pressure100/.9-1,VWAPraw/rawC/.96-1,(moneyYuan-7e8)/7e8,(19e8-moneyYuan)/19e8,totalMV/70e8-1) t-1',COMMON+'NEW continuouspartial of literal nobuy clauses: pressure>.9,VWAP/C>=.96,money7..19亿,totalMV>=70; original vendorcircMV<=520 OMITTED, no guessed totalMVupper. RawC used onlyfor VWAPconversion cancellation equivalentqfqVWAP/qfqC; rawC neverlabel/rankingprice substitute. firstlimit andauctionvolume/openband missing; fullA diagnostic.')]

@njit(cache=True)
def pressure(h,v,pos):
 out=np.full((len(pos),h.shape[1]),np.nan)
 for i in range(len(pos)):
  t=pos[i]
  for j in range(h.shape[1]):
   a=h[t-100:t,j]
   if len(a)!=100 or not np.isfinite(a).all():continue
   d=100
   for k in range(97,-1,-1):
    if a[k]>=a[99]:d=98-k;break
   b=v[t-(d+5):t,j]
   if len(b)!=d+5 or not np.isfinite(b).all():continue
   p=np.max(b[:-1])
   if p>0:out[i,j]=b[-1]/p
 return out

def values(f,pos):
 prior=pos-1;c=pd.DataFrame(f['close'].astype(float));r3=(c/c.shift(3)-1).to_numpy()[prior];body=f['close'][prior]/f['open'][prior]
 money=f['amount'][prior].astype(float)*1000;mv=f['cap'][prior].astype(float)*10000
 a=np.minimum.reduce([(.28-r3)/.28,(body-.95)/.05,(money-3e8)/3e8,(19e8-money)/19e8,mv/70e8-1])
 p=pressure(f['high'].astype(float),f['volume'].astype(float),pos)
 with np.errstate(divide='ignore',invalid='ignore'):
  vw=(f['amount'][prior].astype(float)*1000)/(f['volume'][prior].astype(float)*100)/f['raw_close'][prior]
 b=np.minimum.reduce([p/.9-1,vw/.96-1,(money-7e8)/7e8,(19e8-money)/19e8,mv/70e8-1])
 return [a,p,b]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source-fixed correctedcurrency anddistinct100H/105Vkernel andsource59money7..19,ratio.96,pressure.9 gates; frozen beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 observations=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   h=sf['high'][t-100:t,j].astype(float);v=sf['volume'][:,j].astype(float)
   if not np.isfinite(h).all():continue
   d=next((i-1 for i,x in enumerate(h[-3::-1],2) if x>=h[-1]),100);b=v[t-d-5:t]
   ref=b[-1]/max(b[:-1]) if np.isfinite(b).all() and max(b[:-1])>0 else np.nan
   np.testing.assert_allclose(full[1][i,j],ref,equal_nan=True,atol=1e-8);observations+=1
 # no older high reaches final high:105 requestedV retained, earlier largevolume matters.
 h=np.ones((110,1));h[109]=2;v=np.ones((110,1));v[5]=10
 np.testing.assert_allclose(pressure(h,v,np.array([110]))[0,0],.1)
 # 100000千元=1亿元, 100000手=1000万股 => 10元成交均价.
 assert 100000*1000/(100000*100)==10
 checks.append(dict(test='independent100reverse_enumerate_105externalwindow_and_units_toy',observations=observations,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED160',flush=True)
if __name__=='__main__':main()
