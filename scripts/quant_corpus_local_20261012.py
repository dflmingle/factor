#!/usr/bin/env python3
"""Offline source-grounded quant corpus experiment; never executes source scripts.

Frozen formulas, arithmetic full-A contract requested by the user. This isolated
version must not be merged with the repository's qualitygate4 headline results.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
import hashlib
import json
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import rankdata
from platform_aligned_factor_compare import read_platform_run
from platform_alignment_rules import ALIGNMENT_RULE_VERSION
from financial_factor_local import _normalise_table, _prefer_consolidated

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'quantlab/.quantlab/cache/research/cn_equity'
OUT = ROOT / 'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012'
VERSION = ALIGNMENT_RULE_VERSION + '-quant-source1-user-arithmetic-fullA'
REFERENCE = ROOT / 'h03-t10-single-20260911-candidates.results/6aa36bd3ecb163ea7228cffe.json'
CYCLE = 10

def dump(path, value):
    def clean(v):
        if isinstance(v, dict): return {str(k): clean(x) for k,x in v.items()}
        if isinstance(v, (tuple,list)): return [clean(x) for x in v]
        if isinstance(v, (np.integer,)): return int(v)
        if isinstance(v, (float,np.floating)): return float(v) if np.isfinite(v) else None
        return v
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, default=str, allow_nan=False)+'\n', encoding='utf-8')

def load_market():
    saved = OUT / 'market_arrays.pkl'
    if saved.exists(): return pd.read_pickle(saved)
    paths = sorted((CACHE/'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet'))
    stocks, latest = set(), pd.Timestamp('2018-01-01')
    for p in paths:
        f = pd.read_parquet(p, columns=['date','instrument'])
        stocks.update(s for s in f.instrument.unique() if str(s).endswith(('.SH','.SZ')))
        latest = max(latest,pd.to_datetime(f.date).max())
    stocks = pd.Index(sorted(stocks))
    cal = pd.concat([pd.read_parquet(p,columns=['trade_date','is_open']) for p in (CACHE/'trade_calendar').glob('*.parquet')])
    d = pd.to_datetime(cal.trade_date.astype(str), format='mixed').dt.normalize()
    dates = pd.DatetimeIndex(sorted(d[cal.is_open.eq(1) & d.between('2018-01-01',latest)].unique()))
    fields = {k:np.full((len(dates),len(stocks)),np.nan,np.float32) for k in ['close','open','volume','high','low','amount','turnover','cap','raw_close']}
    schema = {'close':'close','open':'open','volume':'volume','high':'high_qfq','low':'low_qfq','amount':'amount'}
    conflict = {}
    for p in paths:
        available = set(pq.ParquetFile(p).schema_arrow.names)
        mapping = {k:v for k,v in schema.items() if v in available}
        f = pd.read_parquet(p,columns=['date','instrument']+list(mapping.values()))
        di,si = dates.get_indexer(pd.to_datetime(f.date).dt.normalize()), stocks.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)
        for k,col in mapping.items():
            new = f[col].to_numpy(dtype=np.float32)[ok]
            old = fields[k][di[ok],si[ok]]
            bad = np.isfinite(old)&np.isfinite(new)&~np.isclose(old,new,rtol=1e-6,atol=1e-6)
            if bad.any(): raise ValueError(f'Conflicting qfq snapshots {p}: {k} {bad.sum()}')
            finite = np.isfinite(new)
            fields[k][di[ok][finite],si[ok][finite]]=new[finite]
    caps = sorted((CACHE/'tushare_factor_recheck/daily_basic_full_a').glob('*.parquet'))
    for p in caps:
        f=pd.read_parquet(p,columns=['date','instrument','total_mv','turnover','close'])
        di,si=dates.get_indexer(pd.to_datetime(f.date).dt.normalize()),stocks.get_indexer(f.instrument)
        ok=(di>=0)&(si>=0)
        for k,col in [('cap','total_mv'),('turnover','turnover'),('raw_close','close')]:
            fields[k][di[ok],si[ok]]=f[col].to_numpy(dtype=np.float32)[ok]
    active = fields['cap']>0
    for k in ['close','open','high','low','volume','amount','raw_close']:
        fields[k][~active | (fields[k]<=0)] = np.nan
    # Only close is forward filled, exactly as the documented local proxy.
    fields['close'] = pd.DataFrame(fields['close']).ffill().to_numpy(dtype=np.float32)
    sample = (dates >= '2021-09-07') & (dates <= '2026-09-07')
    coverage={k:float(np.isfinite(v[sample][active[sample]]).mean()) for k,v in fields.items()}
    dump(OUT/'data_audit.json', {'calendar_rows':len(dates),'symbols':len(stocks),'latest':latest,'field_coverage_active_5y':coverage,'price_batches':len(paths),'daily_basic_batches':len(caps),'duplicate_conflicts':conflict,'snapshot_hash_verification':'not rerun; existence only','no_high_low_amount_fill':True})
    result=(dates,stocks,fields)
    pd.to_pickle(result,saved)
    print('market loaded',len(dates),len(stocks),coverage,flush=True)
    return result

FIN_FIELDS={
 'fina_indicator':['roe','roa','roic','grossprofit_margin','netprofit_margin','current_ratio','assets_turn','netprofit_yoy','or_yoy','tr_yoy','op_yoy','ocf_yoy','roe_yoy','assets_yoy','rd_exp','ocf_to_or'],
 'balancesheet':['total_assets','total_liab','total_nca','total_ncl','total_cur_assets','total_cur_liab','total_hldr_eqy_exc_min_int','total_share','money_cap','st_borr','lt_borr','bond_payable','non_cur_liab_due_1y','lease_liab','inventories','notes_receiv','accounts_receiv','oth_receiv','goodwill','intan_assets','cip'],
 'income':['revenue','total_revenue','oper_cost','total_cogs','operate_profit','ebit','n_income','n_income_attr_p'],
 'cashflow':['n_cashflow_act']}

def pit_tables():
    result={}
    for endpoint,cols in FIN_FIELDS.items():
        paths=sorted((CACHE/'financial_full_a'/endpoint).glob('*.parquet'))
        available=set(pq.ParquetFile(paths[0]).schema_arrow.names)
        metadata=['ts_code','ann_date','f_ann_date','end_date','report_type','comp_type','end_type','update_flag']
        cols=[c for c in metadata+cols if c in available]
        f=pd.concat([pd.read_parquet(p,columns=cols) for p in paths],ignore_index=True)
        # Late actual publication dates take precedence; never backdate revisions.
        if 'f_ann_date' in f:
            a=pd.to_datetime(f.ann_date,errors='coerce'); b=pd.to_datetime(f.f_ann_date,errors='coerce')
            f['ann_date']=pd.concat([a,b],axis=1).max(axis=1)
        f=_normalise_table(f,endpoint)
        if endpoint!='fina_indicator': f=_prefer_consolidated(f)
        result[endpoint]=f.dropna(subset=['ann_date','end_date'])
    return result

def financial_snapshot(dates,stocks,lags=6):
    """Replay available reports in announcement order, retaining current periods.

    Unlike a merge_asof on raw filing rows, late revisions to old quarters do
    not replace the current quarter. TTM requires four contiguous quarters.
    """
    saved=OUT/('financial_signal_snapshots.pkl' if lags==6 else f'financial_signal_snapshots_lags{lags}.pkl')
    if saved.exists():return pd.read_pickle(saved)
    result={}
    for endpoint,table in pit_tables().items():
        wanted=[c for c in FIN_FIELDS[endpoint] if c in table]
        names = wanted + ([f'{c}_ttm' for c in wanted] if endpoint in ['income','cashflow'] else [])
        for lag in range(lags):
            for name in names:result[f'{endpoint}.{name}.q{lag}']=np.full((len(dates),len(stocks)),np.nan,np.float32)
        for symbol,g in table.groupby('instrument',sort=False):
            j=stocks.get_indexer([symbol])[0]
            if j<0:continue
            g=g.sort_values(['ann_date','end_date','update_flag'])
            ann=pd.DatetimeIndex(g.ann_date).to_numpy(); ends=pd.PeriodIndex(g.end_date,freq='Q-DEC')
            vals=g[wanted].to_numpy(dtype=np.float64)
            reports={}; at=0
            for i,date in enumerate(dates):
                while at<len(g) and ann[at]<=date.to_datetime64():
                    reports[ends[at]]=vals[at]; at+=1
                if not reports:continue
                current=max(reports)
                for lag in range(lags):
                    end=current-lag; v=reports.get(end)
                    if v is not None:
                        for c,x in zip(wanted,v):result[f'{endpoint}.{c}.q{lag}'][i,j]=x
                    if endpoint not in ['income','cashflow']:continue
                    quarters=[]
                    for off in range(4):
                        qe=end-off; cum=reports.get(qe)
                        if cum is None: break
                        if qe.quarter==1:quarters.append(cum)
                        elif qe-1 in reports:quarters.append(cum-reports[qe-1])
                        else:break
                    if len(quarters)==4:
                        ttm=np.sum(quarters,axis=0)
                        for c,x in zip(wanted,ttm):result[f'{endpoint}.{c}_ttm.q{lag}'][i,j]=x
        print('PIT snapshots',endpoint,flush=True)
    pd.to_pickle(result,saved)
    return result


def rank(x):
    return pd.DataFrame(x).rank(axis=1,method='average',pct=True).to_numpy(dtype=np.float32)

def zscore(x):
    f=pd.DataFrame(x);return f.sub(f.mean(axis=1),axis=0).div(f.std(axis=1),axis=0).to_numpy(dtype=np.float32)

def rolling(x,n,method='mean',minimum=None):
    return getattr(pd.DataFrame(x).rolling(n,min_periods=n if minimum is None else minimum),method)().to_numpy(dtype=np.float32)

def delay(x,n=1):
    y=np.full_like(x,np.nan);y[n:]=x[:-n];return y

def ratio(a,b):
    with np.errstate(divide='ignore',invalid='ignore'):
        v=a/b
    return np.where(np.isfinite(v),v,np.nan).astype(np.float32)

def source_meta(key,name,pattern,formula,fidelity='formula_reconstruction',role='candidate',lines=None):
    sources=sorted((ROOT/'quant').rglob(pattern))
    if not sources:raise FileNotFoundError(pattern)
    from quant_strategy_factor_catalog_20261012 import read_text
    return {'key':key,'name':name,'source_paths':[str(p.relative_to(ROOT)) for p in sources],
            'source_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources],
            'source_line_spans':lines,'formula':formula,'direction':1,'fidelity':fidelity,'role':role,
            'source_text_read':True,'execution':'offline_fullA_signal_extraction; original strategy execution/pool not reproduced'}

def recipes(fields,positions):
    """Directions and parameters frozen from sources or explicitly labelled adaptations."""
    c,o,v,t,cap = [fields[k] for k in ['close','open','volume','turnover','cap']]
    active=cap>0
    r=ratio(c,delay(c))-1
    intr=ratio(c,o)-1;night=ratio(o,delay(c))-1
    def emit(key,name,pattern,formula,x,fidelity='formula_reconstruction',role='candidate',lines=None):
        x=np.asarray(x,dtype=np.float32).copy()
        if len(x)==len(c):x=x[positions]
        x[~active[positions] | ~np.isfinite(x)] = np.nan
        return source_meta(key,name,pattern,formula,fidelity,role,lines),x
    mom='42.【研报复现】再论动量因子Ian666.txt'
    yield emit('small_size','小市值控制','80.【深度解析 一】经典小市值模型.txt','-total_mv',-cap,'total_mv_contract_adaptation','known_control',[109,113])
    yield emit('reversal20','20日反转控制',mom,'-(close/lag(close,20)-1)',-(ratio(c,delay(c,20))-1),'raw_atom_without_source_industry_neutralization','known_control',[122,127])
    yield emit('momentum120','120日动量控制',mom,'close/lag(close,120)-1',ratio(c,delay(c,120))-1,'raw_atom_without_source_industry_neutralization','known_control',[122,127])
    yield emit('max_return20_low','低最大日收益',mom,'-max(return1,20), min_obs=12',-rolling(r,20,'max',12),'raw_atom_without_source_industry_neutralization','known_control',[122,127])
    for n,mn in [(20,10),(60,40),(120,80),(240,160)]:
        yield emit(f'ma{n}_over_close',f'{n}日均价/现价',mom,f'mean(close,{n},min_obs={mn})/close',ratio(rolling(c,n,minimum=mn),c),'raw_atom_without_source_industry_neutralization',lines=[194,202])
    lowvol=-rolling(r,20,'std')
    yield emit('low_vol20','20日低波动','78.国盛证券多因子.txt','-std(return1,20)',lowvol,'daily_atom','known_control',[66,70])
    yield emit('low_turn20','20日低换手','81.低PB小市值低换手策略总结.txt','-mean(turnover,20)',-rolling(t,20),'daily_smoothing_adaptation','known_control',[58,86])
    yield emit('low_turn_std20','换手稳定性','56.一创PEG+EBIT+turnover_volatility.txt','-std(turnover,20)',-rolling(t,20,'std'),'window20_adaptation','known_control',[223,241])
    coin='75.【复现】个股动量效应的识别及球队硬币因子.txt'
    dt=t-delay(t)
    change_mean=pd.DataFrame(dt).mean(axis=1).to_numpy()[:,None]
    flip=np.where(dt>=change_mean,1.,-1.);flip[~np.isfinite(dt)]=np.nan
    dn=delay(dt);dist=np.abs(dn-pd.DataFrame(dn).mean(axis=1).to_numpy()[:,None])
    nflag=np.where(dist>=pd.DataFrame(dist).mean(axis=1).to_numpy()[:,None],1.,-1.);nflag[~np.isfinite(dist)]=np.nan
    ndist=np.abs(night-pd.DataFrame(night).mean(axis=1).to_numpy()[:,None])
    composites=[]
    for tag,label,x,flag,ls in [('interday','日间',r,flip,[42,59]),('intraday','日内',intr,flip,[63,78]),('overnight','隔夜距离',ndist,nflag,[82,103])]:
        mean=rolling(x,20);std=rolling(x,20,'std')
        threshold=pd.DataFrame(np.where(active,std,np.nan)).mean(axis=1).to_numpy()[:,None]
        vol_leg=-mean*np.where(std>=threshold,1.,-1.)
        turn_leg=-rolling(x*flag,20)
        yield emit(f'coin_{tag}_vol',f'球队硬币-{label}波动翻转',coin,f'-mean({tag},20)*where(std({tag},20)>=cs_mean(std),1,-1)',vol_leg,lines=ls)
        yield emit(f'coin_{tag}_turn',f'球队硬币-{label}换手翻转',coin,f'-mean({tag}*turnover_change_flag,20); overnight uses lagged turnover-distance flag',turn_leg,lines=ls)
        combined=(zscore(vol_leg[positions])+zscore(turn_leg[positions]))/2
        composites.append(combined)
        yield emit(f'coin_{tag}_eq',f'球队硬币-{label}合成',coin,'equal cross-sectional zscore of two alpha-oriented legs',combined,'equal_CS_zscore_reconstruction',lines=ls)
    yield emit('coin_team_eq','球队硬币整体',coin,'mean(three component CS_zscore composites)',sum(zscore(x) for x in composites)/3,'equal_CS_zscore_reconstruction',lines=[105,107])
    gold='20.行业轮动的黄金律：日内动量与隔夜反转.txt'
    ir,nr=rolling(intr,15,'sum'),rolling(night,15,'sum')
    yield emit('intraday_momentum15','日内动量15',gold,'sum(close/open-1,15)',ir,'industry_to_stock_adaptation',lines=[155,168])
    yield emit('overnight_reversal15','隔夜反转15',gold,'-sum(open/lag(close)-1,15)',-nr,'industry_to_stock_adaptation',lines=[155,168])
    yield emit('golden_rule15','黄金律15',gold,'rank(sum(intraday,15))+rank(-sum(overnight,15))',rank(ir[positions])+rank(-nr[positions]),'industry_to_stock_adaptation',lines=[155,168])
    pv='51.【复现】行业有效量价因子与行业轮动策略.txt'
    yield emit('volume_low_std20','成交量低波动',pv,'-std(volume,20)',-rolling(v,20,'std'),'industry_to_stock_window20_adaptation',lines=[106,121])
    yield emit('amount_low_std20','成交额低波动',pv,'-std(actual_amount,20)',-rolling(fields['amount'],20,'std'),'actual_amount_cached',lines=[106,121])
    yield emit('turn_long_short60_20','长短换手比',pv,'mean(turnover,60)/mean(turnover,20)',ratio(rolling(t,60),rolling(t,20)),'industry_to_stock_windows60_20_adaptation',lines=[106,121])
    yield emit('momentum_term60_20','动量期限差',pv,'return60-return20',ratio(c,delay(c,60))-ratio(c,delay(c,20)),'industry_to_stock_windows60_20_adaptation',lines=[106,121])
    bias=ratio(c,rolling(c,20))-1
    second=pd.DataFrame(bias-delay(bias,20)).ewm(span=20,adjust=False,min_periods=20).mean().to_numpy(dtype=np.float32)
    yield emit('second_momentum20','二阶动量',pv,'EMA(bias20-lag(bias20,20),20)',second,'industry_to_stock_windows20_adaptation',lines=[106,121])
    def corr_roll(a,b):return pd.DataFrame(a).rolling(20,min_periods=20).corr(pd.DataFrame(b)).to_numpy(dtype=np.float32)
    yield emit('pv_corr20','价量背离',pv,'-corr(close,volume,20)',-corr_roll(c,v),'industry_to_stock_window20_adaptation',lines=[106,121])
    cr,vr=rank(np.where(active,c,np.nan)),rank(np.where(active,v,np.nan))
    cov=pd.DataFrame(cr).rolling(20).cov(pd.DataFrame(vr)).to_numpy(dtype=np.float32)
    yield emit('pv_rank_cov20','秩价量协方差',pv,'-cs_rank(cov(cs_rank(close),cs_rank(volume),20))',-rank(cov[positions]),'industry_to_stock_window20_adaptation',lines=[106,121])
    vchg=rank(ratio(v,delay(v))-1)
    yield emit('pv_growth_intraday_corr20','量增与日内收益背离',pv,'-corr(cs_rank(volume_growth),cs_rank(intraday_return),20)',-corr_roll(vchg,rank(intr)),'industry_to_stock_window20_adaptation',lines=[106,121])
    yield emit('volume_amplitude_corr20','量幅同向',pv,'corr(cs_rank(volume_growth),cs_rank(high/low-1),20)',corr_roll(vchg,rank(ratio(fields['high'],fields['low'])-1)),'actual_high_low_cached',lines=[106,121])
    path='16.选股因子系列研究(十八) — 价格形态选股因子.txt'
    for key,name,a,b in [('high_open20','开盘冲高',fields['high'],o),('close_low20','盘低回升',c,fields['low'])]:
        yield emit(key,name,path,'mean(log('+key.split('20')[0]+'),20); low original preferred',-rolling(np.log(ratio(a,b)),20),'actual_high_low_cached',lines=[29,38])
    # Amount is raw currency; convert raw average to qfq using daily raw/qfq close ratio.
    avg_raw=ratio(fields['amount']*1000,v*100)
    avg=avg_raw*ratio(c,fields['raw_close'])
    yield emit('vwap_close20','成交均价偏离',path,'mean(log(qfq_daily_vwap/close),20)',rolling(np.log(ratio(avg,c)),20),'actual_amount_units_and_qfq_conversion_proxy',lines=[29,38])
    cgo='37.处置效应的CGO因子（行为金融学因子）.txt'
    ref=np.full((len(positions),c.shape[1]),np.nan,np.float32)
    for i,p in enumerate(positions):
        if p<99:continue
        a=avg[p-99:p+1].astype(float);turn=t[p-99:p+1].astype(float)/100
        turn[(turn<0)|(turn>1)]=np.nan
        survivor=np.vstack([np.cumprod((1-turn[:0:-1]),axis=0)[::-1],np.ones((1,c.shape[1]))])
        w=turn*survivor
        ref[i]=ratio(np.sum(a*w,axis=0),np.sum(w,axis=0))
    yield emit('cgo100_low','筹码成本CGO',cgo,'-(close/sum(avg_i*t_i*prod(1-t_j,j>i))/sum(weights)-1),100d',-(ratio(c[positions],ref)-1),'actual_vwap_qfq_proxy_no_source_risk_neutralization',lines=[47,62,115,124])
    sal='90.【复现】凸显度因子.txt'
    market=pd.DataFrame(np.where(active,r,np.nan)).mean(axis=1).to_numpy()[:,None]
    sigma=ratio(np.abs(r-market),np.abs(r)+np.abs(market)+.1)
    def st_windows(s):
        vals=np.full((len(positions),c.shape[1]),np.nan,np.float32)
        for i,p in enumerate(positions):
            ss=s[p-19:p+1];rr=r[p-19:p+1]
            k=rankdata(-ss,axis=0,method='average',nan_policy='propagate')
            w=.7**k;w=w/np.mean(w,axis=0)
            vals[i]=-np.sum((w-np.mean(w,axis=0))*(rr-np.mean(rr,axis=0)),axis=0)/19
        return vals
    yield emit('salience_st20_low','凸显度STR',sal,'-cov(0.7^descending_temporal_rank(sigma20)/mean(weights),return1) within 20d',st_windows(sigma),'paper_formula_reconstruction_external_calc_weight_missing',lines=[81,103])
    stv=np.where(np.abs(r)>=.1,np.abs(r)*1000,t)
    yield emit('salience_stv20_low','成交凸显度STV',sal,'same STR with sigma=where(abs(r)>=0.1,abs(r)*1000,turnover_percent)',st_windows(stv),'paper_1000_not_source_code_100_external_weights',lines=[353,384])
    weighted=sigma*r;mn,sd=rolling(weighted,20),rolling(weighted,20,'std')
    yield emit('fear_mean20_low','惊恐收益',sal,'-mean(sigma*r,20)',-mn,'cross_section_market_instead_HS300_proxy',lines=[190,211])
    yield emit('fear_std20_low','惊恐波动',sal,'-std(sigma*r,20)',-sd,'cross_section_market_instead_HS300_proxy',lines=[190,211])
    yield emit('fear_equal20_low','惊恐合成',sal,'-(mean(sigma*r,20)+std(sigma*r,20))/2',-(mn+sd)/2,'source_raw_equal_CS_market_proxy',lines=[190,211])
    decay=sigma-(delay(sigma)+delay(sigma,2))/2
    decay[decay<0]=np.nan;wdec=decay*r
    yield emit('fear_decay20_low','注意力变化惊恐',sal,'-(mean(decay*r,20,min5)+std(decay*r,20,min5))/2; decay=sigma-mean(lag1,lag2),retain >=0',-(rolling(wdec,20,minimum=5)+rolling(wdec,20,'std',5))/2,'paper_formula_CS_market_proxy',lines=[180,186])

def financial_recipes(fin,fields,positions):
    shape=fields['cap'][positions].shape
    def f(table,col,lag=0):return fin.get(f'{table}.{col}.q{lag}',np.full(shape,np.nan,np.float32))
    mv=fields['cap'][positions]*10000
    assets=f('balancesheet','total_assets');equity=f('balancesheet','total_hldr_eqy_exc_min_int');liab=f('balancesheet','total_liab')
    roe,roa,roic=[f('fina_indicator',k) for k in ['roe','roa','roic']]
    revenue=f('income','total_revenue_ttm');rv=f('income','revenue_ttm');revenue=np.where(np.isfinite(revenue),revenue,rv)
    income=f('income','n_income_attr_p_ttm');ocf=f('cashflow','n_cashflow_act_ttm')
    bm=ratio(equity,mv);pb=ratio(mv,np.where(equity>0,equity,np.nan))
    def emit(key,name,pattern,formula,x,fidelity='PIT_Tushare_proxy',role='candidate',lines=None):
        x=np.asarray(x,dtype=np.float32).copy();x[(mv<=0)|~np.isfinite(x)]=np.nan
        return source_meta(key,name,pattern,formula,fidelity,role,lines),x
    q='78.国盛证券多因子.txt'
    yield emit('book_market','账面市值比',q,'latest announced equity/(total_mv*10000)',bm,role='known_control')
    yield emit('roe','ROE',q,'latest announced ROE',roe,role='known_control',lines=[175,197])
    yield emit('roic','ROIC',q,'latest announced ROIC',roic,role='known_control',lines=[175,197])
    yield emit('net_margin','净利率',q,'latest netprofit_margin',f('fina_indicator','netprofit_margin'))
    yield emit('asset_turnover','资产周转率',q,'latest assets_turn',f('fina_indicator','assets_turn'))
    yield emit('cash_assets','现金/资产',q,'money_cap/total_assets',ratio(f('balancesheet','money_cap'),assets),lines=[135,136])
    yield emit('workingcapital_assets','营运资本/资产',q,'(current_assets-current_liabilities)/total_assets',ratio(f('balancesheet','total_cur_assets')-f('balancesheet','total_cur_liab'),assets),lines=[135,136])
    yield emit('roe_over_pb','ROE/PB','22.菜场大妈皇城大妈年化108大妈吉祥.txt','roe/pb with positive book equity',ratio(roe,pb),lines=[134,141])
    yield emit('profitability_ytd_assets','毛盈利能力原文','95.首席质量因子-Gross Profitabilit（简化版）.txt','(YTD total_revenue-YTD total_cogs)/latest total_assets',ratio(f('income','total_revenue')-f('income','total_cogs'),assets),'YTD_source_Tushare_total_cogs_proxy',lines=[87,100])
    yield emit('profitability_ttm_assets','毛盈利能力TTM','95.首席质量因子-Gross Profitabilit（简化版）.txt','(TTM revenue-TTM operating_cost)/latest assets',ratio(rv-f('income','oper_cost_ttm'),assets),'TTM_operating_cost_adaptation',lines=[87,100])
    yield emit('cf_yield','经营现金流收益率',q,'TTM operating_cashflow/(total_mv*10000)',ratio(ocf,mv),role='known_control')
    yield emit('cash_accrual_quality','现金盈利差','98.FScore9因子模型改进——RFScore7因子.txt','TTM CFO/mean(latest four quarterly assets)-ROA/100',ratio(ocf,sum(f('balancesheet','total_assets',i) for i in range(4))/4)-roa/100,lines=[1325,1337])
    ebit=f('income','ebit_ttm');debt=sum(f('balancesheet',k) for k in ['st_borr','lt_borr','bond_payable'])
    # Missing optional debt components cannot be treated as a known total debt.
    ev=mv+debt-f('balancesheet','money_cap')
    yield emit('ebit_ev','EBIT/EV','77.*EBIT*EV*.txt','TTM EBIT/(marketcap+st_borr+lt_borr+bond_payable-money_cap); EV>0',ratio(ebit,np.where(ev>0,ev,np.nan)),'debt_cash_EV_and_reported_EBIT_proxy')
    growth='14.四年多翻9倍，年化73%，成长因子评分筛选.txt'
    for key,col in [('growth_sales','tr_yoy'),('growth_profit','netprofit_yoy'),('growth_operating_profit','op_yoy'),('growth_cashflow','ocf_yoy')]:
        yield emit(key,key,growth,f'latest PIT {col}',f('fina_indicator',col),'source_growth_field_mapping_proxy')
    # Five-year sales regression/sales_growth and earnings_growth have no exact
    # documented equivalents; do not silently substitute this four-field mix.
    peg='44.分享一个兼顾业绩增长和PEG指标的股票策略.txt'
    eps_growth=f('fina_indicator','netprofit_yoy');pe=ratio(mv,income)
    yield emit('peg_low','正盈利成长低PEG',peg,'-PE/netprofit_yoy; positive PE and growth; PEG>0.08 as source',np.where((pe>0)&(eps_growth>0)&(ratio(pe,eps_growth)>.08),-ratio(pe,eps_growth),np.nan),'TTM_EPS_growth_proxy',lines=[70,95])
    froe='24.ROE+PB模型的优化.txt'
    old=[f('fina_indicator','roe',i) for i in range(5)]
    delta=sum(w*(old[3-i]-old[4-i]) for i,w in enumerate([.1,.2,.3,.4]))
    yield emit('roe_weighted_improvement','ROE加权改善',froe,'sum(w*(ROE_q_new-ROE_q_old)), w=.1,.2,.3,.4 chronological',delta,lines=[65,74])
    yield emit('roe_improve_lowpb','低PB约束ROE改善',froe,'weighted_ROE_improvement within bottom25% positive PB',np.where(rank(pb)<=.25,delta,np.nan),'source_atom_PB_constraint; debt/bad_asset_filters_removed',lines=[65,74])
    fscore='98.FScore9因子模型改进——RFScore7因子.txt'
    ocfoa=ratio(ocf,sum(f('balancesheet','total_assets',i) for i in range(4))/4)
    lev=ratio(f('balancesheet','total_ncl'),assets);lev1=ratio(f('balancesheet','total_ncl',1),f('balancesheet','total_assets',1))
    roa_y=ratio(roa,f('fina_indicator','roa',4))-1
    margin_y=ratio(f('fina_indicator','grossprofit_margin'),f('fina_indicator','grossprofit_margin',4))-1
    # Source uses a cross-stock scalar mean denominator (a documented bug).
    denom=pd.DataFrame(assets+f('balancesheet','total_assets',1)).mean(axis=1).to_numpy()[:,None]
    denom4=pd.DataFrame(f('balancesheet','total_assets',4)+f('balancesheet','total_assets',5)).mean(axis=1).to_numpy()[:,None]
    turn=ratio(ratio(f('income','revenue'),denom),ratio(f('income','revenue',4),denom4))-1
    legs=[roa,roa_y,ocfoa,ocfoa-roa/100,-(ratio(lev,lev1)-1),margin_y,turn]
    valid=np.isfinite(np.stack(legs)).all(axis=0)
    score=np.where(valid,np.sum(np.stack(legs)>0,axis=0),np.nan)
    yield emit('rfscore7_source','RFScore7原文结构',fscore,'sum(sign>0 of ROA,deltaROA,OCF/avgAssets,accrual,negative_qoq_leverage,deltaMargin,deltaTurn); preserve source scalar turn denominator',score,'quarterly_CFO_TTM_proxy_source_denominator_bug_preserved',lines=[1303,1368])
    yield emit('rfscore7_lowpb','RFScore7×低PB',fscore,'RFScore7 within lowest20% positive PB',np.where(rank(pb)<=.2,score,np.nan),'same_RFScore_proxy_PB_constraint',lines=[1686,1778])
    alloc='24大容量低回撤价值投资-排除小市值因子.txt'
    vol120=rolling(ratio(fields['close'],delay(fields['close']))-1,120,'var')[positions]
    gp=f('fina_indicator','grossprofit_margin');ps=ratio(mv,revenue)
    def mm(x):
        df=pd.DataFrame(x);return df.sub(df.min(axis=1),axis=0).div(df.max(axis=1)-df.min(axis=1),axis=0).to_numpy(dtype=np.float32)
    mask=np.isfinite(np.stack([roic,gp,ps,vol120])).all(axis=0)
    components=[np.where(mask,x,np.nan) for x in [roic,gp,ps,vol120]]
    combo=mm(components[0])+mm(components[1])-mm(components[2])-mm(components[3])
    yield emit('quality_value_lowvar','大容量质量价值低波动',alloc,'CS_minmax(ROIC)+CS_minmax(grossmargin)-CS_minmax(PS)-CS_minmax(var120)',combo,'same_source_cross_section_scaling_TTM_fields_proxy',lines=[52,69])

def corr(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    ok=np.isfinite(x)&np.isfinite(y);x=x[ok];y=y[ok]
    if len(x)<100 or np.std(x)==0 or np.std(y)==0:return np.nan
    return float(np.corrcoef(x,y)[0,1])

def spearman_mean(a,b):
    values=[]
    for x,y in zip(a,b):
        valid=np.isfinite(x)&np.isfinite(y)
        if valid.sum()<100:continue
        values.append(corr(rankdata(x[valid]),rankdata(y[valid])))
    values=np.asarray(values);return float(np.nanmean(values)) if np.isfinite(values).any() else np.nan

def neutralize_size(values,cap):
    # Signal-date cross-sectional rank regression, no outcome labels used.
    result=np.full_like(values,np.nan)
    for i,(x,sz) in enumerate(zip(values,cap)):
        ok=np.isfinite(x)&(sz>0)
        if ok.sum()<100:continue
        a=rankdata(x[ok]);b=np.log(sz[ok]);design=np.column_stack([np.ones(ok.sum()),b])
        result[i,ok]=a-design@np.linalg.lstsq(design,a,rcond=None)[0]
    return result

def maxdd(nav):
    nav=np.asarray(nav,float)
    return float(-np.min(nav/np.maximum.accumulate(nav)-1)) if len(nav) else np.nan

def evaluate(values,dates,stocks,positions,fields):
    c=fields['close'];rows=[];daily=[];prev=None;nav=1.;bench_nav=1.;last_exit=-1
    for i,(date,pos) in enumerate(zip(dates,positions)):
        if pos+11>=len(c):continue
        target=ratio(c[pos+11],c[pos+1])-1
        valid=np.isfinite(values[i])&np.isfinite(target)&(fields['cap'][pos]>0)
        ids=np.flatnonzero(valid)
        if len(ids)<100:continue
        x,y=values[i,ids],target[ids]
        if np.std(x)==0:continue
        order=np.argsort(x,kind='stable');groups=np.ceil(np.arange(1,len(ids)+1)*10/len(ids)).astype(int)
        held=ids[order[groups==10]];group_returns=[float(np.mean(y[order[groups==g]])) for g in range(1,11)]
        current=set(held.tolist());turn=np.nan if prev is None else 1-len(prev&current)/len(current)
        cost=0 if not np.isfinite(turn) else .006*turn
        bench=float(np.mean(y));gross=group_returns[-1];net=gross-bench-cost
        rawtop=ids[order[-20:]][::-1]
        rows.append({'date':date,'entry_date':dates_all[pos+1],'exit_date':dates_all[pos+11],'n':len(ids),'unique_pct':len(np.unique(x))/len(x),'ic':corr(x,y),'rank_ic':corr(rankdata(x),rankdata(y)),
                     'turnover':turn,'group_return':gross,'benchmark':bench,'gross_excess':gross-bench,'net_excess_path':net,'net_held_return':gross-cost,'cost':cost,
                     'top20_raw':';'.join(stocks[rawtop]),**{f'g{g}':group_returns[g-1] for g in range(1,11)}})
        # Buy-and-hold equal initial weights within each ten-day period. Gaps
        # between saved periods hold cash. Costs debit once at entry.
        if pos+1<last_exit:raise ValueError('overlapping reference periods')
        start=nav;start_b=bench_nav
        if not daily:daily.append({'date':dates_all[pos+1],'nav':1.,'benchmark_nav':1.})
        for step in range(1,11):
            hp=float(np.mean(ratio(c[pos+1+step,held],c[pos+1,held])))
            bp=float(np.mean(ratio(c[pos+1+step,ids],c[pos+1,ids])))
            daily.append({'date':dates_all[pos+1+step],'nav':start*(hp-cost),'benchmark_nav':start_b*bp})
        nav=daily[-1]['nav'];bench_nav=daily[-1]['benchmark_nav'];last_exit=pos+11;prev=current
    p=pd.DataFrame(rows);d=pd.DataFrame(daily)
    if p.empty:return {'periods':0},p,d
    multiplier=252/CYCLE;turn=p.turnover.mean();gross=p.gross_excess.mean()*multiplier;fee=turn*.006*multiplier
    ri=p.rank_ic;sd=ri.std()
    result={'periods':len(p),'first_signal':p.date.min(),'last_signal':p.date.max(),'last_exit':p.exit_date.max(),
            'rank_ic':ri.mean(),'ic':p.ic.mean(),'rank_icir':ri.mean()/sd if sd>0 else None,'gross_excess_pct':gross*100,'net_excess_pct':(gross-fee)*100,
            'turnover_pct':turn*100,'annual_cost_pct':fee*100,'held_arithmetic_annual_net_pct':(p.group_return.mean()*multiplier-fee)*100,
            'held_daily_max_drawdown_pct':maxdd(d.nav.to_numpy())*100,
            'held_rebalance_max_drawdown_pct':maxdd(np.r_[1.,np.cumprod(1+p.net_held_return)])*100,
            'synthetic_excess_rebalance_max_drawdown_pct':maxdd(np.r_[1.,np.cumprod(1+p.net_excess_path)])*100,
            'mean_valid_stocks':p.n.mean(),'mean_unique_factor_pct':p.unique_pct.mean()*100,
            'group_arithmetic_annual_pct':{f'g{g}':p[f'g{g}'].mean()*multiplier*100 for g in range(1,11)},
            'years':{str(y):{'periods':len(g),'net_excess_pct':(g.gross_excess.mean()-g.turnover.mean()*.006)*multiplier*100,'rank_ic':g.rank_ic.mean()} for y,g in p.groupby(p.date.dt.year)}}
    return result,p,d

def experiment():
    global dates_all
    OUT.mkdir(parents=True,exist_ok=True)
    dates_all,stocks,fields=load_market()
    requested=pd.DatetimeIndex(pd.to_datetime(read_platform_run(REFERENCE)['dates'])).sort_values().unique()
    positions=dates_all.get_indexer(requested)
    ok=(positions>=0)&(positions+11<len(dates_all))&(requested>='2021-09-07')&(requested<='2026-09-07')
    dates=requested[ok];positions=positions[ok]
    config={'version':VERSION,'repository_version_read':ALIGNMENT_RULE_VERSION,'user_contract':'arithmetic full SH/SZ A, no ST/listing-age constraint','warmup':'20180101','formal_window':['20210907','20260907'],'recent_window':['20260101',str(dates_all.max().date())],'signal_reference':str(REFERENCE.relative_to(ROOT)),'reference_sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),'cycle':10,'label':'close(t+1)->close(t+11)','groups':10,'benchmark':'factor_valid','one_way_cost':.003,'platform_compute_spent':0,'parameter_selection':'frozen source parameters; no grid optimization','correlation':'cross-sectional Spearman then arithmetic mean over saved signal dates; not complete daily correlation','ties':'stable symbol ordering, plus fixed seed daily jitter sensitivity for discrete factors','snapshot_validation':'existence passed; archive hash not reverified','drawdown':'held_daily uses buy-and-hold intra-period paths and costs; excess_rebalance is synthetic spread proxy','first_period_turnover':'excluded from mean, no first entry fee for alignment convention'}
    existing=OUT/'config.json'
    if existing.exists() and json.loads(existing.read_text())!=config:raise ValueError('Incompatible output configuration')
    dump(existing,config)
    caps=fields['cap'][positions]
    previous=pd.read_pickle(OUT/'signal_panels.pkl') if (OUT/'signal_panels.pkl').exists() else {'panels':{},'metadata':[]}
    oldmeta={m['key']:m for m in previous['metadata']}
    allvalues={};metas=[];summaries=[]
    def process(meta,value):
        key=meta['key'];metas.append(meta);allvalues[key]=pd.DataFrame(value,index=dates,columns=stocks)
        if oldmeta.get(key)==meta and key in previous['panels']:
            for window in ['five_year','recent']:summaries.append(json.loads((OUT/window/f'{key}.json').read_text()))
            print('reused',key,flush=True)
            return
        for window,mask in [('five_year',np.ones(len(dates),bool)),('recent',dates>='2026-01-01')]:
            result,p,d=evaluate(value[mask],dates[mask],stocks,positions[mask],fields)
            nd,npd,ndd=evaluate(neutralize_size(value[mask],caps[mask]),dates[mask],stocks,positions[mask],fields)
            result.update({'key':key,'name':meta['name'],'role':meta['role'],'fidelity':meta['fidelity'],'window':window,'size_rank_rho':spearman_mean(value[mask],-caps[mask]),'size_neutral_net_excess_pct':nd.get('net_excess_pct'),'size_neutral_rank_ic':nd.get('rank_ic'),'size_neutral_dd_pct':nd.get('held_daily_max_drawdown_pct')})
            if result.get('mean_unique_factor_pct',100)<20:
                # Fixed deterministic tie sensitivity, not an optimized tiebreak.
                rng=np.random.default_rng(918273)
                jitter=value[mask].astype(float)+rng.random(value[mask].shape)*1e-8
                tie,_,_=evaluate(jitter,dates[mask],stocks,positions[mask],fields)
                result['jitter_net_excess_pct']=tie.get('net_excess_pct');result['jitter_turnover_pct']=tie.get('turnover_pct')
            summaries.append(result)
            folder=OUT/window;folder.mkdir(exist_ok=True)
            dump(folder/f'{key}.json',result);p.to_csv(folder/f'{key}.periods.csv',index=False);d.to_csv(folder/f'{key}.daily_nav.csv',index=False)
            npd.to_csv(folder/f'{key}.size_neutral.periods.csv',index=False)
        dump(OUT/'recipe_manifest.json',metas)
        pd.DataFrame(summaries).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
        print('tested',len(metas),key,round(summaries[-2].get('net_excess_pct',0),3),round(summaries[-1].get('net_excess_pct',0),3),flush=True)
    for meta,value in recipes(fields,positions):process(meta,value)
    for meta,value in additional_market_recipes(fields,positions):process(meta,value)
    fin=financial_snapshot(dates,stocks)
    for meta,value in financial_recipes(fin,fields,positions):process(meta,value)
    fin['income.__quarter__.q0']=income_report_quarters(dates,stocks)
    for meta,value in additional_financial_recipes(fin,fields,positions):process(meta,value)
    for meta,value in bank_and_rank_recipes(fin,fields,positions,dates_all,stocks):process(meta,value)
    for meta,value in supplemental_recipes(fin,fields,positions):process(meta,value)
    pd.to_pickle({'panels':allvalues,'metadata':metas,'dates':dates,'stocks':stocks},OUT/'signal_panels.pkl')
    dump(OUT/'completion.json',{'recipes':len(metas),'windows':2,'signal_periods':len(dates),'formal_last_exit':dates_all[positions[-1]+11],'latest_cache_date':dates_all.max(),'all_recipes_completed':True})


def additional_market_recipes(fields,positions):
    c=fields['close'];r=ratio(c,delay(c))-1;shape=(len(positions),c.shape[1])
    def emit(key,name,pattern,formula,x,fidelity='source_atom_adaptation',role='candidate',lines=None):
        if len(x)==len(c):x=x[positions]
        x=np.asarray(x,dtype=np.float32).copy();x[~(fields['cap'][positions]>0)|~np.isfinite(x)]=np.nan
        return source_meta(key,name,pattern,formula,fidelity,role,lines),x
    path='16.选股因子系列研究(十八) — 价格形态选股因子.txt'
    yield emit('high_open20_paper_positive','开盘冲高-原文正向定义',path,'+mean(log(high/open),20)',rolling(np.log(ratio(fields['high'],fields['open'])),20),'narrative_positive_direction; original model instead subtracts this field',lines=[234,235,589,594])
    yield emit('close_low20_model_positive','盘低回升-原文合成代码方向',path,'+mean(log(close/low),20)',rolling(np.log(ratio(c,fields['low'])),20),'model_code_positive_direction; original narrative calls it inverse',lines=[234,235,589,594])
    sal='90.【复现】凸显度因子.txt'
    stv=np.where(np.abs(r)>=.1,np.abs(r)*100,fields['turnover'])
    value=np.full(shape,np.nan,np.float32)
    for i,p in enumerate(positions):
        ss=stv[p-19:p+1];rr=r[p-19:p+1]
        k=rankdata(-ss,axis=0,method='average',nan_policy='propagate');w=.7**k;w=w/np.mean(w,axis=0)
        value[i]=-np.sum((w-np.mean(w,axis=0))*(rr-np.mean(rr,axis=0)),axis=0)/19
    yield emit('salience_stv_code100','成交凸显度-原代码系数100',sal,'-STR using where(abs(r)>=0.1,100*abs(r),turnover_percent)',value,'literal_code_coefficient100; local turnover_percent units proxy',lines=[364,384])
    trend='82.势的度量.txt'
    for mode in ['monotone','moving_average','compound']:
        value=np.full(shape,np.nan,np.float32)
        for i,p in enumerate(positions):
            prices=c[p-29:p+1].astype(float)
            returns=ratio(prices,delay(prices))-1
            sm=np.sign(returns);sm[0]=0
            ma=rolling(prices,5);ss=np.sign(prices-ma)
            if mode=='monotone':steps=sm
            elif mode=='moving_average':steps=ss
            else:
                sm[sm==0]=-ss[sm==0];ss[ss==0]=sm[ss==0];steps=(sm+ss)/2
            x=np.nancumsum(steps,axis=0)
            # Original cumsum().fillna(0) replaces initial MA warmup with zero.
            invalid=np.any(~np.isfinite(prices),axis=0)
            extrema=np.zeros_like(x,dtype=bool);extrema[0]=True;extrema[-1]=True
            extrema[1:-1]=((x[1:-1]>x[:-2])&(x[1:-1]>x[2:]))|((x[1:-1]<x[:-2])&(x[1:-1]<x[2:]))
            previous=x[0].copy();score=np.zeros(c.shape[1])
            for row in range(1,len(x)):
                hit=extrema[row];score[hit]+=(x[row,hit]-previous[hit])**2;previous[hit]=x[row,hit]
            direct=(np.max(x,axis=0)>np.max(x[1:-1],axis=0))&(np.min(x,axis=0)<np.min(x[1:-1],axis=0))
            score[direct]=(x[-1,direct]-x[0,direct])**2
            score/=29**1.5;score[invalid]=np.nan;value[i]=score
        yield emit('trend_ultimate30_'+mode,'价格路径终极势-'+mode,trend,'ultimate_score(normalize_'+mode+'(close30)); MA5; high score; unsigned strength',value,'source_example30d_generalized_to_fullA',lines=[20,71,244,295])
    capm='71 【投资学】CAPM单因子回归模型+ROE股票池（含止损）.txt'
    market=pd.DataFrame(np.where(fields['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
    m=np.broadcast_to(market[:,None],c.shape)
    cov=pd.DataFrame(r).rolling(120).cov(pd.DataFrame(m)).to_numpy(dtype=np.float32)
    beta=ratio(cov,rolling(m,120,'var'));alpha=rolling(r-.04/252,120)-beta*rolling(m-.04/252,120)
    yield emit('capm_alpha120','滚动CAPM Alpha',capm,'mean(return-rf,120)-beta120*mean(market-rf,120),rf=.04/252',alpha,'fullA_market_proxy_ROE_filter_removed',lines=[127,155])
    # CAPM residual std can be calculated from rolling covariance without
    # fitting one regression on the entire backtest interval.
    residual_var=rolling(r,120,'var')-ratio(cov**2,rolling(m,120,'var'))
    yield emit('capm_residual_vol120_low','低特质波动CAPM','98.复现东方证券研报--特质波动率因子研究.txt','-sqrt(var(return,120)-cov(return,market,120)^2/var(market,120))',-np.sqrt(np.maximum(residual_var,0)),'rolling120_CAPM_fullA_market_proxy','known_control')
    growth_macd='75.量价MACD组合择时——极速版.txt'
    def ema(x,n):return pd.DataFrame(x).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy(dtype=np.float32)
    dif=ema(c,12)-ema(c,26);macd=(dif-ema(dif,9))/c
    yield emit('macd_scaled','MACD技术控制',growth_macd,'(EMA(close,12)-EMA(close,26)-EMA(DIF,9))/close',macd,'index_timing_to_stock_scaled_adaptation','known_control')
    difv=ema(fields['volume'],12)-ema(fields['volume'],26);vmacd=ratio(difv-ema(difv,9),rolling(fields['volume'],26))
    yield emit('volume_macd_scaled','成交量MACD技术控制',growth_macd,'(EMA(volume,12)-EMA(volume,26)-EMA(VDIF,9))/mean(volume,26)',vmacd,'index_timing_to_stock_scaled_adaptation','known_control')
    ar='15.10年52倍，年化59%，全新因子方法超稳定.txt'
    a=ratio(rolling(fields['high']-fields['open'],26,'sum'),rolling(fields['open']-fields['low'],26,'sum'))*100
    b=ratio(rolling(np.maximum(fields['high']-delay(c),0),26,'sum'),rolling(np.maximum(delay(c)-fields['low'],0),26,'sum'))*100
    yield emit('arbr26','ARBR情绪原子',ar,'AR26-BR26 (stock atom; source uses learned bounds, not an alpha direction)',a-b,'ARBR_definition_proxy_without_learned_bounds','known_control',lines=[35,39])

def additional_financial_recipes(fin,fields,positions):
    shape=fields['cap'][positions].shape
    def f(table,col,lag=0):return fin.get(f'{table}.{col}.q{lag}',np.full(shape,np.nan,np.float32))
    assets=f('balancesheet','total_assets');roe=f('fina_indicator','roe');roa=f('fina_indicator','roa');mv=fields['cap'][positions]*10000
    def emit(key,name,pattern,formula,x,fidelity='PIT_field_proxy',role='candidate',lines=None):
        x=np.asarray(x,dtype=np.float32).copy();x[~(mv>0)|~np.isfinite(x)]=np.nan
        return source_meta(key,name,pattern,formula,fidelity,role,lines),x
    q='78.国盛证券多因子.txt'
    yield emit('roa','ROA',q,'latest PIT ROA',roa,role='known_control')
    yield emit('gross_margin','毛利率',q,'latest PIT grossprofit_margin',f('fina_indicator','grossprofit_margin'))
    yield emit('sales_yield','营收市值比',q,'TTM revenue/total_mv',ratio(f('income','total_revenue_ttm'),mv),role='known_control')
    yield emit('earnings_yield','盈利收益率',q,'TTM parent netprofit/total_mv',ratio(f('income','n_income_attr_p_ttm'),mv),role='known_control')
    yield emit('low_leverage','低资产负债率','24.ROE+PB模型的优化.txt','-total_liab/total_assets',-ratio(f('balancesheet','total_liab'),assets),lines=[40,44])
    rd='03 机器学习多因子策略.txt'
    yield emit('rd_assets','研发投入/资产',rd,'latest PIT rd_exp/latest assets',ratio(f('fina_indicator','rd_exp'),assets),'rd_exp_instead_capitalized_development_expenditure_proxy')
    yield emit('rd_market','研发投入/市值',rd,'latest PIT rd_exp/(total_mv*10000)',ratio(f('fina_indicator','rd_exp'),mv),'R&D_intensity_adaptation')
    ml='75.机器学习策略分享.txt'
    for key,col in [('profit_growth_stability','netprofit'),('roa_growth_stability','roa')]:
        if col=='roa':values=[f('fina_indicator','roa',i) for i in [4,3,2,1]]
        else:
            values=[]
            for i in [4,3,2,1]:
                quarter=((fin['income.__quarter__.q0']-1-i)%4)+1
                raw=f('income','n_income',i)
                values.append(np.where(quarter==1,raw,raw-f('income','n_income',i+1)))
        growth=np.stack([ratio(values[i+1],values[i])-1 for i in range(3)])
        value=ratio(np.mean(growth,axis=0),np.std(growth,axis=0,ddof=1))
        yield emit(key,key,ml,'mean(last3 sequential quarterly growth)/sample_std(growth)',value,'ROA_exact_quarter_lags' if col=='roa' else 'single_quarter_netprofit_PIT_proxy',lines=[176,200])
    fs='98.FScore9因子模型改进——RFScore7因子.txt'
    cfo=ratio(f('cashflow','n_cashflow_act'),assets)
    lev=ratio(f('balancesheet','total_ncl'),f('balancesheet','total_nca'))
    lev4=ratio(f('balancesheet','total_ncl',4),f('balancesheet','total_nca',4))
    liq=ratio(f('balancesheet','total_cur_assets'),f('balancesheet','total_cur_liab'))
    liq4=ratio(f('balancesheet','total_cur_assets',4),f('balancesheet','total_cur_liab',4))
    den=pd.DataFrame(assets+f('balancesheet','total_assets',1)).mean(axis=1).to_numpy()[:,None]
    den4=pd.DataFrame(f('balancesheet','total_assets',4)+f('balancesheet','total_assets',5)).mean(axis=1).to_numpy()[:,None]
    turnover=ratio(ratio(f('income','revenue'),den),ratio(f('income','revenue',4),den4))-1
    legs=[roa,cfo,ratio(roa,f('fina_indicator','roa',4))-1,cfo-roa*.01,-(ratio(lev,lev4)-1),ratio(liq,liq4)-1,ratio(f('fina_indicator','grossprofit_margin'),f('fina_indicator','grossprofit_margin',4))-1,turnover,-(ratio(f('balancesheet','total_share'),f('balancesheet','total_share',4))-1)]
    stack=np.stack(legs);score=np.where(np.isfinite(stack).all(axis=0),np.sum(stack>0,axis=0),np.nan)
    yield emit('fscore9_source','FScore9原文结构',fs,'sum(9 source positive-sign components), preserve scalar denominator; total_share instead paidin_capital',score,'YTD_CFO_and_share_issuance_proxy_source_denominator_bug',lines=[288,365])

def income_report_quarters(dates,stocks):
    paths=sorted((CACHE/'financial_full_a/income').glob('*.parquet'))
    cols=['ts_code','ann_date','f_ann_date','end_date','comp_type','report_type','update_flag']
    available=pq.ParquetFile(paths[0]).schema_arrow.names;cols=[c for c in cols if c in available]
    f=pd.concat([pd.read_parquet(p,columns=cols) for p in paths],ignore_index=True)
    if 'f_ann_date' in f:
        f['ann_date']=pd.concat([pd.to_datetime(f.ann_date,errors='coerce'),pd.to_datetime(f.f_ann_date,errors='coerce')],axis=1).max(axis=1)
    f=_prefer_consolidated(_normalise_table(f,'income')).dropna(subset=['ann_date','end_date'])
    result=np.full((len(dates),len(stocks)),np.nan,np.float32)
    for symbol,g in f.groupby('instrument',sort=False):
        j=stocks.get_indexer([symbol])[0]
        if j<0:continue
        g=g.sort_values(['ann_date','end_date','update_flag'])
        ends=g.end_date.cummax();events=pd.DataFrame({'date':g.ann_date,'quarter':ends.dt.quarter}).drop_duplicates('date',keep='last')
        ix=np.searchsorted(events.date.to_numpy(),pd.DatetimeIndex(dates).to_numpy(),side='right')-1;valid=ix>=0
        result[valid,j]=events.quarter.to_numpy()[ix[valid]]
    return result

def daily_pit_field(endpoint,col,calendar,stocks):
    saved=OUT/f'daily_pit_{endpoint}_{col}.pkl'
    if saved.exists():return pd.read_pickle(saved)
    paths=sorted((CACHE/'financial_full_a'/endpoint).glob('*.parquet'))
    available=pq.ParquetFile(paths[0]).schema_arrow.names
    cols=[x for x in ['ts_code','ann_date','f_ann_date','end_date','report_type','comp_type','end_type','update_flag',col] if x in available]
    f=pd.concat([pd.read_parquet(p,columns=cols) for p in paths],ignore_index=True)
    if 'f_ann_date' in f:
        f['ann_date']=pd.concat([pd.to_datetime(f.ann_date,errors='coerce'),pd.to_datetime(f.f_ann_date,errors='coerce')],axis=1).max(axis=1)
    f=_normalise_table(f,endpoint)
    if endpoint!='fina_indicator':f=_prefer_consolidated(f)
    result=np.full((len(calendar),len(stocks)),np.nan,np.float32)
    for symbol,g in f.dropna(subset=['ann_date','end_date']).groupby('instrument',sort=False):
        j=stocks.get_indexer([symbol])[0]
        if j<0:continue
        g=g.sort_values(['ann_date','end_date','update_flag'])
        anns=[];vals=[];current=None;value=np.nan
        for ann,end,v in zip(g.ann_date,g.end_date,g[col]):
            if current is None or end>=current:current=end;value=v
            anns.append(ann);vals.append(value)
        events=pd.DataFrame({'ann':anns,'val':vals}).drop_duplicates('ann',keep='last')
        ix=np.searchsorted(events.ann.to_numpy(),calendar.to_numpy(),side='right')-1;valid=ix>=0
        result[valid,j]=events.val.to_numpy()[ix[valid]]
    pd.to_pickle(result,saved);return result

def bank_and_rank_recipes(fin,fields,positions,calendar,stocks):
    daily_roe=daily_pit_field('fina_indicator','roe',calendar,stocks)
    daily_eq=daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
    pb=ratio(fields['cap']*10000,daily_eq)
    pb250=rolling(np.where(pb>0,pb,np.nan),250)[positions]
    roe250=rolling(daily_roe,250)[positions]/100
    with np.errstate(divide='ignore',invalid='ignore'):
        time=np.log(2*pb250)/np.log1p(roe250)
    alpha=np.where((roe250>-1)&(fields['cap'][positions]>0),-time,np.nan)
    yield source_meta('bank_doubletime250','银行翻倍时间原子','97 银行翻倍策略.txt','-log(2*mean(PB,250))/log(1+mean(ROE,250)/100); meanROE>-1 after /100','fixed_bank_pool_to_fullA_PIT_Tushare_proxy',lines=[47,62]),alpha
    roe=fin['fina_indicator.roe.q0'];bm=ratio(fin['balancesheet.total_hldr_eqy_exc_min_int.q0'],fields['cap'][positions]*10000)
    mask=(roe>0)&(bm>0);pb=ratio(np.ones_like(bm),bm)
    alpha=-rank(np.where(mask,pb,np.nan))-rank(np.where(mask,ratio(np.ones_like(roe),roe),np.nan))
    alpha[~(fields['cap'][positions]>0)]=np.nan
    yield source_meta('roe_pb_equalrank','ROE与PB双排名','51.行业反转效应（年化32%回撤8%).txt','-cs_rank(PB)-cs_rank(1/ROE), both positive','industry_to_fullA_atom_PIT_proxy',lines=[230,241]),alpha

def supplemental_recipes(fin,fields,positions):
    # Remaining directly reconstructible inputs found in the full per-file
    # field-reference pass. Directions are conventional feature diagnostics,
    # not a claimed replication of the source's trained prediction model.
    c=fields['close'];r=ratio(c,delay(c))-1
    for n in [20,120]:
        value=ratio(rolling(r,n),rolling(r,n,'std'))[positions]*np.sqrt(252)
        value[~(fields['cap'][positions]>0)]=np.nan
        pattern='45此消彼长.txt' if n==20 else '75.机器学习策略分享.txt'
        yield source_meta(f'sharpe{n}_atom',f'{n}日收益波动比',pattern,f'mean(return1,{n})/std(return1,{n})*sqrt(252), rf=0','opaque_vendor_sharpe_input_reconstructed_with_rf0','known_control'),value
    value=ratio(fin['balancesheet.money_cap.q0'],fin['balancesheet.total_cur_liab.q0'])
    value[~(fields['cap'][positions]>0)]=np.nan
    yield source_meta('cash_current_liability','现金/流动负债','75.机器学习策略分享.txt','latest PIT money_cap/current_liabilities','cash_to_current_liability_input_proxy','known_control',lines=[264,269]),value
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.prepare:load_market()
    else:experiment()
