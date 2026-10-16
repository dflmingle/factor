"""Prior-calendar-asof filing comparison; independently reconstructed quarterly proxy."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/29.高增股池小市值轮动.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source135-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-highgrowth29-calendar-schema-20261013'
FIELDS={'income':['revenue','n_income_attr_p'],'fina_indicator':['profit_dedt']}
COMMON='proxy singlequarter revenue,parentNI and deductedprofit via YTD differences, current latestincome quarter matched sameperiod deductedprofit. PRIOR snapshot replayed at signalpreviousdate minus1CALyear (Feb29->Feb28), not currentquarter minus4: retains original possible reportingperiod mismatch. ParentNI_TTM PE not deductedPE as dormantv1.3. Prior-dayconsolidatedPIT, Tushare profit_dedt vendor mapping proxy. No375day/ST/20daylimitblacklist/Aprilcash/7ETF/minute/10positions or full strategy claims; qualification benchmark.'
SPECS=[
 spec('growth29_calendar_asof_qualified_size','去年同日可见增长小盘交集',A,'-totalMV WHERE 0<PE_TTM<=30 AND adjustedProfitQuarter>0 AND adjustedGrowth>0 AND revenueGrowth>=.15 AND PE/(100*adjustedGrowth)<=1',COMMON+' Literal source PEcap30 notcomment40; size sorting original.'),
 spec('growth29_calendar_asof_lowPEG_extension','去年同日可见扣非增长低PEG',A,'-PE/(100*adjustedGrowth) WHERE all source financial gates',COMMON+' NEW lowPEG ranking of computed but only filtered source metric, no source size term.'),
 spec('growth29_calendar_asof_balanced_extension','去年同日可见营收扣非稳健增长',A,'min(revenueGrowth-.15,adjustedGrowth) WHERE all source financial gates',COMMON+' NEW weakest-growth ranking, fixed equalratio units before outcomes.')]
for sp in SPECS:sp['gated']=True

def single(reports,period):
 if period not in reports:return np.nan
 if period.quarter==1:return reports[period]
 return reports[period]-reports[period-1] if period-1 in reports else np.nan

def snapshots(tables,dates,stocks):
 # Independent asof report states, no retrospective replacement by future revisions.
 out=np.full((len(dates),len(stocks),3),np.nan)
 grouped={ep:{k:g.sort_values(['ann_date','end_date','update_flag']) for k,g in t.groupby('instrument',sort=False)} for ep,t in tables.items()}
 for j,s in enumerate(stocks):
  if any(s not in grouped[ep] for ep in FIELDS):continue
  ins=grouped['income'][s];fin=grouped['fina_indicator'][s]
  arrays=[(g.ann_date.to_numpy(),pd.PeriodIndex(g.end_date,freq='Q-DEC'),g[cols].to_numpy(float)) for g,cols in [(ins,['revenue','n_income_attr_p']),(fin,['profit_dedt'])]]
  states=[{},{}];ats=[0,0]
  for i,d in enumerate(dates):
   for e,(ann,ends,v) in enumerate(arrays):
    while ats[e]<len(ann) and ann[ats[e]]<=d.to_datetime64():states[e][ends[ats[e]]]=v[ats[e]];ats[e]+=1
   if not states[0]:continue
   cur=max(states[0]);inc=single(states[0],cur);ded=single(states[1],cur)
   if np.isscalar(inc):continue
   qs=[single(states[0],cur-k) for k in range(4)]
   ni=sum(x[1] for x in qs) if all(not np.isscalar(x) and np.isfinite(x[1]) for x in qs) else np.nan
   out[i,j]=[inc[0],ded[0] if not np.isscalar(ded) else np.nan,ni]
 return out

def values(now,old,cap):
 nr,npf,ni=np.moveaxis(now,-1,0);orr,opf,_=np.moveaxis(old,-1,0)
 rev=np.divide(nr-orr,np.abs(orr),out=np.full(nr.shape,np.nan),where=np.abs(orr)>1e-12)
 pg=np.divide(npf-opf,np.abs(opf),out=np.full(npf.shape,np.nan),where=np.abs(opf)>1e-12)
 pe=np.divide(cap*10000,ni,out=np.full(ni.shape,np.nan),where=np.abs(ni)>1e-12)
 peg=np.divide(pe,100*pg,out=np.full(pe.shape,np.nan),where=np.abs(pg)>1e-12)
 good=(pe>0)&(pe<=30)&(npf>0)&(pg>0)&(rev>=.15)&(peg<=1)&np.isfinite(peg)
 return [np.where(good,-cap,np.nan),np.where(good,-peg,np.nan),np.where(good,np.minimum(rev-.15,pg),np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source exact calendarasof and PE30, singlequarter explicitproxy, fixedextensions before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1];prior=pd.DatetimeIndex([d-pd.DateOffset(years=1) for d in dates])
 oldfields=q.FIN_FIELDS
 try:q.FIN_FIELDS=FIELDS;tables=q.pit_tables()
 finally:q.FIN_FIELDS=oldfields
 q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),prior_dates=list(prior),stocks=list(stocks),rule=q.ALIGNMENT_RULE_VERSION))
 cache=SCHEMA/'snapshots.npz'
 if cache.exists():cached=np.load(cache);now=cached['now'];old=cached['old']
 else:now=snapshots(tables,dates,stocks);old=snapshots(tables,prior,stocks);np.savez(cache,now=now,old=old)
 ids=np.arange(128);checks=[]
 for n in [35,79]:
  for label,ds,whole in [('current',dates,now),('prior_calendar',prior,old)]:
   sub={ep:t[(t.ann_date<=ds[n-1])&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};cut=snapshots(sub,ds[:n],stocks[ids])
   np.testing.assert_allclose(whole[:n,ids],cut,equal_nan=True,atol=1e-8);checks.append(dict(test='rawfiling_prefix_replay_'+label,finite=int(np.isfinite(cut).sum()),passed=True))
 assert pd.Timestamp('20240229')-pd.DateOffset(years=1)==pd.Timestamp('20230228')
 # Known quarter reconstruction independent of replay implementation.
 r={pd.Period('2023Q1') : np.array([10.]),pd.Period('2023Q2'):np.array([35.]),pd.Period('2023Q3'):np.array([65.]),pd.Period('2023Q4'):np.array([110.])}
 np.testing.assert_allclose([single(r,p)[0] for p in sorted(r)],[10,25,30,45])
 checks.append(dict(test='independent_YTD_to_quarters_and_Feb29calendar_replay_boundary',passed=True))
 vals=values(now,old,f['cap'][pos]);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
 q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON,benchmark_warning='source qualification subset'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED135',flush=True)
if __name__=='__main__':main()
