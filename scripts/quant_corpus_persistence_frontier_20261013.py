"""Annual PIT cash persistence and literal flawed quality-source intersections."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
S35='quant/2021年度精选策略/35.精选价值策略.txt'
S54='quant/2021年度精选策略/54.价值投资策略-大盘择时.txt'
S55='quant/2021年度精选策略/55.价值投资改进版-6年9.5倍.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source62-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-persistence-schema-20261013'
FIELDS={'fina_indicator':['roe','eps','or_yoy','netprofit_yoy'],'balancesheet':['total_cur_assets','total_cur_liab','total_assets'],'income':['n_income'],'cashflow':['n_cashflow_act','n_cashflow_inv_act']}
SPECS=[
 spec('roe_fourquarter_min_cs_z','四季度持续高股东回报',S35,'min_q0..q3(CSz(ROE_q))',
      'proxy: continuous weakest-quarter cross-sectional ROE strength; latest4PIT quarters replace fixed source report-calendar and hard mean thresholds; no size term'),
 spec('cash_operating_investing_annual3_min','三年经营投资净现金最弱年',S35,'min3annual((OCF+ICF)/current_assets); annual years y-1..y-3 afterMay, else y-2..y-4',
      'proxy: literal source cash OCF+ICF sum retained despite FCF comment; current-assets scale added for comparability, calendar-year filings only known by signal, strict3years no zero-fill'),
 spec('quality35_literal_qualified_large','价值三十五实际交集大盘',S35,'high totalMV on MV>mean, currentratio>mean, all4ROE>=eachmean, annual3(OCF+ICF)>0, all4(6<revenue_yoy<50), q3profit_yoy>6',
      'proxy: literal df6=df5.merge(df64) bug retains only fourth profit filter; totalMV substitutescircMV, PITlatest4quarters substitute sourcecalendar report requests, sourceindustry/ST/execution omitted'),
 spec('quality54_literal_qualified_shares','价值五十四实际交集股数',S54,'high(totalMV/rawClose) on q3currentratio>mean, all4ROE>mean, annual_y-3(OCF-ICF)>1e6, all4(15<revenue_yoy<50 and .08<EPS<.5)',
      'proxy: l1 size threshold calculated but absent from return; l4 overwritten eachyear hence only oldest year survives; total shares proxy replacescirculating_cap, latestPIT quarters and one calendar annual date; index RSI1000 state and weekly execution omitted'),
 spec('quality55_literal_qualified_shares','价值五十五实际交集股数',S55,'quality54 qualification plus totalMV>mean; high(totalMV/rawClose)',
      'proxy: actual size gate included, source l4 overwrite retained; total shares proxy replacescirculating_cap, PITlatestquarters rather than source statDate; alternatemonth selection/execution and index timing omitted'),
]
for s in SPECS[2:]:s['gated']=True

def annual(tables,grid,stocks):
 table=tables['cashflow'];table=table[table.end_date.dt.month.eq(12)&table.end_date.dt.day.eq(31)]
 sums=np.full((len(grid),len(stocks),3),np.nan);old=np.full((len(grid),len(stocks)),np.nan)
 for symbol,g in table.groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  g=g.sort_values(['ann_date','end_date','update_flag']);ann=g.ann_date.to_numpy();years=g.end_date.dt.year.to_numpy();v=g[['n_cashflow_act','n_cashflow_inv_act']].to_numpy();at=0;reports={}
  for i,d in enumerate(grid):
   while at<len(g) and ann[at]<=d.to_datetime64():reports[int(years[at])]=v[at];at+=1
   base=d.year-1 if d.month>=5 else d.year-2
   for k in range(3):
    if base-k in reports:sums[i,j,k]=np.sum(reports[base-k])
   if d.year-3 in reports:old[i,j]=reports[d.year-3][0]-reports[d.year-3][1]
 return sums,old

def values(fin,ann,f,pos):
 def a(ep,col,k=0):return fin[f'{ep}.{col}.q{k}'].astype(float)
 roe=np.stack([a('fina_indicator','roe',k) for k in range(4)],axis=-1);growth=np.stack([a('fina_indicator','or_yoy',k) for k in range(4)],axis=-1);eps=np.stack([a('fina_indicator','eps',k) for k in range(4)],axis=-1)
 z=np.stack([q.zscore(roe[:,:,k]) for k in range(4)],axis=-1);persist=np.min(z,axis=-1)
 cash3,old=ann;cashmin=q.ratio(np.min(cash3,axis=-1),a('balancesheet','total_assets'))
 cap=f['cap'][pos].astype(float);r0=q.ratio(a('balancesheet','total_cur_assets'),a('balancesheet','total_cur_liab'));r3=q.ratio(a('balancesheet','total_cur_assets',3),a('balancesheet','total_cur_liab',3));rmean=np.nanmean(roe,axis=1)[:,None,:]
 above=(roe>rmean).all(axis=-1);g35=(cap>np.nanmean(cap,axis=1)[:,None])&(r0>np.nanmean(r0,axis=1)[:,None])&(roe>=rmean).all(axis=-1)&(cash3>0).all(axis=-1)&((growth>6)&(growth<50)).all(axis=-1)&(a('fina_indicator','netprofit_yoy',3)>6)
 common=(r3>np.nanmean(r3,axis=1)[:,None])&above&(old>1e6)&((growth>15)&(growth<50)).all(axis=-1)&((eps>.08)&(eps<.5)).all(axis=-1)
 shares=q.ratio(cap,f['raw_close'][pos]);v35=np.where(g35,cap,np.nan);v54=np.where(common,shares,np.nan);v55=np.where(common&(cap>np.nanmean(cap,axis=1)[:,None]),shares,np.nan)
 return [persist,cashmin,v35,v54,v55]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,fields=FIELDS,selection='source flaws retained and proxies fixed before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=4,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=4);tables=q.pit_tables();ann=annual(tables,grid,stocks);checks=[]
  ids=np.arange(512);small={k:v[:,ids] for k,v in f.items()};sf={k:v[:,ids] for k,v in fin.items()};sa=(ann[0][:,ids],ann[1][:,ids]);whole=values(sf,sa,small,pos)
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='annual-quarter-PIT-',dir=OUT) as temp:
    q.OUT=Path(temp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=4);ca=annual(sub,grid[:n],stocks[ids]);cut=values(cf,ca,small,pos[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-5,rtol=1e-5);checks.append(dict(key=sp['key'],test='raw_annual_revision_and_quarter_cutoff_replay',cutoff=str(cutoff),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,ann,f,pos)
  q.dump(OUT/'qualification_coverage.json',{s['key']:dict(signal_stock_counts=np.isfinite(v).sum(axis=1).tolist(),signals_atleast100=int((np.isfinite(v).sum(axis=1)>=100).sum())) for s,v in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no independent OOS',fidelity='source literal faulty intersections plus continuous quality atoms; full strategies not reproduced',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED62',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
