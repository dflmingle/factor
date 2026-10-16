"""Source65 reset adjusted EWM and source88 rounded slope denominator audit."""
import json
import numpy as np
import pandas as pd
from quant_strategy_factor_catalog_20261012 import read_text
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
A='quant/2024年度精选策略1/65.低开买入小市值策略（剥头皮策略）3.0 总结.txt'
B='quant/2024年度精选策略1/88.韶华研究之十六，指数增强.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source123-20261013'
SPECS=[
 spec('open65_resetewm5_eligibility_margin','低开源码五点重置EMA资格余量',A,'min(prevLOW/OPEN-1,OPEN/prevC-1+.08,-.01-(OPEN/prevC-1),.20-(MAX4H/MIN4L-1),prevC/resetAdjustedEWM5-1)',
 'proxy NEW continuous minimum margin of literal active open/priorlow/-8..-1/range4<=20/reset5adjustedEWM. FullA/10day label rather original first5of500 smallcap and nextday0930 sale; actual paused/ST/688 filters and intraday fills unavailable.'),
 spec('open65_resetewm5_lowcap_partial','低开重置五点均线约束小市值',A,'-total_mv WHERE OPEN<prevLOW AND -.08<OPEN/prevC-1<-.01 AND MAX4H/MIN4L-1<=.20 AND prevC>resetAdjustedEWM5',
 'proxy source ranking by size on daily qualification, no fixed500truncation. Original daily nextday0930 sale, paused/ST/688 and fills unimplemented; conditional subset benchmark is not unconstrained fullA excess.'),
 spec('open65_resetewm5_gap_partial','低开重置五点均线约束跌幅腿',A,'-(OPEN/prevC-1) WHERE exact source daily price qualification',
 'proxy NEW gap ranking of eligible stocks; source ranks size, not gap. Reset EWM adjust=True on exactly5 prior closes; no invented paused proxy. Original one-day execution not claimed.'),
 spec('trend88_rounded_slope_denominator21','二十价点斜率含系数分母',B,'round(OLSslope20priorC,3)/((SUM20priorC+roundedSlope)/21)',
 'proxy literal bug retained: coef inserted before rowmean, denominator21 not20. FullA instead missing PIT000905 membership, no ST/paused/IPO365, buffer30percent or fills.'),
 spec('trend88_positive_range15_partial','正斜率与一倍半价格区间约束',B,'roundedSlope/meanIncludingCoef WHERE 0<score<999 AND MAX20C/MIN20C<=1.5',
 'proxy active R numeric1.5 price range, not index-relative return; D dynamic index branch dormant. FullA qualified subset rather source000905, no portfolio buffer/fills.'),
 spec('trend88_range15_drawdown75_partial','价格区间与持仓回撤阈值适配',B,'source88 positive and range1.5 qualified score WHERE prevC/MAX20priorH>=.75',
 'proxy NEW membership application of original held-position losscontrol2 guard, not source entry filter. No PIT index/position state/fills; no claim entire strategy reproduced.')]
for s in SPECS:
 if s['key'].endswith('partial'):s['gated']=True

def values(f,pos):
 c=f['close'].astype(float);o=f['open'].astype(float);h=f['high'].astype(float);l=f['low'].astype(float)
 shape=(len(pos),c.shape[1]);out=[np.full(shape,np.nan) for _ in SPECS]
 w=(2/3)**np.arange(4,-1,-1);w/=w.sum();xx=np.arange(20)-9.5;den=xx@xx
 for i,t in enumerate(pos):
  hist=c[t-5:t];ema=np.sum(hist*w[:,None],axis=0);prev=c[t-1];gap=o[t]/prev-1
  range4=np.max(h[t-4:t],axis=0)/np.min(l[t-4:t],axis=0)-1
  terms=np.stack([l[t-1]/o[t]-1,gap+.08,-.01-gap,.20-range4,prev/ema-1]);margin=np.min(terms,axis=0)
  eligible=(o[t]<l[t-1])&(gap>-.08)&(gap<-.01)&(range4<=.20)&(prev>ema)&np.isfinite(margin)
  out[0][i]=margin;out[1][i]=np.where(eligible,-f['cap'][t],np.nan);out[2][i]=np.where(eligible,-gap,np.nan)
  a=c[t-20:t];slope=np.sum(a*xx[:,None],axis=0)/den
  rounded=np.array([round(float(z),3) if np.isfinite(z) else np.nan for z in slope])
  score=rounded/((np.sum(a,axis=0)+rounded)/21)
  ok=(score>0)&(score<999)&(np.max(a,axis=0)/np.min(a,axis=0)<=1.5)
  out[3][i]=score;out[4][i]=np.where(ok,score,np.nan)
  out[5][i]=np.where(ok&(prev/np.max(h[t-20:t],axis=0)>=.75),score,np.nan)
 return out

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal5adjustTrue_reset/4range/open-8..-1/20slope3decimals_den21/1.5/.75fixed before results')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for s,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=s['key'],test='rawprice_prefix_replay',passed=True))
 observations=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   x=sf['close'][t-20:t,j].astype(float)
   if not np.isfinite(x).all():continue
   ema=pd.Series(x[-5:]).ewm(span=5).mean().iloc[-1]
   gap=sf['open'][t,j]/x[-1]-1;rg=sf['high'][t-4:t,j].max()/sf['low'][t-4:t,j].min()-1
   ref=min(sf['low'][t-1,j]/sf['open'][t,j]-1,gap+.08,-.01-gap,.20-rg,x[-1]/ema-1)
   np.testing.assert_allclose(full[0][i,j],ref,atol=1e-7)
   slope=round(float(np.polyfit(np.arange(20),x,1)[0]),3)
   np.testing.assert_allclose(full[3][i,j],slope/np.append(x,slope).mean(),atol=1e-10);observations+=1
 checks.append(dict(test='independent_pandas_resetadjustedEWM5_and_polyfit_denominator21',observations=observations,passed=True))
 q.dump(OUT/'source_evidence.json',{s:read_text(q.ROOT/s) for s in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='literal source helpers and disclosed NEW extensions, original strategy state unimplemented'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED123',flush=True)
if __name__=='__main__':main()
