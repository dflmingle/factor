"""Source80 exact short-reset RSI14 and literal financial qualification."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/聚宽2025年精选/80基本面01加RSI择时.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source98-20261013'
SPECS=[
 spec('fund80_reset15_rsi14_low','十五价点重置RSI十四低值',SRC,'-100*mean14(positiveRETprice)/mean14(absRETprice), last15completedclose',
 'proxy: exact reset15-price TA-LibRSI14 seed equals simple14change gains/(gains+losses), no longhistoryWilder continuation; stockwide negative ranking NEW adaptation of source<50 buy gate, >70 sell omitted. Priorclose consumed at currentclose signal with delay1, source sameopen fills omitted'),
 spec('fund80_financial_qualified_small','基本面八十真实阈值小市值',SRC,'-totalMV on 0<PB<10,PCF<5,ROE>.3,grossmargin>.3,profitYoY>1.5',
 'proxy: literal percentunits thresholds .3, .3 and1.5 retained, NOT30%,30%,150%; negativePCF allowed. PCF=totalMV/OCF_TTM proxy, repeated platform CFP failure means NOT platform-equivalent. Tushare reportedROE/grossmargin/NIyoy PIT; restricted benchmark; source top50/top10,monthly,375day,ST/board/limit omissions'),
 spec('fund80_financial_rsi_qualified_small','基本面八十加重置RSI交集',SRC,'-totalMV on financialgate AND lag1(reset15 RSI14)<50',
 'proxy: source financial+RSI conjunction retained on full qualifiedset; original first50smallest BEFORE RSI then first10 not asserted. Original <=50source universe cannot satisfy >=100canonical evaluation; fullset adaptation separately disclosed; restricted benchmark, CFP vendorproxy and execution omissions')]
for s in SPECS[1:]:s['gated']=True

def rsi(f):
 c=f['close'].astype(float);diff=c-q.delay(c);gain=q.rolling(np.maximum(diff,0),14);loss=q.rolling(np.maximum(-diff,0),14)
 return q.delay(np.where(gain+loss==0,0,100*gain/(gain+loss)))

def values(fin,cap,rs):
 def g(ep,col):return fin[f'{ep}.{col}.q0'].astype(float)
 mv=cap*10000;pb=q.ratio(mv,g('balancesheet','total_hldr_eqy_exc_min_int'));pcf=q.ratio(mv,g('cashflow','n_cashflow_act_ttm'))
 good=(pb>0)&(pb<10)&(pcf<5)&(g('fina_indicator','roe')>.3)&(g('fina_indicator','grossprofit_margin')>.3)&(g('fina_indicator','netprofit_yoy')>1.5)
 return [-rs,np.where(good,-cap,np.nan),np.where(good&(rs<50),-cap,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='three sourceperiod/gate hypotheses fixed, no tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);rs=rsi(f)[pos];fin=q.financial_snapshot(grid,stocks);checks=[]
 ids=np.arange(64);small={k:v[:,ids] for k,v in f.items()};whole=rsi(small)
 for stop in [1200,len(cal)-31]:
  cut=rsi({k:v[:stop] for k,v in small.items()});np.testing.assert_allclose(whole[:stop],cut,equal_nan=True,atol=1e-6);checks.append(dict(test='daily_reset15_RSI_prefix',stop=stop,passed=True))
 for t in [1200,len(cal)-32]:
  for j in ids:
   x=f['close'][t-15:t,j].astype(float)
   if np.isfinite(x).all():
    d=np.diff(x);a=np.maximum(d,0).mean();b=np.maximum(-d,0).mean();literal=100*a/(a+b) if a+b else 0
    np.testing.assert_allclose(whole[t,j],literal,atol=1e-5,rtol=1e-6)
 checks.append(dict(test='independent_last15prices_reset14_gainloss_seed',passed=True))
 tables=q.pit_tables();oldout,loader=q.OUT,q.pit_tables
 try:
  cap=f['cap'][pos][:,ids];base=values({k:v[:,ids] for k,v in fin.items()},cap,rs[:,ids])
  for n in [35,79]:
   cutoff=grid[n-1];q.pit_tables=lambda:{ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
   with tempfile.TemporaryDirectory(prefix='fund80-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);fresh=q.financial_snapshot(grid[:n],stocks[ids]);cut=values(fresh,cap[:n],rs[:n,ids])
    for sp,a,b in zip(SPECS,base,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True);checks.append(dict(key=sp['key'],test='actual_ann_PIT_revision_TTM_cutoff',cutoff=str(cutoff),passed=True))
 finally:q.OUT,q.pit_tables=oldout,loader
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 vals=values(fin,f['cap'][pos],rs);q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='literal financialgates resetRSI, allqualifiedset adaptation; PCFproxy'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED98',flush=True)
if __name__=='__main__':main()
