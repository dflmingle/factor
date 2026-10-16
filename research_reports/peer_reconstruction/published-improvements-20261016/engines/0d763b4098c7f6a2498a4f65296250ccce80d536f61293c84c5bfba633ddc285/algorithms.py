"""Structural Bayesian MH, MAP-Elites, prefix SMC and Particle Independent MH.

All create new ASTs. Bayesian independence proposals cancel the EXACT
generative grammar probability; arbitrary subtree mutations are not falsely
treated as symmetric MH. PIMH uses an unbiased SMC normalizer estimate.
"""
import math
import numpy as np
from grammar import paths, seed_pool, Grammar, replace


def logmeanexp(values):
    a = np.asarray(values, float); m = a.max()
    return float(m + np.log(np.exp(a - m).mean()))


def normalized(logweights):
    a = np.asarray(logweights, float); p = np.exp(a - a.max()); return p / p.sum()


def potential(e, pool):
    # Positive pseudo-likelihood includes complexity regularization. This is not
    # a calibrated probability of having recovered someone else's private code.
    return float(e.evaluate(pool))


def subtree_proposal(grammar, expr, rng):
    nodes=paths(expr);path,child=nodes[int(rng.integers(len(nodes)))]
    local=Grammar(grammar.max_depth-len(path),grammar.max_nodes-expr.nodes+child.nodes)
    return replace(expr,path,local.sample(rng))


def subtree_logq(grammar, source, target):
    """Sum ALL possible subtree replacement paths yielding the target AST.

    Using only the sampled path would miss overlapping ancestor proposals and
    break detailed balance. Resource-truncated local grammar densities and
    the source's node-selection probability also enter the proposal density.
    """
    possible=[];target_nodes=dict(paths(target));source_nodes=paths(source)
    for path,child in source_nodes:
        if path not in target_nodes:continue
        replacement=target_nodes[path]
        if replace(source,path,replacement)!=target:continue
        local=Grammar(grammar.max_depth-len(path),grammar.max_nodes-source.nodes+child.nodes)
        lp=local.log_prob(replacement)
        if math.isfinite(lp):possible.append(lp-math.log(len(source_nodes)))
    if not possible:return -math.inf
    m=max(possible);return m+math.log(sum(math.exp(v-m)for v in possible))


def mixed_logq(grammar, source, target):
    independent=math.log(.3)+grammar.log_prob(target)
    local=math.log(.7)+subtree_logq(grammar,source,target)
    return float(np.logaddexp(independent,local))


def bayesian(e, grammar, rng, steps=160, chains=4):
    start = tuple(e.best)
    if not all(math.isfinite(grammar.log_prob(x)) for x in start):
        start=tuple(x if math.isfinite(grammar.log_prob(x)) else grammar.sample(rng)for x in e.seed)
    pools = [start] * chains
    # All posterior states must be in the proposal prior's support.
    for g in pools:
        if not all(math.isfinite(grammar.log_prob(x)) for x in g):
            raise ValueError('Bayesian seed outside generative-prior support')
    values = [potential(e, g) for g in pools]; accepted = 0; history = []
    for iteration in range(steps):
        for i, g in enumerate(pools):
            seat = int(rng.integers(len(e.best))); proposal = list(g)
            old=g[seat]
            proposal[seat] = grammar.sample(rng) if rng.random()<.3 else subtree_proposal(grammar,old,rng)
            proposal = tuple(proposal);new=proposal[seat]
            v = potential(e, proposal)
            delta=(v-values[i]+grammar.log_prob(new)-grammar.log_prob(old)
                +mixed_logq(grammar,new,old)-mixed_logq(grammar,old,new))
            if math.log(max(rng.random(), 1e-300)) < delta:
                pools[i], values[i] = proposal, v; accepted += 1
        if iteration % 20 == 0: history.append(dict(step=iteration, best=max(values)))
    winner = pools[int(np.argmax(values))]
    return winner, dict(algorithm='Bayesian structural Metropolis-Hastings',
        steps=steps, chains=chains, proposals=steps*chains, accepted=accepted,
        posterior='p_grammar(AST pool) * exp(inverse log-likelihood - .04*node_count)',
        proposal='30% independent regeneration + 70% subtree replacement; exact forward/reverse proposal densities summed over all paths',
        scope='tempered pseudo-posterior, no identification certainty', history=history)


def descriptor(pool):
    nodes = [x for e in pool for _, x in paths(e)]
    return (min(9, sum(e.nodes for e in pool)//10), max(e.depth for e in pool),
        min(9, len(set().union(*(e.fields for e in pool)))),
        sum(x.op.startswith('ts_') or x.op in ('ema', 'sma', 'delay') for x in nodes)//3,
        sum(x.op in ('mul', 'div', 'rank', 'zscore') for x in nodes)//3)


def map_elites(e, grammar, rng, steps=500, seeds=()):
    archive = {}; rejected = 0
    def put(pool):
        v = e.evaluate(pool)
        if v <= -1e99 or not np.isfinite(v): return
        key = descriptor(pool)
        if key not in archive or v > archive[key][0]: archive[key] = (v, tuple(pool))
    put(e.best)
    for g in seeds: put(g)
    for _ in range(steps):
        parent = list(archive.values())[int(rng.integers(len(archive)))][1]
        pool = list(parent); j = int(rng.integers(len(e.best)))
        pool[j] = grammar.sample(rng) if rng.random() < .15 else grammar.mutate(pool[j], rng)
        if rng.random() < .15 and len(archive) > 1:
            other = list(archive.values())[int(rng.integers(len(archive)))][1]
            target, _ = paths(pool[j])[int(rng.integers(len(paths(pool[j]))))]
            from grammar import replace, validate
            donor = paths(other[j])[int(rng.integers(len(paths(other[j]))))][1]
            candidate = replace(pool[j], target, donor)
            try: validate(candidate, grammar.max_depth, grammar.max_nodes); pool[j] = candidate
            except ValueError: rejected += 1
        put(tuple(pool))
    winner = max(archive.values(), key=lambda p:p[0])[1]
    rows = [dict(descriptor=list(d), score=v, pool=[x.json() for x in g]) for d,(v,g) in archive.items()]
    return winner, dict(algorithm='MAP-Elites with subtree GP mutations/crossover',
        steps=steps, cells=len(archive), rejected_oversize=rejected, archive=rows)


def smc_filter(e, grammar, rng, particles=24, base=None):
    """Feynman-Kac filter over variable-sized ASTs, resampling every seat.

    gamma_j(prefix) = p_grammar(prefix) * exp(G(prefix + baseline suffix)).
    Intermediate G is only a bridge. At j=seat_count the final potential is the exact
    inverse objective; telescoping weights remove the bridge from the target.
    """
    if particles < 2: raise ValueError('At least two particles required')
    base = tuple(e.best if base is None else base)
    prefixes = [()] * particles; scores = np.full(particles, potential(e, base))
    logz = float(scores[0]); history = []
    for seat in range(len(base)):
        new_prefixes, proposed, corrections = [], [], []
        for prefix in prefixes:
            if isinstance(grammar,Grammar):
                reference=base[seat]
                if not math.isfinite(grammar.log_prob(reference)):
                    reference=e.seed[seat]
                if not math.isfinite(grammar.log_prob(reference)):
                    reference=grammar.sample(rng)
                expr=grammar.sample(rng)if rng.random()<.3 else subtree_proposal(grammar,reference,rng)
                correction=grammar.log_prob(expr)-mixed_logq(grammar,reference,expr)
            else:
                expr=grammar.sample(rng);correction=0.
            p = prefix + (expr,)
            new_prefixes.append(p); proposed.append(potential(e, p + base[seat+1:]))
            corrections.append(correction)
        increments = np.array(proposed) - scores + corrections
        logz += logmeanexp(increments)
        weights = normalized(increments)
        history.append(dict(seat=seat, ESS=float(1/np.sum(weights**2)), log_normalizer=logz))
        # Multinomial resampling preserves the unbiased normalizer required by
        # particle independent MH. The last selected trajectory is one particle.
        ids = rng.choice(particles, particles, p=weights)
        prefixes = [new_prefixes[i] for i in ids]; scores = np.array(proposed)[ids]
    index = int(rng.integers(particles))
    return prefixes[index], logz, dict(particles=particles, history=history,
        best_particle_score=float(scores.max()), normalizer='unbiased product of mean incremental weights',
        proposal='grammar-prior and causal AST-subtree mixture, with exact p_grammar/q correction')


def smc(e, grammar, rng, particles=24, runs=3):
    base = tuple(e.best); sampled = []; estimates = []; reports = []
    for _ in range(runs):
        pool, z, info = smc_filter(e, grammar, rng, particles, base)
        sampled.append(pool); estimates.append(z); reports.append(info)
    return max(sampled, key=e.evaluate), dict(algorithm='AST-prefix SMC',
        runs=runs, log_normalizers=estimates, filters=reports)


def particle_mcmc(e, grammar, rng, particles=24, steps=12):
    # Freeze the bridge for every proposal in one Markov chain. Otherwise the
    # normalizer estimates would correspond to different extended-state models.
    base = tuple(e.best)
    current, logz, info = smc_filter(e, grammar, rng, particles, base)
    accepted = 0; traces = []; samples = [current]
    for step in range(steps):
        proposal, proposed_z, report = smc_filter(e, grammar, rng, particles, base)
        accept = math.log(max(rng.random(), 1e-300)) < proposed_z-logz
        if accept: current, logz = proposal, proposed_z; accepted += 1
        samples.append(current)
        traces.append(dict(step=step, accepted=accept, logz=logz, proposed_logz=proposed_z))
    return max(samples, key=e.evaluate), dict(algorithm='Particle Independent Metropolis-Hastings (PIMH)',
        particles=particles, steps=steps, accepted=accepted, trace=traces,
        acceptance='min(1, Zhat_proposed/Zhat_current), not ordinary MH rejuvenation',
        base_frozen=True, initial_filter=info)
