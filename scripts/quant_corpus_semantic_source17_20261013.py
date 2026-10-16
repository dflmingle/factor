"""Previously untested price-shape and short-horizon gap atoms."""
import hashlib, json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source17-20261013'
SOURCES={
 'high_open20':'quant/2022年度精选策略/16.选股因子系列研究(十八) — 价格形态选股因子.txt',
 'close_low20':'quant/2022年度精选策略/16.选股因子系列研究(十八) — 价格形态选股因子.txt',
 'vwap_close20':'quant/2022年度精选策略/16.选股因子系列研究(十八) — 价格形态选股因子.txt',
 'gap10_low':'quant/2022年度精选策略/19.a股跳一跳复现v4.txt',
 'gap10_abs_low':'quant/2022年度精选策略/19.a股跳一跳复现v4.txt',
 'range_position20_low':'quant/2022年度精选策略/16.选股因子系列研究(十八) — 价格形态选股因子.txt',
}
SPECS=[
 ('high_open20','20日高开幅度','-mean(log(high/open),20)','source narrative low direction'),
 ('close_low20','20日收盘相对日低','mean(log(close/low),20)','source model positive direction'),
 ('vwap_close20','20日成交均价相对收盘','mean(log(vwap/close),20)','qfq VWAP proxy'),
 ('gap10_low','10日平均隔夜跳空','-mean(open/lag(close)-1,10)','signed gap, low preferred'),
 ('gap10_abs_low','10日平均绝对跳空','-mean(abs(open/lag(close)-1),10)','absolute gap, low preferred'),
 ('range_position20_low','20日收盘位置低','-mean((close-low)/(high-low),20)','low close position source variant'),
]
def dump(p,x):
 def c(v):
  if isinstance(v,dict):return {str(k):c(z) for k,z in v.items()}
  if isinstance(v,(list,tuple)):return [c(z) for z in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
  return v
 p.write_text(json.dumps(c(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def rho(x,y):
 z=[]
 for a,b in zip(x,y):
  ok=np.isfinite(a)&np.isfinite(b)
  if ok.sum()>=100:z.append(np.corrcoef(rankdata(a[ok]),rankdata(b[ok]))[0,1])
 return float(np.nanmean(z)) if z else np.nan
def build(f):
 c,o,h,l,v,amt,cap=[f[k].astype(float) for k in ['close','open','high','low','volume','amount','cap']]
 gap=q.ratio(o,q.delay(c))-1
 vwap=q.ratio(amt*1000,v*100)*q.ratio(c,f['raw_close'])
 rng=q.ratio(c-l,h-l)
 return {'high_open20':-q.rolling(np.log(q.ratio(h,o)),20),
         'close_low20':q.rolling(np.log(q.ratio(c,l)),20),
         'vwap_close20':q.rolling(np.log(q.ratio(vwap,c)),20),
         'gap10_low':-q.rolling(gap,10),
         'gap10_abs_low':-q.rolling(np.abs(gap),10),
         'range_position20_low':-q.rolling(rng,20)}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 cal,stocks,f=q.load_market();q.dates_all=cal
 saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=pd.DatetimeIndex(saved['dates']);pos=cal.get_indexer(grid)
 allv=build(f); cap=f['cap'][pos]; rev=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos]
 cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source17-20261013-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(cal.max().date())],'warmup':'20180101','universe':'SH/SZ fullA','qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_net_filter':'all','platform_compute_spent':0,'hypotheses':len(SPECS),'parameter_selection':'source-fixed before outcome evaluation','pool_test_done':False,'proxy':'VWAP=amount/volume adjusted by qfq close/raw close'}
 dump(OUT/'config.json',cfg); rows=[];corr=[];panels={};meta=[]
 for key,name,formula,fidelity in SPECS:
  x=allv[key][pos].astype(np.float32); x[~((cap>0)&np.isfinite(x))]=np.nan;panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  m={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[SOURCES[key]],'source_sha256':[hashlib.sha256((q.ROOT/SOURCES[key]).read_bytes()).hexdigest()],'fidelity':fidelity,'source_text_read':True,'execution':'offline signal extraction'};meta.append(m)
  forms={'raw':x,'size_reversal_rank_residual':dual_residual(x,-cap,rev)}
  for form,score in forms.items():
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=win,form=form,fidelity=fidelity,coverage_pct=100*a.get('periods',0)/mask.sum());rows.append(a)
    folder=OUT/win;folder.mkdir(exist_ok=True);dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  for anchor,y in [('size',-cap),('reversal20',rev)]:corr.append({'candidate':key,'anchor':anchor,'mean_daily_cs_spearman':rho(x,y)})
  print(key,[(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-4:]],flush=True)
 pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False);pd.DataFrame(corr).to_csv(OUT/'daily_old_anchor_correlations.csv',index=False);dump(OUT/'recipe_manifest.json',meta);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl');dump(OUT/'completion.json',{'completed':True,'hypotheses':len(SPECS),'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
