"""Resumable offline source frontier. Never imports or executes corpus strategies."""
from __future__ import annotations
import argparse
import json
import gc
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec, audit

TD='quant/2021年度精选策略/74.迪马克TD趋势反转指标.txt'
EAGLE='quant/2024年度精选策略2/92.利用myTT库整合通达信公式——以“飞鹰优选”选股公式为例.txt'
PATH='quant/2024年度精选策略2/79.实盘一周50%的妖股探测器.txt'
VOLUME='quant/2020年度精选策略/54 中长线买入卖出点选择.txt'
RECOVERY='quant/2023年度精选策略/92.【超跌反弹v1.0】3年2.3倍的超跌反弹小牛股.txt'
EXTREMA='quant/2023年度精选策略/69.选取向上趋势的股票.txt'
ORDER='quant/2023年度精选策略/70.回踩均线搏反弹，21年来70%，无未来（测试第一弹）.txt'
BOTTOM='quant/2023年度精选策略/60.抄底神器2.0，低回撤，高成功率，无未来函数.txt'
WEEK='quant/2024年度精选策略2/45.真真正正的诚意之作-2021超十倍.txt'
GFTD='quant/2020年度精选策略/78 GFTD第二版.txt'
ENSEMBLE='quant/2021年度精选策略/92.敢于直接实盘的—八仙过海V2.txt'
MONTH='quant/2023年度精选策略/97.韶华研究之六，简单不一样的发现趋势，3年6倍.txt'
FOF='quant/2021年度精选策略/14.FOF养老成长基金-v2.0.txt'
AMOUNT='quant/2020年度精选策略/39 因子分析——利用JoinQuant因子分析模块选取因子并封装为策略.txt'
MOM91='quant/2024年度精选策略1/49.年化62%的动量策略.txt'
RSRSV='quant/2020年度精选策略/77 RSRS大盘择时优化.txt'
SHORT='quant/2023年度精选策略/57.韶华研究之四-菲阿里四阶在T+1的短线策略应用.txt'
ORDER4='quant/2021年度精选策略/96.分享一个简单的选股器.txt'
TURTLE='quant/2021年度精选策略/46.大盘股也能穿越牛熊市.txt'
CONTRACTION='quant/2022年度精选策略/85.年化20%+的极简指数增强，受RSRS和LLT启发.txt'
PULLBACK='quant/2024年度精选策略2/8.14个月200%，超短线实盘交易策略！无未来函数.txt'

SPECS={27:[
 spec('td_countdown13_contrarian','TD倒计数衰竭',TD,
      '-setup*count/13; setup sign source +/-1; reset on bar after completion',
      'proxy: causal source setup/count/cancel stock adaptation; position execution reset replaced by next-bar reset'),
 spec('eagle_condition_margin','飞鹰条件最小余量',EAGLE,
      'min(normalized margins of all FYYH conditions); OR uses max; AVEDEV14 exact',
      'proxy: continuous distance from original conjunction, retains all FYYH thresholds; first-event execution not reproduced'),
 spec('endpoint_trend29_source','端点路径动量29',PATH,
      '(exp(250*(logC_t-logC_t-28)/29)-1)*abs(1-SSE(endpoint_line)/SST29)',
      'proxy: preserves non-OLS endpoint slope /29 and abs(pseudoR2); fullA without concept/size/intraday/5day execution gates'),
],28:[
 spec('dynamic_quiet_volume_margin','动态静默期放量余量',VOLUME,
      'min(length/30-1,V/(2.5*quiet_mean)-1,V/(2.5*prior5mean)-1,1-amplitude/.1,C/O-1)',
      'proxy: active buy helper reconstructed with source dynamic prior-volume>.8*V, max270 daily bars; missing trigger has length0; no source HS300 or skip-paused execution'),
 spec('ma55_recovery_margin','MA55恢复条件余量',RECOVERY,
      'min((old20above55-1)/20,(3-old20above55)/20,(recent3above55-1)/3,C/MA55-1,-(MIN10/MIN60-1))',
      'proxy: source prior40 first20 count1..3, recent3 count>=1 and equal10/60 low; intraday replaced by daily close'),
 spec('confirmed_low_event_slope126','确认低点序号趋势126',EXTREMA,
      'OLS(local_minimum_qfq_close~event_index) in last126 days, latest unconfirmed point excluded',
      'proxy: source fixed halfyear dates replaced by rolling126; local lows <= neighbours; 1day right confirmation; absolute slope source direction retained'),
],29:[
 spec('ma_order_compact_source','均线紧凑排列源码得分',ORDER,
      '-[sum20(lag1(RMS((MA13,21,55-median)/median)))-sum5(IF(MA13>=MA21>=MA55,MA13/MA21+MA21/MA55-2,0))]',
      'proxy: preserves median-based RMS and pair relative differences, ascending score; source recovery entry gates omitted'),
 spec('bottom_volume_margin','抄底量能复苏余量',BOTTOM,
      'min(.5-abs(1-C/lag1(MIN59)),.5-(1-C/lag2(MAX10)),prior4V/prior29V-1,1-prior29V/lag30(MA30V),lag2(MAX10C)/prior19MA-1,C/10-1)',
      'proxy: all source technical thresholds and literal off-by-one windows retained; qfq C>10 price filter adaptation, financial/position gates omitted'),
 spec('weekly_base_breakout_margin','周线底座突破余量',WEEK,
      'min(C/baseHigh-1,1.35-C/baseHigh,1-gapClose/baseHigh,C/weekOpen-1,weekV/gapMaxV-1,2-weekV/gapMaxV,weekV/baseMaxV-1)',
      'proxy: literal48 weekly bars split44 base/3 gap/current partial week; continuous margin; EMA gate, index gate and range ordering omitted'),
],34:[
 spec('gftd4_position_state','GFTD四阶段持有状态',GFTD,
      'per-stock empty/buy_count/full/sell_count state from source n1=4,n2=4,n3=4; return1 for full or sell_count',
      'proxy: source causal state machine adapted index timing to fullA stock ranks; dormant line-stop block excluded'),
 spec('ma_ensemble_position','五均线仓位状态',ENSEMBLE,
      's=.3I(C>MA5)+.25I(C>MA10)+.2I(C>MA20)+.15I(C>MA30)+.1I(C>MA60); score=1 if s==1 else .3*s',
      'proxy: source active nonlinear position kernel, stocks replace fixed fund pool and intraday price'),
 spec('monthly_three_candle_margin','三根完成月阳线最弱涨幅',MONTH,
      'MIN(last3 fully completed monthly close/open-1)-.05; latest unfinished month excluded',
      'proxy: monthly candle conjunction converted to continuous minimum; source index and lowPE filters omitted'),
],35:[
 spec('es250_tail5_low','250日五个最差收益低尾险',FOF,
      'mean(worst5 daily returns within250prices; first return zero)',
      'proxy: source ES confidence.02×250=5; trading-day implementation; calendar zero-fill only changes non-negative tail cases'),
 spec('fof_es_momentum20','FOF期望损失动量评分',FOF,
      '1.02^(100*RET20)/ES250; ES>0; source VaR function actually returns1',
      'proxy: source growth/risk position kernel without fixed fund weights or risk filters; actual VaR return1 retained'),
 spec('daily_amount_source_high','单日成交额原文方向',AMOUNT,
      'current daily amount, high preferred',
      'proxy: source current trading amount atom, fullA replaces HS300 and source2day cycle becomes10'),
],36:[
 spec('momentum91_source','91日动量原文',MOM91,
      'C/lag90(C)-1 (source count91 closes)',
      'proxy: literal91 observations, source price floor/universe/top10 execution omitted'),
 spec('endpoint_score_deterioration5_low','端点得分五日恶化次数低',PATH,
      '-COUNT(endpoint_trend29_source<lag1(endpoint_trend29_source),4)',
      'proxy: source five historical scores yield four changes; fullA count ranking replaces top-score then count<2 entry'),
 spec('fof_es_momentum_smoothed','FOF风险动量仓位记忆',FOF,
      'daily recursion p=.8*(CSmaxES/ES*1.02^(100*RET20))+.2*lag1(p)',
      'proxy: source80/20 causal position memory; fullA normalization replaces fixed fund pool; start/reset on valid positive ES'),
],38:[
 spec('rsrs1100_volume9_18','RSRS长窗放量右偏',RSRSV,
      'z1100(beta18)*beta18*R2_18*(2*sum9(V)/sum18(V)); exact1100 required',
      'proxy: source index/fund timing adapted to stocks; original2005 initialization unavailable; early signals explicitly missing'),
 spec('short_slope5_60_margin','五日六十日绝对趋势余量',SHORT,
      'min(round(OLS_slope(C,5),3)/2-1,round(OLS_slope(C,60),3)/C)',
      'proxy: literal active5/60 periods and absolute5day slope>2 source thresholds retained on qfq; source nominal-price/universe filters omitted'),
 spec('ma_order_four_compact','四均线紧凑排列源码',ORDER4,
      '-[sum30(lag1(RMS((MA10,20,30,60-median)/median)))-sum5(IF(monotone,adjacent_ratio_sum-3,0))]',
      'proxy: literal source4MA weights/median/window/order; consolidation/volume entry and valuation filters omitted'),
],39:[
 spec('turtle60_atr_channel_margin','海龟ATR上通道距离',TURTLE,
      'C/(MAX60(H)-2*mean60(TR))-1; positive channel',
      'proxy: source61bar talib.ATR60 has one initial mean60TR result; source current1minute price replaced by qfq daily close'),
 spec('contraction_recent_low_state','新低后波幅收缩状态',CONTRACTION,
      'I(lag1(MIN4C)==MIN10C AND MAX5(lag1(floor(MAX10C/MIN10C*100)/100))<MAX10(lag1(same)))',
      'proxy: literal source trailing exclusions/floor/equality; original index timing adapted to stocks; ties separately audited'),
 spec('pullback_deadcross_margin','上涨中的短线死叉余量',PULLBACK,
      'min(MA10/MA5-1,lag1(MA5/MA10)-1,lag1(VMA5/VMA10)-1,1.2*VMA5/VMA10-1,MA20/lag1MA20-1,MA30/lag1MA30-1)',
      'proxy: source active technical pullback conjunction; MACD absolute band/sign alternation/next-open execution omitted'),
]}

def ols_slope(c,n):
 mean=q.rolling(c,n);cov=np.zeros_like(c,dtype=float);var=n*(n*n-1)/12
 for k in range(n):cov+=(k-(n-1)/2)*((q.delay(c,n-1-k) if n-1-k else c)-mean)
 return cov/var

def rsrs_volume(f):
 h,l,v=[pd.DataFrame(f[k]) for k in ['high','low','volume']]
 beta=(h.rolling(18).cov(l)/l.rolling(18).var()).to_numpy()
 r2=h.rolling(18).corr(l).to_numpy()**2
 z=q.ratio(beta-q.rolling(beta,1100),q.rolling(beta,1100,'std')*np.sqrt(1099/1100))
 return z*beta*r2*q.ratio(q.rolling(f['volume'],9),q.rolling(f['volume'],18))

def order_four(f):
 a=np.stack([q.rolling(f['close'],n) for n in [10,20,30,60]]);median=np.median(a,axis=0)
 rms=np.sqrt(np.mean(((a-median)/median)**2,axis=0))
 arr=np.where(np.all(a[:-1]>=a[1:],axis=0),sum(q.ratio(a[k],a[k+1])-1 for k in range(3)),0)
 arr=np.where(np.isfinite(a).all(axis=0),arr,np.nan)
 return -(q.rolling(q.delay(rms),30)*30-q.rolling(arr,5)*5)

def contraction_state(f):
 c=f['close'];ratio=np.floor(q.ratio(q.rolling(c,10,'max'),q.rolling(c,10,'min'))*100)/100
 v=q.delay(ratio);a=q.delay(q.rolling(c,4,'min'));b=q.rolling(c,10,'min')
 x=q.rolling(v,5,'max');y=q.rolling(v,10,'max')
 valid=np.isfinite(np.stack([a,b,x,y])).all(axis=0)
 return np.where(valid,(a==b)&(x<y),np.nan).astype(np.float32)

def turtle_margin(f):
 c,h,l=[f[k] for k in ['close','high','low']];prior=q.delay(c)
 tr=np.maximum.reduce([h-l,np.abs(h-prior),np.abs(l-prior)])
 threshold=q.rolling(h,60,'max')-2*q.rolling(tr,60)
 return q.ratio(c,np.where(threshold>0,threshold,np.nan))-1

def pullback_margin(f):
 c,v=f['close'],f['volume'];ma={n:q.rolling(c,n) for n in [5,10,20,30]};v5=q.rolling(v,5);v10=q.rolling(v,10)
 return np.minimum.reduce([q.ratio(ma[10],ma[5])-1,q.delay(q.ratio(ma[5],ma[10]))-1,
  q.delay(q.ratio(v5,v10))-1,1.2*q.ratio(v5,v10)-1,
  q.ratio(ma[20],q.delay(ma[20]))-1,q.ratio(ma[30],q.delay(ma[30]))-1])

def gftd_state(f):
 c,h,l=[f[k] for k in ['close','high','low']];n=c.shape[1]
 state=np.zeros(n,np.int8);count=np.zeros(n,np.int8);saved=np.zeros(n)
 diff=c-q.delay(c,4)
 down=q.rolling(np.where(np.isfinite(diff),(diff<=0).astype(float),np.nan),4)==1
 up=q.rolling(np.where(np.isfinite(diff),(diff>=0).astype(float),np.nan),4)==1
 out=np.full(c.shape,np.nan,np.float32)
 for t in range(7,len(c)):
  invalid=~np.isfinite(c[t])|~np.isfinite(h[t])|~np.isfinite(l[t]);state[invalid]=0;count[invalid]=0
  setup=((state==0)|(state==1))&down[t]&~invalid
  state[setup]=1;saved[setup]=c[t,setup];count[setup]=0
  buy=(state==1)&(c[t]>=h[t-2])&(h[t]>h[t-1])&(c[t]>saved)&~invalid
  saved[buy]=c[t,buy];count[buy]+=1
  complete=(state==1)&(count==4);state[complete]=2;count[complete]=0
  setup=((state==2)|(state==3))&up[t]&~invalid
  state[setup]=3;saved[setup]=c[t,setup];count[setup]=0
  sell=(state==3)&(c[t]<=l[t-2])&(l[t]<l[t-1])&(c[t]<saved)&~invalid
  saved[sell]=c[t,sell];count[sell]+=1
  complete=(state==3)&(count==4);state[complete]=0;count[complete]=0
  out[t,~invalid]=((state==2)|(state==3))[~invalid].astype(float)
 return out

def ensemble(f):
 c=f['close'];ma=[q.rolling(c,n) for n in [5,10,20,30,60]]
 s=sum(w*(c>m) for w,m in zip([.3,.25,.2,.15,.1],ma))
 valid=np.isfinite(np.stack(ma)).all(axis=0)&np.isfinite(c)
 # Exact mathematical all-five state avoids binary rounding changing branch.
 allabove=np.all(np.stack([c>m for m in ma]),axis=0)
 return np.where(valid,np.where(allabove,1,.3*s),np.nan)

def month_margin(f,cal):
 out=np.full(f['close'].shape,np.nan,np.float32);starts=[];last=None
 for t,code in enumerate(cal.to_period('M')):
  if code!=last:starts.append(t);last=code
  if len(starts)<4:continue
  rs=[q.ratio(f['close'][starts[k+1]-1],f['open'][starts[k]])-1 for k in range(len(starts)-4,len(starts)-1)]
  out[t]=np.minimum.reduce(rs)-.05
 return out

@njit(cache=True)
def es_tail(c):
 out=np.full(c.shape,np.nan,np.float32)
 for j in range(c.shape[1]):
  for t in range(249,len(c)):
   worst=np.full(5,0.);good=True
   for k in range(t-248,t+1):
    if not np.isfinite(c[k,j]) or not np.isfinite(c[k-1,j]):good=False;break
    r=c[k,j]/c[k-1,j]-1
    if r<worst[4]:
     worst[4]=r
     for m in range(4,0,-1):
      if worst[m]<worst[m-1]:tmp=worst[m];worst[m]=worst[m-1];worst[m-1]=tmp
   if good:out[t,j]=-np.mean(worst)
 return out

def risk_position(f):
 es=es_tail(f['close']);growth=100*(q.ratio(f['close'],q.delay(f['close'],20))-1)
 score=q.ratio(np.power(1.02,growth),np.where(es>0,es,np.nan))
 return es,score

def position_memory(es,score):
 maximum=pd.DataFrame(es).max(axis=1).to_numpy()[:,None];raw=score*maximum
 out=np.full_like(raw,np.nan,dtype=np.float32);prev=np.full(raw.shape[1],np.nan)
 for t,x in enumerate(raw):
  valid=np.isfinite(x);prev=np.where(valid,np.where(np.isfinite(prev),.8*x+.2*prev,x),np.nan)
  out[t]=prev
 return out

@njit(cache=True)
def dynamic_quiet(c,o,h,l,v):
 out=np.full(c.shape,np.nan,np.float32)
 for j in range(c.shape[1]):
  for t in range(269,len(c)):
   if not np.isfinite(c[t,j]) or not np.isfinite(v[t,j]) or not np.isfinite(o[t,j]):continue
   trigger=-1
   for k in range(t-1,t-270,-1):
    if np.isfinite(v[k,j]) and v[k,j]>.8*v[t,j]:trigger=k;break
   start=trigger+1;length=t-start if trigger>=0 else 0
   if length<1:out[t,j]=-1.;continue
   vm=0.;hm=-np.inf;lm=np.inf;good=np.isfinite(o[start,j])
   for k in range(start,t):
    vm+=v[k,j];hm=max(hm,h[k,j]);lm=min(lm,l[k,j])
    good=good and np.isfinite(v[k,j]) and np.isfinite(h[k,j]) and np.isfinite(l[k,j])
   prev=np.mean(v[t-5:t,j])
   if not good or not np.isfinite(prev) or vm<=0 or prev<=0:continue
   amp=(hm-lm)/o[start,j]
   out[t,j]=min(length/30-1,v[t,j]/(2.5*vm/length)-1,v[t,j]/(2.5*prev)-1,1-amp/.1,c[t,j]/o[t,j]-1)
 return out

@njit(cache=True)
def low_event_slope(c):
 out=np.full(c.shape,np.nan,np.float32)
 for j in range(c.shape[1]):
  for t in range(125,len(c)):
   ys=np.empty(126);n=0;good=True
   for k in range(t-125,t):
    if not np.isfinite(c[k,j]):good=False;break
    left=c[k-1,j] if k>t-125 else c[k,j]
    if c[k,j]<=left and c[k,j]<=c[k+1,j]:ys[n]=c[k,j];n+=1
   if not good or n<2:continue
   xm=(n-1)/2.;ym=np.mean(ys[:n]);cov=0.;var=0.
   for k in range(n):cov+=(k-xm)*(ys[k]-ym);var+=(k-xm)**2
   out[t,j]=cov/var
 return out

def ma_recovery(f):
 c=f['close'];ma=q.rolling(c,55)
 above=np.where(np.isfinite(ma)&np.isfinite(c),(c>ma).astype(float),np.nan)
 old=q.delay(q.rolling(above,20)*20,20);recent=q.rolling(above,3)*3
 return np.minimum.reduce([(old-1)/20,(3-old)/20,(recent-1)/3,q.ratio(c,ma)-1,
                           -(q.ratio(q.rolling(c,10,'min'),q.rolling(c,60,'min'))-1)]).astype(np.float32)

def order_score(f):
 a=np.stack([q.rolling(f['close'],n) for n in [13,21,55]])
 median=np.median(a,axis=0)
 rms=np.sqrt(np.mean(((a-median)/median)**2,axis=0))
 arr=np.where((a[0]>=a[1])&(a[1]>=a[2]),q.ratio(a[0],a[1])+q.ratio(a[1],a[2])-2,0)
 arr=np.where(np.isfinite(a).all(axis=0),arr,np.nan)
 return -(q.rolling(q.delay(rms),20)*20-q.rolling(arr,5)*5)

def bottom_score(f):
 c,v=f['close'],f['volume'];hi=q.delay(q.rolling(c,10,'max'),2);lo=q.delay(q.rolling(c,59,'min'))
 short=q.delay(q.rolling(v,4));middle=q.delay(q.rolling(v,29));older=q.delay(q.rolling(v,30),30)
 return np.minimum.reduce([.5-np.abs(1-q.ratio(c,lo)),.5-(1-q.ratio(c,hi)),
  q.ratio(short,middle)-1,1-q.ratio(middle,older),q.ratio(hi,q.delay(q.rolling(c,19)))-1,c/10-1])

def weekly_score(f,cal):
 shape=f['close'].shape;out=np.full(shape,np.nan,np.float32)
 blocks=[];codes=cal.to_period('W-FRI');last=None
 for t,code in enumerate(codes):
  if code!=last:blocks.append(t);last=code
  if len(blocks)<48:continue
  start=blocks[-48];gap=blocks[-4];current=blocks[-1]
  if t==current:
   bc=f['high'][start:gap];gv=[];bv=[]
   for k in range(len(blocks)-48,len(blocks)-4):
    bv.append(np.sum(f['volume'][blocks[k]:blocks[k+1]],axis=0))
   for k in range(len(blocks)-4,len(blocks)-1):
    gv.append(np.sum(f['volume'][blocks[k]:blocks[k+1]],axis=0))
   basehigh=np.max(bc,axis=0);basevol=np.max(bv,axis=0);gapvol=np.max(gv,axis=0)
   gapclose=np.max(f['close'][np.array(blocks[-3:])-1],axis=0)
  wv=np.sum(f['volume'][current:t+1],axis=0);c=f['close'][t];wo=f['open'][current]
  out[t]=np.minimum.reduce([q.ratio(c,basehigh)-1,1.35-q.ratio(c,basehigh),1-q.ratio(gapclose,basehigh),
    q.ratio(c,wo)-1,q.ratio(wv,gapvol)-1,2-q.ratio(wv,gapvol),q.ratio(wv,basevol)-1])
 return out

def td_values(f):
 c,h,l=[f[k] for k in ['close','high','low']]
 d=c-q.delay(c,4);up=q.rolling(np.where(np.isfinite(d),(d>0).astype(float),np.nan),8)==1
 down=q.rolling(np.where(np.isfinite(d),(d<0).astype(float),np.nan),8)==1
 hi=q.rolling(h,8,'max');lo=q.rolling(l,8,'min')
 n=c.shape[1];state=np.zeros(n,np.int8);count=np.zeros(n,np.int16)
 ceiling=np.zeros(n);floor=np.zeros(n);out=np.full(c.shape,np.nan,np.float32)
 for t in range(12,len(c)):
  clear=(count==13)|~np.isfinite(c[t])|~np.isfinite(h[t])|~np.isfinite(l[t])
  state[clear]=0;count[clear]=0;ceiling[clear]=0;floor[clear]=0
  first=state.copy()
  a=(state==0)&down[t-1]&(d[t]>0);b=(state==0)&up[t-1]&(d[t]<0)
  state[a]=-1;ceiling[a]=hi[t,a];state[b]=1;floor[b]=lo[t,b]
  count[(state==-1)&(c[t]<l[t-2])]+=1
  count[(state==1)&(c[t]>h[t-2])]+=1
  neg=(state==-1)&(count!=13);pos=(state==1)&(count!=13)
  cancel=(neg&(c[t]>ceiling))|(pos&(c[t]<floor))
  switchup=neg&~cancel&up[t]&up[t-1]
  switchdown=pos&~cancel&down[t]&down[t-1]
  state[cancel]=0;count[cancel]=0;ceiling[cancel]=0;floor[cancel]=0
  state[switchup]=1;count[switchup]=0;ceiling[switchup]=0;floor[switchup]=lo[t,switchup]
  state[switchdown]=-1;count[switchdown]=0;floor[switchdown]=0;ceiling[switchdown]=hi[t,switchdown]
  restart=((neg&down[t]&down[t-1])|(pos&up[t]&up[t-1]))&(first==0)&~cancel
  count[restart]=0
  valid=np.isfinite(c[t])&np.isfinite(d[t])&np.isfinite(hi[t])&np.isfinite(lo[t])
  out[t,valid]=-state[valid]*count[valid]/13
 return out

def eagle_values(f):
 c,h,l=[f[k] for k in ['close','high','low']]
 ma={n:q.rolling(c,n) for n in [17,27,30,40,60,120]}
 typ=(h+l+c)/3;mean=q.rolling(typ,14)
 mad=np.zeros_like(typ,dtype=float)
 for k in range(14):mad+=np.abs((q.delay(typ,k) if k else typ)-mean)
 mad/=14
 cci=q.ratio(typ-mean,.015*mad)
 wide=q.ratio(h,l)>1.051
 count=q.rolling(np.where(np.isfinite(h)&np.isfinite(l),wide.astype(float),np.nan),5)*5
 margins=[q.ratio(h,l)/1.051-1,(count-1)/5,
  np.maximum(.78-q.ratio(c,ma[40]),.74-q.ratio(c,ma[60])),
  q.ratio(ma[27],c)/1.169-1,q.ratio(ma[17],c)/1.158-1,
  1-q.ratio(c,ma[120]),1-q.ratio(ma[60],ma[120]),q.ratio(ma[60],ma[30])-1,(cci+210)/210]
 score=np.minimum.reduce(margins).astype(np.float32)
 literal=wide&(count>1)&((q.ratio(c,ma[40])<.78)|(q.ratio(c,ma[60])<.74))
 literal&=(ma[27]>1.169*c)&(ma[17]>1.158*c)&(c<ma[120])&(ma[60]<ma[120])&(ma[60]>ma[30])&(cci>-210)
 # Normalization and float32 rounding must preserve the original conjunction.
 valid=np.isfinite(score);assert np.array_equal((score>0)[valid],literal[valid])
 event=literal&~np.vstack([np.zeros((1,c.shape[1]),bool),literal[:-1]])
 return score,event

def endpoint_values(f):
 y=np.log(f['close'].astype(float));n=29
 start=q.delay(y,n-1);slope=(y-start)/n
 # Exact source residual line, with x=0..28 and fixed intercept=start.
 sse=np.zeros_like(y);sst=(n-1)*q.rolling(y,n,'var')
 for k in range(n):sse+=((q.delay(y,n-1-k) if n-1-k else y)-(start+slope*k))**2
 pseudo=1-q.ratio(sse,np.where(sst>1e-15,sst,np.nan))
 with np.errstate(over='ignore',invalid='ignore'):
  score=np.expm1(slope*250)*np.abs(pseudo)
 return score.astype(np.float32)

def values(batch,f,cal=None):
 if batch==27:return [td_values(f),eagle_values(f)[0],endpoint_values(f)]
 if batch==28:return [dynamic_quiet(*[f[k] for k in ['close','open','high','low','volume']]),ma_recovery(f),low_event_slope(f['close'])]
 if batch==29:return [order_score(f),bottom_score(f),weekly_score(f,cal)]
 if batch==34:return [gftd_state(f),ensemble(f),month_margin(f,cal)]
 if batch==35:
  es,score=risk_position(f);return [-es,score,f['amount']]
 if batch==36:
  ep=endpoint_values(f);d=ep-q.delay(ep)
  count=q.rolling(np.where(np.isfinite(d),(d<0).astype(float),np.nan),4)*4
  es,score=risk_position(f)
  return [q.ratio(f['close'],q.delay(f['close'],90))-1,-count,position_memory(es,score)]
 if batch==38:
  c=f['close'];s5=np.round(ols_slope(c,5),3);s60=np.round(ols_slope(c,60),3)
  return [rsrs_volume(f),np.minimum(s5/2-1,q.ratio(s60,c)),order_four(f)]
 if batch==39:return [turtle_margin(f),contraction_state(f),pullback_margin(f)]
 raise ValueError(batch)

def checks(batch,f,cal):
 ids=np.flatnonzero(np.isfinite(f['close'][-600:]).all(axis=0))[:7]
 small={k:v[:,ids] for k,v in f.items()};full=values(batch,small,cal);out=[]
 for stop in [1200,len(f['close'])-31]:
  prefix=values(batch,{k:v[:stop] for k,v in small.items()},cal[:stop])
  for sp,a,b in zip(SPECS[batch],full,prefix):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-6,atol=1e-6)
   out.append(dict(key=sp['key'],test='actual_daily_prefix_recompute',stop=stop,passed=True))
 # Independent scalar endpoint residual reconstruction, including its odd /29.
 if batch==27:
  for t in [1200,len(small['close'])-1]:
   y=np.log(small['close'][t-28:t+1,0].astype(float));s=(y[-1]-y[0])/29
   literal=np.expm1(s*250)*abs(1-np.sum((y-(y[0]+s*np.arange(29)))**2)/np.sum((y-y.mean())**2))
   np.testing.assert_allclose(full[2][t,0],literal,rtol=1e-5,atol=1e-6)
  out.append(dict(test='independent_endpoint_literal',passed=True))
 if batch==28:
  for t in [1200,len(small['close'])-1]:
   v=small['volume'][t-269:t+1,0];c=small['close'][t,0];o=small['open'][t,0]
   trigger=next((k for k in range(268,-1,-1) if v[k]>.8*v[-1]),None)
   length=269-trigger-1 if trigger is not None else 0
   literal=-1.
   if length>0:
    a=t-269+trigger+1
    amp=(small['high'][a:t,0].max()-small['low'][a:t,0].min())/small['open'][a,0]
    literal=min(length/30-1,v[-1]/(2.5*v[trigger+1:-1].mean())-1,v[-1]/(2.5*v[-6:-1].mean())-1,1-amp/.1,c/o-1)
   np.testing.assert_allclose(full[0][t,0],literal,equal_nan=True,rtol=1e-5,atol=1e-5)
  out.append(dict(test='independent_dynamic_volume_source_slice',passed=True))
 return out

def tie_diagnostic(out,cal,stocks,f):
 saved=pd.read_pickle(out/'signal_panels.pkl');grid=saved['dates'];pos=cal.get_indexer(grid);rows=[]
 q.dates_all=cal
 for key,df in saved['panels'].items():
  x=df.to_numpy(dtype=float)
  unique=np.mean([len(np.unique(z[np.isfinite(z)]))/max(np.isfinite(z).sum(),1) for z in x])
  if unique>.5:continue
  for seed in [918273,918274,918275]:
   z=x.copy();rng=np.random.default_rng(seed)
   for i in range(len(z)):
    ids=np.flatnonzero(np.isfinite(z[i]));levels,inv=np.unique(z[i,ids],return_inverse=True)
    # Integer levels preserve order; jitter only affects exact ties.
    z[i,ids]=inv+rng.random(len(ids))*.25
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,_,_=q.evaluate(z[mask],grid[mask],stocks,pos[mask],f)
    a.update(key=key,window=win,seed=seed,scope='ties_only_sensitivity_not_original_factor_IC',mean_unique_fraction=unique)
    rows.append(a)
 if rows:pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(out/'tie_sensitivity.csv',index=False)

def main():
 p=argparse.ArgumentParser();p.add_argument('--batches',nargs='+',type=int,default=sorted(SPECS));args=p.parse_args()
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 for batch in args.batches:
  out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{batch}-20261013'
  out.mkdir(parents=True,exist_ok=True)
  plan=dict(specs=SPECS[batch],rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,
            selection='source-specific frozen formulas, no outcome-dependent parameter choice')
  manifest=out/'frozen_plan.json'
  if manifest.exists() and json.loads(manifest.read_text())!=plan:raise ValueError('plan mismatch')
  q.dump(manifest,plan)
  if (out/'audit_complete.json').exists():print('SKIP COMPLETE',batch,flush=True);continue
  verification=checks(batch,f,cal);daily=values(batch,f,cal);vals=[x[pos] for x in daily]
  if batch==27:
   _,event=eagle_values(f)
   q.dump(out/'eagle_event_coverage.json',{'events_on_signal_grid':event[pos].sum(axis=1).tolist(),
     'explanation':'Exact first-event flag too sparse for a whole fullA top decile; margin is an explicit adaptation'})
  run(out,SPECS[batch],vals,cal,stocks,f,verification,
      dict(fidelity='local source adaptation, no platform validation',missing='no financial null to zero fill',
           statistics='exploratory, no independent OOS',new_information_gate='simultaneous size reversal IVOL regression'))
  del daily,vals;gc.collect();audit(out,cal,stocks,f);tie_diagnostic(out,cal,stocks,f)
  q.dump(out/'audit_complete.json',dict(completed=True,batch=batch,platform_compute=0))
  print('AUDIT FINISHED',batch,flush=True)

if __name__=='__main__':main()
