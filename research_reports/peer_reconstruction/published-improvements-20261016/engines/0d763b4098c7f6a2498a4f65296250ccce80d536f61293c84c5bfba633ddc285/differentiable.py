"""Differentiable expression structure, constants, windows, ranks and pool C.

A depth-configurable binary supernet relaxes unary/binary/trailing operators.
Training uses a declared stock/time subsample and smooth execution approximations.
Only projected, full-history, hard-evaluated ASTs are reported as candidates.
"""
import numpy as np
import torch
import pandas as pd
from grammar import field, const, op, seed_pool, validate


def soft_rank(x, temperature=.2):
    # One date's cross-section only; O(N^2) on the declared training subsample.
    return torch.sigmoid((x.unsqueeze(-1)-x.unsqueeze(-2))/temperature).mean(-1)


def rolling(x, n, kind):
    if n > x.shape[0]: return torch.zeros_like(x)
    padded=torch.cat([x[:1].expand(n-1,-1),x],0)
    windows=padded.unfold(0,n,1)
    if kind=='mean':return windows.mean(-1)
    if kind=='std':return (windows.var(-1,unbiased=False)+1e-8).sqrt()
    if kind=='max':return .2*torch.logsumexp(windows/.2,-1)-.2*np.log(n)
    if kind=='min':return -.2*torch.logsumexp(-windows/.2,-1)+.2*np.log(n)
    if kind=='rank':return torch.sigmoid((windows[:,:,-1:]-windows)/.2).mean(-1)
    raise ValueError(kind)


class RelaxedNode(torch.nn.Module):
    OPS=('identity','neg','abs','logabs','sqrtabs','add','sub','mul','div','mean2','max2','min2',
         'rank','zscore','ts_mean','ts_std','ts_max','ts_min','delay','ts_rank','ema','sma')
    WINDOWS=(3,5,10,14,20,60)
    def __init__(self, leaves, depth):
        super().__init__();self.leaves,self.depth=leaves,depth
        self.leaf_logits=torch.nn.Parameter(torch.zeros(len(leaves)+1))
        self.constant=torch.nn.Parameter(torch.tensor(0.))
        if depth:
            self.left=RelaxedNode(leaves,depth-1);self.right=RelaxedNode(leaves,depth-1)
            self.op_logits=torch.nn.Parameter(torch.zeros(len(self.OPS)))
            self.window_logits=torch.nn.Parameter(torch.zeros(len(self.WINDOWS)))
            with torch.no_grad():self.op_logits[0]=2.5

    def forward(self, data, temperature, memo):
        if not self.depth:
            p=(self.leaf_logits/temperature).softmax(0)
            return sum(p[i]*x for i,x in enumerate(data))+p[-1]*self.constant.tanh()*5
        a=self.left(data,temperature,memo);b=self.right(data,temperature,memo)
        p=(self.op_logits/temperature).softmax(0)
        # Numerical safeguards belong only to the declared soft surrogate.
        # Projection exports exact division and the exact hard interpreter rejects
        # degeneracy. No soft-held return is reported as a backtest result.
        safe=torch.where(b<0,-b.abs().clamp(min=.01),b.abs().clamp(min=.01))
        z=(a-a.mean(1,keepdim=True))/(a.std(1,keepdim=True,unbiased=False)+1e-4)
        rank=soft_rank(z)
        values=[a,-a,a.abs(),a.abs().clamp(min=1e-6).log(),(a.abs()+1e-6).sqrt(),
                a+b,a-b,a*b,a/safe,(a+b)/2,torch.logsumexp(torch.stack([a,b])/.2,0)*.2,
                -torch.logsumexp(torch.stack([-a,-b])/.2,0)*.2,rank,z]
        wp=(self.window_logits/temperature).softmax(0)
        for kind in ('mean','std','max','min','delay','rank','ema','sma'):
            result=torch.zeros_like(a)
            for i,n in enumerate(self.WINDOWS):
                if kind=='delay':v=torch.cat([a[:1].expand(n,-1),a[:-n]],0) if n<a.shape[0] else a[:1].expand_as(a)
                elif kind in ('ema','sma'):
                    # Truncated causal exponential FIR; hard projection uses full
                    # 2018 warm-up EWM. This approximation is recorded explicitly.
                    length=min(3*n,a.shape[0]);alpha=2/(n+1) if kind=='ema' else 1/n
                    w=torch.tensor([(1-alpha)**k for k in range(length-1,-1,-1)],dtype=a.dtype)
                    w=w/w.sum();pad=torch.cat([a[:1].expand(length-1,-1),a],0)
                    v=(pad.unfold(0,length,1)*w).sum(-1)
                else:v=rolling(a,n,kind)
                result=result+wp[i]*v
            values.append(result)
        # The old raw market-cap leaf overwhelmed mixtures and drove every
        # branch into a hard clamp with zero gradients. Leaves now explicitly
        # export per-date ZSCORE ASTs, and the surrogate uses a smooth bound.
        mixture=sum(p[i]*v for i,v in enumerate(values))
        return 100*torch.tanh(mixture/100)

    def project(self, rng=None, temperature=.2):
        def pick(logits):
            if rng is None:return int(logits.argmax())
            p=(logits.detach()/temperature).softmax(0).numpy();return int(rng.choice(len(p),p=p))
        if not self.depth:
            i=pick(self.leaf_logits)
            return self.leaves[i] if i<len(self.leaves) else const(float(self.constant.detach().tanh()*5))
        kind=self.OPS[pick(self.op_logits)];a=self.left.project(rng,temperature)
        if kind=='identity':return a
        if kind in ('add','sub','mul','div','mean2','max2','min2'):
            return op(kind,a,self.right.project(rng,temperature))
        if kind in ('ts_mean','ts_std','ts_max','ts_min','delay','ts_rank','ema','sma'):
            return op(kind,a,window=self.WINDOWS[pick(self.window_logits)])
        return op(kind,a)


def train(e,grammar,rng,out,steps=50,stocks=96,depth=1,projections=24):
    """Learn AST topology/operators/constants; hard-evaluate every projection.

    This soft training objective uses sampled stocks and recent diagnostic
    dates. It never replaces the independent full-history A verification.
    """
    from pathlib import Path
    torch.set_num_threads(1);torch.manual_seed(int(rng.integers(2**30)))
    public_ids=set()
    for record in e.records:
        public_ids.update(i for i in e.stocks.get_indexer([r['symbol']for r in record['rows']])if i>=0)
    known=sorted(public_ids)
    chosen=list(rng.choice(known,min(stocks//2,len(known)),replace=False))if known else[]
    other=np.setdiff1d(np.arange(len(e.stocks)),chosen)
    chosen+=rng.choice(other,stocks-len(chosen),replace=False).tolist();chosen=np.array(chosen)
    start=max(0,int(e.pos.min())-180);stop=int(e.pos.max())+1;positions=e.pos-start
    base=tuple(e.best)
    roots=[field(k)for k in e.engine.fields]+list(base)
    leaves=list(dict.fromkeys(op('zscore',x)for x in roots if x.depth<grammar.max_depth))
    if not leaves:raise ValueError('No valid differentiable leaves')
    data=[torch.tensor(np.nan_to_num(e.engine.evaluate(x)[start:stop,chosen]),dtype=torch.float32)for x in leaves]
    models=torch.nn.ModuleList([RelaxedNode(leaves,depth)for _ in base])
    def initialize(node,index):
        with torch.no_grad():
            node.leaf_logits.fill_(-1.);node.leaf_logits[index]=1.
            if node.depth:node.op_logits.fill_(-1.);node.op_logits[0]=1.
        if node.depth:initialize(node.left,index);initialize(node.right,index)
    for j,m in enumerate(models):
        leaf=op('zscore',base[j]);initialize(m,leaves.index(leaf)if leaf in leaves else j%len(leaves))
    optimizer=torch.optim.Adam(models.parameters(),lr=.025)
    direction=torch.tensor(e.directions,dtype=torch.float32).reshape(len(base),1,1)
    active=torch.tensor(e.active,dtype=torch.float32).unsqueeze(-1)
    target=torch.zeros((len(e.signals),stocks));valid=torch.zeros_like(target,dtype=torch.bool)
    for record in e.records:
        i=e.index[pd.Timestamp(record['signal'])]
        mapping={r['symbol']:r['composite']for r in record['rows']if r.get('composite')is not None}
        for j,index in enumerate(chosen):
            symbol=e.stocks[index]
            if symbol in mapping:target[i,j]=mapping[symbol];valid[i,j]=True
    def corr(a,b):
        a=a-a.mean(-1,keepdim=True);b=b-b.mean(-1,keepdim=True)
        return (a*b).mean(-1)/(a.square().mean(-1).sqrt()*b.square().mean(-1).sqrt()+1e-6)
    y=[torch.tensor(np.nan_to_num(v[:,chosen]),dtype=torch.float32)if len(v)else None for v in e.y]
    points=[[e.index[pd.Timestamp(p['exposure_date'])]for p in s['points']]for s in e.seats]
    losses=[];grads=[];trace=[];projected=[]
    for step in range(steps):
        native=torch.stack([m(data,max(.7,1-step/max(steps,1)*.3),{})[positions]for m in models])
        lo=torch.quantile(native,.01,dim=-1,keepdim=True);hi=torch.quantile(native,.99,dim=-1,keepdim=True)
        clipped=torch.maximum(lo,torch.minimum(hi,native))
        z=(clipped-clipped.mean(-1,keepdim=True))/(clipped.std(-1,keepdim=True,unbiased=False)+1e-4)
        composite=(z*direction*active).sum(0)/active.sum(0).clamp(min=1.)
        loss=(composite[valid]-target[valid]).square().mean()if valid.any()else native.square().mean()*0
        ic_losses=[];ric_by_seat=[]
        for j,idx in enumerate(points):
            if not idx:ric_by_seat.append(None);continue
            raw=clipped[j,idx]
            ic=corr(raw,y[j]);ric=corr(soft_rank((raw-raw.mean(-1,keepdim=True))/(raw.std(-1,keepdim=True)+1e-4)),soft_rank(y[j]/.02))
            target_rank=torch.tensor(e.target_rank[j],dtype=torch.float32)
            part=((ric-target_rank)/.1).square().mean()
            known=np.isfinite(e.target_ic[j])
            if known.any():part=part+((ic[known]-torch.tensor(e.target_ic[j][known],dtype=torch.float32))/.1).square().mean()
            ic_losses.append(part);ric_by_seat.append(ric)
        if ic_losses:loss=loss+torch.stack(ic_losses).mean()
        # Directional cumulative B uses each peer's own available periods and
        # denominator; no fixed five-seat or four-observation dimensions.
        b_losses=[]
        for month,public in e.targets.items():
            denom=public.get('denominator_b',0)
            if not denom:continue
            scores=[]
            for j,seat in enumerate(e.seats):
                if month not in seat['A']:continue
                ids=[k for k,p in enumerate(seat['points'])if p['return_end_date']<=e.evidence['cutoff'][month]]
                if len(ids)<3 or ric_by_seat[j]is None:continue
                xs=ric_by_seat[j][ids]*e.directions[j];mu=xs.mean();std=xs.std(unbiased=True).clamp(min=.01)
                scores.append(mu.abs()*mu.abs()/std*torch.sigmoid((xs-.02)/.02).mean())
            if scores:
                estimate=sum(scores)/denom
                b_losses.append((torch.asinh(estimate/.05)-np.arcsinh(public['raw_b']/.05)).square())
        if b_losses:loss=loss+.1*torch.stack(b_losses).mean()
        if not torch.isfinite(loss):raise RuntimeError('Nonfinite differentiable loss')
        optimizer.zero_grad();loss.backward();grad=torch.nn.utils.clip_grad_norm_(models.parameters(),5.)
        if not torch.isfinite(grad):raise RuntimeError('Nonfinite differentiable gradients')
        grads.append(float(grad));losses.append(float(loss.detach()));optimizer.step()
        if step%10==0 or step==steps-1:
            pool=tuple(m.project()for m in models)
            for j,x in enumerate(pool):
                try:
                    validate(x,grammar.max_depth,grammar.max_nodes)
                    proposed=list(e.best);proposed[j]=x;proposed=tuple(proposed);e.evaluate(proposed);projected.append(proposed)
                except ValueError:pass
            try:
                for x in pool:validate(x,grammar.max_depth,grammar.max_nodes)
                score=e.evaluate(pool);projected.append(pool)
            except ValueError:score=-1e6
            trace.append(dict(step=step,loss=float(loss.detach()),gradient_norm=float(grad),hard_score=score))
            print('Variable-seat differentiable AST',trace[-1],flush=True)
    for _ in range(projections):
        pool=tuple(m.project(rng)for m in models)
        for j,x in enumerate(pool):
            try:
                validate(x,grammar.max_depth,grammar.max_nodes);proposed=list(e.best);proposed[j]=x
                proposed=tuple(proposed);e.evaluate(proposed);projected.append(proposed)
            except ValueError:pass
    torch.save(models.state_dict(),Path(out)/'differentiable.pt')
    return max(projected,key=e.evaluate)if projected else e.best,dict(
        algorithm='Variable-seat differentiable AST program synthesis',steps=steps,depth=depth,stocks=stocks,
        seats=len(base),training_days=stop-start,learned=['leaf fields','operators','topology','windows','continuous constants'],
        losses=['composite','Pearson IC','soft RankIC','smooth direction-oriented cumulative B'],
        hard_verification=['all-stock IC/RankIC','holdings','net monthly C','all boards','independent five-year A'],
        soft_limits='sampled stocks; soft ranks/extrema; causal truncated EWM; soft safeguards; hard projection replays full 2018 history',
        loss_initial=losses[0],loss_final=losses[-1],gradient_norm_min=min(grads),trace=trace)

