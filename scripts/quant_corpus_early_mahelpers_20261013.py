"""Early corpus MA helper variants: precise active priority and completed bars."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
def src(prefix):return str(next((q.ROOT/'quant/2020年度精选策略').glob(prefix+'*')).relative_to(q.ROOT))
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source122-20261013'
SPECS=[
 spec('early11_ma3_5_7_priority_add','早期源码三五七均线加仓优先级',src('11 '),'lag1(1 if C<MA3 else1.4 if C<MA5 else1.8 if C<MA7 else0)',
 'proxy NEW ranking of actual50/70/90k conditionalorderbudget, not claimed originalalpha. NamedMA10/15/20 actual3/5/7; fixedorders and6smallsize/retusingpositioncurrentprice notavgcost unimplemented; aftertclose notoriginal intraday.'),
 spec('early14_ma20_15_10_priority_add','早期源码二十十五十加仓优先级',src('14 '),'lag1(.5 if C<MA20 else.3 if C<MA15 else.2 if C<MA10 else0)',
 'proxy NEW ranking of actualcashmultipliers with branchpriority retained;20smallsize universe/cashretcoststate unimplemented. Originalret>5before10/15 makeslatterunreachable, not extraalpha.'),
 spec('early89_multima_nonstruggle_margin','早期五十廿卅多均线脱缠余量',src('89 '),'lag1(min(MA5/MA10-1,MA10/MA20-1-.003,MA20/MA30-1-.002))',
 'proxy NEW continuous extension of exact active bullishAND NOT struggle: struggle isOR abs10/20<.003 orabs20/30<.002; 60/180declaredunused. Stockextension offixed600196, no frozen20kpositionbacktest.'),
 spec('early89_bear2_then_cross10_20','早期两次空头后十廿金叉事件',src('89 '),'lag1(I(MA5<MA10<MA20 at prior2 evaluations AND priorMA10<MA20 AND currentMA10>MA20))',
 'proxy sourceactual10cross20 aftertwo previousbear5/10/20, strict boundaries, completedbarsevaluation underdaily assumption. In minutefrequency arraysappend eachbar repeatedpreviousdailyaverages, not same asdaily; exact currenthistoryday proxy, no original cash/stock path.'),
 spec('early52_boll20_upper_priorclose','早期布林二十日上轨前日余量',src('52 '),'lag1((C-MEAN20C)/popSTD20C-2)',
 'proxy exact source completed20closes populationstd, unlike currentbar source45. OriginalDataFrame np.mean/std mayreturnsSeries andupper[-1] versiondependent; unambiguous onecolumn scalar intended helper, no singleMoutai fills.'),
 spec('early86_ma5_10_price_buy_margin','早期五十均线与价格交集余量',src('86 '),'min(MA5/MA10-1,C/MA5-1)',
 'proxy NEW continuous stockextension of activeif MA5>MA10 andprice>MA5; MA20computedunused. data.mavg/currentbar semantics adapted completedtclose explicitly, no singleAirChina cash or tradeclaim.')]

def values(f,pos):
 c=pd.DataFrame(f['close'].astype(float));ma={n:c.rolling(n).mean() for n in [3,5,7,10,15,20,30]}
 valid7=np.isfinite(ma[7]);a=np.where(valid7,np.where(c<ma[3],1,np.where(c<ma[5],1.4,np.where(c<ma[7],1.8,0))),np.nan)
 valid20=np.isfinite(ma[20]);b=np.where(valid20,np.where(c<ma[20],.5,np.where(c<ma[15],.3,np.where(c<ma[10],.2,0))),np.nan)
 margin=np.minimum.reduce([(ma[5]/ma[10]-1).to_numpy(),(ma[10]/ma[20]-1-.003).to_numpy(),(ma[20]/ma[30]-1-.002).to_numpy()])
 bear=(ma[5]<ma[10])&(ma[10]<ma[20]);cross=(bear.shift(1,fill_value=False)&bear.shift(2,fill_value=False)&(ma[10].shift(1)<ma[20].shift(1))&(ma[10]>ma[20]))
 event=np.where(np.isfinite(ma[20].shift(2)),cross.astype(float),np.nan)
 boll=(c-ma[20])/c.rolling(20).std(ddof=0).where(lambda x:x>0)-2
 price=np.minimum((ma[5]/ma[10]-1).to_numpy(),(c/ma[5]-1).to_numpy())
 return [pd.DataFrame(x).shift(1).to_numpy()[pos] for x in [a,b,margin,event,boll]]+[price[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='reviewedactualMA3/5/7/10/15/20/30priority,.003/.002,20popSTDanddailycross fixed')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawdaily_prefix_replay',passed=True))
 obs=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   x=sf['close'][:t,j].astype(float)
   if not np.isfinite(x[-32:]).all():continue
   m={n:x[-n:].mean() for n in [3,5,7,10,15,20,30]};p0=x[-1]
   a=1 if m[3]>p0 else(1.4 if m[5]>p0 else(1.8 if m[7]>p0 else 0))
   b=.5 if p0<m[20] else(.3 if p0<m[15] else(.2 if p0<m[10] else 0))
   np.testing.assert_allclose(full[0][i,j],a);np.testing.assert_allclose(full[1][i,j],b)
   orig=(m[5]>m[10]>m[20]>m[30]) and not(abs(m[10]/m[20]-1)<.003 or abs(m[20]/m[30]-1)<.002)
   if not any(np.isclose(z,0,atol=1e-10) for z in [m[10]/m[20]-1-.003,m[20]/m[30]-1-.002]):assert (full[2][i,j]>0)==orig
   np.testing.assert_allclose(full[4][i,j],(x[-1]-x[-20:].mean())/x[-20:].std()-2,atol=1e-8);obs+=1
 checks.append(dict(test='independent_literal_orderpriority_struggleOR_and_Boll20',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{sp['source_paths'][0]:read_text(q.ROOT/sp['source_paths'][0]) for sp in SPECS})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='disclosed dailyhelper/newranking proxy, original smallstock/intradaystate not reproduced'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED122',flush=True)
if __name__=='__main__':main()
