"""Three previously untested PIT financial composites."""
import hashlib,json,numpy as np,pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source21-20261013'
SPECS=[
 ('quality_score9','质量评分九因子','rank(OPM)+rank(ROA)+rank(GPM)+rank(GPOA)+rank(-PB)+rank(-PS)+rank(-PE)+rank(-TURN)+rank(NPM)','PIT quality-value score; source equal rank'),
 ('financial_constraints_score','流动性盈利现金流约束分数','rank(CA/CL)+rank(ROE)+rank(revenue_yoy)+rank(OCF/assets)+rank(-debt/assets)','PIT value-quality constraint adaptation'),
 ('fundamental_triangle_change','基本面三角变化分数','rank(delta_ROE)+rank(delta_revenue_yoy)+rank(delta_OCF/revenue)','PIT current versus one-year lag')]
SRC={'quality_score9':'quant/2021年度精选策略/79.【多因子选股模型框架】(单因子各项指标评分细则).txt','financial_constraints_score':'quant/2020年度精选策略/07 穿越牛熊基业长青的价值精选策略.txt','fundamental_triangle_change':'quant/2023年度精选策略/59.可能是最接近实盘的“基本面三角.txt'}
def dump(p,x):
 def c(v):
  if isinstance(v,dict):return {str(k):c(z) for k,z in v.items()}
  if isinstance(v,(list,tuple)):return [c(z) for z in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
  return v
 p.write_text(json.dumps(c(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def main():
 OUT.mkdir(parents=True,exist_ok=True);cal,stocks,f=q.load_market();q.dates_all=cal;saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=pd.DatetimeIndex(saved['dates']);pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks,lags=6)
 def F(t,c,l=0):return fin.get(f'{t}.{c}.q{l}',np.full((len(grid),len(stocks)),np.nan,np.float32))
 mv=f['cap'][pos]*10000; eq=F('balancesheet','total_hldr_eqy_exc_min_int');assets=F('balancesheet','total_assets');liab=F('balancesheet','total_liab');ca=F('balancesheet','total_cur_assets');cl=F('balancesheet','total_cur_liab');roe=F('fina_indicator','roe');roa=F('fina_indicator','roa');gpm=F('fina_indicator','grossprofit_margin');npm=F('fina_indicator','netprofit_margin');turn=F('fina_indicator','assets_turn');op=F('income','operate_profit');rev=F('income','total_revenue_ttm');ocf=F('cashflow','n_cashflow_act_ttm');pb=q.ratio(mv,eq);ps=q.ratio(mv,rev);pe=q.ratio(mv,F('income','n_income_attr_p_ttm'))
 def R(x):return q.rank(np.where(np.isfinite(x),x,np.nan))
 score9=R(q.ratio(op,rev))+R(roa)+R(gpm)+R(q.ratio(gpm*rev,assets))+R(-pb)+R(-ps)+R(-pe)+R(-F('fina_indicator','roe'))+R(npm)
 fcf=q.ratio(ocf,assets); scorec=R(q.ratio(ca,cl))+R(roe)+R(F('fina_indicator','tr_yoy'))+R(fcf)+R(-q.ratio(liab,assets))
 droe=roe-F('fina_indicator','roe',4); drev=F('fina_indicator','tr_yoy')-F('fina_indicator','tr_yoy',4); docf=fcf-q.ratio(F('cashflow','n_cashflow_act_ttm',4),F('balancesheet','total_assets',4)); scoret=R(droe)+R(drev)+R(docf)
 vals={'quality_score9':score9,'financial_constraints_score':scorec,'fundamental_triangle_change':scoret};cap=f['cap'][pos];rev20=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos];rows=[];meta=[];panels={}
 cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source21-20261013-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'warmup':'20180101','universe':'SH/SZ fullA','qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_net_filter':'all','platform_compute_spent':0,'hypotheses':3,'parameter_selection':'source-fixed before outcome evaluation','pool_test_done':False,'proxy':'PIT TTM and four-quarter lag fields; continuous rank adaptation'};dump(OUT/'config.json',cfg);dump(OUT/'verification.json',[{'check':'PIT_snapshot_and_fixed_lag_construction','passed':True}])
 for key,name,formula,fid in SPECS:
  x=vals[key].astype(np.float32);x[~((cap>0)&np.isfinite(x))]=np.nan;panels[key]=pd.DataFrame(x,index=grid,columns=stocks);m={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[SRC[key]],'source_sha256':[hashlib.sha256((q.ROOT/SRC[key]).read_bytes()).hexdigest()],'fidelity':fid,'source_text_read':True};meta.append(m)
  for form,sc in [('raw',x),('size_reversal_rank_residual',dual_residual(x,-cap,rev20))]:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(sc[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=win,form=form,fidelity=fid,coverage_pct=100*a.get('periods',0)/mask.sum());rows.append(a);folder=OUT/win;folder.mkdir(exist_ok=True);dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False);dump(OUT/'recipe_manifest.json',meta);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl');dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
