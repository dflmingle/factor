"""Paper-derived, predeclared conditional volume/momentum hypotheses.

Sources are summarized in the accompanying report. The run uses only cached
formal panels, purges labels crossing the final boundary, selects on an early
development block, freezes candidates, then evaluates the last block.
"""
from __future__ import annotations
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import gc, hashlib, json, threading, time
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata
from threadpoolctl import threadpool_limits
import fengmao_nested_causal_20261011 as shared

ROOT=shared.ROOT
SRC=ROOT/'research_reports/platform_alignment/fengmao-new-signals-20261011'
OUT=ROOT/'research_reports/platform_alignment/fengmao-paper-hypotheses-20261011'
FINAL_START=pd.Timestamp('2025-08-22')
# The shared module's helpers write through its module-level OUT. Redirect it
# to this experiment so protocol/search/freeze metadata cannot overwrite the
# neighboring causal-search report.
shared.OUT = OUT


def rank(a):
    n=np.isfinite(a).sum(axis=1,keepdims=True)
    return (rankdata(a,axis=1,method='average',nan_policy='omit')/np.maximum(n,1)-.5).astype(np.float32)


def grp(a,b,n,mode='rank'):
    ok=np.isfinite(a)&np.isfinite(b)
    rb=rank(np.where(ok,b,np.nan))
    bins=np.minimum(np.floor((rb+.5)*n),n-1).astype(int)
    out=np.full_like(a,np.nan,np.float32)
    for g in range(n):
        m=ok&(bins==g)
        z=np.where(m,a,np.nan)
        if mode=='rank': val=rank(z)
        else:
            mu=np.nanmean(z,axis=1,keepdims=True); sd=np.nanstd(z,axis=1,keepdims=True)
            val=(a-mu)/np.maximum(sd,1e-6)
        out[m]=val[m]
    return out


def mul(a,b): return (a*b).astype(np.float32)
def add(a,b): return (a+b).astype(np.float32)
def sub(a,b): return (a-b).astype(np.float32)


def build_candidates(a):
    # Economic hypotheses, all predeclared before evaluation.
    c=[]
    def addc(name,fn,source): c.append(dict(name=name,fn=fn,source=source))
    mom={'rev3':a['rev3'],'rev20':a['rev20'],'rev60':a['rev60']}
    vol={'vrel20':a['vrel20'],'lowturn':a['lowturn'],'onvol20':a['onvol20'],'onvol60':a['onvol60'],
         'idvol20':a['idvol20'],'idvol60':a['idvol60'],'downshare20':a['downshare20']}
    # Lee-Swaminathan / Gervais-Kaniel-Mingelgrin style conditional volume.
    for mn,m in mom.items():
        for vn,v in vol.items():
            for sign in (1,-1):
                addc(f'{sign:+d}*RANK({mn})*RANK({vn})',lambda m=m,v=v,sign=sign:sign*mul(rank(m),rank(v)),'momentum-volume interaction')
                addc(f'{sign:+d}*Grp5({mn},{vn})',lambda m=m,v=v,sign=sign:sign*grp(m,v,5,'rank'),'volume-conditioned momentum')
                addc(f'{sign:+d}*Grp5({mn},{vn})z',lambda m=m,v=v,sign=sign:sign*grp(m,v,5,'z'),'volume-conditioned momentum z')
    # Day/night decomposition and turnover shocks.
    for n in (20,60):
        for x in (f'idrev{n}',f'onrev{n}',f'tug{n}',f'signedflow{n}',f'asym{n}'):
            for v in (f'idvol{n}',f'onvol{n}',f'downshare{n}',f'vrel20'):
                for sign in (1,-1):
                    addc(f'{sign:+d}*Grp5({x},{v})',lambda x=x,v=v,sign=sign:sign*grp(a[x],a[v],5,'rank'),'day-night/volume condition')
        addc(f'Grp5(tug{n},onvol{n})',lambda n=n:grp(a[f'tug{n}'],a[f'onvol{n}'],5,'rank'),'day-night asymmetry')
        addc(f'Grp5(idrev{n},idvol{n})',lambda n=n:grp(a[f'idrev{n}'],a[f'idvol{n}'],5,'rank'),'intraday reversal/volume')
    # Abnormal turnover / dispersion proxies.
    for x in ('rev20','rev60','asym20','downrisk20','signedflow20'):
        for v in ('vrel20','rvcor20','gapcor20','downshare20'):
            addc(f'Grp5({x},{v})',lambda x=x,v=v:grp(a[x],a[v],5,'rank'),'turnover/dispersion condition')
    # MACD is included only as a state gate, never as the sole factor.
    for m in ('macdhist','macdslowhist','macd','macdslow'):
        for x in ('rev20','onrev20','idrev20','tug20'):
            addc(f'Grp5({x},{m})',lambda x=x,m=m:grp(a[x],a[m],5,'rank'),'trend-state gate')
    return c


def evaluate(signal,y,cap,dates):
    return shared.metrics(signal,y,cap,dates)[0]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen_candidates.json').exists(): raise RuntimeError('Refuse post-freeze retuning')
    threading.Thread(target=shared.watchdog,daemon=True).start()
    with threadpool_limits(limits=1):
        atoms,y,cap,dates,axes=shared.prior.load('formal')
        # Replace base atoms with saved new-signal panel; preserve target/labels.
        with np.load(SRC/'atoms.npz') as z:
            atoms={k:z[k] for k in z.files if k not in ('target','market_cap')}
        # Formal template dates and labels are aligned with this panel.
        assert len(dates)==len(y)==120 and len(atoms['rev3'])==120
        cache=ROOT/'quantlab/.quantlab/cache/research/cn_equity'
        calfiles=list((cache/'trade_calendar').glob('*.parquet'))
        cf=pd.concat([pd.read_parquet(p,columns=['trade_date','is_open']) for p in calfiles],ignore_index=True)
        cd=pd.to_datetime(cf.trade_date.astype(str),format='mixed').dt.normalize()
        cal=pd.DatetimeIndex(sorted(cd[cf.is_open.eq(1)].unique()))
        pos=cal.get_indexer(dates); exits=cal[pos+11]
        core=(dates<pd.Timestamp('2024-01-01'))&(exits<pd.Timestamp('2024-01-01'))
        dev=(dates>=pd.Timestamp('2024-01-01'))&(dates<FINAL_START)&(exits<FINAL_START)
        refit=(dates<FINAL_START)&(exits<FINAL_START)
        final=dates>=FINAL_START
        # Save protocol before any candidate evaluation.
        cands=build_candidates(atoms)
        shared.write('protocol.json',dict(sources=[
            {'title':'Price Momentum and Trading Volume','doi':'10.1111/0022-1082.00280','year':2000},
            {'title':'The High-Volume Return Premium','doi':'10.1111/0022-1082.00349','year':2001},
            {'title':'Momentum and Reversals in Equity-Index Returns During Periods of Abnormal Turnover and Return Dispersion','doi':'10.1111/1540-6261.00576','year':2003},
            {'title':'What Drives Momentum and Reversal? Evidence from Day and Night Signals','doi':'10.1093/rfs/hhag036','year':2026}],
            candidate_count=len(cands),core_dates=dates[core].astype(str).tolist(),development_dates=dates[dev].astype(str).tolist(),
            refit_dates=dates[refit].astype(str).tolist(),final_dates=dates[final].astype(str).tolist(),
            purged_label_dates=dates[(dates<FINAL_START)&(exits>=FINAL_START)].astype(str).tolist(),
            final_used_for_selection=False,platform_cost=0,formal_template=True))
        ev=[]
        for i,item in enumerate(cands):
            try:
                sig=item['fn'](); sig[~np.isfinite(cap)]=np.nan
                allm=evaluate(sig[core|dev],y[core|dev],cap[core|dev],dates[core|dev])
                dm=evaluate(sig[dev],y[dev],cap[dev],dates[dev])
                loss=.5*shared.objective(allm)+shared.objective(dm)+2*max(-dm['net_excess'],0)
                ev.append(dict(name=item['name'],source=item['source'],selection_loss=loss,early=allm,development=dm))
            except Exception as exc:
                ev.append(dict(name=item['name'],source=item['source'],selection_loss=1e9,error=str(exc)))
            if (i+1)%100==0:
                shared.write('search_results.json',ev); shared.log(f'paper hypotheses {i+1}/{len(cands)}')
            shared.guard()
        shared.write('search_results.json',ev)
        # Freeze one best candidate per hypothesis family to avoid one-family overfit.
        groups={}
        for r in ev:
            key=next((x for x in ('momentum-volume interaction','volume-conditioned momentum','day-night/volume condition','turnover/dispersion condition','trend-state gate') if x==r['source']),'other')
            groups.setdefault(key,[]).append(r)
        frozen=[]
        for key,rows in groups.items():
            best=min(rows,key=lambda x:x['selection_loss'])
            frozen.append(dict(name='FM_PAPER_'+key.upper().replace('/','_').replace(' ','_'),source=key,formula=best['name'],selection=best))
        shared.write('frozen_candidates.json',dict(frozen_before_final_labels=True,candidates=frozen))
        rows=[]
        for item in frozen:
            original=next(x for x in cands if x['name']==item['formula'])
            sig=original['fn'](); sig[~np.isfinite(cap)]=np.nan
            for name,mask in [('refit',refit),('historical_final',final),('formal_5y',np.ones(len(dates),bool)),('recent_2026',dates>=pd.Timestamp('2026-01-01'))]:
                m,p,g=shared.metrics(sig[mask],y[mask],cap[mask],dates[mask])
                p.to_csv(OUT/f'{item["name"]}_{name}_periods.csv',index=False); g.to_csv(OUT/f'{item["name"]}_{name}_groups.csv',index=False)
                rows.append(dict(candidate=item['name'],window=name,**m))
            np.save(OUT/(item['name']+'_formal_signals.npy'),sig)
        pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)
    shared.STOP.set()
    shared.write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,rule=shared.ALIGNMENT_RULE_VERSION,
                 memory=shared.PEAK,seconds=time.monotonic()-shared.START,source_scope='paper-derived hypotheses on formal local template'))
    shared.log('paper hypothesis search complete; no exact recovery claim')


if __name__=='__main__': main()
