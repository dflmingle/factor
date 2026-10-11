"""Bounded grammar MCTS inspired by AlphaCFG; an adaptation, not upstream reproduction.

Uniform-prior PUCT with incremental grammar nodes, three predetermined seeds.
Signals use new raw daily atoms plus existing causal ranked context. Early and
purged development labels only; frozen historical evaluation after all searches.
"""
from __future__ import annotations
import gc
import hashlib
import json
import math
from pathlib import Path
import threading
import time
import numpy as np
import pandas as pd
import fengmao_information_shock_20261011 as shock
from fengmao_literal_clue_20261011 import SelectionEvaluator

shared=shock.shared
ROOT=shock.ROOT
OUT=ROOT/'research_reports/platform_alignment/fengmao-grammar-mcts-20261011'
SEEDS=(20261051,20261052,20261053)
ITERATIONS=160


class Node:
    def __init__(self): self.n=0; self.w=0.; self.children={}


def render(spec):
    op,x,y,by=spec
    return f'{op}(rawrank:{x},context:{y},by:{by})'


def expression(spec,atoms):
    op,x,y,by=spec
    a=atoms['raw_'+x]; b=atoms['ctx_'+y]; condition=atoms['raw_'+by]
    if op=='sum_rank': value=a+b
    elif op=='difference_rank': value=a-b
    elif op=='product_rank': value=a*b
    elif op=='peer_gap_sum': value=a+b
    elif op=='peer_gap_difference': value=a-b
    elif op=='group_z_sum': value=a+b
    elif op=='negative_group_rank': value=a
    else: value=a
    mode='peer_diff' if op.startswith('peer_gap') else ('peer_z' if op=='group_z_sum' else 'rank')
    temp={'value':value,'condition':condition}
    result=shock.expression(dict(signal='value',group='condition',mode=mode,buckets=5,sign=1),temp)
    if op=='negative_group_rank': result=-result
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'frozen_candidates.json').exists(): raise RuntimeError('Frozen run cannot be tuned')
    shared.OUT=OUT
    threading.Thread(target=shared.watchdog,daemon=True).start()
    start=time.monotonic()
    rawaxes=json.loads((shock.OUT/'axes.json').read_text(encoding='utf8'))
    union=pd.DatetimeIndex(rawaxes['dates'])
    _,y,cap,dates,axes=shared.prior.load('target'); del _
    context,fy,fc,fd,fa=shared.prior.load('formal')
    assert rawaxes['symbols']==fa['symbols']==axes['symbols']
    # Load exact target/context separately because target and formal schedules
    # differ; fill union at their own date positions and verify common values.
    target_context,_,_,_,_=shared.prior.load('target')
    context_names=['rev3','rev6','rev20','rev60','lowturn','vol20','vstab20','size',
                   'idrev20','onrev20','tug20','downshare20','rvcor20','macdhist']
    atoms={}
    with np.load(shock.OUT/'atoms_raw.npz') as z:
        for name in z.files: atoms['raw_'+name]=shared.rank(z[name])
    for name in context_names:
        a=np.full((len(union),len(fa['symbols'])),np.nan,np.float32)
        a[union.get_indexer(fd)]=context[name]
        ix=union.get_indexer(dates)
        common=np.isfinite(a[ix])&np.isfinite(target_context[name])
        assert np.allclose(a[ix][common],target_context[name][common],atol=1e-7)
        a[ix]=target_context[name]
        atoms['ctx_'+name]=a
    del context,target_context
    gc.collect()
    ix=union.get_indexer(dates); fi=union.get_indexer(fd)
    exits=pd.DatetimeIndex(axes['exits'])
    early=(dates<shared.FINAL_START)&(exits<shared.FINAL_START)
    dev=early&(dates>=shared.DEVELOP_START)
    ev=SelectionEvaluator(y[early],cap[early]); dv=SelectionEvaluator(y[dev],cap[dev])
    new_names=[k.removeprefix('raw_') for k in atoms if k.startswith('raw_') and any(k.startswith('raw_'+p) for p in
        ('corr6_','weightedrev','highvolret','lowvolret','intrarev','overnightmom','tug','shockpressure','disagreement'))]
    actions=[['group_rank','negative_group_rank','sum_rank','difference_rank','product_rank',
              'peer_gap_sum','peer_gap_difference','group_z_sum'],new_names,context_names,
             ['volmean20','volsurprise','volshockz60','volcv20','volatility20','size']]
    shared.write('protocol.json',dict(rule=shared.ALIGNMENT_RULE_VERSION,engine='adapted uniform-prior grammar PUCT',
        upstream='https://github.com/HanYang544/AlphaCFG',upstream_code_executed=False,seeds=SEEDS,
        simulations_per_seed=ITERATIONS,grammar_actions=actions,platform_cost=0,
        selection_dates=dates[early].astype(str).tolist(),development_dates=dates[dev].astype(str).tolist(),
        final_start=str(shared.FINAL_START),final_used_for_selection=False,final_previously_exposed=True,
        all_searches_before_final_evaluation=True,source_run=str(shock.OUT.relative_to(ROOT)),
        selection_objective='joint public IC/IR/win discrepancy plus cost and size penalties; no date/symbol identifiers',
        fidelity='local proxy, frozen historical validation; uniform PUCT, no upstream policy network'))
    records={}; traces=[]; chosen=[]
    for seed in SEEDS:
        rng=np.random.default_rng(seed); root=Node(); tried=[]
        for it in range(ITERATIONS):
            node=root; path=[node]; spec=[]
            for options in actions:
                unvisited=[a for a in options if a not in node.children]
                if unvisited:
                    action=unvisited[int(rng.integers(len(unvisited)))]; node.children[action]=Node()
                else:
                    shuffled=[options[i] for i in rng.permutation(len(options))]
                    action=max(shuffled,key=lambda a:node.children[a].w/max(node.children[a].n,1)+
                               1.25/len(options)*math.sqrt(max(node.n,1))/(1+node.children[a].n))
                spec.append(action); node=node.children[action]; path.append(node)
            key=render(spec)
            if key not in records:
                try:
                    s=expression(spec,atoms)[ix]; s[~np.isfinite(cap)]=np.nan
                    em=ev.evaluate(s[early]); dm=dv.evaluate(s[dev])
                    loss=.5*shared.objective(em)+shared.objective(dm)+2*max(-dm['net_excess'],0)
                    records[key]=dict(formula=key,spec=spec,early=em,development=dm,
                                      selection_loss=loss,status='evaluated')
                except (ValueError,FloatingPointError) as exc:
                    records[key]=dict(formula=key,spec=spec,selection_loss=1e9,status='failed',error=str(exc))
            row=records[key]; reward=math.exp(-min(row['selection_loss'],100)/15)
            for ancestor in path: ancestor.n+=1; ancestor.w+=reward
            tried.append(row); traces.append(dict(seed=seed,iteration=it,formula=key,reward=reward))
            if (it+1)%40==0:
                shared.write('search_results.json',list(records.values()))
                shared.log(f'grammar PUCT seed {seed}: {it+1}/{ITERATIONS}, unique {len(records)}')
            shared.guard()
        best=min(tried,key=lambda r:r['selection_loss'])
        chosen.append(dict(name=f'FM_MCTS_{seed}',spec=best['spec'],selection=best))
    shared.write('search_results.json',list(records.values()))
    shared.write('frozen_candidates.json',dict(frozen_before_final_labels=True,candidates=chosen))
    shared.write('freeze_hashes.json',dict(script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 frozen=hashlib.sha256((OUT/'frozen_candidates.json').read_bytes()).hexdigest()))
    pd.DataFrame(traces).to_csv(OUT/'mcts_traces.csv',index=False)
    rows=[]
    for model in chosen:
        s=expression(model['spec'],atoms)
        for scope,ss,yy,cc,dd in [('target',s[ix],y,cap,dates),('formal',s[fi],fy,fc,fd)]:
            ss[~np.isfinite(cc)]=np.nan
            np.save(OUT/f'{model["name"]}_{scope}_signals.npy',ss)
            windows=[('target119',np.ones(len(dd),bool)),('historical_final24',dd>=shared.FINAL_START)] if scope=='target' else [
                ('formal_5y',np.ones(len(dd),bool)),('formal_final',dd>=shared.FINAL_START),('recent_2026',dd>=pd.Timestamp('2026-01-01'))]
            for window,mask in windows:
                m,p,g=shared.metrics(ss[mask],yy[mask],cc[mask],dd[mask])
                p.to_csv(OUT/f'{model["name"]}_{window}_periods.csv',index=False)
                g.to_csv(OUT/f'{model["name"]}_{window}_groups.csv',index=False)
                rows.append(dict(candidate=model['name'],window=window,**m))
                shared.log(f'{model["name"]} {window}: IC {m["rank_ic"]:.6f}, IR {m["rank_ir"]:.3f}, wins {m["wins"]}/{m["periods"]}')
    pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)
    shared.STOP.set()
    shared.write('metadata.json',dict(status='complete',goal_achieved=False,platform_cost=0,rule=shared.ALIGNMENT_RULE_VERSION,
                 unique_formulas=len(records),simulations=len(traces),seconds=time.monotonic()-start,memory=shared.PEAK))
    shared.log('grammar MCTS complete; recovery not established')


if __name__=='__main__': main()
