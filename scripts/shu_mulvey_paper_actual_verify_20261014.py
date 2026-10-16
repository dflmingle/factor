#!/usr/bin/env python3
"""Truncation/mutation and date checks on the real six-style input and paths."""
import json
import numpy as np
import pandas as pd
import shu_mulvey_paper_replication_20261014 as m


def main():
    bundle=pd.read_pickle(m.BASE/'inputs.pkl');r=bundle['gross_returns'];macro=bundle['macro']
    dates=r.index;cut=dates.searchsorted('2023-06-15');key='book_market';proto=m.Protocol()
    active=(r[key]-r.market).where(dates>=bundle['inceptions'][key])
    full=m.features(active,r.market,macro)
    trunc=m.features(active.iloc[:cut+1],r.market.iloc[:cut+1],macro.iloc[:cut+1])
    np.testing.assert_allclose(full.iloc[:cut+1],trunc,equal_nan=True,atol=1e-12)
    checks=[dict(test='real_input_features_prefix_recompute',passed=True)]
    cache=m.BASE/'models'/m.digest(m.BASE/'inputs.pkl')[:16]
    paths=[]
    for lam,kappa in proto.params:
        import hashlib
        name=hashlib.sha256(key.encode()).hexdigest()[:16]+f'-l{lam}-k{kappa}.pkl'
        paths.append(pd.read_pickle(cache/name)['path'])
    shorter=m.fit_path((key,dates[:cut+1],trunc.to_numpy(),active.iloc[:cut+1].to_numpy(),50.,9.5,proto))
    index=proto.params.index((50.,9.5))
    np.testing.assert_allclose(shorter['views'],paths[index]['views'][:cut+1],equal_nan=True,atol=1e-12)
    np.testing.assert_array_equal(shorter['states'],paths[index]['states'][:cut+1])
    checks.append(dict(test='real_book_market_monthly_SJM_truncated_recompute',passed=True))
    v,c,s,a=m.select_views(paths,dates,active.to_numpy(),proto)
    ap=active.to_numpy().copy();ap[cut+1:]=-.999
    vp,*_=m.select_views(paths,dates,ap,proto)
    np.testing.assert_allclose(vp[:cut+1],v[:cut+1],equal_nan=True,atol=1e-12)
    for row in a:
        if row['selected']>=0:
            assert row['full_six_year_eligible'][row['selected']]
            assert pd.Timestamp(row['validation_last_return'])<pd.Timestamp(row['selection_date'])
    checks.append(dict(test='real_six_year_selection_future_return_mutation_and_date_gate',passed=True))
    for path in paths:
        valid=path['source']>=0
        assert (dates[path['source'][valid]]<dates[valid]).all()
        for row in path['fits']:
            assert pd.Timestamp(row['last_training_date'])<pd.Timestamp(row['refit_date'])
            assert pd.Timestamp(row['first_training_date'])<=pd.Timestamp(row['refit_date'])-pd.DateOffset(years=8)
    checks.append(dict(test='real_training_dates_and_full_eight_year_calendar_coverage',passed=True))
    obs=pd.read_parquet(m.BASE/'macro_observation_dates.parquet')
    assert (obs.to_numpy()<np.array(obs.index)[:,None]).all()
    checks.append(dict(test='US_macro_observed_before_A_share_date',passed=True))
    data=m.BASE/'six_styles';keys=list(m.STYLE_KEYS.values())+['market'];asset=r[keys]
    views=pd.read_parquet(data/'daily_views.parquet');_,b,_,_=m.quarterly_benchmark(asset,.0005)
    for date in ['2022-04-15','2023-06-15','2025-05-15']:
        t=dates.searchsorted(date);cov,_=m.covariance(asset.iloc[:t+1],126)
        answers,_=m.bl_targets(cov,b[t],views.iloc[t].to_numpy(),[.01,.02,.03,.04])
        for te,w in answers.items():
            saved=pd.read_parquet(data/f'TE{int(te*100)}.signal_weights.parquet')
            np.testing.assert_allclose(saved.loc[dates[t]].to_numpy(),w,atol=1e-9)
    checks.append(dict(test='real_BL_allocation_recomputed_from_truncated_history',passed=True))
    for case,cost in [('paper_fee_proxy',.0005),('local_fee_proxy',.003)]:
        source=bundle['gross_returns'] if case=='paper_fee_proxy' else bundle['net_returns']
        weights=pd.read_parquet(data/'TE2.signal_weights.parquet');source=source[keys]
        _,bench,_,_=m.quarterly_benchmark(source,cost)
        start=dates.get_loc(weights.index[0]);end=dates.get_loc(weights.index[-1])
        pnl,fee,turn,executed=m.realized_portfolio(source.iloc[start:end+1],weights,cost,bench[start-1])
        saved=pd.read_csv(data/f'TE2.{case}.ledger.csv')
        np.testing.assert_allclose(pnl,saved.return_.to_numpy(),atol=1e-12)
        np.testing.assert_allclose(fee,saved.fee.to_numpy(),atol=1e-12)
        n=400
        short,*_=m.realized_portfolio(source.iloc[start:start+n],weights.iloc[:n],cost,bench[start-1])
        np.testing.assert_allclose(short,pnl[:n],atol=1e-12)
    checks.append(dict(test='real_delayed_portfolio_ledger_recompute_and_truncation',passed=True))
    m.dump(m.BASE/'actual_data_verification.json',dict(completed=True,tests=checks,
           boundary='model/allocation checks do not eliminate saved sleeve factor_valid/financial-vintage proxy limitations'))
    print('ACTUAL_INPUT_CHECKS_PASSED',len(checks),flush=True)


if __name__=='__main__':main()
