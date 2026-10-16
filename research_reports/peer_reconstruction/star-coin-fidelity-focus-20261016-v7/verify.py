"""Independent full-history formula/A replay and direct daily ledger check."""
import gc
import json
import numpy as np
import pandas as pd
import research
from research import OUT, ROOT, Expr, Interpreter, standardize, correlation, clean


def main():
    result=research.read(OUT/'accepted_result.json');expected=result['selected']
    r=research.Research('independent_objective');m,e=r.m,r.e
    rawdates=m.cal.get_indexer(e.signals);legs=[];checks=[];seat_a=[];signal_grid=[]
    for j,row in enumerate(result['selected_seats']):
        expr=Expr.from_json(row['tree']);fields=r.engines[row['proxy']].fields
        full=Interpreter(fields).evaluate(expr)
        cached=np.load(ROOT/row['source'],mmap_mode='r')[r.positions]
        raw=full[rawdates]
        assert np.array_equal(raw,cached,equal_nan=True),(j,'raw cache mismatch')
        cutoffs=[]
        if expr!=r.base[j] or row['proxy']!='baseline':
            for day in ['20260902','20260923']:
                n=m.cal.get_loc(pd.Timestamp(day))+1
                prefix=Interpreter({k:v[:n] for k,v in fields.items()}).evaluate(expr)
                assert np.array_equal(full[:n],prefix,equal_nan=True),(j,'repaint',day)
                cutoffs.append(dict(date=day,max_abs_delta=0.,nan_mask_equal=True))
                del prefix
        bymonth={}
        for period,a in row['A'].items():
            public=a['public'];grid=(public['window_start'],public['window_end'],int(public['sample_count']))
            sig,y=r.grids[grid];xs=[]
            for k,p in enumerate(sig):
                val=correlation(np.where(m.capmask[p],full[p],np.nan),y[k],True)
                if np.isfinite(val):xs.append(val)
            if len(xs)!=grid[2]:
                assert a['local']['s_i_a'] is None
                bymonth[period]=dict(valid_count=len(xs),s_i_a=None);continue
            x=np.array(xs);mu=x.mean();ir=mu/max(x.std(ddof=1),1e-12)
            win=float(np.mean(np.sign(mu)*x>.02));si=float(abs(mu)*abs(ir)*win)
            assert abs(si-a['local']['s_i_a'])<1e-12,(j,period,'A differs')
            bymonth[period]=dict(s_i_a=si,valid_count=len(x),ic_mean=float(mu),icir=float(ir),
                ic_win_rate=win,public_s_i_a=public['s_i_a'],relative_error=si/public['s_i_a']-1)
        seat_a.append(dict(seat=j+1,name=e.seats[j]['name'],by_month=bymonth))
        # The alternate role of public A endpoints is diagnostic only.
        p=row['A']['2026-10']['public']
        sig,_=r.grids[(p['window_start'],p['window_end'],int(p['sample_count']))]
        sig=sig+e.cycle+1
        y=m.prices[sig+e.cycle+1].astype(float)/m.prices[sig+1]-1
        xs=[correlation(np.where(m.capmask[pos],full[pos],np.nan),y[k],True) for k,pos in enumerate(sig)]
        xs=np.array([x for x in xs if np.isfinite(x)])
        mu=float(xs.mean());ir=mu/max(float(xs.std(ddof=1)),1e-12)
        win=float(np.mean(np.sign(mu)*xs>.02));a=abs(mu)*abs(ir)*win
        signal_grid.append(dict(seat=j+1,s_i_a=a,ic_mean=mu,icir=ir,ic_win_rate=win,
            valid_count=len(xs),public_s_i_a=p['s_i_a'],A_ratio=a/p['s_i_a']))
        r.add(j,expr,row['reason'],row['proxy'],ROOT/row['source'])
        assert abs(r.bank[-1]['rankic_mae']-row['rankic_mae'])<1e-12
        assert abs(r.bank[-1]['ic_mae']-row['ic_mae'])<1e-12
        checks.append(dict(seat=j+1,full_history_cache_equal=True,cutoffs=cutoffs,A_independently_equal=True))
        legs.append(standardize(raw,e.mask)*e.directions[j])
        del full;gc.collect()
        print(json.dumps(dict(stage='independent_verified_seat',seat=j+1)),flush=True)
    z=np.array(legs);held=[];path=[]
    for rec in e.records:
        i=e.index[pd.Timestamp(rec['signal'])];act=e.active[:,i]
        composite=z[act,i].sum(axis=0)/act.sum()
        valid=np.flatnonzero(e.mask[i]&np.isfinite(composite));ordered=valid[np.argsort(composite[valid],kind='stable')][::-1]
        selected=ordered[:int(np.ceil(len(ordered)/10))];held.append(selected)
        truth={p['symbol'] for p in rec['rows']};toptruth={p['symbol'] for p in sorted(rec['rows'],key=lambda p:p['rank'])[:20]}
        top=list(map(str,m.stocks[ordered[:20]]));path.append(dict(trade_date=rec['trade'],top20=len(set(top)&toptruth),
            full_overlap=len(set(m.stocks[selected])&truth)/len(truth),top20_symbols=top))
    assert [p['top20'] for p in path]==[p['top20'] for p in expected['path']]
    assert abs(np.mean([p['full_overlap'] for p in path])-expected['mean_full_overlap'])<1e-12
    days=m.cal[(m.cal>=pd.Timestamp(e.records[0]['trade']))&(m.cal<=pd.Timestamp(e.evidence['last_local_date']))]
    trades={pd.Timestamp(rec['trade']):i for i,rec in enumerate(e.records)};prior=set();ids=[];daily=[]
    for day in days:
        p=m.cal.get_loc(day);turn=0.
        if day in trades:
            ids=held[trades[day]];new=set(ids);turn=.5 if not prior else 1-len(prior&new)/len(new);prior=new
        returns=m.prices[p].astype(float)/m.prices[p-1]-1
        daily.append(dict(date=day.strftime('%Y%m%d'),p=float(np.nanmean(returns[ids]))-.006*turn,
            b=float(m.benchmark[p]),turnover=turn))
    months=[]
    for exp in expected['months']:
        period=exp['period'];ds=[d for d in daily if d['date']<=e.evidence['cutoff'][period] and d['date'][:6]==period.replace('-','')]
        pr=np.array([d['p'] for d in ds]);br=np.array([d['b'] for d in ds])
        rex=float((np.prod(1+pr)/np.prod(1+br))**(252/len(pr))-1)
        sr=float(pr.mean()/pr.std(ddof=1)*np.sqrt(252));nav=np.r_[1.,np.cumprod(1+pr)]
        dd=float(np.max(1-nav/np.maximum.accumulate(nav)));turn=sum(d['turnover'] for d in ds)
        c=max(rex,0)/max(turn,.30)*sr*(1-1.2*dd)
        values=dict(annual_rex=rex,annual_sr=sr,max_dd=dd,turn=turn,raw_c=c)
        for k,v in values.items():assert abs(v-exp[k])<1e-10,(period,k,v,exp[k])
        months.append(dict(period=period,**values,days=len(ds)))
    research.save('verification.json',dict(full_history_replay=True,all_dates_fitted=True,strict_oos=False,
        checks=checks,seat_A=seat_a,path=path,months=months,independent_daily_ledger_equal=True,
        daily=daily,public_daily_scores_available=False,platform_confirmed=False,platform_compute=0))
    research.save('selected_signal_grid_sensitivity.json',dict(rows=signal_grid,
        official_grid_changed=False,role='public endpoints treated as signal dates; diagnostic only'))
    print(json.dumps(dict(stage='verified_complete',path=[p['top20'] for p in path],months=months)),flush=True)


if __name__=='__main__':main()
