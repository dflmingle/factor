#!/usr/bin/env python3
"""Build isolated proxy input for the paper's direct allocation architecture."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from shu_mulvey_paper_replication_20261014 import ROOT, BASE, STYLE_KEYS, dump, digest


def restore_sleeve(period_path, dates, valuation_market):
    periods=pd.read_csv(period_path,parse_dates=['date','entry_date','exit_date'])
    ledger_path=period_path.with_name(period_path.name.replace('.periods.csv','.daily_nav.csv'))
    daily=pd.read_csv(ledger_path,parse_dates=['date']).drop_duplicates('date').set_index('date')
    missing_dates=daily.index[daily.nav.isna()]
    repaired=[]
    if len(missing_dates):
        cal,stocks,original_close,valuation_close,cap=valuation_market
        history=pd.read_pickle(period_path.with_name(period_path.name.replace('.periods.csv','.history.pkl')))
        for row in periods.itertuples():
            bad=missing_dates[(missing_dates>row.entry_date)&(missing_dates<=row.exit_date)]
            if not len(bad):continue
            score=history['values'][history['dates'].get_loc(row.date)]
            entry=cal.get_loc(row.entry_date);exit_=cal.get_loc(row.exit_date);signal=cal.get_loc(row.date)
            # Preserve original saved selection, including its factor_valid proxy.
            y=original_close[exit_]/original_close[entry]-1
            ids=np.flatnonzero(np.isfinite(score)&np.isfinite(y)&(cap[signal]>0))
            order=np.argsort(score[ids],kind='stable');groups=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
            held=ids[order[groups==10]]
            start=daily.nav.loc[daily.index<=row.entry_date].iloc[-1]
            for date in bad:
                t=cal.get_loc(date)
                relative=np.mean(valuation_close[t,held]/original_close[entry,held])
                if not np.isfinite(relative):raise ValueError('No past valuation for '+str(date))
                daily.loc[date,'nav']=start*(relative-row.cost)
            # Endpoint and portfolio membership must remain unchanged.
            endpoint=np.mean(valuation_close[exit_,held]/original_close[entry,held])-1
            if abs(endpoint-row.group_return)>3e-6:raise ValueError('Repair changed endpoint')
            repaired.extend(dict(date=str(d.date()),signal_date=str(row.date.date()),
                                  method='last known qfq close for valuation only; original holdings preserved') for d in bad)
        daily.to_csv(BASE/'repaired_daily'/ledger_path.name)
    if daily.nav.isna().any():raise ValueError('Unrepaired net asset values')
    gross=pd.Series(0.,index=dates); netnav=daily.nav.reindex(dates).ffill()
    net=netnav.pct_change(fill_method=None).fillna(0.)
    audit=[]
    for row in periods.itertuples():
        lo=daily.index.searchsorted(row.entry_date,side='right');hi=daily.index.searchsorted(row.exit_date,side='right')
        observed=daily.nav.iloc[lo:hi]
        start=daily.nav.iloc[lo-1]
        # Saved path: netNAV(t)=startNAV*(grossHoldingRelative(t)-knownEntryCost).
        relative=observed/start+row.cost
        ret=relative/relative.shift(1,fill_value=1.)-1
        gross.loc[ret.index]=ret
        error=abs(float(relative.iloc[-1]-1)-row.group_return)
        if error>3e-6:raise ValueError('Gross restoration mismatch '+str(period_path))
        audit.append(dict(signal_date=str(row.date.date()),entry=str(row.entry_date.date()),
                          exit=str(row.exit_date.date()),gross_restore_error=error,entry_cost=float(row.cost)))
    return gross,net,periods.entry_date.min(),audit,digest(period_path),digest(ledger_path),repaired


def main():
    BASE.mkdir(parents=True,exist_ok=True)
    (BASE/'repaired_daily').mkdir(exist_ok=True)
    meta=pd.read_csv(ROOT/'research_reports/platform_alignment/shu-mulvey-long-ready-20261014/factor_metadata.csv')
    paths={r.key:ROOT/r.period_path for r in meta.itertuples()}
    periods=[pd.read_csv(p,usecols=['entry_date','exit_date']) for p in paths.values()]
    last=pd.Timestamp(max(x.exit_date.max() for x in periods))
    data=ROOT/'quantlab/.quantlab/cache/research/cn_equity/regime_long_history_20060101_v1'
    ix=pd.concat([pd.read_parquet(p) for p in sorted((data/'index_daily/000300.SH').glob('*.parquet'))])
    ix['date']=pd.to_datetime(ix.trade_date.astype(str))
    ix=ix.drop_duplicates('date').set_index('date').sort_index()
    dates=ix.index[(ix.index>='2006-01-01')&(ix.index<=last)]
    returns=ix.close.pct_change(fill_method=None).fillna(ix.close/ix.pre_close-1).reindex(dates)
    cal,stocks,fields=pd.read_pickle(ROOT/'research_reports/platform_alignment/regime-long-history-20261014/market_arrays_long_aliasdedup_v3.pkl')
    valuation=pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    valuation_market=(cal,stocks,fields['close'],valuation,fields['cap'])
    gross={};net={};inceptions={};audits=[];repair_rows=[]
    for i,(key,path) in enumerate(paths.items(),1):
        g,n,start,a,ph,dh,repaired=restore_sleeve(path,dates,valuation_market)
        repair_rows.extend(dict(key=key,**row) for row in repaired)
        gross[key]=g;net[key]=n;inceptions[key]=start
        audits.append(dict(key=key,period_path=str(path.relative_to(ROOT)),period_sha256=ph,daily_sha256=dh,
                           inception=str(start.date()),holding_periods=len(a),
                           max_gross_restore_error=max(x['gross_restore_error'] for x in a),repaired_daily_observations=len(repaired)))
        if i%50==0:print('RESTORED_SLEEVES',i,'/',len(paths),flush=True)
    gross['market']=returns;net['market']=returns
    macro={};macro_dates={}
    for key in ['VIXCLS','DGS2','DGS10','DGS3MO']:
        raw=pd.read_csv(BASE/'macro'/f'{key}.csv',parse_dates=['observation_date'])
        raw[key]=pd.to_numeric(raw[key],errors='coerce')
        raw=raw.dropna(subset=[key]).sort_values('observation_date')
        left=pd.DataFrame({'date':dates,'cutoff':dates-pd.Timedelta(days=1)})
        observed=pd.merge_asof(left,raw,left_on='cutoff',right_on='observation_date',direction='backward')
        assert (observed.observation_date<observed.date).all()
        macro[key]=observed[key].to_numpy();macro_dates[key]=observed.observation_date.to_numpy()
    macro=pd.DataFrame(macro,index=dates)
    if not np.isfinite(macro.to_numpy()).all():raise ValueError('Missing macro inputs')
    gross=pd.DataFrame(gross,index=dates);net=pd.DataFrame(net,index=dates)
    if not np.isfinite(gross.to_numpy()).all() or not np.isfinite(net.to_numpy()).all():
        raise ValueError('Nonfinite assets: '+str(gross.columns[~np.isfinite(gross.to_numpy()).all(axis=0)].tolist())
                         +' net '+str(net.columns[~np.isfinite(net.to_numpy()).all(axis=0)].tolist()))
    limitations=[
        'Not original US total-return indices: A-share factor decile sleeves + CSI300 price-return market proxy.',
        'Six style representatives predeclared by economic meaning; not MSCI index construction: '+str(STYLE_KEYS),
        '353 of 592 factors replayed; no positive-return screen; fixed retrospective research universe.',
        'Saved local holdings use factor_valid/forward-label finite availability; investment paths remain platform-alignment proxies.',
        'Underlying sleeves rebalance on saved cycle10 dates and hold cash in gaps; not smart-beta ETF indices.',
        'Gross sleeves restored from saved paths and known entry costs, retaining all original saved panels unchanged.',
        '2018 join: suspended stocks lacking an initial 2018 quote valued at their last observed 2017 qfq close; original holdings/endpoints preserved; repair manifest saved.',
        'FRED US VIX and yields retained as original named variables, observed by prior calendar day for China; not China macro equivalents.',
        'FRED values are current downloaded vintage, not original unrevised release snapshots.',
        'No original 1993-2024 Bloomberg indices or historical splice verification; original-paper numerical results cannot be claimed.',
        'Local cost sensitivity uses precomputed net sleeves plus 0.30% overlay fees under weights fitted with paper 5bp timing fees.',
        'Financial announcement vintages and some factor fields remain labeled proxies; same-window discovery is exploratory.'
    ]
    bundle=dict(gross_returns=gross,net_returns=net,macro=macro,inceptions=inceptions,
                mode='a_share_method_proxy',limitations=limitations)
    pd.to_pickle(bundle,BASE/'inputs.pkl')
    pd.DataFrame(audits).to_csv(BASE/'sleeve_input_audit.csv',index=False)
    pd.DataFrame(repair_rows).to_csv(BASE/'daily_valuation_repairs.csv',index=False)
    pd.DataFrame(macro_dates,index=dates).to_parquet(BASE/'macro_observation_dates.parquet')
    dump(BASE/'input_manifest.json',dict(mode=bundle['mode'],input_sha256=digest(BASE/'inputs.pkl'),
         market='Tushare index_daily 000300.SH close price-return, not total return',
         first_date=str(dates.min().date()),last_date=str(dates.max().date()),days=len(dates),
         replayed_factors=len(paths),eligible_library=592,all592_completed=False,
         original_bloomberg_total_return_indices_verified=False,limitations=limitations))
    dump(BASE/'original_data_requirements.json',dict(
        status='missing_original_data',
        returns_columns=['value','size','momentum','quality','lowvol','growth','market'],
        sample='1993 to mid-2024; daily total returns; 2007-2024 test',
        source='Bloomberg used by paper; equivalent validated licensed export acceptable',
        indices=dict(market='MSCI USA',value='MSCI USA Enhanced Value',size='MSCI USA Low Size',
          momentum='MSCI USA Momentum SR Variant',quality='MSCI USA Sector Neutral Quality',
          lowvol='MSCI USA Minimum Volatility',growth='Russell 1000 Growth'),
        splices=dict(value='MSCI USA Value Weighted before 1997/12',size='MSCI USA Equal Weighted before 1994/6',
          momentum='MSCI USA Momentum before 2002/6',quality='MSCI USA Quality before 1998/12',
          lowvol='MSCI USA Risk Weighted before 1994/6'),
        remaining_author_details=['hyperparameter search grid','exact active-wealth/RSI/MACD definitions',
            'standardization/winsorization details','confidence calibration and EW drift convention'],
        do_not_replace_with='ETF backfills, price-only indices or long-short Fama-French factors'))
    print('INPUTS_COMPLETE',len(paths),len(dates),dates.min(),dates.max(),flush=True)


if __name__=='__main__':main()
