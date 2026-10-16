#!/usr/bin/env python3
"""Economic/timing/algebraic tests for the paper implementation, no platform calls."""
from dataclasses import replace
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import shu_mulvey_paper_replication_20261014 as m


def main():
    m.BASE.mkdir(exist_ok=True,parents=True); checks=[]
    def record(name):checks.append(dict(test=name,passed=True));print('PASS',name,flush=True)
    m.install_verified_acceleration();record('author_dynamic_programming_equivalence_ties_unreachable_states')
    rng=np.random.default_rng(412)
    x=rng.normal(size=(1200,17));x[600:,0:5]+=2
    fitted=m.SparseJumpModel(n_components=2,jump_penalty=50,max_feats=9.5,random_state=47347).fit(x)
    weighted=x*np.asarray(fitted.feat_weights);centers=np.asarray(fitted.jm_ins.centers_)
    losses=.5*((weighted[:,None,:]-centers[None,:,:])**2).sum(axis=2)
    pen=fitted.jm_ins.jump_penalty_mx
    online=m.author_dp(losses,pen,True).argmin(axis=1)
    np.testing.assert_array_equal(online,np.asarray(fitted.predict_online(x)))
    # Continuing the final value vector is exactly the author's prefix inference.
    last=m.author_dp(losses[:900],pen,True)[-1].copy();continued=[]
    for loss in losses[900:]:
        last=loss+np.min(last[:,None]+pen,axis=0);continued.append(last.argmin())
    np.testing.assert_array_equal(continued,online[900:]);record('incremental_online_matches_author_predict_online')
    # Signal at t=0 does not own t=1's 100% rally; it owns t=2's 10% rally.
    returns=np.array([[0.,0.],[1.,0.],[.1,0.],[0.,0.]])
    signals=np.tile([1.,0.],(4,1))
    pnl,fee,turn,executed=m.realized_portfolio(returns,signals,0.,[0.,1.])
    np.testing.assert_allclose(pnl,[0.,0.,.1,0.]);record('next_day_close_execution_no_same_day_or_next_day_return')
    views=np.array([.05/252,.05/252,-.05/252,-.05/252,0.])
    ret,pos,fee=m.timing_returns(views,np.zeros(5),.0005)
    np.testing.assert_allclose(pos,[0.,0.,1.,1.,-1.])
    assert abs(fee[3]-.002)<1e-12;record('hypothetical_timing_both_legs_and_200pct_flip_cost')
    dates=pd.bdate_range('2020-01-01',periods=150)
    assets=pd.DataFrame(np.tile([.001,0.],(len(dates),1)),index=dates)
    _,b,_,t=m.quarterly_benchmark(assets,0.)
    assert b[20,0]>.5 and b[20,1]<.5
    firstq=np.flatnonzero(dates.to_period('Q')!=dates[0].to_period('Q'))[0]
    np.testing.assert_allclose(b[firstq],[.5,.5]);record('quarterly_ew_drifts_between_rebalances')
    z=rng.normal(size=(1000,7))*.007+np.outer(rng.normal(size=1000)*.01,np.ones(7))
    cov,jitter=m.covariance(z);benchmark=np.ones(7)/7;p=np.column_stack([np.eye(6),-np.ones(6)])
    pi=2.5*cov@benchmark;v=p@pi+np.array([1,-1,1,-1,1,-1])*1e-5;c=20.
    mu=m.posterior(cov,benchmark,v,2.5,c)
    lam=np.linalg.solve(p@cov@p.T+c*np.diag(np.diag(p@cov@p.T)),v-p@pi)/2.5
    closed=benchmark+p.T@lam
    np.testing.assert_allclose(np.linalg.solve(2.5*cov,mu),closed,atol=1e-12)
    assert closed.min()>0
    trial=minimize(lambda w:252*(2.5/2*w@cov@w-mu@w),benchmark,
         jac=lambda w:252*(2.5*cov@w-mu),method='SLSQP',bounds=[(0,1)]*7,
         constraints={'type':'eq','fun':lambda w:w.sum()-1},options={'ftol':1e-15,'maxiter':500})
    assert trial.success;np.testing.assert_allclose(trial.x,closed,atol=1e-5)
    record('appendix_B_BL_closed_form_matches_independent_constrained_optimizer')
    answers,audits=m.bl_targets(cov,benchmark,np.array([.001,-.001,.0001,-.0001,0.,.00005]),[.01,.02,.03,.04])
    for te,w in answers.items():
        assert w.min()>=0 and abs(w.sum()-1)<1e-10 and audits[te]['predicted_te']<=te+1e-7
    record('long_only_full_investment_TE_constraints_without_weight_cap')
    large=rng.normal(size=(1000,21))*.01
    covlarge,_=m.covariance(large);blarge=np.ones(21)/21
    plarge=np.column_stack([np.eye(20),-np.ones(20)])
    vlarge=plarge@(2.5*covlarge@blarge)+rng.normal(0,1e-6,20)
    targets,logs=m.bl_targets(covlarge,blarge,vlarge,[1.])
    mu=m.posterior(covlarge,blarge,vlarge,2.5,logs[1.]['confidence_inverse'])
    independent=minimize(lambda w:252*(2.5/2*w@covlarge@w-mu@w),blarge,
       jac=lambda w:252*(2.5*covlarge@w-mu),method='SLSQP',bounds=[(0,1)]*21,
       constraints={'type':'eq','fun':lambda w:w.sum()-1},options={'ftol':1e-14,'maxiter':1000})
    assert independent.success
    np.testing.assert_allclose(targets[1.],independent.x,atol=2e-6)
    record('large_universe_OSQP_and_spectral_BL_match_independent_optimizer')
    # Six complete calendar years of realized timing returns are required.
    dates=pd.bdate_range('2000-01-03','2018-12-31');a=rng.normal(.0001,.005,len(dates))
    v=np.full(len(dates),.0001);v[dates<'2008-01-01']=np.nan
    paths=[dict(views=v,states=np.zeros(len(v),int))]
    out,choices,states,audit=m.select_views(paths,dates,a,m.Protocol())
    assert np.isnan(out[dates<'2014-07-01']).all() and np.isfinite(out[dates>='2014-07-01']).all()
    stop=dates.searchsorted('2016-03-15')
    changed=a.copy();changed[stop+1:]=-.99
    vr,*_=m.select_views(paths,dates,changed,m.Protocol())
    np.testing.assert_allclose(vr[:stop+1],out[:stop+1],equal_nan=True)
    short=[dict(views=v[:stop+1],states=np.zeros(stop+1,int))]
    trunc,*_=m.select_views(short,dates[:stop+1],a[:stop+1],m.Protocol())
    np.testing.assert_allclose(trunc,out[:stop+1],equal_nan=True)
    record('full_six_year_validation_gate_and_future_mutation_truncation')
    # Reject original-data claims when a proxy manifest or ETF substitutes are supplied.
    rejected=False
    try:m.original_data_gate({'mode':'a_share_method_proxy'},assets)
    except ValueError:rejected=True
    assert rejected;record('proxy_cannot_pass_original_Bloomberg_data_gate')
    # The rolling model itself must survive truncation and future mutation.
    dates=pd.bdate_range('2000-01-03','2009-04-30')
    x=rng.normal(size=(len(dates),17));a=.001*x[:,0]+rng.normal(0,.003,len(dates))
    proto=replace(m.Protocol(),params=((50.,9.5),))
    full=m.fit_path(('causal_test',dates,x,a,50.,9.5,proto))
    stop=dates.searchsorted('2008-06-17');xm=x.copy();am=a.copy();xm[stop+1:]=123.;am[stop+1:]=-.9
    perturbed=m.fit_path(('causal_test',dates,xm,am,50.,9.5,proto))
    truncated=m.fit_path(('causal_test',dates[:stop+1],x[:stop+1],a[:stop+1],50.,9.5,proto))
    np.testing.assert_allclose(full['views'][:stop+1],perturbed['views'][:stop+1],equal_nan=True)
    np.testing.assert_allclose(full['views'][:stop+1],truncated['views'],equal_nan=True)
    record('monthly_SJM_refit_future_mutation_and_truncated_recompute')
    m.dump(m.BASE/'unit_verification.json',dict(completed=True,tests=checks))


if __name__=='__main__':main()
