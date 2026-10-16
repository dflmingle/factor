from pathlib import Path
import json,sys,itertools
OUT=Path(__file__).resolve().parent;HERE=OUT.parents[0]/'top50-20261013/search_v1';sys.path.insert(0,str(HERE))
from grammar import Expr,field,const,op,paths,replace,formula
from engine import Market
from evidence import read,extract,PUBLIC
import objective,verify

def find_formula(base,j,target):
 import residual_refine
 for x,_ in residual_refine.variants(base[j],None):
  if formula(x)==target:return x
 if target=='MARKET_CAP':return field('cap')
 raise ValueError(target)
def main():
 src=json.load(open(OUT.parent/'star-coin-alpha-transfer-20261016-v1'/'best.json'));base=tuple(Expr.from_json(x) for x in src['pool'])
 c=field('close');ret=op('sub',op('div',c,op('delay',c,window=1)),const(1));v18=op('rank',op('ts_std',ret,window=18));v20=op('rank',op('ts_std',ret,window=20))
 m03=op('zscore',base[0]); m02=base[8]
 # M02 best holding variant: change the final SP branch window 20 ->18
 for path,node in paths(m02):
  if node.op=='ts_kurt' and 'sp' in node.fields: m02=replace(m02,path,Expr(node.op,node.args,18));break
 variants=[('v20+m03z',[(0,m03),(1,v20)]),('v20+m02w18',[(1,v20),(8,m02)]),('v20+m03z+m02w18',[(0,m03),(1,v20),(8,m02)]),('v18+m03z+m02w18',[(0,m03),(1,v18),(8,m02)])]
 market=Market();market.cache_dir=OUT/'joint_panels';market.cache_dir.mkdir(exist_ok=True);target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0];evidence=extract(target,market);e=objective.Objective(market,evidence,OUT/'joint_eval',base);e.enable_A();rows=[]
 for name,changes in variants:
  pool=list(base)
  for j,x in changes:pool[j]=x
  row=e.evaluate(tuple(pool),True);checked=verify.verify(e,row);rows.append({'name':name,'formulas':[formula(x) for x in pool],'score':row['score'],'acceptance':checked['acceptance']['actual'],'checks':row['checks'],'months':row['months']})
 (OUT/'joint_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps([{'name':r['name'],'score':r['score'],'min_overlap':r['acceptance']['min_holdings_overlap'],'mean_overlap':r['acceptance']['mean_holdings_overlap'],'rankic_mae':r['acceptance']['rankic_mae'],'raw_c':r['acceptance']['raw_c_relative'],'points':r['acceptance']['points_relative']} for r in rows],ensure_ascii=False))
if __name__=='__main__':main()
