"""Causal coherent quarterly FCF persistence extracted from source27."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略1/27.根据大小盘相对强弱选择合适的板块股票进行交易.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source127-20261013'
SCHEMA=q.ROOT/'research_reports/platform_alignment/quant-corpus-fourquarter-fcf27-schema-20261013'
FIELDS={'cashflow':['n_cashflow_act','c_pay_acq_const_fiolta'],'income':['n_income_attr_p'],'balancesheet':['total_assets','total_cur_assets','total_cur_liab','total_hldr_eqy_exc_min_int'],'fina_indicator':['q_dt_roe','q_op_yoy']}
SPECS=[
 spec('style27_min4quarter_fcf_assets','连续四季最弱自由现金流资产比',SRC,'MIN4coherentSingleQuarter(CFO-capex)/latestAssets',
 'proxy NEW continuous ranking of source all4quarterFCF>0 gate; latestannouncedcashflow quarter anchor, income/balance/fina matchedperiod, YTD differences reconstruct quarters. No unreported capex zero-fill; source flow histories vendor equivalents not guaranteed.'),
 spec('style27_fourfcf_positive_BM_partial','四季自由现金流正约束账面价值',SRC,'equity/totalMV WHERE all4singlequarterFCF>0',
 'proxy source final lowPB sorting math on only fourFCFpositivity, remaining financial/largefloatshares/indexregime omitted explicitly; qualified factor_valid benchmark. Bookratio retains signed equity as sourcePB ascending not positivePB filter; score uses -PB not BM for exact signed sort.'),
 spec('style27_fourquarter_quality_PB_partial','四季现金成长质量约束低PB',SRC,'-PB WHERE currentRatio>fullCSmedian AND qDtROE>fullCSmedian AND min4FCF>0 AND min4quarterOpYoY>10 AND min4quarterParentNI>2*positiveCSmedianQuarterParentNI',
 'proxy latestmatchedquarter cashanchor. Original circulating_cap TOP50 sharecount qualifier omitted, NOT mappedtotalMV orcircmv. q_dt_roe/q_op_yoy vendor proxies; parentNI quarterlyrestored vs JQflow distinction explicit. Median originally fullinitial universe before largecap and allfinancialgates, reproducedfullA not withinqualifiedset. No index/buysell/monthly/positions claim.')]
SPECS[1]['formula']='-PB WHERE all4singlequarterFCF>0'
SPECS[1]['gated']=SPECS[2]['gated']=True

def coherent(tables,grid,stocks):
 out={k:np.full((len(grid),len(stocks),4),np.nan) for k in ['fcf','ni','assets','cr','equity','roe','growth']}
 groups={ep:{s:g.sort_values(['ann_date','end_date','update_flag']) for s,g in tab.groupby('instrument',sort=False)} for ep,tab in tables.items()}
 for j,s in enumerate(stocks):
  events={};at={ep:0 for ep in tables};reports={ep:{} for ep in tables}
  for ep in tables:
   tab=groups[ep].get(s);events[ep]=[] if tab is None else [(r['ann_date'],pd.Period(r['end_date'],freq='Q-DEC'),r) for r in tab.to_dict('records')]
  for i,d in enumerate(grid):
   for ep,rows in events.items():
    while at[ep]<len(rows) and rows[at[ep]][0]<=d:
     _,end,r=rows[at[ep]];reports[ep][end]=r;at[ep]+=1
   if not reports['cashflow']:continue
   current=max(reports['cashflow'])
   for k in range(4):
    end=current-k;cf=reports['cashflow'].get(end);ni=reports['income'].get(end);bs=reports['balancesheet'].get(end);fi=reports['fina_indicator'].get(end)
    def quarter(ep,col):
     r=reports[ep].get(end)
     if r is None:return np.nan
     z=float(r.get(col,np.nan))
     if end.quarter==1:return z
     old=reports[ep].get(end-1)
     return z-float(old.get(col,np.nan)) if old is not None else np.nan
    out['fcf'][i,j,k]=quarter('cashflow','n_cashflow_act')-quarter('cashflow','c_pay_acq_const_fiolta')
    out['ni'][i,j,k]=quarter('income','n_income_attr_p')
    if bs is not None:
     out['assets'][i,j,k]=bs.get('total_assets',np.nan);out['equity'][i,j,k]=bs.get('total_hldr_eqy_exc_min_int',np.nan)
     a=bs.get('total_cur_assets',np.nan);b=bs.get('total_cur_liab',np.nan);out['cr'][i,j,k]=a/b if b!=0 else np.nan
    if fi is not None:out['roe'][i,j,k]=fi.get('q_dt_roe',np.nan);out['growth'][i,j,k]=fi.get('q_op_yoy',np.nan)
 return out

def values(x,cap):
 fcf=x['fcf'];minimum=np.min(fcf,axis=-1);assets=x['assets'][:,:,0];eq=x['equity'][:,:,0];mv=cap.astype(float)*10000
 with np.errstate(divide='ignore',invalid='ignore'):pb=mv/eq;raw=minimum/np.where(assets>0,assets,np.nan)
 base=(minimum>0)&np.isfinite(pb);cr=x['cr'][:,:,0];roe=x['roe'][:,:,0];ni=x['ni']
 medni=np.nanmedian(np.where(ni[:,:,0]>=0,ni[:,:,0],np.nan),axis=1)[:,None]
 good=base&(cr>np.nanmedian(cr,axis=1)[:,None])&(roe>np.nanmedian(roe,axis=1)[:,None])&(np.min(x['growth'],axis=-1)>10)&(np.min(ni,axis=-1)>2*medni)
 return [raw,np.where(base,-pb,np.nan),np.where(good,-pb,np.nan)]

def main():
 OUT.mkdir(exist_ok=True);SCHEMA.mkdir(exist_ok=True);plan=dict(specs=SPECS,fields=FIELDS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='literal4quarters/min>0/median/>10/>2*median; financialproxies frozenbeforeoutcomes')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);oldfields=q.FIN_FIELDS
 try:
  q.FIN_FIELDS=FIELDS;tables=q.pit_tables();ids=np.arange(128);small={ep:t[t.instrument.isin(stocks[ids])] for ep,t in tables.items()};whole=coherent(small,grid,stocks[ids]);full=values(whole,f['cap'][pos][:,ids]);checks=[]
  for n in [35,79]:
   sub={ep:t[t.ann_date<=grid[n-1]] for ep,t in small.items()};cut=coherent(sub,grid[:n],stocks[ids]);vv=values(cut,f['cap'][pos[:n]][:,ids])
   for k in whole:np.testing.assert_allclose(whole[k][:n],cut[k],equal_nan=True,atol=1e-8)
   for s,a,b in zip(SPECS,full,vv):
    np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=s['key'],test='rawfiling_cutoff_and_coherentquarter_differencing_replay',cutoff=str(grid[n-1]),passed=True))
  cache=SCHEMA/'coherent_quarter_snapshots.pkl'
  if cache.exists():x=pd.read_pickle(cache)
  else:x=coherent(tables,grid,stocks);pd.to_pickle(x,cache)
  q.dump(SCHEMA/'schema.json',dict(fields=FIELDS,dates=list(grid),rule=q.ALIGNMENT_RULE_VERSION,anchor='latestannouncedcashflowquarter',fillmissing=False))
  q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
  run(OUT,SPECS,values(x,f['cap'][pos]),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='coherent PIT singlequarter FCF and explicit vendorROE/opgrowth proxies'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
  audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED127',flush=True)
 finally:q.FIN_FIELDS=oldfields
if __name__=='__main__':main()
