"""Full10-day pullback, smoothed bias, strict2000-bar sampled reversal."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
PULL='quant/2022年度精选策略/29.价值投资优选标的，虽然慢，还是有收益的.txt'
BIAS='quant/2024年度精选策略2/66.ETF动量轮动MA乖离择时.txt'
LONG='quant/2024年度精选策略1/40.14年初到23年7月，年化37，夏普1.25，稳健高收益！.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source58-20261013'
SPECS=[
 spec('trend10_pullback_financial_margin','十日多头财务回踩完整余量',PULL,'min(last10 min(MA5/MA10-1,MA10/MA20-1,MA20/MA60-1,MA60/MA120-1),C/MA20-1,1-C/MA10,ROE/5-1,netprofit_yoy/5-1)',
 'proxy: full active HS300 financial ROE>5/profit_growth>5 and10-day MA ordering/MA20<=C<=MA10 entry conjunction continuous margin; source index15daytrend, vendor zero-weight sorting/ST/pause/execution excluded; qfq tradingdays rather than skippaused'),
 spec('smoothed_bias60_10_z30','六十日乖离十日平滑标准分',BIAS,'(MA10(C/MA60)-MA30(MA10(C/MA60)))/populationSTD30(MA10(C/MA60))',
 'proxy: literal source market BUY z>4 / SELL z<-4 direction extracted as fullA highscore atom; ETF/index timing becomes individual stock; 200bar sourcewindow sufficient for exact rolling60+10+30'),
 spec('sampled2000_meanreversion_source','两千日采样均值回复',LONG,'-((mean(last20 of [C[t-1999: t:20],C[t]]) / mean(all101 sampledpoints))-1), require all2000prices',
 'proxy: actual source100*20history and every20bars sample, shortMA20 means20sampledpoints(~380days), NOT dailyMA20; strict2000daily history means earlyformal missing; source ROE>4/PBbottom100/growthtop50 qualification omitted; no shortened window'),
]

@njit
def sampled(c,pos):
 out=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  if t<1999:continue
  for j in range(c.shape[1]):
   if not np.isfinite(c[t-1999:t+1,j]).all():continue
   total=0.;recent=0.
   for k in range(100):
    v=c[t-1999+20*k,j];total+=v
    if k>=81:recent+=v
   total+=c[t,j];recent+=c[t,j]
   if total>0:out[i,j]=-(recent/20/(total/101)-1)
 return out

def build(f,fin,pos):
 c=f['close'].astype(float);ma=[q.rolling(c,n) for n in [5,10,20,60,120]]
 order=np.minimum.reduce([q.ratio(ma[k],ma[k+1])-1 for k in range(4)])
 worst=q.rolling(order,10,'min')
 roe=fin['fina_indicator.roe.q0'];growth=fin['fina_indicator.netprofit_yoy.q0']
 pull=np.minimum.reduce([worst[pos],(q.ratio(c,ma[2])-1)[pos],(1-q.ratio(c,ma[1]))[pos],roe/5-1,growth/5-1])
 bias=q.rolling(q.ratio(c,ma[3]),10)
 z=q.ratio(bias-q.rolling(bias,30),q.rolling(bias,30,'std')*np.sqrt(29/30))
 return [pull,z[pos],sampled(c,pos)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source fixed before outcomes, strict history no fallback',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks)
 ids=np.arange(16);small={k:v[:,ids] for k,v in f.items()};sf={k:v[:,ids] for k,v in fin.items()};full=build(small,sf,pos);checks=[]
 for n in [35,119]:
  stop=pos[n-1]+1;cut=build({k:v[:stop] for k,v in small.items()},{k:v[:n] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-5,atol=1e-5);checks.append(dict(key=sp['key'],test='prefix_daily_prices_and_previously_raw_PIT_verified_financial_features',stop=stop,passed=True))
 # Direct source sampling must be on full2000bars, not every20 of an undersized array.
 t=pos[-1]
 for j in range(16):
  c=small['close'][t-1999:t+1,j].astype(float)
  if np.isfinite(c).all():
   sample=np.r_[c[::20],c[-1]];ref=-(sample[-20:].mean()/sample.mean()-1)
   np.testing.assert_allclose(full[2][-1,j],ref,rtol=1e-6,atol=1e-6)
 checks.append(dict(key=SPECS[2]['key'],test='independent_literal2000bar_101point_20sample_means',passed=True))
 vals=build(f,fin,pos)
 q.dump(OUT/'history_coverage.json',dict(warmup=str(cal[0].date()),strict2000_earliest_calendar_date=str(cal[1999].date()),grid_signals_possible=int((pos>=1999).sum()),total_formal_signals=len(grid),warning='strict2000 recipe cannot support nearfiveyear conclusion; no window shortening'))
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no independent OOS',fidelity='literal source technical kernels and explicit stock adapters',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED58',flush=True)
if __name__=='__main__':main()
