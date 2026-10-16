"""Purged walk-forward meta-labeling test for incumbent A-share factors.

Primary signal selects the highest decile. A logistic meta-model, trained only
on labels whose forward window has fully expired before the next test block,
estimates whether a candidate beats that date's factor-valid benchmark. The
meta score gates the primary basket; no platform call is made.
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/literature/advances-fml-meta-label-20261016'
SEAT=ROOT/'research_reports/platform_alignment/ab-batch-20260929/seat_panels_rebuilt.pkl'
SEATS=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']
CANDIDATES={'T10_ADD_BM':('t10_size_plus_impact_bm',2),'H03_T10':('impact60',1),'INCUMBENT_COMPOSITE':('composite',None)}
COST=.003; PAPER_COST=.0005; TRAIN=36; PURGE=1; TEST=12; SEED=20261016

def load():
 x=pickle.loads(SEAT.read_bytes()); sf=x['signal_frame'][['date','instrument']].copy(); sf['date']=pd.to_datetime(sf['date']); dates=pd.DatetimeIndex(x['dates']); stocks=pd.Index(sorted(sf.instrument.unique())); score=x['scores']; panels={}
 for k in SEATS: panels[k]=sf.assign(v=score[k].to_numpy()).pivot(index='date',columns='instrument',values='v').reindex(index=dates,columns=stocks).to_numpy(float)
 ret=x['returns'].copy(); ret['date']=pd.to_datetime(ret.date); y=ret.pivot(index='date',columns='instrument',values='forward_return').reindex(index=dates,columns=stocks).to_numpy(float)
 return dates,stocks,panels,y

def cs_z(a):
 out=np.full_like(a,np.nan,float)
 for i,row in enumerate(a):
  ok=np.isfinite(row); s=np.nanstd(row)
  if ok.sum()>100 and s>1e-12: out[i,ok]=(row[ok]-np.nanmean(row))/s
 return out

def make_features(z):
 # current cross-sectional exposures plus lagged changes, all observable at
 # the signal date; no future returns enter the feature matrix.
 d=np.diff(z,axis=0,prepend=np.full((1,z.shape[1],z.shape[2]),np.nan))
 return np.concatenate([z,d],axis=2)

def primary(z,name,idx):
 if name=='composite': return np.nanmean(z,axis=2)
 return z[:,:,idx]

def train_meta(X,y,primary_score,train_idx):
 xs=[]; ys=[]
 for i in train_idx:
  mask=np.isfinite(X[i]).all(1)&np.isfinite(y[i]); ids=np.flatnonzero(mask)
  if len(ids)<200: continue
  bench=np.mean(y[i,ids]); p=primary_score[i,ids]; n=max(int(len(ids)*.2),1); cand=ids[np.argsort(-p)[:n]]
  xs.append(X[i,cand]); ys.append((y[i,cand]>bench).astype(int))
 if not xs: return None
 xx=np.vstack(xs); yy=np.concatenate(ys)
 if np.unique(yy).size<2: return None
 model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=300,class_weight='balanced',random_state=SEED))
 model.fit(xx,yy); return model

def choose(score,prob,yrow,prev):
 mask=np.isfinite(score)&np.isfinite(prob)&np.isfinite(yrow); ids=np.flatnonzero(mask)
 n=max(int(len(ids)*.1),1); primary_ids=ids[np.argsort(-score[ids])[:n]]
 # Meta-label gate: retain names with p>=0.5, but keep persistent names that
 # remain in the primary basket. This avoids an all-cash collapse while
 # allowing the classifier to suppress marginal new entrants.
 keep=set(primary_ids[prob[primary_ids]>=.5].tolist())
 keep |= (set(primary_ids)&set(prev))
 if not keep: keep={int(primary_ids[0])}
 return keep

def eval_path(score,y,meta_prob=None,idx=None):
 prev=set(); rows=[]
 for i in idx:
  mask=np.isfinite(score[i])&np.isfinite(y[i]); ids=np.flatnonzero(mask); n=max(int(len(ids)*.1),1); primary_ids=ids[np.argsort(-score[i,ids])[:n]]
  selected=set(primary_ids.tolist()) if meta_prob is None else choose(score[i],meta_prob[i],y[i],prev)
  turn=0. if not prev else 1-len(selected&prev)/len(selected)
  held=np.mean(y[i,list(selected)]); bench=np.mean(y[i,ids]); gross=held-bench; net=gross-COST*turn
  rows.append({'index':int(i),'held':held,'benchmark':bench,'gross':gross,'net':net,'turnover':turn,'n_hold':len(selected)})
  prev=selected
 return pd.DataFrame(rows)

def metrics(d):
 r=d.net.to_numpy(float);g=d.gross.to_numpy(float);t=d.turnover.to_numpy(float);years=len(d)*10/252; nav=np.cumprod(1+r); held=np.prod(1+d.held.to_numpy(float))**(1/years)-1;bench=np.prod(1+d.benchmark.to_numpy(float))**(1/years)-1; gross=held-bench; tm=t.mean();
 return dict(periods=len(d),sharpe_net=np.sqrt(25.2)*r.mean()/r.std(ddof=1),net_annual_pct=(gross-tm*(252/10)*COST)*100,gross_annual_pct=gross*100,turnover_pct=tm*100,mean_holdings=float(d.n_hold.mean()),maxdd_pct=float(-np.min(nav/np.maximum.accumulate(nav)-1)),paper_cost_net_annual_pct=(gross-tm*(252/10)*PAPER_COST)*100)

def main():
 OUT.mkdir(parents=True,exist_ok=True); dates,stocks,panels,y=load(); z=np.stack([cs_z(panels[k]) for k in SEATS],2); X=make_features(z); rows=[]; blocklog=[]
 for cname,(kind,j) in CANDIDATES.items():
  s=primary(z,kind,j); full=eval_path(s,y,None,np.arange(len(dates))); m=metrics(full); m.update(candidate=cname,variant='primary_full120'); rows.append(m)
  base_parts=[]; meta_parts=[]
  for ts in range(TRAIN+PURGE,len(dates)-TEST+1,TEST):
   train_idx=np.arange(max(0,ts-PURGE-TRAIN),ts-PURGE); test_idx=np.arange(ts,ts+TEST); model=train_meta(X,y,s,train_idx); prob=np.full((len(dates),len(stocks)),np.nan)
   if model is not None:
    for i in test_idx:
     ok=np.isfinite(X[i]).all(1); ids=np.flatnonzero(ok); prob[i,ids]=model.predict_proba(X[i,ids])[:,1]
   base=eval_path(s,y,None,test_idx); meta=eval_path(s,y,prob,test_idx); base['block']=ts;meta['block']=ts;base_parts.append(base);meta_parts.append(meta)
   blocklog.append({'candidate':cname,'test_start':str(dates[ts]),'train_start':str(dates[train_idx[0]]),'train_end':str(dates[train_idx[-1]]),'purge_periods':PURGE,'meta_model':model is not None,'meta_positive_rate':float(np.nanmean(prob[test_idx])) if model is not None else None})
  base=pd.concat(base_parts,ignore_index=True);meta=pd.concat(meta_parts,ignore_index=True);base.to_csv(OUT/f'{cname}.primary_oos.csv',index=False);meta.to_csv(OUT/f'{cname}.meta_oos.csv',index=False)
  for variant,d in [('primary_oos',base),('meta_oos',meta)]: mm=metrics(d);mm.update(candidate=cname,variant=variant);rows.append(mm)
 pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False);pd.DataFrame(blocklog).to_csv(OUT/'block_log.csv',index=False);(OUT/'plan.json').write_text(json.dumps({'book':'Advances in Financial Machine Learning','method':'purged walk-forward + meta-label gate','candidates':list(CANDIDATES),'train_periods':TRAIN,'purge_periods':PURGE,'test_block_periods':TEST,'cost':COST,'paper_cost':PAPER_COST,'platform_compute_spent':0},ensure_ascii=False,indent=2)+'\n'); print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__': main()
