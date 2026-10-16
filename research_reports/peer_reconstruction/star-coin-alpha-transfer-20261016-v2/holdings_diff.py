from pathlib import Path
import json,sys
import numpy as np,pandas as pd
OUT=Path(__file__).resolve().parent; HERE=OUT.parents[0]/'top50-20261013/search_v1';sys.path.insert(0,str(HERE))
from grammar import Expr,field,const,op,paths,replace,formula
from engine import Market
from evidence import read,extract,PUBLIC
import objective

def build_pool():
 src=json.load(open(OUT.parent/'star-coin-alpha-transfer-20261016-v1'/'best.json'));base=list(Expr.from_json(x) for x in src['pool'])
 c=field('close');ret=op('sub',op('div',c,op('delay',c,window=1)),const(1));base[1]=op('rank',op('ts_std',ret,window=20))
 m02=base[8]
 for path,node in paths(m02):
  if node.op=='ts_kurt' and 'sp' in node.fields: m02=replace(m02,path,Expr(node.op,node.args,18));break
 base[8]=m02
 return tuple(base)

def clean(x):
 if isinstance(x,float) and not np.isfinite(x): return None
 if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list): return [clean(v) for v in x]
 return x

def main():
 pool=build_pool(); market=Market();market.cache_dir=OUT/'diff_panels';market.cache_dir.mkdir(exist_ok=True)
 target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0];e=objective.Objective(market,extract(target,market),OUT/'diff_eval',pool);e.enable_A()
 legs=[e.leg(x,j)['z'] for j,x in enumerate(pool)]
 z=np.array(legs); out=[]
 for r in e.records:
  i=e.index[pd.Timestamp(r['signal'])]; active=np.flatnonzero(e.active[:,i]); composite=z[active,i].sum(axis=0)/len(active)
  ids=np.flatnonzero(e.mask[i]&np.isfinite(composite)); order=ids[np.argsort(composite[ids],kind='stable')]; chosen=order[-int(np.ceil(len(order)/10)):]
  pub={row['symbol']:row for row in r['rows']}; pub_ids=set(pub); pred_ids=set(str(e.stocks[j]) for j in chosen)
  common=pub_ids&pred_ids; miss=sorted(pub_ids-pred_ids,key=lambda s:pub[s]['rank']); extra=sorted(pred_ids-pub_ids,key=lambda s:float(composite[e.stocks.get_loc(s)]),reverse=True)
  # disagreement names with composite and leg z contributions
  def detail(s):
   j=e.stocks.get_loc(s); vals=z[active,i,j]; return {'symbol':s,'public_rank':pub.get(s,{}).get('rank'),'public_composite':pub.get(s,{}).get('composite'),'local_composite':float(composite[j]),'legs':{str(k):float(vals[q]) for q,k in enumerate(active)}}
  out.append({'trade_date':r['trade'],'signal_date':r['signal'],'active_legs':active.tolist(),'public_count':len(pub_ids),'predicted_count':len(pred_ids),'common':len(common),'overlap':len(common)/len(pub_ids),'missing_public':len(miss),'extra_local':len(extra),'public_cutoff':min((row['composite'] for row in r['rows']),default=None),'local_cutoff':float(np.sort(composite[ids])[-len(chosen)]) if len(chosen) else None,'missing_details':[detail(s) for s in miss[:30]],'extra_details':[detail(s) for s in extra[:30]]})
 (OUT/'holdings_diff.json').write_text(json.dumps(clean(out),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 # compact markdown
 lines=['# star_coin_prediction 持仓差异拆解（v2候选）','', '候选使用 V01 收盘收益波动 20 日、M02 SP 峰度窗口 18 日，其他腿沿用 v1。','']
 for d in out:
  lines += [f"## {d['trade_date']}（信号日 {d['signal_date']}）",'',f"公开 {d['public_count']} 只，本地 {d['predicted_count']} 只，共同 {d['common']} 只，重合 {d['overlap']:.3%}；公开缺失 {d['missing_public']}，本地多出 {d['extra_local']}。",f"公开组合最低 composite={d['public_cutoff']:.6f}；本地 Top10% cutoff={d['local_cutoff']:.6f}",'','公开持仓中本地未选的前 10 只：']
  for x in d['missing_details'][:10]: lines.append(f"- {x['symbol']} 公共rank={x['public_rank']} public={x['public_composite']:.4f} local={x['local_composite']:.4f} legs={x['legs']}")
  lines += ['','本地选入但公开没有的前 10 只：']
  for x in d['extra_details'][:10]: lines.append(f"- {x['symbol']} local={x['local_composite']:.4f} legs={x['legs']}")
  lines += ['']
 (OUT/'holdings_diff.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps([{'trade':d['trade_date'],'overlap':d['overlap'],'missing':d['missing_public'],'extra':d['extra_local'],'public_cutoff':d['public_cutoff'],'local_cutoff':d['local_cutoff']} for d in out],ensure_ascii=False))
if __name__=='__main__':main()
