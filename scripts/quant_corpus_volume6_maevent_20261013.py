"""Literal six-day volume state and early vendor MA-cross disclosed proxy."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2021年度精选策略/82.无需先验知识，动态选择的etf轮动策略，更具鲁棒性.txt'
B='quant/2020年度精选策略/90 MA均线金叉买入，死叉卖出.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source124-20261013'
SPECS=[
 spec('etf82_volume7_run6_exact','量七均线三上六下三十条状态',A,'lag1(first opposite sign within30 of V/MA7(V)-1: +1 up run>=3,-1 down run>=6,else0; no opposite->missing)',
 'proxy literal source lag6, unlike prior source107 lag5. Original WORST among top7liquid ETFs global timing replaced ownstockvolume; no pretend top10/top3 prose. Zero>=0 considered up; exact source None retained.'),
 spec('etf82_return13_run6_qualified','十三日量价及六日缩量状态约束',A,'C/lag13C-1 WHERE ret13>=.001 AND C>=lag1MA13 AND lag1volume7state6>=0',
 'proxy .1percent inclusive, not prose1percent; current11:30price adapted tclose. Top7mean30volume ETF universe absent; >22/>21 branches unreachable within7 so active top1, not top3; banned510880/510500, holding/rebalance/cash ETF absent. factor_valid qualified subset.'),
 spec('early90_ma5_10_cross_dailyproxy','五十均线金叉日频代理',B,'lag1(I(MA5>MA10 AND prevMA5<=prevMA10))',
 'proxy NEW explicit completedbar arithmetic definition of external MA_judge_jincha(5,10), vendor seed/boundary/asof not verified. Source samecross in technical and trade filters, empty sortdict preserves codeorder, no HS300PIT or ST/limit/fills. Known MA family, not newcluster.')]
SPECS[1]['gated']=True

@njit(cache=True)
def volume_state6(v,pos):
 out=np.full((len(pos),v.shape[1]),np.nan)
 for i,t in enumerate(pos):
  for j in range(v.shape[1]):
   h=v[t-100:t,j]
   if not np.isfinite(h).all():continue
   mean=np.mean(h[-7:])
   if mean<=0:continue
   last=h[-1]/mean-1
   for k in range(30):
    end=99-k;mean=np.mean(h[end-6:end+1]);z=h[end]/mean-1 if mean>0 else np.nan
    if last>=0 and z<0:out[i,j]=1 if k>=3 else 0;break
    if last<0 and z>=0:out[i,j]=-1 if k>=6 else 0;break
 return out

def values(f,pos):
 c=pd.DataFrame(f['close'].astype(float));state=volume_state6(f['volume'].astype(float),pos)
 ret=(c/c.shift(13)-1).to_numpy()[pos];prior=c.rolling(13).mean().shift(1).to_numpy()[pos]
 qualified=np.where((ret>=.001)&(f['close'][pos]>=prior)&(state>=0),ret,np.nan)
 m5=c.rolling(5).mean();m10=c.rolling(10).mean()
 cross=(m5>m10)&(m5.shift(1)<=m10.shift(1));valid=np.isfinite(m10.shift(1))
 event=pd.DataFrame(np.where(valid,cross.astype(float),np.nan)).shift(1).to_numpy()[pos]
 return [state,qualified,event]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source82lag6 exact, inclusive.001, MA5/10 discloseddailyproxy; fixedbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for s,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=s['key'],test='rawdaily_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   h=sf['volume'][t-100:t,j].astype(float)
   if np.isfinite(h).all():
    z=pd.Series(h)/pd.Series(h).rolling(7).mean()-1;ref=np.nan
    for k in range(30):
     if z.iloc[-1]>=0 and z.iloc[-1-k]<0:ref=1 if k>=3 else 0;break
     if z.iloc[-1]<0 and z.iloc[-1-k]>=0:ref=-1 if k>=6 else 0;break
    np.testing.assert_allclose(full[0][i,j],ref,equal_nan=True)
   h=sf['close'][t-11:t,j].astype(float)
   if np.isfinite(h).all():
    ref=float(h[-5:].mean()>h[-10:].mean() and h[-6:-1].mean()<=h[-11:-1].mean())
    np.testing.assert_allclose(full[2][i,j],ref)
 assert np.isnan(volume_state6(np.ones((100,1)),np.array([100]))[0,0])
 checks.append(dict(test='independent_pandas30step_search_and_literal_MA_cross; no-crossing-none',passed=True))
 q.dump(OUT/'source_evidence.json',{s:read_text(q.ROOT/s) for s in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='disclosed ETFindividualstock and externalMA proxy'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED124',flush=True)
if __name__=='__main__':main()
