"""Independent saved-data residual audit; only writes this review's peer directory."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
SEARCH = BASE / 'top50-20261013/search_v1'
POOLS = {36:'b2c310a78c6ed155e763aaae', 8:'18067f13fb2f894e0a45b181', 6:'37aa063b9ce7a1d2c3a39852'}


def load(path, sources):
    raw = path.read_bytes()
    relative = path.relative_to(BASE)
    digest = hashlib.sha256(raw).hexdigest()
    frozen = OUT / 'inputs' / digest / path.name
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(raw)
    sources.append(dict(path=str(relative), frozen_path=str(frozen.relative_to(OUT)),
                        sha256=digest))
    return json.loads(raw)


def mae(x, y):
    assert len(x) == len(y)
    pairs = [(a,b) for a,b in zip(x,y) if a is not None and b is not None and math.isfinite(a) and math.isfinite(b)]
    return mean(abs(a-b) for a,b in pairs) if pairs else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rank', type=int, choices=POOLS, required=True)
    rank = parser.parse_args().rank
    pool = POOLS[rank]
    dest = OUT / f'peer-{rank}'
    dest.mkdir(exist_ok=True)
    sources = []
    data = load(SEARCH / 'peers_v5_Broster' / pool / 'verified_best.json', sources)
    evidence = load(SEARCH / 'evidence' / (pool+'.json'), sources)
    assert len(data['seat_A']) == len(evidence['seats']) == len(data['ic']) == len(data['rank_ic'])
    seats = []
    for i, (seat, hist) in enumerate(zip(evidence['seats'],data['seat_A'])):
        assert seat['id'] == hist['seat_id']
        points = seat['points']
        pearson = [p.get('pearson') for p in points]
        rankic = [p.get('rank_ic') for p in points]
        assert len(pearson) == len(data['ic'][i])
        assert len(rankic) == len(data['rank_ic'][i])
        dates = [p['exposure_date'] for p in points]
        assert dates == sorted(dates) and len(dates) == len(set(dates))
        a_rows = []
        for month, values in hist['by_month'].items():
            local, public = values['local'], values['public']
            if local.get('s_i_a') is None or public.get('s_i_a') is None:
                continue
            p = public['s_i_a']
            a_rows.append(dict(month=month, local=local['s_i_a'], public=p,
                               signed_relative=local['s_i_a']/p-1 if p else None,
                               local_first_signal=local.get('first_signal'), local_last_signal=local.get('last_signal'),
                               public_window_start=public.get('window_start'), public_window_end=public.get('window_end'),
                               date_role_confirmed=local.get('date_role_confirmed'), financial_proxy=local.get('financial_proxy')))
        seats.append(dict(index=i, id=seat['id'], name=seat['name'], direction=seat['direction'],
                          formula=data['formulas'][i], effective_trade_date=seat.get('effective_trade_date'),
                          end_trade_date=seat.get('end_trade_date'), points=len(points),
                          exposure_dates=dates, ic_mae=mae(data['ic'][i],pearson),
                          rankic_mae=mae(data['rank_ic'][i],rankic), A=a_rows))
    # Recompute aggregate residuals over observations, not over unequal-length legs.
    for key, observed, predicted in [('ic_mae','pearson','ic'),('rankic_mae','rank_ic','rank_ic')]:
        lhs=[];rhs=[]
        for i, seat in enumerate(evidence['seats']):
            lhs.extend(data[predicted][i]);rhs.extend(p.get(observed) for p in seat['points'])
        computed=mae(lhs,rhs)
        assert computed is not None and abs(computed-data[key]) < 1e-10, (key,computed,data[key])
    records={r['signal_trade_date']:r for r in evidence['records']}
    checks=[]
    for check in data['checks']:
        rec=records[check['signal_date']]
        assert check['public_holdings'] == len(rec['rows'])
        active=[s for s in evidence['seats'] if s.get('effective_trade_date','99999999') <= rec['trade_date']
                and (not s.get('end_trade_date') or rec['trade_date'] < s['end_trade_date'])]
        checks.append(dict(signal_date=check['signal_date'], trade_date=rec['trade_date'],
                           overlap=check['overlap'], public_count=check['public_holdings'],
                           predicted_count=check['predicted_holdings'],
                           count_deficit=check['public_holdings']-check['predicted_holdings'],
                           missing_numeric_predictions=check['missing_numeric_predictions'],
                           universe_count=rec['universe_count'], public_active_count=rec['active_factor_count'],
                           metadata_active_count=len(active), active_ids=[s['id'] for s in active],
                           stuck_count=len(rec.get('stuck_symbols',[]))))
    group={}
    for c in checks:
        group.setdefault(c['public_active_count'],[]).append(c['overlap'])
    summary=dict(rank=rank, name=data['target']['display_name'], pool_id=pool, sources=sources,
                 kind='saved-observation residual audit; no new formula market evaluation',
                 metrics=data['acceptance']['actual'], boards=data['boards'], seats=seats, checks=checks,
                 overlap_by_public_active_count={str(n):dict(dates=len(v),mean_overlap=mean(v)) for n,v in group.items()},
                 seat_order_by_rankic_error=[s['name'] for s in sorted(seats,key=lambda s:s['rankic_mae'] or 0,reverse=True)],
                 validation=dict(passed=True,aggregate_ic_recomputed=True,aggregate_rankic_recomputed=True,
                                 seat_ids_and_observation_lengths_matched=True,public_holding_counts_matched=True),
                 accepted=False, platform_compute=0, new_backtest=False)
    (dest/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(rank=rank,name=summary['name'],validated=True,
                         worst_rankic=summary['seat_order_by_rankic_error'][:3],
                         groups=summary['overlap_by_public_active_count'],
                         count_deficits=[c['count_deficit'] for c in checks]),ensure_ascii=False))


if __name__ == '__main__':
    main()
