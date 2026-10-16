"""Source-fixed new recipes: Normalize_Trend60 strength/activity, ROE-PB. Offline."""
import hashlib,json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source4-20261012'
SPECS=[('trend_absolute60','归一走势绝对点势60','80.','sum squared increments between all min/max points and endpoints of compound sign path; MA5 within60, slice at3'),('trend_activity60','归一走势趋60','80.','last-first of compound sign path; MA5 within60, slice at3'),('roe_minus_pb','ROE减PB','65.','latest PIT ROE(percent)-total_mv*10000/latest PIT equity; positive equity')]
@njit(cache=True)
def trend_scores(c):
 out=np.full((2,c.shape[0],c.shape[1]),np.nan,np.float32)
 for j in range(c.shape[1]):
  for t in range(59,c.shape[0]):
   w=c[t-59:t+1,j].astype(np.float64);valid=True
   for k in range(60):
    if not np.isfinite(w[k]) or w[k]<=0:valid=False
   if not valid:continue
   # source iloc[window-2:] includes index3 NaN -> fillna0
   path=np.zeros(57,np.float64);level=0.
   for k in range(4,60):
    ma=np.mean(w[k-4:k+1]);level+=(np.sign(w[k]/w[k-1]-1)+np.sign(w[k]-ma))/2
    path[k-3]=level
   lo=np.min(path);hi=np.max(path);previous=path[0];strength=0.
   for k in range(1,57):
    if k==56 or path[k]==lo or path[k]==hi:
     strength+=(path[k]-previous)**2;previous=path[k]
   out[0,t,j]=strength;out[1,t,j]=path[-1]-path[0]
 return out

def verify(c):
 small=c[:,np.flatnonzero(np.isfinite(c[-700:]).all(axis=0))[:4]]
 full=trend_scores(small);checks=[]
 for stop in [900,1400,len(c)-31]:
  np.testing.assert_allclose(full[:,:stop],trend_scores(small[:stop]),equal_nan=True)
  checks.append({'check':'prefix_recompute','stop':stop,'passed':True})
 for t in [900,1500,len(c)-1]:
  for j in range(4):
   w=pd.Series(small[t-59:t+1,j].astype(float))
   u=((np.sign(w.pct_change())+np.sign(w-w.rolling(5).mean()))/2).iloc[3:].cumsum().fillna(0)
   points=sorted(set([0,len(u)-1]+np.flatnonzero((u==u.min())|(u==u.max())).tolist()))
   expected=[np.square(u.iloc[points].diff()).sum(),u.diff().sum()]
   np.testing.assert_allclose(full[:,t,j],expected,rtol=1e-6,atol=1e-6)
 checks.append({'check':'independent_pandas_literal','stocks':4,'dates':3,'passed':True})
 return checks

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 calendar,stocks,f=q.load_market();q.dates_all=calendar
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 cfg={'alignment_rule_version':q.ALIGNMENT_RULE_VERSION,'formal_window':['20210907','20260907'],'recent_window':['20260101',str(calendar.max().date())],'warmup':'20180101','universe':'SH/SZ fullA total_mv>0','qfq':True,'cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','annualization':'arithmetic','platform_net_filter':'all','platform_compute_spent':0,'source_fixed_hypotheses':3,'direction':1,'oos':False,'fidelity':'new research proxy; full strategy execution not reproduced; source constraints separately described in ledger'}
 if (OUT/'config.json').exists() and json.loads((OUT/'config.json').read_text())!=cfg:raise ValueError('incompatible output')
 q.dump(OUT/'config.json',cfg);q.dump(OUT/'verification.json',verify(f['close']))
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks)
 pb=q.ratio(f['cap']*10000,np.where(eq>0,eq,np.nan))
 trend=trend_scores(f['close']);print('recipes built',flush=True)
 values=[trend[0],trend[1],roe-pb]
 c=f['close'];r=q.ratio(c,q.delay(c))-1
 days=np.flatnonzero((calendar>='20210907')&(calendar<='20260907'))
 anchors={'B01|SIZE':-f['cap'][days],'N01|REV20':-(q.ratio(c,q.delay(c,20))-1)[days],'N08|TURN_STD21':-q.rolling(f['turnover'],21,'std')[days],'B08|BM':q.ratio(eq,f['cap']*10000)[days],'N27|ROE':roe[days]}
 del eq,roe,pb
 results=[];corrs=[];manifest=[];panels={}
 for spec,allx in zip(SPECS,values):
  key,name,prefix,formula=spec;allx[~(f['cap']>0)]=np.nan;x=allx[pos]
  source=next((q.ROOT/'quant/2023年度精选策略').glob(prefix+'*.txt'))
  meta={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[str(source.relative_to(q.ROOT))],'source_sha256':[hashlib.sha256(source.read_bytes()).hexdigest()],'fidelity':cfg['fidelity']};manifest.append(meta)
  residual=dual_residual(x,-f['cap'][pos],-(q.ratio(c,q.delay(c,20))-1)[pos])
  panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  for window,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
   folder=OUT/window;folder.mkdir(exist_ok=True)
   for form,score in [('raw',x),('size_reversal_rank_residual',residual)]:
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],f);a.update(key=key,name=name,window=window,form=form,coverage_pct=a['periods']/mask.sum()*100);results.append(a)
    q.dump(folder/f'{key}.{form}.json',a);p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  for anchor,y in anchors.items():corrs.append({'candidate':key,'anchor':anchor,**rho_details(allx[days],y)})
  pd.DataFrame(results).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
  pd.DataFrame(corrs).to_csv(OUT/'daily_old_anchor_correlations.csv',index=False);q.dump(OUT/'recipe_manifest.json',manifest)
  print('completed',key,'five-year',results[-4]['net_excess_pct'],'recent',results[-2]['net_excess_pct'],flush=True)
 pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':manifest},OUT/'signal_panels.pkl')
 q.dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(results),'correlations':len(corrs),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
