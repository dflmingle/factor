"""Recovered MTL feature kernels; historical values only, no future targets.
Pure author math is independently replayed only for scalar verification.
"""
import ast,json,hashlib
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_strategy_factor_catalog_20261012 import read_text
SRC='quant/2024年度精选策略1/91.【复现】多任务时序动量策略.txt'
DEP=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012/external_dependency_evidence_20261013/MTL_general.py'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source87-20261013'
HORIZONS=[5,21,63,126,252];NAMES=['Parkinson','GarmanKlass','RogersSatchell','YangZhang']
SPECS=[]
for name in NAMES:
 SPECS.append(spec('mtl_'+name.lower()+'21_low',name+'源码二十一日历史波动',SRC,'-'+name+'_21*sqrt252; literal author kernel',
 'proxy: recovered author historical auxiliary kernel at t used as exploratory stock ranking, NEVER source future21target; low-risk direction frozen before outcomes. YZ preserves var(log(C_t/O_(t-1))) typo, not standardYZ. 21OHLCobs, sample variances20pairs, no NaN0 fill; qfq fullA replaces4hfqETFs; float32inputs/float64 rolling aggregation numerical proxy. Not trained multi-task model'))
for n in HORIZONS:
 SPECS.append(spec(f'mtl_rawvol{n}_low',f'源码{n}价点历史低波动对照',SRC,f'-sampleSTD_{n-1}(logret1)*sqrt252',
 'proxy/control: exact author N-pricepoints gives N-1 logreturns; historical feature, no forward target; known lowvol axis, not new independent factor; no model'))
for n in HORIZONS:
 SPECS.append(spec(f'mtl_volvol{n}_21_low',f'{n}价点波动率的二十一日稳定性',SRC,f'-populationSTD21(sampleSTD_{n-1}(logret1)*sqrt252)',
 'proxy: actual author Raw_N_avg is STD21 not MEAN21 despite avg name; low fluctuation direction frozen; historical source input before causal rollingstandardization; no model/future21 target'))
for n in HORIZONS:
 SPECS.append(spec(f'mtl_volvol{n}_21_causalz_low',f'{n}价点波动稳定性因果标准分',SRC,f'-Z21sampleSTD(populationSTD21(sampleSTD_{n-1}(logret1)*sqrt252))',
 'proxy: literal author preparer_data causal21zscore applied to Raw_N_avg; low direction, no allsample/zero fill/futuretarget; fullA exploratory ranking, no trained model'))
for n in [1,5,21,126,252]:
 SPECS.append(spec(f'mtl_logret{n}_causalz',f'{n}日对数收益因果标准分',SRC,f'Z21sampleSTD(log(C/lag{n}C))',
 'proxy: literal actual MTL ln_return_N feature with rolling21sampleSTDzscore, frozen positive return direction; historical feature only, not author predicted model weights'))

def roll(x,n,kind='mean',ddof=1):
 r=pd.DataFrame(x).rolling(n,min_periods=n)
 return (r.mean() if kind=='mean' else r.std(ddof=ddof) if kind=='std' else r.var(ddof=ddof)).to_numpy()

def z21(x):
 sd=roll(x,21,'std');return np.divide(x-roll(x,21),sd,out=np.full_like(x,np.nan),where=sd>1e-12)

def kernels(f):
 c=f['close'];o=f['open'];h=f['high'];l=f['low']
 # The author casts all inputs float32 before taking logarithms.
 cc=np.log(c/q.delay(c));hl=np.log(h/l);co=np.log(c/o);ho=np.log(h/o);lo=np.log(l/o)
 rs=ho*(ho-co)+lo*(lo-co);k=.34/(1.34+22/20)
 yz=roll(np.log(o/q.delay(c)),20,'var')+k*roll(np.log(c/q.delay(o)),20,'var')+(1-k)*roll(rs,21)
 par=roll(hl**2,21)/(4*np.log(2));gk=roll(.5*hl**2-(2*np.log(2)-1)*co**2,21);rsv=roll(rs,21)
 # Must require the SAME full21 OHLC source window. No extra predecessor for YZ20pairs.
 valid=np.isfinite(np.stack([c,o,h,l])).all(axis=0).astype(float)
 vh=roll(valid,21)==1
 ohlc=[np.where(vh,-np.sqrt(np.where(v>=0,v,np.nan)*252),np.nan) for v in [par,gk,rsv,yz]]
 raws=[roll(cc,n-1,'std')*np.sqrt(252) for n in HORIZONS]
 vovs=[roll(x,21,'std',ddof=0) for x in raws]
 rets=[np.log(c/(c if n==0 else q.delay(c,n))) for n in [1,5,21,126,252]]
 return ohlc+[-x for x in raws]+[-x for x in vovs]+[-z21(x) for x in vovs]+[z21(x) for x in rets]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,dependency_sha256=hashlib.sha256(DEP.read_bytes()).hexdigest(),selection='all sourcekernels/horizons fixed exante; lowrisk/stability or positive-return directions; no scoreselection')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid)
 small={k:v[:,:32] for k,v in f.items()};whole=kernels(small);checks=[]
 for stop in [1200,len(cal)-31]:
  cut=kernels({k:v[:stop] for k,v in small.items()})
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:stop],b,equal_nan=True,rtol=1e-8,atol=1e-8)
  checks.append(dict(test='raw_OHLC_prefix_rolling_features_rebuild_no_future_targets',stop=stop,features=len(SPECS),passed=True))
 # Reviewed pure mathematical helper definitions; never import or run foreign module.
 tree=ast.parse(DEP.read_text());names={'calc_volatility','calc_parkinson_volatility','calc_garmanklass_volatility','calc_rogers_satchell_volatility','calc_yangzhang_volatility'}
 defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 assert len(defs)==5
 ns={'np':np,'N':252};exec(compile(ast.Module(body=defs,type_ignores=[]),str(DEP),'exec'),ns);obs=0
 for t in pos[::29]:
  for j in range(32):
   raw={name:small[field][t-20:t+1,j] for name,field in [('cprice','close'),('oprice','open'),('hprice','high'),('lprice','low')]}
   if not np.isfinite(np.stack(list(raw.values()))).all():continue
   for idx,name in enumerate(NAMES):
    fun=ns['calc_'+{'Parkinson':'parkinson','GarmanKlass':'garmanklass','RogersSatchell':'rogers_satchell','YangZhang':'yangzhang'}[name]+'_volatility']
    ref=-fun(**raw);np.testing.assert_allclose(whole[idx][t,j],ref,equal_nan=True,rtol=3e-6,atol=3e-7)
   ref=-ns['calc_volatility'](raw['cprice']);np.testing.assert_allclose(whole[5][t,j],ref,rtol=3e-6,atol=3e-7);obs+=1
 checks.append(dict(test='original_five_reviewed_pure_math_functions_independent_scalar_replay',observations=obs,passed=True,full_external_module_executed=False))
 q.dump(OUT/'source_evidence.json',{SRC: '\n'.join(l for l in read_text(q.ROOT/SRC).splitlines() if len(l)<700),'helper':str(DEP.relative_to(q.ROOT)),'precision':'helper float32prices, rolling aggregations float64; historical21auxiliary kernels only; forwardtarget never used','model_not_reproduced':'learned network weights and future auxiliary training targets are not trading-time features; model requires21day embargo, zero-fill exclusions and market adaptation'})
 cache=OUT/'daily_kernel_values.pkl'
 if cache.exists():vals=pd.read_pickle(cache)
 else:vals=kernels(f);pd.to_pickle(vals,cache)
 run(OUT,SPECS,[v[pos] for v in vals],cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='author historical math kernels, no learned multiasset model',residual_guard='ptp<=1e-7 invalid'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED87',flush=True)
if __name__=='__main__':main()
