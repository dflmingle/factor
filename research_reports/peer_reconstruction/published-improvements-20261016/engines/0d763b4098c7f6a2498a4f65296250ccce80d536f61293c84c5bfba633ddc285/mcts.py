"""PUCT expression synthesis with auditable dynamic LLM feedback rounds.

The live Codex assistant consumes requests and supplies structured replies.
No external model credentials or paid API calls are hidden in this module.
Absent a real reply, the run is explicitly PENDING, never 'LLM-guided'.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from grammar import Expr, tokens, decode, validate


def request(e, out, round_id):
    row=e.evaluate(e.best,details=True)
    from board_reference import public_reference
    packet=dict(round=round_id,provider='live Codex assistant via file feedback',
        task='Propose causal AST changes using the current per-seat/per-period residuals; no target-valued terminals.',
        best=row,allowed_fields=list(e.engine.fields),
        public_board_reference=public_reference(e.evidence['target']['pool_id']),
        reply_schema=dict(round=round_id,reasoning='why each change addresses a residual',
            token_boost={'rank':2.0},proposals=[dict(seat=0,expression={'op':'field','value':'amount'})]),
        restrictions=['All stocks get identical formulas; no symbol/date gates.',
            'No forward returns or public IC values in formulas.',
            'Avoid fitting B/C summaries while ignoring per-period IC/RankIC.'])
    e.atomic(f'llm_request_{round_id:03d}.json',packet)
    return packet


def round_search(e, grammar, rng, out, round_id, iterations=160):
    out=Path(out); reply=out/f'llm_reply_{round_id:03d}.json'
    if not reply.exists():
        request(e,out,round_id)
        return None,dict(status='pending_real_LLM_feedback',round=round_id)
    guidance=json.loads(reply.read_text())
    if guidance.get('round')!=round_id or not guidance.get('reasoning'):
        raise ValueError('Missing/incorrect LLM feedback metadata')
    if guidance.get('provider')!='live Codex assistant': raise ValueError('Unidentified live feedback provider')
    boosts=guidance.get('token_boost',{})
    for token,value in boosts.items():
        if token not in grammar.ids or not np.isfinite(value) or not .05<=value<=20:
            raise ValueError('Invalid guidance token prior')
    base=tuple(e.best);base_score=e.evaluate(base)
    forests=[{():dict(n=0,total=0.,children={})} for _ in range(len(base))]
    proposed=[];traces=[]
    def prior(prefix,legal):
        p=grammar.prior(prefix,legal)
        p*=np.array([boosts.get(grammar.vocab[i],1.) for i in legal]);return p/p.sum()
    def reward(score):
        x=math.log1p(max(-base_score,0))-math.log1p(max(-score,0))
        return 1/(1+math.exp(-x))
    def backprop(nodes,path,score):
        for p in path:
            nodes.setdefault(p,dict(n=0,total=0.,children={}))
            nodes[p]['n']+=1;nodes[p]['total']+=reward(score)
    for proposal in guidance.get('proposals',[]):
        seat=proposal['seat']
        if type(seat)is not int or not 0<=seat<len(base): raise ValueError('Bad seat')
        expr=Expr.from_json(proposal['expression'])
        validate(expr,grammar.max_depth,grammar.max_nodes)
        if not expr.fields or not math.isfinite(grammar.log_prob(expr)): raise ValueError('Guidance outside grammar')
        pool=list(base);pool[seat]=expr;pool=tuple(pool)
        score=e.evaluate(pool);seq=tokens(expr);prefix=();path=[prefix];nodes=forests[seat]
        for token in seq:
            child=prefix+(token,)
            nodes.setdefault(prefix,dict(n=0,total=0.,children={}));nodes[prefix]['children'][token]=child
            prefix=child;path.append(prefix)
        backprop(nodes,path,score);proposed.append(dict(seat=seat,score=score,expression=expr.json()))
    for iteration in range(iterations):
        seat=iteration%len(base);nodes=forests[seat];prefix=();path=[prefix]
        while grammar.legal(prefix):
            node=nodes.setdefault(prefix,dict(n=0,total=0.,children={}))
            legal=grammar.legal(prefix);p=prior(prefix,legal)
            width=min(len(legal),max(1,int(2*math.sqrt(node['n']+1))))
            unseen=[i for i in legal if grammar.vocab[i]not in node['children']]
            if unseen and len(node['children'])<width:
                q=np.array([p[legal.index(i)]for i in unseen]);q/=q.sum()
                index=int(rng.choice(unseen,p=q));token=grammar.vocab[index]
                child=prefix+(token,);node['children'][token]=child;prefix=child;path.append(prefix)
                # Guidance also influences every rollout token, with no fixed
                # bank of complete formulas and no access to future observations.
                while grammar.legal(prefix):
                    legal=grammar.legal(prefix);i=int(rng.choice(legal,p=prior(prefix,legal)))
                    prefix=prefix+(grammar.vocab[i],);path.append(prefix)
                break
            def uct(item):
                token,child=item;c=nodes.setdefault(child,dict(n=0,total=0.,children={}))
                pr=p[legal.index(grammar.ids[token])]
                return c['total']/max(c['n'],1)+2*pr*math.sqrt(node['n']+1)/(c['n']+1)
            prefix=max(node['children'].items(),key=uct)[1];path.append(prefix)
        expr=decode(prefix);pool=list(base);pool[seat]=expr
        score=e.evaluate(tuple(pool));backprop(nodes,path,score)
        if iteration%40==0:traces.append(dict(iteration=iteration,best=e.best_row['score']))
    meta=dict(algorithm='Dynamically LLM-guided AST PUCT MCTS',round=round_id,
        live_feedback=True,provider=guidance['provider'],reasoning=guidance['reasoning'],
        reply_sha256=hashlib.sha256(reply.read_bytes()).hexdigest(),
        request_sha256=hashlib.sha256((out/f'llm_request_{round_id:03d}.json').read_bytes()).hexdigest(),
        evaluated_LLM_proposals=proposed,iterations=iterations,
        nodes=sum(len(n)for n in forests),trace=traces,
        dynamic_update='new feedback based on each round\'s actual residuals')
    e.atomic(f'mcts_round_{round_id:03d}.json',dict(result=e.evaluate(e.best,True),diagnostics=meta))
    return e.best,meta
