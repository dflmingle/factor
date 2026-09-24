"""Offline pool screening; canonical return proxy, not official A/B/C scoring."""
from pathlib import Path
import gc,json
import numpy as np
import pandas as pd
import exhaustive_representative_combination as e

import os

OUT=Path(os.environ.get('POOL_SCREEN_OUT','research_reports/platform_alignment/pool-screen-20260921'))
BASE={'SIZE','H03','RET40','DD120','CHIP250','DD60','ASSET_GROWTH'}

def main():
 OUT.mkdir(exist_ok=True)
 _,cs=e._load_candidates(e.DEFAULT_ALIGNMENT_REPORT)
 cs=[c for c in cs if c['key'] in BASE]
 cache=OUT/'signals.pkl'
 if cache.exists():
  sf,raw,returns,dates=pd.read_pickle(cache)
 else:
  cal=[pd.Timestamp(x).normalize() for x in e.ensure_calendar(e.DATA_START,e.END,token=None)]
  dates=e._common_schedule(cal)
  print('loading full-A panel',flush=True)
  frame=e.select_market_cap(e.load_full_a_data(e.DEFAULT_PRICE_ROOT,e.DEFAULT_CAP_ROOT,e.DATA_START,e.END),'total_mv').sort_values(['instrument','date'],ignore_index=True)
  close=e.panel_close(frame,cal); returns=e.forward_returns(close,cal,dates,10,1)
  mask=frame.date.isin(dates); sf=frame.loc[mask,['date','instrument']].reset_index(drop=True)
  fin=e.load_financial_cache(e.DEFAULT_FINANCIAL_ROOT); raw={}
  for c in cs:
   print('building '+c['key'],flush=True)
   v=e.build_factor(frame,c['handler'],financial=fin,signal_dates=dates)
   raw[c['handler']]=pd.to_numeric(v.loc[mask].reset_index(drop=True),errors='coerce')
   del v; gc.collect()
  pd.to_pickle((sf,raw,returns,dates),cache)
  del frame,fin,close; gc.collect()
 # Reverse growth rank up to a date-wise additive constant, which cannot affect pool Z-scores.
 r=raw['reversal40']; c=raw['chip250']; g=-raw['asset_growth']; dd=raw['drawdown120']
 for key,value in [('C01',(r+c+g)/3),('C02',(r+dd+c+g)/4),('C03',(r+dd+g)/3)]:
  raw[key]=value
  cs.append(dict(key=key,handler=key,direction=1,cluster='composite',name='F-C260921-'+key[-2:],source_cycle=10,alignment_quality='pending_formula_audit'))
 keys=[c['key'] for c in cs]
 scores=e._competition_cross_sectional_scores(sf,raw,cs)
 blocks=e._build_blocks(sf,scores,returns,dates,keys)
 ds,offsets,fs,fr,fi,_=e._flatten_blocks(blocks,len(keys))
 bitmasks,masks,sizes,labels=e._combination_catalog(keys)
 print('evaluating '+str(len(bitmasks))+' subsets',flush=True)
 held,gross,turn,counts,valid=e._evaluate_combinations_numba(fs,fr,fi,offsets,masks,sizes)
 windows={'full':np.ones(len(ds),bool),'train':ds<=e.TRAIN_END.to_datetime64(),'test':ds>e.TRAIN_END.to_datetime64(),'recent':ds>=e.RECENT_START.to_datetime64()}
 rows=[]
 for j,b in enumerate(bitmasks):
  row={'bitmask':int(b),'components':'+'.join(k for i,k in enumerate(keys) if masks[j,i]),'factor_count':int(sizes[j])}
  for w,m in windows.items():
   s=e._summary(held[j],gross[j],turn[j],counts[j],valid[j].astype(bool),ds,10,w,m)
   row.update({w+'_'+k:v for k,v in s.items()})
  rows.append(row)
 df=pd.DataFrame(rows).set_index('bitmask',drop=False)
 # A from platform summaries only; no fabricated official B/C or weighted total.
 def find_stats(obj):
  if isinstance(obj,dict):
   if 'factor_data_analysis' in obj:return obj['factor_data_analysis']
   if 'query_factor_analysis_data' in obj:return obj['query_factor_analysis_data']
   for v in obj.values():
    z=find_stats(v)
    if z:return z
  if isinstance(obj,str) and obj.lstrip().startswith('{'):
   try:return find_stats(json.loads(obj))
   except (ValueError,TypeError):pass
  return None
 ac={}
 for candidate in cs:
  name=candidate['name']; report=candidate.get('source_id','').split(':')[0]+'.csv' if 'source_id' in candidate else 'cluster-blends-20260921-candidates.report.csv'
  rr=pd.read_csv(report); rr=rr[rr.name.eq(name)].iloc[0]
  stats=find_stats(json.loads(Path(rr.raw_result).read_text()))
  st={v['indicator']:v.get('factor1',v.get('factor_value')) for v in stats}
  win=float(st['P(IC>0.02)' if candidate['direction']==1 else 'P(IC<-0.02)'].strip('%'))/100
  ac[candidate['key']]=abs(float(st['Rank_IC']))*abs(float(st['IC_IR']))*win
  candidate['platform_A_raw']=ac[candidate['key']]
  candidate['platform_net']=float(rr.net_excess_pct)
  candidate['local_net']=float(df.loc[1<<keys.index(candidate['key']),'full_net_excess_pct'])
  candidate['net_gap_pp']=candidate['local_net']-candidate['platform_net']
 for idx,row in df.iterrows():
  members=row.components.split('+')
  df.loc[idx,'platform_A_raw_mean']=np.mean([ac[k] for k in members])
  df.loc[idx,'A_newcomer_no_decay_proxy']=min(df.loc[idx,'platform_A_raw_mean']/0.08,0.7)
  for w in windows:
   if len(members)>1:
    parents=[df.loc[idx^(1<<keys.index(k)),w+'_net_excess_pct'] for k in members]
    df.loc[idx,w+'_min_member_addition_pp']=row[w+'_net_excess_pct']-max(parents)
    df.loc[idx,w+'_vs_best_single_pp']=row[w+'_net_excess_pct']-max(df.loc[1<<keys.index(k),w+'_net_excess_pct'] for k in members)
 df.to_csv(OUT/'all_subsets.csv',index=False)
 pd.DataFrame(cs).to_csv(OUT/'candidates.csv',index=False)
 pools=df[df.factor_count>=5].copy()
 pools['contains_new_proxy']=pools.components.str.contains('C0')
 pools['same_B01_pair']=pools.components.map(lambda s:'SIZE' in s.split('+') and 'H03' in s.split('+'))
 pools.sort_values('train_net_excess_pct',ascending=False).to_csv(OUT/'pools.csv',index=False)
 (OUT/'metadata.json').write_text(json.dumps({'rule':e.ALIGNMENT_RULE_VERSION,'normalization':'winsor_1_99_zscore_equal','official_B':None,'official_C':None,'boundary':'canonical period-return proxy; factor_valid benchmark, not official monthly daily-book C','recent_last_signal':str(ds[-1]),'candidate_count':len(cs),'pool_count':len(pools),'new_composites':'provisional; no Top20/full formula audit; not mining eligible'},indent=2))
 print(pools.sort_values('train_net_excess_pct',ascending=False)[['components','full_net_excess_pct','train_net_excess_pct','test_net_excess_pct','recent_net_excess_pct','full_min_member_addition_pp']].head(8).to_string(index=False),flush=True)
 print('done',flush=True)
if __name__=='__main__':main()
