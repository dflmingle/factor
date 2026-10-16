"""Remaining wizard financial intersections, explicitly unavailable wizard internals."""
import json,sys
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
sys.path.insert(0,str(q.ROOT/'research_reports/platform_alignment/quant-corpus-talib-runtime-20261013'))
import talib
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
S36='quant/2020年度精选策略/36 投资学作业——简单多因子选股策略改进.txt'
S74='quant/2020年度精选策略/74 基于沪深300的增强.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source72-20261013'
SPECS=[spec('wizard36_growth_size_pe_roe_source','投资学作业四项实际加权交集',S36,
 '.30rank(profit_yoy)+.20rank(cap)+.25rank(PE)+.25rank(ROE);revenue_yoy>5,MV亿元>30,PE>3,ROE>4',
 'proxy: actual allDESC weights30/20/25/25 and source gates, vendorwizard rank function unavailable so percentile proxy; fullA replacesHS300/allindustries, PE PITparentNI_TTM'),
 spec('wizard74_grossmargin_atr_source','沪深增强毛利率低ATR交集',S74,
 'high grossprofitmargin on PB<2,ROA>1,netmargin>10,grossmargin>10,ATR14<.5',
 'proxy: original wizardATR_judge_xiaoyu unavailable, TA-Lib WilderATR14 mappeddailyqfq absolute-price .5 threshold; current savedclose/fullA ratherthan sourceHS300/open, qualified benchmark; no byte-equivalence claim')]
for s in SPECS:s['gated']=True

def values(fin,f,pos,atr):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 cap=f['cap'][pos].astype(float);pe=q.ratio(cap*10000,g('income','n_income_attr_p_ttm'));pb=q.ratio(cap*10000,g('balancesheet','total_hldr_eqy_exc_min_int'));roe=g('fina_indicator','roe');profit=g('fina_indicator','netprofit_yoy')
 qual=(g('fina_indicator','or_yoy')>5)&(cap/10000>30)&(pe>3)&(roe>4)
 score=.30*q.rank(np.where(qual,profit,np.nan))+.20*q.rank(np.where(qual,cap,np.nan))+.25*q.rank(np.where(qual,pe,np.nan))+.25*q.rank(np.where(qual,roe,np.nan))
 margin=g('fina_indicator','grossprofit_margin');qual=(pb<2)&(g('fina_indicator','roa')>1)&(g('fina_indicator','netprofit_margin')>10)&(margin>10)&(atr[pos]<.5)
 return [score,np.where(qual,margin,np.nan)]

def atr_values(f):
 out=np.full(f['close'].shape,np.nan)
 for j in range(out.shape[1]):
  h,l,c=[f[k][:,j].astype(float) for k in ['high','low','close']];valid=np.isfinite(h)&np.isfinite(l)&np.isfinite(c)
  # Process each contiguous block: no missing high/low fabrication.
  edges=np.flatnonzero(np.diff(np.r_[False,valid,False]));
  for start,end in zip(edges[::2],edges[1::2]):
   if end-start>14:out[start:end,j]=talib.ATR(h[start:end],l[start:end],c[start:end],timeperiod=14)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks);atr=atr_values(f);small={k:v[:,:256] for k,v in f.items()};full=atr[:,:256]
 checks=[]
 for stop in [1200,len(cal)-31]:
  np.testing.assert_allclose(full[:stop],atr_values({k:v[:stop] for k,v in small.items()}),equal_nan=True,atol=1e-8);checks.append(dict(test='contiguous_WilderATR_prefix_recompute',stop=stop,passed=True))
 q.dump(OUT/'financial_cache_contract.json',dict(source=str(q.OUT/'financial_signal_snapshots.pkl'),source_rule=q.ALIGNMENT_RULE_VERSION,snapshot_origin='original cohort PIT replay financial_snapshot; no new field substitutions',reused=True))
 vals=values(fin,f,pos,atr);q.dump(OUT/'qualification_coverage.json',{s['key']:np.isfinite(v).sum(axis=1).tolist() for s,v in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='wizard rank/ATR explicit proxies; original strategy not reproduced',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED72',flush=True)
if __name__=='__main__':main()
