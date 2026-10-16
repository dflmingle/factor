#!/usr/bin/env python3
"""Audit all real factor training/validation and independent dated allocations."""
import hashlib
import json
import numpy as np
import pandas as pd
import shu_mulvey_paper_replication_20261014 as m


def main():
    folder=m.BASE/'all_replayed';bundle=pd.read_pickle(m.BASE/'inputs.pkl')
    returns=bundle['gross_returns'];dates=returns.index
    views=pd.read_parquet(folder/'daily_views.parquet')
    validation=json.loads((folder/'semiannual_validation.json').read_text());selections=0
    for key,rows in validation.items():
        for row in rows:
            if row['selected']<0:continue
            assert row['full_six_year_eligible'][row['selected']]
            assert pd.Timestamp(row['validation_last_return'])<pd.Timestamp(row['selection_date'])
            assert pd.Timestamp(row['validation_start'])==pd.Timestamp(row['selection_date'])-pd.DateOffset(years=6)
            selections+=1
    fits=json.loads((folder/'monthly_model_fits.json').read_text())
    for row in fits:
        refit=pd.Timestamp(row['refit_date']);first=pd.Timestamp(row['first_training_date']);last=pd.Timestamp(row['last_training_date'])
        assert last<refit
        assert first<=refit-pd.DateOffset(years=8)
        assert first>=refit-pd.DateOffset(years=12)
        assert row['training_days']>=1600
    allocation=pd.read_csv(folder/'allocation_audit.csv')
    assert (allocation.predicted_te<=allocation.target_te+1e-7).all()
    assert allocation.solver_success.all()
    _,benchmark,_,_=m.quarterly_benchmark(returns,.0005)
    for date in ['2022-04-15','2023-06-15','2025-05-15']:
        t=dates.searchsorted(date);cov,_=m.covariance(returns.iloc[:t+1],126)
        answers,_=m.bl_targets(cov,benchmark[t],views.iloc[t].to_numpy(),[.01,.02,.03,.04])
        for te,w in answers.items():
            stored=pd.read_parquet(folder/f'TE{int(te*100)}.signal_weights.parquet')
            np.testing.assert_allclose(stored.loc[dates[t]],w,atol=1e-8)
    for te in [1,2,3,4]:
        w=pd.read_parquet(folder/f'TE{te}.signal_weights.parquet')
        assert np.isfinite(w.to_numpy()).all() and w.to_numpy().min()>=0
        np.testing.assert_allclose(w.sum(axis=1),1.,atol=1e-10)
    for case,cost in [('paper_fee_proxy',.0005),('local_fee_proxy',.003)]:
        assets=bundle['gross_returns'] if case=='paper_fee_proxy' else bundle['net_returns']
        w=pd.read_parquet(folder/'TE2.signal_weights.parquet');start=dates.get_loc(w.index[0]);end=dates.get_loc(w.index[-1])
        _,b,_,_=m.quarterly_benchmark(assets,cost)
        pnl,fee,turn,_=m.realized_portfolio(assets.iloc[start:end+1],w,cost,b[start-1])
        stored=pd.read_csv(folder/f'TE2.{case}.ledger.csv')
        np.testing.assert_allclose(stored.return_,pnl,atol=1e-12)
        np.testing.assert_allclose(stored.fee,fee,atol=1e-12)
        prefix,*_=m.realized_portfolio(assets.iloc[start:start+500],w.iloc[:500],cost,b[start-1])
        np.testing.assert_allclose(prefix,pnl[:500],atol=1e-12)
    # Saved immutable input file provenance must survive this entire calculation.
    source=pd.read_csv(m.BASE/'sleeve_input_audit.csv')
    for row in source.itertuples():
        path=m.ROOT/row.period_path
        assert m.digest(path)==row.period_sha256
        nav=path.with_name(path.name.replace('.periods.csv','.daily_nav.csv'))
        assert m.digest(nav)==row.daily_sha256
    m.dump(m.BASE/'all_actual_data_verification.json',dict(completed=True,
       checks=['all eight-to-twelve-year fit dates','all full six-year daily validation selections',
               'all allocation predicted TE constraints','all long-only fully-invested weights',
               'three truncated-history BL recomputations','both cost ledgers and prefixes',
               'all353 source period/nav hashes unchanged'],
       fit_records=len(fits),validated_selections=selections,model_factors=len(views.columns),
       boundary='saved sleeves remain factor_valid/financial-vintage proxies; original US data missing'))
    print('ALL_REAL_AUDIT_PASSED',len(fits),selections,len(views.columns),flush=True)


if __name__=='__main__':main()
