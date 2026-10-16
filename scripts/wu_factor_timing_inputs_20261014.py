#!/usr/bin/env python3
"""Wu (2024) monthly portfolio method, with explicit Tushare field proxies.

This is a separate paper protocol, never a PandaAI alignment result. It does
not contact PandaAI, trade, or use future returns to select the stock universe.
"""
from __future__ import annotations
import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from regime_long_pit_fast_20261014 import replay
from platform_alignment_rules import ALIGNMENT_RULE_VERSION

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_reports/wu-factor-timing-v2-20261014'
LONG = ROOT / 'research_reports/platform_alignment/regime-long-history-20261014'
CACHE = ROOT / 'quantlab/.quantlab/cache/research/cn_equity'
VERSION = 'wu-monthly-size3-capweighted-tushare-proxy-v2'
KEYS = ['accruals_accruals', 'accruals_noas', 'illiquidity_illiquidity',
        'investment_annualassetgrowth', 'investment_quarterlyassetgrowth',
        'momentum_lagelemreturn', 'profitability_PMU', 'profitability_PMUTTM',
        'profitability_roe', 'reversal_onemonthreturn', 'size_mktcap',
        'turnover_onemabturnover', 'turnover_twelvemturnover',
        'value_bmratio', 'value_cpratio', 'value_epratio', 'volatility_MAX',
        'volatility_onemonthv', 'volatility_oneyearmv', 'volatility_sixmonthv',
        'volatility_threemonthv', 'volatility_threeyearmv',
        'volatility_twelvemonthv', 'volatility_twoyearmv']
LOW = {'accruals_accruals', 'accruals_noas', 'reversal_onemonthreturn',
       'size_mktcap', 'turnover_onemabturnover', 'turnover_twelvemturnover',
       *(k for k in KEYS if k.startswith('volatility_'))}

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''): h.update(b)
    return h.hexdigest()

def ratio(a, b):
    with np.errstate(divide='ignore', invalid='ignore'):
        x = np.asarray(a, float) / np.asarray(b, float)
    return np.where(np.isfinite(x) & (np.asarray(b) != 0), x, np.nan)

def narrow_financial(dates, stocks):
    """Announcement-ordered, consolidated, contiguous-quarter PIT snapshots."""
    path = OUT / 'financial_monthly.pkl'
    if path.exists():
        x = pd.read_pickle(path)
        if not x['dates'].equals(dates) or not x['stocks'].equals(stocks):
            raise ValueError('Incompatible financial cache')
        return x['fields']
    tables = pd.read_pickle(LONG / 'financial_pit_tables_long.pkl')
    wanted = {'balancesheet': ['total_assets', 'total_liab', 'money_cap',
              'total_hldr_eqy_exc_min_int', 'st_borr', 'lt_borr', 'bond_payable'],
              'income': ['revenue', 'oper_cost', 'n_income_attr_p'],
              'cashflow': ['n_cashflow_act'], 'fina_indicator': ['roe']}
    result = {}; checks = []
    for endpoint, cols in wanted.items():
        for lag in range(5):
            for c in cols:
                result[f'{endpoint}.{c}.{lag}'] = np.full((len(dates), len(stocks)), np.nan, np.float32)
                if endpoint in ('income', 'cashflow'):
                    result[f'{endpoint}.{c}_ttm.{lag}'] = np.full((len(dates), len(stocks)), np.nan, np.float32)
        for symbol, g in tables[endpoint].groupby('instrument', sort=False):
            j = stocks.get_indexer([symbol])[0]
            if j < 0: continue
            g = g.sort_values(['ann_date', 'end_date', 'update_flag'])
            ann = pd.DatetimeIndex(g.ann_date).asi8
            quarters = pd.PeriodIndex(g.end_date, freq='Q-DEC').asi8
            vals = g[cols].to_numpy(float)
            ttm = endpoint in ('income', 'cashflow')
            arr = replay(ann, quarters, vals, dates.asi8, 5, ttm)
            for lag in range(5):
                for cidx, c in enumerate(cols):
                    result[f'{endpoint}.{c}.{lag}'][:, j] = arr[:, lag, cidx, 0]
                    if ttm: result[f'{endpoint}.{c}_ttm.{lag}'][:, j] = arr[:, lag, cidx, 1]
            if sum(c['endpoint'] == endpoint for c in checks) < 3 and len(g) > 50:
                cut = len(dates) // 2; keep = ann <= dates[cut - 1].value
                if keep.any():
                    truncated = replay(ann[keep], quarters[keep], vals[keep], dates[:cut].asi8, 5, ttm)
                    np.testing.assert_allclose(truncated, arr[:cut], equal_nan=True)
                checks.append({'endpoint': endpoint, 'symbol': symbol, 'prefix_invariant': True})
        print('WU_PIT', endpoint, flush=True)
    pd.to_pickle(dict(dates=dates, stocks=stocks, fields=result), path)
    dump(OUT / 'financial_verification.json', checks)
    return result

def conditional_weights(score, cap, eligible, size_factor=False):
    """Three conditional size groups, cap weighting within, equal across size."""
    ids = np.flatnonzero(eligible & np.isfinite(score) & np.isfinite(cap) & (cap > 0))
    w = np.zeros((10, len(score)), float)
    if len(ids) < (30 if size_factor else 90): return w
    buckets = [ids] if size_factor else np.array_split(ids[np.argsort(cap[ids], kind='stable')], 3)
    for b in buckets:
        for q, group in enumerate(np.array_split(b[np.argsort(score[b], kind='stable')], 10)):
            w[q, group] = cap[group] / cap[group].sum() / len(buckets)
    np.testing.assert_allclose(w.sum(axis=1), 1.)
    return w

def path_returns(weights, relative):
    nav = relative @ weights.T
    previous = np.vstack((np.ones((1, weights.shape[0])), nav[:-1]))
    return nav / previous - 1

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    saved = OUT / 'inputs.pkl'
    if saved.exists():
        manifest = json.loads((OUT / 'input_manifest.json').read_text())
        if manifest['version'] != VERSION: raise ValueError('Different protocol')
        print('WU_INPUTS_CACHED', flush=True); return
    cal, stocks, fields = pd.read_pickle(LONG / 'market_arrays_long_aliasdedup_v3.pkl')
    monthly = pd.Series(np.arange(len(cal)), index=cal).groupby(cal.to_period('M')).last()
    # Include the current partial month as a live forecast only, not as a
    # completed monthly target in forecast-accuracy statistics.
    positions = monthly.to_numpy(); dates = cal[positions]
    partial = dates[-1].day < 20
    price = pd.DataFrame(fields['close']).ffill().to_numpy(float)
    dailyret = np.full(price.shape, np.nan)
    dailyret[1:] = ratio(price[1:], price[:-1]) - 1
    monthlyret = np.full((len(dates), len(stocks)), np.nan)
    monthlyret[1:] = ratio(price[positions[1:]], price[positions[:-1]]) - 1
    fm = narrow_financial(dates, stocks)
    def f(endpoint, col, lag=0): return fm[f'{endpoint}.{col}.{lag}'].astype(float)
    assets = f('balancesheet', 'total_assets'); mv = fields['cap'][positions].astype(float)
    equity = f('balancesheet', 'total_hldr_eqy_exc_min_int')
    ni = f('income', 'n_income_attr_p_ttm'); cfo = f('cashflow', 'n_cashflow_act_ttm')
    cash = f('balancesheet', 'money_cap'); liab = f('balancesheet', 'total_liab')
    debt = sum(f('balancesheet', c) for c in ('st_borr', 'lt_borr', 'bond_payable'))
    # Reuse latest announced ROE; PMU's undocumented accounting definition is
    # explicitly a YTD gross-profit/assets proxy, not an asserted exact field.
    trait = {'accruals_accruals': ratio(ni - cfo, (assets + f('balancesheet', 'total_assets', 4)) / 2),
             'accruals_noas': ratio(assets - cash - (liab - debt), f('balancesheet', 'total_assets', 4)),
             'investment_annualassetgrowth': ratio(assets, f('balancesheet', 'total_assets', 4)) - 1,
             'investment_quarterlyassetgrowth': ratio(assets, f('balancesheet', 'total_assets', 1)) - 1,
             'profitability_PMU': ratio(f('income', 'revenue') - f('income', 'oper_cost'), assets),
             'profitability_PMUTTM': ratio(f('income', 'revenue_ttm') - f('income', 'oper_cost_ttm'), assets),
             'profitability_roe': f('fina_indicator', 'roe'),
             'size_mktcap': mv, 'value_bmratio': ratio(equity, mv * 10000),
             'value_cpratio': ratio(cfo, mv * 10000), 'value_epratio': ratio(ni, mv * 10000),
             'reversal_onemonthreturn': monthlyret}
    trait['momentum_lagelemreturn'] = pd.DataFrame(price[positions]).shift(1).to_numpy() / pd.DataFrame(price[positions]).shift(12).to_numpy() - 1
    for k in KEYS:
        if k not in trait: trait[k] = np.full(mv.shape, np.nan)
    mt = np.full(mv.shape, np.nan)
    with np.errstate(divide='ignore', invalid='ignore'):
        for i, pos in enumerate(positions):
            begin = positions[i - 1] + 1 if i else 0
            rr = dailyret[begin:pos + 1]
            traded = (fields['volume'][begin:pos + 1] > 0) & np.isfinite(rr)
            rr = np.where(traded, rr, np.nan)
            mt[i] = np.nanmean(np.where(traded, fields['turnover'][begin:pos + 1], np.nan), axis=0)
            trait['illiquidity_illiquidity'][i] = np.nanmean(ratio(np.abs(rr), fields['amount'][begin:pos + 1] * 1000), axis=0)
            trait['volatility_MAX'][i] = np.nanmax(rr, axis=0)
            for n, k in [(1, 'onemonthv'), (3, 'threemonthv'), (6, 'sixmonthv'), (12, 'twelvemonthv')]:
                if i < n: continue
                start = positions[i - n] + 1
                hist = np.where(fields['volume'][start:pos + 1] > 0, dailyret[start:pos + 1], np.nan)
                trait['volatility_' + k][i] = np.nanstd(hist, axis=0, ddof=1)
    trait['turnover_twelvemturnover'] = pd.DataFrame(mt).rolling(12, min_periods=12).mean().to_numpy()
    trait['turnover_onemabturnover'] = ratio(mt, pd.DataFrame(mt).shift(1).rolling(12, min_periods=12).mean().to_numpy()) - 1
    for n, key in [(12, 'oneyearmv'), (24, 'twoyearmv'), (36, 'threeyearmv')]:
        trait['volatility_' + key] = pd.DataFrame(monthlyret).rolling(n, min_periods=n).std().to_numpy()
    traits = np.stack([trait[k] for k in KEYS], axis=-1)
    listing = pd.read_parquet(CACHE / 'stock_basic/data.parquet').drop_duplicates('ts_code').set_index('ts_code')
    ld = pd.to_datetime(listing.list_date.reindex(stocks), errors='coerce')
    listings = ld.to_numpy('datetime64[ns]')
    trading = (fields['volume'] > 0) & np.isfinite(fields['volume'])
    # Paper does not give its insufficient-trading-day thresholds. 120/year
    # and 75% of market trading days/month are declared local assumptions.
    yearcounts = pd.DataFrame(trading.astype(float)).rolling(252, min_periods=120).sum().to_numpy()
    daily = {}; daily_delayed = {}; monthly_return = {}; characteristics = {}; turns = {}; bottom_turns = {}
    holders = {}; previous_holdings = {}; previous_delayed_holdings = {}
    audits = []; costs = {}; delayed_costs = {}
    for keyidx, key in enumerate(KEYS):
        rd = np.full((len(cal), 10), np.nan); rdelay = rd.copy()
        mr = np.full((len(dates), 10), np.nan)
        agg = np.full((len(dates), 10, 24), np.nan)
        turnover = np.full((len(dates), 10), np.nan); fees = np.zeros_like(rd); dfees = fees.copy()
        prev = None; prevdel = None; weights_by_date = []; drift_by_date = []; delay_drift = []
        for i in range(len(dates) - 1):
            pos, end = positions[i], positions[i + 1]
            if pos < 120: continue
            start = positions[i - 1] + 1 if i else 0
            eligible = (mv[i] > 0) & (trading[start:pos + 1].sum(axis=0) >= int(np.ceil(.75 * (pos + 1 - start)))) & (yearcounts[pos] >= 120)
            eligible &= (listings <= (dates[i] - pd.DateOffset(months=6)).to_datetime64())
            eligible &= ~np.asarray(stocks.str.startswith('688'))
            # The cap cutoff uses observable current formation-month cap,
            # before target-factor missingness and before conditional sorting.
            ids = np.flatnonzero(eligible)
            if not len(ids): continue
            eligible[ids[np.argsort(mv[i, ids], kind='stable')][:int(np.floor(.30 * len(ids)))]] = False
            score = -traits[i, :, keyidx] if key in LOW else traits[i, :, keyidx]
            w = conditional_weights(score, mv[i], eligible, key == 'size_mktcap')
            if not w.sum(): continue
            held = np.flatnonzero(w.sum(axis=0) > 0)
            relative = ratio(price[pos + 1:end + 1, held], price[pos, held])
            if not np.isfinite(relative).all(): raise ValueError('Unvalued selected stock')
            rd[pos + 1:end + 1] = path_returns(w[:, held], relative)
            mr[i + 1] = relative[-1] @ w[:, held].T - 1
            rel_del = ratio(price[pos + 2:min(end + 2, len(cal)), held], price[pos + 1, held])
            if len(rel_del): rdelay[pos + 2:min(end + 2, len(cal))] = path_returns(w[:, held], rel_del)
            for q in range(10):
                members = np.flatnonzero(w[q] > 0)
                for j in range(24):
                    valid = np.isfinite(traits[i, members, j]); coverage = w[q, members][valid].sum()
                    if coverage >= .80: agg[i, q, j] = np.dot(w[q, members][valid], traits[i, members, j][valid]) / coverage
            if prev is None:
                tr = np.ones(10); trdel = tr.copy()
            else:
                tr = np.abs(w - prev).sum(axis=1)
                trdel = np.abs(w - prevdel).sum(axis=1)
            drift_by_date.append((dates[i], (np.zeros_like(w) if prev is None else prev)[[0, 9]].astype(np.float32)))
            delay_drift.append((dates[i], (np.zeros_like(w) if prevdel is None else prevdel)[[0, 9]].astype(np.float32)))
            turnover[i] = tr / 2
            fees[pos + 1] = .003 * tr
            if pos + 2 < len(cal): dfees[pos + 2] = .003 * trdel
            # Drift each quantile's combined size buckets independently. The
            # size buckets themselves do not rebalance inside the month.
            growth = ratio(price[end], price[pos]); growth = np.where(np.isfinite(growth), growth, 1.)
            prev = w * growth[None, :]; prev /= prev.sum(axis=1)[:, None]
            dgrowth = ratio(price[min(end + 1, len(cal) - 1)], price[pos + 1]); dgrowth = np.where(np.isfinite(dgrowth), dgrowth, 1.)
            prevdel = w * dgrowth[None, :]; prevdel /= prevdel.sum(axis=1)[:, None]
            weights_by_date.append((dates[i], w[[0, 9]].astype(np.float32)))
            audits.append(dict(key=key, signal=str(dates[i].date()), exit=str(dates[i + 1].date()),
                               universe=int(eligible.sum()), selected=int(len(held)),
                               partial_target=bool(partial and i + 1 == len(dates) - 1)))
        daily[key] = pd.DataFrame(rd, index=cal, columns=range(1, 11))
        daily_delayed[key] = pd.DataFrame(rdelay, index=cal, columns=range(1, 11))
        monthly_return[key] = pd.DataFrame(mr, index=dates.to_period('M'), columns=range(1, 11))
        characteristics[key] = agg; turns[key] = turnover
        costs[key] = pd.DataFrame(fees, index=cal, columns=range(1, 11))
        delayed_costs[key] = pd.DataFrame(dfees, index=cal, columns=range(1, 11))
        holders[key] = weights_by_date
        previous_holdings[key] = drift_by_date
        previous_delayed_holdings[key] = delay_drift
        print('WU_MONTHLY_FACTOR', keyidx + 1, key, int(np.isfinite(mr[:, -1]).sum()), flush=True)
    inputs = dict(version=VERSION, dates=dates, calendar=cal, keys=KEYS,
                  monthly_returns=monthly_return, daily_returns=daily,
                  delayed_daily_returns=daily_delayed, characteristics=characteristics,
                  turnover=turns, costs=costs, delayed_costs=delayed_costs,
                  holdings=holders, previous_holdings=previous_holdings,
                  previous_delayed_holdings=previous_delayed_holdings,
                  partial_last_month=partial)
    pd.to_pickle(inputs, saved)
    pd.DataFrame(audits).to_csv(OUT / 'portfolio_construction_audit.csv', index=False)
    pd.to_pickle(dict(dates=dates, stocks=stocks, traits=trait), OUT / 'monthly_stock_traits.pkl')
    dump(OUT / 'input_manifest.json', dict(version=VERSION, sha256=sha(saved),
         referenced_alignment_version=ALIGNMENT_RULE_VERSION,
         scope='paper monthly cap-weighted size3 protocol; NOT platform aligned',
         factors=24, first_daily=str(cal.min().date()), last_daily=str(cal.max().date()),
         source_market_sha256=sha(LONG / 'market_arrays_long_aliasdedup_v3.pkl'),
         source_financial_sha256=sha(LONG / 'financial_pit_tables_long.pkl'),
         source_stock_basic_sha256=sha(CACHE / 'stock_basic/data.parquet'),
         assumptions=['2006+ Tushare qfq price returns instead of 2000+ Datastream total returns',
          '3 size bins equal-weighted; cap-weighted stocks inside bins; current formation cap',
          'main/SME/ChiNext included; STAR 688 excluded; SH/SZ only',
          '120 traded days/year and >=75% market trading days/month; missing listing dates excluded',
          'PMU/PMUTTM YTD/TTM gross-profit/assets proxies; accrual and NOA accounting proxies',
          '24 trait aggregation on valid >=80% portfolio weight; LS traits are long minus short',
          'paper month-end close hypothetical execution; separate next-close delayed sensitivity',
          'no future-label availability universe screen; last known quote valuation; delisting payoffs absent',
          'current-vintage financial announcements/revisions, NOT verified original vintage',
          'long-short 1 long plus 1 short notional; borrow cost and shortability unmodeled',
          'last partial month excluded from monthly accuracy, retained for dated daily evaluation'],
         original_numeric_replication=False, platform_compute_spent=0))

if __name__ == '__main__': main()
