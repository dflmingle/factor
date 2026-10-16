"""Independent untested partial event volume atoms, no fabricated event data."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_sweep_20261013 import tie_diagnostic
A='quant/聚宽2025年精选/96首版+2版龙虎榜挖掘V2.0，年化1400.txt'
B='quant/聚宽2025年精选/57韶华研究之十八，201系列.txt'
C='quant/量化策略/量化策略/首板回调买入策略2026/实10-首板竞价三模式-25年206.7.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source159-20261013'
COMMON='proxy NEW completedqfq daily partial stockextension, prior completedbar t-1 preserved; no actual limit/auction/minute/PITconcept/Longhu or originalholdingreturn fabricated. '
SPECS=[
 spec('longhu96_volume3_prior15_band_margin','龙虎榜三对十五均量倍数带',A,'min(R/4-1,1-R/6),R=mean(last3V)/mean(prior15V),18bars ending t-1',COMMON+'Actual days18: earlier15 v[:-3], recent3; strict4<R<6, not prose20mean/2times nor monotonic3increase. Missing Longhu net_value>0 buy_rate>4,conceptshared>=2,actual1or2limits18,open>=1.04priorhigh_limit,turn<50 LARGEcircMVsort andoneholding. Continuous centeredband ordering newly disclosed.'),
 spec('series57_RET4_volume20_partial','二零一四间隔低涨幅量约束',B,'-RET4(t-1) WHERE RET4<.1 AND V(t-1)<=5*mean20V(t-1)',COMMON+'Source close[-1]/close[-5] is4intervals, volume_control2 upper ceiling5times includescurrentV, not5timesminimum. Missing firstboard20==1/nononeprice/last60minuteweak-seal/auction.945..985 andhalfaccount; active14:55nonlimitsell,120dayvolume sell inactive. Qualified factor_valid benchmark separately labelled.'),
 spec('auction10_weak3ret_body_amount_margin','弱转强三间隔实体成交额余量',C,'min((.28-RET3)/.28,(C/O-.95)/.05,(amount-3e8)/3e8,(19e8-amount)/19e8,totalMV/70e8-1) ending t-1',COMMON+'Four closepoints means3intervals, not4. Actual<=.28, body>=-.05, amount3..19亿,totalMV>=70; omitted vendorcircMV<=520, VWAP>=.96,auctionvolume3%,openingrelativeactualhigh_limit,.9leftpressure,brokenboardandMAstop. NEW minimumcontinuous dailyqualification margin only, not original union of3modes.')]
SPECS[1]['gated']=True

def values(f,pos):
 c=pd.DataFrame(f['close'].astype(float));v=pd.DataFrame(f['volume'].astype(float));prior=pos-1
 r=(v.rolling(3).mean()/v.rolling(15).mean().shift(3)).to_numpy()[prior]
 a=np.minimum(r/4-1,1-r/6);ret4=(c/c.shift(4)-1).to_numpy()[prior];vm=v.rolling(20).mean().to_numpy()[prior]
 b=np.where((ret4<.1)&(f['volume'][prior]<=5*vm)&np.isfinite(vm),-ret4,np.nan)
 ret3=(c/c.shift(3)-1).to_numpy()[prior];body=f['close'][prior]/f['open'][prior]
 money=f['amount'][prior].astype(float);mv=f['cap'][prior].astype(float)*10000
 d=np.minimum.reduce([(.28-ret3)/.28,(body-.95)/.05,(money-3e8)/3e8,(19e8-money)/19e8,mv/70e8-1])
 return [a,b,d]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source18/15/3 strict4..6 andRET4/.1/V20ceiling5,weakRET3/.28/body.95/amount3..19/size70 frozen beforeoutcomes')
 fp=OUT/'frozen_plan.json'
 if fp.exists() and json.loads(fp.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(fp,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);sf={k:v[:,:64] for k,v in f.items()};full=values(sf,pos);checks=[]
 for n in [35,79]:
  cut=values({k:v[:pos[n-1]+1] for k,v in sf.items()},pos[:n])
  for sp,a,b in zip(SPECS,full,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='raw_daily_prefix_replay',passed=True))
 count=0
 for i in [35,79]:
  t=pos[i]
  for j in range(64):
   v=sf['volume'][t-20:t,j].astype(float);c=sf['close'][t-5:t,j].astype(float)
   if not np.isfinite(v).all() or not np.isfinite(c).all() or v[:-3].mean()<=0:continue
   r=v[-3:].mean()/v[-18:-3].mean();np.testing.assert_allclose(full[0][i,j],min(r/4-1,1-r/6),atol=1e-8)
   ret=c[-1]/c[-5]-1;ref=-ret if ret<.1 and v[-1]<=5*v.mean() else np.nan
   np.testing.assert_allclose(full[1][i,j],ref,equal_nan=True,atol=1e-8);count+=1
 assert count>0;checks.append(dict(test='independent18bar_3vs15_andliteralRET4_volumeceiling',observations=count,passed=True))
 # Unit conversion is already normalized at cache ingestion, no amount multiplier.
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity=COMMON),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f)
 q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED159',flush=True)
if __name__=='__main__':main()
