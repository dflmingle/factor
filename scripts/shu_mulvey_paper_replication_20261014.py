#!/usr/bin/env python3
"""Daily, top-down SJM -> Black--Litterman replication of arXiv:2410.14841v1.

Original-index reproduction and A-share proxies have distinct admission gates.
No stock-ranking synthesis, reliability pruning, weight caps or covariance
shrinkage is used here. Unpublished implementation conventions are recorded.
"""
from __future__ import annotations

import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.linalg import eigh
from scipy.optimize import minimize, brentq
import osqp
from numba import njit
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
LIT = ROOT / 'research_reports/literature/shu-mulvey-dynamic-allocation-20261014'
BASE = ROOT / 'research_reports/platform_alignment/shu-mulvey-paper-replication-20261014'
sys.path.insert(0, str(LIT / 'author_library'))
from jumpmodels.sparse_jump import SparseJumpModel
import jumpmodels.jump as author_jump

VERSION = 'shu-mulvey-daily-topdown-paper-v1'
STYLE_KEYS = dict(value='book_market', size='small_size', momentum='momentum120',
                  quality='roe', lowvol='low_vol20', growth='growth_sales')
FEATURE_NAMES = ([f'active_ew{n}' for n in (8, 21, 63)]
                 + [f'rsi{n}' for n in (8, 21, 63)]
                 + [f'stoch{n}' for n in (8, 21, 63)]
                 + ['macd8_21', 'macd21_63', 'log_downside21', 'active_beta21',
                    'market_ew21', 'vix_logdiff_ew21', '2y_diff_ew21', '10y2y_diff_ew21'])


@dataclass(frozen=True)
class Protocol:
    # Paper does not publish the search grid; never call this the author's grid.
    params: tuple = ((10., 6.), (10., 9.5), (50., 6.), (50., 9.5), (100., 6.), (100., 9.5))
    min_train_years: int = 8
    max_train_years: int = 12
    validation_years: int = 6
    cost: float = .0005
    delta: float = 2.5
    covariance_halflife: int = 126
    random_seed: int = 47347
    sparse_max_iter: int = 30
    jm_max_iter: int = 1000
    jm_initializations: int = 10


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@njit(cache=True)
def dp_fast(loss, penalty):
    n, k = loss.shape
    value = np.empty((n, k)); labels = np.empty(n, np.int64)
    for s in range(k):
        value[0, s] = loss[0, s] if np.isfinite(loss[0, s]) else np.inf
    for t in range(1, n):
        for s in range(k):
            best = np.inf
            for r in range(k):
                best = min(best, value[t - 1, r] + penalty[r, s])
            value[t, s] = best + (loss[t, s] if np.isfinite(loss[t, s]) else np.inf)
    labels[-1] = np.argmin(value[-1])
    for t in range(n - 2, -1, -1):
        best = np.inf; arg = 0
        for s in range(k):
            z = value[t, s] + penalty[s, labels[t + 1]]
            if z < best:
                best = z; arg = s
        labels[t] = arg
    return labels, value[-1, labels[-1]], value


def author_dp(loss, penalty, return_value_mx=False):
    labels, value, values = dp_fast(np.asarray(loss, float), np.asarray(penalty, float))
    return values if return_value_mx else (labels, value)


def install_verified_acceleration():
    original = author_jump.dp
    checks = []
    for seed in (0, 1, 2):
        loss = np.random.default_rng(seed).normal(size=(89, 2)) ** 2
        if seed == 1: loss[:] = 1.
        if seed == 2: loss[:, 1] = np.nan
        penalty = np.array([[0., 50.], [50., 0.]])
        a, av = original(loss, penalty); b, bv = author_dp(loss, penalty)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_allclose(av, bv, atol=1e-10)
        np.testing.assert_allclose(original(loss, penalty, True), author_dp(loss, penalty, True))
        checks.append(dict(seed=seed, passed=True))
    author_jump.dp = author_dp
    return checks


def ew(series, window):
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def features(active, market, macro):
    """Exhibit 3's 17 features; no substitute VIX or extra breadth feature.

    Compound active wealth, unscaled MACD difference, adjusted=False EWM and
    zero-denominator RSI/%K=50 are explicit conventions, not published code.
    Missing macro is an error; it cannot be silently replaced by zero.
    """
    a = pd.Series(active, index=market.index, dtype=float)
    wealth = (1 + a.fillna(0)).cumprod()
    up = a.clip(lower=0); down = (-a).clip(lower=0)
    cols = [ew(a, n) for n in (8, 21, 63)]
    for n in (8, 21, 63):
        u, d = ew(up, n), ew(down, n)
        den = u + d
        cols.append((100 * u / den).where(den > 1e-15, 50.))
    for n in (8, 21, 63):
        low, high = wealth.rolling(n).min(), wealth.rolling(n).max()
        den = high - low
        cols.append((100 * (wealth - low) / den).where(den > 1e-15, 50.))
    cols += [ew(wealth, 8) - ew(wealth, 21), ew(wealth, 21) - ew(wealth, 63)]
    cols.append(np.log(ew(down ** 2, 21).pow(.5).clip(lower=1e-10)))
    # Bias-corrected EWM cov/var cancel in their ratio, use the same convention.
    cov = a.ewm(span=21, adjust=False, min_periods=21).cov(market)
    var = market.ewm(span=21, adjust=False, min_periods=21).var()
    cols += [(cov / var).where(var > 1e-15, 0.), ew(market, 21)]
    cols += [ew(np.log(macro.VIXCLS).diff(), 21), ew(macro.DGS2.diff(), 21),
             ew((macro.DGS10 - macro.DGS2).diff(), 21)]
    out = pd.concat(cols, axis=1); out.columns = FEATURE_NAMES
    out.loc[a.isna()] = np.nan
    return out


def timing_returns(views, active, cost=.0005):
    """Close t view -> close t+1 execution -> return t+2. Both legs pay fees."""
    v = np.asarray(views, float)
    signal = np.clip(v * 252 / .05, -1, 1)
    sig = np.nan_to_num(signal, nan=0.)
    position = np.r_[0., 0., sig[:-2]]
    execution_target = np.r_[0., sig[:-1]]
    fee = 2 * cost * np.abs(execution_target - position)
    ret = position * np.nan_to_num(active, nan=0.) - fee
    return ret, position, fee


def fit_path(task):
    key, dates, x, active, lam, kappa2, protocol = task
    install_verified_acceleration()
    dates = pd.DatetimeIndex(dates); x = np.asarray(x, float); active = np.asarray(active, float)
    good = np.isfinite(x).all(axis=1) & np.isfinite(active)
    out = np.full(len(dates), np.nan); states = np.full(len(dates), -1, np.int8)
    source = np.full(len(dates), -1, np.int32); fit_rows = []
    first = np.flatnonzero(good)
    if not len(first):
        return dict(key=key, lambda_=lam, kappa2=kappa2, views=out, states=states, source=source, fits=[])
    first_date = dates[first[0]]
    periods = dates.to_period('M')
    ready = first_date + pd.DateOffset(years=protocol.min_train_years)
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for month in periods.unique():
            loc = np.flatnonzero(periods == month); t = int(loc[0])
            if dates[t] < ready: continue
            left = dates.searchsorted(dates[t] - pd.DateOffset(years=protocol.max_train_years))
            ids = np.flatnonzero(good[left:t]) + left
            if not len(ids) or dates[ids[0]] > dates[t] - pd.DateOffset(years=protocol.min_train_years):
                continue
            # Calendar coverage alone is insufficient for sparse/disappearing sleeves.
            if len(ids) < int(200 * protocol.min_train_years): continue
            mean = x[ids].mean(axis=0); sd = x[ids].std(axis=0)
            sd = np.maximum(sd, 1e-12); z = (x[ids] - mean) / sd
            model = SparseJumpModel(n_components=2, jump_penalty=lam, max_feats=kappa2,
                                    max_iter=protocol.sparse_max_iter,
                                    max_iter_jm=protocol.jm_max_iter,
                                    n_init_jm=protocol.jm_initializations,
                                    random_state=protocol.random_seed).fit(z, ret_ser=active[ids], sort_by='ret')
            labels = np.asarray(model.labels_, int)
            counts = np.bincount(labels, minlength=2)
            means = np.array([active[ids][labels == s].mean() if counts[s] else np.nan for s in range(2)])
            # The endpoint recurrence equals predict_online, without daily prefix rescans.
            weighted = z * np.asarray(model.feat_weights)
            # Use the author's fitted jump model for loss/penalty conventions.
            centers = np.asarray(model.jm_ins.centers_)
            centers = np.nan_to_num(centers, nan=0.)
            loss = .5 * ((weighted[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            loss[:, counts==0] = np.inf
            penalty = np.asarray(model.jm_ins.jump_penalty_mx)
            dpvalue = author_dp(loss, penalty, True)[-1].copy()
            for day in loc:
                if not good[day]: continue
                obs = (x[day] - mean) / sd * np.asarray(model.feat_weights)
                loss_day = .5 * ((centers - obs) ** 2).sum(axis=1)
                loss_day[counts==0] = np.inf
                dpvalue = loss_day + np.min(dpvalue[:, None] + penalty, axis=0)
                state = int(np.argmin(dpvalue))
                out[day] = means[state]; states[day] = state; source[day] = ids[-1]
            fit_rows.append(dict(key=key, lambda_=lam, kappa2=kappa2,
                                 refit_date=str(dates[t].date()), first_training_date=str(dates[ids[0]].date()),
                                 last_training_date=str(dates[ids[-1]].date()), training_days=len(ids),
                                 sparse_iterations=getattr(model,'n_iter_',None), state0_n=int(counts[0]), state1_n=int(counts[1]),
                                 mu0=float(means[0]), mu1=float(means[1]),
                                 feature_weights=np.asarray(model.w).tolist()))
    return dict(key=key, lambda_=lam, kappa2=kappa2, views=out, states=states, source=source, fits=fit_rows)


def select_views(paths, dates, active, protocol):
    """Six *calendar* years of realized daily validation; freeze for six months."""
    dates = pd.DatetimeIndex(dates); views = np.column_stack([p['views'] for p in paths])
    returns = np.column_stack([timing_returns(p['views'], active, protocol.cost)[0] for p in paths])
    n = len(dates); chosen = np.full(n, -1, int); prediction = np.full(n, np.nan)
    state = np.full(n, -1, int); audit = []
    selected = -1; half = None
    # Valid realized returns require the view from two trading days earlier.
    predgood = np.isfinite(views)
    realizable = np.zeros_like(predgood); realizable[2:] = predgood[:-2]
    for i, date in enumerate(dates):
        epoch = (date.year, (date.month - 1) // 6)
        if epoch != half:
            half = epoch; selected = -1
            start = date - pd.DateOffset(years=protocol.validation_years)
            lo = int(dates.searchsorted(start)); hi = i
            scores = []; available = []
            for k in range(len(paths)):
                # Reject an incomplete initial validation history, no default lambda.
                coverage = hi > lo and dates[lo] <= start + pd.Timedelta(days=7)
                coverage &= bool(realizable[lo:hi, k].all())
                available.append(coverage)
                z = returns[lo:hi, k]
                scores.append(float(z.mean() / z.std(ddof=1) * np.sqrt(252))
                              if coverage and len(z) > 1 and z.std(ddof=1) > 1e-12 else np.nan)
            if np.isfinite(scores).any(): selected = int(np.nanargmax(scores))
            audit.append(dict(selection_date=str(date.date()), validation_start=str(start.date()),
                              validation_last_return=str(dates[hi - 1].date()) if hi else None,
                              validation_days=hi-lo, selected=selected, sharpe=scores,
                              full_six_year_eligible=available))
        if selected >= 0 and predgood[i, selected]:
            prediction[i] = views[i, selected]; chosen[i] = selected
            state[i] = paths[selected]['states'][i]
    return prediction, chosen, state, audit


def covariance(returns, halflife=126):
    """Unshrunk EWM covariance; only machine-precision diagonal jitter if needed."""
    r = np.asarray(returns, float)
    if not np.isfinite(r).all(): raise ValueError('Non-finite covariance inputs')
    w = .5 ** (np.arange(len(r)-1, -1, -1) / halflife); w /= w.sum()
    mu = w @ r; cov = ((r - mu) * w[:, None]).T @ (r - mu)
    cov /= 1 - w @ w
    floor = np.finfo(float).eps * max(float(np.trace(cov)), 1e-8)
    jitter = max(0., floor - float(np.linalg.eigvalsh(cov)[0]))
    return cov + np.eye(cov.shape[0]) * jitter, jitter


def posterior(cov, benchmark, views, delta, confidence_inverse):
    n = len(benchmark); p = np.column_stack([np.eye(n-1), -np.ones(n-1)])
    pi = delta * cov @ benchmark
    var = np.diag(p @ cov @ p.T)
    omega_tau = confidence_inverse * np.diag(var)
    return pi + cov @ p.T @ np.linalg.solve(p @ cov @ p.T + omega_tau, views - p @ pi)


def bl_targets(cov, benchmark, views, tes, delta=2.5):
    """Appendix B relative views, fully invested long-only, no per-factor cap."""
    n = len(benchmark); available = np.flatnonzero(np.isfinite(views))
    if not len(available):
        return {te: benchmark.copy() for te in tes}, {te: dict(predicted_te=0., confidence_inverse=np.inf,
                solver_success=True, active_views=0, reached_target=False) for te in tes}
    p = np.zeros((len(available), n)); p[np.arange(len(available)), available] = 1.; p[:, -1] = -1.
    pi = delta * cov @ benchmark; k = p @ cov @ p.T
    scale = np.sqrt(np.maximum(np.diag(k), 1e-16))
    eigen, u = eigh(k / scale[:, None] / scale[None, :])
    pre = (cov @ p.T / scale[None, :]) @ u
    residual = u.T @ ((views[available] - p @ pi) / scale)
    qp = osqp.OSQP()
    qp.setup(P=sparse.csc_matrix(np.triu(delta * cov * 252)), q=-pi * 252,
             A=sparse.vstack([sparse.csc_matrix(np.ones((1, n))), sparse.eye(n)], format='csc'),
             l=np.r_[1., np.zeros(n)], u=np.r_[1., np.ones(n)],
             eps_abs=1e-9, eps_rel=1e-9, max_iter=20000, polishing=True, verbose=False)
    qp.warm_start(x=benchmark)
    cache = {}
    def solve(log_uncertainty):
        if log_uncertainty in cache: return cache[log_uncertainty]
        c = 10 ** log_uncertainty
        mu = pi + pre @ (residual / (np.maximum(eigen, 0.) + c))
        if n<=20:
            result=minimize(lambda w:252*(delta/2*w@cov@w-mu@w),benchmark,
                jac=lambda w:252*(delta*cov@w-mu),method='SLSQP',bounds=[(0,1)]*n,
                constraints={'type':'eq','fun':lambda w:w.sum()-1,'jac':lambda w:np.ones(n)},
                options={'ftol':1e-13,'maxiter':1000})
            if not result.success:raise RuntimeError('BL optimization failed: '+result.message)
            weight=np.asarray(result.x)
        else:
            qp.update(q=-mu * 252); result = qp.solve(raise_error=False)
            success = result.info.status_val in (1, 2)
            if success:weight = np.asarray(result.x)
            else:
                # Same objective/constraints, independent solver; never replace
                # a failed solve by benchmark weights and report success.
                retry=minimize(lambda w:252*(delta/2*w@cov@w-mu@w),benchmark,
                    jac=lambda w:252*(delta*cov@w-mu),method='SLSQP',bounds=[(0,1)]*n,
                    constraints={'type':'eq','fun':lambda w:w.sum()-1,'jac':lambda w:np.ones(n)},
                    options={'ftol':1e-13,'maxiter':1500})
                if not retry.success:raise RuntimeError('BL optimization failed: '+result.info.status+'; '+retry.message)
                weight=np.asarray(retry.x)
        if weight.min() < -1e-7 or abs(weight.sum()-1) > 1e-7: raise RuntimeError('Invalid BL weights')
        weight = np.maximum(weight, 0); weight /= weight.sum()
        d = weight - benchmark; te = np.sqrt(max(float(d @ cov @ d) * 252, 0.))
        cache[log_uncertainty] = weight, te
        return weight, te
    answers = {}; audits = {}
    previous_log=12.
    for target in tes:
        low, high = (0. if n>20 else -8.), 12.
        wlow, tlow = solve(low); whigh, thigh = solve(high)
        # Avoid ill-conditioned, near-zero uncertainty when the actual root
        # is many orders larger. Expand down only if a stronger view is needed.
        while n>20 and tlow<=target and low>-8.:
            low=max(-8.,low-2.);wlow,tlow=solve(low)
        if tlow <= target:
            w, error, confidence = wlow, tlow, 10 ** low
        else:
            if thigh > target + 1e-7: raise RuntimeError('TE benchmark limit failed')
            w, error, confidence = whigh, thigh, 10 ** high
            if n>20:
                root=brentq(lambda log:solve(log)[1]-target,low,previous_log,xtol=1e-6)
                safe=root+2e-6;w,error=solve(safe);confidence=10**safe;previous_log=safe
                if error>target+1e-7:raise RuntimeError('TE root calibration failed')
            else:
                for _ in range(24):
                    mid = (low+high)/2; candidate, trial = solve(mid)
                    if trial <= target:
                        high = mid; w, error, confidence = candidate, trial, 10 ** mid
                    else: low = mid
        answers[target] = w
        audits[target] = dict(predicted_te=float(error), confidence_inverse=float(confidence),
                             solver_success=True, active_views=len(available), reached_target=bool(error>=target*.995))
    return answers, audits


def quarterly_benchmark(returns, cost):
    r = np.asarray(returns, float); n, m = r.shape; dates = returns.index
    equal = np.full(m, 1/m); weights = np.empty_like(r); out = np.zeros(n); fees = np.zeros(n)
    turnover = np.zeros(n); prev = equal.copy(); quarter = None
    for i, date in enumerate(dates):
        gross = float(prev @ r[i]); pre = prev * (1+r[i]) / (1+gross)
        current = date.to_period('Q')
        if current != quarter:
            quarter = current; target = equal
            turnover[i] = .5 * np.abs(target-pre).sum()
            fees[i] = cost * np.abs(target-pre).sum(); prev = target.copy()
        else: prev = pre
        out[i] = (1+gross)*(1-fees[i])-1; weights[i] = prev
    return out, weights, fees, turnover


def realized_portfolio(returns, signal_weights, cost, initial=None):
    """Weights at close t execute close t+1; no r(t+1) on new weights."""
    r = np.asarray(returns, float); w = np.asarray(signal_weights, float)
    n, m = r.shape; previous = np.full(m, 1/m) if initial is None else np.array(initial, float)
    pnl = np.zeros(n); fee = np.zeros(n); turnover = np.zeros(n); executed = np.empty_like(w)
    for i in range(n):
        gross = float(previous @ r[i]); pretrade = previous * (1+r[i]) / (1+gross)
        target = w[i-1] if i else pretrade
        turnover[i] = .5*np.abs(target-pretrade).sum(); fee[i] = cost*np.abs(target-pretrade).sum()
        pnl[i] = (1+gross)*(1-fee[i])-1; previous = target.copy(); executed[i] = previous
    return pnl, fee, turnover, executed


def stats(ret, market, benchmark, turnover, riskfree=None):
    ret=np.asarray(ret); market=np.asarray(market); benchmark=np.asarray(benchmark)
    nav=np.r_[1.,np.cumprod(1+ret)]
    def active(ref):
        a=ret-ref; wealth=np.r_[1., np.cumprod((1+ret)/(1+ref))]
        return dict(arithmetic_active_pct=float(a.mean()*252*100),
                    information_ratio=float(a.mean()/a.std(ddof=1)*np.sqrt(252)) if a.std(ddof=1)>1e-12 else None,
                    realized_te_pct=float(a.std(ddof=1)*np.sqrt(252)*100),
                    relative_wealth_max_drawdown_pct=float((1-wealth/np.maximum.accumulate(wealth)).max()*100))
    absolute=ret-(np.asarray(riskfree) if riskfree is not None else 0.)
    return dict(days=len(ret),arithmetic_return_pct=float(ret.mean()*252*100),
                compounded_annual_return_pct=float((nav[-1]**(252/len(ret))-1)*100),
                arithmetic_riskfree_excess_pct=float(absolute.mean()*252*100),
                riskfree_excess_sharpe=float(absolute.mean()/absolute.std(ddof=1)*np.sqrt(252)) if absolute.std(ddof=1)>1e-12 else None,
                volatility_pct=float(ret.std(ddof=1)*np.sqrt(252)*100),
                max_drawdown_pct=float((1-nav/np.maximum.accumulate(nav)).max()*100),
                annual_one_way_turnover_pct=float(np.mean(turnover)*252*100),
                vs_market=active(market),vs_quarterly_ew=active(benchmark))


def original_data_gate(manifest, returns):
    reasons=[]
    if manifest.get('mode')!='original_us_indices': reasons.append('mode is not original_us_indices')
    if manifest.get('original_bloomberg_total_return_indices_verified') is not True:
        reasons.append('original Bloomberg total-return indices and historical splices unverified')
    if manifest.get('return_type')!='total_return':reasons.append('total-return provenance missing')
    required_splices={'value':'MSCI USA Value Weighted before 1997/12',
        'size':'MSCI USA Equal Weighted before 1994/6','momentum':'MSCI USA Momentum before 2002/6',
        'quality':'MSCI USA Quality before 1998/12','lowvol':'MSCI USA Risk Weighted before 1994/6'}
    if manifest.get('verified_historical_splices')!=required_splices:
        reasons.append('all five historical splice identities must be verified')
    if not manifest.get('source_file_sha256'):reasons.append('source data checksum/provenance missing')
    if list(returns.columns)!=['value','size','momentum','quality','lowvol','growth','market']:
        reasons.append('original seven-asset order mismatch')
    if returns.index.min()>pd.Timestamp('1993-01-08'): reasons.append('1993 inception missing')
    if returns.index.max()<pd.Timestamp('2024-06-28'): reasons.append('mid-2024 endpoint missing')
    if reasons: raise ValueError('Original result reproduction cannot be claimed: '+'; '.join(reasons))


ALLOC_CONTEXT=None


def allocation_init(r,v,b,dates,protocol):
    global ALLOC_CONTEXT
    ALLOC_CONTEXT=(r,v,b,dates,protocol)


def allocation_day(t):
    r,v,b,dates,protocol=ALLOC_CONTEXT
    with threadpool_limits(limits=1):
        cov,jitter=covariance(r[:t+1],protocol.covariance_halflife)
        targets,logs=bl_targets(cov,b[t],v[t],(.01,.02,.03,.04),protocol.delta)
    return t,targets,[dict(date=str(dates[t].date()),target_te=te,
            covariance_last_date=str(dates[t].date()),jitter=jitter,**log) for te,log in logs.items()]


def run(args):
    protocol=Protocol(); directory=BASE/args.universe; directory.mkdir(parents=True,exist_ok=True)
    input_path=Path(args.input) if args.input else BASE/'inputs.pkl'
    bundle=pd.read_pickle(input_path); allreturns=bundle['gross_returns']; netreturns=bundle['net_returns']
    original=bundle.get('mode')=='original_us_indices'
    if original:
        original_data_gate(bundle['manifest'],allreturns)
        if args.universe!='six_styles':raise ValueError('Original experiment has exactly six factors and market')
        directory=BASE/'original_us_indices';directory.mkdir(exist_ok=True)
        returns=allreturns;local=netreturns
    elif args.universe=='six_styles':
        keys=list(STYLE_KEYS.values())+['market']; returns=allreturns[keys]
        local=netreturns[keys]
    else:
        returns=allreturns; local=netreturns
    dates=returns.index; keys=list(returns.columns[:-1]); macro=bundle['macro']; market=returns.iloc[:,-1]
    if args.exclude_six:
        if not args.fit_only:raise ValueError('--exclude-six is only a disjoint precomputation option')
        keys=[key for key in keys if key not in STYLE_KEYS.values()]
    datahash=digest(input_path); phash=hashlib.sha256(json.dumps(asdict(protocol),sort_keys=True).encode()).hexdigest()
    cache=BASE/'models'/datahash[:16];cache.mkdir(exist_ok=True,parents=True)
    outputs={key:{} for key in keys}; tasks=[]
    for key in keys:
        active=(returns[key]-market).where(dates>=bundle['inceptions'][key])
        x=features(active,market,macro).to_numpy()
        finite=np.flatnonzero(np.isfinite(x).all(axis=1))
        possible=bool(len(finite)) and dates[finite[0]]+pd.DateOffset(years=protocol.min_train_years+protocol.validation_years)<=dates[-1]
        for lam,kappa2 in protocol.params:
            target=cache/(hashlib.sha256(key.encode()).hexdigest()[:16]+f'-l{lam}-k{kappa2}.pkl')
            if target.exists():
                stored=pd.read_pickle(target)
                if stored['datahash']!=datahash or stored['protocol_hash']!=phash:
                    raise ValueError('Incompatible model cache '+str(target))
                outputs[key][(lam,kappa2)]=stored['path']
            elif not possible:
                result=dict(key=key,lambda_=lam,kappa2=kappa2,views=np.full(len(dates),np.nan),
                            states=np.full(len(dates),-1,np.int8),source=np.full(len(dates),-1,np.int32),fits=[],
                            reason='not enough calendar history for eight-year training plus six-year validation')
                outputs[key][(lam,kappa2)]=result
                pd.to_pickle(dict(datahash=datahash,protocol_hash=phash,path=result),target)
            else: tasks.append((target,(key,dates,x,active.to_numpy(),lam,kappa2,protocol)))
    print('PATHS',args.universe,'cached',sum(len(x) for x in outputs.values()),'pending',len(tasks),flush=True)
    if tasks:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            jobs={pool.submit(fit_path,task):path for path,task in tasks}
            for j, future in enumerate(as_completed(jobs),1):
                result=future.result();outputs[result['key']][(result['lambda_'],result['kappa2'])]=result
                pd.to_pickle(dict(datahash=datahash,protocol_hash=phash,path=result),jobs[future])
                print('FITTED',j,'/',len(tasks),result['key'],result['lambda_'],result['kappa2'],len(result['fits']),flush=True)
    if args.fit_only:
        dump(directory/'fit_precomputation.json',dict(completed=True,keys=keys,input_hash=datahash,
             parameter_paths=sum(len(x) for x in outputs.values()),exclude_six=args.exclude_six))
        return
    predictions=[]; states=[]; choices=[]; fits=[]; audit={}
    for key in keys:
        paths=[outputs[key][p] for p in protocol.params]
        view,choice,state,rows=select_views(paths,dates,(returns[key]-market).to_numpy(),protocol)
        predictions.append(view);choices.append(choice);states.append(state);audit[key]=rows
        fits.extend(row for path in paths for row in path['fits'])
    predictions=pd.DataFrame(np.array(predictions).T,index=dates,columns=keys)
    predictions.to_parquet(directory/'daily_views.parquet')
    pd.DataFrame(np.array(states).T,index=dates,columns=keys).to_parquet(directory/'daily_states.parquet')
    pd.DataFrame(np.array(choices).T,index=dates,columns=keys).to_parquet(directory/'daily_parameter_choices.parquet')
    pd.DataFrame(fits).to_json(directory/'monthly_model_fits.json',orient='records',indent=2)
    dump(directory/'semiannual_validation.json',audit)
    # No default parameters or partial validation enters formal allocation.
    start=args.start or ('2007-01-01' if original else '2021-09-07')
    end=args.end or ('2024-06-30' if original else '2026-09-07')
    formal=dates[(dates>=start)&(dates<=end)]
    if not len(formal): raise RuntimeError('No dates in requested evaluation window')
    if not predictions.loc[formal].notna().any(axis=None):raise RuntimeError('No factors pass full six-year validation')
    signal_start=dates.get_loc(formal[0]); signal_end=dates.get_loc(formal[-1])
    tes=(.01,.02,.03,.04); weights={te:[] for te in tes}; allocation=[]
    r=returns.to_numpy(); v=predictions.to_numpy()
    ewret,benchmark,ewfee,ewturn=quarterly_benchmark(returns,protocol.cost)
    if len(returns.columns)>20:
        saved=directory/'allocation_cache';saved.mkdir(exist_ok=True)
        pending=[t for t in range(signal_start,signal_end+1) if not (saved/f'{t}.pkl').exists()]
        with ProcessPoolExecutor(max_workers=args.workers,initializer=allocation_init,
                initargs=(r,v,benchmark,dates,protocol)) as pool:
            jobs=[pool.submit(allocation_day,t) for t in pending]
            for i,future in enumerate(as_completed(jobs),1):
                result=future.result();pd.to_pickle(result,saved/f'{result[0]}.pkl')
                if i%25==0:print('ALLOCATED_PARALLEL',i,'/',len(pending),flush=True)
        for t in range(signal_start,signal_end+1):
            _,target,logs=pd.read_pickle(saved/f'{t}.pkl')
            for te in tes:weights[te].append(target[te])
            allocation.extend(logs)
    else:
        for t in range(signal_start,signal_end+1):
            # Through today's close is observable; execution is tomorrow's close.
            cov,jitter=covariance(r[:t+1],protocol.covariance_halflife)
            target,logs=bl_targets(cov,benchmark[t],v[t],tes,protocol.delta)
            for te in tes:
                weights[te].append(target[te]);allocation.append(dict(date=str(dates[t].date()),target_te=te,
                        covariance_last_date=str(dates[t].date()),jitter=jitter,**logs[te]))
            if (t-signal_start)%100==0:print('ALLOCATED',t-signal_start,'/',signal_end-signal_start+1,flush=True)
    allocation=pd.DataFrame(allocation);allocation.to_csv(directory/'allocation_audit.csv',index=False)
    summary=[]; daily=returns.iloc[signal_start:signal_end+1]; localdaily=local.iloc[signal_start:signal_end+1]
    # Start from the same currently drifted benchmark in each portfolio.
    for cost_case,cost,assets in [('paper_fee_proxy',.0005,daily),('local_fee_proxy',.003,localdaily)]:
        # Benchmark path must retain quarter drift from the earlier history.
        br,bw,bf,bt=quarterly_benchmark(returns if cost_case=='paper_fee_proxy' else local,cost)
        br=br[signal_start:signal_end+1];bt=bt[signal_start:signal_end+1]
        frame=pd.DataFrame({'market':assets.iloc[:,-1],'quarterly_ew':br},index=assets.index)
        for te in tes:
            w=np.array(weights[te]);pnl,fee,turnover,executed=realized_portfolio(assets,w,cost,bw[signal_start-1])
            label=f'TE{int(te*100)}';frame[label]=pnl
            pd.DataFrame(w,index=assets.index,columns=returns.columns).to_parquet(directory/f'{label}.signal_weights.parquet')
            pd.DataFrame(executed,index=assets.index,columns=returns.columns).to_parquet(directory/f'{label}.{cost_case}.executed_weights.parquet')
            pd.DataFrame(dict(return_=pnl,fee=fee,one_way_turnover=turnover),index=assets.index).to_csv(directory/f'{label}.{cost_case}.ledger.csv')
            for window,mask in [('five_year',np.ones(len(assets),bool)),('recent',assets.index>='2026-01-01')]:
                if mask.any():summary.append(dict(configuration=label,cost_case=cost_case,window=window,
                       first_date=str(assets.index[mask][0].date()),last_date=str(assets.index[mask][-1].date()),
                       **stats(pnl[mask],assets.iloc[:,-1].to_numpy()[mask],br[mask],turnover[mask],
                               macro.DGS3MO.iloc[signal_start:signal_end+1].to_numpy()[mask]/100/252)))
        for window,mask in [('five_year',np.ones(len(assets),bool)),('recent',assets.index>='2026-01-01')]:
            summary.append(dict(configuration='QUARTERLY_EW',cost_case=cost_case,window=window,
                first_date=str(assets.index[mask][0].date()),last_date=str(assets.index[mask][-1].date()),
                **stats(br[mask],assets.iloc[:,-1].to_numpy()[mask],br[mask],bt[mask],
                        macro.DGS3MO.iloc[signal_start:signal_end+1].to_numpy()[mask]/100/252)))
        frame.to_csv(directory/f'{cost_case}.daily_returns.csv')
    dump(directory/'results.json',summary)
    flat=[]
    for row in summary:
        z={k:v for k,v in row.items() if not isinstance(v,dict)}
        for family in ('vs_market','vs_quarterly_ew'):
            z.update({family+'_'+k:v for k,v in row[family].items()})
        flat.append(z)
    pd.DataFrame(flat).to_csv(directory/'results.csv',index=False)
    coverage=pd.DataFrame({'key':keys,'first_forecast':[predictions[k].first_valid_index() for k in keys],
                           'formal_forecast_days':[int(predictions.loc[formal,k].notna().sum()) for k in keys]})
    coverage.to_csv(directory/'factor_coverage.csv',index=False)
    dump(directory/'protocol.json',dict(version=VERSION,protocol=asdict(protocol),input_hash=datahash,
        mode=bundle['mode'],original_us_result_reproduced=False,original_index_data_available=original,assets=len(returns.columns),
        model_factors=len(keys),all592_completed=False,universe=args.universe,
        benchmark='fixed-universe equally weighted; rebalance first trading day close each quarter; drift otherwise',
        allocation='daily long-only fully invested, factor sleeves plus investable market sleeve',
        views='each asset return minus the same market return; no factor_valid substitution in model',
        observed_te='reported separately from predictive TE; fees and covariance changes may alter realized TE',
        undisclosed_conventions=['search grid not published; declared local grid','EWM adjust=False and effective span',
          'compound active wealth; MACD difference, not ratio','zero-denominator RSI/K=50',
          'calendar training/validation windows, first-trading-day monthly refits',
          'online TE confidence calibration; covariance numerical jitter only'],
        requested_window=[start,end],actual_window=[str(formal.min().date()),str(formal.max().date())],
        differences=bundle['limitations'],platform_calls=0))
    assert np.all(allocation.predicted_te<=allocation.target_te+1e-7)
    assert np.all(allocation.solver_success)
    dump(directory/'verification.json',dict(completed=True,allocation_constraints=True,all_solvers_success=True,
                                          six_year_validation_required=True,unit_tests='see ../unit_verification.json'))
    print(pd.DataFrame(flat)[['configuration','cost_case','window','vs_quarterly_ew_arithmetic_active_pct',
                             'max_drawdown_pct','annual_one_way_turnover_pct']].to_string(index=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--universe',choices=['six_styles','all_replayed'],default='six_styles')
    parser.add_argument('--workers',type=int,default=12)
    parser.add_argument('--input',help='Validated bundle; original US inputs must pass the data gate')
    parser.add_argument('--start');parser.add_argument('--end')
    parser.add_argument('--fit-only',action='store_true')
    parser.add_argument('--exclude-six',action='store_true')
    args=parser.parse_args();run(args)
