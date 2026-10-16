"""Causal full-history AST evaluation shared across peers and their cycles.

Only recent signal panels are disk-cached for inverse search; every expression
is still computed from full daily history beginning in 2018. Formal five-year
verification is a separate output, never mixed with this fitted diagnostic.
"""
from collections import OrderedDict
import hashlib
import json
import pickle
import sys
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from grammar import validate, Expr, field, const, op

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from platform_alignment_rules import ALIGNMENT_RULE_VERSION
from financial import leaves


def correlation(a,b,rank=False):
    mask = np.isfinite(a)&np.isfinite(b)
    if mask.sum()<100:
        return float('nan')
    a,b=a[mask].astype(float),b[mask].astype(float)
    if rank:
        a,b=rankdata(a),rankdata(b)
    a,b=a-a.mean(),b-b.mean()
    denominator=np.sqrt(np.dot(a,a)*np.dot(b,b))
    return float(np.dot(a,b)/denominator) if denominator>0 else float('nan')


def winsor(a,mask):
    a=np.where(mask & np.isfinite(a),a,np.nan).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        lo,hi=np.nanquantile(a,[.01,.99],axis=1)
    return np.clip(a,lo[:,None],hi[:,None])


def standardize(a,mask):
    a=winsor(a,mask)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        mu=np.nanmean(a,axis=1,keepdims=True);sd=np.nanstd(a,axis=1,keepdims=True)
    return np.divide(a-mu,sd,out=np.full_like(a,np.nan),where=sd>0).astype(np.float32)


class Interpreter:
    def __init__(self,fields,cache_size=5):
        self.fields={k:v for k,v in fields.items() if k!='raw_close'}
        self.shape=self.fields['close'].shape
        self.mask=np.isfinite(fields['cap'])&(fields['cap']>0)
        self.cache=OrderedDict();self.cache_size=cache_size

    def evaluate(self,expr):
        validate(expr)
        if expr in self.cache:
            self.cache.move_to_end(expr);return self.cache[expr]
        if expr.op=='field':return self.fields[expr.value]
        if expr.op=='const':return np.broadcast_to(float(expr.value),self.shape)
        args=[self.evaluate(x)for x in expr.args];a=args[0];n=expr.value
        with np.errstate(all='ignore'),warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            if expr.op=='neg':v=-a
            elif expr.op=='abs':v=np.abs(a)
            elif expr.op=='logabs':v=np.log(np.maximum(np.abs(a),1e-12))
            elif expr.op=='sqrtabs':v=np.sqrt(np.abs(a))
            elif expr.op=='zscore':v=standardize(a,self.mask)
            elif expr.op=='rank':
                v=pd.DataFrame(np.where(self.mask,a,np.nan)).rank(axis=1,method='average',pct=True).to_numpy()
            elif expr.op=='add':v=a+args[1]
            elif expr.op=='sub':v=a-args[1]
            elif expr.op=='mul':v=a*args[1]
            elif expr.op=='div':v=np.divide(a,args[1],out=np.full(self.shape,np.nan),where=args[1]!=0)
            elif expr.op=='mean2':v=(a+args[1])/2
            elif expr.op=='max2':v=np.maximum(a,args[1])
            elif expr.op=='min2':v=np.minimum(a,args[1])
            elif expr.op=='less2':v=np.where(np.isfinite(a)&np.isfinite(args[1]),a<args[1],np.nan)
            elif expr.op=='where':v=np.where(np.isfinite(a),np.where(a!=0,args[1],args[2]),np.nan)
            elif expr.op=='delay':
                v=np.full(self.shape,np.nan)
                if n<len(a):v[n:]=a[:-n]
            else:
                df=pd.DataFrame(a,dtype=float)
                if expr.op in ['ema','sma']:
                    alpha=2/(n+1) if expr.op=='ema' else 1/n
                    v=df.ewm(alpha=alpha,adjust=False,min_periods=n).mean().to_numpy()
                else:
                    rolling=df.rolling(n,min_periods=n)
                    if expr.op=='ts_mean':v=rolling.mean().to_numpy()
                    elif expr.op=='ts_std':v=rolling.std(ddof=1).to_numpy()
                    elif expr.op=='ts_sum':v=rolling.sum().to_numpy()
                    elif expr.op=='ts_min':v=rolling.min().to_numpy()
                    elif expr.op=='ts_max':v=rolling.max().to_numpy()
                    elif expr.op=='ts_rank':v=rolling.rank(method='average',pct=True).to_numpy()
                    elif expr.op=='ts_skew':v=rolling.skew().to_numpy()
                    elif expr.op=='ts_kurt':v=rolling.kurt().to_numpy()
                    elif expr.op=='ts_corr':v=rolling.corr(pd.DataFrame(args[1],dtype=float)).to_numpy()
                    elif expr.op=='decaylinear':
                        t=np.arange(len(a),dtype=float)[:,None]
                        sums=rolling.sum().to_numpy()
                        weighted=pd.DataFrame(a.astype(float)*t).rolling(n,min_periods=n).sum().to_numpy()
                        v=(weighted-(t-n)*sums)/(n*(n+1)/2)
                    else:raise ValueError(expr.op)
            v=np.asarray(v,dtype=np.float32)
            v[~np.isfinite(v)]=np.nan
        self.cache[expr]=v
        while len(self.cache)>self.cache_size:self.cache.popitem(last=False)
        return v


class Market:
    def __init__(self,financial=True):
        source=ROOT/'research_reports/platform_alignment/bc-peer-pools-20261012/market_extended.pkl'
        cal,stocks,fields=pickle.load(source.open('rb'))
        self.cal,self.stocks=pd.DatetimeIndex(cal),pd.Index(stocks)
        assert all(str(s).endswith(('.SH','.SZ'))for s in stocks)
        assert self.cal[0]<=pd.Timestamp('20180103')
        self.fields=fields
        if financial:
            self.fields.update(leaves(self.cal,self.stocks,self.fields))
        self.engine=Interpreter(self.fields)
        self.recent_pos=np.flatnonzero(self.cal>=pd.Timestamp('20260801'))
        self.panel_dates=self.cal[self.recent_pos]
        self.panel_map={d:i for i,d in enumerate(self.panel_dates)}
        self.capmask=np.isfinite(fields['cap'])&(fields['cap']>0)
        self.competition_mask=self.capmask.copy()&np.isfinite(fields['turnover'])
        self.competition_mask &=~((fields['volume']<=0)|(fields['amount']<=0)|np.isclose(fields['high'],fields['low'],rtol=1e-8,atol=1e-8))
        names=pd.read_parquet(ROOT/'quantlab/.quantlab/cache/research/cn_equity/stock_basic/namechange.parquet')
        # ST status must allow later removal; rebuild per-symbol status events.
        for symbol,g in names.groupby('ts_code',sort=False):
            j=self.stocks.get_indexer([symbol])[0]
            if j<0:continue
            flags=np.zeros(len(self.cal),bool)
            for r in g.dropna(subset=['start_date']).sort_values('start_date').itertuples():
                ann=max(r.start_date,r.ann_date) if pd.notna(r.ann_date) else r.start_date
                flags[self.cal>=ann]='ST' in str(r.name).upper()
            numeric=self.capmask[:,j]&np.isfinite(fields['turnover'][:,j])
            numeric &=~((fields['volume'][:,j]<=0)|(fields['amount'][:,j]<=0)|np.isclose(fields['high'][:,j],fields['low'][:,j],rtol=1e-8,atol=1e-8))
            self.competition_mask[:,j]=numeric&~flags
        self.cache_dir=HERE/'panels_v3_raw_labels'
        self.cache_dir.mkdir(exist_ok=True)
        self.panel_cache=OrderedDict()
        self.prices=pd.DataFrame(fields['close']).where(fields['close']>0).ffill().to_numpy(np.float32)
        index=pd.read_parquet(ROOT/'research_reports/platform_alignment/peer-evidence-continuation-20261013/index_000985_csi.parquet')
        index.index=pd.to_datetime(index.trade_date)
        self.benchmark=(index.close/index.pre_close-1).reindex(self.cal).to_numpy(float)
        self.context=dict(version='top50-inverse-variable-seats-v3-raw-labels',rule_reference=ALIGNMENT_RULE_VERSION,
            formal_full_a=False,proxy=True,warmup='20180101',prices='qfq',cap='total_mv',
            label='close(t+1)->close(t+cycle+1)',groups=10,one_way_cost=.003,
            IC='competition eligibility/winsor Pearson diagnostic; not canonical formal factor universe',
            inverse_label_prices='preserve unfilled close NaNs like frozen reference; formal verification uses causal close fill',
            benchmark='000985.CSI competition benchmark proxy; formal single-factor benchmark remains factor_valid',
            financial='causal announcement PIT, consolidated statements and restored TTM; explicit field proxies',
            date_start=str(self.panel_dates[0]),date_end=str(self.panel_dates[-1]),symbols=len(stocks),
            all_public_dates_fitted=True,holdout=False,platform_compute=0)
        existing=self.cache_dir/'context.json'
        if existing.exists() and json.loads(existing.read_text())!=self.context:
            raise ValueError('Panel context differs, use new output version')
        existing.write_text(json.dumps(self.context,ensure_ascii=False,indent=2)+'\n')

    def panel(self,expr):
        if expr in self.panel_cache:
            self.panel_cache.move_to_end(expr);return self.panel_cache[expr]
        key=hashlib.sha256(expr.key().encode()).hexdigest()
        path=self.cache_dir/(key+'.npy')
        if path.exists():v=np.load(path)
        else:
            v=self.engine.evaluate(expr)[self.recent_pos].copy()
            temp=path.with_suffix('.tmp')
            with temp.open('wb')as f:np.save(f,v)
            temp.replace(path)
        self.panel_cache[expr]=v
        while len(self.panel_cache)>240:self.panel_cache.popitem(last=False)
        return v


def initial_bank():
    c,a,t,cap,v,h,l,o=[field(k)for k in ['close','amount','turnover','cap','volume','high','low','open']]
    ret=op('sub',op('div',c,op('delay',c,window=1)),const(1))
    roots=[field(k)for k in ['close','amount','turnover','cap','volume','bm','ep','cfp','sp','roe','roic','gm','assets_growth','current_ratio','leverage']]
    seeds=roots.copy()
    for x in roots:
        seeds +=[op('rank',x),op('logabs',x),op('sqrtabs',x),op('div',const(1),x)]
    for n in [3,5,6,10,14,20,30,40,60,120,252]:
        momentum=op('sub',op('div',c,op('delay',c,window=n)),const(1))
        vol=op('ts_std',ret,window=n)
        seeds += [momentum,vol,op('ts_std',op('min2',ret,const(0)),window=n),
            op('sub',op('div',c,op('ts_mean',c,window=n)),const(1)),
            op('sub',op('div',c,op('ts_max',h,window=n)),const(1)),
            op('sub',op('div',c,op('ts_min',l,window=n)),const(1)),
            op('ts_mean',op('div',op('sub',h,l),c),window=n),
            op('ts_mean',op('div',op('abs',ret),a),window=n),
            op('ts_skew',ret,window=n),op('ts_kurt',ret,window=n),
            op('ts_corr',c,v,window=n),op('ts_corr',ret,op('delay',ret,window=1),window=n)]
        for x in [a,t,v]:
            ma=op('ts_mean',x,window=n)
            seeds +=[ma,op('rank',ma),op('ts_std',x,window=n),op('div',x,ma),
                     op('div',op('ts_std',x,window=n),ma),op('ts_rank',x,window=n)]
        delta=op('sub',c,op('delay',c,window=1))
        up=op('sma',op('max2',delta,const(0)),window=n)
        down=op('sma',op('max2',op('neg',delta),const(0)),window=n)
        seeds += [op('div',up,op('add',up,down)),op('div',op('sub',c,o),o),
                  op('div',op('sub',op('mul',const(2),c),op('add',h,l)),op('sub',h,l))]
    bm=op('rank',field('bm'))
    for n in [5,20,40,60,120]:
        rev=op('neg',op('sub',op('div',c,op('delay',c,window=n)),const(1)))
        lv=op('neg',op('ts_std',ret,window=n))
        for x in [rev,lv,op('neg',op('ts_mean',t,window=n))]:
            seeds +=[op('mul',bm,op('rank',x)),op('add',bm,op('rank',x)),
                op('add',op('zscore',field('bm')),op('zscore',x)),
                op('add',op('rank',op('neg',cap)),op('rank',x))]
    return list(dict.fromkeys(seeds))
