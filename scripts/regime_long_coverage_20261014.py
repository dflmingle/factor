#!/usr/bin/env python3
"""Refresh exact replay/model coverage of every main canonical factor."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import regime_long_history_data_20261014 as d

def main():
    frame=pd.read_csv(d.OUT/'all_factor_replay_inventory.csv');frame['historical_replay_path']='';frame['historical_periods']=0;frame['long_forecast_formal_signals']=0;frame['long_model_status']='not_replayed'
    roots=['regime-long-base-replay-20261014','regime-long-market-replay-20261014','regime-long-financial-replay-v2-20261014','regime-long-financial-risk-replay-20261014']
    for root in roots:
        folder=d.OUT.parent/root
        audit=folder/'replay_audit.csv';lookup=pd.read_csv(audit).set_index('key') if audit.exists() else None
        for path in folder.glob('*.history.pkl'):
            key=path.name[:-12];mask=frame.key==key
            frame.loc[mask,'historical_replay_path']=str(path.relative_to(d.ROOT));frame.loc[mask,'replay_status']='replayed';frame.loc[mask,'data_ready']=True;frame.loc[mask,'long_model_status']='replayed_model_pending'
            if lookup is not None and key in lookup.index:frame.loc[mask,'historical_periods']=int(lookup.loc[key,'historical_periods'])
    study=d.OUT.parent/'shu-mulvey-long-ready-20261014'
    predictions=study/'long/prediction_audit.csv'
    if predictions.exists():
        p=pd.read_csv(predictions,parse_dates=['date']);counts=p[p.date>='2021-09-07'].groupby('key').size()
        for key,n in counts.items():
            mask=frame.key==key;frame.loc[mask,'long_forecast_formal_signals']=int(n);frame.loc[mask,'long_model_status']='long_forecasts_generated'
        modelkeys=pd.read_csv(study/'factor_metadata.csv').key
        frame.loc[frame.key.isin(modelkeys)&(frame.long_forecast_formal_signals==0),'long_model_status']='replayed_no_long_forecast; insufficient_valid_history_or_no_model_fit'
    frame.to_csv(d.OUT/'all_factor_replay_inventory_completed.csv',index=False)
    counts=frame.groupby(['adapter','long_model_status']).size().rename('count').reset_index();counts.to_csv(d.OUT/'factor_coverage_by_adapter.csv',index=False)
    ready=int(frame.data_ready.fillna(False).astype(bool).sum());predicted=int((frame.long_forecast_formal_signals>0).sum())
    q=dict(total=len(frame),replayed=ready,pending_replay=len(frame)-ready,long_models_with_formal_forecasts=predicted,all592_replayed=ready==len(frame),all592_long_models_completed=False,not_performance_screened=True,remaining_reason='per-builder historical inputs and replay adapters pending; not claimed completed')
    (d.OUT/'replay_coverage_latest.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(q)

if __name__=='__main__':main()
