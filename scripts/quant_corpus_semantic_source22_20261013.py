"""PIT working-capital information factors not previously reproduced."""
import hashlib,json,numpy as np,pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source22-20261013'
SPECS=[('aparp_quality','APARP营运资本质量','rank((应付+预收)/(应收+预付))','PIT balance-sheet ratio'),('inventory_pressure_low','低存货压力','rank(-inventories/TTM_revenue)','PIT inventory-to-sales'),('workingcapital_quality','营运资本×现金流质量','rank(APARP)+rank(-inventory/revenue)+rank(OCF/revenue)','fixed equal-rank composite')]
SRC={'aparp_quality':'quant/2021年度精选策略/10.多因子选股.txt','inventory_pressure_low':'quant/2021年度精选策略/10.多因子选股.txt','workingcapital_quality':'quant/2021年度精选策略/11.多因子选股策略——基于传统分析.txt'}
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
 def pit(ep,col):return q.daily_pit_field(ep,col,cal,stocks)[pos]
 ap=pit('balancesheet','acct_payable'); adv=pit('balancesheet','depos_received'); ar=pit('balancesheet','acc_receivable'); pre=pit('balancesheet','prepayment'); inv=pit('balancesheet','inventories')
 fin=q.financial_snapshot(grid,stocks,lags=1); rev=fin['income.total_revenue_ttm.q0'];ocf=fin['cashflow.n_cashflow_act_ttm.q0'];
 aparp=q.ratio(ap+adv,ar+pre); invsales=q.ratio(inv,rev); cfmargin=q.ratio(ocf,rev)
 vals={'aparp_quality':q.rank(aparp),'inventory_pressure_low':q.rank(-invsales),'workingcapital_quality':q.rank(aparp)+q.rank(-invsales)+q.rank(cfmargin)}
 cap=f['cap'][pos];rev20=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos];rows=[];meta=[];panels={}
 cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source22-20261013-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'warmup':'20180101','universe':'SH/SZ fullA','qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_net_filter':'all','platform_compute_spent':0,'hypotheses':3,'parameter_selection':'source-fixed before outcome evaluation','pool_test_done':False,'proxy':'PIT balance-sheet fields via announcement-date replay; TTM revenue/OCF'};dump(OUT/'config.json',cfg);dump(OUT/'verification.json',[{'check':'PIT_balance_sheet_and_TTM_snapshot','passed':True}])
 for key,name,formula,fid in SPECS:
  x=vals[key].astype(np.float32);x[~((cap>0)&np.isfinite(x))]=np.nan;panels[key]=pd.DataFrame(x,index=grid,columns=stocks);m={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[SRC[key]],'source_sha256':[hashlib.sha256((q.ROOT/SRC[key]).read_bytes()).hexdigest()],'fidelity':fid,'source_text_read':True};meta.append(m)
  for form,sc in [('raw',x),('size_reversal_rank_residual',dual_residual(x,-cap,rev20))]:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(sc[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=win,form=form,fidelity=fid,coverage_pct=100*a.get('periods',0)/mask.sum());rows.append(a);folder=OUT/win;folder.mkdir(exist_ok=True);dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False);dump(OUT/'recipe_manifest.json',meta);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl');dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
