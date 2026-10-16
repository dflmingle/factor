"""Fixed PIT accounting hypotheses extracted from three reviewed strategies; offline."""
import hashlib
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_semantic_local_20261012 import dual_residual

OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source6-20261012'
FIELDS={'fina_indicator':['q_roe','q_sales_yoy','q_ocf_to_or','roic'],
        'balancesheet':['acct_payable'],'income':['oper_cost']}
SOURCES=[
 'quant/2024年度精选策略2/28.【回顾2】小市值成长股策略更新FROEC-PB-CAP-HL.txt',
 'quant/2023年度精选策略/59.可能是最接近实盘的“基本面三角.txt',
 'quant/聚宽2025年精选/60高股息V1.0（小程序公开股池）.txt']
SPECS=[
 ('qroe_accel','单季ROE改善',0,'4*qROE0-sum(qROE1..4)',False),
 ('qroe_accel_bm','ROE改善×低PB',0,'rank(4*qROE0-sum(qROE1..4))+rank(BM), BM>0',False),
 ('qroe_lowpb_gate','低PB半池内ROE改善',0,'4*qROE0-sum(qROE1..4); positive income and PB, bottom50% PB',True),
 ('triangle_roe_gate','基本面三角ROE改善',1,'qROE0/mean(qROE1..4)>1, five quarters qROE/growth/CFO-revenue>0',True),
 ('supplier_credit_roic_gate','高ROIC供应商信用',2,'365*mean(AP0,AP4)/TTM operating_cost; ROIC>8%',True),
 ('supplier_credit_quality','供应商信用×投资回报质量',2,'rank(365*mean(AP0,AP4)/TTM operating_cost)+rank(ROIC)',False)]

def build(fin,cap):
 def f(ep,col,i=0):return fin[f'{ep}.{col}.q{i}']
 roes=np.stack([f('fina_indicator','q_roe',i) for i in range(5)])
 accel=4*roes[0]-np.sum(roes[1:],axis=0)
 bm=q.ratio(f('balancesheet','total_hldr_eqy_exc_min_int'),cap*10000)
 positive=(bm>0)&(f('income','n_income_ttm')>0)
 pb=q.ratio(np.ones_like(bm),bm)
 lowpb=q.rank(np.where(positive,pb,np.nan))<=.5
 growth=np.stack([f('fina_indicator','q_sales_yoy',i) for i in range(5)])
 cash=np.stack([f('fina_indicator','q_ocf_to_or',i) for i in range(5)])
 improve=q.ratio(roes[0],np.mean(roes[1:],axis=0))
 gate=(roes>0).all(axis=0)&(growth>0).all(axis=0)&(cash>0).all(axis=0)&(improve>1)
 cost=f('income','oper_cost_ttm');ap=(f('balancesheet','acct_payable')+f('balancesheet','acct_payable',4))/2
 credit=q.ratio(365*ap,np.where(cost>0,cost,np.nan));credit=np.where(ap>=0,credit,np.nan)
 roic=f('fina_indicator','roic')
 vals=[accel,q.rank(np.where(bm>0,accel,np.nan))+q.rank(np.where(bm>0,bm,np.nan)),
       np.where(lowpb,accel,np.nan),np.where(gate,improve,np.nan),
       np.where(roic>8,credit,np.nan),q.rank(credit)+q.rank(roic)]
 return [np.where((cap>0)&np.isfinite(x),x,np.nan).astype(np.float32) for x in vals]

def verify(fin,cap,values):
 checks=[]
 for stop in [31,77,len(cap)-9]:
  cut=build({k:v[:stop] for k,v in fin.items()},cap[:stop])
  for spec,a,b in zip(SPECS,values,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,atol=1e-6)
   checks.append({'key':spec[0],'test':'prefix_recompute','stop':stop,'passed':True})
 expected=4*fin['fina_indicator.q_roe.q0']-sum(fin[f'fina_indicator.q_roe.q{i}'] for i in range(1,5))
 expected=np.where((cap>0)&np.isfinite(expected),expected,np.nan)
 np.testing.assert_allclose(expected,values[0],equal_nan=True,atol=1e-4,rtol=1e-5)
 checks.append({'test':'independent_ROE_four_prior_quarters','passed':True})
 return checks

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 calendar,stocks,fields=q.load_market();q.dates_all=calendar
 grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=calendar.get_indexer(grid)
 base=q.financial_snapshot(grid,stocks)
 original_out=q.OUT;original_fields=q.FIN_FIELDS
 try:
  q.OUT=OUT;q.FIN_FIELDS=FIELDS
  extra=q.financial_snapshot(grid,stocks)
 finally:q.OUT=original_out;q.FIN_FIELDS=original_fields
 base.update(extra);cap=fields['cap'][pos];values=build(base,cap)
 q.dump(OUT/'verification.json',verify(base,cap,values))
 q.dump(OUT/'config.json',{'version':q.ALIGNMENT_RULE_VERSION+'-quant-source6-arithmetic-fullA',
  'warmup':'20180101','formal_window':['20210907','20260907'],'recent_window':['20260101',str(calendar.max().date())],
  'cycle':10,'groups':10,'qfq':True,'total_mv':True,'universe':'SH/SZ fullA','label_offset':1,
  'benchmark':'factor_valid','one_way_cost':.003,'platform_net_filter':'all','platform_compute_spent':0,
  'source_hypotheses':6,'oos':False,'PIT':'announcement replay, quarterly lags, contiguous TTM',
  'proxy':'Tushare quarterly q_roe/q_sales_yoy/q_ocf_to_or; ROIC is reported, not exact JQ ROIC_TTM',
  'source_omissions':'source industry/trading gates, final smallcap ranking and dividend screen removed',
  'ordering':'latest chronological financial quarter assumed for source last column; JQ runtime unavailable',
  'gated_candidates':'different factor_valid benchmark; cannot directly compare gated net excess to full coverage',
  'parameter_selection':'fixed before evaluating outcomes, no grid search'})
 rows=[];meta=[];panels={};rev=-(q.ratio(fields['close'],q.delay(fields['close'],20))-1)[pos]
 for spec,x in zip(SPECS,values):
  key,name,src,formula,gated=spec;path=q.ROOT/SOURCES[src]
  meta.append({'key':key,'name':name,'source_paths':[SOURCES[src]],'source_sha256':[hashlib.sha256(path.read_bytes()).hexdigest()],
               'formula':formula,'direction':1,'fidelity':'PIT_quarterly_accounting_proxy_atom_or_rank_adaptation','gated':gated})
  panels[key]=pd.DataFrame(x,index=grid,columns=stocks)
  for form,score in [('raw',x),('size_reversal_rank_residual',dual_residual(x,-cap,rev))]:
   for win,mask in [('five_year',np.ones(len(grid),bool)),('recent',grid>='20260101')]:
    dest=OUT/win;dest.mkdir(exist_ok=True)
    a,p,d=q.evaluate(score[mask],grid[mask],stocks,pos[mask],fields)
    a.update(key=key,name=name,window=win,form=form,gated=gated,coverage_pct=a['periods']/mask.sum()*100)
    rows.append(a);q.dump(dest/f'{key}.{form}.json',a)
    p.to_csv(dest/f'{key}.{form}.periods.csv',index=False);d.to_csv(dest/f'{key}.{form}.daily_nav.csv',index=False)
  print(key,[(r['window'],r['form'],round(r.get('net_excess_pct',0),3),round(r.get('held_daily_max_drawdown_pct',0),2)) for r in rows[-4:]],flush=True)
  pd.DataFrame(rows).drop(columns=['years','group_arithmetic_annual_pct'],errors='ignore').to_csv(OUT/'results.csv',index=False)
  q.dump(OUT/'recipe_manifest.json',meta)
 pd.to_pickle({'dates':grid,'stocks':stocks,'panels':panels,'metadata':meta},OUT/'signal_panels.pkl')
 q.dump(OUT/'completion.json',{'completed':True,'hypotheses':6,'rows':len(rows),'platform_compute_spent':0,'pool_test_done':False})
if __name__=='__main__':main()
