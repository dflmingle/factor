"""Source65 five-log ranking atoms, explicit omission of unavailable style gate."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/65搭建量化交易模型从零开始——择时，选股，仓位管理和因子分析.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source156-20261013'
COMMON=('proxy NEW partial ranking adapter: currentminuteprice->completedqfqC, '
 'prior21dailyV and firstof55priorclose retained, turnover_ratio->daily_basicturnover; '
 'circMV explicitly replacedtotalMV. Omit sourcePB>1,PE0..200,revenueYoY>30,profitYoY>50,'
 'vendorOCF/operatingprofit>10 qualification. Equalpositive logweights actual [1,1,1,1,1]; '
 'minima addconstants and cancel cross-sectional ranking. Source flips sizeweight on '
 'every13th my_select CALL when144bar LOWindextrend233 bestindex is index_pool[1]; '
 'threeWednesdaybuy plus threedailysell calls, not quarterly calendar. Missing original '
 'index/state means fixedplus/minus regimes only, no invented regime selection. '
 '50dayOHLCmeanZ sizing,100holdings/partialorders/stops not reproduced. ')
SPECS=[
 spec('lowlog65_turn_price_V21_return55_sizefree','五对数换手价格量反转去市值',SRC,'-log(Turn)-log(C)-log(lag1SUM21V)-log(C/lag55C)',COMMON+' NEWremove sizeleg; not source32/145 windowweights.'),
 spec('lowlog65_small_totalMV_fixedregime','五对数固定小盘腿',SRC,'sizefree-log(totalMV)',COMMON+' Fixedpositive sizeweight branch only.'),
 spec('lowlog65_large_totalMV_fixedregime','五对数固定大盘腿',SRC,'sizefree+log(totalMV)',COMMON+' Fixednegative sizeweight branch only.')]

def values(f,pos):
 c=f['close'].astype(float);v=pd.DataFrame(f['volume'].astype(float)).rolling(21).sum().shift(1).to_numpy()
 turn=f['turnover'].astype(float);cap=f['cap'].astype(float)
 with np.errstate(divide='ignore',invalid='ignore'):
  core=-np.log(np.where(turn>0,turn,np.nan))-np.log(c)-np.log(np.where(v>0,v,np.nan))-np.log(c/q.delay(c,55))
  size=np.log(np.where(cap>0,cap,np.nan))
 return [core[pos],(core-size)[pos],(core+size)[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,
  selection='source-fixed21volume/55grossreturn/unitlogweights,three disclosed staticbranches beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   a=np.array([sf['turnover'][t,j],sf['cap'][t,j],sf['close'][t,j],sf['volume'][t-21:t,j].sum(),sf['close'][t,j]/sf['close'][t-55,j]],float)
   if not np.isfinite(a).all() or (a<=0).any():continue
   np.testing.assert_allclose(full[0][i,j],-np.log(a[[0,2,3,4]]).sum(),atol=1e-6)
   np.testing.assert_allclose(full[1][i,j],-np.log(a).sum(),atol=1e-6)
   np.testing.assert_allclose(full[2][i,j],-np.log(a).sum()+2*np.log(a[1]),atol=1e-6)
 checks.append(dict(test='independent_literal21priorV_55priorfirst_and_three_logbranches',passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED156',flush=True)
if __name__=='__main__':main()
