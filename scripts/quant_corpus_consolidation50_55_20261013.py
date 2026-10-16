"""Daily consolidation kernels, without synthetic limit or minute data."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_sweep_20261013 import tie_diagnostic
A='quant/聚宽2025年精选/50分享一种K线小碎步后突破的分钟级打法.txt'
B='quant/聚宽2025年精选/55怎么让龟速变奔跑？以“首版突破一进二”为例.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source158-20261013'
COMMON='proxy NEW fullA completedqfq daily adaptation; original priorbar timing retained. No actual high_limit or intraday breakout/fill/holdingpath fabricated. No original strategy or independent OOS certification. '
SPECS=[
 spec('smallstep50_lowreturn15_nearhigh60_margin','小碎步低振幅近高点余量',A,'min((.025-MAX15(abs(RET1)))/.025,C/MAX15C-1,C/MAX60H/.92-1) at t-1',COMMON+'Source filter_amp actually close/pre_close absolute dailyreturn not intrabarH/L amplitude; requires <=2.5% eachof15, C==MAX15close and C>.92MAX60high. Source prior300 HASlimitup (not excludes), prior30 excludes C>.95actualhigh_limit; both missing/omitted. circMV<25 omitted, EPS queried unused, currentprice.945..975high_limit absent. NEW minimum continuous extension.'),
 spec('first55_nearhigh_ranges300_50_10_margin','首板长短整理近高点余量',B,'min(1.2C/MAX300C-1,1.2C/MAX50C-1,1.1C/MAX10C-1,(3-MAX300C/MIN300C)/3,(1.5-MAX10C/MIN10C)/1.5) at t-1',COMMON+'Literal preC*1.2>high300 AND samehigh50,preC*1.1>high10,range300<2,range10<=.5; source includes own preclose so50condition redundant under300. NEW continuous min of disclosed inequalities, strict/equality qualification not inferred from score. Source priornotlimit,circMV<150,IPO30,minute2barfirstlimit andstrongmatch_by_signal omitted.'),
 spec('smallstep50_size25_dailygate_priority','小碎步日线资格市值优先',A,'2*I(totalMV_billion<25 AND MAX15absRET<=.025 AND priorC==MAX15C AND priorC>.92MAX60H)+rank(-totalMV)',COMMON+'NEW fullA same-support membership adapter: original circMV<25 replaced currenttotalMV explicitly; missing two actuallimit gates andminute entry omitted. Not originalunordered5holdings; compares saved144SIZE.')]

def kernels(f,pos):
 c=pd.DataFrame(f['close'].astype(float));h=pd.DataFrame(f['high'].astype(float));ret=(c/c.shift(1)-1).abs()
 r=ret.rolling(15).max().shift(1).to_numpy()[pos];p=c.shift(1).to_numpy()[pos]
 mx={n:c.rolling(n).max().shift(1).to_numpy()[pos] for n in [10,15,50,300]}
 mn={n:c.rolling(n).min().shift(1).to_numpy()[pos] for n in [10,300]}
 hi=h.rolling(60).max().shift(1).to_numpy()[pos]
 with np.errstate(divide='ignore',invalid='ignore'):
  a=np.minimum.reduce([(.025-r)/.025,p/mx[15]-1,p/hi/.92-1])
  b=np.minimum.reduce([1.2*p/mx[300]-1,1.2*p/mx[50]-1,1.1*p/mx[10]-1,(3-mx[300]/mn[300])/3,(1.5-mx[10]/mn[10])/1.5])
 cap=f['cap'][pos].astype(float);base=q.rank(np.where(cap>0,-cap,np.nan))
 gate=(cap/10000<25)&(r<=.025)&(p==mx[15])&(p>.92*hi)
 return [a,b,base+2*gate]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal15/60/300/50/10 and.025/.92/1.2/1.1/2/.5/25 fixed beforeoutcomes; NEW min andmembership adapters disclosed')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=kernels(sf,pos);checks=[]
 for n in [35,79]:
  cut=kernels({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 count=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   c=sf['close'][:,j].astype(float);h=sf['high'][:,j].astype(float)
   if not np.isfinite(c[t-301:t]).all() or not np.isfinite(h[t-60:t]).all():continue
   p=c[t-1];r=max(abs(c[t-15:t]/c[t-16:t-1]-1));hi=max(h[t-60:t]);mx15=max(c[t-15:t])
   ref=min((.025-r)/.025,p/mx15-1,p/hi/.92-1)
   np.testing.assert_allclose(full[0][i,j],ref,atol=1e-8)
   mx300=max(c[t-300:t]);mn300=min(c[t-300:t]);mx50=max(c[t-50:t]);mx10=max(c[t-10:t]);mn10=min(c[t-10:t])
   ref=min(1.2*p/mx300-1,1.2*p/mx50-1,1.1*p/mx10-1,(3-mx300/mn300)/3,(1.5-mx10/mn10)/1.5)
   np.testing.assert_allclose(full[1][i,j],ref,atol=1e-8);count+=1
 assert count>0;checks.append(dict(test='independent_literal_daily_slices',observations=count,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,kernels(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 b=pd.read_csv(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/results.csv');r=pd.read_csv(OUT/'results.csv');deltas=[]
 for _,x in r[r.form.eq('raw')&r.key.eq(SPECS[2]['key'])].iterrows():
  z=b[b.key.eq('membership144_size_control')&b.window.eq(x.window)&b.form.eq('raw')].iloc[0]
  deltas.append(dict(key=x.key,window=x.window,form='raw',delta_net_excess_pct=x.net_excess_pct-z.net_excess_pct,
   delta_held_daily_max_drawdown_pct=x.held_daily_max_drawdown_pct-z.held_daily_max_drawdown_pct,delta_turnover_pct=x.turnover_pct-z.turnover_pct))
 pd.DataFrame(deltas).to_csv(OUT/'matched_size_control_deltas.csv',index=False)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED158',flush=True)
if __name__=='__main__':main()
