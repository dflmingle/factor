from pathlib import Path
import hashlib, json, sys
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEARCH = ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1'
V2 = ROOT/'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2'
sys.path[:0] = [str(SEARCH), str(V2)]
from grammar import Expr
from engine import Market, standardize, Interpreter
from evidence import read, extract, PUBLIC
import objective

def main():
    manifest=json.loads((HERE/'manifest.json').read_text())
    trees=tuple(Expr.from_json(x) for x in manifest['trees'])
    dirs=np.array([-1,-1,-1,-1,1,-1,-1,-1,-1,1.],float)
    target=next(t for t in read(PUBLIC/'targets.json') if t['rank']==8)
    market=Market(); evidence=extract(target,market)
    lifecycle=objective.Objective(market, evidence, HERE/'bm_top20_lifecycle',
                                  tuple(trees))
    variants={'baseline_pit_exc_latest':None,'bm_equity_inc':'bm_equity_inc.npy',
              'bm_equity_exc_annual':'bm_equity_exc_annual.npy','bm_equity_inc_annual':'bm_equity_inc_annual.npy',
              'bm_bps_raw':'bm_bps_raw.npy','baseline_numeric_mask':'__numeric_mask__'}
    diag=SEARCH/'financial_proxy_diagnostic_v1'
    rows=[]
    for name,fn in variants.items():
        fields=dict(market.fields)
        if fn is not None and fn != '__numeric_mask__': fields['bm']=np.load(diag/fn)
        engine=Interpreter(fields)
        panels=[]
        for expr in trees:
            key=hashlib.sha256(expr.key().encode()).hexdigest()
            panel_name = 'baseline_pit_exc_latest' if fn == '__numeric_mask__' else name
            path=HERE/'bm_sensitivity_panels'/panel_name/(key+'.npy')
            panels.append(np.load(path,mmap_mode='r'))
        z=[]
        for panel,d in zip(panels,dirs):
            # panels are recent_pos; masks below are signal-date slices.
            z.append(panel)
        z=np.asarray(z)
        top20=[]; all20=[]
        for rec in evidence['records']:
            sig=pd.Timestamp(rec['signal']); p=market.cal.get_loc(sig); ri=market.panel_map[sig]
            if fn == '__numeric_mask__':
                mask=np.isfinite(fields['cap'][p])&(fields['cap'][p]>0)&np.isfinite(fields['turnover'][p])
                mask &= ~((fields['volume'][p]<=0)|(fields['amount'][p]<=0)|
                          np.isclose(fields['high'][p],fields['low'][p],rtol=1e-8,atol=1e-8))
            else:
                mask=market.competition_mask[p]
            # only BM-dependent tree (leg 5) needs recalculation; other panels are shared.
            if fn is not None:
                expr=trees[4]; native=engine.evaluate(expr)[market.recent_pos]
                z[4]=native
            active=lifecycle.active[:, lifecycle.index[sig]]
            legs=np.asarray([standardize(z[k,ri:ri+1,:],mask[None,:])[0]*dirs[k]
                             for k in range(len(trees))])
            legs[~active,:]=0.0
            # Match Objective: a missing active leg makes the composite missing;
            # do not treat it as a zero contribution.
            comp=np.sum(legs,axis=0)/max(int(active.sum()),1)
            ids=np.flatnonzero(mask & np.isfinite(comp)); order=ids[np.argsort(comp[ids],kind='stable')]
            peer20={x['symbol'] for x in rec['rows'][:20]}; peerall={x['symbol'] for x in rec['rows']}
            got20=[str(market.stocks[j]) for j in order[-20:]]
            gotall=[str(market.stocks[j]) for j in order[-int(np.ceil(len(order)/10)):]]
            top20.append(len(set(got20)&peer20)); all20.append(len(set(gotall)&peerall)/len(peerall))
        rows.append({'name':name,'top20_overlap_path':top20,'mean_top20_overlap':float(np.mean(top20)),
                     'latest_top20_overlap':int(top20[-1]),'mean_full_holdings_overlap':float(np.mean(all20)),
                     'latest_full_holdings_overlap':float(all20[-1])})
    out={'purpose':'BM proxy sensitivity using frozen equal-weight pool; local diagnostic only','rows':rows}
    (HERE/'bm_top20_compare.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()
