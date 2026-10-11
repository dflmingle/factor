"""Check the three frozen signals with an independent pandas evaluator."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/fengmao-multiround2-20261011'


def main():
    a=np.load(OUT/'atoms.npz')
    y,cap=a['target'],a['market_cap']
    axes=json.loads((OUT/'axes.json').read_text(encoding='utf-8'))
    dates=pd.DatetimeIndex(axes['dates'])
    symbols=np.asarray(axes['symbols'])
    results=pd.read_csv(OUT/'results.csv')
    model=json.loads((OUT/'frozen_models.json').read_text(encoding='utf-8'))
    groups,top,years=[],[],[]
    maxdelta=0.;count=0
    for ci in range(1,4):
        name=f'FM_MULTI_{ci:02d}'
        x=np.load(OUT/(name+'_signals.npy'))
        for window in results.window.unique():
            saved=pd.read_csv(OUT/f'{name}_{window}_periods.csv')
            previous={};detail=[]
            for row in saved.itertuples():
                i=dates.get_loc(pd.Timestamp(row.date))
                mask=np.isfinite(x[i]) & np.isfinite(y[i]) & np.isfinite(cap[i])
                ids=np.flatnonzero(mask)
                xx,yy=pd.Series(x[i,ids],index=ids),pd.Series(y[i,ids],index=ids)
                assert len(ids)==row.stocks
                ic,ric=xx.corr(yy),xx.corr(yy,method='spearman')
                maxdelta=max(maxdelta,abs(ic-row.ic),abs(ric-row.rank_ic))
                # Spearman's rank implementation can differ by a few ulps
                # across pandas/scipy versions on large cross-sections.
                # Keep the check tight while allowing that harmless drift.
                assert abs(ic-row.ic)<1e-8 and abs(ric-row.rank_ic)<2e-8
                buckets=np.ceil(xx.rank(method='first')*10/len(xx)).clip(1,10).astype(int)
                assert set(buckets)==set(range(1,11))
                for group in range(1,11):
                    held=set(buckets.index[buckets.eq(group)])
                    turnover=np.nan if group not in previous else 1-len(held & previous[group])/len(held)
                    previous[group]=held
                    gross=float(yy.loc[list(held)].mean()-yy.mean())
                    detail.append(dict(candidate=name,window=window,date=row.date,group=group,stocks=len(held),gross_excess=gross,turnover=turnover))
                    if group==10:
                        assert abs(gross-row.gross_excess)<1e-10
                        assert (np.isnan(turnover) and np.isnan(row.turnover)) or abs(turnover-row.turnover)<1e-10
                count+=1
            table=pd.DataFrame(detail)
            table.to_csv(OUT/f'{name}_{window}_group_periods.csv',index=False)
            for group,b in table.groupby('group'):
                gross=float(b.gross_excess.mean()*25.2);turn=float(b.turnover.mean())
                net=gross-turn*.006*25.2
                groups.append(dict(candidate=name,window=window,group=int(group),gross_excess=gross,turnover=turn,net_excess=net))
                if group==10:
                    reference=results[(results.candidate==name)&(results.window==window)].iloc[0]
                    assert abs(net-reference.net_excess)<1e-10
            if window=='formal_5y':
                for year,b in saved.groupby(saved.date.str[:4]):
                    years.append(dict(candidate=name,year=year,periods=len(b),rank_ic=float(b.rank_ic.mean()),ic=float(b.ic.mean()),
                        gross_excess=float(b.gross_excess.mean()*25.2),turnover=float(b.turnover.mean()),
                        net_excess=float(b.gross_excess.mean()*25.2-b.turnover.mean()*.006*25.2)))
        for i,date in enumerate(dates):
            raw=pd.Series(x[i],index=np.arange(len(symbols))).dropna().sort_values(ascending=False,kind='stable')
            for rank,ident in enumerate(raw.index[:20],1):
                top.append(dict(candidate=name,date=str(date.date()),rank=rank,instrument=symbols[ident],value=float(raw[ident])))
    checks=json.loads((OUT/'causality_checks.json').read_text(encoding='utf-8'))
    assert all(c['masks_equal'] and c['max_difference']==0 for c in checks)
    pair=[]
    for i in range(1,4):
        for j in range(i+1,4):
            x1=np.load(OUT/f'FM_MULTI_{i:02d}_signals.npy')
            x2=np.load(OUT/f'FM_MULTI_{j:02d}_signals.npy')
            rho=[]
            for day in range(len(dates)):
                left,right=pd.Series(x1[day]),pd.Series(x2[day])
                rho.append(left.corr(right,method='spearman'))
            pair.append(dict(left=f'FM_MULTI_{i:02d}',right=f'FM_MULTI_{j:02d}',signal_date_spearman_mean=float(np.nanmean(rho))))
    pd.DataFrame(pair).to_csv(OUT/'finalist_correlations.csv',index=False)
    pd.DataFrame(groups).to_csv(OUT/'deciles.csv',index=False)
    pd.DataFrame(top).to_csv(OUT/'top20.csv',index=False)
    pd.DataFrame(years).to_csv(OUT/'years.csv',index=False)
    metadata=json.loads((OUT/'metadata.json').read_text(encoding='utf-8'))
    gp=json.loads((OUT/'round_results.json').read_text(encoding='utf-8'))
    assert len(gp)==6
    output=dict(status='passed',pandas_period_checks=count,summary_rows=len(results),ic_max_abs_delta=maxdelta,
        actual_ten_groups_membership_turnover_cost=True,prefix_cells=sum(c['cells'] for c in checks),GP_rounds=6,
        all_models_frozen=model,unique_new_formulas=metadata['unique_formulas'],
        conservative_test_denominator=240+3+5760+2048+1,
        correction_threshold=.05/(240+3+5760+2048+1),validation_status='previously researched historical data')
    (OUT/'verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS',count,'periods; max IC delta',maxdelta)


if __name__=='__main__':
    main()
