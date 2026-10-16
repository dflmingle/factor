"""Seven actual structural search families for stalled peers, isolated outputs.

No paid platform calls; real assistant replies are hash bound to residual
requests. Missing replies remain pending while the other six families run.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
from grammar import Expr, Grammar
from engine import Market
from evidence import extract, read, PUBLIC
import objective
import verify as verification
import algorithms
import mcts

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'seven_methods_v1'


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(objective.clean(data), ensure_ascii=False,
                               indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def context(rank, input_bundle=None, prepare_only=False):
    global ROOT
    if input_bundle is not None:
        import sys
        repo = HERE.parents[3]
        sys.path.insert(0, str(repo / 'scripts'))
        from peer_fresh_data_20261016 import FreshMarket
        import evidence
        bundle = Path(input_bundle).resolve()
        evidence.PUBLIC = bundle / 'public'
        public = evidence.PUBLIC
        ROOT = bundle / 'seven_methods'
    else:
        public = PUBLIC
    target = next(t for t in read(public / 'targets.json') if t['rank'] == rank)
    workspace = ROOT / target['pool_id']
    workspace.mkdir(parents=True, exist_ok=True)
    # Each process owns its A cache, panels, method reports and objectives.
    objective.HERE = workspace
    verification.HERE = workspace
    market = FreshMarket(bundle) if input_bundle is not None else Market()
    incomplete = input_bundle is not None and not market.context.get('C_verification_ready', False)
    if incomplete and not prepare_only:
        raise ValueError('Fresh bundle has incomplete financial/benchmark coverage; frozen holdings/IC replay is available, full seven-method A/B/C search is not ready')
    market.cache_dir = workspace / 'panels'
    market.cache_dir.mkdir(exist_ok=True)
    native = market.panel
    existing = [bundle / 'panels'] if input_bundle is not None else [HERE / 'panels_v3_raw_labels', HERE / 'residual_refinement_v1' / 'panels']
    def panel(expr):
        key = hashlib.sha256(expr.key().encode()).hexdigest() + '.npy'
        for folder in existing:
            p = folder / key
            if p.exists():
                return np.load(p)
        return native(expr)
    market.panel = panel
    source = workspace / 'best.json'
    if not source.exists():
        source = HERE / 'residual_refinement_v1' / target['pool_id'] / 'best.json'
    if input_bundle is not None:
        source = bundle / 'frozen' / f"{target['pool_id']}.json"
    frozen = read(source)
    ev = extract(target, market)
    if input_bundle is not None:
        by_id = dict(zip(frozen['seat_ids'], frozen['pool']))
        if set(by_id) != {s['id'] for s in ev['seats']}:
            raise ValueError('Refreshed roster differs from frozen seed; explicit mapping required')
        seed = tuple(Expr.from_json(by_id[s['id']]) for s in ev['seats'])
    else:
        seed = tuple(Expr.from_json(x) for x in frozen['pool'])
    if incomplete:
        ev['monthly'] = {}  # Holdings/IC residual packet only; no C/points claim.
        ev['notes'].append('fresh bundle: incomplete financial and benchmark; diagnostic preparation only')
    e = objective.Objective(market, ev, workspace, seed)
    if not incomplete:
        e.enable_A()
    atomic(workspace / 'manifest.json', dict(rank=rank, target=target, source=str(source),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        families=['Bayesian Program Synthesis', 'LLM-guided MCTS', 'MAP-Elites',
                  'Neural-guided Symbolic Regression', 'SMC / Particle MCMC',
                  'Differentiable Program Synthesis', 'GFlowNet'],
        platform_compute=0, all_public_dates_fitted=True, holdout=False,
        rule_reference=market.context['rule_reference'], outputs_isolated=True,
        diagnostic_only=bool(incomplete), input_bundle=str(input_bundle) if input_bundle else None))
    return e, workspace


def packet(e, round_id):
    data = mcts.request(e, e.out, round_id)
    if e.market.context.get('C_verification_ready') is False:
        data['public_board_reference'] = dict(status='omitted_in_refreshed_diagnostic',
            reason='old board snapshot does not share refreshed evidence cutoff')
        data['input_context'] = e.market.context
    data['seat_metadata'] = [dict(index=j, name=s['name'], direction=s['direction'],
                                 public_IC=e.target_ic[j], public_RankIC=e.target_rank[j],
                                 points=s['points'], A=s['A']) for j, s in enumerate(e.seats)]
    e.atomic(f'llm_request_{round_id:03d}.json', data)
    return data


def main():
    global ROOT
    p = argparse.ArgumentParser()
    p.add_argument('--rank', type=int, required=True)
    p.add_argument('--continuous', action='store_true')
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--input-bundle', type=Path, help='Versioned refreshed evidence/market bundle; never reuse old panels')
    args = p.parse_args()
    if args.input_bundle is not None:
        ROOT = args.input_bundle.resolve() / 'seven_methods'
    ROOT.mkdir(exist_ok=True)
    lock = (ROOT / f'rank_{args.rank}.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    e, out = context(args.rank, args.input_bundle, args.prepare)
    rng = np.random.default_rng(20261014 + args.rank)
    grammar = Grammar(max_depth=10, max_nodes=100)
    completed = [int(f.name.split('_')[1]) for f in out.glob('round_*_complete.json')]
    round_id = max(completed, default=0) + 1
    if not (out / f'llm_request_{round_id:03d}.json').exists():
        packet(e, round_id)
    if args.prepare:
        if e.market.context.get('C_verification_ready') is False:
            e.atomic('preparation_status.json', dict(status='holdings_IC_residual_prepared',
                full_ABC_search_ready=False, platform_compute=0,
                missing='complete PIT financial refresh and matching benchmark/public board cutoff'))
        else:
            verification.verify(e)
        print('Prepared actual residual packet', args.rank, out, flush=True)
        return
    while True:
        prefix = f'round_{round_id:03d}_'
        work = out / f'round_{round_id:03d}'
        work.mkdir(exist_ok=True)
        before = verification.verify(e)
        e.atomic(prefix + 'starting_verification.json', before)
        reply = out / f'llm_reply_{round_id:03d}.json'
        request = out / f'llm_request_{round_id:03d}.json'
        methods = []
        if reply.exists():
            data = read(reply)
            actual_hash = hashlib.sha256(request.read_bytes()).hexdigest()
            if data.get('basis_request_sha256') != actual_hash:
                raise ValueError('Live feedback does not match the residual request')
            methods.append(('mcts', lambda:mcts.round_search(
                e, grammar, rng, out, round_id, iterations=max(180, e.seat_count*12))))
        else:
            e.atomic(prefix + 'mcts.json', dict(status='pending_real_LLM_feedback',
                     request=request.name, platform_compute=0))
        methods.extend([
            ('map_elites', lambda:algorithms.map_elites(e, grammar, rng,
                steps=max(240, e.seat_count*20))),
            ('bayesian', lambda:algorithms.bayesian(e, grammar, rng,
                steps=max(100, e.seat_count*12), chains=4)),
            ('smc', lambda:algorithms.smc(e, grammar, rng, particles=16, runs=3)),
            ('particle_mcmc', lambda:algorithms.particle_mcmc(
                e, grammar, rng, particles=16, steps=5)),
        ])
        import neural
        from differentiable import train as diff_train
        methods.extend([
            ('neural_sr', lambda:neural.train(e, grammar, rng, work,
                gflownet=False, steps=100, batch=12)),
            ('differentiable', lambda:diff_train(e, grammar, rng, work,
                steps=60, stocks=96, depth=2, projections=24)),
            ('gflownet', lambda:neural.train(e, grammar, rng, work,
                gflownet=True, steps=100, batch=12)),
        ])
        for name, fn in methods:
            atomic(out / 'status.json', dict(pid=os.getpid(), rank=args.rank,
                round=round_id, phase=name, updated_at=datetime.now(timezone.utc).isoformat(),
                platform_compute=0, state='running'))
            start = time.monotonic()
            eval_before = e.evaluations
            try:
                _, report = fn()
                report = dict(report, elapsed_seconds=time.monotonic()-start,
                              objective_calls=e.evaluations-eval_before,
                              status='executed', platform_compute=0)
            except (ValueError, RuntimeError) as exc:
                report = dict(status='failed', reason=str(exc), platform_compute=0)
            e.atomic(prefix + name + '.json', report)
            validated = verification.verify(e)
            e.atomic(prefix + name + '_verification.json', validated)
            print('METHOD', args.rank, round_id, name, report.get('status'),
                  'passed', validated['acceptance']['passed'], flush=True)
        after = verification.verify(e)
        e.atomic(prefix + 'complete.json', dict(round=round_id,
            before=before['acceptance']['actual'], after=after['acceptance']['actual'],
            passed=after['acceptance']['passed'],
            completed_at=datetime.now(timezone.utc).isoformat(), platform_compute=0))
        if after['acceptance']['passed'] or not args.continuous:
            break
        round_id += 1
        packet(e, round_id)
    atomic(out / 'status.json', dict(pid=os.getpid(), rank=args.rank,
           state='completed', passed=after['acceptance']['passed'], platform_compute=0))


if __name__ == '__main__':
    main()
