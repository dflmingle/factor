from pathlib import Path
import numpy as np,pandas as pd,importlib.util,json,pickle
ROOT=Path('/data/games/factor_'); EXP=ROOT/'research_reports/platform_alignment/original60-walkforward-20261012/train94-impute0'
OUT=ROOT/'research_reports/platform_alignment/nonlinear-paper-robust-20261012'
spec=importlib.util.spec_from_file_location('simple',ROOT/'research_reports/platform_alignment/nonlinear-walkforward-20261012/run.py'); simple=importlib.util.module_from_spec(spec); spec.loader.exec_module(simple)
with (ROOT/'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl').open('rb') as f: calendar,stocks,fields=pickle.load(f)
calendar=pd.DatetimeIndex(calendar); stocks=pd.Index(stocks)
cap=fields['cap']; close=fields['close'];
meta=json.loads((ROOT/'research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2/metadata.json').read_text()); dates=pd.DatetimeIndex(meta['signal_dates']); formal=np.ones(len(dates),bool); recent=dates>='2026-01-01'
sig=np.load(EXP/'signal.npy',mmap_mode='r'); y=(close[[calendar.get_loc(d)+11 for d in dates]].astype(float)/close[[calendar.get_loc(d)+1 for d in dates]]-1).astype(np.float32); capx=cap[[calendar.get_loc(d) for d in dates]]
# saved signal raw values; rank each current date, then causal pooling
ranked=simple.rank(sig)
valid=np.isfinite(capx); ranked[~valid]=np.nan
cands={}
for alpha in (.5,.75):
 out=np.full_like(ranked,np.nan)
 for i in range(len(dates)):
  cur=ranked[i]
  if i==0: out[i]=cur
  else:
   prev=np.nan_to_num(out[i-1],nan=0.)
   out[i]=alpha*np.nan_to_num(cur,nan=0.)+(1-alpha)*prev
   out[i][~np.isfinite(cur)]=np.nan
 cands[f'POOL_RANK_EMA{alpha}']=out
# Winsorize current cross-sectional forecast before same .5 pooling
out=np.full_like(ranked,np.nan)
for i in range(len(dates)):
 cur=ranked[i]; good=np.isfinite(cur)
 if good.sum():
  lo,hi=np.nanquantile(cur,[.05,.95]); cur=np.clip(cur,lo,hi)
 if i==0: out[i]=cur
 else:
  out[i]=.5*np.nan_to_num(cur,nan=0.)+.5*np.nan_to_num(out[i-1],nan=0.)
  out[i][~np.isfinite(cur)]=np.nan
cands['POOL_WINSOR5_EMA50']=out
rows=[]
for name,s in [('BASE',ranked),*cands.items()]:
 for w,m in [('formal_5y',formal),('recent_2026',recent)]:
  st,p,g=simple.metrics(s[m],y[m],capx[m],dates[m]); daily,monthly,turn=simple.daily_path(s[m],y[m],capx[m],dates[m],calendar,close); st.update(simple.nav_metrics(daily)); rows.append(dict(candidate=name,window=w,**st,mean_monthly_nc=float(monthly.nc[~monthly.partial].mean()),monthly_turn=float(monthly.turnover[~monthly.partial].mean())) )
df=pd.DataFrame(rows)
df.to_csv(OUT/'results.csv',index=False)
np.save(OUT/'signals_ranked.npy', ranked)
for n,v in cands.items(): np.save(OUT/(n+'.npy'),v)
(OUT/'protocol.json').write_text(json.dumps({'source':'original60-walkforward-20261012/train94-impute0/signal.npy','candidates':['POOL_RANK_EMA0.5','POOL_RANK_EMA0.75','POOL_WINSOR5_EMA50'],'ema_is_causal':True,'weights_fixed_before_scoring':True,'formal_window':['20210907','20260907'],'recent_window':['20260101','20260907'],'platform_runs':0,'constraints':['shallow output pooling only','causal prior signal only','three fixed candidates']},ensure_ascii=False,indent=2)+'\n')
print(df.to_string(index=False))
