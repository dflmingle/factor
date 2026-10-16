"""Remaining reviewed ETF ranking kernels, explicit daily stock adaptations."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2021年度精选策略/30.ETF宽基轮动修改版-1.0.txt'
B='quant/2023年度精选策略/6.21年度6.为了挣点积分自己实盘的策略分享出来.txt'
C='quant/2023年度精选策略/31.北向Boll带_ETF组合宝付费策略.txt'
D='quant/2024年度精选策略2/75.ETF轮动策略-入门2.0.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source107-20261013'
SPECS=[
 spec('etf30_return20_ma90_qualified','二十日动量及九成均线资格',A,'RET20 where RET20>.02 AND C>.9*MA10(C)',
 'proxy: source intradayprice replaced dailyclose, exact20 priorcloses and removeoldest/addcurrent MA10 arithmetic. FullA adaptation, source7 crossasset instruments/top4 return-weight allocation absent; qualified factor_valid benchmark'),
 spec('etf6_volume7_run5_exact','量七均线三上五下三十条搜寻状态',B,'lag1(exact first opposite sign within last30(V/MA7(V)-1): +1 if up run>=3,-1 if down run>=5,else0; no crossing->missing)',
 'proxy: source100daily volume history, loop range30 retained, no opposite sign returnsNone; inclusive zero boundary. FullA perstock volume replaces WORST ETF index volume, NEW partial extension; not source marketstate'),
 spec('etf6_return13_volume5_qualified','十三日量价与五日缩量过滤',B,'RET13 where RET13>=.001 AND C>=lag1MA13(C) AND completedbar_volume_state>=0',
 'proxy: reviewed actual .1percent not prose1percent, equality boundaries retained. Dailyclose replaces11:30quote, missing dynamic indexvolume substituted stockvolume explicitly; top3/2 code both >12 against11ETF so actually top1, holdings and executions absent'),
 spec('etf31_return15_dailyextension','十五日原始动量局部核',C,'C/lag15(C)-1',
 'proxy: exact15priorcloses to intraday replaced dailyclose; source does NOT require positive momentum/MA gap. Northbound currentday252/150bands1.5STD and80/20bands2STD with sell>=2/buy>=3 missing; dormant EmotionMonitor NOT added; fullETF strategy absent'),
 spec('etf75_logtrend27_priorclose','二十七价点趋势拟合度',D,'expm1(250*OLS27(logC).slope)*R2, ending t-1',
 'proxy: exact27pricepoint horizon, monetarylog trend with no positive gate; known family horizonvariant only. Actual indexRSRS18/600*.R2 and MA20slope5 and expandingnorthboundmedian floor5 missing; source3ETF ranking and costs not reproduced')]
SPECS[0]['gated']=SPECS[2]['gated']=True

@njit(cache=True)
def volume_state(v,pos):
 out=np.full((len(pos),v.shape[1]),np.nan)
 for i,t in enumerate(pos):
  for j in range(v.shape[1]):
   h=v[t-100:t,j];good=True
   for z in h:
    if not np.isfinite(z):good=False
   if not good:continue
   dif=np.empty(30)
   for k in range(30):
    end=99-k;mean=np.mean(h[end-6:end+1]);dif[k]=h[end]/mean-1 if mean>0 else np.nan
   last=dif[0]
   if not np.isfinite(last):continue
   for k in range(30):
    if last>=0 and dif[k]<0:
     out[i,j]=1 if k>=3 else 0;break
    if last<0 and dif[k]>=0:
     out[i,j]=-1 if k>=5 else 0;break
 return out

def values(f,pos):
 c=f['close'].astype(float);ma=pd.DataFrame(c).rolling(10).mean().to_numpy();ret20=c[pos]/c[pos-20]-1
 state=volume_state(f['volume'].astype(float),pos);ret13=c[pos]/c[pos-13]-1
 prior13=pd.DataFrame(c).rolling(13).mean().shift(1).to_numpy()[pos]
 return [np.where((ret20>.02)&(c[pos]>.9*ma[pos]),ret20,np.nan),state,
  np.where((ret13>=.001)&(c[pos]>=prior13)&(state>=0),ret13,np.nan),
  c[pos]/c[pos-15]-1,trend_at(c,pos-1,27)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='five source-fixed kernels; no outcome selection; horizonvariants not new clusters')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:64] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawpricevolume_prefix',stop=stop,passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   h=small['close'][t-20:t,j].astype(float);price=float(small['close'][t,j]);ma10=(price+sum(h[-10:])-h[-10])/10
   ret=price/h[0]-1;ref=ret if ret>.02 and price>.9*ma10 else np.nan
   np.testing.assert_allclose(whole[0][i,j],ref,equal_nan=True,atol=1e-8)
   h=small['volume'][t-100:t,j].astype(float)
   if np.isfinite(h).all():
    z=pd.Series(h)/pd.Series(h).rolling(7).mean()-1;ref=np.nan
    for k in range(30):
     if z.iloc[-1]>=0 and z.iloc[-1-k]<0:ref=1 if k>=3 else 0;break
     if z.iloc[-1]<0 and z.iloc[-1-k]>=0:ref=-1 if k>=5 else 0;break
    np.testing.assert_allclose(whole[1][i,j],ref,equal_nan=True)
   h=small['close'][t-27:t,j].astype(float)
   if np.isfinite(h).all() and h.std()>0:
    y=np.log(h);s,b=np.polyfit(np.arange(27),y,1);r2=1-np.square(y-(s*np.arange(27)+b)).sum()/((len(y)-1)*y.var(ddof=1))
    np.testing.assert_allclose(whole[4][i,j],np.expm1(250*s)*r2,atol=1e-7,rtol=1e-6)
 assert np.isnan(volume_state(np.ones((100,1)),np.array([100]))[0,0])
 checks.append(dict(test='independent_literal_source_price_insertion_30step_volume_search_and_polyfit27; no-crossing-none boundary',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C,D]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='daily stock partial adaptation'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED107',flush=True)
if __name__=='__main__':main()
