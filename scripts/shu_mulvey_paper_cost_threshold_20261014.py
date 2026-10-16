#!/usr/bin/env python3
"""Trading-fee break-even on fixed forecasts, not another parameter search."""
import numpy as np
import pandas as pd
from scipy.optimize import brentq
import shu_mulvey_paper_replication_20261014 as m


def main():
    bundle=pd.read_pickle(m.BASE/'inputs.pkl');rows=[]
    for universe in ['six_styles','all_replayed']:
        folder=m.BASE/universe
        if not (folder/'verification.json').exists():continue
        columns=(list(m.STYLE_KEYS.values())+['market']) if universe=='six_styles' else bundle['gross_returns'].columns
        returns=bundle['gross_returns'][columns]
        for label in ['TE1','TE2','TE3','TE4']:
            weights=pd.read_parquet(folder/f'{label}.signal_weights.parquet')
            start=returns.index.get_loc(weights.index[0]);end=returns.index.get_loc(weights.index[-1])
            def annual_excess(cost):
                br,b,_,_=m.quarterly_benchmark(returns,cost)
                pnl,*_=m.realized_portfolio(returns.iloc[start:end+1],weights,cost,b[start-1])
                return float((pnl-br[start:end+1]).mean()*252*100)
            low,high=annual_excess(0.),annual_excess(.01)
            breakeven=brentq(annual_excess,0.,.01,xtol=1e-9) if low>0 and high<0 else np.nan
            rows.append(dict(universe=universe,configuration=label,
                    break_even_one_way_fee_bps=breakeven*10000,
                    zero_fee_relative_ew_annual_pct=low,fee_5bps_relative_ew_annual_pct=annual_excess(.0005),
                    fee_30bps_relative_ew_annual_pct=annual_excess(.003),
                    scope='gross underlying sleeves; overlay fees only; frozen signals; not capacity or stock-netting estimate'))
    pd.DataFrame(rows).to_csv(m.BASE/'overlay_cost_break_even.csv',index=False)
    print(pd.DataFrame(rows).drop(columns='scope').round(3).to_string(index=False),flush=True)


if __name__=='__main__':main()
