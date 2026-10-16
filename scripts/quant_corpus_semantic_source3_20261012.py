#!/usr/bin/env python3
"""Source3: causal KAMA and two distinct RSRS recipes. Offline only."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_semantic_local_20261012 import dual_residual
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source3-20261012'
VERSION=q.ALIGNMENT_RULE_VERSION+'-quant-source3-user-arithmetic-fullA'

@njit(cache=True)
def kama50(c):
    out=np.full(c.shape,np.nan,np.float32)
    for j in range(c.shape[1]):
        for t in range(49,c.shape[0]):
            w=c[t-49:t+1,j]
            valid=True
            for k in range(50):
                if not np.isfinite(w[k]):valid=False
            if not valid:continue
            prev=w[14]
            tail=np.empty(15,np.float64)
            before=prev
            for k in range(15,50):
                volatility=0.
                for z in range(k-14,k+1):volatility+=abs(w[z]-w[z-1])
                change=abs(w[k]-w[k-15])
                er=change/volatility if volatility>0 else 1.
                sc=(er*(2./3.-2./31.)+2./31.)**2
                before=prev
                prev+=sc*(w[k]-prev)
                if k>=35:tail[k-35]=prev
            sigma=np.std(tail)
            if sigma>1e-12:out[t,j]=(prev-before)/sigma
    return out

def recipe(key,f):
    c=f['close'].astype(float)
    if key=='kama15_slope50':return kama50(c)
    lo=pd.DataFrame(f['low'].astype(float));hi=pd.DataFrame(f['high'].astype(float))
    if key=='rsrs18_z480':
        cov=lo.rolling(18).cov(hi).to_numpy();var=lo.rolling(18).var().to_numpy()
        beta=q.ratio(cov,var)
        return q.ratio(beta-q.rolling(beta,480),pd.DataFrame(beta).rolling(480).std(ddof=1).to_numpy())
    if key=='rsrs18_wls_right200':
        v=pd.DataFrame(f['volume'].astype(float));n=18
        def total(x):return x.rolling(n).sum()
        sw=total(v);mx=total(v*lo)/sw;my=total(v*hi)/sw
        vx=total(v*lo*lo)/sw-mx*mx;vy=total(v*hi*hi)/sw-my*my
        cov=total(v*lo*hi)/sw-mx*my
        beta=(cov/vx).where((vx>1e-12)&(sw>0)).to_numpy()
        r2=(cov*cov/(vx*vy)).where((vx>1e-12)&(vy>1e-12)).clip(0,1).to_numpy()
        z=q.ratio(beta-q.rolling(beta,200),pd.DataFrame(beta).rolling(200).std(ddof=0).to_numpy())
        return (z*beta*r2).astype(np.float32)
    raise KeyError(key)

SPECS=[
('kama15_slope50','KAMA15归一化斜率','2020年度精选策略','01 ','(KAMA15_50bar_t-KAMA15_50bar_t-1)/STD15(KAMA15_50bar,ddof0)','stock adaptation; KAMA resets on each 50-bar slice; continuous score extracts source +/-0.3 deadband input; no ATR sizing/CTA execution'),
('rsrs18_z480','RSRS18标准分480','2020年度精选策略','93 ','z480(beta18,ddof1), beta18=COV18(H,L)/VAR18(L)','daily stock proxy for index timing; no beta/R2 multiply'),
('rsrs18_wls_right200','成交量加权RSRS18右偏200','2021年度精选策略','67.','z200(WLS18_beta,ddof0)*WLS18_beta*WLS18_R2; weights=volume/sum18(volume)','daily stock proxy for index timing; source active signal is rightdev, passivation formulas are unused')]

def verify(f,calendar):
    import statsmodels.api as sm
    idx=np.flatnonzero(np.isfinite(f['low'][-700:]).all(axis=0)&np.isfinite(f['high'][-700:]).all(axis=0)&np.isfinite(f['volume'][-700:]).all(axis=0))[:4]
    small={k:v[:,idx] for k,v in f.items()};checks=[]
    for key,*_ in SPECS:
        full=recipe(key,small)
        for stop in [1000,1500,len(calendar)-37]:
            prefix=recipe(key,{k:v[:stop] for k,v in small.items()})
            np.testing.assert_allclose(full[:stop],prefix,rtol=1e-5,atol=1e-6,equal_nan=True)
            checks.append({'key':key,'check':'prefix_recompute','stop':stop,'passed':True})
        for t in [1200,1700,len(calendar)-1]:
            for j in range(len(idx)):
                if key=='kama15_slope50':
                    c=small['close'][t-49:t+1,j].astype(float);values=[float(c[14])]
                    for k in range(15,50):
                        vol=sum(abs(c[m]-c[m-1]) for m in range(k-14,k+1))
                        er=abs(c[k]-c[k-15])/vol if vol else 1
                        alpha=(er*(2/3-2/31)+2/31)**2
                        values.append(values[-1]+alpha*(c[k]-values[-1]))
                    literal=(values[-1]-values[-2])/np.std(values[-15:])
                else:
                    n=480 if key=='rsrs18_z480' else 200
                    betas=[];fit=None
                    for at in range(t-n+1,t+1):
                        a=small['low'][at-17:at+1,j].astype(float);b=small['high'][at-17:at+1,j].astype(float)
                        fit=sm.OLS(b,sm.add_constant(a)).fit() if n==480 else sm.WLS(b,sm.add_constant(a),weights=small['volume'][at-17:at+1,j].astype(float)).fit()
                        betas.append(fit.params[1])
                    literal=(betas[-1]-np.mean(betas))/np.std(betas,ddof=1 if n==480 else 0)
                    if n==200:literal*=fit.params[1]*fit.rsquared
                if np.isfinite(full[t,j]):np.testing.assert_allclose(full[t,j],literal,rtol=3e-4,atol=3e-4)
        checks.append({'key':key,'check':'independent_literal_source_loop_or_statsmodels','stocks':len(idx),'dates':3,'passed':True})
    return checks

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    calendar,stocks,fields=q.load_market();q.dates_all=calendar
    grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
    config={'version':VERSION,'read_alignment_version':q.ALIGNMENT_RULE_VERSION,'formal_window':['20210907','20260907'],'recent_window':['20260101',str(calendar.max().date())],
        'warmup':'20180101','universe':'SH/SZ fullA; active total_mv>0; no ST/listing filter','adjustment':'qfq','cycle':10,'label':'close(t+1)->close(t+11)','groups':10,
        'one_way_cost':.003,'benchmark':'factor_valid','net_annualization':'arithmetic','signal_reference':str(q.REFERENCE.relative_to(q.ROOT)),
        'platform_net_filter':'all','platform_compute_spent':0,'scope':'three additional frozen source hypotheses; research proxy, no official pool test',
        'warmup_limitation':'18+480 observations fit the 2018 warmup; newer listings remain incomplete',
        'hypotheses_in_this_cohort':3,'previous_source_cohort_specs':92,'oos_validation':False,'parameter_selection':'source fixed; no optimization'}
    if (OUT/'config.json').exists() and json.loads((OUT/'config.json').read_text())!=config:raise ValueError('Incompatible output')
    q.dump(OUT/'config.json',config)
    q.dump(OUT/'verification.json',verify(fields,calendar))
    c=fields['close'];cap=fields['cap'];turn=fields['turnover'];v=fields['volume'];r=q.ratio(c,q.delay(c))-1
    positions=np.flatnonzero((calendar>='2021-09-07')&(calendar<='2026-09-07'))
    def sampled(x):
        y=np.array(x,dtype=np.float32,copy=True);y[~(cap>0)]=np.nan;return y[positions]
    eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
    roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks)
    anchors={
        'B01|SIZE-ONLY':sampled(-cap),
        'B02|TURN-BIAS-21/504':sampled(1-q.ratio(q.rolling(turn,21),q.rolling(turn,504))),
        'B03|RET40':sampled(-(q.ratio(c,q.delay(c,40))-1)),
        'B04|DD120':sampled(1-q.ratio(c,q.rolling(c,120,'max'))),
        'B05|CHIP250':sampled(q.ratio(q.ratio(q.rolling(v*(fields['open']+c)/2,250,'sum'),q.rolling(v,250,'sum')),c)-1),
        'B08|BM_latest_proxy':sampled(q.ratio(eq,cap*10000)),
        'B09|DD60':sampled(1-q.ratio(c,q.rolling(c,60,'max'))),
        'N01|REV20':sampled(-(q.ratio(c,q.delay(c,20))-1)),
        'N08|TURN_STD21':sampled(-q.rolling(turn,21,'std')),
        'N09|MAX21':sampled(-q.rolling(r,21,'max')),
        'N16|SKEW60':sampled(-q.rolling(r,60,'skew')),
        'N27|ROE_latest_proxy':sampled(roe),
        'unassigned|H03-IMPACT60':sampled(q.ratio(q.rolling(q.ratio(fields['high']-fields['low'],q.delay(c)+1e-6),60,'sum'),q.rolling(fields['amount'],60,'sum')+1)),
        'composite|WEIGHTED-REV21':sampled(-q.ratio(q.rolling(turn*r,21,'sum'),q.rolling(turn,21,'sum'))),
    }
    del eq,roe
    metas=[];results=[];correlations=[];panels={}
    for key,name,group,prefix,formula,fidelity in SPECS:
        source=next((q.ROOT/'quant'/group).glob(prefix+'*.txt'))
        meta={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[str(source.relative_to(q.ROOT))],
            'source_sha256':[hashlib.sha256(source.read_bytes()).hexdigest()],'fidelity':fidelity,'strategy_execution_reproduced':False}
        metas.append(meta);allx=recipe(key,fields);allx[~(cap>0)]=np.nan
        x=allx[pos];panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
        residual=dual_residual(x,-cap[pos],-(q.ratio(c,q.delay(c,20))-1)[pos])
        for window,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='2026-01-01')]:
            folder=OUT/window;folder.mkdir(exist_ok=True)
            for form,score in [('raw',x),('size_reversal_rank_residual',residual)]:
                result,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],fields)
                result.update({'key':key,'name':name,'window':window,'form':form,'coverage_pct':result['periods']/mask.sum()*100,'fidelity':fidelity})
                results.append(result);q.dump(folder/f'{key}.{form}.json',result)
                p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
        for anchor,y in anchors.items():
            correlations.append({'candidate':key,'anchor':anchor,'scope':'daily_cross_sectional_spearman_mean',**rho_details(allx[positions],y)})
        pd.DataFrame(results).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
        pd.DataFrame(correlations).to_csv(OUT/'daily_old_anchor_correlations.csv',index=False)
        q.dump(OUT/'recipe_manifest.json',metas)
        print('completed',key,'net',round(results[-4].get('net_excess_pct',0),3),'recent',round(results[-2].get('net_excess_pct',0),3),flush=True)
    pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':metas},OUT/'signal_panels.pkl')
    q.dump(OUT/'completion.json',{'candidates':3,'result_rows':len(results),'daily_correlations':len(correlations),'all_candidates_completed':True,
        'formal_last_signal':grid.max(),'last_exit':calendar[pos[-1]+11],'latest_cache_date':calendar.max(),'full_five_year_RSRS_coverage':True,'pool_incremental_test_done':False})

if __name__=='__main__':main()
