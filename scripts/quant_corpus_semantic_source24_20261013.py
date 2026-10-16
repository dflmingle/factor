"""Decompose the newly found small/value rank candidate into independent legs."""
import hashlib,json,numpy as np,pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source24-20261013';SRC='quant/2022年度精选策略/100.实战型小盘价值策略--14年30倍.txt'
SPECS=[('value_rank3','低PB/PE/PCF三项排名','-(rank(PB)+rank(PE)+rank(PCF))','size leg removed'),('value_rank3_roe','低估值×ROE质量','-(rank(PB)+rank(PE)+rank(PCF))+rank(ROE)','fixed equal-rank decomposition'),('value_rank3_lowturn','低估值×低换手','-(rank(PB)+rank(PE)+rank(PCF))+rank(-turnover)','fixed equal-rank decomposition')]
def dump(p,x):
 def c(v):
  if isinstance(v,dict):return {str(k):c(z) for k,z in v.items()}
  if isinstance(v,(list,tuple)):return [c(z) for z in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
  return v
 p.write_text(json.dumps(c(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def main():
 OUT.mkdir(parents=True,exist_ok=True);cal,stocks,f=q.load_market();q.dates_all=cal;saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=pd.DatetimeIndex(saved['dates']);pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks,lags=1)
 def F(t,c):return fin.get(f'{t}.{c}.q0',np.full((len(grid),len(stocks)),np.nan,np.float32))
 mv=f['cap'][pos]*10000;eq=F('balancesheet','total_hldr_eqy_exc_min_int');inc=F('income','n_income_attr_p_ttm');ocf=F('cashflow','n_cashflow_act_ttm');pb=q.ratio(mv,eq);pe=q.ratio(mv,inc);pcf=q.ratio(mv,ocf);roe=F('fina_indicator','roe');turn=F('fina_indicator','assets_turn')*0+q.rolling(f['turnover'],20)[pos]
 vals={'value_rank3':-q.rank(pb)-q.rank(pe)-q.rank(pcf),'value_rank3_roe':-q.rank(pb)-q.rank(pe)-q.rank(pcf)+q.rank(roe),'value_rank3_lowturn':-q.rank(pb)-q.rank(pe)-q.rank(pcf)+q.rank(-turn)}
 cap=f['cap'][pos];rev=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos];rows=[];meta=[];panels={};cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source24-20261013-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'warmup':'20180101','universe':'SH/SZ fullA','qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_net_filter':'all','platform_compute_spent':0,'hypotheses':3,'parameter_selection':'source-fixed before outcome evaluation','pool_test_done':False,'decomposition_of':'small_value_rank4'};dump(OUT/'config.json',cfg)
 for key,name,formula,fid in SPECS:
  x=vals[key].astype(np.float32);x[~((cap>0)&np.isfinite(x))]=np.nan;panels[key]=pd.DataFrame(x,index=grid,columns=stocks);m={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[SRC],'source_sha256':[hashlib.sha256((q.ROOT/SRC).read_bytes()).hexdigest()],'fidelity':fid};meta.append(m)
  for form,sc in [('raw',x),('size_reversal_rank_residual',dual_residual(x,-cap,rev))]:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(sc[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=win,form=form,fidelity=fid,coverage_pct=100*a.get('periods',0)/mask.sum());rows.append(a);folder=OUT/win;folder.mkdir(exist_ok=True);dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False);dump(OUT/'recipe_manifest.json',meta);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl');dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
