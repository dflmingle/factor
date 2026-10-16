"""Source-grounded accounting extensions; local only, fixed before evaluation.

Keep this cohort separate from old cumulative-margin and CFO proxies. Replay
announcements, old-period revisions and missing quarters before building scores.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import json
import hashlib
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import simultaneous_residual
from quant_corpus_correlations_20261012 import rho_details, saved_grid
from quant_strategy_factor_catalog_20261012 import read_text

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-accounting-completion-20261014'
SUE='quant/2024年度精选策略2/82.可转债知识总结.txt'
PROFIT='quant/2021年度精选策略/26.稳定高回报周期股策略2.txt'
MARGIN='quant/2023年度精选策略/78.EPS+MS因子的大盘蓝筹策略.txt'
CASH='quant/2020年度精选策略/67 多因子回测完整模板（筛选和买卖条件强于‘策略生成器’）.txt'
FIELDS={'income':['revenue','oper_cost'], 'fina_indicator':['q_dtprofit'],
        'balancesheet':['total_assets'], 'cashflow':['n_incr_cash_cash_equ','n_cashflow_act']}
NAMES=[('revenue','income','revenue'),('cost','income','oper_cost'),
       ('profit','fina_indicator','q_dtprofit'),('assets','balancesheet','total_assets'),
       ('cashinc','cashflow','n_incr_cash_cash_equ'),('cfo','cashflow','n_cashflow_act')]
DEFS=[
 ('coherent_seasonal_revenue_sue3','同报告期季节收入惊喜',SUE,'(Qrev0-mean(Qrev4,8,12))/sampleSTD(Qrev4,8,12)','audited retest of prior seasonal adaptation; not a new mechanism'),
 ('quarter_revenue_yoy_acceleration','单季收入同比加速',SUE,'Qrev0/Qrev4-Qrev4/Qrev8; positive sales denominators','new acceleration adaptation, no source literal formula claim'),
 ('quarter_deducted_profit_sue3','单季扣非盈利季节惊喜',PROFIT,'(Qdeducted0-mean(Qdeducted4,8,12))/sampleSTD(Qdeducted4,8,12)','new seasonal adaptation of source adjusted-profit growth; q_dtprofit vendor proxy'),
 ('quarter_deducted_roa_yoy_change','单季扣非盈利同比资产增量',PROFIT,'(Qdeducted0-Qdeducted4)/mean(assets0,assets4)','new bounded-denominator growth adaptation; coherent report quarters'),
 ('quarter_margin_stability8','八季单季毛利稳定',MARGIN,'-sampleSTD(GM0..7)/mean(GM0..7); GM=(Qrev-Qcost)/Qrev; meanGM>0','single-quarter 8-quarter proxy; original vendor margin_stability opaque'),
 ('quarter_margin_improvement_yoy','单季毛利率同比改善',MARGIN,'GM0-GM4; positive quarter revenues','new profitability-change adaptation, not original vendor field'),
 ('cash_equivalent_increase_ttm_yield','现金净增加TTM估值',CASH,'sum(Qcashinc0..3)/(total_mv*10000)','source NCFP accounting atom TTM adaptation; no industry/dividend qualification'),
 ('nonoperating_cash_increase_ttm_yield','非经营现金增量TTM估值',CASH,'sum(Qcashinc0..3-QCFO0..3)/(total_mv*10000)','new decomposition diagnostic; may reflect financing, not presumed alpha')]
SPECS=[dict(key=k,name=n,source_paths=[s],formula=f,fidelity='proxy: '+fi,
            gated=False,source_execution_reproduced=False,source_text_read=True)
       for k,n,s,f,fi in DEFS]

@njit(cache=True)
def replay_coherent(ann,ends,cols,vals,dates):
 lo=ends.min();hi=ends.max();reports=np.full((hi-lo+1,6),np.nan)
 latest=-1;at=0;out=np.full((len(dates),13,6),np.nan)
 for i in range(len(dates)):
  while at<len(ann) and ann[at]<=dates[i]:
   end=ends[at]-lo;col=cols[at];reports[end,col]=vals[at]
   if col==0:latest=max(latest,end)
   at+=1
  if latest<0:continue
  for lag in range(13):
   end=latest-lag
   if end<0:continue
   for col in range(6):
    v=reports[end,col]
    if col in (0,1,4,5) and (end+lo)%4!=0:
     v=v-reports[end-1,col] if end>0 else np.nan
    out[i,lag,col]=v
 return out

def prepare(tables,symbol):
 rows=[]
 for col,(_,ep,name) in enumerate(NAMES):
  t=tables[ep];g=t[t.instrument.eq(symbol)].sort_values(['ann_date','end_date','update_flag'])
  if len(g):rows.append(pd.DataFrame({'ann':pd.DatetimeIndex(g.ann_date).asi8,
    'end':pd.PeriodIndex(g.end_date,freq='Q-DEC').asi8,'col':col,'val':g[name].to_numpy(float),
    'order':np.arange(len(g))}))
 if not rows:return None
 f=pd.concat(rows).sort_values(['ann','end','col','order'],kind='stable')
 return (f.ann.to_numpy(np.int64),f.end.to_numpy(np.int64),f.col.to_numpy(np.int64),f.val.to_numpy(float))

def literal_replay(events,dates):
 ann,ends,cols,vals=events;known={};out=np.full((len(dates),13,6),np.nan);at=0;latest=None
 for i,d in enumerate(dates):
  while at<len(ann) and ann[at]<=d:
   end,col=int(ends[at]),int(cols[at]);known[end,col]=vals[at]
   if col==0:latest=end if latest is None else max(latest,end)
   at+=1
  if latest is None:continue
  for lag in range(13):
   end=latest-lag
   for col in range(6):
    v=known.get((end,col),np.nan)
    if col in (0,1,4,5) and end%4!=0:v-=known.get((end-1,col),np.nan)
    out[i,lag,col]=v
 return out

def build(x,cap):
 def div(a,b):
  with np.errstate(divide='ignore',invalid='ignore'):v=a/b
  return np.where(np.isfinite(v)&(np.abs(b)>1e-12),v,np.nan)
 revenue=x[:,:,0];profit=x[:,:,2];assets=x[:,:,3];cash=x[:,:,4];cfo=x[:,:,5]
 prev=revenue[:,[4,8,12]];ps=profit[:,[4,8,12]]
 gm=div(revenue-x[:,:,1],np.where(revenue>0,revenue,np.nan));gm8=gm[:,:8]
 mean=gm8.mean(axis=1)
 return [div(revenue[:,0]-prev.mean(axis=1),prev.std(axis=1,ddof=1)),
         div(revenue[:,0],np.where(revenue[:,4]>0,revenue[:,4],np.nan))-div(revenue[:,4],np.where(revenue[:,8]>0,revenue[:,8],np.nan)),
         div(profit[:,0]-ps.mean(axis=1),ps.std(axis=1,ddof=1)),
         div(profit[:,0]-profit[:,4],np.where((assets[:,0]>0)&(assets[:,4]>0),assets[:,[0,4]].mean(axis=1),np.nan)),
         -div(gm8.std(axis=1,ddof=1),np.where(mean>0,mean,np.nan)),
         gm[:,0]-gm[:,4],
         div(cash[:,:4].sum(axis=1),cap*10000),
         div((cash[:,:4]-cfo[:,:4]).sum(axis=1),cap*10000)]

def verify(tables,stocks,dates,cap):
 checks=[]
 for symbol in stocks[::max(1,len(stocks)//12)][:12]:
  events=prepare(tables,symbol)
  if events is None:continue
  arr=replay_coherent(*events,dates.asi8);ref=literal_replay(events,dates.asi8)
  np.testing.assert_allclose(arr,ref,equal_nan=True,rtol=1e-12,atol=1e-8)
  for cut in [len(dates)//3,2*len(dates)//3]:
   keep=events[0]<=dates[cut-1].value
   if not keep.any():continue
   truncated=replay_coherent(*(a[keep] for a in events),dates[:cut].asi8)
   np.testing.assert_allclose(arr[:cut],truncated,equal_nan=True)
   for a,b in zip(build(arr,cap[:,0]),build(truncated,cap[:cut,0])):
    np.testing.assert_allclose(a[:cut],b,equal_nan=True)
  checks.append(dict(test='literal_raw_filing_replay_and_two_announcement_cutoffs',symbol=symbol,passed=True,finite=int(np.isfinite(arr).sum())))
 # Q1=100, Q2 YTD=250; late Q1 revision to110 changes Q2 to140,
 # but must not replace current quarter. This detects a merge_asof shortcut.
 ends=np.array([200,201,200],np.int64);ann=np.array([1,2,3],np.int64)
 events=(ann,ends,np.zeros(3,np.int64),np.array([100.,250.,110.]))
 toy=replay_coherent(*events,np.array([1,2,3],np.int64))
 np.testing.assert_allclose(toy[:,0,0],[100,150,140]);np.testing.assert_allclose(toy[2,1,0],110)
 checks.append(dict(test='late_old_quarter_revision_not_latest_period_and_YTD_difference',passed=True))
 return checks

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,
           hypotheses=8,platform_compute_spent=0,parameter_selection='frozen before outcomes; no grid search')
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('incompatible frozen plan')
 q.dump(path,plan)
 calendar,stocks,f=q.load_market();q.dates_all=calendar
 positions=np.flatnonzero((calendar>='20210907')&(calendar<='20260907'));dates=calendar[positions]
 old=q.FIN_FIELDS
 try:q.FIN_FIELDS=FIELDS;tables=q.pit_tables()
 finally:q.FIN_FIELDS=old
 q.dump(OUT/'source_evidence.json',{s:dict(text=read_text(q.ROOT/s),sha256=hashlib.sha256((q.ROOT/s).read_bytes()).hexdigest()) for s in [SUE,PROFIT,MARGIN,CASH]})
 q.dump(OUT/'field_audit.json',{ep:dict(rows=len(t),first_ann=t.ann_date.min(),last_ann=t.ann_date.max(),report_types=t.report_type.value_counts().to_dict() if 'report_type' in t else {},
   snapshot_semantics='existing alignment loader, max(ann,f_ann), consolidated preference, chronological revisions, source annual/industry/universe gates omitted') for ep,t in tables.items()})
 checks=verify(tables,stocks,dates,f['cap'][positions])
 cache=OUT/'daily_scores.pkl'
 if cache.exists():panels=pd.read_pickle(cache)
 else:
  panels={s['key']:np.full((len(dates),len(stocks)),np.nan,np.float32) for s in SPECS}
  # Group once; avoid repeatedly scanning large tables for every symbol.
  grouped={ep:{sym:g for sym,g in t.groupby('instrument',sort=False)} for ep,t in tables.items()}
  for j,symbol in enumerate(stocks):
   small={ep:g.get(symbol,tables[ep].iloc[:0]) for ep,g in grouped.items()}
   events=prepare(small,symbol)
   if events is None:continue
   arr=replay_coherent(*events,dates.asi8)
   for s,v in zip(SPECS,build(arr,f['cap'][positions,j])):panels[s['key']][:,j]=np.where(f['cap'][positions,j]>0,v,np.nan)
   if j%1000==0:print('REPLAY',j,len(stocks),flush=True)
  pd.to_pickle(panels,cache)
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];ix=dates.get_indexer(grid);assert (ix>=0).all()
 run(OUT,SPECS,[panels[s['key']][ix] for s in SPECS],calendar,stocks,f,checks,
     dict(accounting='single-quarter revenue/cost/cash YTD differencing; same income-anchored report periods across statements',
          statistic='exploratory cohort, post corpus screen; no untouched OOS; prior failed tests retained',
          proxy='Tushare accounting mapping and stable-symbol ties; source trading execution not reproduced'),
     residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 original=q.OUT
 try:q.OUT=OUT;saved_grid()
 finally:q.OUT=original
 # Primary correlations use EVERY trading day. Saved-grid 54-reference
 # coverage complements these, and is not promoted to daily evidence.
 cap=f['cap'][positions];close=f['close'];rev=-(q.ratio(close,q.delay(close,20))-1)[positions]
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')[positions]
 fin=q.financial_snapshot(grid,stocks)
 bm=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)[positions]/(cap*10000)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks)[positions]
 ret=q.ratio(close,q.delay(close))-1
 anchors={'B01|SIZE':-cap,'N01|REV20':rev,'IVOL120|known':-iv,'B08|BM_proxy':bm,'N27|ROE_proxy':roe,
          'N08|TURN_STD21':-q.rolling(f['turnover'],21,'std')[positions],
          'N09|MAX21':-q.rolling(ret,21,'max')[positions],
          'H03|IMPACT60':q.ratio(q.rolling(q.ratio(f['high']-f['low'],q.delay(close)+1e-6),60,'sum'),q.rolling(f['amount'],60,'sum')+1)[positions]}
 rows=[]
 for key,v in panels.items():
  for name,a in anchors.items():rows.append(dict(candidate=key,anchor=name,scope='every_trading_day_cross_sectional_Spearman',**rho_details(v,a)))
 pd.DataFrame(rows).to_csv(OUT/'daily_anchor_correlations.csv',index=False)
 q.dump(OUT/'daily_correlation_scope.json',dict(days=len(dates),anchors=list(anchors),full_cluster_coverage=False,new_cluster_confirmed=False))
 q.dump(OUT/'audit_complete.json',dict(completed=True,hypotheses=8,platform_compute_spent=0,pool_test_done=False))
 print('ACCOUNTING_COMPLETE',flush=True)

if __name__=='__main__':main()
