"""Fixed offline add/swap test of the platform-verified three-control signal."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
from dataclasses import asdict
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import simultaneous_residual
from quant_corpus_correlations_20261012 import rho_details
from platform_aligned_factor_compare import read_platform_run
import platform_score_rules as sr

OUT=q.ROOT/'research_reports/platform_alignment/revenue-seasonal-pool-20261014'
SOURCE=q.ROOT/'research_reports/platform_alignment/revenue-seasonal-platform-20261014'
POOL=['size_only','impact60','t10_size_plus_impact_bm','book_to_market_lf_minus_size','book_to_market_lf_plus_impact']

def normalize(x):
    frame=pd.DataFrame(x);lo=frame.quantile(.01,axis=1);hi=frame.quantile(.99,axis=1)
    clipped=frame.clip(lo,hi,axis=0);sd=clipped.std(axis=1,ddof=0)
    return clipped.sub(clipped.mean(axis=1),axis=0).div(sd.where(sd>1e-12),axis=0).to_numpy()

def monthly(periods,daily,cal):
    nav=daily.set_index('date')[['nav','benchmark_nav']]
    # Saved dates can have gaps; hold cash between completed ten-day periods.
    nav=nav.reindex(cal[(cal>=nav.index.min())&(cal<=nav.index.max())]).ffill()
    returns=nav.pct_change(fill_method=None).fillna(0);rows=[]
    for period,g in returns.groupby(returns.index.to_period('M')):
        p=g.nav.to_numpy();b=g.benchmark_nav.to_numpy();n=len(g)
        ledger=periods[periods.date.dt.to_period('M').eq(period)]
        std=p.std(ddof=1);sharpe=p.mean()/std*np.sqrt(252) if std>0 else 0
        rex=np.prod(1+p)**(252/n)-np.prod(1+b)**(252/n)
        dd=q.maxdd(np.r_[1.,np.cumprod(1+p)]);turn=ledger.turnover.sum()
        raw=sr.raw_c_value(annual_excess_return=rex,annual_sharpe=sharpe,monthly_turnover=turn,monthly_max_drawdown=dd,sample_count=len(ledger))
        rows.append(dict(month=str(period),days=n,sample_count=len(ledger),rex=rex,sharpe=sharpe,dd=dd,
            E=max(rex,0)*sharpe*(1-1.2*dd),T=turn,raw_c=raw,NC=sr.score_nc(raw)))
    return pd.DataFrame(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    q.dump(OUT/'frozen_plan.json',dict(candidate='F-Q141014-07',scenarios=['base_native','base_shared','add6']+['swap_'+k for k in POOL],
        purpose='same-support add/swap marginal effects; separate support restriction effect',platform_compute=0,
        window=['20210907','20260907'],recent_start='20260101',normalization='per-date1/99 winsor+population zscore; stored old scores already normalized',
        missing='require all original five plus candidate for paired support; no skip-NaN averaging',direction=1,weight='equal',
        rule=q.ALIGNMENT_RULE_VERSION+'-seasonal-pool-arithmetic-fullA',score_rule=sr.SCORE_RULE_VERSION,not_untouched_OOS=True))
    cal,stocks,f=q.load_market();q.dates_all=cal
    state=json.loads((SOURCE/'budget14-control3-candidates.txt.state.json').read_text());entry=next(iter(state.values()))
    platform=read_platform_run(SOURCE/entry['raw_result']);dates=pd.DatetimeIndex(platform['dates']);pos=cal.get_indexer(dates)
    canddata=pd.read_parquet(SOURCE/'seasonal_revenue_control3_daily.parquet')
    cand=canddata.pivot(index='date',columns='symbol',values='value').reindex(index=dates,columns=stocks).to_numpy()
    sf,_,_,_=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl')
    built=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl')
    panels=[]
    for key in POOL:
        frame=sf[['date','instrument']].copy();frame['date']=pd.to_datetime(frame.date);frame['value']=built['scores'][key].to_numpy()
        panels.append(frame.pivot(index='date',columns='instrument',values='value').reindex(index=dates,columns=stocks).to_numpy())
    cz=normalize(cand)
    assert np.allclose(cz[:79],normalize(cand[:79]),equal_nan=True)
    base=sum(panels)/5;common=np.isfinite(cand)&np.isfinite(base)
    score={'base_native':base,'base_shared':np.where(common,base,np.nan),'add6':np.where(common,(sum(panels)+cz)/6,np.nan)}
    for key,v in zip(POOL,panels):score['swap_'+key]=np.where(common,(sum(panels)-v+cz)/5,np.nan)
    cand_si=sr.seat_stats(platform['rank_ic_values']);q.dump(OUT/'candidate_platform_seat_stats.json',asdict(cand_si))
    details=json.loads((q.ROOT/'research_reports/platform_alignment/board-peer-reconstruction-20261012/public_player_details.json').read_text())
    profile=next(x for x in details if x['display_name']=='ddd' and x['period']=='2026-10')
    seats=profile['data']['factor_pool_details']
    si={sr.LOCAL_SEAT_COLUMNS[x['factor_name']]:float(x['s_i_a']) for x in seats}
    assert set(si)==set(POOL)
    q.dump(OUT/'seat_source.json',dict(seats=POOL,normalization_source='pool-extended-search-20260922 stored competition scores',
        historical_current_membership_evidence='board-peer-reconstruction-20261012: mingle, five unchanged legacy seats',
        A_basis='saved October platform profile, rawA=.0258928; never old local built si',seat_si=si,
        source_proxy='legacy local seat reconstruction; not live platform pool holdings byte equality',data_latest=str(cal.max())))
    corrrows=[dict(seat=k,scope='120_saved_platform_signal_dates',**rho_details(cand,v)) for k,v in zip(POOL,panels)]
    pd.DataFrame(corrrows).to_csv(OUT/'seat_correlations.csv',index=False)
    rows=[];months=[]
    for window,mask in [('five_year',np.ones(len(dates),bool)),('recent',dates>='20260101')]:
        results={}
        for name,x in score.items():
            a,p,d=q.evaluate(x[mask],dates[mask],stocks,pos[mask],f)
            assert len(p)==int(mask.sum())
            # A separate size-rank residual diagnostic, not the actual portfolio.
            neutral=simultaneous_residual(x[mask],[-f['cap'][pos[mask]]])
            na,_,_=q.evaluate(neutral,dates[mask],stocks,pos[mask],f)
            rho=rho_details(x[mask],-f['cap'][pos[mask]])['rho']
            a.update(size_rank_residual_net=na['net_excess_pct'],corr_smallsize=rho)
            mt=monthly(p,d,cal);results[name]=(a,p,d,mt)
            folder=OUT/window;folder.mkdir(exist_ok=True)
            q.dump(folder/f'{name}.json',a);p.to_csv(folder/f'{name}.periods.csv',index=False);d.to_csv(folder/f'{name}.daily_nav.csv',index=False)
            mt.to_csv(folder/f'{name}.monthly.csv',index=False)
            baseline=results['base_shared' if name not in ['base_native','base_shared'] else 'base_native']
            ref,_,_,bmt=baseline
            removed=name.removeprefix('swap_') if name.startswith('swap_') else None
            bridge=sr.seat_change_bridge(si.values(),added=cand_si.s_i_a if name=='add6' or removed else None,
                removed=si[removed] if removed else None,pool_age_months=1,nb_active=True)
            paired=bmt.merge(mt,on='month',suffixes=('_base','_new'))
            for term in ['E','T','NC']:paired['delta_'+term]=paired[term+'_new']-paired[term+'_base']
            paired['delta_A_points']=bridge.points_na
            paired['delta_B_steady_proxy_points']=bridge.points_nb_steady
            paired['delta_C_points']=paired.delta_NC*19800
            paired['delta_Comb_AC_points']=bridge.points_na+paired.delta_C_points
            paired['delta_Comb_ABsteadyC_proxy_points']=paired.delta_Comb_AC_points+bridge.points_nb_steady
            paired.to_csv(folder/f'{name}.monthly_delta.csv',index=False)
            for row in paired.to_dict('records'):months.append(dict(window=window,scenario=name,**row))
            row=dict(window=window,scenario=name,baseline='base_shared' if name not in ['base_native','base_shared'] else 'base_native',
                **{k:a[k] for k in ['periods','net_excess_pct','gross_excess_pct','turnover_pct','held_daily_max_drawdown_pct','rank_ic','size_rank_residual_net','corr_smallsize']},
                delta_net_pp=a['net_excess_pct']-ref['net_excess_pct'],delta_dd_pp=a['held_daily_max_drawdown_pct']-ref['held_daily_max_drawdown_pct'],
                delta_turn_pp=a['turnover_pct']-ref['turnover_pct'],delta_size_residual_pp=a['size_rank_residual_net']-ref['size_rank_residual_net'],
                size_guard=abs(rho)<=abs(ref['corr_smallsize'])+1e-9 and a['size_rank_residual_net']>=ref['size_rank_residual_net']-1e-9,
                delta_E_mean=paired.delta_E.mean(),delta_T_month_mean=paired.delta_T.mean(),delta_NC_mean=paired.delta_NC.mean(),
                delta_A_points=bridge.points_na,delta_B_steady_proxy_points=bridge.points_nb_steady,
                delta_C_points_mean=paired.delta_C_points.mean(),delta_Comb_AC_points_mean=paired.delta_Comb_AC_points.mean(),
                delta_Comb_ABsteadyC_proxy_points_mean=paired.delta_Comb_ABsteadyC_proxy_points.mean(),
                months=len(paired),negative_AC_month_share=(paired.delta_Comb_AC_points<0).mean())
            rows.append(row);print(window,name,round(row['net_excess_pct'],3),round(row['delta_net_pp'],3),round(row['delta_dd_pp'],3),'AC',round(row['delta_Comb_AC_points_mean']),flush=True)
    pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False);pd.DataFrame(months).to_csv(OUT/'monthly_deltas.csv',index=False)
    q.dump(OUT/'verification.json',dict(cross_section_prefix_pass=True,all_scenarios_same120_and_recent15=True,
        platform_compute_spent=0,fullA=True,label_offset=1,one_way_cost=.003,
        no_formal_pool_changes=True,all_results_saved=True,monthly_NB='steady proxy only; no real future NB projection'))

if __name__=='__main__':main()
