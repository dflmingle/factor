from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[3]; V2=ROOT/'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'; SEARCH=ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1';sys.path[:0]=[str(SEARCH),str(V2)]
from holdings_diff import build_pool
from grammar import Expr,field,op,paths,replace,formula
OUT=Path(__file__).resolve().parent
base=list(build_pool()); base_json=[x.json() for x in base]
base_src=(OUT/'star_coin_frozen_pool.py').read_text()

def render(name,pool,weights):
 src=base_src
 a=src.index('TREES = ');b=src.index('\nDIRECTIONS = ',a);c=src.index('\n\n\ndef _cast',b)
 dirs='DIRECTIONS = '+repr([-1.,-1.,-1.,-1.,1.,-1.,-1.,-1.,-1.,1.])
 src=src[:a]+'TREES = '+repr([x.json() for x in pool])+'\n'+dirs+'\nWEIGHTS = '+repr(weights)+'\n'+src[c:]
 src=src.replace('class StarCoinFrozenPoolFactor',f'class {name}Factor')
 src=src.replace('composite += np.float32(direction) * normalized','composite += np.float32(direction) * np.float32(weight) * normalized')
 src=src.replace('for tree, direction in zip(TREES, DIRECTIONS):','for tree, direction, weight in zip(TREES, DIRECTIONS, WEIGHTS):')
 return src
# candidate 02: X01 window 15
p2=list(base); 
for path,node in paths(p2[7]):
 if node.op=='ts_mean' and 'open' in node.fields: p2[7]=replace(p2[7],path,Expr(node.op,node.args,15));break
# candidate 03: X01 double seat weight
p3=list(base);w3=[1.0]*10;w3[7]=2.0
# candidate 04: downweight M03/V01/M02 to half, all remaining seats one
p4=list(base);w4=[0.5 if i in [0,1,8] else 1.0 for i in range(10)]
rows=[('F-SCH1016-02','StarCoinOpen15',p2,[1.0]*10,'X01 open mean window 15; local five-snapshot Top20 mean 13.4 vs 13.2 control, latest 10 vs 9.'),('F-SCH1016-03','StarCoinX01Weight2',p3,w3,'Double X01 seat weight; local five-snapshot Top20 mean 13.6, latest 12 vs 9 control.'),('F-SCH1016-04','StarCoinStableWeights',p4,w4,'Half-weight M03/V01/M02; local full-hold overlap mean 87.95% and latest Top20 10/20.')]
lines=[];manifest=[]
for cand,cls,pool,w,reason in rows:
 path=OUT/(cand.lower()+'.py');src=render(cls,pool,w);path.write_text(src);lines.append(f'{cand} ~ {path.name} ~ 1');manifest.append({'name':cand,'path':path.name,'formulas':[formula(x) for x in pool],'weights':w,'directions':[-1,-1,-1,-1,1,-1,-1,-1,-1,1],'reason':reason,'sha256':hashlib.sha256(src.encode()).hexdigest()})
(OUT/'candidates_opt.txt').write_text('\n'.join(lines)+'\n');(OUT/'optimization_candidates.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(manifest,ensure_ascii=False))
