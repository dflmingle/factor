"""All six source notebook horizons, fixed in two local batches; no source execution."""
import argparse,json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/43.ETF动量因子评估.txt'
def specs_for(batch):
 windows=[3,5,10] if batch==142 else [20,30,60]
 return [spec(f'notebook43_normalized_slope{n}_current',f'笔记本{n}价首值归一线性斜率',A,
  f'100*OLS{n}(C/Cfirst).slope endingcurrentcompletedclose',
  f'proxy fullAstock replaces4ETF2013..2021 notebook; literal {n}PRICEpoints notreturns count, currentbar notpriorbar. HIGH directionfixed as descriptivetrend experiment; original evaluatesmultiplefuturelabels and longerhorizonnegativecorrelation prose is NOT universalcycle10direction. No pooledstockdayPearson substituted for dailyIC; no strategy/ETFperformance claim. Knownlineartrend familyhorizon, not independentnewcluster.') for n in windows]

def values(f,pos,specs):
 c=f['close'].astype(float);vals=[]
 for sp in specs:
  n=int(sp['key'].split('slope')[1].split('_')[0]);xx=np.arange(n)-(n-1)/2;out=np.full((len(pos),c.shape[1]),np.nan)
  for i,t in enumerate(pos):
   a=c[t-n+1:t+1];valid=np.isfinite(a).all(axis=0)&(a[0]>0)
   out[i]=np.where(valid,100*np.sum(xx[:,None]*(a/a[0]),axis=0)/np.sum(xx**2),np.nan)
  vals.append(out)
 return vals

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--batch',type=int,choices=[142,143],required=True);args=parser.parse_args();specs=specs_for(args.batch)
 out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{args.batch}-20261013';out.mkdir(exist_ok=True)
 plan=dict(specs=specs,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all6notebookhorizons,threeperbatch,HIGHdirectionfixed,notbestwindowselection')
 p=out/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (out/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos,specs);checks=[]
 for nn in [35,79]:
  cut=values({k:v[:pos[nn-1]+1] for k,v in sf.items()},pos[:nn],specs)
  for sp,a,b in zip(specs,full,cut):
   np.testing.assert_allclose(a[:nn],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 for sp,whole in zip(specs,full):
  n=int(sp['key'].split('slope')[1].split('_')[0])
  for i in [35,79]:
   t=pos[i]
   for j in range(64):
    a=sf['close'][t-n+1:t+1,j].astype(float)
    if np.isfinite(a).all() and a[0]>0:np.testing.assert_allclose(whole[i,j],100*np.polyfit(np.arange(n),a/a[0],1)[0],atol=1e-8)
  checks.append(dict(key=sp['key'],test='independent_literal_notebook_polyfit',passed=True))
 q.dump(out/'source_evidence.json',{A:read_text(q.ROOT/A)})
 run(out,specs,values(f,pos,specs),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='all6listednotebookkernels; onlydirectionHIGH,noholdoutwindowchoice'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(out,cal,stocks,f);q.dump(out/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED',args.batch,flush=True)
if __name__=='__main__':main()
