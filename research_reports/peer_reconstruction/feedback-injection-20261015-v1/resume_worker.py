"""Resume the existing worker with isolated initialization and feedback receipts.

The original search, objective, candidates and scoring are unchanged. Financial
arrays are loaded read-only from the existing snapshot; startup metadata and
receipts are written only into the owning peer's directory.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import pickle
import sys

OUT=Path(__file__).resolve().parent
SEARCH=OUT.parent/'top50-20261013/search_v1'
sys.path.insert(0,str(SEARCH))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rank',type=int,choices=(6,27,36),required=True)
    args=parser.parse_args()
    import financial
    import engine
    import seven_suite
    import mcts
    policy=next(p for p in json.loads((OUT/'policies.json').read_text())['policies']if p['rank']==args.rank)
    workspace=SEARCH/'seven_methods_v1'/policy['pool_id']
    cached=financial.OUT
    specs={'balancesheet':['total_hldr_eqy_exc_min_int','total_assets','total_liab','total_cur_assets','total_cur_liab'],
           'fina_indicator':['roe','roic','grossprofit_margin','assets_yoy'],
           'income':['n_income_attr_p','total_revenue'],'cashflow':['n_cashflow_act']}
    def cached_financials(calendar,stocks):
        metadata=json.loads((cached/'metadata.json').read_text())
        expected=dict(calendar_start=str(calendar[0]),calendar_end=str(calendar[-1]),dates=len(calendar),
                      stocks=len(stocks),symbols=list(stocks),version='top50-pit-daily-ttm-proxy-v2-last-row-nan-preserved')
        if metadata!=expected:raise ValueError('Read-only financial snapshot does not match market')
        result={}
        for endpoint,columns in specs.items():
            for column in columns:
                key=f'{endpoint}.{column}'
                with (cached/(key+'.pkl')).open('rb')as stream:result[key]=pickle.load(stream)
        return result
    financial.rebuild=cached_financials
    financial.OUT=workspace/'financial_initialization'
    financial.OUT.mkdir(exist_ok=True)
    engine.HERE=workspace
    actual=mcts.round_search
    def with_receipt(e,grammar,rng,out,round_id,iterations=160):
        out=Path(out)
        reply_path=out/f'llm_reply_{round_id:03d}.json'
        request_path=out/f'llm_request_{round_id:03d}.json'
        raw=reply_path.read_bytes();guidance=json.loads(raw)
        request_hash=hashlib.sha256(request_path.read_bytes()).hexdigest()
        if guidance.get('basis_request_sha256')!=request_hash:raise ValueError('Feedback request mismatch')
        receipt=dict(rank=args.rank,round=round_id,status='read_verified',
            reply_sha256=hashlib.sha256(raw).hexdigest(),request_sha256=request_hash,
            read_at=datetime.now(timezone.utc).isoformat(),proposal_count=len(guidance.get('proposals',[])),
            evaluated_proposals=[],platform_compute=0,search_semantics_unchanged=True)
        name=f'feedback_receipt_{round_id:03d}.json'
        e.atomic(name,receipt)
        print('FEEDBACK_READ',args.rank,round_id,receipt['proposal_count'],flush=True)
        base=tuple(e.best)
        expected={}
        for index,p in enumerate(guidance.get('proposals',[])):
            forest=list(base);forest[p['seat']]=engine.Expr.from_json(p['expression'])
            expected.setdefault(tuple(forest),[]).append((index,p['seat']))
        original=e.evaluate
        recorded=set()
        def evaluate(pool,details=False):
            value=original(pool,details)
            for index,seat in expected.get(tuple(pool),[]):
                if index not in recorded:
                    recorded.add(index)
                    score=value['score']if isinstance(value,dict)else value
                    receipt['evaluated_proposals'].append(dict(index=index,seat=seat,score=float(score)))
                    receipt['status']='all_proposals_evaluated'if len(recorded)==receipt['proposal_count']else 'evaluating_proposals'
                    e.atomic(name,receipt)
                    print('FEEDBACK_PROPOSAL',args.rank,round_id,index,score,flush=True)
            return value
        e.evaluate=evaluate
        try:
            result=actual(e,grammar,rng,out,round_id,iterations)
            receipt.update(status='mcts_completed',completed_at=datetime.now(timezone.utc).isoformat())
            e.atomic(name,receipt)
            return result
        finally:e.evaluate=original
    mcts.round_search=with_receipt
    sys.argv=[str(SEARCH/'seven_suite.py'),'--rank',str(args.rank),'--continuous']
    seven_suite.main()


if __name__=='__main__':main()
