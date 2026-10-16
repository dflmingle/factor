from pathlib import Path
import json,sys
OUT=Path(__file__).resolve().parent; HERE=OUT.parents[0]/'top50-20261013/search_v1';sys.path.insert(0,str(HERE))
from grammar import Expr,field,const,op,formula
from engine import Market
from evidence import read,extract,PUBLIC
import objective,verify

def main():
    src=json.load(open(OUT.parent/'star-coin-alpha-transfer-20261016-v1'/'best.json'));base=tuple(Expr.from_json(x) for x in src['pool'])
    c=field('close'); ret=op('sub',op('div',c,op('delay',c,window=1)),const(1))
    market=Market();market.cache_dir=OUT/'compare_panels';market.cache_dir.mkdir(exist_ok=True);target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0]
    e=objective.Objective(market,extract(target,market),OUT/'compare',base);e.enable_A(); rows=[]
    for n in (18,19,20,21,22):
        x=op('rank',op('ts_std',ret,window=n)); pool=list(base);pool[1]=x;row=e.evaluate(tuple(pool),True);checked=verify.verify(e,row)
        rows.append({'window':n,'formula':formula(x),'score':row['score'],'acceptance':checked['acceptance']['actual'],'checks':row['checks'],'months':row['months']})
    (OUT/'v01_window_compare.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps([{'window':r['window'],'score':r['score'],'min_overlap':r['acceptance']['min_holdings_overlap'],'mean_overlap':r['acceptance']['mean_holdings_overlap'],'rankic_mae':r['acceptance']['rankic_mae'],'raw_c':r['acceptance']['raw_c_relative'],'points':r['acceptance']['points_relative']} for r in rows],ensure_ascii=False))
if __name__=='__main__':main()
