"""Fixed source60 RSRS mean-exit and completedbar bias slope variants."""
import json
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略2/60.ETF动量轮动RSRS择时-v2.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source112-20261013'
COMMON='proxy: daily fullA extension of ETF/index kernel, completed t-1 bars, rolling600seed; source 60minute MA20 stop missing, get_rank returns [code,score] rather than symbol list. Not original strategy, known family variant.'
SPECS=[
 spec('rsrs60_nonsell_positive_below_mean12','RSRS正值低于十二日均值退出',SRC,'I(rsrs>-.7 AND NOT(0<rsrs<MA12(rsrs)))',COMMON+' Source strict >-.7 and strict 0<score<mean. First11 callback means0; warmup proxy uses full causal history.'),
 spec('bias90_linear20_first_priorclose','前收盘九十乖离首点归一斜率',SRC,'OLS20((C/MA90)/(firstof20bias)) endingt-1',COMMON+' Exact source bias20/90, source83 used currentbar and scale10000; positive scale does not affect rank but onebar timing differs.')]

def values(f,pos):
 c=f['close'].astype(float);h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float));cov=h.rolling(18).cov(l);vl=l.rolling(18).var();vh=h.rolling(18).var();b=cov/vl
 rs=(((b-b.rolling(600).mean())/b.rolling(600).std(ddof=0))*cov**2/(vl*vh)).shift(1)
 m=rs.rolling(12).mean();gate=np.where(np.isfinite(rs)&np.isfinite(m),((rs>-.7)&~((rs>0)&(rs<m))).astype(float),np.nan)
 bias=c/pd.DataFrame(c).rolling(90).mean().to_numpy();x=np.arange(20)-9.5;out=np.full((len(pos),c.shape[1]),np.nan)
 for i,t in enumerate(pos):
  a=bias[t-20:t];out[i]=(x[:,None]*(a/a[0])).sum(axis=0)/(x*x).sum()
 return [gate[pos],out]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='source fixed mean12 and bias90/20 before evaluation')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:32] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawOHLC_prefix_meanexit',passed=True))
 obs=0
 for i in [35,79]:
  for j in range(32):
   t=pos[i];a=pd.Series(small['close'][:t,j].astype(float));bias=(a/a.rolling(90).mean()).iloc[-20:]
   if np.isfinite(bias).all():
    np.testing.assert_allclose(whole[1][i,j],np.polyfit(np.arange(20),bias/bias.iloc[0],1)[0],atol=1e-8);obs+=1
 checks.append(dict(test='literal_completed110closes_bias_normalization_polyfit',observations=obs,passed=True))
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC)})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED112',flush=True)
if __name__=='__main__':main()
