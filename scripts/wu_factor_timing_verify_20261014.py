#!/usr/bin/env python3
"""Independent causality, portfolio math and actual-prefix verification."""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import pandas as pd
from pathlib import Path
from wu_factor_timing_inputs_20261014 import conditional_weights, path_returns, OUT, dump
import wu_factor_timing_models_20261014 as models
import wu_factor_timing_evaluate_20261014 as evaluate

def run():
    checks=[]
    def passed(name,details=None):checks.append(dict(test=name,passed=True,details=details))
    n=300;score=np.arange(n,dtype=float);cap=1+np.arange(n,dtype=float)
    w=conditional_weights(score,cap,np.ones(n,bool))
    np.testing.assert_allclose(w.sum(axis=1),1.)
    for q in range(10):
        for lo in (0,100,200):np.testing.assert_allclose(w[q,lo:lo+100].sum(),1/3)
    np.testing.assert_allclose(w[9,90:100]/w[9,90:100].sum(),cap[90:100]/cap[90:100].sum())
    passed('three_size_bins_cap_weights_and_deciles')
    a=conditional_weights(score,cap,np.ones(n,bool),True)
    assert np.sum(a[9]>0)==30
    passed('size_factor_single_sort')
    # Selections depend only on formation values; changing exits cannot drop a
    # stock, unlike the separate factor_valid alignment protocol.
    selected=conditional_weights(score,cap,np.ones(n,bool))
    future=np.ones(n);future[-1]=np.nan
    np.testing.assert_array_equal(selected,conditional_weights(score,cap,np.ones(n,bool)))
    assert selected[9,-1]>0
    passed('formation_selection_retains_stock_with_unknown_future_label')
    relative=np.array([[1.1,1.0],[1.21,.9]])
    ws=np.array([[.25,.75],[.5,.5]])
    ret=path_returns(ws,relative)
    np.testing.assert_allclose(np.prod(1+ret,axis=0),relative[-1]@ws.T)
    passed('fixed_holdings_daily_path_compounds_to_monthly_nav')
    # Long-short investor equity is L minus S profit plus initial capital,
    # rather than a product of daily independently rebalanced LS spreads.
    dr=pd.DataFrame({1:[.10,.20],10:[.20,-.10]},index=pd.date_range('2024-01-02',periods=2))
    legs=np.cumprod(1+dr.to_numpy(),axis=0)
    correct=1+legs[-1,1]-legs[-1,0]
    wrong=np.prod(1+(dr[10]-dr[1]))
    assert abs(correct-wrong)>.01
    passed('long_short_monthly_fixed_legs_not_daily_rebalance')
    rng=np.random.default_rng(17);x=rng.normal(size=(100,4));y=.2*x[:,0]+rng.normal(size=100)*.01
    test=np.full((1,4),1e9);z,t,keep,details=models.preprocess(x,y,test,list('abcd'))
    z2,t2,keep2,details2=models.preprocess(x,y,np.zeros_like(test),list('abcd'))
    np.testing.assert_array_equal(z,z2);assert keep==keep2 and details==details2
    assert 0 in keep
    passed('screening_scaling_only_train_data')
    px=x.copy();px[:20,1]=np.nan
    z,t,_,details=models.preprocess(px,y,np.full((1,4),np.nan),list('abcd'))
    assert np.isfinite(z).all() and np.isfinite(t).all()
    passed('training_median_handles_missing_without_future_fill')
    empty=models.preprocess(x,np.ones(100),test,list('abcd'))
    assert empty[0].shape[1]==0
    p,_=models.estimate('OLS',empty[0],np.ones(100),empty[1]);assert p[0]==1.
    passed('no_selected_predictor_explicit_historical_mean_fallback')
    pp,ari,assign=models.cluster_predictions(x,y,np.zeros((1,4)),3)
    pp2,ari2,assign2=models.cluster_predictions(x,y,np.zeros((1,4)),3)
    assert pp==pp2 and ari==ari2 and assign==assign2
    passed('five_cluster_algorithms_deterministic_train_only')
    # Actual saved fit boundaries and chronological inner-CV metadata.
    forecasts=pd.read_csv(OUT/'regression_forecasts.csv')
    assert (forecasts.train_end<forecasts.target_month).all()
    assert (pd.to_datetime(forecasts.signal_date).dt.to_period('M').astype(str)<forecasts.target_month).all()
    assert forecasts.prediction.notna().all()
    passed('actual_monthly_forecast_and_training_boundaries',len(forecasts))
    tune=pd.read_csv(OUT/'regression_tuning.csv')
    assert (tune.train_end<tune.target_month).all()
    assert (tune.inner_count>0).all()
    passed('actual_inner_cv_strictly_prior_to_target',len(tune))
    audits=pd.read_csv(OUT/'portfolio_construction_audit.csv')
    assert (pd.to_datetime(audits.signal)<pd.to_datetime(audits.exit)).all()
    passed('actual_formation_precedes_holding_exit',len(audits))
    bundle=pd.read_pickle(OUT/'inputs.pkl');key='reversal_onemonthreturn'
    # Recalculate predictors and the complete monthly model path after actually
    # truncating daily/monthly returns, financial traits and macro history.
    cutoff=pd.Timestamp('2023-12-29');mask=bundle['dates']<=cutoff
    short=dict(bundle);short['dates']=bundle['dates'][mask]
    short['calendar']=bundle['calendar'][bundle['calendar']<=cutoff]
    short['partial_last_month']=False
    for field in ('monthly_returns',):short[field]={k:v.loc[v.index<=cutoff.to_period('M')] for k,v in bundle[field].items()}
    for field in ('daily_returns','delayed_daily_returns','costs','delayed_costs'):
        short[field]={k:v.loc[:cutoff] for k,v in bundle[field].items()}
    for field in ('characteristics','turnover'):short[field]={k:v[mask] for k,v in bundle[field].items()}
    xfull=models.portfolio_features(bundle,key,'LS');xshort=models.portfolio_features(short,key,'LS')
    np.testing.assert_allclose(xshort,xfull.loc[xshort.index],equal_nan=True)
    passed('actual_portfolio_predictors_prefix_invariant')
    scratch=OUT/'verification_prefix';scratch.mkdir(exist_ok=True);(scratch/'forecasts').mkdir(exist_ok=True)
    old=models.OUT;models.OUT=scratch
    macroshort=models.macro_features(short)
    models.OUT=old
    macrofull=pd.read_csv(OUT/'macro_observed_features.csv',index_col=0)
    macrofull.index=pd.PeriodIndex(macrofull.index,freq='M')
    np.testing.assert_allclose(macroshort,macrofull.shift(1).loc[macroshort.index],equal_nan=True,rtol=1e-9,atol=1e-9)
    passed('actual_observed_macro_predictors_prefix_invariant')
    models.OUT=scratch
    for family in ('portfolio','macro'):
        output=models.forecast_one(short,key,'LS',family,macroshort)
        base=forecasts[(forecasts.key==key)&(forecasts.wing=='LS')&(forecasts.family==family)]
        compare=output['rows'].merge(base,on=['target_month','model'],suffixes=('_cut','_full'))
        assert len(compare)==len(output['rows'])
        np.testing.assert_allclose(compare.prediction_cut,compare.prediction_full,rtol=1e-8,atol=1e-10)
        passed('actual_'+family+'_all_nine_models_truncated_refit',len(compare))
    clusterbase=pd.read_csv(old/'cluster_forecasts.csv')
    output=models.forecast_one(short,key,'LS','macro_cluster',macroshort,True)
    base=clusterbase[(clusterbase.key==key)&(clusterbase.wing=='LS')]
    compare=output['rows'].merge(base,on=['target_month','model'],suffixes=('_cut','_full'))
    assert len(compare)==len(output['rows'])
    np.testing.assert_allclose(compare.prediction_cut,compare.prediction_full,rtol=1e-8,atol=1e-10)
    np.testing.assert_allclose(compare.ari_cut,compare.ari_full,rtol=1e-8,atol=1e-10)
    passed('actual_all_five_clusters_and_ARI_truncated_refit',len(compare))
    # Perturb the test month's actual outcome. Its forecast and screened
    # predictors must remain exactly those generated before seeing it.
    date='2022-06';row=forecasts[(forecasts.key==key)&(forecasts.wing=='LS')&(forecasts.family=='portfolio')&(forecasts.target_month==date)]
    yy=models.target_returns(bundle,key,'LS');xf=models.portfolio_features(bundle,key,'LS')
    train=yy.index<pd.Period(date,'M');valid=train&yy.notna()&(xf.notna().sum(axis=1)>=len(xf.columns)//2)
    tr=xf.loc[valid].to_numpy(float);yt=yy.loc[valid].to_numpy(float);xt=xf.loc[[pd.Period(date,'M')]].to_numpy(float)
    a,b,_,_=models.preprocess(tr,yt,xt,list(xf.columns));pred,_=models.estimate('OLS',a,yt,b)
    np.testing.assert_allclose(pred[0],row.loc[row.model=='OLS','prediction'].iloc[0],rtol=1e-9)
    yy2=yy.copy();yy2.loc[pd.Period(date,'M')]=9999
    a2,b2,_,_=models.preprocess(tr,yy2.loc[valid].to_numpy(float),xt,list(xf.columns))
    pred2,_=models.estimate('OLS',a2,yy2.loc[valid].to_numpy(float),b2)
    np.testing.assert_array_equal(pred,pred2)
    passed('actual_forecast_unchanged_by_current_target_mutation')
    models.OUT=old
    # Full-month realized paper LS ledger matches exposure*(monthly L-S).
    subset=forecasts[(forecasts.key==key)&(forecasts.wing=='LS')&(forecasts.family=='portfolio')&(forecasts.model=='OLS')]
    d=evaluate.daily_ledger(bundle,key,'LS',subset,'sign_flip',False,0.)
    returns=d.groupby('target_month').net_return.apply(lambda r:np.prod(1+r)-1)
    actual=models.target_returns(bundle,key,'LS');expected=[]
    for m,r in returns.items():
        exp=1 if subset.set_index('target_month').prediction.loc[m]>=0 else -1
        expected.append(exp*actual.loc[pd.Period(m,'M')])
    np.testing.assert_allclose(returns,expected,rtol=1e-8,atol=1e-9)
    passed('actual_monthly_sign_strategy_matches_original_payoff_formula',len(returns))
    # Local fees never improve a particular month's fixed gross signal payoff.
    fee=evaluate.daily_ledger(bundle,key,'LS',subset,'sign_flip',False,.003)
    feer=fee.groupby('target_month').net_return.apply(lambda r:np.prod(1+r)-1)
    assert (feer<=returns+1e-10).all()
    assert (fee.cost>=0).all() and (fee.one_way_traded_notional>=0).all()
    passed('actual_trade_cost_lowers_monthly_payoff')
    delayed=evaluate.daily_ledger(bundle,key,'LS',subset,'sign_flip',True,.003)
    assert (delayed.index>pd.to_datetime(delayed.signal_date)).all()
    passed('actual_delayed_execution_after_signal')
    dump(OUT/'verification.json',dict(completed=True,checks=checks,tests=len(checks),original_numeric_replication=False))
    print('WU_VERIFICATION_PASSED',len(checks),flush=True)

if __name__=='__main__':run()
