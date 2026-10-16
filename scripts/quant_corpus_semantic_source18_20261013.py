"""FFScore-style financial change factors, frozen from the 2023 source."""
import hashlib,json
import numpy as np,pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source18-20261013'
SRC='quant/2023年度精选策略/18.【复现】FFScore财务模型.txt'
SPECS=[('ffscore6_count','FFScore六项变化计数','sum(I(delta ROE, ROA, margin, asset_turnover, ROA2, liquidity)>0)','continuous count; no sparse gate'),('ffscore6_bm','FFScore六项×BM','rank(score6)+rank(BM)','fixed equal-rank composite'),('ffscore6_quality','FFScore六项质量分','score6/6','continuous quality score')]
def dump(p,x):
 def c(v):
  if isinstance(v,dict):return {str(k):c(z) for k,z in v.items()}
  if isinstance(v,(list,tuple)):return [c(z) for z in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
  return v
 p.write_text(json.dumps(c(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def main():
 OUT.mkdir(parents=True,exist_ok=True); cal,stocks,f=q.load_market();q.dates_all=cal
 saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=pd.DatetimeIndex(saved['dates']);pos=cal.get_indexer(grid)
 fin=q.financial_snapshot(grid,stocks,lags=6)
 def F(t,c,l):return fin.get(f'{t}.{c}.q{l}',np.full((len(cal),len(stocks)),np.nan,np.float32))
 # Source's six enabled changes, all PIT and one-year (four-quarter) deltas.
 legs=[F('fina_indicator','roe',0)-F('fina_indicator','roe',4),F('fina_indicator','roa',0)-F('fina_indicator','roa',4),F('fina_indicator','grossprofit_margin',0)-F('fina_indicator','grossprofit_margin',4),F('fina_indicator','assets_turn',0)-F('fina_indicator','assets_turn',4),F('fina_indicator','roa',0)-F('fina_indicator','roa',4),F('fina_indicator','current_ratio',0)-F('fina_indicator','current_ratio',4)]
 stack=np.stack(legs); valid=np.isfinite(stack).all(axis=0); score=np.where(valid,np.sum(stack>0,axis=0),np.nan)
 bm=q.ratio(F('balancesheet','total_hldr_eqy_exc_min_int',0),f['cap'][pos]*10000);bm=np.where(bm>0,bm,np.nan)
 vals={'ffscore6_count':score,'ffscore6_bm':q.rank(score)+q.rank(bm),'ffscore6_quality':score/6.0}
 cap=f['cap'][pos];rev=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos];rows=[];meta=[];panels={}
 cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source18-20261013-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'warmup':'20180101','universe':'SH/SZ fullA','qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_net_filter':'all','platform_compute_spent':0,'hypotheses':3,'parameter_selection':'source-fixed before outcome evaluation','pool_test_done':False,'proxy':'PIT six-change fields; duplicate ROA2 retained as source declaration'}
 dump(OUT/'config.json',cfg);dump(OUT/'verification.json',[{'check':'PIT_snapshots_and_fixed_four_quarter_deltas','passed':True}])
 for key,name,formula,*_ in SPECS:
  x=vals[key].astype(np.float32);x[~((cap>0)&np.isfinite(x))]=np.nan;panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  m={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[SRC],'source_sha256':[hashlib.sha256((q.ROOT/SRC).read_bytes()).hexdigest()],'fidelity':'PIT FFScore source adaptation; original PB gate and stock pool not reproduced','source_text_read':True};meta.append(m)
  forms={'raw':x,'size_reversal_rank_residual':dual_residual(x,-cap,rev)}
  for form,sc in forms.items():
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(sc[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=win,form=form,fidelity=m['fidelity'],coverage_pct=100*a.get('periods',0)/mask.sum());rows.append(a);folder=OUT/win;folder.mkdir(exist_ok=True);dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False);dump(OUT/'recipe_manifest.json',meta);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl');dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
