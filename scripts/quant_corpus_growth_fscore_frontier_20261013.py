"""Daily/PIT adaptations of two previously untested corpus recipes.

The source strategies are not imported or executed.  All formulas are frozen
before loading outcomes and are reported as adaptations where vendor fields or
the original execution pool are unavailable.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec, audit, simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic

SRC74='quant/2024年度精选策略2/74.【动量应用V1】12年120倍，根据研报思路调整.txt'
SRC78='quant/2024年度精选策略2/78.ffscore选股加rsrs择时.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-growth-fscore-frontier-20261013'
SPECS=[
 spec('growth74_qualified_size_ma','高营收增长后小市值叠加120/20趋势',SRC74,
      'I(or_yoy top10% and EPS>0) then rank(-totalMV)+rank(C/MA120-1)+rank(C/MA20-1)',
      'proxy: source sales_growth mapped to PIT fina_indicator.or_yoy; circulating_mv/30-stock execution and weekly timing omitted; qualification subset is disclosed'),
 spec('growth74_continuous_rank_ma','营收增长×120/20趋势连续组合',SRC74,
      'rank(or_yoy)+rank(C/MA120-1)+rank(C/MA20-1)',
      'proxy: same source fields without source top10/EPS/small-cap gate, used only to test whether the gate adds information'),
 spec('fscore78_roaimprove_lowivol','FScore>=7且ROA改善、残差波动低80%',SRC78,
      'I(FScore8>=7 and adjacent deducted-ROA change>.002 and IVOL120 in lowest80%) * ROA_change',
      'proxy: coherent PIT eight-condition score from source78 reconstruction; residual_volatility is equal-weight fullA CAPM120 proxy; RSRS/index/HS300 and execution omitted; qualified benchmark')
]
SPECS[0]['gated']=True; SPECS[2]['gated']=True

def ivol(f):
    r=q.ratio(f['close'],q.delay(f['close']))-1
    m=pd.DataFrame(np.where(f['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
    mf=pd.DataFrame(np.broadcast_to(m[:,None],r.shape))
    cov=pd.DataFrame(r).rolling(120).cov(mf).to_numpy()
    mv=mf.rolling(120).var().to_numpy()
    return np.sqrt(np.maximum(q.rolling(r,120,'var')-q.ratio(cov**2,mv),0))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cal,stocks,f=q.load_market()
    saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=saved['dates'];pos=cal.get_indexer(grid)
    old=q.FIN_FIELDS
    try:
        fin=q.financial_snapshot(grid,stocks)
    finally:q.FIN_FIELDS=old
    cap=f['cap'][pos]
    growth=fin['fina_indicator.or_yoy.q0']
    eps=q.daily_pit_field('fina_indicator','eps',cal,stocks)[pos]
    c=f['close'];ma120=q.rolling(c,120)[pos];ma20=q.rolling(c,20)[pos]
    trend120=q.ratio(c[pos],ma120)-1;trend20=q.ratio(c[pos],ma20)-1
    rg=q.rank(np.where(cap>0,growth,np.nan));small=q.rank(np.where(cap>0,-cap,np.nan))
    qualified=(rg>=.9)&(eps>0)&(cap>0)
    v1=np.where(qualified,small+q.rank(np.where(qualified,trend120,np.nan))+q.rank(np.where(qualified,trend20,np.nan)),np.nan)
    v2=rg+q.rank(np.where(cap>0,trend120,np.nan))+q.rank(np.where(cap>0,trend20,np.nan))
    sp91=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source91-20261013/signal_panels.pkl')
    assert sp91['dates'].equals(grid) and sp91['stocks'].equals(stocks)
    score=sp91['panels']['fscore8_coherent_adjacent_count'].to_numpy()
    roa_chg=sp91['panels']['adjacent_ttm_deducted_roa_change'].to_numpy()
    iv=ivol(f)[pos]
    ivrank=q.rank(np.where(cap>0,iv,np.nan))
    gate=(score>=7)&(roa_chg>.002)&(ivrank<=.8)&(cap>0)
    v3=np.where(gate,roa_chg,np.nan)
    vals=[v1,v2,v3]
    checks=[]
    for n in [35,79]:
        stop=pos[n-1]+1
        cp=f['cap'][:stop][pos[:n]]
        gg=fin['fina_indicator.or_yoy.q0'][:n];ee=eps[:n]
        t120=q.ratio(c[:stop][pos[:n]],q.rolling(c[:stop],120)[pos[:n]])-1
        t20=q.ratio(c[:stop][pos[:n]],q.rolling(c[:stop],20)[pos[:n]])-1
        rr=q.rank(np.where(cp>0,gg,np.nan));sm=q.rank(np.where(cp>0,-cp,np.nan));qq=(rr>=.9)&(ee>0)&(cp>0)
        a=np.where(qq,sm+q.rank(np.where(qq,t120,np.nan))+q.rank(np.where(qq,t20,np.nan)),np.nan)
        b=rr+q.rank(np.where(cp>0,t120,np.nan))+q.rank(np.where(cp>0,t20,np.nan))
        np.testing.assert_allclose(vals[0][:n],a,equal_nan=True,atol=1e-5,rtol=1e-5)
        np.testing.assert_allclose(vals[1][:n],b,equal_nan=True,atol=1e-5,rtol=1e-5)
        checks += [dict(test='PIT_market_prefix_rebuild',key='growth74_qualified_size_ma',stop=int(n),passed=True),dict(test='PIT_market_prefix_rebuild',key='growth74_continuous_rank_ma',stop=int(n),passed=True)]
    checks.append(dict(test='source78_upstream_panel_grid_alignment',source='quant-corpus-semantic-source91-20261013',passed=True))
    run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source74/78 daily and PIT adaptations; no original pool/execution claim',residual_guard='constant residual<=1e-7 invalid',source_fields='or_yoy and q_dtprofit coherent score explicitly mapped'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
    tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
    q.dump(OUT/'frozen_plan.json',dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,source_panel='source91'))
    q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0))
    print('FINISHED_FRONTIER',flush=True)

if __name__=='__main__':main()
