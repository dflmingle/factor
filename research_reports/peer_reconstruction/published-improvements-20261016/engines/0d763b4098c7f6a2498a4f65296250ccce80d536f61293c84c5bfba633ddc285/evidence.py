"""Extract variable-seat public targets, preserving missing/revised evidence."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PUBLIC=HERE.parent/'public'


def read(path):return json.loads(path.read_text())


def extract(target,market):
    pool=target['pool_id'];profiles={m:read(PUBLIC/'players'/pool/f'{m}.json')for m in ['2026-09','2026-10']}
    latest=profiles['2026-10'];cycle=int(latest['header']['rebalance_cycle_days'])
    monthly={m:d['breakdown']for m,d in profiles.items()}
    cutoff={m:pd.Timestamp(d.get('data_cutoff_at', '2026-10-12')).tz_localize(None).normalize()
            for m,d in monthly.items()}
    last=min(market.cal[-1],cutoff['2026-10'])
    seats={}
    for month,d in profiles.items():
        for s in d.get('factor_pool_details',[]):
            seat_id=s['factor_instance_id']
            seats.setdefault(seat_id,dict(id=seat_id,name=s['factor_name'],direction=s['direction'],A={},points={},pearson={},snapshots=[],revision_conflicts=[]))
            seats[seat_id]['A'][month]=s
    for seat in seats.values():
        files=sorted((PUBLIC/'trends'/pool/seat['id']).glob('*.json'))
        previous_n,previous_total,previous_revision=0,0.,None
        snapshots=[]
        for f in files:
            d=read(f)
            if d.get('collection_error')or not d.get('trade_date')or pd.Timestamp(d['trade_date'])>last:
                continue
            rev=d.get('revision');ic=d.get('ic_metrics',{});n=int(ic.get('sample_count')or 0);mu=ic.get('ic_mean')
            if previous_revision is not None and rev!=previous_revision:
                seat['revision_conflicts'].append(dict(date=d['trade_date'],previous=previous_revision,current=rev))
                previous_n,previous_total=0,0.
            seat.update({k:d.get(k)for k in ['revision','effective_trade_date','end_trade_date','is_historical','included_in_current_metrics','factor_status']})
            for point in d.get('trend',{}).get('points',[]):
                key=point['exposure_date'];end=point['return_end_date']
                if pd.Timestamp(end)>last or pd.Timestamp(key)not in market.panel_map:
                    continue
                if key in seat['points']and abs(seat['points'][key]['rank_ic']-point['rank_ic'])>1e-10:
                    seat['revision_conflicts'].append(dict(date=d['trade_date'],exposure=key,reason='rankIC changed'))
                seat['points'][key]=point
            total=n*mu if mu is not None else None
            if total is not None and n==previous_n+1 and ic.get('last_exposure_date'):
                seat['pearson'][ic['last_exposure_date']]=float(total-previous_total)
            elif total is not None and n==previous_n and abs(total-previous_total)>1e-8:
                seat['revision_conflicts'].append(dict(date=d['trade_date'],reason='same count, cumulative Pearson changed'))
            if total is not None and n>=previous_n:
                previous_n,previous_total=n,total
            previous_revision=rev
            if n and total is not None:
                snapshots.append(dict(date=d['trade_date'],revision=rev,count=n,mean=mu))
        seat['snapshots']=snapshots
        metadata_path=PUBLIC/'latest_metadata'/pool/(seat['id']+'.json')
        if metadata_path.exists():
            metadata=read(metadata_path)
            if metadata.get('effective_trade_date'):
                # Use lifecycle metadata only. October-13 returns/IC never
                # enter the frozen October-12 fitted diagnostic.
                seat.update({k:metadata.get(k)for k in ['revision','effective_trade_date','end_trade_date',
                    'is_historical','included_in_current_metrics','factor_status']})
                seat['lifecycle_metadata_asof']=metadata.get('trade_date')
        seat['points']=[dict(**p,pearson=seat['pearson'].get(p['exposure_date']))for p in sorted(seat['points'].values(),key=lambda p:p['exposure_date'])]
        del seat['pearson']
    records=[]
    for f in sorted((PUBLIC/'holdings'/pool).glob('*.json')):
        if f.stem=='latest':continue
        d=read(f)
        if d.get('collection_error')or d.get('data_status')!='ok'or not d.get('collection_complete')or not d.get('rows'):
            continue
        if pd.Timestamp(d['trade_date'])>last or pd.Timestamp(d['signal_trade_date'])not in market.panel_map:
            continue
        d['trade']=d['trade_date'];d['signal']=d['signal_trade_date'];records.append(d)
    records=sorted({r['trade']:r for r in records}.values(),key=lambda r:r['trade'])
    seat_list=list(seats.values())
    notes=[]
    if any(s['revision_conflicts']for s in seat_list):notes.append('revised public observations retained, not silently merged')
    if any(not s['points']for s in seat_list):notes.append('some seats lack completed IC periods; A/holdings still constrain them')
    if any(not s.get('effective_trade_date')for s in seat_list):notes.append('some effective dates unavailable; inferred active membership is a proxy')
    pack=dict(target=target,cycle=cycle,last_local_date=last.strftime('%Y%m%d'),seats=seat_list,records=records,
        monthly=monthly,cutoff={m:d.strftime('%Y%m%d')for m,d in cutoff.items()},notes=notes,
        scope='retrospective public behavior reconstruction; no source identity or alpha claim',
        lifecycle_version='public-activation-metadata-v2',platform_compute=0)
    return pack


def pack_all(market):
    targets=read(PUBLIC/'targets.json');out=HERE/'evidence';out.mkdir(exist_ok=True)
    rows=[]
    for t in targets:
        e=extract(t,market)
        (out/f"{t['pool_id']}.json").write_text(json.dumps(e,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        rows.append(dict(rank=t['rank'],name=t['display_name'],pool_id=t['pool_id'],seats=len(e['seats']),cycle=e['cycle'],
                         holding_dates=len(e['records']),rankic_points=sum(len(s['points'])for s in e['seats']),
                         pearson_points=sum(p['pearson']is not None for s in e['seats']for p in s['points']),
                         seats_without_IC=sum(not s['points']for s in e['seats']),notes=e['notes']))
    (out/'coverage.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return rows
