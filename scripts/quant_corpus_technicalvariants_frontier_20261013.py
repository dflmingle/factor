"""Untested exact-window technical kernels from sources formerly family-labelled."""
import sys,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
BASE=q.ROOT/'quant/2020年度精选策略'
def src(prefix):return str(next(BASE.glob(prefix+'*')).relative_to(q.ROOT))
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source78-20261013'
SPECS=[
 spec('turtle19_skip1_atr20_source','海龟十九条排除近一条突破',src('49 '),
 '(C-lag2(MAX19(H)))/mean20(max(H,lag1C)-min(L,lag1C))',
 'proxy: exact source21bar high[-21:-2]19bars and ATR20 simplemean retained; current last close included only in ATR, not breakout threshold. Stock adaptation of sugar futures; portfolio pyramiding/shorting/contractroll omitted'),
 spec('macd9_24_zero_source60','六十条价格重置九二十四MACD零轴',src('76 '),
 'TA-Lib MACD(last60close,9,24,9).DIF[-1]/C; source buys DIF>0, not histogramcross',
 'proxy: exact source60bar reset/TA-Lib periods and rawDIF selection, continuous price-scaled fullA stock adaptation of index timing'),
 spec('dmi18_adx_rise_source100','百条价格重置DMI十八上升交集',src('79 '),
 'min((ADX18[-1]-ADX18[-2])/100,(PLUS_DI18[-1]-MINUS_DI18[-1])/100), each last100OHLC reset',
 'proxy: exact sourceTA-Lib100OHLC reset, continuous margin of buyconjunction; stocks replace index, source asymmetric sell and holdings gates omitted'),
 spec('slowema120_cross_fast60_source','慢线一百二十穿快线六十',src('46 '),
 '(EMA120_SMAseed-EMA60_SMAseed)/C',
 'proxy: source misnamedshort120/long60 retained, buy slowabovefast. Seed firstcompleteNdailycloseSMA then alpha2/(N+1). Source recursively updates intraday bars/currentprice, dailyclose proxy explicitly; fixed5stocks/4capitalunits omitted')]

def seeded_ema(c,n):
 out=np.full(c.shape,np.nan);mean=q.rolling(c,n);prev=np.full(c.shape[1],np.nan)
 for t in range(len(c)):
  known=np.isfinite(prev)&np.isfinite(c[t]);new=np.where(known,prev+(c[t]-prev)*2/(n+1),mean[t])
  new[~np.isfinite(c[t])]=np.nan;out[t]=new;prev=new
 return out

def daily(f):
 c=f['close'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float)
 tr=np.maximum(h,q.delay(c))-np.minimum(l,q.delay(c));atr=q.rolling(tr,20)
 return [q.ratio(c-q.delay(q.rolling(h,19,'max'),2),atr),q.ratio(seeded_ema(c,120)-seeded_ema(c,60),c)]

def signals(f,pos):
 c=f['close'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float)
 mac=np.full((len(pos),c.shape[1]),np.nan);dmi=mac.copy()
 for i,t in enumerate(pos):
  for j in range(c.shape[1]):
   a=c[t-59:t+1,j]
   if len(a)==60 and np.isfinite(a).all():mac[i,j]=talib.MACD(a,fastperiod=9,slowperiod=24,signalperiod=9)[0][-1]/c[t,j]
   hh=h[t-99:t+1,j];ll=l[t-99:t+1,j];cc=c[t-99:t+1,j]
   if len(cc)!=100 or not np.isfinite(np.stack([hh,ll,cc])).all():continue
   adx=talib.ADX(hh,ll,cc,timeperiod=18);pdi=talib.PLUS_DI(hh,ll,cc,timeperiod=18);ndi=talib.MINUS_DI(hh,ll,cc,timeperiod=18)
   dmi[i,j]=min((adx[-1]-adx[-2])/100,(pdi[-1]-ndi[-1])/100)
  if i%30==0:print('EXACT_WINDOW_SIGNAL',i,len(pos),flush=True)
 return [mac,dmi]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='actual formerly family-labelled source windows; no reusing a different-lookback old output')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:64] for k,v in f.items()};full=daily(small);whole=signals(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cutf={k:v[:stop] for k,v in small.items()};d=daily(cutf);s=signals(cutf,pos[:n])
  for sp,a,b in zip([SPECS[0],SPECS[3]],full,d):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-7);checks.append(dict(key=sp['key'],test='daily_price_prefix_rebuild',cutoff=str(cal[stop-1]),passed=True))
  for sp,a,b in zip(SPECS[1:3],whole,s):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-7);checks.append(dict(key=sp['key'],test='price_truncation_and_TA_Lib_reset100_60_replay',cutoff=str(cal[stop-1]),passed=True))
 # Independent literal source49 functions, without executing corpus imports/trades.
 checked=0
 for t in [1200,1800,len(cal)-1]:
  for j in range(64):
   c=small['close'][t-20:t+1,j].astype(float);h=small['high'][t-20:t+1,j].astype(float);l=small['low'][t-20:t+1,j].astype(float)
   if not np.isfinite(np.stack([c,h,l])).all():continue
   atr=np.mean([max(h[k],c[k-1])-min(l[k],c[k-1]) for k in range(1,21)])
   if atr<=0:continue
   np.testing.assert_allclose(full[0][t,j],(c[-1]-max(h[-21:-2]))/atr,atol=1e-7);checked+=1
 checks.append(dict(test='independent_original19bar_slice_and_ATR20_loop',observations=checked,passed=True))
 source_code=read_text(q.ROOT/SPECS[1]['source_paths'][0]);assert 'fastperiod=9' in source_code and 'slowperiod=24' in source_code and "60" in source_code
 checks.append(dict(test='source_MACD9_24_9_reset60_constants_checked',passed=True))
 d=daily(f);s=signals(f,pos);vals=[d[0][pos],s[0],s[1],d[1][pos]]
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='exact source slice/library windows with explicitly disclosed stock/daily adaptations',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED78',flush=True)

if __name__=='__main__':main()
