"""A/B/C score-shape diagnostic from public pool snapshots and frozen local candidates."""
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SEARCH=HERE/'search'

def main():
    targets=pd.read_csv(HERE/'factor_targets.csv')
    targets=targets[targets.period.eq('2026-10')].copy()
    pools=pd.read_csv(HERE/'pool_metrics.csv')
    pools=pools[pools.score_period.eq('2026-10')].set_index('display_name')
    stats=pd.read_csv(SEARCH/'single_results.csv')
    stats=stats[(stats.cycle==3)&stats.window.eq('formal_5y')].set_index('candidate')
    rows=[]
    for t in targets.itertuples():
        if t.display_name not in pools.index or not bool(t.counted) or not np.isfinite(t.s_i_a): continue
        p=pools.loc[t.display_name]
        peer=targets[(targets.display_name==t.display_name)&targets.counted&targets.s_i_a.notna()]
        if len(peer)==0: continue
        base_vals=peer.s_i_a.to_numpy(float)
        # A: replace one public seat using candidate S_i.
        for cand,s in stats.iterrows():
            vals=base_vals.copy(); matches=np.flatnonzero(np.isclose(vals,float(t.s_i_a)))
            if len(matches): vals[matches[0]]=float(s.s_i)
            raw_a=float(np.mean(vals)); na=min(raw_a/0.08,float(p.new_pool_cap))
            # B is only a same-history diagnostic. Official B uses a separate OOS series.
            nb_same=min(raw_a/0.06,1.0) if float(p.pool_age_months)>=1 else 0.0
            nc_local=float(s.mean_monthly_nc)
            comb_pubc=.20*na+.35*float(p.nb)+.45*float(p.nc)
            comb_localc=.20*na+.35*nb_same+.45*nc_local
            rows.append(dict(candidate=cand,opponent=t.display_name,target_factor=t.factor_name,
                public_na=p.na,public_nb=p.nb,public_nc=p.nc,public_comb=p.comb,
                rebuilt_public_raw_a=np.mean(base_vals),public_raw_a=p.raw_a,
                proxy_raw_a=raw_a,proxy_na=na,proxy_nb_same_history=nb_same,
                candidate_nc_standalone=nc_local,publicC_comb=comb_pubc,localC_comb=comb_localc,
                delta_na=na-float(p.na),delta_nb_same=nb_same-float(p.nb),
                delta_nc_standalone=nc_local-float(p.nc),delta_comb_publicC=comb_pubc-float(p.comb),
                delta_comb_localC=comb_localc-float(p.comb)))
    d=pd.DataFrame(rows); d.to_csv(SEARCH/'abc_score_fit.csv',index=False)
    summary=d.groupby('candidate').agg(rows=('candidate','size'),mean_abs_dna=('delta_na',lambda x:float(np.mean(np.abs(x)))),mean_dna=('delta_na','mean'),mean_abs_dnb_same=('delta_nb_same',lambda x:float(np.mean(np.abs(x)))),mean_dnb_same=('delta_nb_same','mean'),mean_abs_dnc_standalone=('delta_nc_standalone',lambda x:float(np.mean(np.abs(x)))),mean_dnc_standalone=('delta_nc_standalone','mean'),mean_abs_dcomb_publicC=('delta_comb_publicC',lambda x:float(np.mean(np.abs(x)))),mean_dcomb_publicC=('delta_comb_publicC','mean'),mean_abs_dcomb_localC=('delta_comb_localC',lambda x:float(np.mean(np.abs(x)))),mean_dcomb_localC=('delta_comb_localC','mean')).reset_index()
    summary.to_csv(SEARCH/'abc_score_fit_summary.csv',index=False)
    print(summary.to_string(index=False))

if __name__=='__main__': main()
