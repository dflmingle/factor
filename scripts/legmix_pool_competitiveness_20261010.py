"""Offline cached-panel diagnosis; never claims current formal reproduction or live rank."""
from pathlib import Path
import json,pickle
import numpy as np
import pandas as pd
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, ALIGNMENT_ROUND_TRIP_COST
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/legmix-competitiveness-20261010'
SEATS=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']

def corr(a,b):
    vals=[]
    for d in a.index:
        x=a.loc[d];y=b.loc[d];ok=x.notna()&y.notna()
        if ok.sum()>=100 and x[ok].nunique()>1 and y[ok].nunique()>1:
            vals.append(x[ok].corr(y[ok],method='spearman'))
    return float(np.nanmean(vals))

def standardize(v):
    lo=v.quantile(.01,axis=1);hi=v.quantile(.99,axis=1)
    c=v.clip(lo,hi,axis=0)
    return c.sub(c.mean(axis=1),axis=0).div(c.std(axis=1,ddof=0).replace(0,np.nan),axis=0)

def evaluate(score,close,start):
    prev=set();records=[];daily=[];heldr=[];benchr=[]
    for date in score.index[score.index>=pd.Timestamp(start)]:
        pos=close.index.get_loc(date)+1
        if pos+10>=len(close): continue
        path=close.iloc[pos:pos+11];anchor=path.iloc[0];future=path.iloc[-1]/anchor-1
        valid=score.loc[date].notna()&future.notna()&(anchor>0)
        if valid.sum()<100:continue
        ids=score.columns[valid];n=len(ids);nheld=n-(n*9//10)
        selected=score.loc[date,ids].sort_values(ascending=False,kind='stable').index[:nheld]
        current=set(selected);turn=.5 if not prev else 1-len(current&prev)/len(current);prev=current
        pv=path[selected].div(anchor[selected],axis=1).mean(axis=1)
        bv=path[ids].div(anchor[ids],axis=1).mean(axis=1)
        pr=pv.pct_change(fill_method=None).iloc[1:].astype('float64');br=bv.pct_change(fill_method=None).iloc[1:].astype('float64')
        pr.iloc[0]-=turn*ALIGNMENT_ROUND_TRIP_COST
        daily.append(pd.DataFrame({'portfolio':pr,'benchmark':br}))
        heldr.append(float(future[selected].mean()));benchr.append(float(future[ids].mean()))
        records.append({'date':date,'turn':turn})
    daily=pd.concat(daily).sort_index();assert daily.index.is_unique
    ledger=pd.DataFrame(records);monthly=[]
    for (y,m),b in daily.groupby([daily.index.year,daily.index.month]):
        p=b.portfolio.to_numpy();q=b.benchmark.to_numpy();n=len(p)
        if n<2:continue
        rex=np.prod(1+p)**(252/n)-np.prod(1+q)**(252/n)
        sr=p.mean()/p.std(ddof=1)*np.sqrt(252)
        eq=np.r_[1.,np.cumprod(1+p)];dd=1-np.min(eq/np.maximum.accumulate(eq))
        t=ledger.loc[(ledger.date.dt.year==y)&(ledger.date.dt.month==m),'turn'].sum()
        raw=max(rex,0)*sr*(1-1.2*dd)/max(t,.3)
        monthly.append(dict(year=y,month=m,days=n,rex=rex,sr=sr,dd=dd,turn=t,raw_c=raw,nc=np.clip(raw/.6,0,1)))
    n=len(records);turn=ledger.turn.iloc[1:].mean()
    gross=np.prod(1+np.array(heldr))**(252/(10*n))-np.prod(1+np.array(benchr))**(252/(10*n))
    return pd.DataFrame(monthly),dict(periods=n,turn=turn,net=gross-turn*25.2*.006,first=str(daily.index.min().date()),last=str(daily.index.max().date()))

def neutral_net(score,size,close,start):
    h=[];b=[];turn=[];prev=set()
    for d in score.index[score.index>=pd.Timestamp(start)]:
        pos=close.index.get_loc(d)+1
        if pos+10>=len(close):continue
        ret=close.iloc[pos+10]/close.iloc[pos]-1
        x=score.loc[d];s=size.loc[d];ok=x.notna()&s.notna()&ret.notna()
        if ok.sum()<200:continue
        buckets=pd.qcut(s[ok].rank(method='first'),20,labels=False)
        resid=x[ok]-x[ok].groupby(buckets).transform('mean')
        ids=resid.sort_values(ascending=False,kind='stable').index[:len(resid)//10]
        sel=set(ids)
        if prev:turn.append(1-len(sel&prev)/len(sel))
        prev=sel;h.append(ret[ids].mean());b.append(ret[ok].mean())
    return float((np.prod(1+np.array(h))**(252/(10*len(h)))-np.prod(1+np.array(b))**(252/(10*len(b))))-np.mean(turn)*25.2*.006)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    payload=pickle.load((ROOT/'research_reports/platform_alignment/ab-batch-20260929/seat_panels_rebuilt.pkl').open('rb'))
    panels=pickle.load((ROOT/'research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl').open('rb'))
    dates=pd.DatetimeIndex(payload['dates']);sf=payload['signal_frame'];scores={}
    for k in SEATS:
        f=sf.copy();f['v']=payload['scores'][k].to_numpy();scores[k]=f.pivot(index='date',columns='instrument',values='v').reindex(index=dates)
    stocks=scores[SEATS[0]].columns
    a=panels['amount'];t=panels['turn'];c=panels['close'];o=panels['open']
    raw={'A':((-a.rolling(60).mean()).rank(axis=1,pct=True)+(-((c-o)/o).rolling(20).mean()).rank(axis=1,pct=True)+(-t.rolling(20).std()).rank(axis=1,pct=True))/3,
         'B':((-t.rolling(5).mean()).rank(axis=1,pct=True)+(-a.rolling(60).mean()).rank(axis=1,pct=True))/2}
    close=c.reindex(columns=stocks).ffill();size=panels['mcap'].reindex(index=dates,columns=stocks)
    for k,v in raw.items():scores[k]=standardize(v.reindex(index=dates,columns=stocks))
    scenarios={'CTRL':SEATS}
    # Both additions and all single-seat replacements, rather than assuming the weakest A seat is best to remove.
    for k in ['A','B']:
        scenarios['ADD_'+k]=SEATS+[k]
        for s in SEATS:scenarios['SWAP_'+k+'_'+s]=[z for z in SEATS if z!=s]+[k]
    near=[]
    for k in ['A','B']:
        for s in SEATS:near.append(dict(candidate=k,seat=s,rho=corr(scores[k],scores[s])))
    pd.DataFrame(near).to_csv(OUT/'seat_correlations.csv',index=False)
    rows=[]
    for window,start in [('archived_5y','20210907'),('recent','20260101')]:
        base=None;base_score=None;base_guard=None
        for name,keys in scenarios.items():
            # Preserve required-valid rows, never pandas skip-NaN averaging.
            score=sum(scores[k] for k in keys)/len(keys)
            mt,stats=evaluate(score,close,start)
            rho=corr(score.loc[score.index>=pd.Timestamp(start)],size.loc[size.index>=pd.Timestamp(start)])
            neu=neutral_net(score,size,close,start)
            if name=='CTRL':base=mt;base_score=score;base_guard=(rho,neu)
            pair=base.merge(mt,on=['year','month'],suffixes=('_base','_new'))
            sat=pair.nc_base>=1-1e-9;keep=pair.nc_new>=1-1e-9
            dc=(pair.nc_new-pair.nc_base)*19800
            pair['delta_c_points']=dc;pair.to_csv(OUT/f'monthly_{window}_{name}.csv',index=False)
            rows.append(dict(window=window,scenario=name,**stats,corr_mcap=rho,size_neutral_net=neu,delta_abs_corr=abs(rho)-abs(base_guard[0]),delta_neutral=neu-base_guard[1],size_guard=abs(rho)<=abs(base_guard[0])+1e-9 and neu>=base_guard[1]-1e-9,months=len(pair),base_sat=int(sat.sum()),kept_sat=int((sat&keep).sum()),lost_sat=int((sat&~keep).sum()),kept_sat_ratio=float((sat&keep).sum()/sat.sum()) if sat.any() else None,delta_c_mean=float(dc.mean()),delta_c_worst=float(dc.min()),new_sat=int(keep.sum())))
            print(window,name,'net',round(stats['net'],4),'dC',round(dc.mean()),'guard',rows[-1]['size_guard'],flush=True)
    pd.DataFrame(rows).to_csv(OUT/'pool_diagnostics.csv',index=False)
    # Use the public monthly pool snapshot for a competitor stress envelope, not a forecast.
    board=json.loads((ROOT/'research_reports/platform_alignment/board-snapshot-20261009c/board_live.json').read_text())
    br=[]
    for r in board['rows']:
        m=r['metrics']
        if not isinstance(m.get('raw_a'),(int,float)): continue
        br.append(dict(name=r['display_name'],rank=r['rank'],raw_a=m['raw_a'],nb=m['nb'],nc=m['nc'],actual_score=r['score'],saturated_BC_score=min(40000.,44000*(.2*min(m['raw_a']/.08,.7)+.35+.45))))
    pd.DataFrame(br).sort_values('saturated_BC_score',ascending=False).to_csv(OUT/'competitor_saturation_scenario.csv',index=False)
    (OUT/'metadata.json').write_text(json.dumps(dict(method_version='cached-factor-valid-nav1-diagnostic-v1',alignment_reference=ALIGNMENT_RULE_VERSION,status='archived_cache_diagnostic_proxy_not_formal_reproduction',source_provenance=payload['provenance'],cache_end=str(c.index.max().date()),last_signal=str(dates.max().date()),recent_status='through_archived_cache_not_latest_local_date',benchmark='scenario_factor_valid',cost=.006,dd_includes_initial_nav=True,B='unobserved_future_outcome_not_imputed',A='not_assumed_equal_to_platform_chart_proxy'),indent=2,ensure_ascii=False))
if __name__=='__main__':main()
