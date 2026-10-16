from pathlib import Path
import json,sys
OUT=Path(__file__).resolve().parent
HERE=OUT.parents[0]/'top50-20261013/search_v1'
sys.path.insert(0,str(HERE))
from grammar import Expr
from engine import Market
from evidence import read,extract,PUBLIC
import objective
import verify

def main():
    x=json.load(open(OUT/'heuristic_results.json')); best=x['best']['row']; pool=tuple(Expr.from_json(p) for p in best['pool'])
    market=Market(); market.cache_dir=OUT/'verify_panels'; market.cache_dir.mkdir(exist_ok=True)
    target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0]
    e=objective.Objective(market,extract(target,market),OUT/'final',pool); e.enable_A()
    row=e.evaluate(pool,True); checked=verify.verify(e,row)
    (OUT/'verified_best.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (OUT/'verification_status.json').write_text(json.dumps(checked.get('acceptance',{}),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'score':row.get('score'),'acceptance':checked.get('acceptance'),'boards':checked.get('boards')},ensure_ascii=False))
if __name__=='__main__':main()
