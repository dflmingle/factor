"""Independent checks against the frozen raw observations, without live inputs."""
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np

OUT = Path(__file__).resolve().parent
PREFIX = 'research_reports/peer_reconstruction/top50-20261013'


def main():
    manifest = json.loads((OUT / 'input_manifest.json').read_text())
    teams = json.loads((OUT / 'audit.json').read_text())
    replay = np.load(OUT / 'replay_axes_mask.npz')
    available_dates = set(replay['dates'])
    verified_files, dates_checked = 0, 0
    with zipfile.ZipFile(OUT / 'frozen_inputs.zip') as archive:
        entries = archive.namelist()
        assert len(entries) == len(set(entries)), 'duplicate archived source'
        for key in entries:
            data = archive.read(key)
            assert hashlib.sha256(data).hexdigest() == manifest[key]['sha256'], key
            verified_files += 1
        def read(key):
            return json.loads(archive.read(key))
        for team in teams:
            pool = team['summary']['pool_id']
            evidence = read(f'{PREFIX}/search_v1/evidence/{pool}.json')
            valid_raw = {}
            for key in entries:
                if not key.startswith(f'{PREFIX}/public/holdings/{pool}/') or key.endswith('/latest.json'):
                    continue
                record = read(key)
                if (not record.get('collection_error') and record.get('data_status') == 'ok'
                        and record.get('collection_complete') and record.get('rows')
                        and record['trade_date'] <= evidence['last_local_date']
                        and record['signal_trade_date'] in available_dates):
                    valid_raw[record['trade_date']] = record
            audited = {r['trade_date']: r for r in team['dates']}
            assert valid_raw.keys() == audited.keys(), (pool, 'raw date coverage')
            dates_checked += len(valid_raw)
            for day, row in valid_raw.items():
                assert row['active_factor_count'] == audited[day]['public_count']
                e = next(r for r in evidence['records'] if r['trade'] == day)
                assert e['rows'] == row['rows'], (pool, day, 'evidence/raw holding disagreement')
            segdates = [d for s in team['segments'] for d in s['dates']]
            assert sorted(segdates) == sorted(valid_raw), 'missing or repeated segment date'
            checks = read(f'{PREFIX}/search_v1/peers_v5_Broster/{pool}/verified_best.json')['checks']
            original_mean = sum(c['overlap'] for c in checks) / len(checks)
            segment_mean = sum(s['mean_overlap'] * s['scored_snapshots'] for s in team['segments']) / len(checks)
            assert abs(original_mean - segment_mean) < 1e-12
    for kind in ['chen', 'yi']:
        d = json.loads((OUT / (kind + '_fixed_roster_diagnostics.json')).read_text())
        assert d['baseline_replay_matches'] and d['formula_changes'] == d['direction_changes'] == 0
        base = d['baseline']['path']
        for c in d['scenarios']:
            for i, row in enumerate(c['path']):
                if kind == 'chen':
                    assert row['active_count'] == (4 if i < 2 else 5)
                    if i >= 2:
                        assert row == base[i], 'post-change dates must remain unchanged'
                elif i:
                    assert row == base[i], 'only first date may change'
    result = dict(archived_files_hash_verified=verified_files, teams_checked=len(teams),
        raw_complete_dates_independently_checked=dates_checked,
        raw_holdings_match_extracted_evidence=True, all_raw_dates_retained=True,
        segment_dates_unique_and_exhaustive=True, segment_means_restore_frozen_results=True,
        unchanged_scenario_dates_identical=True, platform_compute=0)
    (OUT / 'frozen_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
