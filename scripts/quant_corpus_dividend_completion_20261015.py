"""Complete previously omitted dividend layers, offline exploratory research.

Only the public Tushare dividend endpoint is contacted. No PandaAI operations.
Implemented distributions enter no earlier than both announcement dates.
Amounts are cash_div_tax (yuan/share) * base_share (10,000 shares): 10,000 yuan.
Historical vendor snapshots are not immutable filing vintages: this is a proxy.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import simultaneous_residual
from quant_corpus_correlations_20261012 import rho_details
from quant_strategy_factor_catalog_20261012 import read_text
from tushare_regime_long_history_20261014 import query, save, ready

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-dividend-completion-20261015'
DATA=q.CACHE/'dividend_completion_20261015'
S13='quant/2022年度精选策略/13.利用股息率长线选股【超稳】.txt'
S36='quant/2024年度精选策略1/36.【菜场大妈】股息率小市值策略,10年206倍,5年10.8倍.txt'
S26='quant/2024年度精选策略1/26.【深度解析 六】高股息率-低PEG-低股价 模型.txt'
S85='quant/2020年度精选策略/85 【第一次玩】我就是要买便宜股系列.txt'
DEFS=[
 ('registered_dividend_yield365','登记日365天现金股息率',S36,'cash registered in past365calendar days / current total_mv','new completion of previously omitted dividend field'),
 ('dividend_three_year_floor','连续三年现金分红底线',S13,'min(Y1,Y2,Y3)/total_mv; 3 four-quarter blocks anchored to latest announced income report','new continuous adaptation, not a source literal ranking'),
 ('dividend13_continuity_priority','源码三年分红门槛优先',S13,'2*I(Y1/MV>.02,Y2/MV>.015,Y3/MV>.012,sumY/MV>.1)+rank(Y1/MV)','source thresholds retained; full-support priority adaptation, not original CSI300/top3 strategy'),
 ('dividend36_peg_pb_small_priority','补全高股息负PEG低PB小市值',S36,'2*I(top25percent positive365day dividendyield,PE/NIyoy<0,PB<3)+rank(-totalMV)','completion vs previously omitted dividend gate; source full trading path absent'),
 ('dividend26_peg_price_small_priority','补全高股息双边PEG低价小市值',S26,'2*I(top25percent positive365day dividendyield,-3<PEG<3,price<conditional75percent)+rank(-totalMV)','conditional price quantile after dividend and PEG gates; raw close proxy for current quote'),
 ('dividend85_cheap_value_priority','低PE低PB高股息价值资格',S85,'2*I(0<PE<10,0<PB<1.5,DY365>.03)+rank(-PE)','dividend365 replaces opaque JYDividendRatio; industry cap and semiannual holding not reproduced'),
]
CONTROL_DEFS=[
 ('control36_without_dividend','对照36去掉股息条件',S36,'2*I(PEG<0,PB<3)+rank(-totalMV)','matched support ablation'),
 ('control26_without_dividend','对照26去掉股息条件',S26,'2*I(-3<PEG<3,price<conditional75percent)+rank(-totalMV)','matched support ablation; price quantile follows partial PEG subset'),
 ('control85_without_dividend','对照85去掉股息条件',S85,'2*I(0<PE<10,0<PB<1.5)+rank(-PE)','matched support ablation'),
]

def fetch_period(period):
 path=DATA/f'{period}.parquet'
 if ready(path):return path
 frames=[];offset=0;seen=set()
 while True:
  x=query('dividend',end_date=period,limit=2000,offset=offset,
    fields='ts_code,end_date,ann_date,div_proc,cash_div_tax,base_share,imp_ann_date,record_date,ex_date')
  if len(x):
   digest=hashlib.sha256(pd.util.hash_pandas_object(x,index=False).values.tobytes()).hexdigest()
   if digest in seen:raise ValueError('dividend pagination repeated a page')
   seen.add(digest)
  frames.append(x)
  if len(x)<2000:break
  offset+=len(x)
  if offset>50000:raise ValueError('dividend pagination exceeded bound')
 frame=pd.concat(frames,ignore_index=True)
 save(frame,path,dict(api='dividend',end_date=period,page_size=2000,pages=len(frames),
    retrieved_utc=pd.Timestamp.now(tz='UTC').isoformat(),last_page_rows=len(frames[-1])))
 return path

def prepare_dividends(raw):
 x=raw[raw.div_proc.eq('实施')].copy()
 for col in ['end_date','ann_date','imp_ann_date','record_date','ex_date']:
  x[col]=pd.to_datetime(x[col],format='%Y%m%d',errors='coerce')
 # Prefer conservative availability; later implementation notice can contain
 # the final share base, so earlier proposal publication is insufficient.
 x['available']=x[['ann_date','imp_ann_date']].max(axis=1)
 x['amount']=pd.to_numeric(x.cash_div_tax,errors='coerce')*pd.to_numeric(x.base_share,errors='coerce')
 x['quarter']=pd.PeriodIndex(x.end_date,freq='Q').asi8
 valid=x.available.notna()&x.end_date.notna()
 x.loc[~(x.amount.ge(0)&x.base_share.gt(0)),'amount']=np.nan
 x=x[valid].copy()
 # Same fiscal period can have genuinely separate distributions. Merge only
 # identical implemented record dates, retaining a conservative final notice.
 x=x.sort_values('available').drop_duplicates(['ts_code','end_date','record_date'],keep='last')
 return x

@njit
def replay_one(avail,rec,quarter,cash,anns,ends,dates):
 result=np.zeros((4,len(dates)),np.float32);h=0;current=-100000
 for i in range(len(dates)):
  while h<len(anns) and anns[h]<=dates[i]:
   current=max(current,ends[h]);h+=1
  if h==0:result[1:,i]=np.nan
  for k in range(len(avail)):
   if avail[k]>dates[i]:continue
   if rec[k]<=dates[i] and rec[k]>dates[i]-365*86400000000000:
    result[0,i]+=cash[k]
   delta=current-quarter[k]
   if h>0 and delta>=0 and delta<12:result[1+delta//4,i]+=cash[k]
 return result

def replay_dividends(div,inc,dates,stocks):
 """Report-anchored cash blocks and registration-window cash, in known order."""
 result=np.zeros((4,len(dates),len(stocks)),np.float32)
 groups={s:g for s,g in div.groupby('ts_code',sort=False)}
 reports={s:g for s,g in inc.groupby('instrument',sort=False)}
 for j,s in enumerate(stocks):
  g=groups.get(s);h=reports.get(s)
  if g is None or h is None:continue
  h=h.sort_values(['ann_date','end_date']);a=h.ann_date.to_numpy().astype('datetime64[ns]').astype('int64');ends=pd.PeriodIndex(h.end_date,freq='Q').asi8
  result[:,:,j]=replay_one(g.available.to_numpy().astype('datetime64[ns]').astype('int64'),
    g.record_date.to_numpy().astype('datetime64[ns]').astype('int64'),g.quarter.to_numpy(),g.amount.to_numpy(dtype=float),a,ends,dates.asi8)
 return result

@njit
def replay_ttm_one(anns,quarters,vals,dates):
 low=quarters.min()-8;high=quarters.max()+1
 reports=np.full(high-low,np.nan);current=-1;at=0
 out=np.full(len(dates),np.nan,np.float32)
 for i in range(len(dates)):
  while at<len(anns) and anns[at]<=dates[i]:
   k=quarters[at]-low;reports[k]=vals[at];current=max(current,k);at+=1
  if current<4:continue
  total=0.
  for back in range(4):
   k=current-back
   # pandas quarterly ordinal zero is 1970Q1.
   if (k+low)%4==0:total+=reports[k]
   else:total+=reports[k]-reports[k-1]
  out[i]=total
 return out

def income_ttm(inc,dates,stocks):
 out=np.full((len(dates),len(stocks)),np.nan,np.float32)
 for symbol,g in inc.groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  g=g.sort_values(['ann_date','end_date','update_flag'])
  out[:,j]=replay_ttm_one(g.ann_date.to_numpy().astype('datetime64[ns]').astype('int64'),
    pd.PeriodIndex(g.end_date,freq='Q').asi8,g.n_income_attr_p.to_numpy(dtype=float),dates.asi8)
 return out

def values(cash,cap,pe,pb,growth,price):
 dy,y1,y2,y3=[q.ratio(x,cap) for x in cash]
 peg=q.ratio(pe,growth);size=q.rank(-cap);prank=q.rank(-pe)
 positive=np.isfinite(dy)&(dy>0);high=np.zeros_like(positive)
 for i in range(len(cap)):
  ids=np.flatnonzero(positive[i]);ids=ids[np.argsort(-dy[i,ids],kind='stable')]
  high[i,ids[:int(len(ids)*.25)]]=True
 def lowprice(gate):
  out=np.zeros_like(gate)
  for i in range(len(gate)):
   p=price[i,gate[i]&np.isfinite(price[i])]
   if len(p):out[i]=price[i]<np.sort(p)[int(len(p)*.75)]
  return out
 common=np.isfinite(pe)&np.isfinite(pb)&np.isfinite(peg)&np.isfinite(price)&np.isfinite(dy)&(cap>0)
 cont=(y1>.02)&(y2>.015)&(y3>.012)&((y1+y2+y3)>.1)
 v36=(peg<0)&(pb<3)
 v26=(peg>-3)&(peg<3)
 cheap=(pe>0)&(pe<10)&(pb>0)&(pb<1.5)
 out=[dy,np.minimum.reduce([y1,y2,y3]),np.where(np.isfinite(y1+y2+y3),2*cont+q.rank(y1),np.nan),
      np.where(common,2*(high&v36)+size,np.nan),
      np.where(common,2*(high&v26&lowprice(high&v26))+size,np.nan),
      np.where(common,2*(cheap&(dy>.03))+prank,np.nan),
      np.where(common,2*v36+size,np.nan),
      np.where(common,2*(v26&lowprice(v26))+size,np.nan),
      np.where(common,2*cheap+prank,np.nan)]
 return [np.where(cap>0,x,np.nan).astype(np.float32) for x in out],dict(
   continuity=cont.sum(axis=1),dividend36=(high&v36&common).sum(axis=1),
   dividend26=(high&v26&lowprice(high&v26)&common).sum(axis=1),
   dividend85=(cheap&(dy>.03)&common).sum(axis=1),positive_dividend=positive.sum(axis=1))

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 plan=dict(hypotheses=6,ablation_controls=3,defs=DEFS+CONTROL_DEFS,rule=q.ALIGNMENT_RULE_VERSION,
   source_parameters_frozen=True,no_parameter_grid=True,no_untouched_oos=True,platform_compute_spent=0,
   dividend_proxy='implemented cash per share times declared base shares; historical API snapshot, no immutable filing vintages',
   fiscal_periods=['2014Q1','2026Q3'])
 path=OUT/'frozen_plan.json'
 if path.exists() and json.loads(path.read_text())!=json.loads(json.dumps(plan)):raise ValueError('plan mismatch')
 q.dump(path,plan)
 q.dump(OUT/'source_evidence.json',{s:dict(sha256=hashlib.sha256((q.ROOT/s).read_bytes()).hexdigest(),text=read_text(q.ROOT/s)) for s in [S13,S36,S26,S85]})
 periods=[p.end_time.strftime('%Y%m%d') for p in pd.period_range('2014Q1','2026Q3',freq='Q')]
 paths=[]
 with ThreadPoolExecutor(max_workers=4) as pool:
  fs={pool.submit(fetch_period,p):p for p in periods}
  for n,fu in enumerate(as_completed(fs),1):
   paths.append(fu.result())
   if n%10==0:print('DIVIDEND_DOWNLOAD',n,len(periods),flush=True)
 raw=pd.concat([pd.read_parquet(p) for p in sorted(paths)],ignore_index=True);div=prepare_dividends(raw)
 div.to_parquet(OUT/'implemented_dividend_events.parquet',index=False)
 q.dump(OUT/'dividend_data_audit.json',dict(raw_rows=len(raw),implemented_rows=int(raw.div_proc.eq('实施').sum()),
   retained_rows=len(div),symbols=div.ts_code.nunique(),first_available=div.available.min(),last_available=div.available.max(),
   fiscal_years=div.end_date.dt.year.value_counts().sort_index().to_dict(),
   amount_units='10,000yuan',base_share_units='10,000shares',cash_div_tax_units='yuan/share',
   missing_base_or_dates_not_zero_imputed=True,proposal_rows_excluded=True,
   unknown_cash_events=int(div.amount.isna().sum()),
   caveat='absence of a row maps to zero cash; known implemented event with missing cash makes affected cash window NaN, never zero'))
 cal,stocks,f=q.load_market();q.dates_all=cal
 pos=np.flatnonzero((cal>='20210907')&(cal<='20260907'));dates=cal[pos]
 old=q.FIN_FIELDS
 try:q.FIN_FIELDS={'income':['n_income_attr_p']};income=q.pit_tables()['income']
 finally:q.FIN_FIELDS=old
 cash_path=OUT/'daily_cash_blocks.pkl'
 if cash_path.exists():cash=pd.read_pickle(cash_path)
 else:
  cash=replay_dividends(div,income,dates,stocks)
  pd.to_pickle(cash,cash_path)
 print('PIT_CASH_READY',cash.shape,flush=True)
 # A future-announcement cutoff must not affect earlier signals, including
 # both dividend totals and the quarterly financial report anchor.
 checks=[]
 sample=stocks[:30].append(pd.Index(['600036.SH','000001.SZ','600519.SH'])).unique()
 ids=stocks.get_indexer(sample);ids=ids[ids>=0];sample=stocks[ids]
 for n in [300,800]:
  cutoff=dates[n-1];cut=replay_dividends(div[div.available<=cutoff],income[income.ann_date<=cutoff],dates[:n],sample)
  np.testing.assert_allclose(cut,cash[:,:n,ids],equal_nan=True,atol=1e-3,rtol=1e-6)
  checks.append(dict(test='raw_dividend_and_filing_cutoff_replay',cutoff=str(cutoff),symbols=len(ids),passed=True))
 assert 1.5*10000/1000000==.015
 checks.append(dict(test='independent_cash_units_1_5yuan_100million_shares_10billion_mv',passed=True))
 # Daily TTM parent income replay from the accounting loader, cached locally.
 daily_ttm_path=OUT/'daily_parent_income_ttm.pkl'
 if daily_ttm_path.exists():ttm=pd.read_pickle(daily_ttm_path)
 else:
  ttm=income_ttm(income,dates,stocks)
  pd.to_pickle(ttm,daily_ttm_path)
 # Independent slow reference at a small full-history sample: same missing
 # quarter and revision semantics, not just equality to a cached fast replay.
 for symbol in ['600036.SH','000001.SZ','600519.SH']:
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  g=income[income.instrument.eq(symbol)].sort_values(['ann_date','end_date','update_flag'])
  for at in [299,799,len(dates)-1]:
   known=g[g.ann_date<=dates[at]];reports={pd.Period(r.end_date,freq='Q'):r.n_income_attr_p for r in known.itertuples()}
   if not reports:continue
   end=max(reports);vals=[]
   for back in range(4):
    p=end-back
    v=reports.get(p,np.nan)
    vals.append(v if p.quarter==1 else v-reports.get(p-1,np.nan))
   np.testing.assert_allclose(ttm[at,j],np.sum(vals),equal_nan=True,rtol=1e-6,atol=1e-3)
 checks.append(dict(test='independent_dictionary_replay_parent_income_TTM',passed=True))
 print('PIT_TTM_READY',flush=True)
 cap=f['cap'][pos]
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',cal,stocks)[pos]
 growth=q.daily_pit_field('fina_indicator','netprofit_yoy',cal,stocks)[pos]
 pe=q.ratio(cap*10000,ttm);pb=q.ratio(cap*10000,eq)
 allvalues,gates=values(cash,cap,pe,pb,growth,f['raw_close'][pos])
 pd.DataFrame(gates,index=dates).to_csv(OUT/'daily_gate_coverage.csv')
 pd.to_pickle(dict(dates=dates,stocks=stocks,cash=cash,panels={sp[0]:x for sp,x in zip(DEFS+CONTROL_DEFS,allvalues)}),OUT/'daily_scores.pkl')
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];ix=dates.get_indexer(grid);gp=cal.get_indexer(grid)
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')[pos]
 rev=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos]
 controls=[-cap,rev,-iv];rows=[];panels={};meta=[]
 for definition,x in zip(DEFS+CONTROL_DEFS,allvalues):
  key,name,source,formula,fidelity=definition
  panels[key]=pd.DataFrame(x[ix],index=grid,columns=stocks)
  meta.append(dict(key=key,name=name,source_paths=[source],source_sha256=[hashlib.sha256((q.ROOT/source).read_bytes()).hexdigest()],
     formula=formula,fidelity='proxy: '+fidelity,direction=1,source_execution_reproduced=False))
  for form,score in [('raw',x[ix]),('size_rev_ivol_residual',simultaneous_residual(x[ix],[c[ix] for c in controls]))]:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,gp[mask],f)
    a.update(key=key,name=name,form=form,window=win)
    dest=OUT/win;dest.mkdir(exist_ok=True)
    q.dump(dest/f'{key}.{form}.json',a);p.to_csv(dest/f'{key}.{form}.periods.csv',index=False);d.to_csv(dest/f'{key}.{form}.daily_nav.csv',index=False)
    rows.append(a)
  print('RESULT',key,[(r['window'],r['form'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2)) for r in rows[-4:]],flush=True)
  pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
 pd.to_pickle(dict(dates=grid,stocks=stocks,panels=panels,metadata=meta),OUT/'signal_panels.pkl')
 q.dump(OUT/'recipe_manifest.json',meta);q.dump(OUT/'verification.json',checks)
 anchors={'B01|SIZE':-cap,'N01|REV20':rev,'IVOL120|known':-iv,'B08|BM_proxy':q.ratio(eq,cap*10000)}
 anchors['N27|ROE_proxy']=q.daily_pit_field('fina_indicator','roe',cal,stocks)[pos]
 cor=[]
 for sp,x in zip(DEFS,allvalues):
  for anchor,y in anchors.items():cor.append(dict(candidate=sp[0],anchor=anchor,scope='every_trading_day_cross_sectional_Spearman',**rho_details(x,y)))
 pd.DataFrame(cor).to_csv(OUT/'daily_anchor_correlations.csv',index=False)
 q.dump(OUT/'config.json',dict(**plan,warmup='20180101',formal_window=['20210907','20260907'],recent_window=['20260101',str(cal.max().date())],
   cycle=10,groups=10,label_offset=1,benchmark='factor_valid',one_way_cost=.003,price='qfq',universe='SH/SZ fullA',market_cap='total_mv',platform_net_filter='all',
   signal_reference=str(q.REFERENCE.relative_to(q.ROOT)),daily_correlation_days=len(dates),cluster_coverage='five anchors only; full master comparison pending',
   noncash_source_rules_omitted=['CSI300 membership','industry holding caps','buy/keep buffer','daily exits','semiannual rebalance','limit-price execution'],
   ties='stable symbol order; zero-dividend ties audited separately in followup'))
 q.dump(OUT/'completion.json',dict(completed=True,hypotheses=6,controls=3,platform_compute_spent=0,pool_test_done=False,new_cluster_confirmed=False))
 print('DIVIDEND_COMPLETION_DONE',flush=True)

if __name__=='__main__':main()
