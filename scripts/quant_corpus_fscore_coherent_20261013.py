"""Five coherent announced quarters, source28/78 adjacent TTM quality atoms.

Eight observed accounting conditions only: no invented issuance event. Integer
count is an explicit repair of pandas boolean addition, not original execution.
"""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
S28='quant/2023年度精选策略/28.F_Score 选股，年化80%+.txt'
S78='quant/2024年度精选策略2/78.ffscore选股加rsrs择时.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source91-20261013'
FIELDS={'income':['revenue','oper_cost'],'cashflow':['n_cashflow_act'],
 'balancesheet':['total_assets','total_ncl','total_cur_assets','total_cur_liab'],
 'fina_indicator':['q_dtprofit']}
SPECS=[
 spec('fscore8_coherent_adjacent_count','同报告期相邻TTM八条件整数分',S28,
 'I(adjNI_TTM/avg4assets>0)+I(CFO_TTM/avg4assets>0)+I(adjROA-previousAdjacentTTMROA>0)+I(CFOA-adjROA>0)+I(qoqNCL/assets<=0)+I(qoqcurrentratio>0)+I(adjacentTTMgrossmargin>0)+I(adjacentTTMassetturn>0)',
 'proxy: five coherent quarters and actual-announcement revisions; Tushare q_dtprofit for JQ adjusted_profit; eight integer accounting scores repair original pandas bool+bool OR; unavailable actual SPO event is OMITTED, not assumed no issuance; fullA replaces HS300, source strict9/9 selection not reproduced'),
 spec('adjacent_ttm_deducted_roa_change','扣非TTM盈利相邻季改善',S78,
 'sum(q_dtprofit.q0..3)/mean(assets.q0..3)-sum(q_dtprofit.q1..4)/mean(assets.q1..4)',
 'proxy: source fivequarter adjacent TTM ROA change preserved; same-period statement matching, deducted profit vendor mapping; no RSRS/index/industry/residualvol gates'),
 spec('adjacent_ttm_grossmargin_change','TTM毛利率相邻季改善',S28,
 'cost_TTMprior/revenue_TTMprior-cost_TTMcurrent/revenue_TTMcurrent; positive revenues',
 'proxy: source margin accounting atom; reported YTD revenue/cost differenced into quarters before TTM; latest income period matches other statements'),
 spec('adjacent_ttm_assetturn_change','TTM资产周转相邻季改善',S28,
 'revenue_TTMcurrent/mean4currentAssets-revenue_TTMprior/mean4priorAssets',
 'proxy: source quarteradjacent TTM turnover; individual asset denominators, not previous RFScore crosssection scalar bug'),
 spec('fscore8_ge7_roaimprove_conservative','八条件至少七项内ROA改善',S78,
 'adjacent deductedROAchange ranked on score8>=7 and ROAchange>.002',
 'proxy: explicit NEW conservative qualification requiring seven observed conditions outofeight, not source score9>6; unknown SPO not given pass. Original highest80pct Barra residualvol/index/industry/RSRS omitted; factor_valid restricted benchmark')]
SPECS[-1]['gated']=True

def coherent(tables,grid,stocks):
 names={'profit':('fina_indicator','q_dtprofit'),'revenue':('income','revenue'),
 'cost':('income','oper_cost'),'cfo':('cashflow','n_cashflow_act'),
 'assets':('balancesheet','total_assets'),'ncl':('balancesheet','total_ncl'),
 'ca':('balancesheet','total_cur_assets'),'cl':('balancesheet','total_cur_liab')}
 out={n:np.full((len(grid),len(stocks),5),np.nan) for n in names}
 grouped={ep:{s:g.sort_values(['ann_date','end_date','update_flag']) for s,g in t.groupby('instrument',sort=False)} for ep,t in tables.items()}
 for j,symbol in enumerate(stocks):
  events={ep:[(r['ann_date'],pd.Period(r['end_date'],freq='Q-DEC'),r) for r in grouped[ep].get(symbol,pd.DataFrame()).to_dict('records')] for ep in tables}
  reports={ep:{} for ep in tables};at={ep:0 for ep in tables}
  for i,d in enumerate(grid):
   for ep,rows in events.items():
    while at[ep]<len(rows) and rows[at[ep]][0]<=d:
     _,end,r=rows[at[ep]];reports[ep][end]=r;at[ep]+=1
   if not reports['income']:continue
   current=max(reports['income'])
   for k in range(5):
    end=current-k
    for n,(ep,col) in names.items():
     r=reports[ep].get(end)
     if r is None:continue
     value=float(r.get(col,np.nan))
     if ep in ['income','cashflow'] and end.quarter!=1:
      prior=reports[ep].get(end-1)
      value-=float(prior.get(col,np.nan)) if prior is not None else np.nan
     out[n][i,j,k]=value
 return out

def values(x):
 a=x['assets'];cur=a[:,:,:4].mean(axis=-1);prior=a[:,:,1:].mean(axis=-1)
 cur=np.where(cur>0,cur,np.nan);prior=np.where(prior>0,prior,np.nan)
 p=x['profit'];roa=q.ratio(p[:,:,:4].sum(axis=-1),cur);roap=q.ratio(p[:,:,1:].sum(axis=-1),prior)
 cfoa=q.ratio(x['cfo'][:,:,:4].sum(axis=-1),cur)
 rv=x['revenue'];cv=x['cost'];r0=rv[:,:,:4].sum(axis=-1);r1=rv[:,:,1:].sum(axis=-1)
 gm=q.ratio(cv[:,:,1:].sum(axis=-1),np.where(r1>0,r1,np.nan))-q.ratio(cv[:,:,:4].sum(axis=-1),np.where(r0>0,r0,np.nan))
 at=q.ratio(r0,cur)-q.ratio(r1,prior)
 lev=-(q.ratio(x['ncl'][:,:,0],a[:,:,0])-q.ratio(x['ncl'][:,:,1],a[:,:,1]))
 cr=q.ratio(x['ca'][:,:,0],np.where(x['cl'][:,:,0]>0,x['cl'][:,:,0],np.nan))-q.ratio(x['ca'][:,:,1],np.where(x['cl'][:,:,1]>0,x['cl'][:,:,1],np.nan))
 legs=np.stack([roa,cfoa,roa-roap,cfoa-roa,lev,cr,gm,at]);ok=np.isfinite(legs).all(axis=0)
 cond=legs>0;cond[4]=legs[4]>=0;score=np.where(ok,cond.astype(int).sum(axis=0),np.nan)
 return [score,roa-roap,gm,at,np.where((score>=7)&(roa-roap>.002),roa-roap,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='all5 fixed source hypotheses before evaluation; no tuning')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];old=q.FIN_FIELDS
 try:
  q.FIN_FIELDS=FIELDS;tables=q.pit_tables();ids=np.arange(256);small={ep:t[t.instrument.isin(stocks[ids])] for ep,t in tables.items()}
  full=coherent(small,grid,stocks[ids]);vv=values(full);checks=[]
  for n in [35,79]:
   cutoff=grid[n-1];cut=coherent({ep:t[t.ann_date<=cutoff] for ep,t in small.items()},grid[:n],stocks[ids])
   for name in full:np.testing.assert_allclose(full[name][:n],cut[name],equal_nan=True)
   for sp,a,b in zip(SPECS,vv,values(cut)):
    np.testing.assert_allclose(a[:n],b,equal_nan=True);checks.append(dict(key=sp['key'],test='raw_announcements_revision_cutoff_YTDquarters_coherent_reports',cutoff=str(cutoff),finite=int(np.isfinite(b).sum()),passed=True))
  bools=pd.DataFrame({'a':[True,False],'b':[True,True]})
  assert (bools.a+bools.b).tolist()==[True,True]
  assert (bools.a.astype(int)+bools.b.astype(int)).tolist()==[2,1]
  checks.append(dict(test='source_boolean_addition_OR_not_integer_count',pandas=pd.__version__,original=(bools.a+bools.b).tolist(),repaired=(bools.a.astype(int)+bools.b.astype(int)).tolist(),passed=True))
  toy={name:np.ones((1,1,5)) for name in full};toy['assets'][:]=100;toy['profit'][0,0]=[5,4,3,2,1];toy['revenue'][0,0]=[50,40,30,20,10];toy['cost'][0,0]=[25,20,15,10,5]
  got=values(toy);np.testing.assert_allclose([got[1][0,0],got[2][0,0],got[3][0,0]],[.04,0,.4],atol=1e-7)
  checks.append(dict(test='independent_adjacent5quarter_TTM_toy_not_YoY',passed=True))
  cache=OUT/'coherent_quarters.pkl'
  if cache.exists():x=pd.read_pickle(cache)
  else:x=coherent(tables,grid,stocks);pd.to_pickle(x,cache)
 finally:q.FIN_FIELDS=old
 q.dump(OUT/'source_evidence.json',{S28:read_text(q.ROOT/S28),S78:read_text(q.ROOT/S78)})
 run(OUT,SPECS,values(x),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='eight accounting conditions proxy; no source9point claim',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED91',flush=True)
if __name__=='__main__':main()
