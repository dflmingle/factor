"""Current banking valuation and literal value/low-vol qualification atoms."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
BANK='quant/2021年度精选策略/38.python搭建简单交易系统.txt'
LOW='quant/2021年度精选策略/5.价值低波（下）--十年十倍（2020拜年）.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source57-20261013'
SPECS=[
 spec('bank_current_doubletime','银行当前估值翻倍期',BANK,'-round(log(2*PB)/log(1+ROE/100),2); ROE>0 and PB>0',
 'proxy: literal latest PIT signal-date finance, not previously studied mean250(PB/ROE); source fixed14bank pool/top3/intersection fallback omitted; rounding retains ties; TushareYTDROE/total_mv/equity valuation'),
 spec('graham_operatingprofit_value','格氏经营利润成长价值比',BANK,'operate_profit_YTD/totalMV*(27+2*reported_op_yoy/100); ROE>0',
 'proxy: source operating_profit/capitalization/close cancels to operating-profit yield up to universal capitalization unit and signal-date vendor qfq normalization; Tushare latestYTD profit/op_yoy; source current-price shares identity uses totalMV, not raw-close return label; bank and smallest10/top3/intersection omitted'),
 spec('value_lowvol240_source','价值约束两百四十收益低波',LOW,'-STD240(ret1) within 0<PE<20,PB>0,PB/PE>.1',
 'proxy: literal source241closes gives240 returns; source firstlowPEtop10 then inversevol portfolio weights adapted to broad valuation-qualified stock factor; HS300/treasury/index/portfolioDD state omitted; not distinct raw lowvol cluster'),
]
for sp in SPECS:sp['gated']=True

def build(fin,cap,c,pos):
 def g(ep,k):return fin[f'{ep}.{k}.q0'].astype(float)
 mv=cap*10000;pb=q.ratio(mv,g('balancesheet','total_hldr_eqy_exc_min_int'));pe=q.ratio(mv,g('income','n_income_attr_p_ttm'));roe=g('fina_indicator','roe')
 with np.errstate(divide='ignore',invalid='ignore'):
  time=np.log(2*pb)/np.log1p(roe/100)
 a=np.where((roe>0)&(pb>0),-np.round(time,2),np.nan)
 b=np.where(roe>0,q.ratio(g('income','operate_profit'),mv)*(27+2*g('fina_indicator','op_yoy')/100),np.nan)
 r=q.ratio(c,q.delay(c))-1;vol=q.rolling(r,240,'std')[pos]
 d=np.where((pe>0)&(pe<20)&(pb>0)&(q.ratio(pb,pe)>.1),-vol,np.nan)
 return [a,b,d]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,selection='source fixed before outcomes',platform_compute=0)
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks);vals=build(fin,f['cap'][pos],f['close'],pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=build({k:v[:n] for k,v in fin.items()},f['cap'][pos[:n]],f['close'][:stop],pos[:n])
  for sp,a,b in zip(SPECS,vals,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,rtol=1e-6,atol=1e-6);checks.append(dict(key=sp['key'],test='price_prefix_and_formula_previously_raw_PIT_verified_financial_cache',passed=True))
 # Rounding/domain and source241observations/240returns independently checked.
 assert np.round(np.log(2*1.5)/np.log1p(.12),2)==9.69
 for j in range(32):
  xx=f['close'][pos[-1]-240:pos[-1]+1,j].astype(float)
  if np.isfinite(xx).all():
   ref=np.std(xx[1:]/xx[:-1]-1,ddof=1)
   actual=q.rolling(q.ratio(f['close'][:,:32],q.delay(f['close'][:,:32]))-1,240,'std')[pos[-1],j]
   np.testing.assert_allclose(actual,ref,rtol=1e-4,atol=1e-7)
 checks.append(dict(test='literal_source241close_vol_and_doubletime_rounding',passed=True))
 run(OUT,SPECS,vals,cal,stocks,f,checks,dict(fidelity='explicit PIT financial source proxies; original bank/HS300 allocation not reproduced',benchmark_warning='financial qualification subset factor_valid',statistics='exploratory no independent OOS',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED57',flush=True)
if __name__=='__main__':main()
