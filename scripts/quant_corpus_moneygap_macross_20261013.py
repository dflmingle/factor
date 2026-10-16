"""Disclosed daily proxies for remaining auction joint and size stop rule."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_corpus_limithelpers_20261013 import values as helpers119
A='quant/量化策略/量化策略/首板回调买入策略2026/实10-首板竞价三模式-25年206.7.txt'
B='quant/2022年度精选策略/70.年化64%的市值选股策略（有止损模块）.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source161-20261013'
SPECS=[
 spec('auction10_lowrange60_money_gap955_daily','低位成交额低开新带部分腿',A,'-priorRange60 where priorRange<=.5 AND priorMoneyYuan>=1e8 AND .955<=O(t)/priorC<=.97',
 'proxy NEWpartial dailyopeningquote replaces auction[0]. No actualfirstlimit/nonchain/PITIPO50/ST/pause orsameopeningfill. Source lowopen mode does NOT have auctionvolume3% gate contrary introductory prose; retains1亿 and.955boundary differs119.96. Source skippaused adaptedcalendar qfq. Qualifiedbenchmark mayhave sparse support, not complete3modeunion.'),
 spec('size70_strict10_50_crossunder_avoid','市值策略十日五十日死叉回避',B,'-I(priorMA10<priorMA50 AND prevMA10>prevMA50)',
 'proxy daily strictonebar stophelper, source actualperiod10/50 notcomment2/20. Usespriorclose information; equalitydoesnotcross. FullAhighrank means no sell signal, standalonebinarynewextension, not originally economicranking. Missing63daypaused/PIT000001+399106universe/T+1/rebalance+stopexecution.'),
 spec('size70_no_crossunder_priority_fullA','死叉回避市值资格同支持',B,'2*I(NOT strictprior10/50crossunder)+rank(-totalMV)',
 'proxy NEWfullA membershipadapter of source stop rule, never pretend stopnewentrygateoriginal. SamefullAsupport andsaved144SIZEcontrol. Source rebalancefirst thenexitcloseable, doubleorderloop, nextdayrebuy paths omitted. Dormantstairs10/15/20 unused; pureSIZEwithstopnotnewclusterproof.')]
SPECS[0]['gated']=True

def values(f,pos):
 c=pd.DataFrame(f['close'].astype(float));h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float))
 hi=h.rolling(60,min_periods=1).max().shift(1);lo=l.rolling(60,min_periods=1).min().shift(1)
 complete=np.isfinite(c)&np.isfinite(h)&np.isfinite(l)
 # Same source60 dropna helper as119 (fullshared arithmetic upstream reference).
 hi=h.where(complete).rolling(60,min_periods=1).max().shift(1);lo=l.where(complete).rolling(60,min_periods=1).min().shift(1)
 last=c.where(complete).ffill(limit=59).shift(1);rp=(last-lo)/(hi-lo).where(hi>lo)
 gap=f['open'][pos]/f['close'][pos-1];r=rp.to_numpy()[pos];money=f['amount'][pos-1].astype(float)*1000
 a=np.where((r<=.5)&(money>=1e8)&(gap>=.955)&(gap<=.97),-r,np.nan)
 m10=c.rolling(10).mean();m50=c.rolling(50).mean()
 valid=np.isfinite(m50.shift(1));cross=(m10<m50)&(m10.shift(1)>m50.shift(1))
 event=pd.DataFrame(np.where(valid,cross.astype(float),np.nan)).shift(1).to_numpy()[pos]
 base=q.rank(np.where(f['cap'][pos]>0,-f['cap'][pos],np.nan))
 # History insufficient is outsidequalification, fullA SIZEfallback retained.
 return [a,-event,base+2*(event==0)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal.955..97 money1e8 and10/50strictcross,fullApriorityextension disclosed beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 reference=helpers119(sf,pos)[0];mask=np.isfinite(full[0]);np.testing.assert_allclose(full[0][mask],reference[mask],atol=1e-8)
 count=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   c=sf['close'][t-51:t,j].astype(float)
   if not np.isfinite(c).all():continue
   e=c[-10:].mean()<c[-50:].mean() and c[-11:-1].mean()>c[-51:-1].mean()
   np.testing.assert_allclose(full[1][i,j],-float(e));count+=1
 assert count>0;checks.append(dict(test='literal10_50_twooverlappingwindows_andshared60helper',observations=count,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='partial daily gating andstopextension only'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 b=pd.read_csv(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source144-20261013/results.csv');r=pd.read_csv(OUT/'results.csv');deltas=[]
 for _,x in r[r.form.eq('raw')&r.key.eq(SPECS[2]['key'])].iterrows():
  z=b[b.key.eq('membership144_size_control')&b.window.eq(x.window)&b.form.eq('raw')].iloc[0]
  deltas.append(dict(key=x.key,window=x.window,form='raw',delta_net_excess_pct=x.net_excess_pct-z.net_excess_pct,delta_held_daily_max_drawdown_pct=x.held_daily_max_drawdown_pct-z.held_daily_max_drawdown_pct,delta_turnover_pct=x.turnover_pct-z.turnover_pct))
 pd.DataFrame(deltas).to_csv(OUT/'matched_size_control_deltas.csv',index=False)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED161',flush=True)
if __name__=='__main__':main()
