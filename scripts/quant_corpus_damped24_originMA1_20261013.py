"""All three literal damping configurations and through-origin MA filter."""
import argparse,json
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_lowlog2_motion36_20261013 import rsrs_series
from quant_corpus_trenddamping_exact_20261013 import trend_at
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/24.宽基ETF动量轮动钝化RSRS择时-回撤小.txt'
B='quant/2024年度精选策略2/1.一颗耀眼的星—【回顾2】小市值成长股策略更新—改.txt'
SPECS149=[spec(f'damped24_rsrs18_{m}_source','十八日RSRS钝化'+str(m),A,f'Z{m}(beta18)*R2_18**(2*lastpercentilerank{m}(sampleSTD18ret))',
 f'proxy fullAstock extension of source index configuration M={m}, sourceN18 fixed. Literalrolling{m} beta/popSTD and volatility/sampleSTD with average inclusive ranks. Selectedindexthresholds .7/1/.4 and BUY/KEEP persistentportfolio/cashfund/2%intraday and10%accountDD stops not represented by highrankatom. Source800/700/500 not source83N16/M600. No window selected by performance.') for m in [700,800,500]]
SPECS150=[
 spec('growth1_originMA20_slope20','二十均线强制过原点斜率',B,'round(100*sum(x*(MA20[-20:]-firstMA))/sum(x*x),1); x=0..19',
 'proxy literal sm.OLS(y-first,x) WITHOUT constant, NOT centeredOLS slope or20dailyreturn. Uses40completedprices thenrolling20.iloc20. Source only prohibits NEWholding ifscore<-2, does notsell existing atthreshold; continuousrank newadaptation. MissingSG/MS/PEGvendor,circMV and actualholdingrisk omitted.'),
 spec('growth1_originMA20_newentry_allowed','二十均线新开仓非下跌门',B,'I(round(100*OLSnoIntercept20(MA20-first),1)>=-2)',
 'proxy source exact newentryrule adaptation to everyfullAstock; incumbentholdexception not fabricated asstate, binarytiesaudited; inputcurrentcompletedclose replaces priorpricecall.'),
 spec('damped24_logtrend29_atom','钝化轮动二十九价趋势原子',A,'expm1(250*OLS29(logC).slope)*R2',
 'proxy threeindex tofullAstock; currentcompletedbar, originalpriorbar timeproxy explicit. Actual29pricepoints, unweighted, no positivefilter. Source active indexorders/cashfund/selectedindexRSRS andportfolioDD not whole reproduced.')]

def values(f,pos,batch):
 c=f['close'].astype(float)
 if batch==150:
  ma=pd.DataFrame(c).rolling(20).mean().to_numpy();x=np.arange(20);out=np.full((len(pos),c.shape[1]),np.nan)
  for i,t in enumerate(pos):
   a=ma[t-19:t+1];out[i]=np.round(100*(x[:,None]*(a-a[0])).sum(axis=0)/(x*x).sum(),1)
  return [out,np.where(np.isfinite(out),(out>=-2).astype(float),np.nan),trend_at(c,pos,29)]
 h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));cv=h.rolling(18).cov(l,ddof=0);vl=l.rolling(18).var(ddof=0);vh=h.rolling(18).var(ddof=0);beta=cv/vl;r2=(cv**2/(vl*vh)).clip(0,1)
 ret=pd.DataFrame(c).pct_change(fill_method=None);vol=ret.rolling(18).std(ddof=1);out=[]
 for m in [700,800,500]:
  z=(beta-beta.rolling(m).mean())/beta.rolling(m).std(ddof=0);vq=vol.rolling(m).rank(method='average',pct=True)
  out.append((z*r2**(2*vq)).to_numpy()[pos])
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',type=int,choices=[149,150],required=True);batch=p.parse_args().batch;specs=SPECS149 if batch==149 else SPECS150
 out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{batch}-20261013';out.mkdir(exist_ok=True);plan=dict(specs=specs,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all3literalindexconfigs or actualnointerceptMA/29trend, beforeoutcomes')
 fp=out/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (out/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:32] for k,v in f.items()};full=values(sf,pos,batch);checks=[]
 for nn in [35,79]:
  cut=values({k:v[:pos[nn-1]+1] for k,v in sf.items()},pos[:nn],batch)
  for sp,a,b in zip(specs,full,cut):
   np.testing.assert_allclose(a[:nn],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(8):
   if batch==150:
    a=pd.Series(sf['close'][t-39:t+1,j].astype(float)).rolling(20).mean().iloc[20:].to_numpy();x=np.arange(20)
    if np.isfinite(a).all():np.testing.assert_allclose(full[0][i,j],np.round(100*np.linalg.lstsq(x[:,None],a-a[0],rcond=None)[0][0],1),atol=1e-8)
   else:
    for k,m in enumerate([700,800,500]):
     slopes=[];vols=[];lastR=np.nan
     for end in range(t-m+1,t+1):
      lo=sf['low'][end-17:end+1,j].astype(float);hi=sf['high'][end-17:end+1,j].astype(float);c=sf['close'][end-18:end+1,j].astype(float)
      if not np.isfinite(lo).all() or not np.isfinite(hi).all() or lo.std()==0:slopes.append(np.nan)
      else:slopes.append(np.polyfit(lo,hi,1)[0]);lastR=np.corrcoef(lo,hi)[0,1]**2
      vols.append(np.std(c[1:]/c[:-1]-1,ddof=1) if np.isfinite(c).all() else np.nan)
     a=np.array(slopes);b=np.array(vols)
     if np.isfinite(a).all() and np.isfinite(b).all():np.testing.assert_allclose(full[k][i,j],(a[-1]-a.mean())/a.std()*lastR**(2*rankdata(b)[-1]/m),atol=1e-5)
 checks.append(dict(test='independent_literal_nointercept_lstsq' if batch==150 else 'independent_all3_OLS18_beta_popZ_samplevol_avgpercentile',passed=True))
 q.dump(out/'source_evidence.json',{src:read_text(q.ROOT/src) for src in sorted(set(s['source_paths'][0] for s in specs))})
 run(out,specs,values(f,pos,batch),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='index/ETF/holding dailyproxy explicit'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 if batch==150:tie_diagnostic(out,cal,stocks,f)
 audit(out,cal,stocks,f);q.dump(out/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED',batch,flush=True)
if __name__=='__main__':main()
