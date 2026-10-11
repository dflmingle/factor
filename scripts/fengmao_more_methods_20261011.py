"""Bounded AlphaGen PPO, TB-GFN and original AlphaPool on cached causal atoms.

No platform API. PPO reuses AlphaPROBE's LSTMSharedNet + MaskablePPO but
adapts the token environment/reward to grouped full-A signal-date panels.
This is not an unmodified benchmark replication of the AlphaGen paper.
"""
from __future__ import annotations

import os
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import types
import warnings

import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'quantlab/third_party/AlphaPROBE/src'))
# TensorBoard is optional here; don't load unrelated TensorFlow into the RAM budget.
sys.modules['tensorboard.compat.notf'] = types.ModuleType('tensorboard.compat.notf')
import torch
import gymnasium as gym
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from alphagen.rl.policy import LSTMSharedNet
from alphagen.models.alpha_pool import AlphaPool
import fengmao_multiround_20261011 as old
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, alignment_config_snapshot, validate_alignment_config
from search_field_policy import load_field_exclusion_policy

SOURCE = ROOT/'research_reports/platform_alignment/fengmao-multiround2-20261011'
OUT = ROOT/'research_reports/platform_alignment/fengmao-more-methods-20261011'
OPS = [('Neg', 1), ('Rank', 1), ('Add', 2), ('Sub', 2), ('Mul', 2),
       ('Grp3', 2), ('Grp5', 2), ('GZ3', 2), ('GZ5', 2),
       ('Resid3', 2), ('Resid5', 2), ('Blend3', 2), ('Blend5', 2)]
PEAK = dict(rss_gib=0., private_gib=0., min_available_gib=100.)
DONE = threading.Event()
START = time.monotonic()
warnings.filterwarnings('ignore', message=".*DataFrame.swapaxes.*", category=FutureWarning)
warnings.filterwarnings('ignore', message='.*env.action_masks.*', category=UserWarning)
warnings.filterwarnings('ignore', message='Mean of empty slice', category=RuntimeWarning)
warnings.filterwarnings('ignore', message='Degrees of freedom <= 0 for slice', category=RuntimeWarning)


def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str, allow_nan=False)+'\n', encoding='utf-8')


def log(msg):
    print(f'[{time.monotonic()-START:.1f}s] {msg}', flush=True)


def guard():
    info = psutil.Process().memory_info()
    rss, private = info.rss/2**30, getattr(info, 'private', info.rss)/2**30
    available = psutil.virtual_memory().available/2**30
    PEAK['rss_gib'] = max(PEAK['rss_gib'], rss)
    PEAK['private_gib'] = max(PEAK['private_gib'], private)
    PEAK['min_available_gib'] = min(PEAK['min_available_gib'], available)
    if max(rss, private) > 2.25 or available < 1.25:
        raise MemoryError(f'RAM boundary: rss={rss:.2f}, private={private:.2f}, available={available:.2f} GiB')


def watchdog():
    while not DONE.wait(.5):
        try:
            guard()
        except MemoryError as exc:
            save('memory_stop.json', dict(reason=str(exc), memory=PEAK))
            log(str(exc))
            os._exit(78)


def load():
    validate_alignment_config(alignment_config_snapshot())
    policy = load_field_exclusion_policy(allow_version_mismatch=True)
    # Existing registry predates qualitygate4. Empty exclusions are unchanged;
    # never use this escape hatch to bypass a non-empty stale block decision.
    if policy.get('version_mismatch') and policy['blocked_fields']:
        raise ValueError('Non-empty stale registry needs refresh')
    if set(policy['blocked_fields']) & {'close', 'volume', 'turnover', 'market_cap'}:
        raise ValueError('Required data field blocked')
    meta = json.loads((SOURCE/'metadata.json').read_text(encoding='utf-8'))
    assert meta['alignment_reference'] == ALIGNMENT_RULE_VERSION
    axes = json.loads((SOURCE/'axes.json').read_text(encoding='utf-8'))
    dates = pd.DatetimeIndex(axes['dates'])
    calendars = list((old.base.CACHE/'trade_calendar').glob('*.parquet'))
    frame = pd.concat([pd.read_parquet(p, columns=['trade_date','is_open']) for p in calendars], ignore_index=True)
    days = pd.to_datetime(frame.trade_date.astype(str), format='mixed').dt.normalize()
    calendar = pd.DatetimeIndex(sorted(days[frame.is_open.eq(1)].unique()))
    positions = calendar.get_indexer(dates)
    assert np.all(positions >= 0)
    exits = calendar[positions+11]
    masks = {'formal_5y': np.ones(len(dates), bool),
             'training': (dates<='2023-12-29') & (exits<='2023-12-29'),
             'validation_2024_2025': (dates>='2024-01-01') & (dates<='2025-12-31') & (exits<='2025-12-31'),
             'recent_2026': dates>='2026-01-01'}
    a = np.load(SOURCE/'atoms.npz')
    atoms = {k: a[k] for k in a.files if k not in ('target','market_cap','size')}
    y, cap = a['target'], a['market_cap']
    a.close()
    return atoms, y, cap, dates, exits, masks, axes, policy


class Search:
    def __init__(self, atoms, target, cap, dates):
        self.atoms, self.ev = atoms, old.FastEvaluator(target, cap, dates)
        self.records, self.origin = {}, ''
        path = OUT/'search_train.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                r = json.loads(line)
                self.records[r['formula']] = r

    def assess(self, formula):
        if formula in self.records:
            return self.records[formula]
        guard()
        row = dict(formula=formula, origin=self.origin, status='invalid', fitness=-.5)
        try:
            x = old.value(formula, self.atoms)
            p = self.ev.periods(x)
            if len(p)<.95*len(self.ev.dates):
                raise ValueError('Less than 95% training period coverage')
            s = old.base.summarize(p.assign(tied_fraction=0.))
            absolute_size = float(p.corr_size.abs().mean())
            segment_ic = [float(b.rank_ic.mean()) for b in np.array_split(p, 3)]
            # Competition quality, turnover and multi-regime IC; no net-return
            # maximisation. Raw size exposure is measured before any neutralisation.
            fitness = (s['s_i_proxy'] + .15*min(segment_ic)
                       - .06*s['turnover'] - .25*max(absolute_size-.30, 0.)
                       - .05*max(-s['net_excess'], 0.))
            if absolute_size>.50 or s['ic_mean']<=0:
                fitness -= .20
            row.update(s, abs_size_corr=absolute_size, train_worst_third_rank_ic=min(segment_ic),
                       fitness=float(fitness), status='evaluated')
        except (ValueError, KeyError, SyntaxError, FloatingPointError) as exc:
            row['error'] = str(exc)
        self.records[formula] = row
        with (OUT/'search_train.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, allow_nan=False)+'\n')
        return row

    def best(self, names):
        return max((self.records[f] for f in names), key=lambda r:r['fitness'])


class TokenEnv(gym.Env):
    """Masked postfix tree grammar; leaves are causal, date-wise ranked atoms."""
    def __init__(self, search, seed):
        self.search = search
        self.names = sorted(search.atoms)
        self.nleaf = len(self.names)
        self.stop = self.nleaf+len(OPS)
        self.max_tokens = 9
        self.action_space = gym.spaces.Discrete(self.stop+1)
        self.observation_space = gym.spaces.Box(0, self.stop+1, (self.max_tokens+1,), np.int32)
        self.seen, self.episodes = set(), 0
        self.reset(seed=seed)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.stack, self.tokens = [], []
        self.obs = np.zeros(self.max_tokens+1, np.int32)
        return self.obs.copy(), {}

    def action_masks(self):
        mask = np.zeros(self.stop+1, bool)
        depth, remaining = len(self.stack), self.max_tokens-len(self.tokens)
        # After each action, enough tokens must remain to collapse the stack.
        if remaining>=depth+1 and depth<3:
            mask[:self.nleaf] = True
        for i, (_, arity) in enumerate(OPS):
            if depth>=arity and remaining>=max(1, depth-arity+1):
                mask[self.nleaf+i] = True
        mask[self.stop] = depth==1
        if remaining==0:
            mask[:self.stop] = False
        assert mask.any(), (depth, remaining)
        return mask

    def step(self, action):
        action = int(action)
        assert self.action_masks()[action]
        done = action==self.stop
        if not done:
            if action<self.nleaf:
                self.stack.append(self.names[action])
            else:
                name, arity = OPS[action-self.nleaf]
                args = self.stack[-arity:]
                del self.stack[-arity:]
                self.stack.append(name+'('+','.join(args)+')')
            self.obs[len(self.tokens)] = action+1
            self.tokens.append(action)
            done = len(self.tokens)==self.max_tokens
        reward = 0.
        if done:
            assert len(self.stack)==1
            formula = self.stack[0]
            self.seen.add(formula)
            self.episodes += 1
            reward = float(np.clip(20*self.search.assess(formula)['fitness'], -2., 2.))
        return self.obs.copy(), reward, done, False, {}


class Progress(BaseCallback):
    def __init__(self, env, tag):
        super().__init__()
        self.token_env, self.tag = env, tag
        self.last = -1
        self.history = []

    def _on_step(self):
        guard()
        env = self.token_env
        block = env.episodes//64
        if block>self.last and env.seen:
            self.last = block
            row = dict(steps=self.num_timesteps, episodes=env.episodes, unique=len(env.seen),
                       best=env.search.best(env.seen), memory=dict(PEAK))
            self.history.append(row)
            save(self.tag+'_progress.json', self.history)
            log(f"{self.tag}: {self.num_timesteps}/6144 tokens, {env.episodes} episodes, {len(env.seen)} formulas, best fitness {row['best']['fitness']:.5f}")
        return True


def ppo(search, seed):
    tag = 'alphagen_ppo_'+str(seed)
    path = OUT/(tag+'_result.json')
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    search.origin = tag
    env = TokenEnv(search, seed)
    model = MaskablePPO('MlpPolicy', env, n_steps=256, batch_size=64, n_epochs=4,
                        learning_rate=.0003, gamma=1., ent_coef=.03, seed=seed,
                        policy_kwargs=dict(features_extractor_class=LSTMSharedNet,
                            features_extractor_kwargs=dict(n_layers=1, d_model=32, dropout=0., device=torch.device('cpu')),
                            net_arch=dict(pi=[32], vf=[32])), device='cpu', verbose=0)
    model.learn(total_timesteps=6144, callback=Progress(env, tag))
    model.save(str(OUT/tag))
    best = search.best(env.seen)
    result = dict(engine='AlphaGen_adapted_MaskablePPO_original_LSTM', seed=seed,
                  episodes=env.episodes, tokens=6144, unique=len(env.seen), best=best)
    save(tag+'_result.json', result)
    del model, env
    gc.collect()
    return result


def frontier(search, count=8):
    picks, panels = [], []
    for r in sorted(search.records.values(), key=lambda r:r['fitness'], reverse=True):
        if r['status']!='evaluated' or r['abs_size_corr']>.50 or r['ic_mean']<=0:
            continue
        x = old.value(r['formula'], search.atoms)
        rx = old.rank(x)
        if any(abs(float(np.nanmean(old.rowcorr(rx, old.rank(p)))))>.93 for p in panels):
            continue
        picks.append(r)
        panels.append(x)
        if len(picks)==count:
            break
    return picks, panels


def gfn(search, picks):
    if (OUT/'gfn_result.json').exists():
        return json.loads((OUT/'gfn_result.json').read_text(encoding='utf-8'))
    seed = 20261103
    torch.manual_seed(seed)
    search.origin = 'TB_GFN_signed_subset'
    names = [r['formula'] for r in picks]
    k = len(names)
    policy = torch.nn.Sequential(torch.nn.Linear(2*k,48), torch.nn.Tanh(), torch.nn.Linear(48,2*k+1))
    logz = torch.nn.Parameter(torch.zeros(()))
    opt = torch.optim.Adam(list(policy.parameters())+[logz], lr=.003)
    found, history = set(), []
    for batch in range(96):
        state = torch.zeros(16,2*k)
        active = torch.ones(16, dtype=torch.bool)
        lpf, lpb = torch.zeros(16), torch.zeros(16)
        for _ in range(4):
            used = state[:,:k].bool() | state[:,k:].bool()
            mask = torch.cat((~used,~used,torch.ones(16,1,dtype=torch.bool)), 1)
            mask[:,-1] = state.sum(1)>0
            mask[state.sum(1)>=3,:-1] = False
            probs = .9*torch.softmax(policy(state).masked_fill(~mask,-1e9),1)+.1*mask.float()/mask.sum(1,keepdim=True)
            dist = torch.distributions.Categorical(probs=probs)
            action = dist.sample()
            lpf = lpf+torch.where(active, dist.log_prob(action), 0.)
            added = active & (action<2*k)
            ids = torch.nonzero(added).flatten()
            nxt = state.clone()
            nxt[ids,action[ids]] = 1.
            lpb = lpb+torch.where(added, -torch.log(nxt.sum(1).clamp_min(1)), 0.)
            active = active & (action<2*k)
            state = nxt
            if not active.any():
                break
        rewards = []
        for s in state.numpy():
            parts = [names[j] if j<k else f'Neg({names[j-k]})' for j in np.flatnonzero(s)]
            expr = parts[0]
            for part in parts[1:]:
                expr = f'Add({expr},{part})'
            r = search.assess(expr)
            found.add(expr)
            rewards.append(float(np.clip(20*r['fitness'], -12, 8)))
        loss = (logz+lpf-lpb-torch.tensor(rewards)).square().mean()
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 5.)
        opt.step()
        if (batch+1)%12==0:
            row = dict(batch=batch+1, trajectories=(batch+1)*16, unique=len(found),
                       loss=float(loss.detach()), best=search.best(found), memory=dict(PEAK))
            history.append(row)
            save('gfn_progress.json', history)
            log(f"TB-GFN {batch+1}/96 batches; unique={len(found)}; loss={row['loss']:.3f}")
    result = dict(engine='native_PyTorch_trajectory_balance_signed_subset', seed=seed, trajectories=1536,
                  unique=len(found), frontier=names, best=search.best(found), final_tb_loss=float(loss.detach()))
    torch.save(dict(policy=policy.state_dict(), logz=logz.detach()), OUT/'gfn_checkpoint.pt')
    save('gfn_result.json', result)
    return result


class PanelExpr:
    def __init__(self, name, x):
        self.name, self.x = name, torch.from_numpy(np.asarray(x, np.float32).copy())
    def evaluate(self, data, period=slice(0,1)):
        return self.x
    def __str__(self):
        return self.name


def alphapool(search):
    if (OUT/'alphapool_model.json').exists():
        return json.loads((OUT/'alphapool_model.json').read_text(encoding='utf-8'))
    picks, panels = frontier(search, count=6)
    data = types.SimpleNamespace(device=torch.device('cpu'))
    pool = AlphaPool(len(picks), data, PanelExpr('training_label1', search.ev.target))
    pool.force_load_exprs([PanelExpr(r['formula'], x) for r,x in zip(picks,panels)])
    alternatives = []
    for alpha in (.005, .02, .05):
        weights = pool._optimize(alpha=alpha, lr=.0005, n_iter=300)
        weights = weights/max(float(np.abs(weights).sum()), 1e-12)
        model = dict(engine='original_bundled_AlphaPool', alpha=alpha,
                     components=[dict(formula=r['formula'], weight=float(w)) for r,w in zip(picks,weights)],
                     normalization='same-date population zscore, vendor missing zero-fill, final intersection restored')
        p = search.ev.periods(old.model_value(model, search.atoms))
        s = old.base.summarize(p.assign(tied_fraction=0.))
        absolute_size = float(p.corr_size.abs().mean())
        thirds = [float(b.rank_ic.mean()) for b in np.array_split(p,3)]
        fitness = s['s_i_proxy']+.15*min(thirds)-.06*s['turnover']-.25*max(absolute_size-.30,0.)-.05*max(-s['net_excess'],0.)
        if absolute_size>.50 or s['ic_mean']<=0:
            fitness -= .20
        model['training'] = dict(**s, abs_size_corr=absolute_size, fitness=float(fitness))
        alternatives.append(model)
        log(f'original AlphaPool alpha={alpha}: training fitness={fitness:.5f}, ICIR={s["icir"]:.3f}')
    best = max(alternatives,key=lambda m:m['training']['fitness'])
    save('alphapool_alternatives.json', alternatives)
    save('alphapool_model.json', best)
    return best


def evaluate(models, atoms, y, cap, dates, masks, axes):
    rows, prefix = [], dates<='2024-06-28'
    cut = {k:v[prefix] for k,v in atoms.items()}
    checks = []
    for i, m in enumerate(models,1):
        name = f'FM_MORE_{i:02d}'
        x = old.model_value(m, atoms)
        z = old.model_value(m, cut)
        finite = np.isfinite(z)
        delta = float(np.max(np.abs(x[prefix][finite]-z[finite])))
        same = bool(np.array_equal(np.isfinite(x[prefix]),finite))
        assert same and delta==0
        checks.append(dict(candidate=name,cells=int(finite.sum()),masks_equal=same,max_difference=delta,
                           scope='expression and same-date normalization; raw daily atoms checked separately'))
        np.save(OUT/(name+'_signals.npy'),x)
        for window, mask in masks.items():
            p = old.FastEvaluator(y[mask],cap[mask],dates[mask]).periods(x[mask])
            # Actual ties remain diagnostic; do not hard-code zero for generated trees.
            ties = []
            for date in p.date:
                at = dates.get_loc(pd.Timestamp(date))
                xx = x[at,np.isfinite(x[at]) & np.isfinite(y[at]) & np.isfinite(cap[at])]
                ties.append(float(pd.Series(xx).duplicated(keep=False).mean()))
            p['tied_fraction'] = ties
            s = old.base.summarize(p)
            s['abs_size_corr'] = float(p.corr_size.abs().mean())
            rows.append(dict(candidate=name,engine=m['engine'],window=window,**s))
            p.to_csv(OUT/f'{name}_{window}_periods.csv', index=False)
            log(f'{name} {window}: ICIR={s["icir"]:.3f}, S_i={s["s_i_proxy"]:.4f}, net={s["net_excess"]:.2%}, turn={s["turnover"]:.1%}')
        top = []
        for day in range(len(dates)):
            ids = np.flatnonzero(np.isfinite(x[day]))
            held = ids[np.argsort(-x[day,ids],kind='stable')[:20]]
            top.extend(dict(date=str(dates[day].date()),rank=j+1,instrument=axes['symbols'][ident],value=float(x[day,ident])) for j,ident in enumerate(held))
        pd.DataFrame(top).to_csv(OUT/(name+'_top20.csv'), index=False)
    save('expression_prefix_checks.json',checks)
    pd.DataFrame(rows).to_csv(OUT/'results.csv',index=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT/'plan.json').exists() and not args.resume:
        raise FileExistsError('Choose --resume; do not overwrite a research run')
    torch.set_num_threads(1)
    threading.Thread(target=watchdog, daemon=True).start()
    atoms,y,cap,dates,exits,masks,axes,policy = load()
    save('plan.json',dict(methods=['AlphaGen-adapted MaskablePPO + original LSTM, two seeds',
        'native TB-GFN signed subset', 'original bundled AlphaPool, three L1 settings'],
        ppo_tokens_per_seed=6144, ppo_seeds=[20261101,20261102],gfn_trajectories=1536,finalists=3,
        source=str(SOURCE.relative_to(ROOT)),alignment_rule_version=ALIGNMENT_RULE_VERSION,
        objective='S_i + worst-third RankIC - turnover - mean absolute size correlation - negative net penalty',
        training_periods=int(masks['training'].sum()),validation_periods=int(masks['validation_2024_2025'].sum()),
        training_end='20231229',purge='label exit <= split end',platform_cost=0,
        memory_limits=dict(process_gib=2.25,available_floor_gib=1.25),field_policy=policy,
        limitations=['opponent formula private','historical validation already researched','token env and reward adapted',
                     'GFlowNet is native TB, not original torchgfn neural token engine','stable ties proxy']))
    save('axes.json',axes)
    search = Search({k:v[masks['training']] for k,v in atoms.items()}, y[masks['training']],cap[masks['training']], dates[masks['training']])
    # Re-score only the saved training frontier under this round's new reward.
    # Previous validation metrics play no part in selection.
    oldrows = {}
    for line in (SOURCE/'search_progress.jsonl').read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        oldrows[r['formula']] = r
    search.origin = 'existing_GP_training_frontier'
    for r in sorted(oldrows.values(),key=lambda r:r['fitness'],reverse=True)[:32]:
        search.assess(r['formula'])
    log(f'cached full-A grid={y.shape}; training={masks["training"].sum()}, leaves={len(atoms)}')
    rounds = [ppo(search,seed) for seed in (20261101,20261102)]
    ppo_best = max(rounds,key=lambda r:r['best']['fitness'])
    picks,_ = frontier(search,8)
    gf = gfn(search,picks)
    pool = alphapool(search)
    models = [dict(engine=ppo_best['engine'],formula=ppo_best['best']['formula'],training=ppo_best['best'],seed=ppo_best['seed']),
              dict(engine=gf['engine'],formula=gf['best']['formula'],training=gf['best']), pool]
    save('models_frozen.json',models)
    log('THREE MODELS FROZEN before historical validation')
    evaluate(models,atoms,y,cap,dates,masks,axes)
    guard()
    save('metadata.json',dict(status='complete',rule=ALIGNMENT_RULE_VERSION,platform_cost=0,
        training_unique_formulas=len(search.records),valid_formulas=sum(r['status']=='evaluated' for r in search.records.values()),
        ppo_rounds=rounds,gfn=gf,memory=PEAK,seconds=time.monotonic()-START,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        original_alphapool_sha256=hashlib.sha256((ROOT/'quantlab/third_party/AlphaPROBE/src/alphagen/models/alpha_pool.py').read_bytes()).hexdigest(),
        torch=torch.__version__,actual_dates=[str(dates[0].date()),str(dates[-1].date())],
        last_realized_exit=str(exits[-1].date()),date_source='saved H03-T10 platform template, proxy for private opponent schedule',
        raw_atom_source=str(SOURCE.relative_to(ROOT)),nominal_window=['20210907','20260907'],recent_window=['20260101','20260907'],
        universe='full historical SH/SZ',prices='qfq',cap='daily_basic.total_mv',warmup='20180101',
        label='close(t+1)->close(t+11)',benchmark='factor_valid',one_way_cost=.003,groups=10,
        normalization='same-date only',validation='previously researched historical data, not pristine OOS'))
    DONE.set()
    log('COMPLETE '+str(OUT))


if __name__=='__main__':
    main()
