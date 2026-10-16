"""Attribution and shared-support pool checks for the fixed local survivors."""
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details,saved_grid
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-survivor-audit-20261012'
SELECT=[('source9','idio_bm_rank'),('source9','idio_ep_rank'),('source11','idio_margin_stable_rank'),
        ('source12','fixed_ff3_ivol120'),('source10','fixed_ff5_ivol504')]
POOL=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']

def residual_with_ivol(x,cap,rev,iv):
 out=np.full_like(x,np.nan)
 for i in range(len(x)):
  ok=np.isfinite(x[i])&np.isfinite(cap[i])&np.isfinite(rev[i])&np.isfinite(iv[i])
  if ok.sum()<100:continue
  design=np.column_stack([np.ones(ok.sum()),rankdata(-cap[i,ok]),rankdata(rev[i,ok]),rankdata(-iv[i,ok])])
  y=rankdata(x[i,ok]);out[i,ok]=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
 return out

def main():
 OUT.mkdir(parents=True,exist_ok=True);calendar,stocks,f=q.load_market();q.dates_all=calendar
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
 cap=f['cap'][pos];rv=-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos]
 rows=[];panels={};stats=[]
 frame,_,_,_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
 old=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
 oldpanels=[]
 for key in POOL:
  data=frame[['date','instrument']].copy();data['value']=old['scores'][key].to_numpy()
  data.date=pd.to_datetime(data.date)
  oldpanels.append(data.pivot(index='date',columns='instrument',values='value').reindex(index=grid,columns=stocks).to_numpy(dtype=np.float32))
 for batch,key in SELECT:
  root=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-{batch}-20261012'
  x=pd.read_pickle(root/'signal_panels.pkl')['panels'][key].reindex(index=grid,columns=stocks).to_numpy()
  panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  variants={'raw':x,'size_reversal_rank_residual':dual_residual(x,-cap,rv),
   'size_reversal_IVOL_rank_residual':residual_with_ivol(x,cap,rv,iv[pos])}
  # Compare each candidate with the known low-IVOL using identical support.
  mask=np.isfinite(x);known=np.where(mask,-iv[pos],np.nan)
  variants['known_IVOL_same_support']=known
  variants['known_IVOL_dual_residual_same_support']=dual_residual(known,-cap,rv)
  for form,v in variants.items():
   for win,wm in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    a,p,d=q.evaluate(v[wm],grid[wm],stocks,pos[wm],f);a.update(key=key,form=form,window=win)
    stats.append(a);dest=OUT/win;dest.mkdir(exist_ok=True)
    q.dump(dest/f'{key}.{form}.json',a);p.to_csv(dest/f'{key}.{form}.periods.csv',index=False)
  for form in ['raw','size_reversal_rank_residual']:
   candidate=variants[form];common=np.isfinite(candidate)&np.isfinite(np.stack(oldpanels)).all(axis=0)
   seats=[np.where(common,v,np.nan) for v in oldpanels];z=[q.zscore(v) for v in seats]
   base=sum(z)/5;cz=q.zscore(np.where(common,candidate,np.nan))
   scenarios={'incumbent_shared_support':base,'add6':(sum(z)+cz)/6}
   scenarios.update({f'swap_{k}':(sum(z)-z[i]+cz)/5 for i,k in enumerate(POOL)})
   for name,score in scenarios.items():
    for win,wm in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
     a,p,d=q.evaluate(score[wm],grid[wm],stocks,pos[wm],f)
     nr=dual_residual(score[wm],-cap[wm],rv[wm]);na,_,_=q.evaluate(nr,grid[wm],stocks,pos[wm],f)
     a.update(candidate=key,form=form,scenario=name,window=win,
      size_reversal_residual_net=na.get('net_excess_pct'),corr_size=rho_details(score[wm],-cap[wm])['rho'])
     rows.append(a)
  print('audit',key,flush=True)
  pd.DataFrame(stats).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'incremental_information.csv',index=False)
  pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'shared_support_pool_scenarios.csv',index=False)
 pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels},OUT/'signal_panels.pkl')
 original=q.OUT
 try:q.OUT=OUT;saved_grid()
 finally:q.OUT=original
 q.dump(OUT/'config.json',{'version':q.ALIGNMENT_RULE_VERSION+'-quant-survivor-shared-support-arithmetic-fullA',
  'shared_support':True,'incumbents':POOL,'pool':'equal per-date CS_z of saved historical score legs, restriction before scaling',
  'diagnostic_only':'legacy stored seats, no live pool platform equivalence; no scoring-Comb inference',
  'pool_scenarios':len(rows),'saved_correlations':'54 legacy references on120 saved signal dates; not daily',
  'oos':False,'platform_compute_spent':0,'candidate_selection':'selected after multi-hypothesis screen; in-sample exploratory'})
if __name__=='__main__':main()
