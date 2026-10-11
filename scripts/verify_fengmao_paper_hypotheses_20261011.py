from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import fengmao_paper_hypotheses_20261011 as task

ROOT = task.ROOT
OUT = task.OUT


def independent_periods(signal, y, cap, dates):
    rows = []
    held_prev = None
    for i, date in enumerate(dates):
        ok = np.isfinite(signal[i]) & np.isfinite(y[i]) & np.isfinite(cap[i])
        f = pd.DataFrame({'signal': signal[i, ok], 'label': y[i, ok], 'cap': cap[i, ok]},
                         index=np.flatnonzero(ok))
        rank_ic = f.signal.corr(f.label, method='spearman')
        pearson = f.signal.corr(f.label)
        order = f.signal.sort_values(kind='stable').index.to_numpy()
        held = order[np.ceil(np.arange(1, len(order)+1)*10/len(order)).astype(int) == 10]
        gross = float(f.loc[held, 'label'].mean() - f.label.mean())
        turnover = np.nan if held_prev is None else 1-len(set(held)&held_prev)/len(held)
        rows.append(dict(date=str(pd.Timestamp(date).date()), rank_ic=rank_ic, ic=pearson,
                         gross_excess=gross, turnover=turnover))
        held_prev = set(held)
    p = pd.DataFrame(rows)
    # The production metric leaves the first period undefined because no
    # prior portfolio exists; preserve NaN for an exact comparison.
    return p


def main():
    protocol = json.loads((OUT/'protocol.json').read_text(encoding='utf8'))
    frozen = json.loads((OUT/'frozen_candidates.json').read_text(encoding='utf8'))['candidates']
    results = pd.read_csv(OUT/'results.csv')
    atoms0, y0, cap0, dates, _ = task.shared.prior.load('formal')
    with np.load(task.SRC/'atoms.npz') as z:
        atoms = {k: z[k] for k in z.files if k not in ('target', 'market_cap')}
    assert len(dates) == 120 and not protocol['final_used_for_selection']
    cand_map = {c['name']: c for c in task.build_candidates(atoms)}
    checks = [dict(check='final_holdout_not_used_for_selection', passed=True,
                   final_dates=protocol['final_dates'])]
    errors = []
    for item in frozen:
        original = cand_map[item['formula']]
        rebuilt = original['fn']()
        rebuilt[~np.isfinite(cap0)] = np.nan
        cached = np.load(OUT/(item['name']+'_formal_signals.npy'), mmap_mode='r')
        diff = float(np.nanmax(np.abs(rebuilt-cached)))
        assert diff < 1e-7, (item['name'], diff)
        checks.append(dict(check='frozen_formula_rebuild', candidate=item['name'], passed=True,
                           max_difference=diff))
        for window, mask in [('formal_5y', np.ones(len(dates), dtype=bool)),
                             ('historical_final', dates >= task.FINAL_START),
                             ('recent_2026', dates >= pd.Timestamp('2026-01-01'))]:
            p = independent_periods(cached[mask], y0[mask], cap0[mask], dates[mask])
            saved = pd.read_csv(OUT/f'{item["name"]}_{window}_periods.csv')
            assert p.date.tolist() == saved.date.tolist()
            for col in ('rank_ic', 'ic', 'gross_excess', 'turnover'):
                e = float(np.nanmax(np.abs(p[col].to_numpy()-saved[col].to_numpy())))
                assert e < 1e-7, (item['name'], window, col, e)
            rank_ic = float(p.rank_ic.mean())
            rank_ir = rank_ic / float(p.rank_ic.std(ddof=0))
            wins = int((p.rank_ic > .02).sum())
            row = results[(results.candidate == item['name']) & (results.window == window)].iloc[0]
            assert abs(rank_ic-float(row.rank_ic)) < 1e-8
            assert abs(rank_ir-float(row.rank_ir)) < 1e-8
            assert wins == int(row.wins)
            errors.append(dict(candidate=item['name'], window=window,
                               rank_ic=rank_ic, rank_ir=rank_ir, wins=wins))
    report = dict(status='passed', checks=checks, metric_windows=len(errors),
                  scope='independent pandas rank/period audit; final block frozen before evaluation',
                  opponent_exact_recovery_verified=False)
    (OUT/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    pd.DataFrame(errors).to_csv(OUT/'independent_metrics.csv', index=False)
    print(f'paper hypotheses: {len(errors)} windows independently verified', flush=True)


if __name__ == '__main__':
    main()
