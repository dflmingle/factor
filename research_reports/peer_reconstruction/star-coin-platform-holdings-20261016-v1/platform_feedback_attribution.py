from pathlib import Path
import json,hashlib,sys,pickle
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[3]; V2=ROOT/'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'; SEARCH=ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1';sys.path[:0]=[str(SEARCH),str(V2)]
from holdings_diff import build_pool
from engine import standardize
OUT=Path(__file__).resolve().parent
cal,stocks,fields=pickle.load((ROOT/'research_reports/platform_alignment/bc-peer-pools-20261012/market_extended.pkl').open('rb'));cal=pd.DatetimeIndex(cal);stocks=pd.Index(stocks);recent_pos=np.flatnonzero(cal>=pd.Timestamp('20260801'));recent=cal[recent_pos];signal=pd.Timestamp('20261008');i=recent.get_loc(signal);p=cal.get_loc(signal)
mask=np.isfinite(fields['cap'][p])&(fields['cap'][p]>0)&np.isfinite(fields['turnover'][p]);mask &= ~((fields['volume'][p]<=0)|(fields['amount'][p]<=0)|np.isclose(fields['high'][p],fields['low'][p],rtol=1e-8,atol=1e-8))
names=pd.read_parquet(ROOT/'quantlab/.quantlab/cache/research/cn_equity/stock_basic/namechange.parquet')
for symbol,g in names.groupby('ts_code',sort=False):
 j=stocks.get_indexer([symbol])[0]
 if j<0: continue
 flag=False
 for r in g.dropna(subset=['start_date']).sort_values('start_date').itertuples():
  ann=max(r.start_date,r.ann_date) if pd.notna(r.ann_date) else r.start_date
  if signal>=ann: flag='ST' in str(r.name).upper()
 if flag: mask[j]=False
pool=build_pool(); dirs=np.array([-1,-1,-1,-1,1,-1,-1,-1,-1,1.],float); z=[]
for x in pool:
 key=hashlib.sha256(x.key().encode()).hexdigest();raw=np.load(V2/'diff_panels'/(key+'.npy'))
 z.append(standardize(raw[i:i+1],mask[None,:])[0])
z=np.array(z); contrib=z*dirs[:,None]/10; comp=np.nansum(contrib,axis=0)
peer=json.loads((ROOT/'research_reports/peer_reconstruction/top50-20261013/public/holdings/18067f13fb2f894e0a45b181/20261009.json').read_text())['rows']; peer_rank={x['symbol']:x['rank'] for x in peer};peer20={x['symbol'] for x in peer[:20]}
platform=json.loads((OUT/'platform_vs_peer.json').read_text())['platform_top20'];plat20=[x['symbol'] for x in platform]; local=json.loads((OUT/'local_same_date_baseline.json').read_text())['baselines']['competition_st_filtered']['top20'];loc20=[x['symbol'] for x in local]
sets={'platform_only':[s for s in plat20 if s not in loc20],'local_only':[s for s in loc20 if s not in plat20],'common':[s for s in plat20 if s in loc20]}
rows=[]
for bucket,syms in sets.items():
 for s in syms:
  j=stocks.get_loc(s) if s in stocks else -1
  if j<0: rows.append({'bucket':bucket,'symbol':s,'available_local':False,'peer_rank':peer_rank.get(s)});continue
  vals=contrib[:,j]
  finite_vals=np.isfinite(vals)
  largest_leg=(int(np.nanargmax(np.abs(vals)))+1) if finite_vals.any() else None
  local_rank=(int((mask&np.isfinite(comp)&(comp>comp[j])).sum()+1)
              if np.isfinite(comp[j]) else None)
  rows.append({'bucket':bucket,'symbol':s,'available_local':True,
               'peer_rank':peer_rank.get(s),'local_rank':local_rank,
               'local_composite':float(comp[j]) if np.isfinite(comp[j]) else None,
               'leg_contributions':{f'leg{k+1}':(float(v) if np.isfinite(v) else None)
                                     for k,v in enumerate(vals)},
               'largest_abs_leg':largest_leg})
report={'signal_date':'20261008','trade_date':'20261009','platform_top20':plat20,'local_top20':loc20,'platform_only':sets['platform_only'],'local_only':sets['local_only'],'rows':rows,'interpretation':['Platform-only and local-only sets are field/mask diagnostics, not proof of a single faulty field.','Composite values are local equal-weight standardized contributions; platform factor values are not byte-comparable.','No opponent weight change is assumed.']}
(OUT/'platform_feedback_attribution.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# star_coin 平台反馈的本地逐腿归因','','本次只解释平台原生结果与本地等权复刻的排序差异，不调对手权重。','',f"平台 Top20 与本地 Top20 的平台独有项：{', '.join(sets['platform_only'])}",f"本地独有项：{', '.join(sets['local_only'])}",'','|类别|代码|对手名次|本地名次|本地综合值|绝对贡献最大的腿|','|---|---|---:|---:|---:|---:|']
for x in rows:
 value = x.get('local_composite')
 value_text = '—' if value is None else f'{value:.4f}'
 lines.append(
  f"|{x['bucket']}|{x['symbol']}|{x.get('peer_rank','—')}|"
  f"{x.get('local_rank','—')}|{value_text}|{x.get('largest_abs_leg','—')}|"
 )
lines += ['', '## 结论', '', '平台反馈支持继续修正本地字段代理：优先排查 EP/CFP/SP/BM 的 PIT 时点、缺失传播和可交易过滤。由于平台没有逐腿输出，当前归因只用于缩小排查范围，不能把某一腿直接判定为错误。']
(OUT/'platform_feedback_attribution.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'platform_only':sets['platform_only'],'local_only':sets['local_only'],'rows':len(rows)},ensure_ascii=False))
