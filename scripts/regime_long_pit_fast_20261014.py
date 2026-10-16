"""Compiled chronological-quarter replay, checked against the reference reader."""
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
import regime_long_history_data_20261014 as data

@njit(cache=True)
def replay(ann,quarters,values,dates,lags,ttm):
    ncols=values.shape[1];lo=quarters.min();hi=quarters.max()
    known=np.zeros(hi-lo+1,np.bool_);reports=np.full((hi-lo+1,ncols),np.nan)
    out=np.full((len(dates),lags,ncols,2 if ttm else 1),np.nan,np.float32)
    at=0;current=-1
    for i in range(len(dates)):
        while at<len(ann) and ann[at]<=dates[i]:
            end=quarters[at]-lo;known[end]=True;reports[end]=values[at];current=max(current,end);at+=1
        if current<0:continue
        for lag in range(lags):
            end=current-lag
            if end<0:continue
            if known[end]:out[i,lag,:,0]=reports[end]
            if not ttm:continue
            total=np.zeros(ncols);valid=True
            for off in range(4):
                qe=end-off
                if qe<0 or not known[qe]:valid=False;break
                if (qe+lo)%4==0:total+=reports[qe]
                elif qe>0 and known[qe-1]:total+=reports[qe]-reports[qe-1]
                else:valid=False;break
            if valid:out[i,lag,:,1]=total
    return out

def snapshot(dates,stocks,lags=6,table_path=None):
    path=q.OUT/('financial_signal_snapshots.pkl' if lags==6 else f'financial_signal_snapshots_lags{lags}.pkl')
    if path.exists():return pd.read_pickle(path)
    tables=pd.read_pickle(table_path or data.OUT/'financial_pit_tables_long.pkl');result={};checks=[]
    for endpoint,table in tables.items():
        if endpoint not in q.FIN_FIELDS:continue
        wanted=[c for c in q.FIN_FIELDS[endpoint] if c in table];ttm=endpoint in ['income','cashflow']
        names=wanted+([c+'_ttm' for c in wanted] if ttm else [])
        for lag in range(lags):
            for col in names:result[f'{endpoint}.{col}.q{lag}']=np.full((len(dates),len(stocks)),np.nan,np.float32)
        for count,(symbol,g) in enumerate(table.groupby('instrument',sort=False)):
            j=stocks.get_indexer([symbol])[0]
            if j<0:continue
            g=g.sort_values(['ann_date','end_date','update_flag'])
            quarters=pd.PeriodIndex(g.end_date,freq='Q-DEC').asi8
            ann=pd.DatetimeIndex(g.ann_date).asi8;vals=g[wanted].to_numpy(float)
            arr=replay(ann,quarters,vals,pd.DatetimeIndex(dates).asi8,lags,ttm)
            for lag in range(lags):
                for k,col in enumerate(wanted):
                    result[f'{endpoint}.{col}.q{lag}'][:,j]=arr[:,lag,k,0]
                    if ttm:result[f'{endpoint}.{col}_ttm.q{lag}'][:,j]=arr[:,lag,k,1]
            # Independent literal Python replay on several real histories,
            # including old reports and restatements. Match NaN propagation.
            if sum(c['endpoint']==endpoint for c in checks)<3 and len(g)>30:
                reports={};at=0;ends=pd.PeriodIndex(g.end_date,freq='Q-DEC');reference=np.full(arr.shape,np.nan,np.float32)
                for i,date in enumerate(dates):
                    while at<len(g) and ann[at]<=date.value:reports[ends[at]]=vals[at];at+=1
                    if not reports:continue
                    current=max(reports)
                    for lag in range(lags):
                        end=current-lag
                        if end in reports:reference[i,lag,:,0]=reports[end]
                        if not ttm:continue
                        qs=[]
                        for off in range(4):
                            qe=end-off
                            if qe not in reports:break
                            if qe.quarter==1:qs.append(reports[qe])
                            elif qe-1 in reports:qs.append(reports[qe]-reports[qe-1])
                            else:break
                        if len(qs)==4:reference[i,lag,:,1]=np.sum(qs,axis=0)
                np.testing.assert_allclose(reference,arr,equal_nan=True,rtol=1e-6,atol=1e-4)
                # Truncate announcements and requested dates simultaneously.
                cutoff=len(dates)//2;keep=ann<=dates[cutoff-1].value
                if keep.any():
                    cut=replay(ann[keep],quarters[keep],vals[keep],pd.DatetimeIndex(dates[:cutoff]).asi8,lags,ttm)
                    np.testing.assert_allclose(cut,arr[:cutoff],equal_nan=True,rtol=1e-6,atol=1e-4)
                else:assert np.isnan(arr[:cutoff]).all()
                checks.append(dict(endpoint=endpoint,symbol=symbol,reference_and_prefix=True))
        print('FAST_PIT_COMPLETE',endpoint,flush=True)
    pd.to_pickle(result,path);q.dump(q.OUT/'pit_numerical_verification.json',dict(completed=True,checks=checks,method='same announcement max, quarter ordering, contiguous TTM; compiled numerical loop only'))
    return result
