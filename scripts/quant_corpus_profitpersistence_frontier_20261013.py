"""Six PIT quarter deducted-profit growth and actual turnover/value intersections."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
S97='quant/2021年度精选策略/97.稳定高回报周期股策略2-RSRS择时.txt'
S85='quant/2024年度精选策略2/85.价值策略重开，再次向Jqz1226致敬.txt'
S87='quant/2021年度精选策略/87.穿越牛熊基业长青的价值精选策略（小资本也有大作为）.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source70-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-profitpersistence-schema-20261013'
FIELDS={'fina_indicator':['q_dtprofit','roe','or_yoy','eps'], 'income':['revenue','n_income','n_income_attr_p'],
 'balancesheet':['total_assets','total_liab','notes_receiv','accounts_receiv','adv_receipts','total_cur_assets','total_cur_liab'], 'cashflow':['n_cashflow_act']}
SPECS=[
 spec('deducted_profit_halfyear_growth','扣非利润半年度环比',S97,'(q_dtprofit.q0+q1)/(q2+q3); denominator!=0','proxy: continuous source hb atom; reported single-quarter deductedprofit substitutesvendoradjusted_profit; sixquarter PIT completeness'),
 spec('deducted_profit_halfyear_yoy','扣非利润半年度同比',S97,'(q_dtprofit.q0+q1)/(q4+q5); denominator!=0','proxy: continuous source tb atom; retained ratio across signed profits, no automatic positive-growth gate'),
 spec('growthvalue97_actual_qualified','周期股九十七实际成长价值交集',S97,'rank(deductedEP)+.3rank(hb)+.5rank(tb); YTDNI>0,0<PE<25,debt/assets<.9,0<deductedPE<20,receivableturn>6 or<=0',
 'proxy: original sixquarter profits and4quarter revenue reconstructed singlequarter; latest PIT reports with no null0 fill; receivable accounts+notes-advreceipt denominator0->inf exactly; historical industry/listing/ST,indexRSRS/execution omitted; qualified benchmark'),
 spec('growthvalue85_actual_qualified','价值重开八十五实际交集',S85,'rank(deductedEP)+.5rank(hb)+.4rank(tb); same source97 gates except PE<35',
 'proxy: distinct source85 weights and PE cap retained, quarterly PIT and fullA adaptations same97; marketPE regime/7day20pct momentum/longhu/ETF execution omitted'),
 spec('quality87_literal_qualified_lowshares','价值八十七实际低股数交集',S87,'low totalshares on MV>mean,q3currentratio>mean,all4ROE>mean,oldestannual y-3OCF>0,all4(0<revgrowth<50 and .04<EPS<.5)',
 'proxy: source l4 overwritten eachyear hence onlyy-3OCF survives; computed FCF unused; ascending circulating_cap replaced totalMV/rawClose shares proxy; sourcecircMV gate ->totalMV; PITlatestquarters'),
]
for s in SPECS[2:]:s['gated']=True

def oldest(tables,grid,stocks):
 out=np.full((len(grid),len(stocks)),np.nan);table=tables['cashflow'];table=table[table.end_date.dt.month.eq(12)&table.end_date.dt.day.eq(31)]
 for symbol,g in table.groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  g=g.sort_values(['ann_date','end_date','update_flag']);ann=g.ann_date.to_numpy();years=g.end_date.dt.year.to_numpy();vals=g.n_cashflow_act.to_numpy();at=0;reports={}
  for i,date in enumerate(grid):
   while at<len(g) and ann[at]<=date.to_datetime64():reports[int(years[at])]=vals[at];at+=1
   out[i,j]=reports.get(date.year-3,np.nan)
 return out

def values(fin,old,f,pos):
 def g(ep,col,k=0):return fin[f'{ep}.{col}.q{k}'].astype(float)
 p=[g('fina_indicator','q_dtprofit',k) for k in range(6)]
 hb=q.ratio(p[0]+p[1],p[2]+p[3]);tb=q.ratio(p[0]+p[1],p[4]+p[5]);profit=sum(p[:4]);mv=f['cap'][pos].astype(float)*10000
 a=g('balancesheet','total_assets');li=g('balancesheet','total_liab');pe=q.ratio(mv,g('income','n_income_attr_p_ttm'));dpe=q.ratio(mv,profit)
 ar=np.mean(np.stack([g('balancesheet','accounts_receiv',k)+g('balancesheet','notes_receiv',k)-g('balancesheet','adv_receipts',k) for k in range(4)]),axis=0)
 # zero denominator maps to infinity, source turnover then equals0.
 turn=q.ratio(g('income','revenue_ttm'),np.where(ar==0,np.inf,ar));base=(g('income','n_income')>0)&(pe>0)&(q.ratio(li,a)<.9)&(dpe>0)&(dpe<20)&((turn>6)|(turn<=0))
 out=[]
 for maxpe,wh,wt in [(25,.3,.5),(35,.5,.4)]:
  good=base&(pe<maxpe)&np.isfinite(hb)&np.isfinite(tb)
  ep=np.where(good,-dpe,np.nan);hh=np.where(good,hb,np.nan);tt=np.where(good,tb,np.nan)
  out.append(q.rank(ep)+wh*q.rank(hh)+wt*q.rank(tt))
 roe=np.stack([g('fina_indicator','roe',k) for k in range(4)],axis=-1);growth=np.stack([g('fina_indicator','or_yoy',k) for k in range(4)],axis=-1);eps=np.stack([g('fina_indicator','eps',k) for k in range(4)],axis=-1)
 cr=q.ratio(g('balancesheet','total_cur_assets',3),g('balancesheet','total_cur_liab',3));cap=f['cap'][pos]
 good=(cap>np.nanmean(cap,axis=1)[:,None])&(cr>np.nanmean(cr,axis=1)[:,None])&(roe>np.nanmean(roe,axis=1)[:,None,:]).all(axis=-1)&(old>0)&((growth>0)&(growth<50)).all(axis=-1)&((eps>.04)&(eps<.5)).all(axis=-1)
 shares=-q.ratio(cap,f['raw_close'][pos]);out.append(np.where(good,shares,np.nan))
 return [hb,tb,*out]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),lags=6,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(grid,stocks,lags=6);tables=q.pit_tables();ann=oldest(tables,grid,stocks);checks=[]
  ids=np.arange(512);small={k:v[:,ids] for k,v in f.items()};whole=values({k:v[:,ids] for k,v in fin.items()},ann[:,ids],small,pos)
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='profit-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(grid[:n],stocks[ids],lags=6);cut=values(cf,oldest(sub,grid[:n],stocks[ids]),small,pos[:n])
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='raw_filing_cutoff_and_annual_revision_replay',nonempty=int(np.isfinite(b).sum()),cutoff=str(cutoff),passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,ann,f,pos)
  q.dump(OUT/'qualification_coverage.json',{s['key']:np.isfinite(v).sum(axis=1).tolist() for s,v in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='PIT singlequarter field/source qualified adaptations',statistics='exploratory no untouched OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED70',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
