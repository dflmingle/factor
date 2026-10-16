"""Source55 public helper, causal detection-time fullA chart-pattern proxies.
Never executes corpus/imported author code. Math independently implemented.
"""
import json,time,hashlib
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from scipy.optimize import fmin
from scipy.signal import argrelmax,argrelmin
from statsmodels.nonparametric.kernel_regression import KernelReg
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略2/55.【复现】技术指标形态识别.txt'
DEP=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012/external_dependency_evidence_20261013/technical_analysis_patterns_original.py'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source85-numericalguard-20261013'
NAMES=['HS','IHS','BTOP','BBOT','TTOP','TBOP','RTOP','RBOT']
SPECS=[spec('pattern35_cvll_'+n.lower(),n+'三十五日因果形态事件',SRC,
 'I(any five-extrema '+n+' priority match in last35; localLinear gaussian cv_ls bandwidth*.3, offset1)',
 'proxy: recovered public original math; event assigned to CURRENT detection day, never extrema end date. Repeated per-window events allowed for stock adaptation; original global first/reset120 event-bookkeeping NOT reproduced; index/industry eventstudy -> fullA; binary ties audited; consecutive smoothed differences<=1e-10*meanPrice excluded as numerical ambiguity proxy; high-event direction is frozen exploratory, not claimed source portfolio') for n in NAMES]
SPECS += [spec('pattern35_cvll_'+n.lower()+'_margin',n+'三十五日最新五极点连续余量',SRC,
 'dimensionless minimum inequality margin for latest5 mapped extrema: '+n,
 'proxy: NEW continuous geometric extension of exact source inequalities; no category priority for margins; recent5 only, 35bar causal cv_ls localLinear, not original eventstudy; numerical nearflat smoothing excluded rather than ranked; HS/TTOP bearish margin negated, IHS/BBOT/BTOP/TBOP positive, source RTOP continuation positive and RBOT negative fixed ex ante') for n in NAMES]

@njit(cache=True)
def ll(y,h,loo):
 n=len(y);out=np.empty(n);w=np.exp(-.5*(np.arange(n)/h)**2)
 for i in range(n):
  s0=s1=s2=v0=v1=0.
  for j in range(n):
   if loo and i==j:continue
   d=j-i;ww=w[abs(d)];s0+=ww;s1+=ww*d;s2+=ww*d*d;v0+=ww*y[j];v1+=ww*d*y[j]
  det=s0*s2-s1*s1
  emax=(s0+s2+np.sqrt((s0-s2)**2+4*s1*s1))/2
  if emax==0:out[i]=0.
  elif det/emax<=emax*1e-15:out[i]=(s0*v0+s1*v1)/(emax*emax)
  else:out[i]=(s2*v0-s1*v1)/det
 return out

def cv(h,y):
 if not np.isfinite(h[0]) or abs(h[0])<1e-7:return np.inf
 p=ll(y,h[0],True)
 if not np.isfinite(p).all():return np.inf
 return np.mean((y-p)**2)

def smooth(y):
 n=len(y);h0=1.06*np.std(np.arange(n))*n**(-.2)
 h=float(fmin(cv,[h0],args=(y,),maxiter=1000,maxfun=1000,disp=False)[0])
 s=ll(y,.3*h,False)
 return s,h,False

def ambiguous(s):
 return np.any(abs(np.diff(s))<=1e-10*np.mean(abs(s)))

def extrema(y,s):
 loc=[]
 for kind,fun in [(1,argrelmax),(-1,argrelmin)]:
  for i in fun(s)[0]:
   lo=max(0,i-1);hi=min(len(y),i+2);z=y[lo:hi]
   loc.append(lo+(np.argmax(z) if kind==1 else np.argmin(z)))
 return np.sort(np.unique(loc))

def margins(e):
 a,b,c,d,f=e;avg1=(a+f)/2;avg2=(b+d)/2;g1=np.array([a,c,f]);g2=np.array([b,d]);scale=np.mean(e)
 hs=min(a-b,c-a,c-f,.015*avg1-abs(a-avg1),.015*avg1-abs(f-avg1),.015*avg2-abs(b-avg2),.015*avg2-abs(d-avg2))/scale
 ihs=min(b-a,a-c,f-c,.015*avg1-abs(a-avg1),.015*avg1-abs(f-avg1),.015*avg2-abs(b-avg2),.015*avg2-abs(d-avg2))/scale
 bt=min(a-b,c-a,f-c,b-d)/scale;bb=min(b-a,a-c,c-f,d-b)/scale
 tt=min(a-np.max(e[1:]),a-c,c-f,d-b)/scale;tb=min(np.min(e[1:])-a,c-a,f-c,b-d)/scale
 rt=min((a-np.max(e[1:]))/scale,.0075-np.max(abs(g1/g1.mean()-1)),.0075-np.max(abs(g2/g2.mean()-1)),(g1.min()-g2.max())/scale)
 rb=min((np.min(e[1:])-a)/scale,.0075-np.max(abs(g1/g1.mean()-1)),.0075-np.max(abs(g2/g2.mean()-1)),(g2.min()-g1.max())/scale)
 return np.array([hs,ihs,bt,bb,tt,tb,rt,rb])

def categories(e):
 a,b,c,d,f=e;av1=(a+f)/2;av2=(b+d)/2;g1=np.array([a,c,f]);g2=np.array([b,d])
 cond=[a>b and c>a and c>f and all(.985*av1<=x<=1.015*av1 for x in [a,f]) and all(.985*av2<=x<=1.015*av2 for x in [b,d]),
 a<b and c<a and c<f and all(.985*av1<=x<=1.015*av1 for x in [a,f]) and all(.985*av2<=x<=1.015*av2 for x in [b,d]),
 a>b and a<c<f and b>d,a<b and a>c>f and b<d,
 np.argmax(e)==0 and a>c>f and b<d,np.argmin(e)==0 and a<c<f and b>d,
 np.argmax(e)==0 and np.all(abs(g1/g1.mean()-1)<=.0075) and np.all(abs(g2/g2.mean()-1)<=.0075) and g1.min()>g2.max(),
 np.argmin(e)==0 and np.all(abs(g1/g1.mean()-1)<.0075) and np.all(abs(g2/g2.mean()-1)<.0075) and g2.min()>g1.max()]
 return next((i for i,z in enumerate(cond) if z),-1)

def one(y):
 if not np.isfinite(y).all() or (y<=0).any():return np.full(16,np.nan),np.nan,False
 s,h,fallback=smooth(y)
 if ambiguous(s):return np.full(16,np.nan),h,False
 loc=extrema(y,s);event=np.zeros(8);margin=np.full(8,np.nan)
 for z in range(len(loc)-4):
  cat=categories(y[loc[z:z+5]])
  if cat>=0:event[cat]=1
 if len(loc)>=5:margin=margins(y[loc[-5:]])*np.array([-1,1,1,1,-1,1,1,-1])
 return np.r_[event,margin],h,fallback

def chunk(ys):
 return [one(y) for y in ys]

def independent_checks(c,pos):
 rng=np.random.default_rng(20261013);checks=[];pairs=[]
 for t in pos[::19]:
  for j in range(min(64,c.shape[1])):
   y=c[t-34:t+1,j].astype(float)
   if np.isfinite(y).all() and np.std(y)>0:pairs.append(y)
 pairs=pairs[:32]+[10+np.cumsum(rng.normal(0,.1,35)) for _ in range(8)]
 for y in pairs:
  fast,h,_=smooth(y);kr=KernelReg(y,np.arange(35),var_type='c',reg_type='ll',bw='cv_ls');kr.bw*=.3;ref=kr.fit(np.arange(35))[0]
  np.testing.assert_allclose(fast,ref,rtol=2e-5,atol=2e-5)
  if not ambiguous(fast) and not ambiguous(ref):assert np.array_equal(extrema(y,fast),extrema(y,ref)),(h,kr.bw)
  for hh in [1.,3.,7.,20.]:
   kr0=KernelReg(y,np.arange(35),var_type='c',reg_type='ll',bw=[hh])
   np.testing.assert_allclose(cv([hh],y),float(kr0.cv_loo(np.array([hh]),kr0._est_loc_linear)),rtol=1e-9,atol=1e-9)
 checks.append(dict(test='independent_statsmodels_cv_ls_localLinear_smoothing_and_exact_extrema',windows=len(pairs),passed=True))
 # Prefix slicing never includes bars beyond detection day.
 for t in pos[::39]:
  for j in range(8):
   a=one(c[t-34:t+1,j].astype(float))[0];b=one(c[:t+1,j][-35:].astype(float))[0]
   np.testing.assert_allclose(a,b,equal_nan=True)
 checks.append(dict(test='daily_raw_prefix_rebuild_at_actual_detectiondate_not_patternendpoint',passed=True))
 # Primitive definitions independently checked against handwritten cases.
 cases=[([10,9,11,9,10],0),([10,11,9,11,10],1),([10,8,12,7,14],2),([8,10,7,12,6],3),([14,7,12,8,10],4),([6,12,8,10,9],5)]
 for e,k in cases:assert categories(np.array(e,dtype=float))==k
 checks.append(dict(test='eight_source_inequality_priority_handwritten_pattern_cases',cases=len(cases),passed=True))
 return checks

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,external_helper_sha256=hashlib.sha256(DEP.read_bytes()).hexdigest(),selection='all8 categories and8 continuous adaptations fixed before returns; no outcome sign selection')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);c=f['close']
 checks=independent_checks(c,pos);q.dump(OUT/'verification.json',checks)
 q.dump(OUT/'source_evidence.json',{SRC:read_text(q.ROOT/SRC),'external_dependency':str(DEP.relative_to(q.ROOT)),'causality':'source records extrema endpoints although smoothing sees later bars; assign detection-date to repair; original strategy/eventstudy not claimed'})
 cache=OUT/'kernel_values.pkl'
 if cache.exists():vals=pd.read_pickle(cache)
 else:
  vals=np.full((16,len(pos),len(stocks)),np.nan,dtype=np.float32);fallback=0;t0=time.time()
  with ProcessPoolExecutor(max_workers=6) as pool:
   for i,t in enumerate(pos):
    snap=OUT/f'checkpoint_{i:03}.npz'
    if snap.exists():
     d=np.load(snap);vals[:,i]=d['values'];continue
    ys=c[t-34:t+1].T.astype(float);parts=[ys[z:z+128] for z in range(0,len(ys),128)]
    rr=[r for block in pool.map(chunk,parts) for r in block];vals[:,i]=np.array([r[0] for r in rr]).T
    fallback+=sum(r[2] for r in rr);np.savez_compressed(snap,values=vals[:,i],bandwidth=np.array([r[1] for r in rr]))
    print('PATTERN_SIGNAL',i+1,len(pos),'seconds',round(time.time()-t0,1),'fallback',fallback,flush=True)
  pd.to_pickle(vals,cache)
 run(OUT,SPECS,list(vals),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='actual public pattern math and detectiontime repair; repeatedwindow/continuous proxies disclosed',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED85',flush=True)
if __name__=='__main__':main()
