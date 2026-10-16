#!/usr/bin/env python3
"""Descriptive delayed state returns, never an asset-universe admission screen."""
import numpy as np
import pandas as pd
import shu_mulvey_paper_replication_20261014 as m


def main():
    bundle=pd.read_pickle(m.BASE/'inputs.pkl');rows=[]
    for universe in ['six_styles','all_replayed']:
        folder=m.BASE/universe
        if not (folder/'verification.json').exists():continue
        state=pd.read_parquet(folder/'daily_states.parquet')
        returns=bundle['net_returns'];dates=state.index
        formal=(dates>='2021-09-07')&(dates<='2026-09-07')
        for key in state.columns:
            active=returns[key]-returns.market
            # State observed at close t governs returns beginning t+2.
            future=active.shift(-2)
            global_net=float(active.loc[formal].mean()*252*100)
            data=pd.DataFrame({'state':state[key],'next_execution_return':future},index=dates)
            data=data.loc[formal&(state[key]>=0)].dropna()
            for value,g in data.groupby('state'):
                mean=float(g.next_execution_return.mean()*252*100)
                rows.append(dict(universe=universe,key=key,state=int(value),observations=len(g),
                     global_net_active_annual_pct=global_net,delayed_state_net_active_annual_pct=mean,
                     global_negative_state_positive=bool(global_net<0 and mean>0 and len(g)>=252),
                     semantics='monthly refit label sorted by training return; state0 higher train mean',
                     use='posthoc descriptive only, not new alpha or out-of-sample selection evidence'))
    pd.DataFrame(rows).to_csv(m.BASE/'delayed_state_return_diagnostics.csv',index=False)
    print('STATE_DIAGNOSTICS',len(rows),flush=True)


if __name__=='__main__':main()
