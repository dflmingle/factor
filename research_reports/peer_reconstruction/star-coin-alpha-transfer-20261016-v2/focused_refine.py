from pathlib import Path
import json,sys,itertools
import numpy as np
OUT=Path(__file__).resolve().parent;HERE=OUT.parents[0]/'top50-20261013/search_v1';sys.path.insert(0,str(HERE))
from grammar import Expr,field,const,op,paths,replace,formula
from engine import Market
from evidence import read,extract,PUBLIC
import objective,verify
import holdings_heuristic as hh

def main():
 src=json.load(open(OUT.parent/'star-coin-alpha-transfer-20261016-v1'/'best.json'));base=list(Expr.from_json(x) for x in src['pool'])
 c=field('close');ret=op('sub',op('div',c,op('delay',c,window=1)),const(1));
 # v2 seed: V01 close return 20, M02 SP kurt 18, BM light shape mixture.
 base[1]=op('rank',op('ts_std',ret,window=20)); m02=base[8]
 for path,node in paths(m02):
  if node.op=='ts_kurt' and 'sp' in node.fields:m02=replace(m02,path,Expr(node.op,node.args,18));break
 base[8]=m02;base[4]=op('add',op('mul',const(.975),op('zscore',field('bm'))),op('mul',const(.025),op('zscore',op('rank',field('bm')))))
 market=Market();market.cache_dir=OUT/'focused_panels';market.cache_dir.mkdir(exist_ok=True);target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0];e=objective.Objective(market,extract(target,market),OUT/'focused_eval',tuple(base));e.enable_A()
 # Candidate pools selected from holding inversion but evaluated around v2, not v1.
 m03={base[0]: 'v2 baseline'}
 for x,reason in hh.hand_variants(base[0],0).items(): m03[x]=reason
 m03={x:r for x,r in m03.items() if r in ('v2 baseline','M03 holdings inverse: cap/CFP shape','M03 holdings inverse: cap/CFP mean','M03 zscore cap/CFP')}
 m03=list(m03.items())
 # Keep structurally distinct first 10, plus baseline.
 seen=set();m03=[(x,r) for x,r in m03 if formula(x) not in seen and not seen.add(formula(x))][:12]
 m02={base[8]:'v2 baseline'}
 for x,reason in hh.hand_variants(base[8],8).items():m02[x]=reason
 m02=list(m02.items()); seen=set();m02=[(x,r) for x,r in m02 if formula(x) not in seen and not seen.add(formula(x))][:12]
 v01=[(op('rank',op('ts_std',ret,window=n)),f'V01 close-return {n}') for n in (18,19,20,21,22)]
 rows=[]
 for (x,rx),(y,ry), (v,rv) in itertools.product(m03,m02,v01):
  pool=list(base);pool[0]=x;pool[8]=y;pool[1]=v;row=e.evaluate(tuple(pool),True)
  if row.get('valid'):
   rows.append({'formula0':formula(x),'formula1':formula(v),'formula8':formula(y),'reasons':[rx,rv,ry],'score':row['score'],'acceptance':verify.verify(e,row)['acceptance']['actual'],'checks':row['checks']})
 rows.sort(key=lambda r:r['score'],reverse=True);(OUT/'focused_results.json').write_text(json.dumps(rows[:100],ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps([{'score':r['score'],'f1':r['formula1'],'f0':r['formula0'],'f8':r['formula8'],'min_overlap':r['acceptance']['min_holdings_overlap'],'mean_overlap':r['acceptance']['mean_holdings_overlap'],'raw_c':r['acceptance']['raw_c_relative'],'rankic':r['acceptance']['rankic_mae'],'points':r['acceptance']['points_relative']} for r in rows[:15]],ensure_ascii=False))
if __name__=='__main__':main()
