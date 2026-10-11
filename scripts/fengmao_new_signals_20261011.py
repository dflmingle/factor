"""One authorized offline round: new causal signals, PPO, CEM and AlphaPool."""
import argparse
import ast
import gc
import hashlib
import json
from pathlib import Path
import threading
import time
import numpy as np
import pandas as pd
import fengmao_more_methods_20261011 as methods
import fengmao_new_atoms_20261011 as features

ROOT = methods.ROOT
OUT = ROOT/'research_reports/platform_alignment/fengmao-new-signals-20261011'
CONTEXT = ['rev3','rev20','rev60','vol20','vol60','vrel20','lowturn','vstab20']


class Search(methods.Search):
    def assess(self, formula):
        leaves = {n.id for n in ast.walk(ast.parse(formula,mode='eval')) if isinstance(n,ast.Name)}
        if not leaves.intersection(features.NEW_NAMES):
            if formula not in self.records:
                row = dict(formula=formula,origin=self.origin,status='excluded_old_only',fitness=-.5)
                self.records[formula] = row
                with (OUT/'search_train.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps(row)+'\n')
            return self.records[formula]
        return super().assess(formula)


def cross_entropy(search):
    """Categorical cross entropy over interpretable conditional tree templates."""
    path = OUT/'cem_result.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    rng = np.random.default_rng(20261202)
    choices = [features.NEW_NAMES, sorted(search.atoms),
               ['Grp3','Grp5','Resid3','Resid5','Blend3','Blend5'],
               ['plain','negative','difference','product'], ['positive','negative']]
    probs = [np.ones(len(a))/len(a) for a in choices]
    seen, history = set(), []
    search.origin = 'CEM_conditional_formula'
    for generation in range(8):
        population = []
        for _ in range(48):
            indices = [int(rng.choice(len(a),p=p)) for a,p in zip(choices,probs)]
            x,by,op,template,sign = [a[i] for a,i in zip(choices,indices)]
            inner = x if template=='plain' else (f'Neg({x})' if template=='negative' else
                    (f'Sub({x},{by})' if template=='difference' else f'Mul({x},{by})'))
            formula = f'{op}({inner},{by})'
            if sign=='negative':
                formula = f'Neg({formula})'
            record = search.assess(formula)
            seen.add(formula)
            population.append((record['fitness'],indices))
        elites = sorted(population,reverse=True)[:12]
        for j,a in enumerate(choices):
            counts = np.bincount([inds[j] for _,inds in elites],minlength=len(a)).astype(float)+.5
            probs[j] = .55*probs[j]+.45*counts/counts.sum()
        row = dict(generation=generation+1,draws=(generation+1)*48,unique=len(seen),
                   best=search.best(seen), probabilities=[p.tolist() for p in probs])
        history.append(row)
        methods.save('cem_progress.json',history)
        methods.log(f'CEM {generation+1}/8; unique={len(seen)}, fitness={row["best"]["fitness"]:.5f}')
    result = dict(engine='categorical_cross_entropy_conditional_trees',seed=20261202,
                  draws=384,unique=len(seen),best=search.best(seen))
    methods.save('cem_result.json',result)
    return result


def load():
    atoms,y,cap,dates,exits,masks,axes,policy = methods.load()
    atoms = {k:atoms[k] for k in CONTEXT}
    if (OUT/'atoms.npz').exists():
        with np.load(OUT/'atoms.npz') as saved:
            atoms = {k:saved[k] for k in saved.files if k not in ('target','market_cap')}
    else:
        methods.log('Loading actual qfq opens and causal daily inputs')
        calendar,stocks,fields = methods.old.base.load_data()
        assert stocks.tolist()==axes['symbols']
        features.load_open(calendar,stocks,fields)
        positions = calendar.get_indexer(dates)
        assert np.all(positions>=0)
        rebuilt_y = fields['close'][positions+11].astype(float)/fields['close'][positions+1].astype(float)-1
        assert np.allclose(rebuilt_y,y,equal_nan=True,atol=1e-12,rtol=0)
        assert np.array_equal(fields['cap'][positions],cap,equal_nan=True)
        atoms.update(features.build_new_atoms(fields,positions))
        np.savez_compressed(OUT/'atoms.npz',**atoms,target=y,market_cap=cap)
        del fields,calendar,rebuilt_y
        gc.collect()
    return atoms,y,cap,dates,exits,masks,axes,policy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resume',action='store_true')
    args = ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'plan.json').exists() and not args.resume:
        raise FileExistsError('Existing round; use --resume')
    if (OUT/'metadata.json').exists():
        raise FileExistsError('Completed round will not be overwritten')
    methods.OUT = OUT
    methods.old.base.memory_guard = methods.guard
    methods.torch.set_num_threads(1)
    threading.Thread(target=methods.watchdog,daemon=True).start()
    methods.save('plan.json',dict(methods=['adapted AlphaGen PPO + original LSTM, one seed',
        'categorical cross entropy, 8x48 formulas','original AlphaPool, 3 L1 settings'],
        new_atoms=features.NEW_NAMES,context_atoms=CONTEXT,ppo_tokens=6144,ppo_seed=20261201,
        cem_draws=384,baseline_formulas=56,finalists=3,platform_cost=0,
        alignment_rule_version=methods.ALIGNMENT_RULE_VERSION,
        training_end='20231229',purge='label exit <= split end',
        final_selection='training only, independent method winner; frozen before validation',
        memory_limits=dict(process_gib=2.25,available_floor_gib=1.25,chunk_stocks=192),
        hypotheses='conditional daily/overnight pressure, asymmetric risk and technical state',
        prior_research='standalone overnight/intraday and correlation legs already studied; this round tests conditional combinations',
        limitations=['local diagnostic proxy; private opponent formula unavailable',
                     '2024-2025 validation already researched; not pristine OOS',
                     'stable-symbol ties proxy; no fabricated amount/high/low']))
    atoms,y,cap,dates,exits,masks,axes,policy = load()
    methods.save('axes.json',axes)
    search = Search({k:v[masks['training']] for k,v in atoms.items()},
                    y[masks['training']],cap[masks['training']],dates[masks['training']])
    search.origin = 'new_atom_direction_controls'
    for name in features.NEW_NAMES:
        search.assess(name)
        search.assess(f'Neg({name})')
    methods.log(f'New feature grid {y.shape}, leaves={len(atoms)}, training={masks["training"].sum()}')
    ppo = methods.ppo(search,20261201)
    cem = cross_entropy(search)
    pool = methods.alphapool(search)
    models = [dict(engine=ppo['engine'],formula=ppo['best']['formula'],training=ppo['best']),
              dict(engine=cem['engine'],formula=cem['best']['formula'],training=cem['best']),pool]
    methods.save('models_frozen.json',models)
    methods.log('THREE NEW-SIGNAL MODELS FROZEN before historical validation')
    # Reuse the exact previous evaluator. Names FM_MORE_* are local opaque IDs,
    # distinguished by the run directory; no previous artifacts are modified.
    methods.evaluate(models,atoms,y,cap,dates,masks,axes)
    methods.guard()
    methods.save('metadata.json',dict(status='complete',rule=methods.ALIGNMENT_RULE_VERSION,
        platform_cost=0,training_unique_formulas=len(search.records),
        valid_formulas=sum(r['status']=='evaluated' for r in search.records.values()),
        ppo=ppo,cem=cem,memory=methods.PEAK,seconds=time.monotonic()-methods.START,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        feature_source_sha256=hashlib.sha256(Path(features.__file__).read_bytes()).hexdigest(),
        actual_dates=[str(dates[0].date()),str(dates[-1].date())],
        last_realized_exit=str(exits[-1].date()),nominal_window=['20210907','20260907'],
        recent_window=['20260101','20260907'],warmup='20180101',universe='full historical SH/SZ',
        prices='qfq, actual open and close',cap='daily_basic.total_mv',
        label='close(t+1)->close(t+11)',benchmark='factor_valid',one_way_cost=.003,groups=10,
        field_policy=policy,raw_atom_source=str(OUT.relative_to(ROOT)),
        date_source='saved H03-T10 platform template, proxy for private opponent schedule',
        validation='previously researched historical data, not pristine OOS'))
    methods.DONE.set()
    methods.log('COMPLETE '+str(OUT))


if __name__=='__main__':
    main()
