#!/usr/bin/env python3
"""Audit and assemble an isolated 2006+ training snapshot; preserve formal data."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q

ROOT=q.ROOT
DATA=q.CACHE/'regime_long_history_20060101_v1'
OUT=ROOT/'research_reports/platform_alignment/regime-long-history-20261014'
VERSION=q.ALIGNMENT_RULE_VERSION+'-regime-training2006-finannquarantine-v2'

def dump(name,value):q.dump(OUT/name,value)

def audit_download():
    progress=json.loads((OUT/'download_progress.json').read_text())
    if not progress.get('completed'):raise RuntimeError('Historical download is incomplete')
    rows=[];errors=[]
    for path in sorted(DATA.rglob('*.parquet')):
        if any(part in {'combined_view','financial_pit_validated_v3'} for part in path.relative_to(DATA).parts):continue
        manifest=path.with_suffix('.json')
        if not manifest.exists():errors.append(str(path)+': missing manifest');continue
        m=json.loads(manifest.read_text())
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        frame=pd.read_parquet(path)
        if digest!=m.get('sha256') or len(frame)!=m.get('rows'):errors.append(str(path)+': checksum/rows mismatch')
        rows.append(dict(path=str(path.relative_to(ROOT)),api=m.get('api'),rows=len(frame),sha256=digest))
    cal=pd.concat([pd.read_parquet(p) for p in sorted((DATA/'trade_calendar').glob('*.parquet'))])
    dates=sorted(cal.loc[(cal.is_open==1)&(cal.cal_date.astype(str)<'20180101'),'cal_date'].astype(str).unique())
    for api in ['stk_factor','daily_basic']:
        for date in dates:
            if not (DATA/api/f'{date}.parquet').exists():errors.append(f'missing {api} {date}')
    for endpoint in ['income','balancesheet','cashflow','fina_indicator']:
        for period in pd.period_range('2006Q1','2017Q4',freq='Q'):
            if not (DATA/'financial_full_a'/endpoint/f'period_{period.end_time.strftime("%Y%m%d")}.parquet').exists():errors.append(f'missing {endpoint} {period}')
            if not (DATA/'financial_full_fields_v2'/endpoint/f'period_{period.end_time.strftime("%Y%m%d")}.parquet').exists():errors.append(f'missing explicit research fields {endpoint} {period}')
    pd.DataFrame(rows).to_csv(OUT/'download_file_inventory.csv',index=False)
    dump('download_verification.json',dict(completed=not errors,files=len(rows),historical_trading_days=len(dates),errors=errors,checks=['SHA256','row_count','every_open_day_both_price_endpoints','every_quarter_four_financial_endpoints']))
    if errors:raise RuntimeError(f'{len(errors)} historical snapshot verification errors')
    return pd.DatetimeIndex(pd.to_datetime(dates))

def assemble_market():
    oldcal=audit_download()
    basecal,basestocks,base=q.load_market()
    if oldcal.max()>=basecal.min():raise ValueError('Historical and immutable calendars overlap')
    symbols=set(basestocks)
    for date in oldcal:
        for api in ['stk_factor','daily_basic']:
            a=pd.read_parquet(DATA/api/f'{date:%Y%m%d}.parquet',columns=['ts_code'])
            symbols.update(s for s in a.ts_code.astype(str) if s.endswith(('.SH','.SZ')))
    stocks=pd.Index(sorted(symbols));calendar=oldcal.append(basecal)
    mapping=stocks.get_indexer(basestocks);offset=len(oldcal)
    # Newly queried qfq prices may use a later rebasing date. Compare native
    # qfq at several real-trading anchors to the immutable saved snapshot.
    ratios=[]
    for path in sorted((DATA/'qfq_overlap_anchors').glob('*.parquet')):
        date=pd.Timestamp(path.stem);t=basecal.get_loc(date);a=pd.read_parquet(path)
        idx=basestocks.get_indexer(a.ts_code);ok=idx>=0
        idx=idx[ok];a=a.loc[ok].copy()
        saved=base['close'][t,idx];new=a.close_qfq.to_numpy(float)
        good=np.isfinite(saved)&np.isfinite(new)&(new>0)&np.isfinite(base['open'][t,idx])
        ratios.extend(dict(symbol=str(s),date=str(date.date()),scale=float(r)) for s,r in zip(a.ts_code.to_numpy()[good],(saved/new)[good]))
    ratio=pd.DataFrame(ratios)
    if ratio.empty:raise ValueError('No overlap anchors')
    scale=ratio.groupby('symbol').scale.median()
    spread=ratio.assign(relative_error=abs(ratio.scale/ratio.symbol.map(scale)-1))
    worst=spread.groupby('symbol').relative_error.max()
    bad=worst[worst>5e-4]
    ratio.to_csv(OUT/'qfq_overlap_ratios.csv',index=False)
    if len(bad):
        bad.to_csv(OUT/'qfq_nonconstant_rebase.csv')
        raise ValueError(f'{len(bad)} stocks have inconsistent qfq rebase across anchors')
    fields={k:np.full((len(calendar),len(stocks)),np.nan,np.float32) for k in base}
    factors=stocks.map(scale).to_numpy(float);no_anchor=~np.isfinite(factors);factors[no_anchor]=1.
    for t,date in enumerate(oldcal):
        a=pd.read_parquet(DATA/'stk_factor'/f'{date:%Y%m%d}.parquet');j=stocks.get_indexer(a.ts_code);ok=j>=0;j=j[ok];a=a.loc[ok]
        for field,column in [('close','close_qfq'),('open','open_qfq'),('high','high_qfq'),('low','low_qfq')]:fields[field][t,j]=(a[column].to_numpy(float)*factors[j]).astype(np.float32)
        for field,column in [('volume','vol'),('amount','amount')]:fields[field][t,j]=a[column].to_numpy(np.float32)
        a=pd.read_parquet(DATA/'daily_basic'/f'{date:%Y%m%d}.parquet');j=stocks.get_indexer(a.ts_code);ok=j>=0;j=j[ok];a=a.loc[ok]
        for field,column in [('cap','total_mv'),('turnover','turnover_rate'),('raw_close','close')]:fields[field][t,j]=a[column].to_numpy(np.float32)
        if t%500==0:print('ASSEMBLED',t,'/',len(oldcal),flush=True)
    active=fields['cap']>0
    for k in ['close','open','high','low','volume','amount','raw_close']:
        fields[k][~active|(fields[k]<=0)]=np.nan
    fields['close'][:offset]=pd.DataFrame(fields['close'][:offset]).ffill().to_numpy(np.float32)
    for k,v in base.items():fields[k][offset:,mapping]=v
    historical_only=stocks.get_indexer(stocks.difference(basestocks))
    # Continue only the historical-only close columns after the join. These
    # stocks have no later active cap or score, but a held terminal price must
    # not vanish just because the immutable base snapshot omits the symbol.
    fields['close'][:,historical_only]=pd.DataFrame(fields['close'][:,historical_only]).ffill().to_numpy(np.float32)
    for k,v in base.items():np.testing.assert_array_equal(fields[k][offset:,mapping],v)
    unanchored=[]
    for j in np.flatnonzero(no_anchor):
        ix=np.flatnonzero(active[:offset,j])
        if len(ix):unanchored.append(dict(symbol=stocks[j],first=str(oldcal[ix[0]].date()),last=str(oldcal[ix[-1]].date()),base_active_days=int(np.sum(active[offset:,j])),qfq_scale=1.,status='native_qfq_unanchored_price_scale_proxy'))
    pd.DataFrame(unanchored).to_csv(OUT/'unanchored_historical_stocks.csv',index=False)
    delta=fields['close'][offset]/fields['close'][offset-1]-1
    linked=np.isfinite(delta)&active[offset]&active[offset-1]
    discontinuities=[dict(symbol=stocks[j],close_return=float(delta[j])) for j in np.flatnonzero(linked&(abs(delta)>.25))]
    coverage=[]
    for year in sorted(set(oldcal.year)):
        mask=oldcal.year==year;act=active[:offset][mask]
        coverage.append(dict(year=int(year),active_stock_days=int(act.sum()),**{k:float(np.isfinite(v[:offset][mask][act]).mean()) for k,v in fields.items()}))
    pd.DataFrame(coverage).to_csv(OUT/'historical_active_field_coverage.csv',index=False)
    dump('market_assembly_audit.json',dict(version=VERSION,completed=True,history_start=str(calendar.min().date()),latest=str(calendar.max().date()),calendar_rows=len(calendar),symbols=len(stocks),base_symbols=len(basestocks),historical_only_symbols=len(stocks)-len(basestocks),qfq_anchors=3,anchored_symbols=len(scale),max_anchor_relative_error=float(worst.max()),unanchored_historical_symbols=len(unanchored),unanchored_policy='native qfq proxy; use with scale sensitivity for price-level factors',formal_base_values='every field exact equality including NaNs',immutable_base_calendar_start=str(basecal.min().date()),historical_only_stocks_base_active_days=int(active[offset:,stocks.get_indexer(stocks.difference(basestocks))].sum()),boundary_return_above25pct=discontinuities,one_way_cost=.003,label='close(t+1)->close(t+11)',formal_window=['20210907','20260907'],warmup_formal_unchanged='20180101',training_history_extension=True,scope='data assembly; long-history factor replay and model refit are separate outputs'))
    saved=OUT/'market_arrays_long.pkl';tmp=saved.with_suffix('.pkl.tmp');pd.to_pickle((calendar,stocks,fields),tmp);tmp.replace(saved)
    print('MARKET_COMPLETE',len(calendar),len(stocks),flush=True)
    return calendar,stocks,fields

def financial_view():
    """Isolated raw financial union usable by the existing causal PIT readers."""
    target=DATA/'combined_view';target.mkdir(exist_ok=True)
    files=[]
    for endpoint in ['income','balancesheet','cashflow','fina_indicator']:
        folder=target/'financial_full_a'/endpoint;folder.mkdir(parents=True,exist_ok=True)
        for prefix,parent in [('historical_validated',DATA/'financial_pit_validated_v3'),('immutable2018',q.CACHE/'financial_full_a')]:
            for p in sorted((parent/endpoint).glob('*.parquet')):
                link=folder/f'{prefix}_{p.name}'
                if not link.exists():link.symlink_to(p.resolve())
                files.append(dict(endpoint=endpoint,path=str(link.relative_to(ROOT)),source=str(p.relative_to(ROOT))))
    pd.DataFrame(files).to_csv(OUT/'financial_union_inventory.csv',index=False)
    dump('financial_union_config.json',dict(data_root=str(target.relative_to(ROOT)),endpoints=4,files=len(files),PIT='max(ann_date,f_ann_date), consolidated statements, chronological quarter replay and contiguous TTM; historical vendor revision completeness is a proxy',no_backward_fill=True,immutable_snapshots_unchanged=True))

def training_market_path():return OUT/'market_arrays_long_aliasdedup_v3.pkl'

def finalize_historical_aliases():
    """Deduplicate only verified identical-cap rename aliases before 2018."""
    final=training_market_path()
    if final.exists():return final
    calendar,stocks,fields=pd.read_pickle(OUT/'market_arrays_long.pkl')
    historical=calendar<'2018-01-01';rows=[]
    for old,new in [('000022.SZ','001872.SZ'),('000043.SZ','001914.SZ')]:
        j,k=stocks.get_indexer([old,new])
        if min(j,k)<0:continue
        same=np.isclose(fields['cap'][:,j],fields['cap'][:,k],rtol=1e-6,atol=1e-5)
        mask=historical&same&np.isfinite(fields['close'][:,k])&~np.isfinite(fields['close'][:,j])&(fields['cap'][:,j]>0)
        rows.append(dict(old_code=old,canonical_code=new,verified_identical_cap_days=int(mask.sum()),first=str(calendar[mask].min().date()) if mask.any() else None,last=str(calendar[mask].max().date()) if mask.any() else None,scope='historical only; old alias without qfq removed from active cross-section'))
        for value in fields.values():value[mask,j]=np.nan
    pd.DataFrame(rows).to_csv(OUT/'historical_code_alias_dedup.csv',index=False)
    active=fields['cap']>0;coverage=[]
    for year in sorted(set(calendar[historical].year)):
        mask=calendar.year==year;act=active[mask]
        coverage.append(dict(year=int(year),active_stock_days=int(act.sum()),**{k:float(np.isfinite(v[mask][act]).mean()) for k,v in fields.items()}))
    pd.DataFrame(coverage).to_csv(OUT/'historical_active_field_coverage_aliasdedup_v3.csv',index=False)
    basecal,basestocks,base=q.load_market();di=calendar.get_indexer(basecal);si=stocks.get_indexer(basestocks)
    for k,value in base.items():np.testing.assert_array_equal(fields[k][np.ix_(di,si)],value)
    pd.to_pickle((calendar,stocks,fields),final)
    audit=json.loads((OUT/'market_assembly_audit.json').read_text());audit.update(version=q.ALIGNMENT_RULE_VERSION+'-regime-training2006-finann-aliasdedup-v3',verified_aliases=rows,formal_base_values='every field exact equality including NaNs after alias dedup',active_cross_section_policy='verified identical-cap missing-qfq old aliases excluded before2018; formal values immutable')
    dump('market_assembly_audit_aliasdedup_v3.json',audit)
    print('ALIAS_DEDUP_COMPLETE',sum(r['verified_identical_cap_days'] for r in rows),flush=True)
    return final

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if not (OUT/'market_arrays_long.pkl').exists():assemble_market()
    else:audit_download()
    financial_view()

if __name__=='__main__':main()
