"""Five-quarter signed-root growth and source PB/deducted-ROE score."""
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
GROWTH='quant/2022年度精选策略/30.优质股高抛低吸策略.txt'
VALUE='quant/2022年度精选策略/48.买不到710亿爆款基金怎么办？自己做一个量化价值成长策略吧.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source49-20261013'
SPECS=[
 spec('signed_root_growth5','五季符号平方根成长',GROWTH,'rank(sum0..4(sign(tr_yoy)*sqrt(abs(tr_yoy))))+rank(sum0..4(sign(netprofit_yoy)*sqrt(abs(netprofit_yoy))))',
      'proxy: growth-only extraction from source4rank financial_factor; reported YTD vendor YoY; missing preserved, zero sign-root0 continuous extension rather than source0/0'),
 spec('financial_growth4_source','五季成长每股价值四秩',GROWTH,'rank(EPS_TTM)+rank(BPS)+rank(signed_root_sales5)+rank(signed_root_profit5); optional source explicit score NaN->0 only after existing current financial coverage',
      'proxy: source descending feature rank then ascending aggregate means high4legs; EPS_TTM=parent_NI_TTM/totalshares; BPS=equity/totalshares; source same-value symbol tie order not reconstructed; fullA rather than top500 strength gate'),
 spec('pb_deducted_roe_scaled_source','PB扣非ROE截面比例分',VALUE,'roe_annual=roe_dt if latest reportQ4 else4*roe_dt; gates 0<PB<10,0<roe_annual<1000; score=-(PB-stdPB)/meanPB+(roe_annual-stdROE)/meanROE',
      'proxy: Tushare YTD roe_dt for JQ inc_return; original non-Q4 multiplier4 preserved even for Q2/Q3; fullA replaces ZZ800 and quarter scheduling'),
]

def build(fin,cap,quarters):
 def g(ep,c,k=0):return fin[f'{ep}.{c}.q{k}'].astype(float)
 def root(c):
  x=np.stack([g('fina_indicator',c,k) for k in range(5)])
  return np.sum(np.sign(x)*np.sqrt(np.abs(x)),axis=0)
 sales=root('tr_yoy');profit=root('netprofit_yoy');growth=q.rank(sales)+q.rank(profit)
 ni=g('income','n_income_attr_p_ttm');eq=g('balancesheet','total_hldr_eqy_exc_min_int');shares=g('balancesheet','total_share')*10000
 eps=q.ratio(ni,shares);bps=q.ratio(eq,shares)
 known=np.isfinite(ni)&np.isfinite(eq)&(shares>0)
 four=sum(q.rank(np.where(known,np.nan_to_num(x,nan=0),np.nan)) for x in [eps,bps,sales,profit])
 pb=q.ratio(cap*10000,eq);roe=g('fina_indicator','roe_dt')*np.where(quarters==4,1,4)
 valid=(pb>0)&(pb<10)&(roe>0)&(roe<1000);a=np.where(valid,pb,np.nan);b=np.where(valid,roe,np.nan)
 score=-q.ratio(a-np.nanstd(a,axis=1,ddof=1)[:,None],np.nanmean(a,axis=1)[:,None])+q.ratio(b-np.nanstd(b,axis=1,ddof=1)[:,None],np.nanmean(b,axis=1)[:,None])
 return [growth,four,score]

def report_quarters(table,grid,stocks):
 out=np.full((len(grid),len(stocks)),np.nan)
 for symbol,t in table.groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  rows=list(t.sort_values(['ann_date','end_date','update_flag'])[['ann_date','end_date']].itertuples(index=False,name=None));at=0;latest=None
  for i,d in enumerate(grid):
   while at<len(rows) and rows[at][0]<=d:
    latest=max(latest,rows[at][1]) if latest is not None else rows[at][1];at+=1
   if latest is not None:out[i,j]=(latest.month-1)//3+1
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source-fixed before evaluation',platform_compute=0)
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(path,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 base=q.financial_snapshot(grid,stocks);oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 schema=q.ROOT/'research_reports/platform_alignment/quant-corpus-growth-schema-20261013';schema.mkdir(exist_ok=True)
 try:
  q.OUT=schema;q.FIN_FIELDS={'fina_indicator':['tr_yoy','netprofit_yoy','roe_dt']}
  extra=q.financial_snapshot(grid,stocks,lags=5);tables=q.pit_tables();quarters=report_quarters(tables['fina_indicator'],grid,stocks)
  fin={**base,**extra};values=build(fin,f['cap'][pos],quarters);checks=[];ids=np.arange(128)
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='raw-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);replay=q.financial_snapshot(grid[:n],stocks[ids],lags=5)
    small={k:v[:n,ids] for k,v in fin.items()};quarter=report_quarters(sub['fina_indicator'],grid[:n],stocks[ids])
    a=build(small,f['cap'][pos[:n]][:,ids],quarters[:n,ids]);b=build({**small,**replay},f['cap'][pos[:n]][:,ids],quarter)
    for sp,x,y in zip(SPECS,a,b):
     np.testing.assert_allclose(x,y,equal_nan=True,rtol=1e-6,atol=1e-6);assert np.isfinite(y).any()
     checks.append(dict(key=sp['key'],test='raw_fina_filing_cutoff_replay',cutoff=str(cutoff),passed=True))
  q.OUT=oldout;q.pit_tables=loader
  run(OUT,SPECS,values,cal,stocks,f,checks,dict(fidelity='PIT financial vendor proxies',gated_benchmark='pb_deducted_roe scaled uses qualification-subset benchmark',statistics='exploratory no independent OOS',verification_limit='raw cutoff replay for new growth/ROE fields; existing cached base accounting fields were checked in earlier cohorts'))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED49',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
