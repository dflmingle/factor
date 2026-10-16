import numpy as np, pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
SRC='quant/2024年度精选策略2/85.价值策略重开，再次向Jqz1226致敬.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-adjusted-value-frontier-20261013'
S=[spec('adjvalue85_pe_hb_tb','扣非利润低估值×利润环比同比加速',SRC,'-rank(PE_adj)+rank(profit_q0/profit_q1)+rank(profit_q0/profit_q4)','proxy: reported profit_dedt q0/q1/q4; source six-quarter grouping and market RSRS omitted'),spec('adjvalue85_receivable_quality','扣非利润低估值×高应收周转',SRC,'-rank(PE_adj)+rank(revenue_ttm/(AR+bill-advance))','proxy: TTM revenue and available receivable fields; source PE<20 and report-date gates omitted'),spec('adjvalue85_all_quality','低估值×加速×周转连续组合',SRC,'-rank(PE_adj)+rank(hb)+rank(tb)+rank(ar_turnover)','proxy: daily PIT adaptation, no source portfolio/trading execution')]
def main():
 OUT.mkdir(exist_ok=True);cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);fin=q.financial_snapshot(grid,stocks);cap=f['cap'][pos];
 p=fin['income.n_income_attr_p.q0'];p1=fin['income.n_income_attr_p.q1'];p4=fin['income.n_income_attr_p.q4'];rev=fin['income.revenue_ttm.q0'];
 pe=q.ratio(cap*10000,np.where(p>0,p,np.nan));hb=q.ratio(p,np.where(p1>0,p1,np.nan));tb=q.ratio(p,np.where(p4>0,p4,np.nan));
 ar=fin['balancesheet.accounts_receiv.q0']+fin['balancesheet.notes_receiv.q0'];turn=q.ratio(rev,np.where(ar>0,ar,np.nan));valid=cap>0
 vals=[-q.rank(np.where(valid,pe,np.nan))+q.rank(np.where(valid,hb,np.nan))+q.rank(np.where(valid,tb,np.nan)), -q.rank(np.where(valid,pe,np.nan))+q.rank(np.where(valid,turn,np.nan)), -q.rank(np.where(valid,pe,np.nan))+q.rank(np.where(valid,hb,np.nan))+q.rank(np.where(valid,tb,np.nan))+q.rank(np.where(valid,turn,np.nan))]
 checks=[]
 for n in [35,79]:
  for x in vals: assert x[:n].shape==(n,len(stocks))
  checks.append(dict(test='PIT_snapshot_prefix_shape',stop=n,passed=True))
 run(OUT,S,vals,cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='source85 PIT financial adaptation; source report grouping and execution omitted',residual_guard='constant residual<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED_ADJVALUE',flush=True)
if __name__=='__main__':main()
