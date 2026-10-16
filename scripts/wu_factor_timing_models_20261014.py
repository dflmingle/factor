#!/usr/bin/env python3
"""Expanding-window Pearson-screened forecasts and Wu's ARI cluster selector.

Undisclosed predictor definitions and estimator conventions are explicitly
local proxies. Hyperparameters are chosen on chronological inner folds only.
"""
from __future__ import annotations
import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, norm, t as student_t
from sklearn.cluster import KMeans, Birch, SpectralClustering, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_rand_score
from sklearn.linear_model import ElasticNet
from sklearn.cross_decomposition import PLSRegression
from sklearn.exceptions import ConvergenceWarning
import statsmodels.api as sm
from wu_factor_timing_inputs_20261014 import ROOT, OUT, CACHE, KEYS, dump, sha

MODELS = ['PCA1_OLS', 'PCA1_VAR1', 'OLS', 'ElasticNet', 'PC', 'PLS',
          'C_Simple', 'C_ENet', 'Predictor_Average']
CLUSTERS = ['KMeans', 'Birch', 'GaussianMixture', 'Spectral', 'Agglomerative']
SEED = 20241014

def target_returns(bundle, key, wing):
    m = bundle['monthly_returns'][key]
    return m[10] - m[1] if wing == 'LS' else m[10 if wing == 'L' else 1]

def portfolio_features(bundle, key, wing):
    dates = bundle['dates']; idx = dates.to_period('M')
    chars = bundle['characteristics'][key]
    a = chars[:, 9] - chars[:, 0] if wing == 'LS' else chars[:, 9 if wing == 'L' else 0]
    x = pd.DataFrame(a, index=idx, columns=KEYS)
    y = target_returns(bundle, key, wing)
    d = bundle['daily_returns'][key]
    # Daily portfolio vol proxy uses daily long minus daily short leg returns.
    # Its role is a predictor only; strategy NAV uses fixed monthly holdings.
    dr = d[10] - d[1] if wing == 'LS' else d[10 if wing == 'L' else 1]
    for n in (1, 3, 6, 12):
        x[f'pret_{n}m'] = (1 + y).rolling(n, min_periods=n).apply(np.prod, raw=True) - 1
        vals = []
        for i in range(len(dates)):
            if i < n: vals.append(np.nan); continue
            hist = dr.loc[(dr.index > dates[i - n]) & (dr.index <= dates[i])]
            vals.append(hist.std() if hist.notna().mean() > .80 else np.nan)
        x[f'std_{n}m'] = vals
    x['lag11_pret'] = (1 + y).shift(1).rolling(11, min_periods=11).apply(np.prod, raw=True) - 1
    for n in (12, 24, 36): x[f'mstd_{n}m'] = y.rolling(n, min_periods=n).std()
    turn = bundle['turnover'][key]
    # Sum the two leg turnovers for a one-long/one-short portfolio.
    tv = turn[:, 9] + turn[:, 0] if wing == 'LS' else turn[:, 9 if wing == 'L' else 0]
    x['tuov_1m'] = tv
    x['tuov_12m'] = pd.Series(tv, index=idx).rolling(12, min_periods=12).mean()
    assert len(x.columns) == 38
    # Predict target month t exclusively from information at formation t-1.
    return x.shift(1)

def macro_features(bundle):
    dates = bundle['dates']; idx = dates.to_period('M')
    base = CACHE / 'regime_long_history_20060101_v1'
    x = pd.DataFrame(index=idx); provenance = []
    for code in ('000001.SH', '000300.SH', '000905.SH', '399001.SZ', '399006.SZ'):
        fs = sorted((base / 'index_daily' / code).glob('*.parquet'))
        raw = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates('trade_date')
        raw.index = pd.to_datetime(raw.trade_date.astype(str)); raw = raw.sort_index()
        close = raw.close.reindex(bundle['calendar']).ffill()
        mc = close.reindex(dates); ret = mc.pct_change(fill_method=None)
        for n in (1, 3, 12):
            x[f'{code}_ret{n}m'] = (mc / mc.shift(n) - 1).to_numpy()
            v = close.pct_change(fill_method=None).rolling(n * 21, min_periods=n * 15).std()
            x[f'{code}_dvol{n}m'] = v.reindex(dates).to_numpy()
        for n in (12, 24, 36): x[f'{code}_mvol{n}m'] = ret.rolling(n, min_periods=n).std().to_numpy()
        provenance.extend(dict(path=str(f.relative_to(ROOT)), sha256=sha(f)) for f in fs)
    fred = ROOT / 'research_reports/platform_alignment/shu-mulvey-paper-replication-20261014/macro'
    for k in ('VIXCLS', 'DGS2', 'DGS10', 'DGS3MO'):
        fp = fred / f'{k}.csv'; raw = pd.read_csv(fp, parse_dates=['observation_date'])
        raw[k] = pd.to_numeric(raw[k], errors='coerce'); raw = raw.dropna(subset=[k]).sort_values('observation_date')
        observed = pd.merge_asof(pd.DataFrame({'cutoff': dates-pd.Timedelta(days=1)}),
                                 raw, left_on='cutoff', right_on='observation_date', direction='backward')
        assert (observed.observation_date < dates).all()
        x[k] = observed[k].to_numpy()
        provenance.append(dict(path=str(fp.relative_to(ROOT)), sha256=sha(fp)))
    x['US_yield_10_2'] = x.DGS10 - x.DGS2
    x['US_yield_10_3mo'] = x.DGS10 - x.DGS3MO
    # Shibor is observable daily; no GDP/CPI period-to-release-date shortcuts.
    fs = sorted((base / 'shibor').glob('*.parquet'))
    raw = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates('date')
    raw.index = pd.to_datetime(raw.date.astype(str)); raw = raw.sort_index()
    for k in ('on', '1w', '2w', '1m', '3m', '6m', '9m', '1y'):
        vals = raw[k].reindex(dates, method='ffill').to_numpy()
        x['shibor_' + k] = vals
    provenance.extend(dict(path=str(f.relative_to(ROOT)), sha256=sha(f)) for f in fs)
    ls = pd.DataFrame({k: target_returns(bundle, k, 'LS') for k in KEYS})
    # Fixed 24-factor equal aggregate requires all factor targets observed;
    # no dynamic replacement of unavailable factors or performance selection.
    avg = ls.mean(axis=1).where(ls.notna().all(axis=1))
    for n in (1, 3, 12):
        x[f'factor_mean_ret{n}m'] = (1 + avg).rolling(n, min_periods=n).apply(np.prod, raw=True) - 1
    for n in (3, 12, 36): x[f'factor_mean_mstd{n}m'] = avg.rolling(n, min_periods=n).std()
    x.to_csv(OUT / 'macro_observed_features.csv')
    dump(OUT / 'macro_manifest.json', dict(variables=len(x.columns), original_variables=178,
         replicated_original_count=None, source_files=provenance,
         limitations=[f'{len(x.columns)} local macro proxies, not the original 178 named series',
           'no original iFind release-vintage panel; no claimed Realtime/Announcement reproduction',
           'FRED US levels use prior-calendar-day observations; current downloaded vintages',
           'Chinese price indices rather than Datastream total returns',
           'rolling21/63/252 daily market volatility proxies; exact original horizons undocumented']))
    return x.shift(1)

def preprocess(x, y, test, names):
    """Fit missing-value replacement, screening, scaling on supplied train only."""
    keep = []; ps = []; correlations = []
    for j in range(x.shape[1]):
        ok = np.isfinite(x[:, j]) & np.isfinite(y)
        if ok.sum() < 24 or np.std(x[ok, j]) < 1e-12 or np.std(y[ok]) < 1e-12: continue
        r, p = pearsonr(x[ok, j], y[ok])
        if p <= .05: keep.append(j); ps.append(float(p)); correlations.append(float(r))
    if not keep:
        return np.zeros((len(y), 0)), np.zeros((len(test), 0)), [], []
    x = x[:, keep].copy(); test = test[:, keep].copy()
    median = np.nanmedian(x, axis=0)
    x = np.where(np.isfinite(x), x, median); test = np.where(np.isfinite(test), test, median)
    mu = x.mean(axis=0); sd = x.std(axis=0); sd[sd < 1e-12] = 1
    info = [dict(name=names[j], p=p, correlation=r, train_mean=float(m), train_sd=float(s))
            for j, p, r, m, s in zip(keep, ps, correlations, mu, sd)]
    return (x - mu) / sd, (test - mu) / sd, keep, info

def ols(x, y, test):
    beta = np.linalg.lstsq(np.c_[np.ones(len(x)), x], y, rcond=1e-10)[0]
    return np.c_[np.ones(len(test)), test] @ beta, beta[1:]

def single_forecasts(x, y, test):
    var = (x ** 2).mean(axis=0); cov = (x * (y - y.mean())[:, None]).mean(axis=0)
    beta = np.divide(cov, var, out=np.zeros_like(cov), where=var > 1e-12)
    return y.mean() + test * beta, y.mean() + x * beta

def estimate(model, x, y, test, param=None, lagy=None, testlag=None):
    if x.shape[1] == 0: return np.full(len(test), y.mean()), np.empty(0)
    if model == 'OLS': return ols(x, y, test)
    if model in ('PCA1_OLS', 'PCA1_VAR1', 'PC'):
        _, _, vh = np.linalg.svd(x, full_matrices=False)
        n = min(x.shape[1], 1 if model.startswith('PCA1') else int(param or 1))
        xx, tt = x @ vh[:n].T, test @ vh[:n].T
        if model == 'PCA1_VAR1':
            valid = np.isfinite(lagy)
            pred, coef = ols(np.c_[xx[valid], lagy[valid]], y[valid], np.c_[tt, testlag])
            return pred, vh[:n].T @ coef[:n]
        pred, coef = ols(xx, y, tt); return pred, vh[:n].T @ coef
    if model == 'PLS':
        m = PLSRegression(n_components=min(int(param or 1), x.shape[1], len(y) - 1), scale=False, max_iter=1000)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); m.fit(x, y)
        return m.predict(test).reshape(-1), np.asarray(m.coef_).reshape(-1)
    if model in ('ElasticNet', 'C_ENet'):
        alpha, mix = param or (.01, .5)
        trainx, testx = x, test
        if model == 'C_ENet':
            testx, trainx = single_forecasts(x, y, test)
            mu = trainx.mean(axis=0); sd = trainx.std(axis=0); sd[sd < 1e-12] = 1
            trainx = (trainx - mu) / sd; testx = (testx - mu) / sd
        sd_y = np.std(y) or 1.; mean_y = y.mean()
        m = ElasticNet(alpha=alpha, l1_ratio=mix, max_iter=5000, tol=1e-6)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', ConvergenceWarning); m.fit(trainx, (y - mean_y) / sd_y)
        return mean_y + sd_y * m.predict(testx), m.coef_ * sd_y
    if model == 'C_Simple':
        z, _ = single_forecasts(x, y, test); return z.mean(axis=1), np.full(x.shape[1], np.nan)
    if model == 'Predictor_Average':
        return ols(x.mean(axis=1)[:, None], y, test.mean(axis=1)[:, None])[0], np.full(x.shape[1], np.nan)
    raise ValueError(model)

def choose_param(model, raw, y, names):
    grid = [(a, b) for a in (.001, .01, .1) for b in (.1, .5, .9)] if model in ('ElasticNet', 'C_ENet') else [1, 2, 3, 4, 5]
    n = len(y); cuts = np.linspace(max(36, n // 2), n, 4, dtype=int)
    totals = np.zeros(len(grid)); count = 0
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b <= a: continue
        x, test, _, _ = preprocess(raw[:a], y[:a], raw[a:b], names)
        for j, param in enumerate(grid):
            pred, _ = estimate(model, x, y[:a], test, param)
            totals[j] += float(np.sum((y[a:b] - pred) ** 2))
        count += b - a
    return grid[int(np.argmin(totals))], dict(inner_count=count, candidates=len(grid),
                                            inner_msfe=float(np.min(totals) / max(count, 1)))

def cluster_predictions(x, y, test, k):
    true = np.empty(len(y), int)
    for label, ids in enumerate(np.array_split(np.argsort(y, kind='stable'), k)): true[ids] = label
    output = {}; ari = {}; assigned = {}
    if x.shape[1] == 0:
        return {m: float(y.mean()) for m in CLUSTERS}, {m: 0. for m in CLUSTERS}, {m: -1 for m in CLUSTERS}
    for name in CLUSTERS:
        if name == 'KMeans': model = KMeans(n_clusters=k, random_state=SEED, n_init=10)
        elif name == 'Birch': model = Birch(n_clusters=k, threshold=.5)
        elif name == 'GaussianMixture': model = GaussianMixture(n_components=k, random_state=SEED, reg_covar=1e-5, n_init=2)
        elif name == 'Spectral': model = SpectralClustering(n_clusters=k, random_state=SEED, affinity='nearest_neighbors', n_neighbors=min(10, len(y) - 1), assign_labels='kmeans', n_init=10)
        else: model = AgglomerativeClustering(n_clusters=k, linkage='ward')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); labels = model.fit_predict(x)
        if hasattr(model, 'predict'): label = int(model.predict(test)[0])
        else:
            labs = np.unique(labels); centers = np.stack([x[labels == j].mean(axis=0) for j in labs])
            label = int(labs[np.argmin(((centers - test[0]) ** 2).sum(axis=1))])
        output[name] = float(y[labels == label].mean())
        ari[name] = float(adjusted_rand_score(true, labels)); assigned[name] = label
    return output, ari, assigned

def forecast_one(bundle, key, wing, family, macro, do_clusters=False):
    path = OUT / 'forecasts' / f'{key}.{wing}.{family}.pkl'
    if path.exists(): return pd.read_pickle(path)
    y = target_returns(bundle, key, wing)
    features = portfolio_features(bundle, key, wing) if family == 'portfolio' else macro
    # Require at least half of the proxy predictors observable, without using
    # their p-values or future performance to select the start of the sample.
    usable = features.notna().sum(axis=1) >= len(features.columns) // 2
    usable &= y.notna() | (y.index == y.index[-1])
    data = features.loc[usable]; yy = y.reindex(data.index)
    paper = data.index <= pd.Period('2021-12', 'M')
    initial = max(60, int(np.floor(.60 * int(paper.sum()))))
    names = list(data.columns); rows = []; screening = []; tuning = []
    parameters = {}; tune_year = None
    for i in range(initial, len(data)):
        date = data.index[i]; train_mask = np.isfinite(yy.iloc[:i].to_numpy())
        tx = data.iloc[:i].to_numpy(float)[train_mask]; ty = yy.iloc[:i].to_numpy(float)[train_mask]
        rawtest = data.iloc[[i]].to_numpy(float)
        x, test, keep, details = preprocess(tx, ty, rawtest, names)
        for d in details: screening.append(dict(key=key, wing=wing, family=family, target_month=str(date), **d))
        pm = float(ty.mean())
        common = dict(key=key, wing=wing, family=family, target_month=str(date),
                      signal_date=str(bundle['dates'][bundle['dates'].to_period('M').get_loc(date) - 1].date()),
                      train_start=str(data.index[0]), train_end=str(data.index[i - 1]),
                      train_count=len(ty), selected=len(keep), actual=float(yy.iloc[i]), benchmark=pm,
                      partial=bool(bundle['partial_last_month'] and date == y.index[-1]))
        if do_clusters:
            for k in (2, 3, 4):
                preds, ari, assigned = cluster_predictions(x, ty, test, k)
                chosen = max(CLUSTERS, key=lambda m: ari[m])
                for model in CLUSTERS:
                    rows.append(dict(**common, model=f'{model}_K{k}', prediction=preds[model],
                                     cluster=assigned[model], ari=ari[model]))
                rows.append(dict(**common, model=f'ARI_Combination_K{k}', prediction=preds[chosen],
                                 chosen_model=chosen, cluster=assigned[chosen], ari=ari[chosen]))
            continue
        if tune_year != date.year:
            for model in ('ElasticNet', 'PC', 'PLS', 'C_ENet'):
                parameters[model], detail = choose_param(model, tx, ty, names)
                tuning.append(dict(key=key, wing=wing, family=family, target_month=str(date), model=model,
                                   train_end=common['train_end'], parameter=parameters[model], **detail))
            tune_year = date.year
        lag_all = y.shift(1).reindex(data.index).iloc[:i].to_numpy(float)[train_mask]
        testlag = y.shift(1).reindex([date]).to_numpy(float)
        # A missing prior monthly target is an explicit local fallback, never
        # filled from a later observed return.
        testlag = np.where(np.isfinite(testlag), testlag, pm)
        for model in MODELS:
            pred, coef = estimate(model, x, ty, test, parameters.get(model), lag_all, testlag)
            if not np.isfinite(pred).all(): raise ValueError(f'Invalid forecast {key} {date} {model}')
            rows.append(dict(**common, model=model, prediction=float(pred[0])))
            if model in ('ElasticNet', 'PC', 'PLS'):
                for d, c in zip(details, coef):
                    d = dict(d); screening.append(dict(key=key, wing=wing, family=family,
                       target_month=str(date), model=model, coefficient=float(c), **d))
    output = dict(rows=pd.DataFrame(rows), screening=pd.DataFrame(screening), tuning=pd.DataFrame(tuning),
                  sample_start=str(data.index[0]) if len(data) else None, initial_train=initial,
                  paper_available_months=int(paper.sum()))
    pd.to_pickle(output, path)
    print('WU_FORECAST', key, wing, family, 'clusters' if do_clusters else 'regression', len(rows), flush=True)
    return output

def accuracy(frame):
    d = frame.loc[~frame.partial & np.isfinite(frame.actual) & np.isfinite(frame.prediction)]
    if not len(d): return dict(n=0)
    actual, pred, pm = [d[k].to_numpy(float) for k in ('actual', 'prediction', 'benchmark')]
    e0 = actual - pm; e = actual - pred; adjusted = e0 ** 2 - e ** 2 + (pm - pred) ** 2
    den = np.mean(e0 ** 2); r2 = 1 - np.mean(e ** 2) / den if den else np.nan
    se = np.std(adjusted, ddof=1) / np.sqrt(len(d)); cw = adjusted.mean() / se if se else 0.
    hac = sm.OLS(adjusted, np.ones((len(d), 1))).fit(cov_type='HAC', cov_kwds={'maxlags': min(3, len(d) - 1)})
    return dict(n=len(d), r2_oos_pct=float(100 * r2), msfe=float(np.mean(e ** 2)),
                benchmark_msfe=float(den), cw_t=float(cw), cw_one_sided_p=float(norm.sf(cw)),
                cw_hac_t=float(hac.tvalues[0]), cw_hac_one_sided_p=float(norm.sf(hac.tvalues[0])),
                signal_accuracy=float(np.mean(np.sign(pred) == np.sign(actual))))

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--clusters', action='store_true')
    parser.add_argument('--keys', nargs='*'); parser.add_argument('--wings', nargs='*', default=['LS', 'L', 'S'])
    args = parser.parse_args(); (OUT / 'forecasts').mkdir(parents=True, exist_ok=True)
    bundle = pd.read_pickle(OUT / 'inputs.pkl'); macro = macro_features(bundle)
    allrows = []; screenings = []; tuning = []; coverage = []
    for key in args.keys or KEYS:
        for wing in args.wings:
            for family in (['macro_cluster'] if args.clusters else ['portfolio', 'macro']):
                output = forecast_one(bundle, key, wing, family, macro, args.clusters)
                allrows.append(output['rows']); screenings.append(output['screening']); tuning.append(output['tuning'])
                coverage.append(dict(key=key, wing=wing, family=family, **{k:output[k] for k in ['sample_start', 'initial_train', 'paper_available_months']}))
    prefix = 'cluster' if args.clusters else 'regression'
    rows = pd.concat(allrows, ignore_index=True); rows.to_csv(OUT / f'{prefix}_forecasts.csv', index=False)
    pd.concat(screenings, ignore_index=True).to_csv(OUT / f'{prefix}_screening.csv', index=False)
    pd.concat(tuning, ignore_index=True).to_csv(OUT / f'{prefix}_tuning.csv', index=False)
    pd.DataFrame(coverage).to_csv(OUT / f'{prefix}_coverage.csv', index=False)
    stats = []
    for group, d in rows.groupby(['key', 'wing', 'family', 'model']):
        for window, lo, hi in [('paper_overlap', '2000-01', '2021-12'),
                              ('five_year_months', '2021-09', '2026-09'), ('recent', '2026-01', '2026-09')]:
            dd = d[d.target_month.between(lo, hi)]
            stats.append(dict(zip(['key','wing','family','model'],group), window=window, **accuracy(dd)))
    pd.DataFrame(stats).to_csv(OUT / f'{prefix}_accuracy.csv', index=False)
    dump(OUT / f'{prefix}_protocol.json', dict(version=bundle['version'], input_sha256=sha(OUT / 'inputs.pkl'),
         paper='10.1002/ise3.86', original_numeric_replication=False, targets='24 paper-named factors x three portfolio targets',
         predictor_screen='Pearson two-sided p <= 0.05; supplied training labels only',
         missing='training median; current target never used', standardization='training mean/std only',
         initial_training='floor(60% of available proxy months ending 2021-12), min60; then expand',
         hyperparameter_selection='annual inner 3 chronological folds; all screening refit inside each fold; monthly final fits',
         original_model_settings_known=False,
         local_assumptions=['C-Simple equal mean of screened univariate OLS forecasts',
           'C-ENet elastic-net combination of univariate fitted forecasts; exact original combination convention unknown',
           'Predictor Average univariate OLS on mean standardized screened predictors; exact original convention unknown',
           'PCA1 VAR1 response equation with previous target return and first predictor PC',
           'ENet alpha 0.001/0.01/0.1, L1 mix0.1/0.5/0.9; PC/PLS components1..5',
           'Spectral/agglomerative new-point assignment to nearest training cluster centroid; paper does not specify extension',
           'fixed cluster counts2/3/4; KMeans n_init10; Birch threshold0.5; GMM full covariance reg1e-5',
           'ARI uses training return ranks only; ties stable by chronological order; deterministic fixed algorithm tie-break'],
         platform_compute_spent=0))
    print('WU_MODELS_COMPLETE', prefix, len(rows), flush=True)

if __name__ == '__main__': main()
