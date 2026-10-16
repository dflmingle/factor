"""Multi-peer objective: IC paths, holdings, raw B/C and every signal board.

A is replayed independently for each finalist on five-year dates by verify.py.
No score agreement can pass acceptance while A or evidence coverage is missing.
"""
from collections import OrderedDict
import json
import math
import os
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
from grammar import Expr,formula
from engine import correlation,standardize,winsor

HERE=Path(__file__).resolve().parent


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v)for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
    return x


def holding_check(pred,mask,stocks,record):
    ids=np.flatnonzero(mask&np.isfinite(pred));order=ids[np.argsort(pred[ids],kind='stable')]
    chosen=order[-int(np.ceil(len(order)/10)):]if len(order)else np.array([],int)
    truth={r['symbol']for r in record['rows']}
    numeric=[r for r in record['rows']if r.get('composite')is not None]
    indices=stocks.get_indexer([r['symbol']for r in numeric]);estimates=np.full(len(indices),np.nan)
    valid=indices>=0;estimates[valid]=pred[indices[valid]]
    target=np.array([r['composite']for r in numeric],float);good=np.isfinite(estimates)
    error=np.where(good,estimates-target,1.)
    top=min(numeric,key=lambda r:r['rank'])['symbol']if numeric else None
    prediction=str(stocks[order[-1]])if len(order)else None
    return chosen,dict(trade_date=record['trade'],signal_date=record['signal'],overlap=len(truth&set(stocks[chosen]))/max(len(truth),1),
        public_top1=top,predicted_top1=prediction,top1_exact=top==prediction,
        public_holdings=len(truth),predicted_holdings=len(chosen),numeric_labels=len(target),
        missing_numeric_predictions=int((~good).sum()),unknown_symbols=int((indices<0).sum()),
        composite_rmse=float(np.sqrt(np.mean(error**2)))if len(error)else None,
        observed_composite_rmse=float(np.sqrt(np.mean(error[good]**2)))if good.any()else None)


class Objective:
    def __init__(self,market,evidence,out,seed):
        self.market,self.evidence,self.out=market,evidence,Path(out);self.out.mkdir(parents=True,exist_ok=True)
        self.engine=market.engine;self.cal=market.cal;self.stocks=market.stocks;self.fields=market.fields
        self.seats=evidence['seats'];self.seat_count=len(self.seats);self.cycle=evidence['cycle']
        self.records=evidence['records'];self.targets=evidence['monthly'];self.seed=tuple(seed);self.best=tuple(seed)
        self.best_row=None;self.cache=OrderedDict();self.leg_cache=OrderedDict();self.evaluations=0;self.invalid=0
        self.common_cache=OrderedDict()
        # IC signatures are tiny; keeping all bank signatures avoids rebuilding
        # full standardized panels 44 times for a 44-version peer. The separate
        # panel cache is needed only for joint pool/holdings evaluation.
        self.signature_cache={}
        if not hasattr(market,'ic_signature_cache'):market.ic_signature_cache=OrderedDict()
        self.use_A=False
        self.ic_measurement='winsor';self.protocol=market.context
        signals=sorted({pd.Timestamp(r['signal'])for r in self.records}|{pd.Timestamp(p['exposure_date'])for s in self.seats for p in s['points']})
        self.signals=pd.DatetimeIndex(signals);self.pos=self.cal.get_indexer(self.signals)
        self.index={d:i for i,d in enumerate(self.signals)};self.mask=market.competition_mask[self.pos]
        self.directions=np.array([1. if s['direction']=='positive'else -1. for s in self.seats])
        self.active=np.ones((self.seat_count,len(self.signals)),bool)
        for j,s in enumerate(self.seats):
            if s.get('effective_trade_date'):
                self.active[j]&=(self.cal[self.pos+1]>=pd.Timestamp(s['effective_trade_date']))
            if s.get('end_trade_date'):
                self.active[j]&=(self.cal[self.pos+1]<pd.Timestamp(s['end_trade_date']))
        self.membership_mismatch=[dict(trade=r['trade'],known=int(self.active[:,self.index[pd.Timestamp(r['signal'])]].sum()),
                                      public=r['active_factor_count'])for r in self.records
            if int(self.active[:,self.index[pd.Timestamp(r['signal'])]].sum())!=r['active_factor_count']]
        self.y=[];self.target_ic=[];self.target_rank=[]
        for seat in self.seats:
            labels=[];ics=[];ranks=[]
            for point in seat['points']:
                p=self.cal.get_loc(pd.Timestamp(point['exposure_date']))
                end=p+self.cycle+1
                if self.cal[end]!=pd.Timestamp(point['return_end_date']):
                    raise ValueError('Published IC holding interval differs from cycle/label1')
                # Preserve the frozen reference's inverse-measurement NaNs.
                # Canonical formal five-year verification separately uses the
                # documented causal close fill; do not mix those measurements.
                label=self.fields['close'][end].astype(float)/self.fields['close'][p+1]-1
                label[~market.competition_mask[p]]=np.nan
                labels.append(label);ics.append(point['pearson']);ranks.append(point['rank_ic'])
            self.y.append(np.array(labels));self.target_ic.append(np.array([np.nan if v is None else v for v in ics]));self.target_rank.append(np.array(ranks))
        self.atomic('protocol.json',dict(**market.context,target=evidence['target'],cycle=self.cycle,seats=self.seat_count,
            rawB='direction-oriented RankIC, sample std ddof1, win oriented RankIC>.02, cumulative through monthly cutoff',
            membership_mismatch=self.membership_mismatch,evidence_notes=evidence['notes']))

    def atomic(self,name,value):
        p=self.out/name;temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n');temp.replace(p)

    def leg(self,expr,j):
        key=(expr,j)
        if key in self.leg_cache:self.leg_cache.move_to_end(key);return self.leg_cache[key]
        if expr not in self.common_cache:
            positions=[self.market.panel_map[d]for d in self.signals]
            native=self.market.panel(expr)[positions].astype(float)
            signature=self.signature(expr,native)
            self.common_cache[expr]=dict(z=standardize(native,self.mask),**signature)
            while len(self.common_cache)>960:self.common_cache.popitem(last=False)
        common=self.common_cache[expr];self.common_cache.move_to_end(expr)
        ic=[common['by_date'][pt['exposure_date']][0]for pt in self.seats[j]['points']]
        ric=[common['by_date'][pt['exposure_date']][1]for pt in self.seats[j]['points']]
        result=dict(z=common['z']*self.directions[j],ic=np.array(ic),ric=np.array(ric),coverage=common['coverage'])
        self.leg_cache[key]=result
        while len(self.leg_cache)>1800:self.leg_cache.popitem(last=False)
        return result

    def signature(self,expr,native=None):
        if expr in self.signature_cache:return self.signature_cache[expr]
        if native is None:
            positions=[self.market.panel_map[d]for d in self.signals]
            native=self.market.panel(expr)[positions].astype(float)
        by_date={};shared=self.market.ic_signature_cache
        for seat,labels in zip(self.seats,self.y):
            for pt,y in zip(seat['points'],labels):
                date=pt['exposure_date']
                if date in by_date:continue
                i=self.index[pd.Timestamp(date)]
                key=(expr,self.cycle,date)
                if key not in shared:
                    raw=winsor(native[i:i+1],self.mask[i:i+1])[0]
                    shared[key]=(correlation(raw,y),correlation(np.where(self.mask[i],native[i],np.nan),y,True))
                    while len(shared)>300000:shared.popitem(last=False)
                else:shared.move_to_end(key)
                by_date[date]=shared[key]
        result=dict(by_date=by_date,coverage=float(np.mean(np.isfinite(native[self.mask])))if self.mask.any()else 0.)
        self.signature_cache[expr]=result
        return result

    def seat_loss(self,expr,j):
        try:
            signature=self.signature(expr)
            pairs=[signature['by_date'][p['exposure_date']]for p in self.seats[j]['points']]
            x=dict(ic=np.array([p[0]for p in pairs]),ric=np.array([p[1]for p in pairs]),coverage=signature['coverage'])
            target=self.target_rank[j];ic=self.target_ic[j]
            if len(target)and not np.isfinite(x['ric']).all():return 1e100
            loss=float(np.mean(((x['ric']-target)/.008)**2))if len(target)else 0.
            good=np.isfinite(ic)&np.isfinite(x['ic'])
            if good.any():loss+=float(np.mean(((x['ic'][good]-ic[good])/.015)**2))
            return loss+.008*expr.nodes+(1-x['coverage'])*10
        except (ValueError,FloatingPointError):return 1e100

    def monthly(self,held,legs):
        if not self.targets:return []  # Explicit holdings/IC-only diagnostic context.
        if not self.records:return []
        first=pd.Timestamp(self.records[0]['trade']);last=pd.Timestamp(self.evidence['last_local_date'])
        days=self.cal[(self.cal>=first)&(self.cal<=last)]
        trades={pd.Timestamp(r['trade']):i for i,r in enumerate(self.records)}
        ids=np.array([],int);old=set();daily=[]
        for day in days:
            p=self.cal.get_loc(day);turn=0.
            if day in trades:
                ids=held[trades[day]];new=set(ids)
                turn=.5 if not old else 1-len(new&old)/max(len(new),1);old=new
            if not len(ids):continue
            returns=self.market.prices[p].astype(float)/self.market.prices[p-1]-1
            r=float(np.nanmean(returns[ids]))
            b=self.market.benchmark[p]
            if not np.isfinite(r)or not np.isfinite(b):raise ValueError('Missing net daily ledger/benchmark')
            daily.append(dict(date=day.strftime('%Y%m%d'),p=r-.006*turn,b=float(b),turnover=turn))
        months=[]
        for month,target in self.targets.items():
            cutoff=self.evidence['cutoff'][month]
            rows=[d for d in daily if d['date']<=cutoff and d['date'][:6]==month.replace('-','')]
            if not rows:continue
            p=np.array([r['p']for r in rows]);b=np.array([r['b']for r in rows])
            rex=float((np.prod(1+p)/np.prod(1+b))**(252/len(rows))-1)
            sr=float(p.mean()/max(p.std(ddof=1),1e-12)*np.sqrt(252))if len(rows)>=2 else 0.
            nav=np.r_[1.,np.cumprod(1+p)];dd=float(np.max(1-nav/np.maximum.accumulate(nav)))
            turn=sum(r['turnover']for r in rows);c=max(rex,0)/max(turn,.30)*sr*(1-1.2*dd)
            seat_b=[]
            for j,seat in enumerate(self.seats):
                # The month profile identifies the actual scored roster. The
                # latest lifecycle can include tomorrow's replacements while
                # the published return cutoff still refers to yesterday.
                if month not in seat['A']:continue
                indices=[k for k,pt in enumerate(seat['points'])if pt['return_end_date']<=cutoff]
                if len(indices)<3:continue
                x=legs[j]['ric'][indices]*self.directions[j]
                if not np.isfinite(x).all():continue
                mu=x.mean();sd=x.std(ddof=1)
                seat_b.append(dict(id=seat['id'],score=float(abs(mu)*abs(mu/max(sd,1e-12))*np.mean(x>.02)),periods=len(x)))
            denominator=target.get('denominator_b',0)
            rawb=sum(x['score']for x in seat_b)/denominator if denominator else 0.
            months.append(dict(period=month,annual_rex=rex,annual_sr=sr,max_dd=dd,turn=turn,raw_c=c,
                raw_b=rawb,seat_b=seat_b,denominator_b=denominator,local_B_count=len(seat_b),
                daily=rows,public={k:target.get(k)for k in ['raw_a','raw_b','raw_c','annual_rex','annual_sr','max_dd','turn']},
                relative_delta={k:(v-target[k])/max(abs(target[k]),1e-8)for k,v in [('raw_b',rawb),('raw_c',c)]}))
        return months

    def evaluate(self,pool,details=False):
        pool=tuple(pool)
        if len(pool)!=self.seat_count:raise ValueError('Seat count differs from target')
        if pool in self.cache and not details:return self.cache[pool]
        self.evaluations+=1
        try:
            legs=[self.leg(x,j)for j,x in enumerate(pool)]
            errors={};all_ic=[];all_ric=[]
            for j,x in enumerate(legs):
                if len(self.target_rank[j]):
                    if not np.isfinite(x['ric']).all():raise ValueError('Nonfinite RankIC')
                    delta=x['ric']-self.target_rank[j];all_ric.extend(abs(delta));errors[f'seat{j}:RankIC']=float(np.mean((delta/.008)**2))
                good=np.isfinite(self.target_ic[j])
                if good.any():
                    if not np.isfinite(x['ic'][good]).all():raise ValueError('Nonfinite Pearson')
                    delta=x['ic'][good]-self.target_ic[j][good];all_ic.extend(abs(delta));errors[f'seat{j}:IC']=float(np.mean((delta/.015)**2))
            z=np.array([x['z']for x in legs]);active=self.active[:,:,None]
            denominator=np.maximum(self.active.sum(0),1)[:,None]
            composite=np.where(active,z,0).sum(0)/denominator
            held=[];checks=[]
            for r in self.records:
                i=self.index[pd.Timestamp(r['signal'])]
                chosen,check=holding_check(composite[i],self.mask[i],self.stocks,r);held.append(chosen);checks.append(check)
            if checks:
                errors['composite']=float(np.mean([(c['composite_rmse']or 2.)**2 for c in checks])/.05**2)
                errors['holdings']=float(np.mean([((1-c['overlap'])/.07)**2 for c in checks]))
            months=self.monthly(held,legs)
            for month in months:
                target=self.targets[month['period']]
                for key,scale,floor in [('raw_b',.02,.001),('raw_c',.06,.1),('turn',.04,.05),('annual_sr',.05,.1),('max_dd',.05,.003),('annual_rex',.04,.1)]:
                    errors[month['period']+':'+key]=((month[key]-target[key])/(max(abs(target[key]),floor)*scale))**2
            if self.use_A:
                # New but not-yet-effective seats have no B/holding influence;
                # their independently replayed A must still guide synthesis.
                from verify import A_for_grid
                cache=HERE/'A_cache';cache.mkdir(exist_ok=True)
                a_values={m:[]for m in self.targets}
                for j,(expr,seat)in enumerate(zip(pool,self.seats)):
                    for period,s in seat['A'].items():
                        if not s.get('counted'):continue
                        value=A_for_grid(self.market,expr,s['window_start'],s['window_end'],
                                         int(s['sample_count']),self.cycle,cache)
                        if value.get('s_i_a')is None:
                            errors[f'{period}:A_missing{j}']=1000.
                            continue
                        a_values[period].append(value['s_i_a'])
                        errors[f'{period}:A_seat{j}']=.05*((value['s_i_a']-s['s_i_a'])/(max(abs(s['s_i_a']),.0001)*.15))**2
                for period,values in a_values.items():
                    target=self.targets[period]
                    if len(values)==target['denominator_a']and values:
                        rawa=sum(values)/target['denominator_a']
                        errors[period+':raw_a']=((rawa-target['raw_a'])/(max(abs(target['raw_a']),.001)*.02))**2
                    else:errors[period+':A_count_mismatch']=1000.
            score=float(-.5*sum(errors.values())-.04*sum(x.nodes for x in pool))
            if not np.isfinite(score):raise ValueError('Nonfinite objective')
            row=dict(valid=True,score=score,pool=[x.json()for x in pool],formulas=[formula(x)for x in pool],
                directions=self.directions.tolist(),equal_seat_weights=True,target=self.evidence['target'],cycle=self.cycle,
                ic=[x['ic'].tolist()for x in legs],rank_ic=[x['ric'].tolist()for x in legs],
                ic_mae=float(np.mean(all_ic))if all_ic else None,ic_max=float(max(all_ic))if all_ic else None,
                rankic_mae=float(np.mean(all_ric))if all_ric else None,rankic_max=float(max(all_ric))if all_ric else None,
                checks=checks,months=months,components=errors,membership_mismatch=self.membership_mismatch,
                reconstructed=False,status='searching; A and all-board final verification pending',
                A_status='independent A guides this round'if self.use_A else'final A verification pending',
                search_objective_version='IC-holdings-ABC-v3-month-roster-B3'if self.use_A else'IC-holdings-BC-v3-month-roster-B3-bootstrap')
        except (ValueError,FloatingPointError)as exc:
            self.invalid+=1;score=-1e100;row=dict(valid=False,score=score,reason=str(exc),reconstructed=False)
        self.cache[pool]=score
        while len(self.cache)>12000:self.cache.popitem(last=False)
        if row['valid']and (self.best_row is None or score>self.best_row['score']):
            self.best,self.best_row=pool,row;self.atomic('best.json',row)
        if self.evaluations%20==0:self.atomic('progress.json',dict(pid=os.getpid(),evaluations=self.evaluations,invalid=self.invalid,
            best_score=self.best_row['score']if self.best_row else None,platform_compute=0,reconstructed=False))
        return row if details else score

    def likelihood(self,pool):return self.evaluate(pool)+.04*sum(x.nodes for x in pool)

    def enable_A(self):
        if self.use_A:return
        self.use_A=True;self.cache.clear();self.best_row=None
        self.evaluate(self.best,True)

    def gate(self,row):
        # Final gate also requires verify.py's A and boards. This stage never
        # declares success from clipped B/C scores or a favorable single board.
        return False
