"""Untested EPS PEG and causal cross-sectional OLS source recipes. Offline only."""
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
SLATER='quant/2020年度精选策略/23 Principle by Jim Slater 祖鲁法则在A股的实现与改进.txt'
LYNCH='quant/2022年度精选策略/11.林奇PEG选股轮动，十年20倍，有止损模块.txt'
OLS='quant/2021年度精选策略/39.因子分析系列文章（八）：多因子策略（多元线性回归）.txt'
SPECS={43:[
 spec('slater_annual_eps_peg','祖鲁年度EPS估值',SLATER,'-PE_TTM/(100*(EPS_calendar_year_minus2/EPS_calendar_year_minus3-1)); 0<PEG<5',
      'proxy: exact source last loop year Y-2 and Y-3 annual EPS, NOT four-year average; Tushare PIT annual EPS and PE_TTM; original preceding PB20%/RS/universe omitted'),
 spec('lynch_pit_eps_peg','林奇历史快照EPS估值',LYNCH,'-PE_TTM/(100*(latest_PIT_reported_EPS/latest_PIT_EPS_asof_signal_minus365days-1)); both EPS>0,growth>0,PE>0,BM>0',
      'proxy: historical-date PIT snapshot rather than quarter-lag4; reported YTD EPS mapping and PE_TTM; market MA60/stop omitted'),
 spec('slater_pb20_eps_peg','祖鲁低PB内EPS估值',SLATER,'slater_annual_eps_peg only positivePB lowest20% on signal date',
      'proxy: preserves source PB20% sequential filter; filtered factor_valid benchmark is a subset diagnostic, not full-universe alpha'),
],44:[
 spec('crosssection_ols5_source','五财务截面滚动OLS',OLS,'OLS(past4gap_ret~LEV,rev_yoy,profit_yoy,ROE*BM,PE/profit_yoy) with PIT features asof next_trade_day_minus6calendar_days; predict current; both dates 0<PE/profit_yoy<1',
      'proxy: literal source five-price target and6calendar-day pre_date; quarterly PIT/TTM PE; fullA no index/ST gates; source PEG admits negativePE/negativegrowth'),
 spec('crosssection_rank_ols5_fulla','五财务秩OLS全A适配',OLS,'same causal training dates/target, CS ranks of five features, all finite data without PEG gate',
      'proxy: explicit repaired rank-input fullA adaptation, separate hypothesis, not original raw source implementation'),
]}

def annual_eps(table,grid,stocks):
 out=np.full((2,len(grid),len(stocks)),np.nan,np.float32)
 for symbol,t in table.groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  t=t[t.end_date.dt.month==12].sort_values(['ann_date','end_date','update_flag'])
  rows=list(t[['ann_date','end_date','eps']].itertuples(index=False,name=None));at=0;known={}
  for i,d in enumerate(grid):
   while at<len(rows) and rows[at][0]<=d:
    a,e,v=rows[at];known[e.year]=v;at+=1
   for k,off in enumerate([2,3]):out[k,i,j]=known.get(d.year-off,np.nan)
 return out

def data_dates(cal,grid):
 pos=cal.get_indexer(grid)
 pre=cal[np.maximum(0,cal.searchsorted(cal[pos+1]-pd.Timedelta(days=6),side='right')-1)]
 dates=grid.union(grid-pd.Timedelta(days=365)).union(pre).sort_values()
 return dates,pre

def build(batch,fin,dates,grid,stocks,f,cal,annual):
 def g(ep,c,at):return fin[f'{ep}.{c}.q0'][dates.get_indexer(at)].astype(float)
 mv=f['cap'][cal.get_indexer(grid)]*10000
 profit=g('income','n_income_attr_p_ttm',grid);eq=g('balancesheet','total_hldr_eqy_exc_min_int',grid)
 pe=q.ratio(mv,profit);bm=q.ratio(eq,mv)
 if batch==43:
  growth=q.ratio(annual[0],annual[1])-1;peg=q.ratio(pe,100*growth)
  sl=np.where((peg>0)&(peg<5),-peg,np.nan)
  a=g('fina_indicator','eps',grid);b=g('fina_indicator','eps',grid-pd.Timedelta(days=365))
  growth=q.ratio(a,b)-1
  ly=np.where((a>0)&(b>0)&(growth>0)&(pe>0)&(bm>0),-q.ratio(pe,100*growth),np.nan)
  # PB ascending == positive BM descending; strict source bottom20% rank proxy.
  rank=q.rank(np.where(bm>0,-bm,np.nan));gated=np.where(rank<=.2,sl,np.nan)
  return [sl,ly,gated]
 dates2,pre=data_dates(cal,grid)
 def features(at):
  cap=f['cap'][cal.get_indexer(at)]*10000
  ni=g('income','n_income_attr_p_ttm',at);equity=g('balancesheet','total_hldr_eqy_exc_min_int',at)
  growth=g('fina_indicator','netprofit_yoy',at)
  lev=q.ratio(g('balancesheet','total_assets',at),g('balancesheet','total_liab',at))
  peg=q.ratio(q.ratio(cap,ni),growth)
  vals=[lev,g('fina_indicator','or_yoy',at),growth,g('fina_indicator','roe',at)*q.ratio(equity,cap),peg]
  return np.stack(vals,axis=-1),peg
 old,pegold=features(pre);cur,pegcur=features(grid)
 pos=cal.get_indexer(grid);y=q.ratio(f['close'][pos],f['close'][pos-4])-1
 outputs=[]
 for repaired in [False,True]:
  x=old.copy();z=cur.copy()
  if repaired:
   x=np.stack([q.rank(x[:,:,k]) for k in range(5)],axis=-1)
   z=np.stack([q.rank(z[:,:,k]) for k in range(5)],axis=-1)
  score=np.full(y.shape,np.nan,np.float32)
  for i in range(len(grid)):
   train=np.isfinite(x[i]).all(axis=1)&np.isfinite(y[i])&(f['cap'][cal.get_indexer(pre)[i]]>0)&(f['cap'][pos[i]]>0)
   test=np.isfinite(z[i]).all(axis=1)&(f['cap'][pos[i]]>0)
   if not repaired:
    both=(pegold[i]>0)&(pegold[i]<1)&(pegcur[i]>0)&(pegcur[i]<1)
    train&=both;test&=both
   if train.sum()<100:continue
   a=x[i,train];mean=a.mean(axis=0);sd=a.std(axis=0);sd=np.where(sd>1e-12,sd,1)
   design=np.column_stack([np.ones(train.sum()),(a-mean)/sd])
   weights=np.linalg.lstsq(design,y[i,train],rcond=None)[0]
   score[i,test]=np.column_stack([np.ones(test.sum()),(z[i,test]-mean)/sd])@weights
  outputs.append(score)
 return outputs

def main():
 p=argparse.ArgumentParser();p.add_argument('--batches',nargs='+',type=int,default=[43,44]);args=p.parse_args()
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 dates,pre=data_dates(cal,grid);oldout,oldfields,oldloader=q.OUT,q.FIN_FIELDS,q.pit_tables
 schema=q.ROOT/'research_reports/platform_alignment/quant-corpus-eps-ols-schema-20261013';schema.mkdir(exist_ok=True)
 try:
  q.OUT=schema;q.FIN_FIELDS={'fina_indicator':['eps','roe','or_yoy','netprofit_yoy'],
   'income':['n_income_attr_p'],'balancesheet':['total_hldr_eqy_exc_min_int','total_assets','total_liab']}
  q.dump(schema/'schema.json',dict(fields=q.FIN_FIELDS,dates=[str(d) for d in dates],rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();annual=annual_eps(tables['fina_indicator'],grid,stocks)
  for batch in args.batches:
   out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{batch}-20261013';out.mkdir(exist_ok=True)
   plan=dict(specs=SPECS[batch],rule=q.ALIGNMENT_RULE_VERSION,selection='fixed source definitions before outcomes',platform_compute=0)
   path=out/'frozen_plan.json'
   if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('frozen mismatch')
   q.dump(path,plan)
   if (out/'audit_complete.json').exists():continue
   vals=build(batch,fin,dates,grid,stocks,f,cal,annual);verification=[]
   # Retrain on broad enough cross sections, not on all-NaN 8-stock OLS.
   ids=np.arange(512)
   for n in [35,79]:
    cut=grid[n-1];dt=dates[dates<=cut];sub={ep:t[(t.ann_date<=cut)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
    q.pit_tables=lambda:sub
    with tempfile.TemporaryDirectory(prefix='raw-pit-',dir=out) as temp:
     q.OUT=Path(temp);replay=q.financial_snapshot(dt,stocks[ids],lags=1);small={k:v[:,ids] for k,v in f.items()}
     ann=annual_eps(sub['fina_indicator'],grid[:n],stocks[ids])
     full=build(batch,{k:v[:,ids] for k,v in fin.items()},dates,grid[:n],stocks[ids],small,cal,annual[:,:n,ids])
     trunc=build(batch,replay,dt,grid[:n],stocks[ids],{k:v[:pos[n-1]+1] for k,v in small.items()},cal,ann)
     for sp,a,b in zip(SPECS[batch],full,trunc):
      np.testing.assert_allclose(a,b,equal_nan=True,rtol=1e-5,atol=1e-5)
      if not np.isfinite(b).any():raise AssertionError('empty prefix verification '+sp['key'])
      verification.append(dict(key=sp['key'],test='raw_PIT_cutoff_replay_and_model_retraining',stocks=512,cutoff=str(cut),finite_values=int(np.isfinite(b).sum()),passed=True))
   q.pit_tables=oldloader;q.OUT=oldout
   pd.DataFrame(dict(signal=grid,feature_pre=pre,target_start=cal[pos-4],target_end=grid)).to_csv(out/'training_dates.csv',index=False)
   run(out,SPECS[batch],vals,cal,stocks,f,verification,dict(fidelity='PIT source proxy, no platform validation',selection_bias='gated variants use restricted factor_valid benchmark; compare separately',statistics='exploratory; no independent OOS'))
   audit(out,cal,stocks,f);q.dump(out/'audit_complete.json',dict(completed=True,batch=batch,platform_compute=0));print('FINISHED',batch,flush=True)
   q.OUT=schema
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,oldloader
if __name__=='__main__':main()
