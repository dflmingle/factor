"""Frozen public leaderboard references; no network or platform mutations."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / 'public' / 'boards'
CORE = ('rex', 'quality', 'robust', 'points')
DEFINITIONS = {
    'rex': 'arithmetic mean of each valid month separately annualized net excess',
    'quality': 'mean monthly Na plus mean monthly Nb',
    'robust': 'mean monthly SR minus twice the worst monthly MaxDD',
    'points': 'sum valid monthly points; no annual A/B/C recomputation',
}


def public_reference(pool_id):
    result = {}
    for path in sorted(PUBLIC.glob('*.json')):
        source = json.loads(path.read_text())
        row = next((x for x in source.get('rows', []) if x['pool_id'] == pool_id), None)
        result[path.stem] = dict(
            scope='formula outcome target' if path.stem in CORE else 'context only',
            definition=DEFINITIONS.get(path.stem),
            snapshot={k:source.get(k) for k in ('ranking_snapshot_id', 'period',
                'snapshot_type', 'data_cutoff_at', 'published_at', 'formula_version')},
            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            present=row is not None, rank=row.get('rank') if row else None,
            score=row.get('score') if row else None,
            metrics=row.get('metrics') if row else None)
    return result


def candidate_comparison(candidate, source):
    public = public_reference(candidate['target']['pool_id'])
    comparisons = {}
    for board in CORE:
        local = candidate.get('boards', {}).get(board, {}).get('local')
        target = public[board]['score']
        comparisons[board] = dict(public[board], local=local,
            absolute_delta=local-target if local is not None and target is not None else None,
            relative_error=abs(local-target)/max(abs(target), 1e-8)
                if local is not None and target is not None else None)
    # Auxiliary metrics are derived from the SAME candidate monthly ledger.
    months = candidate.get('months', [])
    mean_sr = sum(m['annual_sr'] for m in months)/len(months) if months else None
    worst_dd = max((m['max_dd'] for m in months), default=None)
    return dict(target=candidate['target'], candidate_source=str(source),
        candidate_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        passed=candidate.get('acceptance', {}).get('passed', False),
        acceptance=candidate.get('acceptance'), core_boards=comparisons,
        auxiliary=dict(mean_monthly_SR=mean_sr, worst_monthly_MaxDD=worst_dd),
        monthly_ledger=[{k:m.get(k) for k in ('period', 'annual_rex', 'annual_sr',
            'max_dd', 'turn', 'raw_a', 'raw_b', 'raw_c', 'na', 'nb', 'nc', 'points')}
            for m in months],
        context_boards={k:v for k,v in public.items() if k not in CORE},
        warnings=['Derived boards reuse monthly evidence; not independent validation.',
                  'Rank is public reference only; local candidate rank is not inferred.',
                  'Clipped scores cannot establish formula identity.',
                  'Saved public cutoff is frozen; no newer dates mixed into this comparison.'])


def main():
    out = HERE / 'all_board_reference_v1'
    out.mkdir(exist_ok=True)
    variants = {}
    for dirname in ('peers_v5_Broster', 'residual_refinement_v1', 'seven_methods_v1'):
        for source in (HERE / dirname).glob('*/verified_best.json'):
            candidate = json.loads(source.read_text())
            pool = candidate['target']['pool_id']
            variants.setdefault(pool, []).append(candidate_comparison(candidate, source))
    summary = []
    for pool, records in variants.items():
        target = records[0]['target']
        (out / f'{pool}.json').write_text(json.dumps(dict(target=target,
            candidates=records), ensure_ascii=False, indent=2) + '\n')
        for record in records:
            summary.append(dict(rank=target['rank'], name=target['display_name'],
                source=record['candidate_source'], passed=record['passed'],
                boards={k:dict(rank=v['rank'], public=v['score'], local=v['local'],
                    relative_error=v['relative_error']) for k,v in record['core_boards'].items()}))
    manifest = dict(updated_at=datetime.now(timezone.utc).isoformat(), pools=len(variants),
        candidates=len(summary), rows=summary, platform_compute=0)
    (out / 'summary.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    lines=['# 各榜同候选对照', '',
        '同一候选分别核对超额、质量、稳健和积分榜。不同候选不拼接最优指标；所有公开快照日期保留在逐队JSON。', '',
        '|积分名次|队伍|候选来源|超额榜误差|质量榜误差|稳健榜误差|积分榜误差|',
        '|---:|---|---|---:|---:|---:|---:|']
    for row in sorted(summary, key=lambda x:(x['rank'],x['source'])):
        values=[]
        for k in CORE:
            value=row['boards'][k]['relative_error']
            values.append(f'{value:.3%}' if value is not None else '缺证据')
        src=Path(row['source']).parents[1].name
        lines.append(f"|{row['rank']}|{row['name']}|{src}|"+'|'.join(values)+'|')
    lines.extend(['', '勤劳、校园、幸运和跃升榜为参考背景；无因子可重算指标时不纳入公式拟合。',
        '分榜由同一月度数据派生，不算新增独立样本；积分封顶接近不能替代逐期IC/RankIC和持仓验收。'])
    (out / 'README.md').write_text('\n'.join(lines)+'\n')
    print('Exported',len(variants),'pools,',len(summary),'separate candidate comparisons')


if __name__ == '__main__':
    main()
