"""PIT annual/current growth intersection; cannot substitute latest YoY for annual."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/82.实盘模拟的小盘股策略，低频，带基本面优化以及个股风控.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source134-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-annualgrowth82-schema-20261013'
FIELDS={'income':['revenue','n_income_attr_p']}
COMMON='proxy prior-day announced consolidated income: latestknown Q4 versus previous Q4 annual growth, latestknown YTD versus same quarter prior year current YoY. Signed growth=(new-old)/abs(old)*100; zero denominator missing, vendor bases not byte-equivalent. No PITindustry/7holdings/20buy10sell/14% exit or capital helpers; source alleged trailing maximum actually ends at PURCHASEdate and expands backwards. factor_valid qualified subset; not full strategy.'
SPECS=[
 spec('small82_annual_current_growth_size','年度当期双增长小盘交集',A,'-totalMV WHERE annualRevenueYoY>0 AND currentRevenueYoY>20 AND currentParentNIYoY>0 AND annualParentNIYoY>40',COMMON+' Literal source totalMV order; pure-size residual degeneracy does not test membership value.'),
 spec('small82_balanced_growth_margin_extension','双增长交集最弱增长余量',A,'min(annualRevYoY,currentRevYoY-20,currentParentNIYoY,annualParentNIYoY-40) WHERE all four source gates',COMMON+' NEW equal-percentpoint weakest-leg rank extension, absent original source ranking, direction fixed before outcomes.'),
 spec('small82_parent_annual_current_min_extension','归母利润年度当期稳健增长',A,'min(currentParentNIYoY,annualParentNIYoY) WHERE all four source gates',COMMON+' NEW conservative parentNI growth rank extension; original source uses only size rank.')]
for sp in SPECS:sp['gated']=True

def growth(a,b):
 return (a-b)/abs(b)*100 if np.isfinite(a) and np.isfinite(b) and abs(b)>1e-12 else np.nan

def snapshots(table,dates,stocks):
 out=np.full((len(dates),len(stocks),4),np.nan)
 for symbol,g in table.groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  g=g.sort_values(['ann_date','end_date','update_flag']);ann=g.ann_date.to_numpy();ends=pd.PeriodIndex(g.end_date,freq='Q-DEC');v=g[['revenue','n_income_attr_p']].to_numpy(float);reports={};at=0
  for i,d in enumerate(dates):
   while at<len(g) and ann[at]<=d.to_datetime64():reports[ends[at]]=v[at];at+=1
   if not reports:continue
   current=max(reports);years=[k for k in reports if k.quarter==4]
   if not years:continue
   annual=max(years);new=reports[current];old=reports.get(current-4,np.array([np.nan,np.nan]));an=reports[annual];ao=reports.get(annual-4,np.array([np.nan,np.nan]))
   out[i,j]=[growth(an[0],ao[0]),growth(new[0],old[0]),growth(new[1],old[1]),growth(an[1],ao[1])]
 return out

def values(x,cap):
 a,b,c,d=np.moveaxis(x,-1,0);good=(a>0)&(b>20)&(c>0)&(d>40)
 return [np.where(good,-cap,np.nan),np.where(good,np.minimum.reduce([a,b-20,c,d-40]),np.nan),np.where(good,np.minimum(c,d),np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,fields=FIELDS,platform_compute=0,selection='annual Q4 and current YTD,absdenominator and extensiondirections before outcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldfields=q.FIN_FIELDS
 try:q.FIN_FIELDS=FIELDS;table=q.pit_tables()['income']
 finally:q.FIN_FIELDS=oldfields
 q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),stocks=list(stocks),rule=q.ALIGNMENT_RULE_VERSION))
 cache=SCHEMA/'annual_current_growth.npy'
 if cache.exists():x=np.load(cache)
 else:x=snapshots(table,dates,stocks);np.save(cache,x)
 ids=np.arange(128);checks=[]
 for n in [35,79]:
  sub=table[(table.ann_date<=dates[n-1])&table.instrument.isin(stocks[ids])];cut=snapshots(sub,dates[:n],stocks[ids])
  np.testing.assert_allclose(x[:n,ids],cut,equal_nan=True,atol=1e-8);checks.append(dict(test='raw_announced_filing_prefix_replay',cutoff=str(dates[n-1]),finite=int(np.isfinite(cut).sum()),passed=True))
 # A revision to last year's Q4 cannot replace a newer annual anchor.
 toy=pd.DataFrame(dict(instrument=['X']*6,ann_date=pd.to_datetime(['20210301','20220301','20220501','20230301','20230501','20230502']),end_date=pd.to_datetime(['20201231','20211231','20220331','20221231','20211231','20230331']),update_flag=[0,0,0,0,1,0],revenue=[100,120,20,180,150,30],n_income_attr_p=[10,20,2,40,25,3]))
 got=snapshots(toy,pd.DatetimeIndex(['20230315','20230601']),pd.Index(['X']))[:,0]
 np.testing.assert_allclose(got[0],[50,50,100,100]);np.testing.assert_allclose(got[1],[20,50,50,60]);assert growth(5,-10)==150 and np.isnan(growth(5,0))
 checks.append(dict(test='annual_current_anchor_and_late_older_revision_and_loss_recovery_toy',passed=True))
 vals=values(x,f['cap'][pos]);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
 q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON,benchmark_warning='qualification subset; not unconstrained fullA portfolio excess'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED134',flush=True)
if __name__=='__main__':main()
