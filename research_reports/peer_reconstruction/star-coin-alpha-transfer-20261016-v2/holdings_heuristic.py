"""Retrospective holdings-inversion heuristic for star_coin_prediction."""
from pathlib import Path
import json, itertools, sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

OUT=Path(__file__).resolve().parent
HERE=OUT.parents[0]/'top50-20261013/search_v1'
sys.path.insert(0,str(HERE))
from grammar import Expr, field, const, op, paths, replace, validate, formula
from engine import Market
from evidence import read, extract, PUBLIC
import objective
import residual_refine

POOL='18067f13fb2f894e0a45b181'
SOURCE=OUT.parent/'star-coin-alpha-transfer-20261016-v1'/'best.json'
if not SOURCE.exists(): raise FileNotFoundError(SOURCE)

def add_unique(xs,x,reason):
    try: validate(x,10,100)
    except Exception: return
    if x not in xs: xs[x]=reason

def hand_variants(base,j):
    cap,cfp,sp,close,open_,vol,low=[field(x) for x in ['cap','cfp','sp','close','open','volume','low']]
    d={}
    if j==0:
        ncap=op('rank',op('neg',cap))
        cfps=[cfp,op('rank',cfp),op('zscore',cfp),op('ts_mean',cfp,window=20),op('rank',op('ts_mean',cfp,window=20)),op('neg',cfp)]
        prices=[op('rank',op('neg',close)),ncap,op('zscore',op('neg',cap))]
        for p in prices:
            for q in cfps:
                add_unique(d,op('neg',op('add',p,q)),'M03 holdings inverse: cap/CFP shape')
                add_unique(d,op('neg',op('mean2',p,q)),'M03 holdings inverse: cap/CFP mean')
        add_unique(d,op('neg',op('add',op('zscore',op('neg',cap)),op('zscore',cfp))),'M03 zscore cap/CFP')
    elif j==8:
        for path,node in paths(base):
            if node.op not in ('ts_mean','ts_std','ts_skew','ts_kurt'): continue
            for n in sorted({max(1,node.value-4),max(1,node.value-2),max(1,node.value-1),node.value+1,node.value+2,node.value+4}):
                if 1<=n<=120: add_unique(d,replace(base,path,Expr(node.op,node.args,n)),'M02 window neighbourhood')
        for newop in ('ts_std','ts_mean','ts_skew','ts_kurt'):
            for n in (18,20,22,30,49):
                for path,node in paths(base):
                    if node.op=='ts_kurt' and 'sp' in node.fields:
                        add_unique(d,replace(base,path,Expr(newop,node.args,n)),'M02 SP dispersion operator')
        for n in (16,18,20,22,24,30):
            for path,node in paths(base):
                if node.op=='ts_mean' and node.value==20 and node.args and 'ep' in node.fields:
                    add_unique(d,replace(base,path,Expr(node.op,node.args,n)),'M02 EP smoothing window')
    elif j==1:
        ret=op('sub',op('div',close,op('delay',close,window=1)),const(1))
        intra=op('sub',op('div',close,open_),const(-1))
        for n in range(18,25):
            add_unique(d,op('rank',op('ts_std',intra,window=n)),'V01 volatility window')
            add_unique(d,op('rank',op('ts_std',ret,window=n)),'V01 close-return window')
            add_unique(d,op('rank',op('ts_std',op('logabs',op('div',close,op('delay',close,window=1))),window=n)),'V01 log-return window')
    elif j==2:
        inner=op('neg',op('add',op('rank',op('neg',op('sma',vol,window=1))),op('rank',op('neg',low))))
        for n in (2,3,4,5,6): add_unique(d,op('ema',op('zscore',inner),window=n),'M04 EMA window')
        for norm in (op('zscore',inner),op('rank',inner),inner): add_unique(d,op('ema',norm,window=3),'M04 normalization order')
        for left,right in [(vol,low),(low,vol)]:
            x=op('neg',op('add',op('rank',op('neg',op('sma',left,window=1))),op('rank',op('neg',right))))
            add_unique(d,op('ema',op('zscore',x),window=3),'M04 input order')
    elif j==7:
        for n in (5,6,8,9,10,11,12,15,20):
            add_unique(d,op('div',close,op('ts_mean',open_,window=n)),'X01 open mean window')
            add_unique(d,op('neg',op('div',close,op('ts_mean',open_,window=n))),'X01 direction shape')
    return d

def holdings_inverse_score(e,pool,expr,j):
    cand=e.leg(expr,j)['z']; others=[e.leg(pool[k],k)['z'] for k in range(e.seat_count)]
    xs=[];ys=[];weights=[]
    for r in e.records:
        i=e.index[pd.Timestamp(r['signal'])]; active=np.flatnonzero(e.active[:,i])
        if j not in active: continue
        for row in r['rows']:
            if row.get('composite') is None or row['symbol'] not in e.stocks: continue
            s=e.stocks.get_loc(row['symbol'])
            if not np.isfinite(cand[i,s]): continue
            total=0.;good=True
            for k in active:
                if k==j: continue
                v=others[k][i,s]
                if not np.isfinite(v): good=False; break
                total+=v
            if not good: continue
            xs.append(float(cand[i,s]));ys.append(len(active)*float(row['composite'])-total)
            rank=int(row.get('rank',500));weights.append(3.0 if rank<=20 else 2.0 if rank<=100 else 1.0)
    if len(xs)<20:return {'n':len(xs),'score':-1e9,'rankcorr':None,'rmse':None,'top20_rmse':None}
    x=np.asarray(xs);y=np.asarray(ys);w=np.asarray(weights); mask=np.asarray(weights)>=3
    rc=float(spearmanr(x,y).statistic) if np.std(x)>0 and np.std(y)>0 else -1.
    rmse=float(np.sqrt(np.average((x-y)**2,weights=w))); top=float(np.sqrt(np.mean((x[mask]-y[mask])**2))) if mask.any() else rmse
    return {'n':len(xs),'score':2*rc-.35*rmse-.15*top,'rankcorr':rc,'rmse':rmse,'top20_rmse':top}

def main():
    seed=json.load(open(SOURCE));base=tuple(Expr.from_json(x) for x in seed['pool'])
    market=Market();market.cache_dir=OUT/'panels';market.cache_dir.mkdir(exist_ok=True)
    target=[x for x in read(PUBLIC/'targets.json') if x['rank']==8][0]
    evidence=extract(target,market);objective.HERE=OUT
    e=objective.Objective(market,evidence,OUT/'baseline',base);e.enable_A()
    worst=[8,0,1,2,7];shortlist={};short_rows=[]
    for j in worst:
        variants={}
        for x,reason in residual_refine.variants(base[j],e.seats[j]):add_unique(variants,x,reason)
        for x,reason in hand_variants(base[j],j).items():add_unique(variants,x,reason)
        scored=[]
        for x,reason in variants.items():scored.append((holdings_inverse_score(e,base,x,j)['score'],x,reason,holdings_inverse_score(e,base,x,j)))
        scored.sort(key=lambda z:z[0],reverse=True);keep=scored[:4];shortlist[j]=keep
        for _,x,reason,inv in keep:short_rows.append({'seat':j,'formula':formula(x),'reason':reason,'inverse':inv})
    (OUT/'holdings_shortlist.json').write_text(json.dumps(short_rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    results=[]
    for j,items in shortlist.items():
        for _,x,reason,inv in items:
            pool=list(base);pool[j]=x;row=e.evaluate(tuple(pool),True)
            if row.get('valid'):results.append({'seat':j,'formula':formula(x),'reason':reason,'inverse':inv,'score':row['score'],'row':row})
    pair_rows=[];top2={j:items[:2] for j,items in shortlist.items()}
    for j,k in itertools.combinations(sorted(top2),2):
        for _,x,rx,ix in top2[j]:
            for _,y,ry,iy in top2[k]:
                pool=list(base);pool[j]=x;pool[k]=y;row=e.evaluate(tuple(pool),True)
                if row.get('valid'):pair_rows.append({'seats':[j,k],'formulas':[formula(x),formula(y)],'reasons':[rx,ry],'inverse':[ix,iy],'score':row['score'],'row':row})
    allrows=[{'kind':'one','item':r} for r in results]+[{'kind':'pair','item':r} for r in pair_rows]
    best=max(allrows,key=lambda z:z['item']['score']) if allrows else None
    summary={'baseline':e.evaluate(base,True),'best_kind':best['kind'] if best else None,'best':best['item'] if best else None,'one_count':len(results),'pair_count':len(pair_rows),'platform_compute':0,'retrospective_inverse_only':True}
    (OUT/'heuristic_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'best_kind':summary['best_kind'],'best_score':best['item']['score'] if best else None,'one_count':len(results),'pair_count':len(pair_rows)},ensure_ascii=False))
if __name__=='__main__':main()
