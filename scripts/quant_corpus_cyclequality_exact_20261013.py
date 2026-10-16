"""Source31 six coherent PIT quarters and literal within-report fillna0.

Align all three statements to latest income report period, not independently
latest financial endpoint periods. No zero-filling an absent quarter/report.
"""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
SOURCE='quant/2021年度精选策略/31.RSRS择时+货币基金--6年8倍行业周期股策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source79-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-cyclequality-coherent-schema-20261013'
FIELDS={'fina_indicator':['q_dtprofit'],'income':['revenue','n_income','n_income_attr_p'],
 'balancesheet':['total_assets','total_liab','notes_receiv','accounts_receiv','adv_receipts']}
SPECS=[
 spec('cycle31_growthvalue_coherent_unqualified','周期股三十一同报告期成长价值分',SOURCE,
 'rank(-deductedPE)+.5rank(hb)+.4rank(tb);6positivequarterdeductedprofits/revenue, coherentperiodmatching; no value/AR gates',
 'proxy: available prequalification source score; positive6quarters source quality retained, quarter profit Tushare q_dtprofit; JQ ordinalrank->CSpercentilerank. All statements coherent with incomeperiod; whole strategy indexRSRS/PITindustry/listing/ST/monthlybuffer omitted'),
 spec('cycle31_growthvalue_fill0_qualified','周期股三十一填零和应收交集',SOURCE,
 'same score on YTDNI>0,0<PE<25,debt/assets<.9,0<deductedPE<20,receivableturn>6;receivable<=0 turnover100, explicit available-report null0',
 'proxy: actual source31 .5/.4 weights, sixpositivequarters, PE25/deductedPE20/AR>6 intersection, AR<=0->100; only present matching report optionalAR fields fill0. Qualified factor_valid subset benchmark; industry exclusions/listing500days/indexRSRS/source5stock portfolio omitted')]
for sp in SPECS:sp['gated']=True

def coherent(tables,grid,stocks):
 names=['profit','revenue','ni_parent','ytd_ni','assets','liab','ar'];out={n:np.full((len(grid),len(stocks),6),np.nan) for n in names}
 grouped={ep:{s:g.sort_values(['ann_date','end_date','update_flag']) for s,g in tab.groupby('instrument',sort=False)} for ep,tab in tables.items()}
 for j,symbol in enumerate(stocks):
  events={};reports={ep:{} for ep in tables};at={ep:0 for ep in tables}
  for ep in tables:
   tab=grouped[ep].get(symbol)
   if tab is None:events[ep]=[];continue
   events[ep]=[(r['ann_date'],pd.Period(r['end_date'],freq='Q-DEC'),r) for r in tab.to_dict('records')]
  for i,d in enumerate(grid):
   for ep,rows in events.items():
    while at[ep]<len(rows) and rows[at[ep]][0]<=d:
     _,end,r=rows[at[ep]];reports[ep][end]=r;at[ep]+=1
   inc=reports['income'];bs=reports['balancesheet'];fi=reports['fina_indicator']
   if not inc:continue
   current=max(inc)
   for k in range(6):
    end=current-k;r=inc.get(end);b=bs.get(end);v=fi.get(end)
    # Missing whole report is not an explicit source zero.
    if r is None or b is None or v is None:continue
    def raw(row,col):return float(row.get(col,np.nan))
    def present0(row,col):
     x=raw(row,col);return x if np.isfinite(x) else 0.
    old=inc.get(end-1)
    for name,col in [('revenue','revenue'),('ni_parent','n_income_attr_p')]:
     a=raw(r,col)
     value=a if end.quarter==1 else a-raw(old,col) if old is not None else np.nan
     out[name][i,j,k]=value
    out['profit'][i,j,k]=raw(v,'q_dtprofit')
    out['ytd_ni'][i,j,k]=raw(r,'n_income')
    out['assets'][i,j,k]=raw(b,'total_assets');out['liab'][i,j,k]=raw(b,'total_liab')
    out['ar'][i,j,k]=present0(b,'notes_receiv')+present0(b,'accounts_receiv')-present0(b,'adv_receipts')
 return out

def values(x,cap):
 p=x['profit'];rv=x['revenue'];valid=(p>0).all(axis=-1)&(rv>0).all(axis=-1)
 hb=q.ratio(p[:,:,0]+p[:,:,1],p[:,:,2]+p[:,:,3]);tb=q.ratio(p[:,:,0]+p[:,:,1],p[:,:,4]+p[:,:,5]);mv=cap*10000
 dp=p[:,:,:4].sum(axis=-1);dpe=q.ratio(mv,dp);pe=q.ratio(mv,x['ni_parent'][:,:,:4].sum(axis=-1))
 ar=x['ar'][:,:,:4].mean(axis=-1);art=np.where(ar<=0,100,q.ratio(rv[:,:,:4].sum(axis=-1),ar))
 good=valid&(x['ytd_ni'][:,:,0]>0)&(pe>0)&(pe<25)&(q.ratio(x['liab'][:,:,0],x['assets'][:,:,0])<.9)&(dpe>0)&(dpe<20)&(art>6)
 def score(mask):return q.rank(np.where(mask,-dpe,np.nan))+.5*q.rank(np.where(mask,hb,np.nan))+.4*q.rank(np.where(mask,tb,np.nan))
 return [score(valid),score(good)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,coherent_anchor='latest announced income report quarter',fill0='optional receivables only within present matched balance report')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 oldfields=q.FIN_FIELDS
 try:
  q.FIN_FIELDS=FIELDS;tables=q.pit_tables();ids=np.arange(512);small={ep:t[t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
  whole=coherent(small,grid,stocks[ids]);wholevalues=values(whole,f['cap'][pos][:,ids]);checks=[]
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[t.ann_date<=cutoff] for ep,t in small.items()};cut=coherent(sub,grid[:n],stocks[ids]);vv=values(cut,f['cap'][pos[:n]][:,ids])
   for key in whole:np.testing.assert_allclose(whole[key][:n],cut[key],equal_nan=True,atol=1e-6)
   for sp,a,b in zip(SPECS,wholevalues,vv):
    np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6);checks.append(dict(key=sp['key'],test='coherent_report_PIT_raw_filing_cutoff_revision_and_YTDquarter_replay',cutoff=str(cutoff),finite_values=int(np.isfinite(b).sum()),passed=True))
  # Later revision to an old Q cannot make it replace the latest report anchor.
  t=pd.Timestamp('2021-09-07');s='toy.SH'
  def table(rows):return pd.DataFrame([dict(instrument=s,update_flag='0',**r) for r in rows])
  irows=[dict(ann_date=t-pd.Timedelta(days=30),end_date=pd.Timestamp('2021-03-31'),revenue=100,n_income=10,n_income_attr_p=9),dict(ann_date=t-pd.Timedelta(days=20),end_date=pd.Timestamp('2021-06-30'),revenue=250,n_income=25,n_income_attr_p=23),dict(ann_date=t-pd.Timedelta(days=1),end_date=pd.Timestamp('2021-03-31'),revenue=110,n_income=12,n_income_attr_p=11)]
  brow=[dict(ann_date=t-pd.Timedelta(days=10),end_date=pd.Timestamp('2021-06-30'),total_assets=300,total_liab=100,notes_receiv=np.nan,accounts_receiv=20,adv_receipts=np.nan)]
  firow=[dict(ann_date=t-pd.Timedelta(days=10),end_date=pd.Timestamp('2021-06-30'),q_dtprofit=13)]
  toy=coherent({'income':table(irows),'balancesheet':table(brow),'fina_indicator':table(firow)},pd.DatetimeIndex([t]),pd.Index([s]))
  assert toy['revenue'][0,0,0]==140 and toy['ar'][0,0,0]==20 and np.isnan(toy['ar'][0,0,1])
  checks.append(dict(test='independent_oldquarter_revision_differencing_optional0_and_absentreport_NaN',passed=True))
  cache=SCHEMA/'coherent_snapshots.pkl'
  if cache.exists():x=pd.read_pickle(cache)
  else:x=coherent(tables,grid,stocks);pd.to_pickle(x,cache)
  q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),rule=q.ALIGNMENT_RULE_VERSION,anchor='latestincome',report_matching=True));vals=values(x,f['cap'][pos])
  q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(v).sum(axis=1).tolist() for sp,v in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='coherent PIT sourcequarter adaptation, optional explicitsourcezero',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED79',flush=True)
 finally:q.FIN_FIELDS=oldfields

if __name__=='__main__':main()
