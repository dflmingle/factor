"""Resumable local queue for all top-50 peers; no platform/account mutations.

First fit a broad causal hypothesis bank to each seat and public composites,
then synthesize new ASTs with real search algorithms. LLM MCTS runs only when
the live assistant has answered that peer's actual residual request. A missing
reply is explicitly pending, never counted as LLM-guided execution.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from grammar import Expr,Grammar,field,const,op,validate,formula
from engine import Market,initial_bank
from evidence import extract,pack_all,read,PUBLIC
from objective import Objective,clean
from verify import verify,reference,FROZEN
from hypotheses import additions,named,signed,PROVENANCE
import algorithms

HERE=Path(__file__).resolve().parent
OUTPUT='peers_v5_Broster'
STATUS_PATH=HERE/'queue_status.json'


def save(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n');temp.replace(path)


def seed_for(seat):
    n=seat['name'].lower();positive=seat['direction']=='positive'
    c=field('close');ret=op('sub',op('div',c,op('delay',c,window=1)),const(1))
    if any(k in n for k in ['illiquidity','amihud','非流动','冷清']):x=op('ts_mean',op('div',op('abs',ret),field('amount')),window=20);good=True
    elif any(k in n for k in ['small','市值','size','sml']):x=field('cap');good=False
    elif any(k in n for k in ['bm','bp','value','val_','价值']):x=field('bm');good=True
    elif any(k in n for k in ['pb','市净']):x=op('div',const(1),field('bm'));good=False
    elif any(k in n for k in ['ep','ey','盈利收益']):x=field('ep');good=True
    elif any(k in n for k in ['cfp','cash','现金']):x=field('cfp');good=True
    elif any(k in n for k in ['roe','质量','quality']):x=field('roe');good=True
    elif any(k in n for k in ['gm','毛利']):x=field('gm');good=True
    elif any(k in n for k in ['turn','换手']):x=op('ts_mean',field('turnover'),window=20);good=False
    elif any(k in n for k in ['vol','波动','振幅']):x=op('ts_std',ret,window=20);good=False
    elif any(k in n for k in ['rsi']):
        d=op('sub',c,op('delay',c,window=1));up=op('sma',op('max2',d,const(0)),window=14)
        down=op('sma',op('max2',op('neg',d),const(0)),window=14);x=op('div',up,op('add',up,down));good=False
    elif any(k in n for k in ['amount','amt','成交额']):x=op('ts_mean',field('amount'),window=20);good=False
    else:
        window=60 if '60'in n else 120 if '120'in n else 5 if '_5'in n or 'rev5'in n else 20
        x=op('sub',op('div',c,op('delay',c,window=window)),const(1));good=False
    return x if good==positive else op('neg',x)


def objectives(market, targets):
    result=[]
    for target in targets:
        evidence=extract(target,market)
        seed=[seed_for(s)for s in evidence['seats']]
        if target['rank']==1:
            frozen=read(FROZEN/'frozen_best.json')
            seed=[Expr.from_json(x)for x in frozen['pool']]
            seed=[x if s['direction']=='positive'else op('neg',x)for x,s in zip(seed,evidence['seats'])]
        out=HERE/OUTPUT/target['pool_id']
        e=Objective(market,evidence,out,seed)
        existing=out/'best.json'
        if not existing.exists():existing=HERE/'peers_v4_lifecycle'/target['pool_id']/'best.json'
        if existing.exists():
            old=read(existing)
            if old.get('target',{}).get('pool_id')!=target['pool_id']or len(old.get('pool',[]))!=e.seat_count:
                raise ValueError('Existing search context changed')
            e.best=tuple(Expr.from_json(x)for x in old['pool'])
            e.seed=e.best
        e.evaluate(e.best,True)
        result.append(e)
    return result


def summary(es,phase,epoch=0):
    peers=[]
    for e in es:
        p=e.out/'verification_status.json';v=read(p)if p.exists()else {}
        peers.append(dict(rank=e.evidence['target']['rank'],name=e.evidence['target']['display_name'],pool_id=e.evidence['target']['pool_id'],
            local_threshold_passed=v.get('passed',False),status=v.get('status','searching; verification pending'),
            score=e.best_row['score']if e.best_row else None,evaluations=e.evaluations,
            seats=e.seat_count,holding_dates=len(e.records),membership_mismatches=len(e.membership_mismatch)))
    save(STATUS_PATH,dict(updated_at=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),phase=phase,epoch=epoch,output_directory=OUTPUT,
        target_count=len(es),local_threshold_passed=sum(p['local_threshold_passed']for p in peers),
        platform_confirmed=1,platform_compute_this_job=0,peers=peers,done=all(p['local_threshold_passed']for p in peers)))


def bank_pass(es,market,bank,rng):
    # Full causal history to evaluate each expression, shared by all peer cycles.
    for i,x in enumerate(bank):
        market.panel(x)
        if i%20==0:
            save(HERE/'bank_progress.json',dict(completed=i+1,total=len(bank),formula=formula(x),pid=os.getpid()))
            print('Causal bank',i+1,'/',len(bank),flush=True)
    ordered=sorted(es,key=lambda e:(bool(e.membership_mismatch),e.evidence['target']['rank']))
    for e in ordered:
        t=e.evidence['target'];print('Fit peer',t['rank'],t['display_name'],'seats',e.seat_count,flush=True)
        if t['rank']==1:
            verify(e);continue
        bank_id=hashlib.sha256(''.join(x.key()for x in bank).encode()).hexdigest()
        finished=e.out/'initial_bank_fit.json'
        if finished.exists()and read(finished).get('bank_hash')==bank_id:
            verify(e);summary(es,'resumed completed first-pass candidates');continue
        choices=[]
        expanded=list(dict.fromkeys(list(bank)+list(e.best)))
        for j,seat in enumerate(e.seats):
            hypotheses=list(dict.fromkeys(expanded+named(seat)))
            ranked=sorted(((e.seat_loss(x,j),x)for x in hypotheses),key=lambda z:z[0])
            top=[x for _,x in ranked[:10]]
            # Preserve distinct field/structure families and named hypotheses
            # for seats without completed IC, whose sequence loss is uninformative.
            if not seat['points']:
                top=list(dict.fromkeys([seed_for(seat),field('bm'),field('ep'),field('roe'),
                    op('neg',field('cap')),op('neg',field('turnover'))]+top))
            top=list(dict.fromkeys([e.best[j]]+top))
            choices.append(top)
        pool=list(e.best)
        for j,options in enumerate(choices):
            pool[j]=min(options,key=lambda x:e.seat_loss(x,j))
        e.evaluate(tuple(pool),True)
        for sweep in range(2):
            for j in rng.permutation(e.seat_count):
                for x in choices[j]:
                    proposal=list(e.best);proposal[j]=x;e.evaluate(tuple(proposal))
        e.atomic('initial_bank_fit.json',dict(candidates=len(expanded),bank_hash=bank_id,provenance=PROVENANCE,choices=[[x.json()for x in xs]for xs in choices],
            method='causal hypothesis enumeration + joint coordinate selection; not mislabelled as seven search algorithms'))
        verify(e);summary(es,'first-pass candidates')


def search_epoch(es,grammar,rng,epoch):
    for e in sorted(es,key=lambda e:(bool(e.membership_mismatch),e.evidence['target']['rank'])):
        status=e.out/'verification_status.json'
        if status.exists()and read(status).get('passed'):continue
        prefix=f'epoch_{epoch:04d}_';method_dir=e.out/prefix.rstrip('_');method_dir.mkdir(exist_ok=True)
        print('Search peer',e.evidence['target']['rank'],e.evidence['target']['display_name'],'epoch',epoch,flush=True)
        mcts_request=__import__('mcts').request(e,e.out,epoch)
        summary(es,f"structural synthesis rank {e.evidence['target']['rank']}",epoch)
        methods=[('map_elites',lambda:algorithms.map_elites(e,grammar,rng,steps=max(120,e.seat_count*5))),
                 ('bayesian',lambda:algorithms.bayesian(e,grammar,rng,steps=max(40,e.seat_count*2),chains=3)),
                 ('smc',lambda:algorithms.smc(e,grammar,rng,particles=12,runs=2)),
                 ('particle_mcmc',lambda:algorithms.particle_mcmc(e,grammar,rng,particles=12,steps=3))]
        for name,fn in methods:
            summary(es,f"rank {e.evidence['target']['rank']} {name}",epoch)
            try:
                _,report=fn();e.atomic(prefix+name+'.json',report)
            except (ValueError,RuntimeError)as exc:e.atomic(prefix+name+'.json',dict(status='failed',reason=str(exc)))
        # Neural methods generate variable-length AST tokens, not bank IDs.
        import neural
        for gf in [False,True]:
            name='gflownet'if gf else'neural_sr'
            summary(es,f"rank {e.evidence['target']['rank']} {name}",epoch)
            try:
                _,report=neural.train(e,grammar,rng,method_dir,gflownet=gf,steps=max(40,e.seat_count*2),batch=8)
                e.atomic(prefix+name+'.json',report)
            except (ValueError,RuntimeError)as exc:e.atomic(prefix+name+'.json',dict(status='failed',reason=str(exc)))
        from differentiable import train as diff_train
        try:
            _,report=diff_train(e,grammar,rng,method_dir,steps=50,stocks=96)
            e.atomic(prefix+'differentiable.json',report)
        except (ValueError,RuntimeError)as exc:e.atomic(prefix+'differentiable.json',dict(status='failed',reason=str(exc)))
        import mcts
        if (e.out/f'llm_reply_{epoch:03d}.json').exists():
            _,report=mcts.round_search(e,grammar,rng,e.out,epoch,iterations=max(120,e.seat_count*4))
            e.atomic(prefix+'mcts.json',report)
        else:e.atomic(prefix+'mcts.json',dict(status='pending_real_LLM_feedback',request=f'llm_request_{epoch:03d}.json'))
        verify(e);summary(es,'structural synthesis',epoch)
        e.atomic(prefix+'complete.json',dict(epoch=epoch,completed_at=datetime.now(timezone.utc).isoformat(),passed=read(e.out/'verification_status.json')['passed']))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--continuous',action='store_true');parser.add_argument('--verify-reference',action='store_true')
    parser.add_argument('--skip-bank',action='store_true');parser.add_argument('--ranks',type=int,nargs='*')
    parser.add_argument('--status-file',type=Path,default=None)
    args=parser.parse_args();rng=np.random.default_rng(20261013 + (min(args.ranks) if args.ranks else 0))
    global STATUS_PATH
    if args.status_file is not None:
        STATUS_PATH=args.status_file.resolve();STATUS_PATH.parent.mkdir(parents=True,exist_ok=True)
    market=Market();pack_all(market);targets=read(PUBLIC/'targets.json')
    if args.ranks:targets=[x for x in targets if x['rank']in args.ranks]
    if args.verify_reference:targets=targets[:1]
    es=objectives(market,targets);summary(es,'initialized')
    save(HERE/'acceptance_reference.json',reference())
    save(HERE/'source_manifest.json',dict(source_implementations='isolated adaptations of expression_tree_upgrade',
        hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in HERE.glob('*.py')},
        algorithm_support='arbitrary historical/current seat counts and cycles; no shared original files edited',platform_compute=0))
    if args.verify_reference:
        result=verify(es[0]);print(json.dumps(clean(result['acceptance']),ensure_ascii=False),flush=True);return
    if not args.skip_bank:bank_pass(es,market,list(dict.fromkeys(signed(initial_bank())+additions())),rng)
    for e in es:
        e.enable_A()
    grammar=Grammar(max_depth=10,max_nodes=100)
    existing_epochs=[int(p.name.split('_')[1])for e in es for p in e.out.glob('epoch_*_complete.json')]
    epoch=max(existing_epochs,default=0)+1
    while True:
        statuses=[read(e.out/'verification_status.json').get('passed')if (e.out/'verification_status.json').exists()else False for e in es]
        if all(statuses):summary(es,'all local thresholds passed',epoch);break
        search_epoch(es,grammar,rng,epoch);epoch+=1
        if not args.continuous:break
        summary(es,'continuing incomplete peers',epoch)


if __name__=='__main__':main()
