"""Active KDJ entry extracted from grid strategy; no invented grid PnL."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/53.超跌网格交易大法V1.2：稳健跑赢大盘-年化13%回撤7%.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source151-20261013'
COMMON='proxy explicit reconstruction of jqlibKDJ9/3/3: RSV=100*(C-LL9)/(HH9-LL9), causalK/D EWMAalpha1/3 adjustFalse seededfirstfiniteRSV, J=3K-2D. JQinternalseed/flatdenominator byteequivalence unavailable; flatHH=LL missing, no null0. FullAadapter of fixedstock+ETFgridbasket; 14:50lastprice replacedcompletedpriorbar. No sourceholdings/cash/grid execution claim. '
SPECS=[
 spec('grid53_low_J9_3_3_proxy','九三三KDJ低J原子',A,'-(3*EWMAalpha1/3(RSV9)-2*EWMAalpha1/3(EWMAalpha1/3(RSV9))) endingt-1',COMMON+'NEWcontinuous lowJranking of sourceactiveJ<0entry, not itscashreturn.'),
 spec('grid53_J9_belowzero_entry_proxy','九三三KDJ负J入场代理',A,'I(J9_3_3<0) endingt-1',COMMON+'Literalstrictnegativeentry, fetch90priorclose max>0isvaliditycheck notdrawdown90threshold. Discrete ties audited. FinancialEBIT/EV/dividend/FScore functions dormant (callsitecommented), not combinedintoactiveformula.')]

def jseries(f):
 c=pd.DataFrame(f['close'].astype(float));hi=pd.DataFrame(f['high'].astype(float)).rolling(9).max();lo=pd.DataFrame(f['low'].astype(float)).rolling(9).min()
 rsv=(100*(c-lo)/(hi-lo)).replace([np.inf,-np.inf],np.nan);k=rsv.ewm(alpha=1/3,adjust=False,ignore_na=True).mean();d=k.ewm(alpha=1/3,adjust=False,ignore_na=True).mean()
 valid=rsv.notna()&k.notna()&d.notna();return (3*k-2*d).where(valid).to_numpy()

def values(f,pos):
 j=jseries(f)[pos-1];return [-j,np.where(np.isfinite(j),(j<0).astype(float),np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source9/3/3andstrictJ<0 fixed, explicitJQseedproxy')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:32] for k,v in f.items()};full=values(sf,pos);checks=[]
 for nn in [35,79]:
  cut=values({k:v[:pos[nn-1]+1] for k,v in sf.items()},pos[:nn])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:nn],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_priorbar',passed=True))
 for j in range(8):
  k=d=np.nan;ref=np.full(len(cal),np.nan)
  for t in range(8,len(cal)):
   hi=sf['high'][t-8:t+1,j].astype(float);lo=sf['low'][t-8:t+1,j].astype(float);cc=float(sf['close'][t,j])
   if not np.isfinite(hi).all() or not np.isfinite(lo).all() or not np.isfinite(cc) or hi.max()==lo.min():
    # k's EWM output holds its last finite state on absent RSV. The
    # second EWM still observes that held K; the final output stays missing.
    if np.isfinite(k):d=k if not np.isfinite(d) else (2*d+k)/3
    continue
   r=100*(cc-lo.min())/(hi.max()-lo.min());k=r if not np.isfinite(k) else (2*k+r)/3;d=k if not np.isfinite(d) else (2*d+k)/3;ref[t]=3*k-2*d
  np.testing.assert_allclose(-full[0][:,j],ref[pos-1],equal_nan=True,atol=1e-7)
 checks.append(dict(test='independent_scalar_RSV9_recursive_K_D_firstfinite_seed',passed=True))
 q.dump(OUT/'source_evidence.json',{A:read_text(q.ROOT/A)})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED151',flush=True)
if __name__=='__main__':main()
