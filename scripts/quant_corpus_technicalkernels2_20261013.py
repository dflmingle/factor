"""Exact source lookbacks, reset ATR and priority STOCH stock adaptations."""
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
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source81-20261013'
SPECS=[
 spec('futures_source_return9','十观测实际九日动量',src('04 '),'C/lag9C-1',
 'proxy: source last versus [-10] means9day gap, positive direction; continuous companion of literal ternary sign, futures->stock; weekly trade/contractroll/shorting omitted'),
 spec('futures_source_sign9_atr10_exposure','九日方向乘十日ATR风险预算',src('04 '),'sign(C/lag9C-1)*C/TA_Lib_ATR10(last15OHLC)',
 'proxy: sign source direction and reset15barATR10 retained; C/ATR is dimensionless exposure from source inverseATR contract sizing, adapted to stocks; not full futures strategy'),
 spec('futures_source_return14','十五观测实际十四日动量',src('17 '),'C/lag14C-1',
 'proxy: exact source last versus [-15]14day gap, stock adaptation; source top/bottom30percent futures universe and ATR15 sizing omitted'),
 spec('futures_source_return14_atr15_exposure','十四日动量乘十五日ATR预算',src('17 '),'(C/lag14C-1)*C/TA_Lib_ATR15(last20OHLC)',
 'proxy: explicit continuous extension combining source14day momentum and inverseATR15(last20) risk sizing, not original futures categorical portfolio'),
 spec('ma5_over_ma20_source09','五二十双均线差',src('09 '),'MA5(C)/MA20(C)-1',
 'proxy: exact source5/20 buy-direction kernel, futures->stock, reentry and chandelier exits omitted; source has no20daypricebreakout'),
 spec('boll20_population_upper_source45','布林二十总体标准差上轨余量',src('45 '),'(C-MA20(C))/(population_STD20(C))-2',
 'proxy: TA_LibBBANDS20/2/2 SMA exact continuous upper-margin; fixed600519->fullA, faulty position/exit rules omitted; same price kernel as source52 but its upper[-1] scalar indexing bug not silently repaired'),
 spec('ma10_threshold101_source66','十日线百分之一买入余量',src('66 '),'C/MA10(C)-1.01',
 'proxy: actual source1percent threshold and MA10 buy, MA20 namedMA5 sell asymmetry omitted; fixed000333->fullA; threshold only translates continuous rank'),
 spec('ma10_over_ma60_source83','十六十双均线差',src('83 '),'MA10(C)/MA60(C)-1',
 'proxy: exact source10/60 SMA buy atom, ETF->stock; intrabar execution and holdings omitted'),
 spec('stoch17_9_7_buy_priority_source91','随机指标十七九七源码买入优先级',src('91 '),
 'min(max(min(K-20,20-lag1K),min(K-80,K-D)),-max(min(80-K,lag1K-80),min(K-20,80-K,D-K)))/100; resetlast60OHLC',
 'proxy: exact TA_LibSTOCH17/9SMA/7SMA reset60 and original SELL-if before BUY-elif retained in continuous conjunction margin; current_position clauses omitted, index->stocks')]

def basic(f):
 c=f['close'].astype(float);df=pd.DataFrame(c);ma={n:df.rolling(n,min_periods=n).mean().to_numpy() for n in [5,10,20,60]}
 sd=df.rolling(20,min_periods=20).std(ddof=0).to_numpy()
 return [q.ratio(c,q.delay(c,9))-1,q.ratio(c,q.delay(c,14))-1,
 q.ratio(ma[5],ma[20])-1,q.ratio(c-ma[20],sd)-2,q.ratio(c,ma[10])-1.01,q.ratio(ma[10],ma[60])-1]

def priority(k,d,p):
 buy=np.maximum(np.minimum(k-20,20-p),np.minimum(k-80,k-d))
 sell=np.maximum(np.minimum(80-k,p-80),np.minimum(np.minimum(k-20,80-k),d-k))
 return np.minimum(buy,-sell)/100

def signals(f,pos):
 c=f['close'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float)
 a10=np.full((len(pos),c.shape[1]),np.nan);a15=a10.copy();st=a10.copy()
 for i,t in enumerate(pos):
  for j in range(c.shape[1]):
   for n,back,target in [(10,15,a10),(15,20,a15)]:
    hh=h[t-back+1:t+1,j];ll=l[t-back+1:t+1,j];cc=c[t-back+1:t+1,j]
    if len(cc)!=back or not np.isfinite(np.stack([hh,ll,cc])).all():continue
    atr=talib.ATR(hh,ll,cc,timeperiod=n)[-1]
    if atr>0:target[i,j]=cc[-1]/atr
   hh=h[t-59:t+1,j];ll=l[t-59:t+1,j];cc=c[t-59:t+1,j]
   if len(cc)!=60 or not np.isfinite(np.stack([hh,ll,cc])).all():continue
   k,d=talib.STOCH(hh,ll,cc,fastk_period=17,slowk_period=9,slowk_matype=0,slowd_period=7,slowd_matype=0)
   st[i,j]=priority(k[-1],d[-1],k[-2])
  if i%30==0:print('RESET_ATR_STOCH',i,len(pos),flush=True)
 b=basic(f)
 return [b[0][pos],np.sign(b[0][pos])*a10,b[1][pos],b[1][pos]*a15,b[2][pos],b[3][pos],b[4][pos],b[5][pos],st]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source windows/formulas fixed before outcomes; no sign or window selection after returns')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:64] for k,v in f.items()};whole=signals(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=signals({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-7,rtol=1e-7)
   checks.append(dict(key=sp['key'],test='truncated_daily_price_rebuild_resetATR_STOCH',cutoff=str(cal[stop-1]),passed=True))
 for k in [0,19,21,79,81,99]:
  for d in [10,50,90]:
   for prev in [0,19,21,79,81,99]:
    sell=(k<80 and prev>80) or (20<k<80 and k<d)
    buy=(k>20 and prev<20) or (k>20 and k>80 and k>d)
    assert (priority(k,d,prev)>0)==(buy and not sell)
 checks.append(dict(test='independent_original_scalar_sell_before_buy_branches',combinations=108,passed=True))
 count=0
 for t in pos[::31]:
  for j in range(64):
   a=small['close'][t-19:t+1,j].astype(float)
   if not np.isfinite(a).all() or a.std()==0:continue
   np.testing.assert_allclose(whole[5][list(pos).index(t),j],(a[-1]-a.mean())/a.std(ddof=0)-2,atol=1e-7);count+=1
 checks.append(dict(test='independent_numpy_population_STD20_source_BBANDS',observations=count,passed=True))
 for sp in SPECS:
  assert (q.ROOT/sp['source_paths'][0]).exists()
 q.dump(OUT/'source_evidence.json',{src(x):read_text(q.ROOT/src(x)) for x in ['04 ','09 ','17 ','45 ','52 ','66 ','83 ','91 ']})
 vals=signals(f,pos)
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory, no untouched OOS',fidelity='source windows, units and branch priorities with disclosed market adaptations',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED81',flush=True)

if __name__=='__main__':main()
