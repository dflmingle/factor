#!/usr/bin/env python3
"""Local daily proxies for three newly reviewed nested strategies.

No source strategy execution is reproduced.  Signals are causal daily proxies
under the fixed arithmetic full-A alignment contract.
"""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from platform_alignment_rules import ALIGNMENT_RULE_VERSION

ROOT=q.ROOT
OUT=ROOT/'research_reports/platform_alignment/quant-corpus-nested-local-20261012'
CYCLE=10

def dump(path,obj):
    def clean(v):
        if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)): return [clean(x) for x in v]
        if isinstance(v,(np.integer,)): return int(v)
        if isinstance(v,(float,np.floating)): return float(v) if np.isfinite(v) else None
        return v
    path.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')

def shift(x,n=1): return q.delay(x,n)
def roll(x,n,method='mean'):
    return getattr(pd.DataFrame(x).rolling(n,min_periods=n),method)().to_numpy(dtype=np.float32)
def all_true(cond,n):
    return (pd.DataFrame(cond.astype(float)).rolling(n,min_periods=n).sum().to_numpy()==n)

def source_meta(key,name,path,formula,fidelity):
    p=ROOT/path
    return {'key':key,'name':name,'source_paths':[path],
            'source_sha256':[hashlib.sha256(p.read_bytes()).hexdigest()],
            'formula':formula,'direction':1,'fidelity':fidelity,
            'strategy_execution_reproduced':False}

def build(f):
    c,o,h,l,v,cap=[f[k] for k in ['close','open','high','low','volume','cap']]
    r=q.ratio(c,shift(c))-1
    # Strong rise, 10-20% retreat, and three-day volume/price stabilization.
    first_ret=q.ratio(shift(c,7),shift(c,30))-1
    first_high=shift(roll(h,23,'max'),7)
    retr=q.ratio(first_high-c,first_high)
    stable=all_true(np.abs(r)<=.03,3)&(v<shift(v,2))&(c>=shift(c,3))
    p1=np.where((first_ret>=.20)&(retr>=.10)&(retr<=.20)&stable,-retr,np.nan)

    # MA5>MA20, 5-15% ten-day pullback, and low ATR14/price.
    ma5=roll(c,5);ma20=roll(c,20);hi10=roll(c,10,'max')
    dd=q.ratio(hi10-c,hi10)
    tr=np.maximum(h-l,np.maximum(np.abs(h-shift(c)),np.abs(l-shift(c))))
    atr14=q.ratio(roll(tr,14),c)
    p2=np.where((ma5>ma20)&(dd>=.05)&(dd<=.15)&(atr14<=.05)&(c>=ma5),-(dd+atr14),np.nan)

    # Recent limit-up then MA reclaim, volume burst, and pullback (daily proxy:
    # a 9.5% close-to-close move approximates the standard 10% limit).
    lim=r>=.095
    past_count=shift(roll(lim.astype(float),10,'sum'),1)
    ma5_prev=shift(ma5);ma10=roll(c,10);ma10_prev=shift(ma10)
    dd5=q.ratio(roll(h,5,'max')-c,roll(h,5,'max'))
    p3=np.where((past_count>=1)&(past_count<=2)&(~lim)&(c>ma10)&(shift(c)>ma10_prev)&(shift(c)<=shift(ma5)*1.01)&(c>ma5)&(v>roll(v,20)*1.3)&(q.ratio(np.abs(ma5-ma10),ma10)>.01)&(dd5>.05),-dd5,np.nan)
    for x in (p1,p2,p3): x[cap<=0]=np.nan
    return [p1,p2,p3]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    calendar,stocks,f=q.load_market();q.dates_all=calendar;q.CYCLE=CYCLE
    saved=pd.read_pickle(ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source5-20261012/signal_panels.pkl')
    grid=pd.DatetimeIndex(saved['dates']); pos=calendar.get_indexer(grid)
    ok=(pos>=0)&(pos+CYCLE+1<len(calendar));grid=grid[ok];pos=pos[ok]
    cfg={'version':ALIGNMENT_RULE_VERSION+'-nested-daily-proxies-arithmetic-fullA','formal_window':['20210907','20260907'],'recent_window':['20260101',str(calendar.max().date())],'warmup':'20180101','universe':'SH/SZ fullA; active total_mv>0','qfq':True,'market_cap':'total_mv','cycle':CYCLE,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid','platform_compute_spent':0,'source_execution_reproduced':False,'proxy_note':'daily adaptations; auction/portfolio execution omitted'}
    dump(OUT/'config.json',cfg)
    vals=build(f); results=[]; metas=[]; panels={}
    specs=[
      ('pullback_stabilization','强势上涨后回撤缩量企稳','quant/量化策略/量化策略/首板回调买入策略2026/02上升途中回调到位-优化版-25年42.txt','RET22>=20%; retrace10-20%; abs(RET1)<=3% for 3d; V_t<V_{t-2}; C_t>=C_{t-3}','daily proxy; source buys 09:45'),
      ('trend_pullback_lowatr','趋势回撤低ATR','quant/量化策略/量化策略/首板回调买入策略2026/08上升趋势-回档买入-25年0.78.txt','MA5>MA20; drawdown10 5-15%; ATR14/C<=5%; C>=MA5','daily proxy; source randomizes execution'),
      ('limitup_reclaim_pullback','涨停后均线回收放量回撤','quant/量化策略/量化策略/首板回调买入策略2026/09涨停回调止盈止损-25年30.62.txt','past10 limit count 1-2; C>MA10; MA5 reclaim; V>1.3*MA20; MA distance>1%; drawdown5>5%','daily proxy; 9.5% limit approximation')]
    for (key,name,path,formula,fidelity),x in zip(specs,vals):
        meta=source_meta(key,name,path,formula,fidelity);metas.append(meta);panels[key]=pd.DataFrame(x[pos],index=grid,columns=stocks)
        for window,mask in [('five_year',(grid>='20210907')&(grid<='20260907')),('recent',grid>='20260101')]:
            folder=OUT/window;folder.mkdir(exist_ok=True)
            res,p,d=q.evaluate(x[pos][mask],grid[mask],stocks,pos[mask],f)
            res.update({'key':key,'name':name,'window':window,'fidelity':fidelity,'coverage_pct':100*res.get('periods',0)/mask.sum()})
            dump(folder/f'{key}.json',res);p.to_csv(folder/f'{key}.periods.csv',index=False);d.to_csv(folder/f'{key}.daily_nav.csv',index=False);results.append(res)
    pd.DataFrame(results).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
    dump(OUT/'recipe_manifest.json',metas);pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':metas},OUT/'signal_panels.pkl')
    dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(results),'platform_compute_spent':0,'formal_last_signal':str(grid.max().date()),'latest_cache_date':str(calendar.max().date())})
    print(pd.DataFrame(results)[['key','window','net_excess_pct','turnover_pct','held_daily_max_drawdown_pct','periods']].to_string(index=False))

if __name__=='__main__': main()
