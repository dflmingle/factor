"""Source body exit and two-day fear timing as explicitly new stock adapters."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略1/17.5年超额收益1055%，K线处理大阴线，无未来.txt'
B='quant/2024年度精选策略2/47.别人恐惧我贪婪——重视大盘择时.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source130-20261013'
SPECS=[
 spec('bigyin17_prior_body_low','昨日阴线实体相对前收低',A,'-(lag1O-lag1C)/lag2C',
 'proxy NEW continuous ranking of actual exit body=(Oprev-Cprev)/Cprevprev, not highshadow and not (O-C)/O. Priorcompleted qfqbar. Original sell threshold body>.068 active since secondday; holdings/weeklysmallcap growth/circMV/highlimits/orders omitted.'),
 spec('bigyin17_noexit_body068_state','原百分之六点八阴线退出非触发',A,'lag1 I((O-C)/lag1C<=.068)',
 'proxy NEW stockranking of only exit nontrigger, actual formula includes gap accounting canceled open-return minus close-return. Exactstrict> .068 exit; ties audited, not original costbasis or wholeportfolio.'),
 spec('fear47_twofall015_daily_margin','连续两日百分之一点五跌幅余量',B,'min(-.015-(lag1C/lag2C-1),-.015-(C/lag1C-1))',
 'proxy NEW stockcontinuous extension of source Shanghaicomposite marketglobaltrigger yesterday<=-.015,today14:55<=-.015; completed tclose replacesminute. Original CSI500 top50 LARGEST circMV,19daycounter heldpositions/pendingfills omitted. Marketconstant itself no stockalpha.')]

def values(f,pos):
 c=f['close'].astype(float);o=f['open'].astype(float)
 with np.errstate(divide='ignore',invalid='ignore'):
  body=(o[pos-1]-c[pos-1])/c[pos-2]
  retprev=c[pos-1]/c[pos-2]-1;ret=c[pos]/c[pos-1]-1
 state=np.where(np.isfinite(body),(body<=.068).astype(float),np.nan)
 return [-body,state,np.minimum(-.015-retprev,-.015-ret)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='sourceexact .068body and paired .015drawdown beforeoutcomes; allstockadapters explicitly NEW')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   a=float(sf['open'][t-1,j]);b=float(sf['close'][t-1,j]);p=float(sf['close'][t-2,j])
   if np.isfinite([a,b,p]).all() and p>0:
    ref=-((a-p)/p-(b-p)/p);np.testing.assert_allclose(full[0][i,j],ref,atol=1e-8)
 checks.append(dict(test='independent_source_openreturn_minus_closereturn_cancellation',passed=True))
 q.dump(OUT/'source_evidence.json',{s:read_text(q.ROOT/s) for s in [A,B]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='stockNEW exit/timing adaptations not original strategyreplication'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED130',flush=True)
if __name__=='__main__':main()
