"""Independently verify saved GP finalists and export decile/Top20 diagnostics."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_reports/platform_alignment/fengmao-group-gp-20261011'


def main():
    panels = np.load(OUT / 'atoms.npz')
    target, cap = panels['target'], panels['market_cap']
    axes = json.loads((OUT / 'axes.json').read_text(encoding='utf-8'))
    dates = pd.DatetimeIndex(axes['dates'])
    symbols = np.asarray(axes['symbols'])
    summaries = pd.read_csv(OUT / 'results.csv')
    windows = {'formal_5y': np.ones(len(dates), bool), 'training': dates <= '2023-12-29',
               'validation_2024_2025': (dates >= '2024-01-01') & (dates <= '2025-12-31'),
               'recent_2026': dates >= '2026-01-01'}
    groups, top, checked_periods, ic_delta = [], [], 0, 0.
    finalists = json.loads((OUT / 'frozen_finalists.json').read_text(encoding='utf-8'))
    registry = pd.read_csv(OUT / 'search_registry.csv')
    assert len(registry) <= 240 and registry.formula.is_unique
    assert len(finalists) == 3
    for ci in range(1, 4):
        name = f'FMGP{ci:02d}'
        values = np.load(OUT / f'{name}_signals.npy')
        assert values.shape == target.shape
        for i, date in enumerate(dates):
            ids = np.flatnonzero(np.isfinite(values[i]))
            order = pd.Series(values[i, ids], index=ids).sort_values(ascending=False, kind='stable')
            for rank, ident in enumerate(order.index[:20], 1):
                top.append(dict(candidate=name, date=str(date.date()), rank=rank,
                                instrument=symbols[ident], value=float(values[i, ident])))
        for window, mask in windows.items():
            persisted = pd.read_csv(OUT / f'{name}_{window}_periods.csv').set_index('date')
            previous = {}
            detail = []
            for i in np.flatnonzero(mask):
                valid = np.isfinite(values[i]) & np.isfinite(target[i]) & np.isfinite(cap[i])
                ids = np.flatnonzero(valid)
                x, y = pd.Series(values[i, ids], index=ids), pd.Series(target[i, ids], index=ids)
                day = str(dates[i].date())
                assert day in persisted.index
                ric, ic = x.corr(y, method='spearman'), x.corr(y)
                ic_delta = max(ic_delta, abs(ric - persisted.loc[day, 'rank_ic']), abs(ic - persisted.loc[day, 'ic']))
                assert abs(ric - persisted.loc[day, 'rank_ic']) < 1e-10
                assert abs(ic - persisted.loc[day, 'ic']) < 1e-10
                ranked = x.rank(method='first')
                deciles = np.ceil(ranked / len(x) * 10).clip(1, 10).astype(int)
                assert set(deciles) == set(range(1, 11))
                for group in range(1, 11):
                    selected = set(deciles.index[deciles.eq(group)])
                    turnover = np.nan if group not in previous else 1 - len(selected & previous[group]) / len(selected)
                    previous[group] = selected
                    gross = float(y.loc[list(selected)].mean() - y.mean())
                    row = dict(candidate=name, window=window, date=day, group=group,
                               stocks=len(selected), gross_excess=gross, turnover=turnover)
                    detail.append(row)
                    if group == 10:
                        assert abs(gross - persisted.loc[day, 'gross_excess']) < 1e-10
                        saved_turn = persisted.loc[day, 'turnover']
                        assert (np.isnan(turnover) and np.isnan(saved_turn)) or abs(turnover - saved_turn) < 1e-10
                checked_periods += 1
            assert len(persisted) == int(mask.sum())
            table = pd.DataFrame(detail)
            table.to_csv(OUT / f'{name}_{window}_group_periods.csv', index=False)
            for group, b in table.groupby('group'):
                turn = float(b.turnover.mean())
                gross = float(b.gross_excess.mean() * 25.2)
                net = gross - turn * .006 * 25.2
                groups.append(dict(candidate=name, window=window, group=int(group), gross_excess=gross,
                                   turnover=turn, net_excess=net))
                if group == 10:
                    saved = summaries[(summaries.candidate == name) & (summaries.window == window)].iloc[0]
                    assert abs(net - saved.net_excess) < 1e-10
    pd.DataFrame(groups).to_csv(OUT / 'deciles.csv', index=False)
    pd.DataFrame(top).to_csv(OUT / 'top20.csv', index=False)
    checks = json.loads((OUT / 'causality_checks.json').read_text(encoding='utf-8'))
    assert all(c['masks_equal'] and c['max_abs_difference'] == 0 and c['valid_cells'] > 0 for c in checks)
    result = dict(status='passed', summary_rows=len(summaries), stock_period_checks=checked_periods,
                  ic_max_delta=ic_delta, ten_groups_and_actual_membership=True,
                  independent_pandas_ic_and_turnover=True, initial_turnover_excluded_each_window=True,
                  arithmetic_net_and_cost=True, prefix_recomputed_cells=sum(c['valid_cells'] for c in checks),
                  unique_search_formulas=len(registry), valid_search_formulas=int(registry.status.eq('evaluated').sum()),
                  invalid_search_formulas=int(registry.status.eq('invalid').sum()),
                  correction_threshold_conservative=.05 / (240 + 3),
                  correction_scope='240 possible calls plus previous three fixed grpvol candidates; not a proof of OOS')
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
