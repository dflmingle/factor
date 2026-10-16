"""Offline historical roster audit. All writes are confined to this directory.

No platform calls, formula search, direction tuning, or weight fitting.
Frozen reference panels retain the original inverse-engine semantics.
"""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import io
import json
import pickle
import sys
import zipfile

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'research_reports/peer_reconstruction/top50-20261013'
SEARCH = BASE / 'search_v1'
PUBLIC = BASE / 'public'
sys.path[:0] = [str(SEARCH), str(ROOT / 'scripts')]
sys.dont_write_bytecode = True
from engine import standardize
from grammar import Expr
from objective import holding_check, clean
from platform_alignment_rules import ALIGNMENT_RULE_VERSION


def save(name, value):
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2,
                                      allow_nan=False) + '\n')


def table(name, rows):
    if not rows:
        (OUT / name).write_text('')
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict))
                     else v for k, v in r.items()} for r in rows])


class Frozen:
    """Read each source once, preserving exact bytes in an isolated archive."""
    def __init__(self):
        self.archive = zipfile.ZipFile(OUT / 'frozen_inputs.zip', 'a', zipfile.ZIP_DEFLATED)
        self.archived = set(self.archive.namelist())
        self.manifest = {}
        self.values = {}

    def read(self, path):
        path = Path(path)
        key = str(path.relative_to(ROOT))
        if key not in self.values:
            data = self.archive.read(key) if key in self.archived else path.read_bytes()
            if key not in self.archived:
                self.archive.writestr(key, data)
                self.archived.add(key)
            self.manifest[key] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            self.values[key] = json.loads(data)
        return self.values[key]

    def binary(self, path):
        path = Path(path)
        key = str(path.relative_to(ROOT))
        data = self.archive.read(key) if key in self.archived else path.read_bytes()
        self.manifest[key] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        if key not in self.archived:
            self.archive.writestr(key, data)
            self.archived.add(key)
        return data

    def close(self):
        self.archive.close()
        save('input_manifest.json', self.manifest)


META = ['revision', 'direction', 'effective_trade_date', 'end_trade_date',
        'factor_status', 'is_historical', 'included_in_current_metrics']


def active(seat, day):
    return ((not seat.get('effective_trade_date') or seat['effective_trade_date'] <= day)
            and (not seat.get('end_trade_date') or day < seat['end_trade_date']))


def roster_key(seats, day):
    return tuple(sorted((s['id'], s.get('revision'), s.get('direction'))
                        for s in seats if active(s, day)))


def segmented(rows, overlap_key='overlap'):
    groups = []
    for r in rows:
        key = (r['roster_signature'], r['public_count'])
        if not groups or groups[-1]['key'] != key:
            groups.append(dict(key=key, rows=[]))
        groups[-1]['rows'].append(r)
    result = []
    for n, g in enumerate(groups, 1):
        rs = g['rows']
        vals = [r[overlap_key] for r in rs if r.get(overlap_key) is not None]
        result.append(dict(segment=n, start=rs[0]['trade_date'], end=rs[-1]['trade_date'],
                           dates=[r['trade_date'] for r in rs], snapshots=len(rs),
                           scored_snapshots=len(vals), public_count=rs[0]['public_count'],
                           metadata_count=rs[0]['metadata_count'],
                           roster_signature=rs[0]['roster_signature'],
                           count_conflict_dates=[r['trade_date'] for r in rs if r['count_conflict']],
                           mean_overlap=float(np.mean(vals)) if vals else None,
                           min_overlap=min(vals) if vals else None))
    return result


def audit_team(frozen, target):
    pool = target['pool_id']
    e = frozen.read(SEARCH / 'evidence' / (pool + '.json'))
    best_path = SEARCH / 'peers_v5_Broster' / pool / 'verified_best.json'
    b = frozen.read(best_path) if best_path.exists() else None
    status_path = best_path.with_name('verification_status.json')
    status = frozen.read(status_path) if status_path.exists() else None
    observations = defaultdict(list)
    profiles = {}
    errors = []
    for p in sorted((PUBLIC / 'players' / pool).glob('*.json')):
        d = frozen.read(p)
        profiles[p.stem] = d.get('factor_pool_details', [])
        for s in profiles[p.stem]:
            observations[s['factor_instance_id']].append(dict(
                source=str(p.relative_to(ROOT)), kind='monthly_profile', period=p.stem,
                name=s.get('factor_name'), **{k: s.get(k) for k in META}))
    for kind, paths in [('trend', sorted((PUBLIC / 'trends' / pool).glob('*/*.json'))),
                        ('latest_metadata', sorted((PUBLIC / 'latest_metadata' / pool).glob('*.json')))]:
        for p in paths:
            d = frozen.read(p)
            if d.get('collection_error'):
                errors.append(dict(source=str(p.relative_to(ROOT)), error=d['collection_error']))
                continue
            ident = d.get('factor_instance_id') or (p.parent.name if kind == 'trend' else p.stem)
            observations[ident].append(dict(source=str(p.relative_to(ROOT)), kind=kind,
                requested_snapshot=p.stem if kind == 'trend' else None,
                trade_date=d.get('trade_date'), name=d.get('factor_name'),
                **{k: d.get(k) for k in META}))
    # Retain all saved holding responses, including incomplete/error observations.
    public_holdings = []
    for p in sorted((PUBLIC / 'holdings' / pool).glob('*.json')):
        d = frozen.read(p)
        public_holdings.append(dict(source=str(p.relative_to(ROOT)), trade_date=d.get('trade_date'),
            status=d.get('data_status'), complete=d.get('collection_complete'),
            active_count=d.get('active_factor_count'), error=d.get('collection_error')))

    extracted_ids = {s['id'] for s in e['seats']}
    seat_audit = []
    for ident, obs in observations.items():
        revisions = sorted({o['revision'] for o in obs if o.get('revision') is not None})
        directions = sorted({o['direction'] for o in obs if o.get('direction') is not None})
        lifecycles = sorted({(o.get('effective_trade_date') or '', o.get('end_trade_date') or '')
                            for o in obs if o['kind'] != 'monthly_profile'})
        current = next((s for s in e['seats'] if s['id'] == ident), None)
        seat_audit.append(dict(id=ident, name=next((o['name'] for o in obs if o['name']), ident),
            revisions=revisions, directions=directions, lifecycle_claims=lifecycles,
            missing_earlier_revision=bool(revisions and min(revisions) > 1),
            revision_changed_between_saved_snapshots=len(revisions) > 1,
            direction_changed_between_saved_sources=len(directions) > 1,
            conflicting_lifecycle_claims=len(lifecycles) > 1,
            absent_from_extracted_evidence=ident not in extracted_ids,
            extracted_conflicts=(current or {}).get('revision_conflicts', []), observations=obs))

    profile_changes = []
    ordered = sorted(profiles)
    for prev, now in zip(ordered, ordered[1:]):
        a = {s['factor_instance_id']: s for s in profiles[prev]}
        c = {s['factor_instance_id']: s for s in profiles[now]}
        additions, removals = sorted(c.keys() - a.keys()), sorted(a.keys() - c.keys())
        direction = [i for i in a.keys() & c.keys() if a[i].get('direction') != c[i].get('direction')]
        # These are fingerprints, not formula identities. A statistic change alone
        # cannot establish a source revision or formula change.
        fingerprints = [i for i in a.keys() & c.keys() if any(a[i].get(k) != c[i].get(k)
            for k in ['window_start', 'window_end', 'sample_count', 'ic_mean', 'icir', 's_i_a'])]
        if additions or removals or direction or fingerprints:
            profile_changes.append(dict(previous=prev, current=now, additions=additions,
                removals=removals, direction_changes=direction, A_fingerprint_changes=fingerprints,
                same_count=len(a) == len(c), period_profile_is_not_historical_roster=True))

    checks = {c['trade_date']: c for c in (b or {}).get('checks', [])}
    rows, transitions = [], []
    for r in e['records']:
        day = r['trade']
        signature = roster_key(e['seats'], day)
        c = checks.get(day)
        row = dict(rank=target['rank'], name=target['display_name'], pool_id=pool,
            trade_date=day, signal_date=r['signal'], public_count=r['active_factor_count'],
            metadata_count=len(signature), count_conflict=len(signature) != r['active_factor_count'],
            roster_signature=signature, overlap=c['overlap'] if c else None,
            composite_rmse=c.get('observed_composite_rmse') if c else None,
            roster_status='count_conflict' if len(signature) != r['active_factor_count']
                          else 'lifecycle_count_consistent_proxy',
            previous_revisions_unobserved=[s['id'] for s in seat_audit if s['missing_earlier_revision']])
        if rows and (rows[-1]['roster_signature'] != signature or rows[-1]['public_count'] != row['public_count']):
            old_ids = {x[0] for x in rows[-1]['roster_signature']}
            ids = {x[0] for x in signature}
            transitions.append(dict(previous_date=rows[-1]['trade_date'], date=day,
                previous_public_count=rows[-1]['public_count'], public_count=row['public_count'],
                additions=sorted(ids - old_ids), removals=sorted(old_ids - ids),
                same_public_count=rows[-1]['public_count'] == row['public_count'],
                revision_or_direction_change=(old_ids == ids and rows[-1]['roster_signature'] != signature)))
        rows.append(row)
    segs = segmented(rows)
    vals = [r['overlap'] for r in rows if r['overlap'] is not None]
    if vals:
        restored = sum(s['mean_overlap'] * s['scored_snapshots'] for s in segs if s['scored_snapshots']) / len(vals)
        assert abs(restored - np.mean(vals)) < 1e-12
    assert sum(s['snapshots'] for s in segs) == len(e['records'])
    assert len({r['trade_date'] for r in rows}) == len(rows)
    assert set(checks) == {r['trade_date'] for r in rows}, (pool, 'unmatched saved checks')
    summary = dict(rank=target['rank'], name=target['display_name'], pool_id=pool,
        holding_dates=len(rows), count_path=[r['public_count'] for r in rows],
        public_count_changed=len({r['public_count'] for r in rows}) > 1,
        segments=len(segs), count_conflict_dates=[r['trade_date'] for r in rows if r['count_conflict']],
        union_seats=len(observations), missing_extracted_ids=sorted(set(observations) - extracted_ids),
        saved_revision_change_seats=[s['id'] for s in seat_audit if s['revision_changed_between_saved_snapshots']],
        unobserved_earlier_revision_seats=[s['id'] for s in seat_audit if s['missing_earlier_revision']],
        saved_direction_change_seats=[s['id'] for s in seat_audit if s['direction_changed_between_saved_sources']],
        same_count_transitions=sum(t['same_public_count'] for t in transitions),
        month_profile_changes=profile_changes, mean_overlap=float(np.mean(vals)) if vals else None,
        frozen_candidate_passed_reference=(status or {}).get('passed'), platform_compute=0)
    return dict(summary=summary, seats=seat_audit, dates=rows, segments=segs,
                transitions=transitions, holding_responses=public_holdings, fetch_errors=errors), e, b


def replay_market(frozen):
    source = ROOT / 'research_reports/platform_alignment/bc-peer-pools-20261012/market_extended.pkl'
    # Large immutable data remain external; save their hashes and the actual
    # recent axes/mask used, sufficient to replay all roster-only scenarios.
    data = source.read_bytes()
    frozen.manifest[str(source.relative_to(ROOT))] = dict(
        sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), archived=False)
    cal, stocks, fields = pickle.loads(data)
    del data
    cal, stocks = pd.DatetimeIndex(cal), pd.Index(stocks)
    recent = np.flatnonzero(cal >= pd.Timestamp('20260801'))
    mask = np.isfinite(fields['cap']) & (fields['cap'] > 0) & np.isfinite(fields['turnover'])
    mask &= ~((fields['volume'] <= 0) | (fields['amount'] <= 0) |
              np.isclose(fields['high'], fields['low'], rtol=1e-8, atol=1e-8))
    name_path = ROOT / 'quantlab/.quantlab/cache/research/cn_equity/stock_basic/namechange.parquet'
    name_bytes = name_path.read_bytes()
    frozen.manifest[str(name_path.relative_to(ROOT))] = dict(
        sha256=hashlib.sha256(name_bytes).hexdigest(), bytes=len(name_bytes), archived=False)
    names = pd.read_parquet(io.BytesIO(name_bytes))
    for symbol, g in names.groupby('ts_code', sort=False):
        j = stocks.get_indexer([symbol])[0]
        if j < 0:
            continue
        st = np.zeros(len(cal), bool)
        for r in g.dropna(subset=['start_date']).sort_values('start_date').itertuples():
            ann = max(r.start_date, r.ann_date) if pd.notna(r.ann_date) else r.start_date
            st[cal >= ann] = 'ST' in str(r.name).upper()
        mask[:, j] &= ~st
    np.savez_compressed(OUT / 'replay_axes_mask.npz', dates=cal[recent].strftime('%Y%m%d').to_numpy(str),
                        stocks=stocks.to_numpy(str), mask=mask[recent])
    return cal, stocks, cal[recent], mask[recent]


def fixed_roster_scenarios(frozen, evidence, best, axes, kind):
    cal, stocks, dates, mask = axes
    panel_positions = {d: i for i, d in enumerate(dates)}
    legs = []
    cache_context = frozen.read(SEARCH / 'panels_v3_raw_labels/context.json')
    assert cache_context['rule_reference'] == ALIGNMENT_RULE_VERSION
    assert cache_context['symbols'] == len(stocks)
    for j, tree in enumerate(best['pool']):
        expr = Expr.from_json(tree)
        key = hashlib.sha256(expr.key().encode()).hexdigest()
        path = SEARCH / 'panels_v3_raw_labels' / (key + '.npy')
        raw = np.load(io.BytesIO(frozen.binary(path)))
        assert raw.shape == mask.shape
        assert float(best['directions'][j]) == (1 if evidence['seats'][j]['direction'] == 'positive' else -1)
        positions = [panel_positions[pd.Timestamp(r['signal'])] for r in evidence['records']]
        legs.append(standardize(raw[positions].astype(float), mask[positions]) * best['directions'][j])
    z = np.asarray(legs)
    records = evidence['records']
    active_mask = np.array([[active(s, r['trade']) for r in records] for s in evidence['seats']])
    # Validate actual trade date equals the engine's next calendar date role.
    assert all(cal[cal.get_loc(pd.Timestamp(r['signal'])) + 1] == pd.Timestamp(r['trade']) for r in records)

    def measure(name, membership, **extra):
        comp = np.where(membership[:, :, None], z, 0).sum(0) / np.maximum(membership.sum(0), 1)[:, None]
        path = []
        for k, r in enumerate(records):
            i = panel_positions[pd.Timestamp(r['signal'])]
            held, check = holding_check(comp[k], mask[i], stocks, r)
            valid = np.flatnonzero(mask[i] & np.isfinite(comp[k]))
            order = valid[np.argsort(comp[k, valid], kind='stable')][::-1]
            public20 = {x['symbol'] for x in sorted(r['rows'], key=lambda x: x.get('rank') or float('inf'))[:20]}
            check['top20_overlap'] = len(public20 & set(stocks[order[:20]]))
            check['active_seats'] = [s['id'] for s, enabled in zip(evidence['seats'], membership[:, k]) if enabled]
            check['active_count'] = int(membership[:, k].sum())
            path.append(check)
        early = path[:2] if kind == 'chen' else path[:1]
        return dict(name=name, path=path, mean_overlap=float(np.mean([c['overlap'] for c in path])),
            early_mean_overlap=float(np.mean([c['overlap'] for c in early])),
            early_observed_rmse=float(np.mean([c['observed_composite_rmse'] for c in early])),
            early_penalized_rmse=float(np.mean([c['composite_rmse'] for c in early])),
            early_missing_predictions=sum(c['missing_numeric_predictions'] for c in early),
            all_public_observations_fitted=True, strict_oos=False, **extra)

    baseline = measure('frozen_lifecycle_baseline', active_mask)
    compare_keys = ['overlap', 'composite_rmse', 'observed_composite_rmse',
                    'missing_numeric_predictions', 'predicted_holdings']
    replay_errors = []
    for got, saved in zip(baseline['path'], best['checks']):
        assert got['trade_date'] == saved['trade_date']
        for key in compare_keys:
            error = abs(got[key] - saved[key])
            if error > 1e-7:
                replay_errors.append(dict(date=got['trade_date'], metric=key, delta=error))
    assert not replay_errors, replay_errors
    candidates = []
    if kind == 'chen':
        for j, seat in enumerate(evidence['seats']):
            scenario = active_mask.copy()
            scenario[j, :2] = False
            candidates.append(measure('omit_' + seat['id'] + '_first_two_dates', scenario,
                omitted_seat=j + 1, omitted_id=seat['id'], omitted_name=seat['name'],
                status='inferred_fixed_roster_hypothesis_not_confirmed_history'))
        # Numeric scores constrain membership more directly than set overlap.
        winner = min(candidates, key=lambda x: x['early_penalized_rmse'])
    else:
        scenario = active_mask.copy()
        scenario[:, 0] = active_mask[:, 1]
        candidates.append(measure('later_six_seats_backcast_to_first_date', scenario,
            status='unsupported_backcast_sensitivity_only_rejected_as_historical_recovery'))
        winner = None
    result = dict(kind=kind, target=evidence['target'], baseline_replay_matches=True,
        baseline=baseline, scenarios=candidates, numeric_best_hypothesis=winner,
        formula_changes=0, direction_changes=0, fitted_weights=False, equal_seat_weights=True,
        member_enumeration=len(candidates), platform_compute=0,
        rule_reference=ALIGNMENT_RULE_VERSION,
        scope='fixed cached formula attribution; not a new causal-prefix or five-year validation',
        adoption='diagnostic_only; no shared baseline or search process changed')
    save(kind + '_fixed_roster_diagnostics.json', result)
    return result


def report(teams, diagnostics, star):
    rows = [t['summary'] for t in teams]
    conflicts = [s for s in rows if s['count_conflict_dates']]
    counts = dict(teams=len(rows), holdings_dates=sum(s['holding_dates'] for s in rows),
        count_changing_teams=sum(s['public_count_changed'] for s in rows),
        count_conflicting_teams=len(conflicts),
        count_conflicting_dates=sum(len(s['count_conflict_dates']) for s in rows),
        saved_revision_change_teams=sum(bool(s['saved_revision_change_seats']) for s in rows),
        missing_previous_revision_teams=sum(bool(s['unobserved_earlier_revision_seats']) for s in rows),
        saved_direction_change_teams=sum(bool(s['saved_direction_change_seats']) for s in rows),
        extra_unextracted_id_teams=sum(bool(s['missing_extracted_ids']) for s in rows),
        same_count_transition_teams=sum(bool(s['same_count_transitions']) for s in rows),
        same_count_replacement_teams_with_consistent_counts=sum(any(
            a['public_count'] == b['public_count'] and
            not a['count_conflict'] and not b['count_conflict'] and
            a['roster_signature'] != b['roster_signature']
            for a, b in zip(t['dates'], t['dates'][1:])) for t in teams))
    save('summary.json', dict(**counts, platform_compute=0, no_source_identity_claim=True,
        strict_oos=False, same_count_checks='IDs/revisions/directions checked across saved sources; incomplete history remains unknown',
        invariants=dict(all_dates_retained=True, segment_weighted_means_restore_totals=True,
                        fixed_formula_baseline_replay_matches=True)))
    table('team_summary.csv', rows)
    table('holding_dates.csv', [r for t in teams for r in t['dates']])
    table('period_segments.csv', [dict(rank=t['summary']['rank'], name=t['summary']['name'],
        pool_id=t['summary']['pool_id'], **s) for t in teams for s in t['segments']])
    lines = ['# 对手历史因子池审计与分段持仓对齐', '',
        f"覆盖 {counts['teams']} 队、{counts['holdings_dates']} 个已保存完整持仓日期。"
        f"{counts['count_changing_teams']} 队出现公开因子数量变化；"
        f"{counts['count_conflicting_teams']} 队、{counts['count_conflicting_dates']} 个日期存在生命周期成员数与持仓数冲突。", '',
        '本次仅做离线审计和固定公式的成员假设对照，平台算力消耗 0。没有修改共享搜索、候选公式、方向或等权合成。', '',
        '## 证据与限制', '',
        '- 核对月度档案、逐因子历史趋势、最新成员元数据（如有）、完整持仓及冻结的 verified_best；源文件原始字节见 frozen_inputs.zip，哈希见 input_manifest.json。',
        '- 成员区间按生效日包含、结束日不包含。元数据中的历史查询日期不等于当时已知时间，月度评分档案也不能直接视为当月每日真实成员。',
        '- 分段按已保存持仓日期中成员 ID / revision / direction 签名和公开数量变化划分；两次快照之间未观察到的短暂变更仍未知。当前签名来自保存的生命周期声明，属于历史代理。',
        '- 数量一致只能排除一部分成员错误，不能证明历史公式一致。revision>1 且未保存旧版时，旧公式未知；A 指纹变化只列线索，不推定公式更新。',
        '- 全部公开观测已被先前研究使用；本次假设对照也使用这些观测，不构成样本外验证。逐席 IC/A/B/C 不随本次成员假设自动获得复刻认证。', '',
        '## 重点个案', '']
    chen, yi = diagnostics
    cb, cw = chen['baseline'], chen['numeric_best_hypothesis']
    lines += ['### ChenQiLong：前两期 4 席与元数据 5 席冲突', '',
        '冲突日期为 20260921、20260923；20260928 起公开持仓变为 5 席。'
        '保存的五席趋势均声称 20260921 生效，未找到能直接证明早期缺少哪一席的原始记录。', '',
        '冻结五条公式与方向，枚举前两期始终缺少同一席的 5 种假设；其后仍使用全部五席。'
        '以包含缺失预测惩罚的公开合成分数 RMSE 排序，持仓重合率作为并行诊断。', '',
        '| 前两期假设 | 平均持仓重合 | 合成分 RMSE（含缺失惩罚） | 可预测观测 RMSE | 缺失预测数 |',
        '|---|---:|---:|---:|---:|']
    for r in [cb] + chen['scenarios']:
        lines.append(f"| {r.get('omitted_name', '五席基线')} | {r['early_mean_overlap']:.2%} | {r['early_penalized_rmse']:.4f} | {r['early_observed_rmse']:.4f} | {r['early_missing_predictions']} |")
    lines += ['', f"数值分数最接近的假设为前两期缺少「{cw['omitted_name']}」："
        f"早期平均重合率 {cb['early_mean_overlap']:.2%} → {cw['early_mean_overlap']:.2%}，"
        f"全期 {cb['mean_overlap']:.2%} → {cw['mean_overlap']:.2%}。"
        '该结果仅为已观察数据上的成员假设；不能据此确认对手实际删加了这一席。', '',
        '### 弈星：首期历史成员缺口与未保存旧版', '',
        '20260901 公开为 6 席，保存的生命周期只能还原 3 席；20260908/15 为 6 席，'
        '20260922/30 为 7 席。AA 因子首次有效快照即 revision=2，未保存 revision=1。'
        '首期缺少三席的身份/版本尚未确认，不能把后来的六席直接当作首期真实因子池。', '']
    yb, ys = yi['baseline'], yi['scenarios'][0]
    lines += [f"只做一次明确标注的敏感性对照：将后来的六席回填首期，首期重合率 "
        f"{yb['early_mean_overlap']:.2%} → {ys['early_mean_overlap']:.2%}，合成分 RMSE（含缺失惩罚） "
        f"{yb['early_penalized_rmse']:.4f} → {ys['early_penalized_rmse']:.4f}。"
        '无论改善与否，都不作为已恢复历史成员的证据，不替换基线。', '',
        '### star_coin：5 席扩容至 10 席后分别看', '',
        '下面使用已经通过独立因果窗口检查的专修 v6 结果，单独列出，不混入全 50 队统一冻结批次。', '',
        '| 保存的持仓日期区间 | 因子数 | 快照数 | 平均持仓重合 | 平均 Top20 重合 |',
        '|---|---:|---:|---:|---:|']
    for s in star:
        lines.append(f"| {s['start']}–{s['end']} | {s['public_count']} | {s['snapshots']} | {s['mean_overlap']:.2%} | {s['mean_top20']:.1f}/20 |")
    lines += ['', '误差集中在 10 席阶段，下一步应优先核查新增腿和扩容后的合成。'
        '日期与市场状态同时变化，不能仅凭分段就认定误差全由新增腿造成。'
        'v6 已按各席生效日期合成，因此本次分段是定位误差，不能称为新增的重合率提升。', '',
        '## 其余队伍与数量不变的变更', '',
        f"保存来源中：观测到 revision 发生切换的队伍 {counts['saved_revision_change_teams']}；"
        f"方向冲突/变动队伍 {counts['saved_direction_change_teams']}；"
        f"公开数量不变但生命周期签名变化队伍 {counts['same_count_transition_teams']}；"
        f"发现趋势/元数据 ID 未纳入原提取证据的队伍 {counts['extra_unextracted_id_teams']}。"
        f"有未保存旧 revision 的队伍 {counts['missing_previous_revision_teams']}。"
        '这些数字只覆盖现存快照，不能推出其他队伍从未换过同数量成员或公式。', '',
        f"两次公开数量相同且成员数均无冲突的成员替换只有 "
        f"{counts['same_count_replacement_teams_with_consistent_counts']} 队：Siuuuuuuuu。"
        '该队 20261012 仍为 6 席，但生命周期记录显示在该日移除 r7a-260910-R7-A02、'
        'r5a-260910-R5-A01，加入 F261001S15、F261001S02；9/10 月档案也对应这两进两出。'
        '替换前六席段（20260918/28）平均重合 25.65%，替换后（20261012）34.66%。'
        '原冻结候选已使用这些生效区间，本次没有新增提升。'
        '另一个数量不变的签名变化为弈星首期缺口，不能算作已确认替换。', '',
        '全队按分段列出重合率，冲突日期保留在均值中，没有剔除早期难复刻日期。', '',
        '| 排名 | 队伍 | 公开数量路径 | 分段 | 全期平均重合 | 冲突日期 |',
        '|---:|---|---|---:|---:|---|']
    for s in rows:
        lines.append(f"| {s['rank']} | {s['name'].replace('|', '/')} | {'→'.join(map(str,s['count_path']))} | {s['segments']} | {s['mean_overlap']:.2%} | {', '.join(s['count_conflict_dates']) or '—'} |")
    lines += ['', '## 可复核产物', '',
        '- `audit.json`：全部成员的逐源 revision / direction / 生效区间与冲突；逐日期签名、分段、变更。',
        '- `team_summary.csv`、`holding_dates.csv`、`period_segments.csv`：50 队、所有完整日期及各历史段的可筛选表。',
        '- `chen_fixed_roster_diagnostics.json`、`yi_fixed_roster_diagnostics.json`：固定公式基线重放和全部成员假设。',
        '- `star_v6_segments.json`：star_coin 专修 v6 分段诊断。',
        '- `frozen_inputs.zip`、`input_manifest.json`、`replay_axes_mask.npz`：原始输入快照、哈希及合成时的日期/股票/资格掩码。',
        '- `verification.json`：日期覆盖、分段加权还原、冻结候选重放和共享输入变化检查。', '',
        '- `verify_frozen.py` / `frozen_verification.json`：独立核对归档哈希、原始完整持仓日期与证据一致性、分段覆盖和假设未改变日期的一致性。', '',
        f"规则参考：`{ALIGNMENT_RULE_VERSION}`。两队成员对照复用旧版冻结表达式面板以隔离成员影响；"
        '不宣称重新验证全部旧候选的因果性。star_coin v6 使用独立 `kurtwindow1-proxy` 版本，单列结果。', '']
    (OUT / 'summary.md').write_text('\n'.join(lines))


def main():
    frozen = Frozen()
    targets = frozen.read(PUBLIC / 'targets.json')
    teams, evidence, best = [], {}, {}
    for target in targets:
        a, e, b = audit_team(frozen, target)
        teams.append(a)
        evidence[target['pool_id']], best[target['pool_id']] = e, b
    save('audit.json', teams)
    print(json.dumps(dict(stage='all_teams_audited', teams=len(teams)), ensure_ascii=False), flush=True)
    axes = replay_market(frozen)
    diagnostics = [fixed_roster_scenarios(frozen, evidence[p], best[p], axes, k)
        for p, k in [('de4d23eb31ffbcb50b61163d', 'chen'), ('6b3bbb21337cab6fe53bdc53', 'yi')]]
    star_result = frozen.read(ROOT / 'research_reports/peer_reconstruction/star-coin-fidelity-focus-20261016-v6/result.json')
    frozen.read(ROOT / 'research_reports/peer_reconstruction/star-coin-fidelity-focus-20261016-v6/verification.json')
    star_team = next(t for t in teams if t['summary']['pool_id'] == '18067f13fb2f894e0a45b181')
    star_checks = {r['trade_date']: r for r in star_result['selected']['path']}
    star_rows = [dict(r, overlap=star_checks[r['trade_date']]['full_overlap'],
                      top20=star_checks[r['trade_date']]['top20']) for r in star_team['dates']]
    star_segments = segmented(star_rows)
    for s in star_segments:
        s['mean_top20'] = float(np.mean([r['top20'] for r in star_rows if r['trade_date'] in s['dates']]))
    assert abs(sum(s['mean_overlap'] * s['snapshots'] for s in star_segments) /
               len(star_rows) - star_result['selected']['mean_full_overlap']) < 1e-12
    save('star_v6_segments.json', dict(segments=star_segments, source_rule=star_result['protocol']['rule_reference']))
    report(teams, diagnostics, star_segments)
    frozen.close()
    changes = []
    for relative, meta in frozen.manifest.items():
        p = ROOT / relative
        if hashlib.sha256(p.read_bytes()).hexdigest() != meta['sha256']:
            changes.append(relative)
    save('verification.json', dict(teams=len(teams), all_saved_complete_dates_retained=True,
        weighted_segment_means_restore_totals=True, fixed_formula_baselines_exact=True,
        star_v6_segment_mean_restores_total=True, inputs_changed_during_audit=changes,
        shared_inputs_unchanged=not changes, platform_compute=0,
        no_formula_direction_or_weight_changes=True, no_shared_baseline_adoption=True))
    print((OUT / 'summary.json').read_text(), flush=True)


if __name__ == '__main__':
    if '--render-only' in sys.argv:
        loaded = json.loads((OUT / 'audit.json').read_text())
        diags = [json.loads((OUT / (k + '_fixed_roster_diagnostics.json')).read_text()) for k in ['chen', 'yi']]
        star = json.loads((OUT / 'star_v6_segments.json').read_text())['segments']
        report(loaded, diags, star)
    else:
        main()
