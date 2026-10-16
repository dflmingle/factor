"""Offline, self-financing equal-weight ledger used by the Meta-label audit.

Fees are paid out of NAV. Targets are weights *after* fees, so buys/sells
must be solved against the invested capital rather than charged on fictitious
pre-fee targets. Inputs are explicit selected names; this module cannot train
or call a platform. No terminal liquidation is assumed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trade(old, target, one_way=.003):
    """Return actual buys/sells/fee as fractions of pre-trade NAV.

    old may contain cash (sum < 1); target must sum to one. At the root,
    post-trade equity = (1-fee)*target and cash balances exactly.
    """
    old = np.asarray(old, dtype=float)
    target = np.asarray(target, dtype=float)
    if old.shape != target.shape or np.any(old < 0) or np.any(target < 0):
        raise ValueError('invalid weights')
    if not np.isfinite(old).all() or not np.isfinite(target).all():
        raise ValueError('nonfinite weights')
    if old.sum() > 1 + 1e-10 or not np.isclose(target.sum(), 1):
        raise ValueError('long-only fully invested target required')
    low, high = 0., 2 * one_way
    for _ in range(60):
        fee = (low + high) / 2
        residual = fee - one_way * np.abs((1-fee)*target-old).sum()
        if residual > 0:
            high = fee
        else:
            low = fee
    fee = (low + high) / 2
    delta = (1-fee)*target-old
    buys = float(np.maximum(delta, 0).sum())
    sells = float(np.maximum(-delta, 0).sum())
    cash_residual = float(1-old.sum()+sells-buys-fee)
    if abs(cash_residual) > 1e-10:
        raise AssertionError(f'cash conservation failed: {cash_residual}')
    return dict(buy=buys, sell=sells, fee=fee, turnover=(buys+sells)/2,
                cash_residual=cash_residual)


def equal_target(selected, width):
    ids = np.asarray(sorted(selected), dtype=int)
    if not len(ids) or len(np.unique(ids)) != len(ids):
        raise ValueError('empty or duplicate holdings')
    target = np.zeros(width)
    target[ids] = 1/len(ids)
    return target


def period_ledger(selections, universes, returns, indices, one_way=.003):
    """Endpoint-only audit; supports frozen old selections and cached labels.

    Period weights drift with actual endpoint stock returns. No daily Sharpe
    or daily drawdown can be derived from this ledger.
    """
    width = returns.shape[1]
    old = np.zeros(width)
    previous = set()
    rows = []
    for offset, i in enumerate(indices):
        selected = set(selections[offset]); ids = np.array(sorted(selected))
        target = equal_target(selected, width)
        t = trade(old, target, one_way)
        rr = returns[i, ids]
        if not np.isfinite(rr).all() or np.any(rr <= -1):
            raise ValueError('invalid held returns')
        held = float(rr.mean())
        benchmark = float(np.mean(returns[i, universes[offset]]))
        net_held = (1-t['fee'])*(1+held)-1
        rows.append(dict(index=int(i), held=held, benchmark=benchmark,
                         gross=held-benchmark, net=net_held-benchmark,
                         net_held=net_held, n_hold=len(ids),
                         member_turnover=0. if not previous else 1-len(previous & selected)/len(ids),
                         **t))
        old[:] = 0
        end_values = (1+rr)/len(ids)
        old[ids] = end_values/end_values.sum()
        previous = selected
    return pd.DataFrame(rows)


def daily_ledger(selections, universes, indices, dates, calendar, close,
                 one_way=.003, cycle=10):
    """t+1 close execution, continuously drifting weights and explicit trades.

    At a shared exit/entry close the old interval's last daily return is
    applied first, then the next rebalance fee; these events are multiplied.
    The final basket is valued, not sold.
    """
    positions = calendar.get_indexer(dates)
    indices = np.asarray(indices, dtype=int)
    if np.any(positions[indices] < 0) or np.any(positions[indices]+cycle+1 >= len(calendar)):
        raise ValueError('calendar does not cover labels')
    if np.any(np.diff(positions[indices]) != cycle):
        raise ValueError('non-contiguous signal grid: do not silently bridge gaps')
    y = np.full((len(dates), close.shape[1]), np.nan)
    with np.errstate(divide='ignore', invalid='ignore'):
        y[indices] = close[positions[indices]+cycle+1].astype(float)/close[positions[indices]+1]-1
    periods = period_ledger(selections, universes, y, indices, one_way)
    events = []
    holdings = []
    for offset, i in enumerate(indices):
        start = positions[i]+1; end = start+cycle
        ids = np.array(sorted(selections[offset])); valid = universes[offset]
        block = close[start:end+1].astype(float)
        if not np.isfinite(block[:, valid]).all() or np.any(block[:, valid] <= 0):
            raise ValueError('invalid prices in factor-valid benchmark or holdings')
        pnav = np.mean(block[:, ids]/block[0, ids], axis=1)
        bnav = np.mean(block[:, valid]/block[0, valid], axis=1)
        fee = periods.iloc[offset].fee
        events.append(dict(date=calendar[start], portfolio=-fee, benchmark=0.,
                           turnover=periods.iloc[offset].turnover, fee=fee))
        for step in range(cycle):
            events.append(dict(date=calendar[start+step+1],
                               portfolio=pnav[step+1]/pnav[step]-1,
                               benchmark=bnav[step+1]/bnav[step]-1,
                               turnover=0., fee=0.))
        for stock in ids:
            holdings.append(dict(index=int(i), stock=int(stock), weight=1/len(ids)))
    daily = pd.DataFrame(events).groupby('date', sort=True).agg(
        portfolio=('portfolio', lambda x: np.prod(1+x)-1),
        benchmark=('benchmark', lambda x: np.prod(1+x)-1),
        turnover=('turnover', 'sum'), fee=('fee', 'sum'))
    # Independent endpoint vs daily compounding identity, including all fees.
    np.testing.assert_allclose(np.prod(1+daily.portfolio), np.prod(1+periods.net_held), rtol=1e-11)
    np.testing.assert_allclose(np.prod(1+daily.benchmark), np.prod(1+periods.benchmark), rtol=1e-11)
    periods['signal_date'] = dates[indices].to_numpy()
    periods['entry_date'] = calendar[positions[indices]+1].to_numpy()
    periods['exit_date'] = calendar[positions[indices]+cycle+1].to_numpy()
    return periods, daily, pd.DataFrame(holdings)


def maxdd(returns):
    nav = np.r_[1., np.cumprod(1+np.asarray(returns))]
    return float(1-np.min(nav/np.maximum.accumulate(nav)))


def summarize(periods, daily=None, cycle=10, holding_intervals=None):
    annualizer = 252/cycle
    out = dict(periods=len(periods), gross_annual_pct=100*periods.gross.mean()*annualizer,
               net_annual_pct=100*periods.net.mean()*annualizer,
               fee_drag_annual_pp=100*(periods.gross-periods.net).mean()*annualizer,
               turnover_pct=100*periods.turnover.mean(),
               member_turnover_pct=100*periods.member_turnover.mean(),
               mean_holdings=float(periods.n_hold.mean()))
    if daily is not None:
        p = daily.portfolio.to_numpy(); b = daily.benchmark.to_numpy()
        # Daily observations include the initial fee-only close. Annualization
        # uses actual close-to-close holding intervals; risk uses every row.
        elapsed = max(len(daily)-1 if holding_intervals is None else holding_intervals, 1)
        out.update(daily_observations=len(daily), holding_trading_days=elapsed,
                   daily_net_sharpe=float(p.mean()/p.std(ddof=1)*np.sqrt(252)),
                   daily_net_maxdd_pct=100*maxdd(p),
                   compound_net_excess_pct=100*(np.prod(1+p)**(252/elapsed)-np.prod(1+b)**(252/elapsed)))
    return out
