"""Bias normalization, dual trend horizon, LR and RSRS damping source variants."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
BIAS='quant/2024年度精选策略1/10.多因子宽基ETF择时轮动改进版-高收益大资金低回撤.txt'
DUAL='quant/2024年度精选策略1/38.ETF核心资产轮动-添油加醋.txt'
DAMP='quant/2021年度精选策略/60.【分享】对RSRS模型的一次修改.txt'
BASE='quant/2021年度精选策略/59.【复现】RSRS择时改进.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source83-20261013'
SPECS=[
 spec('bias90_normalized_slope20_source','九十日乖离归一后二十日斜率',BIAS,'OLS20slope((C/MA90C)/(first_of_20_bias))*10000',
 'proxy: exact source90rolling mean plus latest20bias normalized by FIRST bias, not price or mean normalization; ETF->fullA, holdingSwitchFactor1.04 and timing omitted'),
 spec('logtrend25_minus_trend200_over6_source','短趋势减六分之一长趋势',DUAL,'trend25(logC)-trend200(logC)/6; trendN=expm1(250*slopeN)*R2_N',
 'proxy: actual source g.m_days25, long8*25, divisor6 fixed; ETF->fullA, trading and timing omitted'),
 spec('lr24_movingaverage_breadth_source','个股二十四条均线上方占比',DAMP,'mean(I(C>MA_nC)) for n=10,20,...240; all24means required',
 'proxy: actual standalone cala_LR source stock extension of index trend diagnostic, highdirection exploratory not disclosed portfolio alpha; count ties audited'),
 spec('rsrs16_600_original_damping_proxy','十六六百RSRS波动率钝化',DAMP,'Z600(beta16)*R2_16**(2*percentile600(populationSTD16ret))',
 'proxy: source16/600 and exponent retained; missing Creat_RSRS base reconstructed from displayed OLS and pandas sampleSTD600 conventions in source59. Not claiming its imported base byteequivalence. FullA stocks replace index; highdirection'),
 spec('rsrs16_600_reverse_damping_proxy','十六六百RSRS反向波动率钝化',DAMP,'Z600(beta16)*R2_16**(2*(1-percentile600(populationSTD16ret)))',
 'proxy: exact source improved exponent, explicit same imported-base reconstruction as original; stock adaptation; noindexpositionbacktest'),
 spec('rsrs16_600_lr_damping_proxy','十六六百RSRS均线广度钝化',DAMP,'Z600(beta16)*R2_16**(2*percentile600(1-LR24))',
 'proxy: actual improve2 inherits BASE RSRS not improve1; therefore exponent2*q of(1-LR), not2*(1-q). Creat_RSRS unavailable; reconstructed same displayed source59 OLS/sample600std base; fullA stocks replaceindex')]
for sp in SPECS[3:]:sp['source_paths'].append(BASE)

def rsrs(f):
 # Only the source59 base OLS explicitly converts missing high/low to zero.
 # This is disclosed in reconstruction, not a generic market-cache fill.
 l=np.nan_to_num(f['low'].astype(float),nan=0);h=np.nan_to_num(f['high'].astype(float),nan=0)
 ld=pd.DataFrame(l);hd=pd.DataFrame(h);ml=ld.rolling(16).mean();mh=hd.rolling(16).mean()
 cov=ld.rolling(16).cov(hd,ddof=0);vl=ld.rolling(16).var(ddof=0);vh=hd.rolling(16).var(ddof=0)
 beta=(cov/vl).replace([np.inf,-np.inf],np.nan);r2=(cov**2/(vl*vh)).replace([np.inf,-np.inf],np.nan).clip(0,1)
 z=(beta-beta.rolling(600).mean())/beta.rolling(600).std(ddof=1)
 return z.to_numpy(),r2.to_numpy()

def trend_at(c,pos,n):
 out=np.full((len(pos),c.shape[1]),np.nan);x=np.arange(n);xc=x-x.mean();den=np.sum(xc**2)
 for i,t in enumerate(pos):
  hist=c[t-n+1:t+1];ok=np.isfinite(hist).all(axis=0)&(hist>0).all(axis=0)
  y=np.log(hist[:,ok]);yc=y-y.mean(axis=0);s=(xc[:,None]*yc).sum(axis=0)/den
  total=(yc**2).sum(axis=0);r2=1-((yc-xc[:,None]*s)**2).sum(axis=0)/np.where(total>0,total,np.nan)
  out[i,ok]=np.expm1(250*s)*r2
 return out

def values(f,pos):
 c=f['close'].astype(float);df=pd.DataFrame(c);ma90=df.rolling(90).mean().to_numpy();bias=c/ma90
 b=np.full((len(pos),c.shape[1]),np.nan);x=np.arange(20);xc=x-x.mean()
 for i,t in enumerate(pos):
  y=bias[t-19:t+1]/bias[t-19]
  b[i]=(xc[:,None]*y).sum(axis=0)/np.sum(xc**2)*10000
 dual=trend_at(c,pos,25)-trend_at(c,pos,200)/6
 count=np.zeros(c.shape,dtype=float);valid=np.ones(c.shape,dtype=bool)
 for n in range(10,250,10):
  ma=df.rolling(n).mean().to_numpy();valid&=np.isfinite(ma);count+=(c>ma)
 lr=np.where(valid,count/24,np.nan)
 z,r2=rsrs(f)
 ret=df.pct_change(fill_method=None)
 vol=ret.rolling(16,min_periods=1).std(ddof=0)
 vq=vol.rolling(600).rank(method='average',pct=True).to_numpy()
 lq=pd.DataFrame(1-lr).rolling(600).rank(method='average',pct=True).to_numpy()
 return [b,dual,lr[pos],(z*r2**(2*vq))[pos],(z*r2**(2*(1-vq)))[pos],(z*r2**(2*lq))[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal source variant parameters; no postoutcome choice of damping/horizon')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:32] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-7,atol=1e-7);checks.append(dict(key=sp['key'],test='raw_daily_prefix_rebuild_600rank_no_future',cutoff=str(cal[stop-1]),passed=True))
 z,r2=rsrs(small);obs=0
 for i in [12,60,119]:
  t=pos[i]
  for j in range(32):
   cc=small['close'][t-109:t+1,j].astype(float);ser=pd.Series(cc)
   bb=(ser/ser.rolling(90).mean()).iloc[-20:]
   if np.isfinite(bb).all():
    ref=np.polyfit(np.arange(20),bb/bb.iloc[0],1)[0]*10000
    np.testing.assert_allclose(whole[0][i,j],ref,atol=1e-6,rtol=1e-6)
   ll=np.nan_to_num(small['low'][t-15:t+1,j].astype(float),nan=0);hh=np.nan_to_num(small['high'][t-15:t+1,j].astype(float),nan=0)
   if ll.std()>0 and hh.std()>0:
    ref=np.corrcoef(ll,hh)[1,0]**2;np.testing.assert_allclose(r2[t,j],ref,atol=1e-6,rtol=1e-6)
   sig=pd.Series(1-whole[2][:,j]);obs+=1
 checks.append(dict(test='independent_source_polyfit_bias_first_and_correlation_R2',observations=obs,passed=True))
 toy=pd.Series([1.,2.,2.,3.]);assert toy.rank(pct=True).iloc[-2]==.625
 checks.append(dict(test='rolling_percentile_uses_average_ties_inclusive_current',passed=True))
 q.dump(OUT/'source_evidence.json',{p:read_text(q.ROOT/p) for p in [BIAS,DUAL,DAMP,BASE]})
 vals=values(f,pos)
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source displayed kernels and disclosed imported-base reconstruction',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED83',flush=True)

if __name__=='__main__':main()
