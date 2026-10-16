"""Local pool-level test of attribution-guided feature exposure intervention.

This adapts the economic-explanation idea to saved A-share factor sleeves. It
does not submit a platform factor: the five incumbent sleeves (and three
locally reproduced weak sleeves) are treated as model features, and a causal
walk-forward FFN uses prior validation net-Sharpe ablations to update feature
exposures. Results are long-only top-decile factor-valid excess returns with
the project's 30bp cost and the paper's 5bp sensitivity.
"""
from __future__ import annotations
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(k,'1')
import json, math, pickle
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/literature/economic-explanation-ml-portfolios-20261016/pool_intervention'
SEAT=ROOT/'research_reports/platform_alignment/ab-batch-20260929/seat_panels_rebuilt.pkl'
ACCOUNT=ROOT/'research_reports/platform_alignment/quant-corpus-accounting-completion-20261014/signal_panels.pkl'
FNET=ROOT/'research_reports/platform_alignment/seat-rescreen-20260924/fnet01_panels.pkl'
NL02=ROOT/'research_reports/platform_alignment/nonlinear-walkforward-20261012/NL02_signal.npy'
ETA=.5; COST=.003; PAPER_COST=.0005; N_TRAIN=24; N_VALID=12; BLOCK=12; SEED=20261016
SEATS=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']
CANDIDATES={
 'P1_all_five':SEATS,
 'P2_fixed_size':SEATS,
 'P3_weak_sleeves':SEATS+['coherent_seasonal_revenue_sue3','fnet01_qfq','nl02'],
}

def cross_zscore(a):
    out=np.full_like(a,np.nan,dtype=np.float32)
    for t in range(a.shape[0]):
        row=a[t]; ok=np.isfinite(row)
        if ok.sum()<100: continue
        m=np.nanmean(row); s=np.nanstd(row)
        if s>1e-12: out[t,ok]=(row[ok]-m)/s
    return out

def load_data():
    seat=pickle.loads(SEAT.read_bytes())
    sf=seat['signal_frame'][['date','instrument']].copy(); sf['date']=pd.to_datetime(sf['date'])
    dates=pd.DatetimeIndex(seat['dates']); stocks=pd.Index(sorted(sf.instrument.unique()))
    score=seat['scores'].copy(); score.index=sf.index
    panels={}
    # Explicitly pivot once to guard against any non-contiguous instrument ordering.
    # pivot once to guard against any non-contiguous instrument ordering.
    for k in SEATS:
        panels[k]=sf.assign(v=score[k].to_numpy()).pivot(index='date',columns='instrument',values='v').reindex(index=dates,columns=stocks).to_numpy(np.float32)
    ret=seat['returns'].copy(); ret['date']=pd.to_datetime(ret['date'])
    y=ret.pivot(index='date',columns='instrument',values='forward_return').reindex(index=dates,columns=stocks).to_numpy(np.float32)
    acc=pickle.loads(ACCOUNT.read_bytes()); astocks=pd.Index(acc['stocks'])
    for k,v in acc['panels'].items():
        if k=='coherent_seasonal_revenue_sue3':
            p=pd.DataFrame(v,index=acc['dates'],columns=astocks).reindex(index=dates,columns=stocks)
            panels[k]=p.to_numpy(np.float32)
    fnet=pickle.loads(FNET.read_bytes())['qfq']
    panels['fnet01_qfq']=sf.assign(v=fnet.to_numpy()).pivot(index='date',columns='instrument',values='v').reindex(index=dates,columns=stocks).to_numpy(np.float32)
    nl=np.load(NL02).astype(np.float32)
    nlp=pd.DataFrame(nl,index=dates,columns=astocks).reindex(index=dates,columns=stocks)
    panels['nl02']=nlp.to_numpy(np.float32)
    return dates,stocks,panels,y

class FFN(nn.Module):
    def __init__(self,p):
        super().__init__(); self.net=nn.Sequential(nn.Linear(p,32),nn.ReLU(),nn.Linear(32,16),nn.ReLU(),nn.Linear(16,1))
    def forward(self,x): return self.net(x).squeeze(-1)

def rows_for(idx,X,y):
    xs=[]; ys=[]
    for i in idx:
        ok=np.isfinite(X[i]).all(axis=1)&np.isfinite(y[i])
        if ok.sum()<200: continue
        xs.append(X[i,ok]); ys.append(y[i,ok])
    return (np.vstack(xs).astype(np.float32),np.concatenate(ys).astype(np.float32)) if xs else (np.empty((0,X.shape[2]),np.float32),np.empty(0,np.float32))

def train(X,y,idx):
    xx,yy=rows_for(idx,X,y)
    if len(yy)<10000: raise RuntimeError(f'too few training rows {len(yy)}')
    torch.manual_seed(SEED); model=FFN(X.shape[2]); opt=torch.optim.Adam(model.parameters(),lr=.002,weight_decay=1e-4)
    tx=torch.from_numpy(xx); ty=torch.from_numpy(yy); model.train(); batch=8192
    for _ in range(18):
        order=torch.randperm(len(ty))
        for st in range(0,len(ty),batch):
            ids=order[st:st+batch]; pred=model(tx[ids]); loss=((pred-ty[ids])**2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    return model

def predict(model,x):
    model.eval(); tx=torch.tensor(x,dtype=torch.float32,requires_grad=True); out=model(tx)
    g=torch.autograd.grad(out.sum(),tx)[0].detach().numpy(); return out.detach().numpy(),(g*x).astype(np.float32)

def select(pred,mask):
    ids=np.flatnonzero(mask); n=max(int(len(ids)*.1),1); order=ids[np.argsort(-pred[ids],kind='stable')[:n]]
    w=np.zeros(len(pred),np.float32); w[order]=1./len(order); return w, set(order.tolist())

def eval_block(model,X,y,idx,lam,prev=None):
    p=X.shape[2]; prev=set() if prev is None else prev; rows=[]; attrs=[]
    for i in idx:
        mask=np.isfinite(X[i]).all(axis=1)&np.isfinite(y[i]); xx=X[i]*lam[None,:]
        ids=np.flatnonzero(mask); pred0,attr0=predict(model,xx[ids]); pred=np.full(X.shape[1],np.nan); attr=np.zeros((X.shape[1],p),np.float32); pred[ids]=pred0; attr[ids]=attr0
        w,selected=select(pred,mask); turn=np.nan if not prev else 1-len(selected&prev)/len(selected)
        if not np.isfinite(turn): turn=1.0
        gross=float(np.mean(y[i,list(selected)])-np.mean(y[i,mask])); net=gross-COST*turn
        # Economically scaled local attribution proxy: feature contribution
        # on selected names relative to the factor-valid benchmark.
        phi=np.array([float(np.mean(attr[list(selected),j]*y[i,list(selected)])) for j in range(p)])
        rows.append({'index':int(i),'date':str(i),'gross':gross,'net':net,'turnover':turn}); attrs.append(phi); prev=selected
    return pd.DataFrame(rows),np.asarray(attrs),prev

def sr(r):
    r=np.asarray(r,float); return float(np.sqrt(25.2)*r.mean()/r.std(ddof=1)) if len(r)>1 and r.std(ddof=1)>0 else np.nan

def metrics(df):
    r=df.net.to_numpy(float);g=df.gross.to_numpy(float);t=df.turnover.to_numpy(float); nav=np.cumprod(1+r)
    return dict(periods=len(df),sharpe_net=sr(r),sharpe_gross=sr(g),mean_net_annual_pct=r.mean()*25.2*100,mean_gross_annual_pct=g.mean()*25.2*100,turnover_period_pct=t.mean()*100,drawdown_pct=float(-np.min(nav/np.maximum.accumulate(nav)-1)),paper_cost_sensitivity_net_annual_pct=(g-t*PAPER_COST).mean()*25.2*100)

def main():
    OUT.mkdir(parents=True,exist_ok=True); dates,stocks,raw,y=load_data(); all_results=[]; attrlog=[]; lambdalog=[]
    plan={'candidates':CANDIDATES,'dates':[str(dates[0]),str(dates[-1])],'train_periods':N_TRAIN,'validation_periods':N_VALID,'oos_block_periods':BLOCK,'eta':ETA,'cost':COST,'paper_cost':PAPER_COST,'no_platform_calls':True,'method':'FFN regression; gradient-times-input attribution proxy; validation attribution lagged one OOS block'}
    (OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    for cname,keys in CANDIDATES.items():
        X=np.stack([cross_zscore(raw[k]) for k in keys],axis=2); p=X.shape[2]; fixed=np.zeros(p,bool)
        if cname=='P2_fixed_size': fixed[0]=True
        variants={v:[] for v in ['baseline','unstabilised','stabilised']}; state=np.ones(p)
        for test_start in range(N_TRAIN+N_VALID,len(dates)-BLOCK+1,BLOCK):
            tr=np.arange(test_start-N_VALID-N_TRAIN,test_start-N_VALID); va=np.arange(test_start-N_VALID,test_start); te=np.arange(test_start,test_start+BLOCK)
            model=train(X,y,tr); vr,_,_=eval_block(model,X,y,va,np.ones(p)); base_sr=sr(vr.net.to_numpy())
            phi=np.full(p,np.nan)
            for j in range(p):
                if fixed[j]: continue
                lam=np.ones(p); lam[j]=0.; abr,_,_=eval_block(model,X,y,va,lam); phi[j]=base_sr-sr(abr.net.to_numpy())
            sd=np.nanstd(phi); step=np.ones(p) if not np.isfinite(sd) or sd<1e-12 else 1+ETA*np.tanh(np.where(np.isfinite(phi),phi/sd,0.))
            step[fixed]=1.; unst=np.clip(step,0,3); stab=np.clip(state*unst,0,3); stab[fixed]=1.
            for variant,lam in [('baseline',np.ones(p)),('unstabilised',unst),('stabilised',stab)]:
                rr,aa,_=eval_block(model,X,y,te,lam); rr['candidate']=cname;rr['variant']=variant;rr['block']=test_start;variants[variant].append(rr)
                if variant=='stabilised': state=stab.copy()
            attrlog.append({'candidate':cname,'test_start':str(dates[test_start]),**{keys[j]:float(phi[j]) if np.isfinite(phi[j]) else None for j in range(p)}})
            lambdalog.append({'candidate':cname,'test_start':str(dates[test_start]),**{f'lambda_{keys[j]}':float(unst[j]) for j in range(p)}})
        for variant,parts in variants.items():
            d=pd.concat(parts,ignore_index=True); d.to_csv(OUT/f'{cname}.{variant}.periods.csv',index=False); m=metrics(d); m.update(candidate=cname,variant=variant); all_results.append(m)
    result=pd.DataFrame(all_results).sort_values(['candidate','variant']); result.to_csv(OUT/'results.csv',index=False); pd.DataFrame(attrlog).to_csv(OUT/'validation_attributions.csv',index=False); pd.DataFrame(lambdalog).to_csv(OUT/'lambda_log.csv',index=False)
    (OUT/'verification.json').write_text(json.dumps({'completed':True,'platform_compute_spent':0,'causal':'train/validation/test disjoint; validation attribution lagged before test block','finite_results':bool(np.isfinite(result.select_dtypes('number')).all().all()),'features':'saved incumbent seat panels plus local seasonal revenue/F-NET01/NL02 panels'},ensure_ascii=False,indent=2)+'\n')
    print(result.to_string(index=False))

if __name__=='__main__': main()
