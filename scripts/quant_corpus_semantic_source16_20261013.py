"""Six previously untested source-grounded daily factor mechanisms.

All parameters are frozen from the source notes before evaluation.  This is
offline only: no PandaAI calls and no changes to the original quant corpus.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata

import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual

OUT = q.ROOT / "research_reports/platform_alignment/quant-corpus-semantic-source16-20261013"
SOURCE = {
    "downside_vol63_low": "quant/2022年度精选策略/90.相信波动率还是相信基本面？波动与估值因子A股驱动力测试.txt",
    "downside_asymmetry63_low": "quant/2022年度精选策略/90.相信波动率还是相信基本面？波动与估值因子A股驱动力测试.txt",
    "overnight_gap60_low": "quant/2022年度精选策略/19.a股跳一跳复现v4.txt",
    "breakout30_strength": "quant/2021年度精选策略/41.均线黏合，突破前三十个交易日最高点选股法.txt",
    "trend_stack55": "quant/2021年度精选策略/41.均线黏合，突破前三十个交易日最高点选股法.txt",
    "cov_slope60_240": "quant/2023年度精选策略/91.致敬市场--4 解析细节.txt",
}

SPECS = [
    ("downside_vol63_low", "63日下行波动低", "-sqrt(mean(min(ret-mean63(ret),0)^2,63))", "downside volatility, low is preferred"),
    ("downside_asymmetry63_low", "63日下行/总波动比低", "-downside_std63/std63", "downside asymmetry, low is preferred"),
    ("overnight_gap60_low", "60日隔夜跳空绝对幅度低", "-mean(abs(open/lag(close)-1),60)", "overnight gap stability, low is preferred"),
    ("breakout30_strength", "30日新高突破强度", "close/max(high[-30:-1])-1", "continuous breakout distance; previous 30 observations"),
    ("trend_stack55", "13/34/55日均线多头排列强度", "(MA13/MA34-1)+(MA34/MA55-1)", "continuous moving-average stack strength"),
    ("cov_slope60_240", "系统协方差短长变化", "-(cov60-cov240)", "declining short-horizon covariance preferred"),
]

def dump(path, value):
    def clean(v):
        if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)): return [clean(x) for x in v]
        if isinstance(v, (np.integer,)): return int(v)
        if isinstance(v, (float, np.floating)): return float(v) if np.isfinite(v) else None
        return v
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, default=str, allow_nan=False)+"\n", encoding="utf-8")

def rho(x, y):
    vals=[]
    for a,b in zip(x,y):
        ok=np.isfinite(a)&np.isfinite(b)
        if ok.sum()>=100: vals.append(np.corrcoef(rankdata(a[ok]),rankdata(b[ok]))[0,1])
    return float(np.nanmean(vals)) if vals else np.nan

def truncation_checks(fields, values, dates, pos):
    # Each construction uses only trailing windows. Recompute a few prefixes
    # directly and compare the saved full-array prefix.
    checks=[]
    for stop in [1200, 1700, len(dates)-31]:
        c={k:v[:stop] for k,v in fields.items()}
        fresh=build_values(c)
        for key in values:
            np.testing.assert_allclose(values[key][:stop], fresh[key], equal_nan=True, atol=2e-5, rtol=2e-5)
        checks.append({"check":"future_truncation", "stop":stop, "passed":True})
    return checks

def build_values(f):
    c,o,h,l,v,cap=[f[k].astype(float) for k in ["close","open","high","low","volume","cap"]]
    r=q.ratio(c,q.delay(c))-1
    m63=q.rolling(r,63)
    dev=np.minimum(r-m63,0.0)
    down=np.sqrt(q.rolling(dev*dev,63))
    total=q.rolling(r,63,"std")
    gap=np.abs(q.ratio(o,q.delay(c))-1)
    ma13=q.rolling(c,13); ma34=q.rolling(c,34); ma55=q.rolling(c,55)
    # previous 30 observations: delay before rolling max avoids including t
    prev30=q.rolling(q.delay(h),30,"max")
    # full-A equal-weight market return proxy for covariance
    market=pd.DataFrame(np.where(cap>0,r,np.nan)).mean(axis=1).to_numpy()
    m=np.broadcast_to(market[:,None],r.shape)
    cov60=pd.DataFrame(r).rolling(60).cov(pd.DataFrame(m)).to_numpy(dtype=np.float32)
    cov240=pd.DataFrame(r).rolling(240).cov(pd.DataFrame(m)).to_numpy(dtype=np.float32)
    return {
        "downside_vol63_low": -down,
        "downside_asymmetry63_low": -q.ratio(down,total),
        "overnight_gap60_low": -q.rolling(gap,60),
        "breakout30_strength": q.ratio(c,prev30)-1,
        "trend_stack55": q.ratio(ma13,ma34)-1 + q.ratio(ma34,ma55)-1,
        "cov_slope60_240": -(cov60-cov240),
    }

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    calendar, stocks, fields = q.load_market(); q.dates_all=calendar
    saved=pd.read_pickle(q.OUT/'signal_panels.pkl')
    grid=pd.DatetimeIndex(saved['dates']); pos=calendar.get_indexer(grid)
    values_all=build_values(fields)
    checks=truncation_checks(fields, values_all, calendar, pos)
    q.dump(OUT/'verification.json', checks)
    cfg={"version":q.ALIGNMENT_RULE_VERSION+"-quant-source16-20261013-arithmetic-fullA",
         "formal_window":["20210907","20260907"],"recent_window":["20260101",str(calendar.max().date())],
         "warmup":"20180101","universe":"SH/SZ fullA","qfq":True,"market_cap":"total_mv",
         "cycle":10,"groups":10,"label_offset":1,"one_way_cost":0.003,"benchmark":"factor_valid",
         "platform_net_filter":"all","platform_compute_spent":0,"hypotheses":len(SPECS),
         "parameter_selection":"source-fixed before outcome evaluation","pool_test_done":False,
         "proxy":"full-A equal-weight market covariance; all other fields qfq daily cache"}
    dump(OUT/'config.json', cfg)
    cap=fields['cap'][pos]; rev=-(q.ratio(fields['close'],q.delay(fields['close'],20))-1)[pos]
    iv=np.full_like(fields['close'],np.nan)
    # Known low-IVOL diagnostic proxy for incremental information only.
    market=pd.DataFrame(np.where(fields['cap']>0,q.ratio(fields['close'],q.delay(fields['close']))-1,np.nan)).mean(axis=1).to_numpy()
    rr=q.ratio(fields['close'],q.delay(fields['close']))-1
    cov120=pd.DataFrame(rr).rolling(120).cov(pd.DataFrame(np.broadcast_to(market[:,None],rr.shape))).to_numpy()
    mm=pd.DataFrame(np.broadcast_to(market[:,None],rr.shape))
    iv=-np.sqrt(np.maximum(q.rolling(rr,120,'var')-q.ratio(cov120**2,mm.rolling(120).var().to_numpy()),0))
    rows=[]; corr_rows=[]; panels={}; metadata=[]
    for key,name,formula,fidelity in SPECS:
        x=values_all[key][pos].astype(np.float32)
        x[~((cap>0)&np.isfinite(x))]=np.nan
        meta={"key":key,"name":name,"formula":formula,"direction":1,"source_paths":[SOURCE[key]],
              "source_sha256":[hashlib.sha256((q.ROOT/SOURCE[key]).read_bytes()).hexdigest()],
              "fidelity":fidelity,"source_text_read":True,"execution":"offline signal extraction; original strategy execution not reproduced"}
        metadata.append(meta); panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
        forms={"raw":x,"size_reversal_rank_residual":dual_residual(x,-cap,rev),
               "size_reversal_ivol_rank_residual":dual_residual(dual_residual(x,-cap,rev),-iv[pos],np.zeros_like(rev))}
        for form,score in forms.items():
            for window,mask in [("five_year",np.ones(len(grid),bool)),("recent",grid>='20260101')]:
                a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],fields)
                a.update({"key":key,"name":name,"window":window,"form":form,"fidelity":fidelity,
                          "coverage_pct":100*a.get('periods',0)/mask.sum()})
                rows.append(a); folder=OUT/window; folder.mkdir(exist_ok=True)
                dump(folder/f'{key}.{form}.json',a); p.to_csv(folder/f'{key}.{form}.periods.csv',index=False); d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
        for anchor,y in [("size",-cap),("reversal20",rev),("known_low_ivol",iv[pos]),("market_cov240",-q.rolling(pd.DataFrame(rr).rolling(240).cov(pd.DataFrame(np.broadcast_to(market[:,None],rr.shape))).to_numpy(),1)[pos])]:
            corr_rows.append({"candidate":key,"anchor":anchor,"mean_daily_cs_spearman":rho(x,y)})
        print(key, [(r['form'],r['window'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2),round(r.get('turnover_pct',0),2)) for r in rows[-6:]], flush=True)
    pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
    pd.DataFrame(corr_rows).to_csv(OUT/'daily_old_anchor_correlations.csv',index=False)
    dump(OUT/'recipe_manifest.json',metadata)
    pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':metadata},OUT/'signal_panels.pkl')
    dump(OUT/'completion.json',{"completed":True,"hypotheses":len(SPECS),"rows":len(rows),"platform_compute_spent":0,"formal_last_signal":str(grid.max()),"last_exit":str(calendar[pos[-1]+11]),"pool_test_done":False})

if __name__=='__main__': main()
