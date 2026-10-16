#!/usr/bin/env python3
"""Three newly read source recipes, isolated local proxy; no platform calls."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-reproduction-20261012'
VERSION=q.ALIGNMENT_RULE_VERSION+'-quant-source2-user-arithmetic-fullA'

def recipe(key, f):
    c=f['close'].astype(float)
    if key=='detrended_z60_low':
        sub=c-q.rolling(c,20)
        return -q.ratio(sub-q.rolling(sub,60),q.rolling(sub,60,'std'))
    if key=='bias29_ma19':
        bias=100*(q.ratio(c,q.rolling(c,29))-1)
        bias=np.ceil(bias*10000)/10000
        bias=np.where(bias>0,np.ceil(bias*1000)/1000,np.where(bias<0,np.floor(bias*1000)/1000,bias))
        ma=q.rolling(bias,19)
        ma=np.where(ma>0,np.ceil(ma*1000)/1000,np.where(ma<0,np.floor(ma*1000)/1000,ma))
        return (bias-ma).astype(np.float32)
    if key=='rsrs18_rightdev1100':
        lo=pd.DataFrame(f['low'].astype(float));hi=pd.DataFrame(f['high'].astype(float))
        cov=lo.rolling(18).cov(hi).to_numpy()
        vl=lo.rolling(18).var().to_numpy();vh=hi.rolling(18).var().to_numpy()
        beta=q.ratio(cov,vl)
        r2=q.ratio(cov**2,vl*vh)
        z=q.ratio(beta-q.rolling(beta,1100),pd.DataFrame(beta).rolling(1100).std(ddof=0).to_numpy())
        return (z*beta*r2).astype(np.float32)
    raise KeyError(key)

SPECS=[
    ('detrended_z60_low','去趋势价格Z60反转','12 ', '-z60(C-MA20(C)), sample STD ddof=1','daily_formula_exact_stock_universe_adaptation'),
    ('bias29_ma19','BIAS29相对自身MA19','21 ','rounded_BIAS29 - rounded_MA19(rounded_BIAS29), source rounding retained','daily_qfq_close_proxy_for_raw_intraday_index'),
    ('rsrs18_rightdev1100','RSRS18右偏1100','05 ','z1100(COV18(H,L)/VAR18(L), ddof=0)*beta18*CORR18(H,L)^2','stock_adaptation_partial_warmup; source index timing starts in 2005'),
]

def dual_residual(x,sz,rv):
    out=np.full_like(x,np.nan)
    for i in range(len(x)):
        valid=np.isfinite(x[i])&np.isfinite(sz[i])&np.isfinite(rv[i])
        if valid.sum()<100:continue
        a=np.column_stack([np.ones(valid.sum()),rankdata(sz[i,valid]),rankdata(rv[i,valid])])
        y=rankdata(x[i,valid]);out[i,valid]=y-a@np.linalg.lstsq(a,y,rcond=None)[0]
    return out

def verify(fields,calendar):
    # Compare against independently calculated source loops / OLS, then
    # append future data and check the causal history is unchanged.
    import statsmodels.api as sm
    selected=np.flatnonzero(np.isfinite(fields['low'][-1200:]).all(axis=0)&np.isfinite(fields['high'][-1200:]).all(axis=0))[:4]
    f={k:v[:,selected] for k,v in fields.items()}
    checks=[]
    for key,*_ in SPECS:
        full=recipe(key,f)
        for stop in [1200,1700,len(calendar)-37]:
            trunc=recipe(key,{k:v[:stop] for k,v in f.items()})
            np.testing.assert_allclose(full[:stop],trunc,rtol=1e-5,atol=1e-6,equal_nan=True)
            checks.append({'key':key,'check':'future_truncation','stop':stop,'passed':True})
    for pos in [1250,1650,len(calendar)-1]:
        for j in range(len(selected)):
            c=f['close'][:pos+1,j].astype(float)
            sub=np.array([c[t-19:t+1].mean() for t in range(pos-59,pos+1)])
            dif=c[pos-59:pos+1]-sub
            literal=-(dif[-1]-dif.mean())/dif.std(ddof=1)
            np.testing.assert_allclose(recipe('detrended_z60_low',f)[pos,j],literal,rtol=2e-4,atol=2e-4)
            def rounded(v):
                import math
                return math.ceil(v*1000)/1000 if v>0 else math.floor(v*1000)/1000 if v<0 else v
            import math
            biases=[rounded(math.ceil(100*(c[t]-c[t-28:t+1].mean())/c[t-28:t+1].mean()*10000)/10000) for t in range(pos-18,pos+1)]
            literal=biases[-1]-rounded(np.mean(biases))
            np.testing.assert_allclose(recipe('bias29_ma19',f)[pos,j],literal,atol=.002,rtol=1e-4)
            lo=f['low'][pos-17:pos+1,j].astype(float);hi=f['high'][pos-17:pos+1,j].astype(float)
            fit=sm.OLS(hi,sm.add_constant(lo)).fit()
            b=np.array([sm.OLS(f['high'][t-17:t+1,j].astype(float),sm.add_constant(f['low'][t-17:t+1,j].astype(float))).fit().params[1] for t in range(pos-1099,pos+1)])
            literal=(b[-1]-b.mean())/b.std(ddof=0)*fit.params[1]*fit.rsquared
            np.testing.assert_allclose(recipe('rsrs18_rightdev1100',f)[pos,j],literal,atol=1e-3,rtol=1e-3)
    checks.append({'check':'independent_source_loops_and_OLS','stocks':len(selected),'dates':3,'passed':True,'BIAS_rounding_tolerance':.002})
    return checks

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    calendar,stocks,fields=q.load_market();q.dates_all=calendar
    grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
    config={'version':VERSION,'read_alignment_version':q.ALIGNMENT_RULE_VERSION,'formal_window':['20210907','20260907'],'recent_window':['20260101',str(calendar.max().date())],
        'warmup':'20180101','universe':'SH/SZ fullA; active total_mv>0; no ST/listing filter','adjustment':'qfq','cycle':10,'label':'close(t+1)->close(t+11)','groups':10,
        'one_way_cost':.003,'benchmark':'factor_valid','net_annualization':'arithmetic','signal_reference':str(q.REFERENCE.relative_to(q.ROOT)),
        'platform_net_filter':'all','platform_compute_spent':0,'scope':'three frozen source hypotheses; research proxy, no official pool test',
        'warmup_limitation':'RSRS1100+18 requires >1116 daily observations; initial 2021 signals cannot be recovered from 2018 cache',
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
    for key,name,prefix,formula,fidelity in SPECS:
        source=next((q.ROOT/'quant/2020年度精选策略').glob(prefix+'*.txt'))
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
        'formal_last_signal':grid.max(),'last_exit':calendar[pos[-1]+11],'latest_cache_date':calendar.max(),'full_five_year_RSRS_coverage':False,'pool_incremental_test_done':False})

if __name__=='__main__':main()
