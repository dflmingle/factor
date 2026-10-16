"""Local PIT financial leaves, written only in this isolated research folder.

Announcement order, consolidated filings and quarter-to-TTM restoration are
mandatory. These Tushare leaves are explicit proxies for platform definitions.
"""
import json
import pickle
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from financial_factor_local import _normalise_table, _prefer_consolidated

CACHE = ROOT/'quantlab/.quantlab/cache/research/cn_equity/financial_full_a'
OUT = HERE/'financial_data_v2'


def table(endpoint, columns):
    files = sorted((CACHE/endpoint).glob('*.parquet'))
    if not files:
        raise ValueError('Missing local PIT table '+endpoint)
    available = set(pq.ParquetFile(files[0]).schema_arrow.names)
    cols = [k for k in ['ts_code','ann_date','f_ann_date','end_date','report_type','comp_type','end_type','update_flag']+columns if k in available]
    frame = pd.concat([pd.read_parquet(p, columns=cols) for p in files], ignore_index=True)
    if 'f_ann_date' in frame:
        frame['ann_date'] = pd.concat([pd.to_datetime(frame.ann_date,errors='coerce'),
                                     pd.to_datetime(frame.f_ann_date,errors='coerce')],axis=1).max(axis=1)
    frame = _normalise_table(frame, endpoint)
    if endpoint != 'fina_indicator':
        frame = _prefer_consolidated(frame)
    return frame.dropna(subset=['ann_date','end_date'])


def rebuild(calendar, stocks):
    OUT.mkdir(exist_ok=True)
    fingerprint = dict(calendar_start=str(calendar[0]), calendar_end=str(calendar[-1]),
                       dates=len(calendar), stocks=len(stocks), symbols=list(stocks),
                       version='top50-pit-daily-ttm-proxy-v2-last-row-nan-preserved')
    metadata_path = OUT/'metadata.json'
    if metadata_path.exists():
        if json.loads(metadata_path.read_text()) != fingerprint:
            raise ValueError('Existing financial cache differs; new version required')
    else:
        metadata_path.write_text(json.dumps(fingerprint, ensure_ascii=False, indent=1)+'\n')
    specs = {'balancesheet':['total_hldr_eqy_exc_min_int','total_assets','total_liab','total_cur_assets','total_cur_liab'],
             'fina_indicator':['roe','roic','grossprofit_margin','assets_yoy'],
             'income':['n_income_attr_p','total_revenue'], 'cashflow':['n_cashflow_act']}
    result = {}
    for endpoint, columns in specs.items():
        needed = [k for k in columns if not (OUT/f'{endpoint}.{k}.pkl').exists()]
        if needed:
            frame = table(endpoint, needed)
            arrays = {k:np.full((len(calendar),len(stocks)),np.nan,np.float32) for k in needed}
            for symbol, group in frame.groupby('instrument',sort=False):
                j = stocks.get_indexer([symbol])[0]
                if j < 0:
                    continue
                group = group.sort_values(['ann_date','end_date','update_flag'])
                ends = pd.PeriodIndex(group.end_date,freq='Q-DEC')
                reports = {}; anns = []; events = []
                for ann, end, values in zip(group.ann_date, ends, group[needed].to_numpy(float)):
                    reports[end] = values
                    current = max(reports)
                    if endpoint in ['income','cashflow']:
                        qs = []
                        for off in range(4):
                            qe = current-off
                            cum = reports.get(qe)
                            prev = reports.get(qe-1)
                            if cum is None or (qe.quarter != 1 and prev is None):
                                qs = []
                                break
                            qs.append(cum if qe.quarter == 1 else cum-prev)
                        value = np.sum(qs,axis=0) if qs else np.full(len(needed),np.nan)
                    else:
                        value = reports[current]
                    anns.append(ann); events.append(value.copy())
                events = pd.DataFrame(events,index=pd.DatetimeIndex(anns))
                events = events.loc[~events.index.duplicated(keep='last')]
                index = np.searchsorted(events.index.to_numpy(),calendar.to_numpy(),side='right')-1
                valid = index>=0
                for k, col in enumerate(needed):
                    arrays[col][valid,j] = events.iloc[index[valid],k].to_numpy(np.float32)
            for col, values in arrays.items():
                temp = OUT/f'{endpoint}.{col}.pkl.tmp'
                pd.to_pickle(values,temp)
                temp.replace(OUT/f'{endpoint}.{col}.pkl')
            print('PIT daily leaves:', endpoint, needed, flush=True)
        for col in columns:
            result[f'{endpoint}.{col}'] = pickle.load((OUT/f'{endpoint}.{col}.pkl').open('rb'))
    return result


def ratio(a,b):
    return np.divide(a,b,out=np.full_like(a,np.nan),where=np.isfinite(b)&(b!=0)).astype(np.float32)


def leaves(calendar, stocks, fields):
    data = rebuild(calendar, stocks)
    equity = data['balancesheet.total_hldr_eqy_exc_min_int']
    cap_yuan = fields['cap']*10000
    result = dict(bm=ratio(equity,cap_yuan), ep=ratio(data['income.n_income_attr_p'],cap_yuan),
        cfp=ratio(data['cashflow.n_cashflow_act'],cap_yuan), sp=ratio(data['income.total_revenue'],cap_yuan),
        roe=data['fina_indicator.roe'], roic=data['fina_indicator.roic'], gm=data['fina_indicator.grossprofit_margin'],
        assets_growth=data['fina_indicator.assets_yoy'],
        current_ratio=ratio(data['balancesheet.total_cur_assets'],data['balancesheet.total_cur_liab']),
        leverage=ratio(data['balancesheet.total_liab'],data['balancesheet.total_assets']))
    proxies = dict(bm='PIT latest consolidated book equity / total_mv yuan',
        ep='PIT restored consolidated attributable net profit TTM / total_mv yuan',
        cfp='PIT restored consolidated operating cashflow TTM / total_mv yuan',
        sp='PIT restored consolidated total revenue TTM / total_mv yuan',
        roe='Tushare PIT latest cumulative ROE, percent; platform vintage/annual semantics unconfirmed',
        roic='Tushare PIT latest cumulative ROIC, percent; platform vintage/annual semantics unconfirmed',
        gm='Tushare PIT latest grossprofit_margin, percent', assets_growth='Tushare PIT latest assets_yoy, percent',
        current_ratio='PIT current assets / current liabilities', leverage='PIT liabilities / total assets')
    (OUT/'proxy_mapping.json').write_text(json.dumps(proxies,ensure_ascii=False,indent=2)+'\n')
    return result
