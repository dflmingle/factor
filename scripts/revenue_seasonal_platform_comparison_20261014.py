"""Offline comparison using each uploaded factor's saved platform signal dates."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from platform_aligned_factor_compare import read_platform_run

OUT=q.ROOT/'research_reports/platform_alignment/revenue-seasonal-platform-20261014'

def main():
    cal,stocks,f=q.load_market();q.dates_all=cal;rows=[]
    for label in ['upload','control3','control6']:
        statepath=OUT/f'budget14-{label}-candidates.txt.state.json'
        if not statepath.exists():continue
        entry=next(iter(json.loads(statepath.read_text()).values()))
        if not entry.get('raw_result'):continue
        run=read_platform_run(OUT/entry['raw_result']);dates=pd.DatetimeIndex(run['dates'])
        file='seasonal_revenue_pit_daily.parquet' if label=='upload' else f'seasonal_revenue_{label}_daily.parquet'
        data=pd.read_parquet(OUT/file)
        scores=data.pivot(index='date',columns='symbol',values='value').reindex(index=dates,columns=stocks).to_numpy()
        pos=cal.get_indexer(dates);assert (pos>=0).all()
        for window,mask in [('five_year',np.ones(len(dates),bool)),('recent',dates>='20260101')]:
            result,periods,daily=q.evaluate(scores[mask],dates[mask],stocks,pos[mask],f)
            result.update(label=label,window=window,date_source=entry['run_id'],
                fidelity='uploaded Tushare causal signal on local qfq/fullA/total_mv/label1; price/platform universe proxy',
                rule=q.ALIGNMENT_RULE_VERSION+'-uploaded-seasonal-user-arithmetic')
            directory=OUT/'local_platform_signal_dates'/window;directory.mkdir(parents=True,exist_ok=True)
            q.dump(directory/f'{label}.json',result)
            periods.to_csv(directory/f'{label}.periods.csv',index=False);daily.to_csv(directory/f'{label}.daily_nav.csv',index=False)
            row=dict(label=label,window=window,**{k:result[k] for k in ['periods','rank_ic','gross_excess_pct','net_excess_pct','turnover_pct','held_daily_max_drawdown_pct']})
            if window=='five_year':
                m=entry['metrics'];platform_net=float(m['long_excess'])-float(m['turnover'])*.1512
                row.update(platform_net_excess_pct=platform_net,net_delta_pp=result['net_excess_pct']-platform_net,
                    platform_rank_ic=float(m['rank_ic']),ic_series_corr=q.corr(periods.rank_ic.to_numpy(),run['rank_ic_values'][:len(periods)]))
                if run['top']:
                    topdate=pd.Timestamp(run['top'][0]['date'])
                    rawtop=data[data.date.eq(topdate)].sort_values('value',ascending=False).head(20)
                    row['top20_raw_overlap']=len(set(rawtop.symbol)&{x['symbol'] for x in run['top']})
            rows.append(row)
        print(label,dates.min(),dates.max(),len(dates),flush=True)
    pd.DataFrame(rows).to_csv(OUT/'budget14-local-platform-comparison.csv',index=False)
    print(pd.DataFrame(rows).drop(columns=['top_schema_keys'],errors='ignore').to_string(index=False),flush=True)

if __name__=='__main__':main()
