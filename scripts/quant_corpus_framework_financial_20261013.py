"""Literal financial branch qualifications from fully reviewed frameworks."""
import json,tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/聚宽2025年精选/9干积分-量化策略简易框架.txt'
B='quant/聚宽2025年精选/12用子账户模拟多策略分仓.txt'
C='quant/聚宽2025年精选/39干积分-大小盘反复横跳V2.0.txt'
D='quant/聚宽2025年精选/5四大搅屎棍策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source116-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-framework-financial-schema-20261013'
FIELDS={'fina_indicator':['roe','roa','eps','netprofit_margin','grossprofit_margin','or_yoy','tr_yoy','op_yoy','netprofit_yoy','profit_dedt','roic'],
 'balancesheet':['total_hldr_eqy_exc_min_int','total_hldr_eqy_inc_min_int','total_liab','undistr_porfit'],
 'income':['n_income_attr_p','total_revenue'], 'cashflow':['n_cashflow_act','c_inf_fr_operate_a']}
SPECS=[
 spec('framework9_small_literal_quality','框架小盘源码质量交集',A,'-totalMV where reportedROE>.15 and ROA>.10',
 'proxy: literal reportedpercent thresholds .15/.10 POINTS, not narrative15%/10%; allA insteadCSI399101, totalMV original order; index375day/ST/price/limit/holdstate absent. Qualificationbenchmark and pure-size residual degeneracy do not measure membership value.'),
 spec('framework9_big_literal_quality','框架大盘源码质量交集',A,'totalMV where 0<PE_LYR<30,0<PS_TTM<8,PCF_TTM<10,EPS>.3,ROE>.1,NPM>.1,GPM>.3,revYoy>.25',
 'proxy: literal percentpoint gates .1/.3/.25, signed PCF permits negatives and no PCF>0 added; PE_LYR latestannouncedannualparentNI, PS totalrevenueTTM, PCF netoperatingcashTTM explicitvendor mappings; allA ratherHS300, no top3truncate for100stockminimum.'),
 spec('framework9_retained_roic_quality','框架留存利润投入回报交集',A,'undistr_profit where MV>300e8,0<PE_TTM<50,EPS>.12,ROA>.15,total_liab/equity<.5,trYoy>.3,orYoy>.2,retain>0,ROIC>.08',
 'proxy: actual source retainedprofit absolute descending, rawROICpercent .08points; equity source total_sheet_owner_equities mapsconsolidatedinclusiveequity; vendorPIT/ROICnotbyteequivalent. AllA replaceHS300, untruncatedqualification, not entiremonthlystylechooser.'),
 spec('framework9_bm_quality_size','框架中盘价值质量交集',A,'-totalMV where 100e8<MV<900e8,0<PB<10,PCF<4,EPS>.3,ROE>.2,NPM>.1,orYoy>.2,opYoy>.1',
 'proxy: source betweenbounds inclusive locally, signed PCF and literalrawpercentpoints retained. Source g.stock_num3 andHS300 absent, no originalETFfallback/10price9intervalstyle switch/stoploss claimed.'),
 spec('subportfolio12_pb098_opgrowth_roa','子账户低PB营业增长ROA交集',B,'reportedROA where PB<.98,operatingcashinflowYTD>1e6,deductedprofitYTD>1e6,ROA>.15,opYoy>0',
 'proxy: .98 cutoff and OPERATINGprofitYoY distinctfrom previouslytested PB1+NETprofitYoY. No PB>0 added. TusharePITfieldproxies. Originalmonthlytop3/hold1, stockpool/stopstate/subaccountallocationunreproduced.')]
for sp in SPECS:sp['gated']=True
SPECS[0]['source_paths']=[A,C,D]
SPECS[1]['source_paths']=[A,C]

def annual_profit(table,dates,stocks):
 out=np.full((len(dates),len(stocks)),np.nan)
 for symbol,g in table[table.end_date.dt.quarter.eq(4)].groupby('instrument',sort=False):
  j=stocks.get_indexer([symbol])[0]
  if j<0:continue
  g=g.sort_values(['ann_date','end_date','update_flag']);reports={};at=0;ann=g.ann_date.to_numpy();ends=g.end_date.to_numpy();vals=g.n_income_attr_p.to_numpy()
  for i,date in enumerate(dates):
   while at<len(g) and ann[at]<=date.to_datetime64():reports[ends[at]]=vals[at];at+=1
   if reports:out[i,j]=reports[max(reports)]
 return out

def values(fin,cap,annual):
 def g(ep,c):return fin[f'{ep}.{c}.q0'].astype(float)
 mv=cap.astype(float)*10000;eq=g('balancesheet','total_hldr_eqy_inc_min_int')
 pb=q.ratio(mv,g('balancesheet','total_hldr_eqy_exc_min_int'));pe=q.ratio(mv,g('income','n_income_attr_p_ttm'));pely=q.ratio(mv,annual)
 ps=q.ratio(mv,g('income','total_revenue_ttm'));pcf=q.ratio(mv,g('cashflow','n_cashflow_act_ttm'))
 roe=g('fina_indicator','roe');roa=g('fina_indicator','roa');eps=g('fina_indicator','eps');or_yoy=g('fina_indicator','or_yoy');op=g('fina_indicator','op_yoy');ret=g('balancesheet','undistr_porfit')
 small=(roe>.15)&(roa>.10)
 big=(pely>0)&(pely<=30)&(ps>0)&(ps<=8)&(pcf<10)&(eps>.3)&(roe>.1)&(g('fina_indicator','netprofit_margin')>.1)&(g('fina_indicator','grossprofit_margin')>.3)&(or_yoy>.25)
 retained=(mv>300e8)&(pe>0)&(pe<=50)&(eps>.12)&(roa>.15)&(q.ratio(g('balancesheet','total_liab'),eq)<.5)&(g('fina_indicator','tr_yoy')>.3)&(or_yoy>.2)&(ret>0)&(g('fina_indicator','roic')>.08)
 bm=(mv>=100e8)&(mv<=900e8)&(pb>0)&(pb<=10)&(pcf<4)&(eps>.3)&(roe>.2)&(g('fina_indicator','netprofit_margin')>.1)&(or_yoy>.2)&(op>.1)
 lowpb=(pb<.98)&np.isfinite(pb)&(g('cashflow','c_inf_fr_operate_a')>1e6)&(g('fina_indicator','profit_dedt')>1e6)&(roa>.15)&(op>0)
 return [np.where(small,-cap,np.nan),np.where(big,cap,np.nan),np.where(retained,ret,np.nan),np.where(bm,-cap,np.nan),np.where(lowpb,roa,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literalbranchgates, absolute retainedrank, no fittedthresholds; prior-dayPIT')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);dates=cal[pos-1]
 oldout,oldfields,loader=q.OUT,q.FIN_FIELDS,q.pit_tables
 try:
  q.OUT=SCHEMA;q.FIN_FIELDS=FIELDS;q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(dates),lags=1,rule=q.ALIGNMENT_RULE_VERSION));fin=q.financial_snapshot(dates,stocks,lags=1);tables=q.pit_tables();annual=annual_profit(tables['income'],dates,stocks)
  ids=np.arange(128);cap=f['cap'][pos][:,ids];whole=values({k:v[:,ids] for k,v in fin.items()},cap,annual[:,ids]);checks=[]
  for n in [35,79]:
   cutoff=dates[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])] for ep,t in tables.items()};q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='framework-PIT-',dir=OUT) as tmp:
    q.OUT=Path(tmp);cf=q.financial_snapshot(dates[:n],stocks[ids],lags=1);ap=annual_profit(sub['income'],dates[:n],stocks[ids]);cut=values(cf,cap[:n],ap)
    for sp,a,b in zip(SPECS,whole,cut):
     np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-6,rtol=1e-6);checks.append(dict(key=sp['key'],test='rawpriorPITfiling_and_annualrevision_cutoff_replay',nonempty=int(np.isfinite(b).sum()),passed=True))
  # Latest old-year revision must not erase the newer known annual report.
  toy=pd.DataFrame(dict(instrument=['X']*3,ann_date=pd.to_datetime(['20220301','20230301','20230501']),end_date=pd.to_datetime(['20211231','20221231','20211231']),update_flag=[0,0,1],n_income_attr_p=[10.,20.,15.]))
  np.testing.assert_allclose(annual_profit(toy,pd.DatetimeIndex(['20220601','20230601']),pd.Index(['X']))[:,0],[10.,20.]);checks.append(dict(test='annual_latestyear_not_latestannouncement_revision',passed=True))
  q.OUT=oldout;q.pit_tables=loader;vals=values(fin,f['cap'][pos],annual)
  q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C,D]})
  q.dump(OUT/'qualification_coverage.json',{sp['key']:np.isfinite(x).sum(axis=1).tolist() for sp,x in zip(SPECS,vals)})
  run(OUT,SPECS,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='sourcefinancialqualification proxies, prior-dayPIT, not complete framework or portfolio',benchmark_warning='factor_valid subset; pure-size residual noobservation does not test membershipvalue'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED116',flush=True)
 finally:q.OUT,q.FIN_FIELDS,q.pit_tables=oldout,oldfields,loader
if __name__=='__main__':main()
