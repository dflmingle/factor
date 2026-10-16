"""Financial source frontier with isolated PIT schemas and raw cutoff replay."""
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit
from quant_corpus_sweep_20261013 import tie_diagnostic

RISK='quant/2022年度精选策略/94.量化排雷—一个实用排雷系统.txt'
ASSETS='quant/2023年度精选策略/99.全市场选股？7年5倍不择时，回撤30%左右.txt'
FF='quant/2023年度精选策略/18.【复现】FFScore财务模型.txt'
VALUE='quant/2020年度精选策略/31 低PB价值投资策略分享.txt'
QUALITY='quant/2021年度精选策略/79.【多因子选股模型框架】(单因子各项指标评分细则).txt'
RETAIN='quant/聚宽2025年精选/48投资回报率ROIC中等市值.txt'
BOARD='quant/2024年度精选策略2/93.因子看板多因子模型---由量化课堂多因子模型修改.txt'
RD='quant/2021年度精选策略/42.市值，研发支出，roe，三因子，跑赢大盘.txt'
SVR='quant/2020年度精选策略/06 为什么股票市值是当前的样子？.txt'
SPECS={30:[
 spec('soft_assets_low','低软资产比例',RISK,
      '(fix_assets+cip+const_materials+money_cap)/total_assets-1; optional source nulls filled0 only after an available filing',
      'proxy: source annual risk atom adapted to quarterly latest PIT; explicit source null-to-zero retained for components'),
 spec('goodwill_pretax_low','低商誉利润压力',RISK,
      '-goodwill/total_profit_ttm, profit_ttm>0; goodwill missing remains missing',
      'proxy: annual source goodwill/profit atom adapted to PIT TTM pretax profit'),
 spec('deposit_loan_overlap_low','低存贷双高交集',RISK,
      '-min((cash+notes_receiv+other_cur_assets)/assets-.3,(st_borr+notes_payable+noncur_due1y+bond_payable+lt_payable+lt_borr)/assets-.3)',
      'proxy: quarterly continuous source risk intersection; source source component fillna0 retained with known positive assets'),
],31:[
 spec('roa_recent_acceleration4','ROA最新季相对四季改善',ASSETS,
      'latest reported ROA-mean(q0..q3 ROA)',
      'proxy: source4quarter ROA improvement atom; quality/value and trading filters omitted'),
 spec('good_asset_turnover','优质资产周转',ASSETS,
      'total_revenue_ttm/(assets-notes_receiv-accounts_receiv-oth_receiv-goodwill-intan_assets-inventories-cip); denom>0',
      'proxy: source quarterly revenue adapted to PIT TTM; all seven bad-asset components required, no zero fill'),
 spec('good_asset_roa_bm_rank','优质资产改善价值组合',ASSETS,
      'rank(good_asset_turnover)+rank(ROA_q0-mean(q0..q3))+rank(positive_BM)+rank(-liabilities/assets)',
      'proxy: fixed equal-rank fullA adaptation of source sequential gates; source middle bad-asset percentile filter omitted'),
],32:[
 spec('ffscore6_literal_repaired','FFScore六项源码结构重建',FF,
      'count>0 of ROE/lag4ROE-1,ROA2,GPM/lag4GPM-1,CATURN/lag4CATURN-1,ROA2/lag4ROA2-1,LIQ/lag4LIQ-1; ROA2=total_profit+fin_exp/CSmean(CA+lag1CA)',
      'proxy: source parenthesis and cross-stock denominator retained; reported YTD fields; supersedes wrong duplicated ROA term in source18'),
 spec('value_quality_source_weights','低PB源码质量权重',VALUE,
      '.7 rank(ROE)+.05 rank(-positive_PB)+.2 rank(profit_yoy)+.05 rank(total_mv)',
      'proxy: exact source weights/order with fullA ranking, source lowPB top10 and filters omitted'),
 spec('quality_score9_turn_fixed','九项评分换手字段修复',QUALITY,
      'rank(OPM)+rank(ROA)+rank(GPM)+rank(GPOA)+rank(-positivePB)+rank(-positivePS)+rank(-positivePE)+rank(-turnover)+rank(NPM)',
      'proxy: fixes source21 erroneous negativeROE turnover leg; daily_basic turnover and PIT TTM margin mappings'),
],33:[
 spec('retained_profit_source','未分配利润源码排序',RETAIN,
      'latest PIT balancesheet.undistr_porfit',
      'proxy: source retained-profit order without original size/ROIC/quality filters; absolute scale size-exposure control required'),
 spec('retained_profit_equity','留存利润净资产占比',RETAIN,
      'latest undistr_porfit/positive total_hldr_eqy_exc_min_int',
      'proxy: size-scaled adaptation of source retained earnings; not original source exact formula'),
 spec('retained_profit_roic_rank','留存利润×ROIC质量',RETAIN,
      'rank(undistr_porfit/positive equity)+rank(latest ROIC)',
      'proxy: fixed fullA equal-rank adaptation; source ROIC>.08 gate replaced by rank'),
],40:[
 spec('financing_cash_growth_yoy','筹资现金流同比变化',BOARD,
      '(TTM financing_cash_q0-TTM financing_cash_q4)/abs(TTM financing_cash_q4); nonzero prior',
      'proxy: vendor financing_cash_growth_rate not byte-equivalent; explicit net financing cash TTM mapping, high source direction'),
 spec('reported_sales_cash_ratio_low','销售商品现金收入比低',BOARD,
      '-TTM c_fr_sale_sg/TTM revenue; revenue>0',
      'proxy: source goods_service_cash_to_operating_revenue_ttm low direction preserved; Tushare PIT sales cash mapping'),
 spec('davol20_relative_turn_low','相对长期换手DAVOL20低',BOARD,
      '-(MEAN20(turnover)-MEAN250(turnover))',
      'proxy: source DAVOL20 documented as short-minus-long average daily turnover; freefloat vendor turnover->local turnover; exact vendor long-window unknown,250 fixed'),
],41:[
 spec('capitalized_development_assets','资本化研发资产占比',RD,
      'latest PIT balancesheet.r_and_d/positive total_assets',
      'proxy: capitalized development expenditure, distinct from income R&D expense; source raw-amount direction high, normalized by assets explicitly'),
 spec('development_size_roe_source','市值研发ROE源码三秩',RD,
      'rank(total_mv)+rank(capitalized r_and_d)+rank(ROE)',
      'proxy: source custom getRank DESCENDING then bubble points DESCENDING × weights[-1,-1,-1] means HIGH all three; corrects old low-three semantic note; missing preserved'),
 spec('svr_financial_valuation_residual','财务SVR估值残差',SVR,
      '-[log(cap/10000)-SVR_RBF(gamma=.1,C=1,epsilon=.1).fit_predict(log(assets-liab),assets/liab,log(abs(YTD_NI)),log(abs(NI+1)) if NI+1<0 else0,revenue_yoy,log(capitalizedRD))]',
      'proxy: six financial inputs preserve source NI_p/NI_n bugs and explicit null0/clamp10000; CYE and PIT industry inputs unavailable and OMITTED; not complete source SVR'),
]}
EXTRA={'balancesheet':['fix_assets','const_materials','oth_cur_assets','notes_payable','lt_payable','undistr_porfit'],
       'income':['total_profit','fin_exp']}

def build(batch,fin,fields,pos):
 def g(ep,col,k=0):return fin[f'{ep}.{col}.q{k}'].astype(float)
 if batch==40:
  a=g('cashflow','n_cash_flows_fnc_act_ttm');b=g('cashflow','n_cash_flows_fnc_act_ttm',4)
  growth=q.ratio(a-b,np.where(np.abs(b)>1,np.abs(b),np.nan))
  revenue=g('income','revenue_ttm');cash=-q.ratio(g('cashflow','c_fr_sale_sg_ttm'),np.where(revenue>0,revenue,np.nan))
  relative=-(q.rolling(fields['turnover'],20)-q.rolling(fields['turnover'],250))[pos]
  return [growth,cash,relative]
 if batch==41:
  from sklearn.svm import SVR as Regressor
  assets=g('balancesheet','total_assets');liab=g('balancesheet','total_liab');dev=g('balancesheet','r_and_d')
  ratio=q.ratio(dev,np.where(assets>0,assets,np.nan))
  combo=q.rank(fields['cap'][pos])+q.rank(dev)+q.rank(g('fina_indicator','roe'))
  ni=g('income','n_income');growth=g('fina_indicator','or_yoy')
  with np.errstate(divide='ignore',invalid='ignore'):
   terms=[np.log(assets-liab),q.ratio(assets,liab),np.log(np.abs(ni)),
          np.where(ni+1<0,np.log(np.abs(ni+1)),np.nan),growth,np.log(dev)]
  x=np.stack(terms,axis=-1)
  # Source explicitly fills NaN after logs, then caps both signs at10000.
  x=np.nan_to_num(x,nan=0,posinf=10000,neginf=-10000);x=np.clip(x,-10000,10000)
  cap=fields['cap'][pos];res=np.full(cap.shape,np.nan,np.float32)
  for i in range(len(cap)):
   valid=(cap[i]>0)&np.isfinite(assets[i])&(assets[i]>0)
   if valid.sum()<100:continue
   y=np.log(cap[i,valid]/10000);model=Regressor(kernel='rbf',gamma=.1)
   res[i,valid]=-(y-model.fit(x[i,valid],y).predict(x[i,valid]))
  return [ratio,combo,res]
 def bs(col,k=0):return g('balancesheet',col,k)
 def fi(col,k=0):return g('fina_indicator',col,k)
 a=bs('total_assets');a=np.where(a>0,a,np.nan)
 eq=bs('total_hldr_eqy_exc_min_int');eq=np.where(eq>0,eq,np.nan)
 mv=fields['cap'][pos]*10000;bm=q.ratio(eq,mv)
 if batch==30:
  soft=q.ratio(sum(np.nan_to_num(bs(k),nan=0) for k in ['fix_assets','cip','const_materials','money_cap']),a)-1
  profit=g('income','total_profit_ttm');gw=-q.ratio(bs('goodwill'),np.where(profit>0,profit,np.nan))
  deposit=q.ratio(sum(np.nan_to_num(bs(k),nan=0) for k in ['money_cap','notes_receiv','oth_cur_assets']),a)
  loan=q.ratio(sum(np.nan_to_num(bs(k),nan=0) for k in ['st_borr','notes_payable','non_cur_liab_due_1y','bond_payable','lt_payable','lt_borr']),a)
  return [soft,gw,-np.minimum(deposit-.3,loan-.3)]
 if batch==31:
  delta=fi('roa')-sum(fi('roa',k) for k in range(4))/4
  good=a-sum(bs(k) for k in ['notes_receiv','accounts_receiv','oth_receiv','goodwill','intan_assets','inventories','cip'])
  turn=q.ratio(g('income','total_revenue_ttm'),np.where(good>0,good,np.nan))
  return [delta,turn,q.rank(turn)+q.rank(delta)+q.rank(bm)+q.rank(-q.ratio(bs('total_liab'),a))]
 if batch==32:
  def denom(k):return np.nanmean(bs('total_cur_assets',k)+bs('total_cur_assets',k+1),axis=1)[:,None]
  ca0=denom(0);ca4=denom(4)
  roa2=g('income','total_profit')+q.ratio(g('income','fin_exp'),ca0)
  roa24=g('income','total_profit',4)+q.ratio(g('income','fin_exp',4),ca4)
  liq=q.ratio(bs('total_cur_assets'),bs('total_cur_liab'));liq4=q.ratio(bs('total_cur_assets',4),bs('total_cur_liab',4))
  cat=q.ratio(g('income','revenue'),ca0);cat4=q.ratio(g('income','revenue',4),ca4)
  legs=[q.ratio(fi('roe'),fi('roe',4))-1,roa2,q.ratio(fi('grossprofit_margin'),fi('grossprofit_margin',4))-1,
        q.ratio(cat,cat4)-1,q.ratio(roa2,roa24)-1,q.ratio(liq,liq4)-1]
  # Original sign() turns invalid legs to0; require complete financial coverage
  # here, because unreported values do not establish a failed quality condition.
  valid=np.isfinite(np.stack(legs)).all(axis=0)
  ff=np.where(valid,np.sum(np.stack(legs)>0,axis=0),np.nan)
  weighted=.7*q.rank(fi('roe'))+.05*q.rank(bm)+.2*q.rank(fi('netprofit_yoy'))+.05*q.rank(mv)
  rev=g('income','total_revenue_ttm');op=g('income','operate_profit_ttm');ni=g('income','n_income_attr_p_ttm')
  ey=np.where(ni>0,q.ratio(ni,mv),np.nan);sy=np.where(rev>0,q.ratio(rev,mv),np.nan)
  score=q.rank(q.ratio(op,rev))+q.rank(fi('roa'))+q.rank(fi('grossprofit_margin'))+q.rank(q.ratio(fi('grossprofit_margin')*.01*rev,a))
  score+=q.rank(bm)+q.rank(sy)+q.rank(ey)+q.rank(-fields['turnover'][pos])+q.rank(fi('netprofit_margin'))
  return [ff,weighted,score]
 if batch==33:
  retain=bs('undistr_porfit');r=q.ratio(retain,eq)
  return [retain,r,q.rank(r)+q.rank(fi('roic'))]
 raise ValueError(batch)

def verify(batch,fin,grid,stocks,out,f,pos):
 checks=[];oldout,oldloader=q.OUT,q.pit_tables
 tables=q.pit_tables();ids=np.arange(min(128 if batch==41 else 8,len(stocks)))
 try:
  for n in [35,79]:
   cutoff=grid[n-1];sub={ep:t[(t.ann_date<=cutoff)&t.instrument.isin(stocks[ids])].copy() for ep,t in tables.items()}
   q.pit_tables=lambda:sub
   with tempfile.TemporaryDirectory(prefix='raw-pit-check-',dir=out) as tmp:
    q.OUT=Path(tmp);replay=q.financial_snapshot(grid[:n],stocks[ids],lags=6)
    smallf={k:v[:,ids] for k,v in f.items()}
    a=build(batch,{k:v[:n,ids] for k,v in fin.items()},smallf,pos[:n]);b=build(batch,replay,smallf,pos[:n])
    for sp,x,y in zip(SPECS[batch],a,b):
     np.testing.assert_allclose(x,y,equal_nan=True,rtol=1e-6,atol=1e-6)
     checks.append(dict(key=sp['key'],test='raw_filing_cutoff_replay',cutoff=str(cutoff),stocks=len(ids),passed=True))
 finally:q.OUT,q.pit_tables=oldout,oldloader
 if batch==41:
  toy=np.array([[1.,1.,1.],[2.,2.,2.],[3.,3.,3.]])
  source_ranks=np.column_stack([pd.Series(toy[:,k]).rank(ascending=False).to_numpy() for k in range(3)])
  source_points=source_ranks@np.array([-1.,-1.,-1.])
  assert np.argmax(source_points)==2
  checks.append(dict(test='independent_descending_rank_descending_bubble_direction',passed=True))
 return checks

def main():
 p=argparse.ArgumentParser();p.add_argument('--batches',type=int,nargs='+',default=[30,31,32,33]);args=p.parse_args()
 if any(b in args.batches for b in [40,41]) and len(args.batches)!=1:p.error('schemas40/41 require a separate --batches40 or41 invocation')
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 oldout,oldfields=q.OUT,q.FIN_FIELDS
 # Different schemas always get their own cache directory; the snapshot helper
 # itself does not key caches by dates or fields.
 extra_only=args.batches==[40]
 rd_only=args.batches==[41]
 name='quant-corpus-cash-frontier-schema-20261013' if extra_only else ('quant-corpus-rd-frontier-schema-20261013' if rd_only else 'quant-corpus-financial-frontier-schema-20261013')
 dataout=q.ROOT/'research_reports/platform_alignment'/name;dataout.mkdir(exist_ok=True)
 try:
  if extra_only:q.FIN_FIELDS={'income':['revenue'],'cashflow':['n_cash_flows_fnc_act','c_fr_sale_sg']}
  elif rd_only:q.FIN_FIELDS={'balancesheet':['r_and_d','total_assets','total_liab'],'income':['n_income'],'fina_indicator':['roe','or_yoy']}
  else:q.FIN_FIELDS={ep:list(dict.fromkeys(cols+EXTRA.get(ep,[]))) for ep,cols in oldfields.items()}
  q.OUT=dataout
  q.dump(dataout/'schema.json',dict(fields=q.FIN_FIELDS,signal_dates=[str(x) for x in grid],symbols=len(stocks),rule=q.ALIGNMENT_RULE_VERSION))
  fin=q.financial_snapshot(grid,stocks,lags=6)
  for batch in args.batches:
   # source41 was stopped before evaluation to correct the written ranking
   # explanation and to strengthen SVR cutoff checks to128 stocks. Preserve its
   # frozen plan; the unchanged formulas run in a fresh source42 directory.
   output_batch=42 if batch==41 else batch
   out=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{output_batch}-20261013';out.mkdir(exist_ok=True)
   plan=dict(specs=SPECS[batch],rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='fixed source formula before evaluation')
   path=out/'frozen_plan.json'
   if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('plan mismatch')
   q.dump(path,plan)
   if (out/'audit_complete.json').exists():print('SKIP COMPLETE',batch,flush=True);continue
   verification=verify(batch,fin,grid,stocks,out,f,pos);vals=build(batch,fin,f,pos)
   for sp,x in zip(SPECS[batch],vals):print('coverage',sp['key'],np.isfinite(x).sum(axis=1).min(),flush=True)
   q.OUT=oldout
   run(out,SPECS[batch],vals,cal,stocks,f,verification,dict(fidelity='PIT financial source proxy, not platform validated',
       missing='source30 soft/deposit optional report components0 only per explicit source; all other missing preserved',
       statistics='exploratory, no independent OOS',source32_note='corrected experiment, original source18/source21 untouched'))
   audit(out,cal,stocks,f);tie_diagnostic(out,cal,stocks,f)
   q.dump(out/'audit_complete.json',dict(completed=True,batch=batch,platform_compute=0))
   q.OUT=dataout;print('AUDIT FINISHED',batch,flush=True)
 finally:q.OUT,q.FIN_FIELDS=oldout,oldfields

if __name__=='__main__':main()
