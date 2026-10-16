"""Three fixed source hypotheses, offline; explicitly labelled daily proxies."""
import hashlib
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_correlations_20261012 import rho_details
from quant_corpus_semantic_local_20261012 import dual_residual

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source5-20261012'
SPECS=[
 ('idio_vroc_size','低特质波动×低量增×小规模','67.',
  '-sum(winsor5_93(cs_z(CAPM_residual_std120), cs_z(100*(V/lag12(V)-1)), cs_z(log(total_mv))))',
  'Barra residual_volatility→rolling120 CAPM equal-weight fullA proxy; size→log(total_mv); source quarterly/monthly execution removed'),
 ('rising_trend_pullback','上升长趋势中的回调','61.',
  '1-C/MA60(C), valid only when MA60>=lag1(MA60)>=lag2(MA60), C<MA60 and MA5>lag1(MA5)',
  'ETF gate adapted to fullA; eligible stocks ranked by pullback depth; factor_valid benchmark is eligible subset; not original first-ETF execution'),
 ('fresh_high_gap252','久未新高后的252日新高','99.',
  'argmax(C252)==251 and argmax(C252[:-1])<191, ties choose first occurrence',
  'individual binary event extracted from market breadth; stable-symbol tie diagnostic plus fixed-seed jitter; not breadth timing return'),
]

@njit(cache=True)
def fresh_high(c):
 out=np.full(c.shape,np.nan,np.float32)
 for j in range(c.shape[1]):
  for t in range(251,len(c)):
   w=c[t-251:t+1,j]
   if not np.isfinite(w).all():continue
   out[t,j]=1. if np.argmax(w)==251 and np.argmax(w[:-1])<191 else 0.
 return out

def build(f):
 c=f['close'];r=q.ratio(c,q.delay(c))-1
 m=pd.DataFrame(np.where(f['cap']>0,r,np.nan)).mean(axis=1).to_numpy()
 mf=pd.DataFrame(np.broadcast_to(m[:,None],c.shape))
 cov=pd.DataFrame(r).rolling(120).cov(mf).to_numpy()
 iv=np.sqrt(np.maximum(q.rolling(r,120,'var')-q.ratio(cov**2,mf.rolling(120).var().to_numpy()),0))
 terms=[iv,100*(q.ratio(f['volume'],q.delay(f['volume'],12))-1),np.log(np.where(f['cap']>0,f['cap'],np.nan))]
 total=np.zeros_like(c)
 for term in terms:
  term=np.where(f['cap']>0,term,np.nan)
  z=pd.DataFrame(q.zscore(term));lo=z.quantile(.05,axis=1);hi=z.quantile(.93,axis=1)
  total+=z.clip(lower=lo,upper=hi,axis=0).to_numpy(dtype=np.float32)
 ma60=q.rolling(c,60);ma5=q.rolling(c,5)
 gate=(ma60>=q.delay(ma60))&(q.delay(ma60)>=q.delay(ma60,2))&(c<ma60)&(ma5>q.delay(ma5))
 pullback=np.where(gate,1-q.ratio(c,ma60),np.nan)
 return [-total,pullback,fresh_high(c)],iv

def verify(f):
 ids=np.flatnonzero(np.isfinite(f['close'][-700:]).all(axis=0))[:5]
 small={k:v[:,ids] for k,v in f.items()};full,_=build(small);checks=[]
 for stop in [900,1400,len(f['close'])-31]:
  trunc,_=build({k:v[:stop] for k,v in small.items()})
  for i in range(3):np.testing.assert_allclose(full[i][:stop],trunc[i],equal_nan=True,atol=1e-6,rtol=1e-5)
  checks.append({'check':'prefix_recompute_all_three','stop':stop,'passed':True})
 # Independently check the event's exact first-argmax / gap boundary.
 w=np.ones((270,3),np.float32)
 # The last 252-observation window starts at row 18: keep old peaks inside it.
 w[30,0]=2;w[-1,0]=3;w[-20,1]=2;w[-1,1]=3;w[30,2]=3;w[-1,2]=3
 np.testing.assert_array_equal(fresh_high(w)[-1],np.array([1,0,0]))
 checks.append({'check':'fresh_high_old_peak_recent_peak_equal_peak','passed':True})
 return checks

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 calendar,stocks,f=q.load_market();q.dates_all=calendar
 saved=pd.read_pickle(q.OUT/'signal_panels.pkl');grid=saved['dates'];pos=calendar.get_indexer(grid)
 cfg={'version':q.ALIGNMENT_RULE_VERSION+'-quant-source5-user-arithmetic-fullA','formal_window':['20210907','20260907'],
  'recent_window':['20260101',str(calendar.max().date())],'warmup':'20180101','universe':'SH/SZ fullA; active total_mv>0',
  'qfq':True,'market_cap':'total_mv','cycle':10,'groups':10,'label_offset':1,'one_way_cost':.003,'benchmark':'factor_valid',
  'annualization':'arithmetic','platform_net_filter':'all','platform_compute_spent':0,'source_fixed_hypotheses':3,'direction':1,
  'oos':False,'failure_registry':'qualitygate3 registry is stale vs qualitygate4; blocked_fields empty; only OHLCV/total_mv used',
  'ties':'stable symbol primary; binary random jitter diagnostic seeded918273; residual diagnostic can reintroduce ordering',
  'scope':'signal extraction; no source strategy execution or official pool reproduction'}
 if (OUT/'config.json').exists() and json.loads((OUT/'config.json').read_text())!=cfg:raise ValueError('incompatible output')
 q.dump(OUT/'config.json',cfg);q.dump(OUT/'verification.json',verify(f))
 values,iv=build(f);print('built source5 hypotheses',flush=True)
 days=np.flatnonzero((calendar>='20210907')&(calendar<='20260907'))
 c=f['close'];r=q.ratio(c,q.delay(c))-1;cap=f['cap'];turn=f['turnover'];v=f['volume']
 def sampled(x):
  x=np.asarray(x,np.float32).copy();x[~(cap>0)]=np.nan;return x[days]
 eq=q.daily_pit_field('balancesheet','total_hldr_eqy_exc_min_int',calendar,stocks)
 roe=q.daily_pit_field('fina_indicator','roe',calendar,stocks)
 anchors={
  'B01|SIZE-ONLY':sampled(-cap),'B02|TURN-BIAS-21/504':sampled(1-q.ratio(q.rolling(turn,21),q.rolling(turn,504))),
  'B03|RET40':sampled(-(q.ratio(c,q.delay(c,40))-1)),'B04|DD120':sampled(1-q.ratio(c,q.rolling(c,120,'max'))),
  'B05|CHIP250':sampled(q.ratio(q.ratio(q.rolling(v*(f['open']+c)/2,250,'sum'),q.rolling(v,250,'sum')),c)-1),
  'B08|BM_latest_proxy':sampled(q.ratio(eq,cap*10000)),'B09|DD60':sampled(1-q.ratio(c,q.rolling(c,60,'max'))),
  'N01|REV20':sampled(-(q.ratio(c,q.delay(c,20))-1)),'N08|TURN_STD21':sampled(-q.rolling(turn,21,'std')),
  'N09|MAX21':sampled(-q.rolling(r,21,'max')),'N16|SKEW60':sampled(-q.rolling(r,60,'skew')),
  'N27|ROE_latest_proxy':sampled(roe),'known|CAPM_IVOL120':sampled(-iv),
  'unassigned|H03-IMPACT60':sampled(q.ratio(q.rolling(q.ratio(f['high']-f['low'],q.delay(c)+1e-6),60,'sum'),q.rolling(f['amount'],60,'sum')+1)),
  'composite|WEIGHTED-REV21':sampled(-q.ratio(q.rolling(turn*r,21,'sum'),q.rolling(turn,21,'sum')))}
 del eq,roe,iv
 results=[];corrs=[];manifest=[];panels={}
 for spec,allx in zip(SPECS,values):
  key,name,prefix,formula,fidelity=spec;allx[~(cap>0)]=np.nan;x=allx[pos]
  source=next((q.ROOT/'quant/2024年度精选策略2').glob(prefix+'*.txt'))
  meta={'key':key,'name':name,'formula':formula,'direction':1,'source_paths':[str(source.relative_to(q.ROOT))],
   'source_sha256':[hashlib.sha256(source.read_bytes()).hexdigest()],'fidelity':fidelity,'strategy_execution_reproduced':False}
  manifest.append(meta);panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  residual=dual_residual(x,-cap[pos],-(q.ratio(c,q.delay(c,20))-1)[pos])
  forms=[('raw',x),('size_reversal_rank_residual',residual)]
  if key=='fresh_high_gap252':
   forms.append(('fixed_seed_tie_jitter',x.astype(float)+np.random.default_rng(918273).random(x.shape)*1e-8))
  for window,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
   folder=OUT/window;folder.mkdir(exist_ok=True)
   for form,score in forms:
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],f)
    a.update(key=key,name=name,window=window,form=form,coverage_pct=a['periods']/mask.sum()*100,fidelity=fidelity)
    results.append(a);q.dump(folder/f'{key}.{form}.json',a)
    p.to_csv(folder/f'{key}.{form}.periods.csv',index=False);d.to_csv(folder/f'{key}.{form}.daily_nav.csv',index=False)
  for anchor,y in anchors.items():corrs.append({'candidate':key,'anchor':anchor,'scope':'daily_cross_sectional_spearman_mean',**rho_details(allx[days],y)})
  pd.DataFrame(results).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
  pd.DataFrame(corrs).to_csv(OUT/'daily_old_anchor_correlations.csv',index=False);q.dump(OUT/'recipe_manifest.json',manifest)
  print('completed',key,flush=True)
 pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':manifest},OUT/'signal_panels.pkl')
 q.dump(OUT/'completion.json',{'completed':True,'hypotheses':3,'rows':len(results),'correlations':len(corrs),
  'formal_last_signal':grid.max(),'last_exit':calendar[pos[-1]+11],'latest_cache_date':calendar.max(),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
