"""Freeze saved peer evidence without loading a market engine or changing searches."""
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
SEARCH = BASE / 'top50-20261013/search_v1'


def source(path):
    raw = path.read_bytes()
    relative = path.relative_to(BASE)
    digest = hashlib.sha256(raw).hexdigest()
    frozen = OUT / 'inputs' / digest / path.name
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(raw)
    return json.loads(raw), dict(path=str(relative), frozen_path=str(frozen.relative_to(OUT)),
                                sha256=digest)


def main():
    peers = []
    for path in sorted((SEARCH / 'peers_v5_Broster').glob('*/verified_best.json')):
        data, provenance = source(path)
        acceptance = data['acceptance']
        row = dict(rank=data['target']['rank'], name=data['target']['display_name'],
                   pool_id=path.parent.name, cycle=data['cycle'], formula_count=len(data['formulas']),
                   source=provenance, metrics=acceptance['actual'], boards=data['boards'],
                   automated_reference_pass=acceptance['passed'],
                   failure_metrics=[r['metric'] for r in acceptance['failures']],
                   observed_dates=len(data['checks']), public_date_role_confirmed=data['public_date_role_confirmed'])
        row['status'] = 'historical_reference_pass' if acceptance['passed'] else 'not_accepted'
        if row['pool_id'] == '0b658b582ae4601c1f4d52d8':
            checkpoint, cp_source = source(BASE / 'cases/alpha-20261015-acceptance/checkpoint.json')
            refinement, ref_source = source(BASE / 'alpha-final-mechanisms-20261015-v1/result.json')
            row.update(status='user_accepted_behavioral_replication',
                       historical_metrics_superseded=True, acceptance_source=cp_source,
                       refinement_source=ref_source,
                       current_summary=dict(october_top20=refinement['corrected']['october']['top20'],
                                            note='Use Alpha case and refinement; do not rank stale automated metrics'))
        peers.append(row)
    peers.sort(key=lambda r: r['rank'])
    assert len(peers) == 50 and len({p['pool_id'] for p in peers}) == 50
    assert sum(p['status'] != 'not_accepted' for p in peers) == 2
    refinements = []
    for rank in (6,27,36):
        data, provenance = source(SEARCH / f'residual_refinement_v1/refine_{rank}.status.latest_cycle.json')
        refinements.append(dict(rank=rank, source=provenance, saved_result=data,
                                note='Separate candidate/version; do not splice metrics into broad-search row. Not live process status.'))
    result = dict(as_of='2026-10-15', scope='saved-evidence inventory; no new market rebuild or live status claim',
                  total=50, behavioral_outcomes=2, not_accepted=48, peers=peers,
                  separate_refinements=refinements, platform_compute=0, restarted_searches=False)
    (OUT / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print('Inventory: 50 peers; 2 behavioral outcomes; 48 not accepted; zero platform compute')


if __name__ == '__main__':
    main()
