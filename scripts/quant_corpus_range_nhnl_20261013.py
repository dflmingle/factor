"""Reviewed firstboard range, literal nonaccumulating CUSUM and NHNL atoms.

These are explicitly partial full-A adaptations, never original strategy runs.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/78首板低开策略-终极版 最大回撤15%，年化50%.txt'
B='quant/2024年度精选策略1/96.大盘预测器v1.1--引入世界数据.txt'
C='quant/2024年度精选策略1/89.【复现·水】市场情绪指标专题行业指数顶部和底部信号.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source115-20261013'
SPECS=[
 spec('firstboard78_lowrange15_priorclose','首板源码十五日低区间位置',A,'-(lag1C-MIN15(L)t-1)/(MAX15(H)t-1-MIN15(L)t-1)',
 'proxy NEW continuous ranking of original eligibility helper; qfq/fullA completed bars; source skips NaNs in max/min, reproduced with min_periods1; missing actual firstlimitup/ST/auction/execution, not source complete strategy.'),
 spec('firstboard78_lowrange30_priorclose','首板源码三十日低区间位置',A,'-(lag1C-MIN30(L)t-1)/(MAX30(H)t-1-MIN30(L)t-1)',
 'proxy NEW continuous ranking of original <=.5 eligibility, not original ranking or firstboard strategy; no fabricated limit prices.'),
 spec('firstboard78_stproxy_openband_range15','源码四至六点涨幅开盘带区间腿',A,'-range15 where 4%<lag1RET<6% AND lag1C>2.5 AND 0<=O/lag1C-1<=.01 AND 0<=range15<=.3',
 'proxy partial source classification, not actual ST; price2.5 uses raw_close. Opening known on t but evaluated after t close under nextclose label; actual limitup/no-limitpriorcalendar/IPO60/paused/11:25exit missing. Gated benchmark; event support may be insufficient.'),
 spec('firstboard78_regular_openband_range30','源码普通板低开带区间腿',A,'-range30 where 9%<lag1RET<22% AND lag1(C/O-1)>.05 AND -.04<=O/lag1C-1<=-.03 AND 0<=range30<=.5',
 'proxy partial daily source helper; missing actual high_limit, calendar no-limit and intraday exits. FullA signal t close to nextclose label explicit adaptation, never same-opening trade claim.'),
 spec('world96_nonaccumulating_cusum_lag1','世界数据源码非累积五日偏离事件',B,'U if log(lag1C/MEAN5(C)t-2)>1.1*popSTD5(log(C)t-2), else D if <negativeband, else0',
 'proxy literal plotted ETF close helper, istart5 threshold.1; S_h/S_l never updated, so not CUSUM accumulator. Last loop skips lastbar, retains lag1; plots markers onepoint early. No four-worldETF inputs/LightGBM futureprice model reproduced.'),
 spec('nhnl89_highlow260_offset5_reversal','行业NHNL实际高低价个股反向事件',C,'-(I(H>=MAX260(H)t-5)-I(L<=MIN260(L)t-5))',
 'proxy NEW individual stock extension, no industry aggregation or PIT industry denominator. Frozen author core.py tradition=False actually HIGH/LOW contrary narrative CLOSE; >=/<= literal; t-264..t-5 bounds. Missing currentindustrybackfill/IPO252naturalday denominator. Not original markettiming strategy.')]
for sp in SPECS[2:4]:sp['gated']=True

def values(f,pos):
 c=pd.DataFrame(f['close'].astype(float));h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));o=pd.DataFrame(f['open'].astype(float))
 ranges=[]
 for n in [15,30]:
  hi=h.rolling(n,min_periods=1).max().shift(1);lo=l.rolling(n,min_periods=1).min().shift(1)
  ranges.append((c.shift(1)-lo)/(hi-lo).where(hi>lo))
 r1,r2=ranges;ret=c.shift(1)/c.shift(2)-1;gap=o/c.shift(1)-1
 rawprev=pd.DataFrame(f['raw_close']).shift(1)
 g1=(ret>.04)&(ret<.06)&(rawprev>2.5)&(gap>=0)&(gap<=.01)&(r1>=0)&(r1<=.3)
 g2=(ret>.09)&(ret<.22)&((c/o-1).shift(1)>.05)&(gap>=-.04)&(gap<=-.03)&(r2>=0)&(r2<=.5)
 mean=c.rolling(5).mean().shift(2);sd=np.log(c).rolling(5).std(ddof=0).shift(2);z=np.log(c.shift(1)/mean)
 cusum=np.where(np.isfinite(z)&np.isfinite(sd),np.where(z>1.1*sd,1,np.where(z< -1.1*sd,-1,0)),np.nan)
 hi=h.rolling(260).max().shift(5);lo=l.rolling(260).min().shift(5)
 nh=np.where(np.isfinite(hi)&np.isfinite(lo)&np.isfinite(h)&np.isfinite(l),-((h>=hi).astype(float)-(l<=lo).astype(float)),np.nan)
 return [(-r1).to_numpy()[pos],(-r2).to_numpy()[pos],(-r1.where(g1)).to_numpy()[pos],(-r2.where(g2)).to_numpy()[pos],cusum[pos],nh[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source-fixed15/30, actualistart5/.1, actualNHNL260offset5 before outcome')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:32] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 obs=0
 for i in [35,79]:
  t=pos[i]
  for j in range(32):
   c=small['close'][:,j].astype(float);hh=small['high'][:,j].astype(float);ll=small['low'][:,j].astype(float)
   for k,n in enumerate([15,30]):
    lo=np.nanmin(ll[t-n:t]);hi=np.nanmax(hh[t-n:t]);ref=-(c[t-1]-lo)/(hi-lo) if hi>lo else np.nan
    np.testing.assert_allclose(whole[k][i,j],ref,equal_nan=True,atol=1e-8)
   a=c[t-6:t-1]
   if np.isfinite(a).all() and np.isfinite(c[t-1]):
    sd=np.std(np.log(a/a.mean()));z=np.log(c[t-1]/a.mean());up=max(0,z-sd);down=min(0,z+sd)
    ref=1 if up>.1*sd else(-1 if abs(down)>.1*sd else 0)
    np.testing.assert_allclose(whole[4][i,j],ref,atol=1e-8)
   a=hh[t-264:t-4];b=ll[t-264:t-4]
   if np.isfinite(a).all() and np.isfinite(b).all():
    ref=-(float(hh[t]>=max(a))-float(ll[t]<=min(b)));np.testing.assert_allclose(whole[5][i,j],ref,atol=1e-8);obs+=1
 checks.append(dict(test='literal_range_nonaccumulating_loop_and_inclusive260bounds',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
 ext=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012/external_dependency_evidence_20261013'
 q.dump(OUT/'external_core_evidence.json',dict(manifest=json.loads((ext/'NHNL_download_manifest.json').read_text()),code=(ext/'NHNL_core.py').read_text(),executed=False))
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory; no untouched OOS',fidelity='partial dailyhelpers, not original full strategies'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED115',flush=True)
if __name__=='__main__':main()
