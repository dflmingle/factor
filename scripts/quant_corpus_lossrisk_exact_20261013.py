"""Calendar PIT three-loss-year risk and weakest-year profit source86 proxies."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略1/86.根据连续亏损预判st股票.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source86-20261013'
FIELDS={'income':['n_income'],'fina_indicator':['q_dtprofit'],'balancesheet':['total_assets']}
SPECS=[
 spec('st_threeannual_loss_risk_low','三个已披露年度连亏风险反向',SRC,'-I(all3years(min(annualNI, sum4quarterDeductedNI))<0); latest three complete PIT annual years',
 'proxy: source three annual minloss idea generalized to latest three full announced annual reports; no forecasts/audit/ST/listing filters available; sparse binary ties cannot establish standalone alpha; original fixed2022calendar and Nov-Feb screening not claimed'),
 spec('st_threeannual_weakest_profitability','三个披露年度最弱盈利资产比',SRC,'min_y(latest3fullAnnual, min(annualNI, sum4quarterDeductedNI)/sameyearAnnualAssets)',
 'proxy: new continuous quality adaptation of disclosed three-year risk mechanism; exact actual announcement/revision replay and coherent samequarter dtprofit/income/yearendassets; no forecast or audit substitute'),
 spec('st_q3_priorq4_lossrisk_low','前三季加前年度末季连亏风险反向',SRC,'-I(all3year minloss<0); latest year=Q1+Q2+Q3 + PRIORyearQ4, earlier2fullAnnual',
 'proxy: source explicit priorQ4 estimate retained for newestyear; each stock uses latest jointly disclosed Q3 not fixed2022dates, no forecast removal; if actual newannual is positive, source actualannual removal retained; no ST designation claims'),
 spec('st_q3_priorq4_weakest_profitability','前三季加前末季最弱年度盈利',SRC,'min(threeyear min(NI,deductedNI)/matchinglatestAnnualAssets), latestestimated=Q1..3+priorQ4',
 'proxy: new continuous adaptation of literal source Q4 estimate, calendar latestjointQ3 and sameyear annualassets for pastyears/latestknownAnnualAssets for estimatedyear; no interim denominators')]

def rebuild(tables,grid,stocks):
 out=np.full((4,len(grid),len(stocks)),np.nan)
 groups={ep:{s:g.sort_values(['ann_date','end_date','update_flag']) for s,g in t.groupby('instrument',sort=False)} for ep,t in tables.items()}
 for j,symbol in enumerate(stocks):
  events={ep:[(r['ann_date'],pd.Period(r['end_date'],freq='Q-DEC'),r) for r in groups[ep].get(symbol,pd.DataFrame()).to_dict('records')] for ep in tables}
  at={ep:0 for ep in tables};reports={ep:{} for ep in tables}
  for i,date in enumerate(grid):
   for ep,rows in events.items():
    while at[ep]<len(rows) and rows[at[ep]][0]<=date:
     _,end,r=rows[at[ep]];reports[ep][end]=r;at[ep]+=1
   ni=reports['income'];dp=reports['fina_indicator'];bs=reports['balancesheet']
   def raw(reps,end,col):return float(reps.get(end,{}).get(col,np.nan))
   def quarter(end):
    n=raw(ni,end,'n_income')
    if end.quarter!=1:n-=raw(ni,end-1,'n_income')
    return np.array([n,raw(dp,end,'q_dtprofit')])
   def annual(y):return np.sum([quarter(pd.Period(f'{y}Q{k}',freq='Q-DEC')) for k in [1,2,3,4]],axis=0)
   annualyears=sorted({p.year for p in ni if p.quarter==4 and p in bs and p in dp})
   if len(annualyears)>=3:
    y=annualyears[-1];av=np.array([annual(y-k) for k in range(3)]);den=np.array([raw(bs,pd.Period(f'{y-k}Q4',freq='Q-DEC'),'total_assets') for k in range(3)])
    if np.isfinite(av).all() and np.isfinite(den).all() and (den>0).all():
     mins=av.min(axis=1);out[0,i,j]=-float((mins<0).all());out[1,i,j]=np.min(mins/den)
   q3years=sorted({p.year for p in ni if p.quarter==3 and p in dp})
   if not q3years or not annualyears:continue
   y=q3years[-1]
   est=np.sum([quarter(pd.Period(f'{y}Q{k}',freq='Q-DEC')) for k in [1,2,3]],axis=0)+quarter(pd.Period(f'{y-1}Q4',freq='Q-DEC'))
   av=np.array([est,annual(y-1),annual(y-2)])
   den=np.array([raw(bs,pd.Period(f'{annualyears[-1]}Q4',freq='Q-DEC'),'total_assets'),raw(bs,pd.Period(f'{y-1}Q4',freq='Q-DEC'),'total_assets'),raw(bs,pd.Period(f'{y-2}Q4',freq='Q-DEC'),'total_assets')])
   if np.isfinite(av).all() and np.isfinite(den).all() and (den>0).all():
    mins=av.min(axis=1);actual=annual(y)
    removed=np.isfinite(actual).all() and actual.min()>0
    out[2,i,j]=-float((mins<0).all() and not removed);out[3,i,j]=np.min(mins/den)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all4 definitions fixed exante, no outcome directionselection')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);old=q.FIN_FIELDS
 try:
  q.FIN_FIELDS=FIELDS;tables=q.pit_tables();ids=np.arange(512);small={ep:t[t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
  full=rebuild(small,grid,stocks[ids]);checks=[]
  for n in [35,79]:
   cutoff=grid[n-1];cut=rebuild({ep:t[t.ann_date<=cutoff] for ep,t in small.items()},grid[:n],stocks[ids])
   np.testing.assert_allclose(full[:,:n],cut,equal_nan=True,atol=1e-8)
   checks.append(dict(test='raw_announcement_cutoff_calendar_reports_revision_YTDdiff',stocks=512,cutoff=str(cutoff),finite=int(np.isfinite(cut).sum()),passed=True))
  # Calendar reconstruction: Q3 estimate uses previous Q4 and revisions update past quarters causally.
  rows={ep:[] for ep in FIELDS};sym='toy.SH'
  for y in [2019,2020,2021,2022]:
   for k in [1,2,3,4]:
    if y==2022 and k==4:continue
    end=pd.Period(f'{y}Q{k}',freq='Q-DEC').end_time.normalize();ann=end+pd.Timedelta(days=30)
    base=dict(instrument=sym,end_date=end,ann_date=ann,update_flag='0')
    rows['income'].append(dict(**base,n_income=-10*k));rows['fina_indicator'].append(dict(**base,q_dtprofit=-12));rows['balancesheet'].append(dict(**base,total_assets=100))
  tab={ep:pd.DataFrame(r) for ep,r in rows.items()};toy=rebuild(tab,pd.DatetimeIndex(['2022-11-02']),pd.Index([sym]));np.testing.assert_allclose(toy[:,0,0],[-1,-.48,-1,-.48])
  checks.append(dict(test='independent_toy_singlequarter_YTD_and_priorQ4_estimate',passed=True))
  cache=OUT/'raw_calendar_panels.pkl'
  if cache.exists():v=pd.read_pickle(cache)
  else:v=rebuild(tables,grid,stocks);pd.to_pickle(v,cache)
 finally:q.FIN_FIELDS=old
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,list(v),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='calendar announced financial proxies; not source ST classifier',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED86',flush=True)
if __name__=='__main__':main()
