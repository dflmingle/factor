"""Offline audit: continuous qfq returns, lagged total_mv groups and pool proxy."""
from pathlib import Path
import sys,json,pickle
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION
R=ROOT/'quantlab/.quantlab/cache/research/cn_equity'
O=ROOT/'research_reports/platform_alignment/style-audit-20261010-v2'
TARGET=['2022-04','2024-01','2024-02','2024-04','2026-03','2026-05','2026-06']
TECH={'半导体','元器件','通信设备','软件服务','IT设备','互联网'}
O.mkdir(parents=True,exist_ok=True)
parts=[]
for p in sorted((R/'tushare_factor_recheck/qfq/daily_batches').glob('*.parquet')):
 a,b=p.stem.split('_')[1:3]
 if b<'20210801': continue
 x=pd.read_parquet(p,columns=['date','instrument','close']); x.date=pd.to_datetime(x.date)
 x=x[(x.date>='2021-08-01')&(x.date<='2026-09-07')&x.instrument.str.endswith(('.SH','.SZ'))]
 parts.append(x)
x=pd.concat(parts,ignore_index=True)
# overlapping batches must agree, otherwise refuse silent selection
agg=x.groupby(['date','instrument']).close.agg(['min','max'])
conflict=((agg['max']-agg['min']).abs()>1e-7*agg['max'].abs()).sum()
assert conflict==0, f'{conflict} conflicting close observations'
px=x.drop_duplicates(['date','instrument']).pivot(index='date',columns='instrument',values='close').sort_index()
del x,parts,agg
ret=px.ffill().pct_change(fill_method=None)
assert ret.index.is_monotonic_increasing and ret.index.is_unique
sb=pd.read_parquet(R/'stock_basic/data.parquet').drop_duplicates('ts_code').set_index('ts_code')
industry=sb.industry.reindex(px.columns).fillna('UNKNOWN')
print('continuous prices',px.shape,'duplicates consistent',flush=True)
sf,_,forward,signals=pickle.loads((ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl').read_bytes())
built=pickle.loads((ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl').read_bytes())['scores']
keys=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']
sf=sf.copy(); sf.date=pd.to_datetime(sf.date)
ps={k:pd.DataFrame({'date':sf.date,'instrument':sf.instrument,'v':built[k].to_numpy()}).pivot(index='date',columns='instrument',values='v') for k in keys}
score=sum(p.sub(p.mean(axis=1),axis=0).div(p.std(axis=1,ddof=0).replace(0,np.nan),axis=0) for p in ps.values())/5
fwd=forward.pivot(index='date',columns='instrument',values='forward_return')
# Entry next-day CLOSE: old holdings earn entry day's return, new holdings from following day.
active={}; exposure=[]
for s in score.index:
 entry=ret.index.searchsorted(s,side='right')
 if entry>=len(ret.index): continue
 sc=score.loc[s].dropna(); sc=sc.reindex(sc.index.intersection(fwd.columns)); sc=sc[np.isfinite(fwd.loc[s].reindex(sc.index))]
 names=sc.nlargest(int(len(sc)*.1)).index.intersection(ret.columns)
 active[ret.index[entry]]= (s,names,sc.index.intersection(ret.columns))
filled=px.ffill()
cur=None; daily=[]; last_rel=None; benchmark_rel=None; attr=[]
for t in ret.index:
 if cur is not None:
  s,names,valid=cur
  rel=filled.loc[t,names]/filled.loc[active_entry,names]
  br=filled.loc[t,valid]/filled.loc[active_entry,valid]
  pnow=float(rel.mean()); bnow=float(br.mean())
  weights=(last_rel/last_rel.sum()).reindex(names)
  r=ret.loc[t,names].fillna(0)
  daily.append({'date':t,'pool_gross':pnow/float(last_rel.mean())-1,'factor_valid':bnow/float(benchmark_rel.mean())-1})
  for ind in industry.reindex(names).unique():
   mask=industry.reindex(names)==ind
   attr.append({'date':t,'industry':ind,'weight':float(weights[mask].sum()),'contribution':float((weights[mask]*r[mask]).sum())})
  last_rel=rel; benchmark_rel=br
 if t in active:
  cur=active[t]; active_entry=t
  last_rel=pd.Series(1.,index=cur[1]); benchmark_rel=pd.Series(1.,index=cur[2])
D=pd.DataFrame(daily).set_index('date')
# Pool uses equal entry weights with drift; this is diagnostic, not formal C reproduction.
monthly=[]; groups=[]; exp=[]
for m in TARGET:
 mask=ret.index.to_period('M').astype(str)==m; d=ret.loc[mask]
 first=d.index[0]; prev=ret.index[ret.index<first][-1]
 capfile=R/'tushare_factor_recheck/daily_basic_full_a'/f'daily_basic_{prev:%Y%m%d}.parquet'
 cap=pd.read_parquet(capfile).set_index('instrument').total_mv.dropna(); cap=cap[cap>0].reindex(d.columns).dropna()
 q=pd.qcut(cap.rank(method='first'),10,labels=False) # 0 small, 9 large
 # Fixed month-start cap membership; market/sector groups rebalance to equal weights daily.
 total=d.columns[d.notna().any()]
 def group_return(names):
  z=d[d.columns.intersection(names)]; dr=z.mean(axis=1); return float((1+dr).prod()-1),len(z.columns)
 for name,names in [('all_A',total),('tech',industry[industry.isin(TECH)].index),('nontech',industry[~industry.isin(TECH)].index)]+[(i,industry[industry==i].index) for i in industry.unique()]+[(f'mv_decile_{b+1}',q[q==b].index) for b in range(10)]:
  rr,n=group_return(names); groups.append({'month':m,'group':name,'stocks':n,'return':rr})
 valid_counts=d.notna().sum(axis=1); up=d.gt(0).sum(axis=1)/valid_counts; market=d.mean(axis=1)
 pool=D.loc[D.index.to_period('M').astype(str)==m]; market_rex=(1+market).prod()-1
 monthly.append({'month':m,'days':len(d),'market_return':market_rex,'up_share':up.mean(),'majority_up_days':(up>.5).mean(),'worst_day':str(market.idxmin().date()),'worst_day_return':market.min(),'pool_proxy_gross':float((1+pool.pool_gross).prod()-1),'factor_valid_proxy':float((1+pool.factor_valid).prod()-1)})
 for t in d.index:
  applicable=[e for e in active if e<t]
  if not applicable: continue
  s,names,valid=active[max(applicable)]
  inds=industry.reindex(names).value_counts(normalize=True)
  dq=q.reindex(names).dropna()
  exp.append({'month':m,'date':t,'signal':s,'small30_weight':(dq<=2).mean(),'small10_weight':(dq==0).mean(),'tech_weight':industry.reindex(names).isin(TECH).mean(),'industry_hhi':(inds**2).sum(),'industry_top3':inds.nlargest(3).sum()})
M=pd.DataFrame(monthly); G=pd.DataFrame(groups); E=pd.DataFrame(exp)
I=G[~G.group.isin(['all_A','tech','nontech','UNKNOWN'])&~G.group.str.startswith('mv_decile_')].copy()
I['rank']=I.groupby('month')['return'].rank(ascending=False,method='min')
I.to_csv(O/'all_industry_ranking.csv',index=False)
M.to_csv(O/'verified_months.csv',index=False); G.to_csv(O/'industry_size_returns.csv',index=False); E.to_csv(O/'daily_exposure.csv',index=False); D.to_csv(O/'pool_proxy_daily.csv')
A=pd.DataFrame(attr); A['month']=pd.to_datetime(A.date).dt.to_period('M').astype(str); A=A[A.month.isin(TARGET)]; A.groupby(['month','industry']).agg(mean_weight=('weight','mean'),arithmetic_contribution=('contribution','sum')).to_csv(O/'pool_industry_contribution.csv')
# First-day-return check and source traceability
checks={'rule_version':ALIGNMENT_RULE_VERSION,'price_overlap_conflicts':int(conflict),'continuous_price_start':str(px.index.min()),'continuous_price_end':str(px.index.max()),'months':TARGET,'static_industry_proxy':True,'pool_proxy_notes':['Archived precomputed scores, not newly reconstructed exact platform panels','Buy-and-hold equal entry weights drift between signal-next-close rebalances; excludes costs','Signal next-day-close timing and month-internal changes respected','Market all-A benchmark is diagnostic, not formal factor_valid result'],'warmup':'Archived factor scores use historical warmup; this script does not generate factors','missing_return_denominator':'only finite returns counted for breadth','source_signal_end':str(score.index.max())}
cal=pd.concat([pd.read_parquet(R/'trade_calendar'/f'{y}.parquet') for y in range(2021,2027)])
open_dates=pd.DatetimeIndex(pd.to_datetime(cal.loc[cal.is_open.eq(1),'trade_date'].astype(str))).unique()
open_dates=open_dates[(open_dates>=ret.index.min())&(open_dates<=ret.index.max())]
checks['missing_open_dates']=[str(t.date()) for t in open_dates.difference(ret.index)]
assert not checks['missing_open_dates']
checks['max_industry_daily_sum_residual']=float((A.groupby('date').contribution.sum()-D.pool_gross.reindex(A.date.unique())).abs().max())
checks['monthly_market_compounding_residual']=float(max(abs(float((1+ret.loc[ret.index.to_period('M').astype(str)==m].mean(axis=1)).prod()-1)-M.set_index('month').loc[m,'market_return']) for m in TARGET))
ledger=pd.read_csv(ROOT/'research_reports/platform_alignment/monthly-attribution-20261010/monthly_attribution.csv')
ledger=ledger[ledger.label.eq('现役5席')][['period','portfolio_return','benchmark_return']]
rec=M.merge(ledger,left_on='month',right_on='period',how='left')
rec['pool_gap_pp']=(rec.pool_proxy_gross-rec.portfolio_return)*100
rec['bench_gap_pp']=(rec.factor_valid_proxy-rec.benchmark_return)*100
rec.to_csv(O/'saved_ledger_reconciliation.csv',index=False)
checks['archived_ledger_max_pool_gap_pp']=float(rec.pool_gap_pp.abs().max())
checks['archived_ledger_max_bench_gap_pp']=float(rec.bench_gap_pp.abs().max())
checks['ledger_alignment_status']='not_identical_proxy_do_not_attribute_platform_31_64_percent_dd'
checks['exposure_measure']='Equal constituent count shares, daily average; not drifting capital weights'
checks['price_missing_policy']='Forward-fill missing closes; suspension/delisting handling is a diagnostic proxy'
comparison=M[['month','market_return','pool_proxy_gross','factor_valid_proxy']].copy()
for col,group in [('tech','tech'),('nontech','nontech'),('smallest10','mv_decile_1'),('largest10','mv_decile_10')]:
 comparison[col]=comparison.month.map(G[G.group.eq(group)].set_index('month')['return'])
comparison['pool_tech_weight']=comparison.month.map(E.groupby('month').tech_weight.mean())
comparison['market_tech_weight']=comparison.month.map({m:float(industry.reindex(ret.loc[ret.index.to_period('M').astype(str)==m].columns[ret.loc[ret.index.to_period('M').astype(str)==m].notna().any()]).isin(TECH).mean()) for m in TARGET})
comparison.to_csv(O/'comparison.csv',index=False)
(O/'audit_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(M.to_string(index=False)); print(G[G.group.isin(['tech','nontech','半导体','元器件','mv_decile_1','mv_decile_10'])].to_string(index=False)); print(E.groupby('month').mean(numeric_only=True).to_string())
