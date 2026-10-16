"""Continuous daily proxies for the previously untested leader weak-to-strong recipe."""
import hashlib,json,numpy as np,pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source19-20261013'
SRC='quant/2024年度精选策略2/77.龙头弱转强战法.txt'
SPECS=[('leader_range20_nearhigh','20日幅度×近高','rank(range20)+rank(-distance_to_20d_high)','continuous source proxy'),('leader_range20_gap','20日幅度×近高×温和跳空','rank(range20)+rank(-distance_to_20d_high)+rank(-abs_gap10)','continuous source proxy')]
def dump(p,x):
 def c(v):
  if isinstance(v,dict):return {str(k):c(z) for k,z in v.items()}
  if isinstance(v,(list,tuple)):return [c(z) for z in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
  return v
 p.write_text(json.dumps(c(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def main():
 OUT.mkdir(parents=True,exist_ok=True);cal,stocks,f=q.load_market();q.dates_all=cal;saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=pd.DatetimeIndex(saved['dates']);pos=cal.get_indexer(grid)
 c,h,o=f['close'],f['high'],f['open'];rng=q.ratio(q.rolling(c,20,'max'),q.rolling(c,20,'min'))-1;dist=q.ratio(q.rolling(h,20,'max'),c)-1;gap=np.abs(q.ratio(o,q.delay(c))-1);x1=q.rank(rng[pos])+q.rank(-dist[pos]);x2=x1+q.rank(-q.rolling(gap,10)[pos]);vals={'leader_range20_nearhigh':x1,'leader_range20_gap':x2}
 cap=f['cap'][pos];rev=-(q.ratio(c,q.delay(c,20))-1)[pos];rows=[];meta=[];panels={};cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source19-20261013-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'warmup':'20180101','universe':'SH/SZ fullA','qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_net_filter':'all','platform_compute_spent':0,'hypotheses':2,'parameter_selection':'source-fixed before outcome evaluation','pool_test_done':False}
 dump(OUT/'config.json',cfg)
 for key,name,formula,fid in SPECS:
  x=vals[key].astype(np.float32);x[~((cap>0)&np.isfinite(x))]=np.nan;panels[key]=pd.DataFrame(x,index=grid,columns=stocks);m={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[SRC],'source_sha256':[hashlib.sha256((q.ROOT/SRC).read_bytes()).hexdigest()],'fidelity':fid};meta.append(m)
  for form,sc in [('raw',x),('size_reversal_rank_residual',dual_residual(x,-cap,rev))]:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(sc[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=win,form=form,fidelity=fid,coverage_pct=100*a.get('periods',0)/mask.sum());rows.append(a);folder=OUT/win;folder.mkdir(exist_ok=True);dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False);dump(OUT/'recipe_manifest.json',meta);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl');dump(OUT/'completion.json',{'completed':True,'hypotheses':2,'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
