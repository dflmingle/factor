"""RSRS600 and macro strategy daily helpers, separately from missing market data."""
import json
import numpy as np
import pandas as pd
from numba import njit
import quant_corpus_local_20261012 as q
from quant_corpus_offline_batch_20261012 import run
from quant_corpus_continue_20261013 import spec,audit,simultaneous_residual
from quant_corpus_sweep_20261013 import tie_diagnostic
from quant_strategy_factor_catalog_20261012 import read_text
A='quant/2024年度精选策略2/75.ETF轮动策略-入门2.0.txt'
B='quant/2023年度精选策略/29.价值成长轮动策略.txt'
C='quant/2024年度精选策略1/21.一种宏观数据的中长线策略，年化15%，最大回撤9%.txt'
D='quant/量化策略/量化策略/实盘2026/Ptrade/pt版02小市值技术过滤策略.txt'
OUT=q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source108-20261013'
COMMON='proxy: stock OHLC replaces singleHS300 index, daily priorcompletedbars, rolling600 beta standardization ddof0; source initialization removesone initial slope and skips one day, unknown original start state not recoverable, rollingseedproxy disclosed. Fullstrategy/ETF/northbound andindex data absent.'
SPECS=[
 spec('rsrs75_beta18_z600_r2_priorclose','十八斜率六百标准分乘拟合度',A,'lag1(z600(beta18)*R2_18)',COMMON+' Fixed sourceN18/M600; neither rightdev nor WLS.'),
 spec('rsrs75_not_sell_ma20gap5','RSRS与五日均线斜率非卖出分支',A,'I(NOT(rsrs_score<-.7 AND completedMA20<MA20_lag5))',COMMON+' Actual KEEP adjustspositions just asBUY, so Boolean nonSELL, not persistentBUYstate; large ties audited.'),
 spec('rsrs29_orbuy_andsell_state','或买且卖双门状态',B,'state=1 if rsrs>.7 OR completedMA20>MA20_lag3; state=0 if rsrs<-.7 AND completedMA20<MA20_lag3; else hold',COMMON+' Explicit stock state adaptation initialized0 at first finite controls; source BUYusesOR, not AND; value/growth vendorfinanciallegs not reproduced.'),
 spec('macro21_rightside_ma_stack','宏观策略右侧均线纯技术核',C,'I(MA5>MA10>MA20>MA30>lag1MA30)',
 'proxy: source14:55 prices replaced dailyclose, fullAstockextension of indexhelper only; PMI quadratic13month/inventory state and priormode gate omitted explicitly. Binaryties audited, not fullmacrostrategy'),
 spec('macro21_no_sell_cross_above120','宏观策略百二十均线上死叉退出核',C,'-I(C>MA120 AND lag1MA5>lag1MA20 AND MA5<MA20)',
 'proxy: source technicalsell conjunction independentdaily stockextension; source only sells inmode2 and holdsETF, mode/cashflow state unavailable and omitted. Ties audited'),
 spec('ptrade02_size_above_prevMA5','技术过滤小市值代理',D,'-total_mv where C>lag1MA5',
 'proxy: source previous5closes mean, qfq actuallyrequested despite comment raw; dailyclose replaces14:55 snapshot. FullA/total_mv substitutes399101components/smallestfloatcap30then3, explicitly expanded membership >=100. Qualifiedbenchmark, not source3stockportfolio')]
SPECS[-1]['gated']=True

@njit(cache=True)
def persistent(rs,gap):
 out=np.full(rs.shape,np.nan)
 for j in range(rs.shape[1]):
  state=0.
  for t in range(rs.shape[0]):
   if not np.isfinite(rs[t,j]) or not np.isfinite(gap[t,j]):continue
   if rs[t,j]>.7 or gap[t,j]>0:state=1.
   elif rs[t,j]<-.7 and gap[t,j]<0:state=0.
   out[t,j]=state
 return out

def values(f,pos):
 c=f['close'].astype(float);h=pd.DataFrame(f['high'].astype(float));l=pd.DataFrame(f['low'].astype(float))
 cov=h.rolling(18).cov(l);vl=l.rolling(18).var();vh=h.rolling(18).var();beta=cov/vl;r2=cov*cov/(vl*vh)
 z=(beta-beta.rolling(600).mean())/beta.rolling(600).std(ddof=0);rs=(z*r2).shift(1).to_numpy()
 ma={n:pd.DataFrame(c).rolling(n).mean().to_numpy() for n in [5,10,20,30,120]}
 g3=q.delay(ma[20])-q.delay(ma[20],4);g5=q.delay(ma[20])-q.delay(ma[20],6)
 valid=np.isfinite(rs)&np.isfinite(g5)
 nonsell=np.where(valid,(~((rs<-.7)&(g5<0))).astype(float),np.nan)
 stack=np.where(np.isfinite(q.delay(ma[30])),((ma[5]>ma[10])&(ma[10]>ma[20])&(ma[20]>ma[30])&(ma[30]>q.delay(ma[30]))).astype(float),np.nan)
 cross=(c>ma[120])&(q.delay(ma[5])>q.delay(ma[20]))&(ma[5]<ma[20]);nosell=np.where(np.isfinite(ma[120]),-cross.astype(float),np.nan)
 gate=np.where(c>q.delay(ma[5]),-f['cap'],np.nan)
 return [rs[pos],nonsell[pos],persistent(rs,g3)[pos],stack[pos],nosell[pos],gate[pos]]

def main():
 OUT.mkdir(exist_ok=True);plan=dict(specs=SPECS,rule=q.ALIGNMENT_RULE_VERSION,platform_compute=0,selection='six actual technical helpers fixed before evaluation; partialadaptations andseedgaps explicit')
 p=OUT/'frozen_plan.json'
 if p.exists() and json.loads(p.read_text())!=plan:raise ValueError('frozen mismatch')
 q.dump(p,plan)
 if (OUT/'audit_complete.json').exists():return
 cal,stocks,f=q.load_market();grid=pd.read_pickle(q.OUT/'signal_panels.pkl')['dates'];pos=cal.get_indexer(grid);small={k:v[:,:32] for k,v in f.items()};whole=values(small,pos);checks=[]
 for n in [35,79]:
  stop=pos[n-1]+1;cut=values({k:v[:stop] for k,v in small.items()},pos[:n])
  for sp,a,b in zip(SPECS,whole,cut):
   np.testing.assert_allclose(a[:n],b,equal_nan=True,atol=1e-8);checks.append(dict(key=sp['key'],test='rawOHLC_prefix_persistentstate',stop=stop,passed=True))
 for i in [35,79]:
  t=pos[i]
  for j in range(12):
   hh=small['high'][:,j].astype(float);ll=small['low'][:,j].astype(float);bs=[]
   if not np.isfinite(hh[t-617:t]).all() or not np.isfinite(ll[t-617:t]).all():continue
   for end in range(t-600,t):
    xx=ll[end-17:end+1];yy=hh[end-17:end+1];s,b=np.polyfit(xx,yy,1);bs.append(s)
   xx=ll[t-18:t];yy=hh[t-18:t];r=np.corrcoef(xx,yy)[0,1]**2;ref=(bs[-1]-np.mean(bs))/np.std(bs)*r
   np.testing.assert_allclose(whole[0][i,j],ref,atol=1e-6,rtol=1e-6)
   cc=small['close'][:,j].astype(float);ma={n:cc[t-n+1:t+1].mean() for n in [5,10,20,30,120]}
   expected=float(ma[5]>ma[10]>ma[20]>ma[30]>cc[t-30:t].mean())
   np.testing.assert_allclose(whole[3][i,j],expected)
 checks.append(dict(test='independent600_literal_polyfits_and_source_currentbar_ma_slices',passed=True))
 synthetic=persistent(np.array([[.8],[-.8],[0.],[-.8]]),np.array([[-1.],[1.],[0.],[-1.]]));np.testing.assert_array_equal(synthetic.ravel(),[1,1,1,0])
 checks.append(dict(test='sourceORbuy_branch_priority_KEEP_and_ANDsell',passed=True))
 q.dump(OUT/'source_evidence.json',{src:read_text(q.ROOT/src) for src in [A,B,C,D]})
 run(OUT,SPECS,values(f,pos),cal,stocks,f,checks,dict(statistics='exploratory no untouched OOS',fidelity='only dailyhelpers, sourceindexandportfolio absent'),residualizer=lambda x,s,r:simultaneous_residual(x,[s,r]))
 tie_diagnostic(OUT,cal,stocks,f);audit(OUT,cal,stocks,f);q.dump(OUT/'audit_complete.json',dict(completed=True,platform_compute=0));print('FINISHED108',flush=True)
if __name__=='__main__':main()
