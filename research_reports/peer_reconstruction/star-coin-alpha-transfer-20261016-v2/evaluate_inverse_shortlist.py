from pathlib import Path
import json,sys
OUT=Path(__file__).resolve().parent; HERE=OUT.parents[0]/'top50-20261013/search_v1';sys.path.insert(0,str(HERE))
from grammar import Expr,formula
from engine import Market
from evidence import read,extract,PUBLIC
import objective,verify

def main():
    src=json.load(open(OUT.parent/'star-coin-alpha-transfer-20261016-v1'/'best.json'));base=tuple(Expr.from_json(x) for x in src['pool'])
    short=json.load(open(OUT/'holdings_shortlist.json')); market=Market();market.cache_dir=OUT/'inverse_panels';market.cache_dir.mkdir(exist_ok=True)
    target=[t for t in read(PUBLIC/'targets.json') if t['rank']==8][0];e=objective.Objective(market,extract(target,market),OUT/'inverse_eval',base);e.enable_A(); rows=[]
    for s in short:
        if s['seat'] not in (0,8):continue
        x=Expr.from_json(next(p for p in (json.loads((OUT/'heuristic_results.json').read_text())['baseline']['pool']) if False)) if False else None
        # recover AST by matching formula against generated candidates through a small formula map
        import residual_refine
        found=None
        for y,reason in residual_refine.variants(base[s['seat']],e.seats[s['seat']]):
            if formula(y)==s['formula']: found=y;break
        if found is None:
            # Recreate the simple market-cap candidate if it is present.
            from grammar import field
            if s['formula']=='MARKET_CAP': found=field('cap')
        if found is None:continue
        pool=list(base);pool[s['seat']]=found;row=e.evaluate(tuple(pool),True);checked=verify.verify(e,row)
        rows.append({'seat':s['seat'],'formula':s['formula'],'inverse':s['inverse'],'score':row['score'],'acceptance':checked['acceptance']['actual'],'checks':row['checks'],'months':row['months']})
    (OUT/'inverse_shortlist_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps([{'seat':r['seat'],'formula':r['formula'],'score':r['score'],'min_overlap':r['acceptance']['min_holdings_overlap'],'mean_overlap':r['acceptance']['mean_holdings_overlap'],'rankic_mae':r['acceptance']['rankic_mae'],'raw_c':r['acceptance']['raw_c_relative'],'points':r['acceptance']['points_relative']} for r in rows],ensure_ascii=False))
if __name__=='__main__':main()
