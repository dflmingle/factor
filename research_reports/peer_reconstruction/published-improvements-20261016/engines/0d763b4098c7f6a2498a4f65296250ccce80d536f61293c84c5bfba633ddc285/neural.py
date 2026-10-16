"""Autoregressive grammar-token SR and genuine trajectory-balance GFlowNet.

Tokens describe operators, fields, constants and windows, NOT bank formula IDs.
Every trajectory creates a variable-length expression tree in a frozen pool
context. Unique prefix paths give PB=1. Grammar masks enforce causal typing.
"""
import math
import numpy as np
import torch
from grammar import tokens, decode


class TokenPolicy(torch.nn.Module):
    def __init__(self, grammar, seats=5, hidden=64):
        super().__init__(); self.grammar = grammar
        self.embedding = torch.nn.Embedding(len(grammar.vocab)+1, 32)
        self.seat_embedding = torch.nn.Embedding(seats, hidden)
        self.cell = torch.nn.GRUCell(32, hidden)
        self.head = torch.nn.Linear(hidden, len(grammar.vocab))

    def trajectory(self, seat, forced=None, rng=None, explore=False):
        h = self.seat_embedding(torch.tensor([seat]))
        previous = torch.tensor([len(self.grammar.vocab)])
        prefix, logprob, entropy = [], torch.tensor(0.), torch.tensor(0.)
        for position in range(2*self.grammar.max_nodes+1):
            legal = self.grammar.legal(prefix)
            if not legal: return decode(prefix), logprob, entropy
            h = self.cell(self.embedding(previous), h)
            mask = torch.full((len(self.grammar.vocab),), -torch.inf)
            mask[legal] = 0
            distribution = torch.distributions.Categorical(logits=self.head(h)[0]+mask)
            if forced is not None:
                if position >= len(forced): raise ValueError('Incomplete forced trajectory')
                index = self.grammar.ids[forced[position]]
                if index not in legal: raise ValueError('Forced token violates grammar')
            elif explore:
                index = int(rng.choice(legal, p=self.grammar.prior(prefix, legal)))
            else: index = int(distribution.sample())
            action = torch.tensor(index)
            logprob = logprob + distribution.log_prob(action)
            entropy = entropy + distribution.entropy()
            prefix.append(self.grammar.vocab[index]); previous = action.reshape(1)
        raise RuntimeError('Grammar failed to terminate')


def train(e, grammar, rng, out, gflownet=False, steps=120, batch=16):
    torch.set_num_threads(1); torch.manual_seed(int(rng.integers(2**30)))
    seats=len(e.best)
    policy = TokenPolicy(grammar, seats=seats)
    logz = torch.nn.Parameter(torch.zeros(seats))
    params = list(policy.parameters()) + ([logz] if gflownet else [])
    optimizer = torch.optim.Adam([dict(params=list(policy.parameters()),lr=.003),
        dict(params=[logz],lr=.03)] if gflownet else params, lr=.003)
    base = tuple(e.best)  # fixed reward context, stationary during training
    replay = [[] for _ in range(seats)]; trace = []; samples = []
    temperature = 5.
    # Teach syntax/economic structures before reward training. These examples
    # are AST token sequences, not terminal formula IDs; the network can change
    # their topology, operators, fields and windows during subsequent sampling.
    demonstrations=[(j,tokens(x)) for j,x in enumerate(base) if math.isfinite(grammar.log_prob(x))]
    warmup=min(80,max(20,steps//2));imitation=[]
    for iteration in range(warmup):
        loss=torch.tensor(0.)
        for j,seq in demonstrations:
            _,lp,_=policy.trajectory(j,forced=seq)
            loss=loss-lp/len(seq)
        if not demonstrations:break
        optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,10.);optimizer.step()
        if iteration%10==0:imitation.append(float(loss.detach()))
    # Preserve reward differences even when the initial peer mismatch is huge;
    # a hard floor made all such formulas indistinguishable to the learner.
    def logreward(score): return -math.log1p(max(0.,-float(score)))/temperature
    calibration = [(j, grammar.sample(rng)) for j in range(seats) for _ in range(6)]
    def calibration_error():
        with torch.no_grad():
            error=[]
            for seat, expr in calibration:
                _, lp, _ = policy.trajectory(seat, forced=tokens(expr))
                pool=list(base);pool[seat]=expr
                error.append(float((logz[seat]+lp-logreward(e.evaluate(tuple(pool))))**2))
            return float(np.mean(error))
    # logZ initialized to prior importance estimates. Updates still learn it.
    if gflownet:
        with torch.no_grad():
            for j in range(seats):
                estimates=[]
                for seat, expr in calibration:
                    if seat != j: continue
                    pool=list(base);pool[j]=expr
                    estimates.append(logreward(e.evaluate(tuple(pool)))-grammar.log_prob(expr))
                estimate=torch.logsumexp(torch.tensor(estimates), 0)-math.log(len(estimates))
                # Z=sum R(terminal) is at least R(one valid base AST). A handful
                # of uniform/prior terminals can miss that mode; this bound is a
                # valid initialization aid, never a claimed exact normalizer.
                logz[j] = torch.maximum(estimate,torch.tensor(logreward(e.evaluate(base))))
    initial = calibration_error() if gflownet else None
    for step in range(steps):
        seat = step % seats; losses=[]; scores=[]; lp_list=[]; entropy_list=[]
        for k in range(batch):
            forced = None
            if gflownet and k%4 == 0 and replay[seat]:
                ranked=sorted(replay[seat], key=lambda x:x[0], reverse=True)[:64]
                forced=tokens(ranked[int(rng.integers(len(ranked)))][1])
            elif k%4 == 1 and math.isfinite(grammar.log_prob(base[seat])): forced=tokens(base[seat])
            expr, lp, entropy = policy.trajectory(seat, forced=forced, rng=rng, explore=k%4 == 2)
            pool=list(base);pool[seat]=expr;pool=tuple(pool)
            score=e.evaluate(pool); reward=logreward(score)
            scores.append(score); lp_list.append(lp); entropy_list.append(entropy)
            samples.append(pool); replay[seat].append((score,expr))
            if gflownet: losses.append((logz[seat]+lp-reward)**2)
        if gflownet: loss=torch.stack(losses).mean()
        else:
            # On-policy REINFORCE only. Off-policy seeds/exploration are useful
            # evaluations, but cannot enter this gradient without corrections.
            onpolicy=[k for k in range(batch) if k%4 == 0 or k%4 == 3 or
                      (k%4 == 1 and not math.isfinite(grammar.log_prob(base[seat])))]
            rs=torch.tensor([logreward(scores[k]) for k in onpolicy])
            threshold=torch.quantile(rs,.75)
            advantages=(rs-threshold).clamp(min=0)
            loss=-(advantages*torch.stack([lp_list[k] for k in onpolicy])).mean()
            loss=loss-.002*torch.stack([entropy_list[k] for k in onpolicy]).mean()
        optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,10.);optimizer.step()
        if len(replay[seat])>1000: replay[seat]=sorted(replay[seat],key=lambda x:x[0],reverse=True)[:500]
        if step%10==0:
            row=dict(step=step, loss=float(loss.detach()), best=float(max(scores)))
            trace.append(row);print('AST-GFN' if gflownet else 'AST-neural-SR',row,flush=True)
    final=calibration_error() if gflownet else None
    name='gflownet' if gflownet else 'neural_sr'
    from pathlib import Path
    torch.save(dict(policy=policy.state_dict(), logz=logz.detach(), vocabulary=grammar.vocab,
                    base=[x.json() for x in base]),Path(out)/(name+'.pt'))
    return max(samples,key=e.evaluate),dict(algorithm='AST trajectory-balance GFlowNet' if gflownet else 'Neural-guided AST symbolic regression',
        steps=steps,batch=batch,architecture='GRU over operators/fields/windows/constants with typed prefix masks',
        reward_context_frozen=True,trace=trace,variable_length=True,
        syntax_imitation_steps=warmup,imitation_loss=imitation,
        loss='(logZ[seat]+sum logPF-logR)^2; unique-prefix PB=1' if gflownet else 'on-policy risk-seeking REINFORCE + entropy',
        calibration_TB_initial=initial,calibration_TB_final=final,
        calibration_used_for_initial_logZ=gflownet,
        logZ_initialization='prior importance estimate with known valid-terminal lower bound' if gflownet else None,
        calibration_used_for_gradient=False,
        reward_transform='-log1p(max(-score,0))/temperature; no saturation floor',reward_temperature=temperature,
        formula_bank_ids=False)
