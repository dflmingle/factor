"""Source-grounded additions and signed candidates, never target-valued leaves.

Factor names are hypotheses, not proof of the opponent's private formula.
DAVOL definition comes from the local platform manual. Alpha191 definitions
come from the archived reference; its 010 MAX ambiguity is explicitly retained.
"""
import re
from grammar import field,const,op,validate

C,O,H,L,A,V,T,M=[field(k)for k in ('close','open','high','low','amount','volume','turnover','cap')]
R=lambda x:op('rank',x)
Z=lambda x:op('zscore',x)
MA=lambda x,n:op('ts_mean',x,window=n)
SD=lambda x,n:op('ts_std',x,window=n)
D=lambda x,n:op('delay',x,window=n)
DIV=lambda x,y:op('div',x,y)
RET=lambda n:op('sub',DIV(C,D(C,n)),const(1))
REV=lambda n:op('neg',RET(n))
LV=lambda n:op('neg',SD(RET(1),n))
LOWT=lambda n:op('neg',MA(T,n))
VWAP=DIV(op('mul',const(10),A),V)


def signed(xs):
    result=[]
    for x in xs:
        for y in [x,op('neg',x)]:
            try:validate(y)
            except ValueError:continue
            result.append(y)
    return list(dict.fromkeys(result))


def alpha191(which):
    if which==10:
        branch=op('where',op('less2',RET(1),const(0)),SD(RET(1),20),C)
        square=op('mul',branch,branch)
        return [R(op('max2',square,const(5))),R(op('ts_max',square,window=5))]
    if which==120:return [DIV(R(op('sub',VWAP,C)),R(op('add',VWAP,C)))]
    if which==124:
        return [DIV(op('sub',C,VWAP),op('decaylinear',R(op('ts_max',C,window=30)),window=2))]
    if which==140:
        spread=op('sub',op('add',R(O),R(L)),op('add',R(H),R(C)))
        first=R(op('decaylinear',spread,window=8))
        corr=op('ts_corr',op('ts_rank',C,window=8),op('ts_rank',MA(V,60),window=20),window=8)
        second=op('ts_rank',op('decaylinear',corr,window=7),window=3)
        return [op('min2',first,second),first]
    if which==42:return [op('neg',op('mul',R(SD(H,10)),op('ts_corr',H,V,window=10)))]
    return []


def additions():
    xs=[]
    for n in [3,5,10,14,20,21,28,30,40,60,90,120,150,180,252]:
        xs += [DIV(MA(T,n),MA(T,120)),DIV(SD(C,n),MA(C,n)),
               DIV(MA(V,5),MA(V,n)),DIV(MA(A,5),MA(A,n)),
               DIV(MA(T,5),MA(T,n)),DIV(V,D(V,n)),
               DIV(op('sub',C,MA(C,n)),SD(C,n)),
               op('ts_mean',op('less2',RET(1),const(0)),window=n),
               DIV(op('sub',C,D(C,n)),op('ts_sum',op('abs',op('sub',C,D(C,1))),window=n)),
               DIV(MA(SD(RET(1),120),n),SD(RET(1),120)),
               SD(SD(RET(1),120),n)]
    for n in [5,20,40,60,120]:
        for m in [20,60]:
            xs += [op('mul',R(REV(n)),R(LV(m))),
                   op('mul',R(REV(n)),R(LOWT(m))),
                   op('add',Z(REV(n)),Z(LV(m))),
                   DIV(field('bm'),op('add',const(1),R(RET(n)))),
                   op('mul',op('mul',R(field('bm')),R(REV(n))),R(LV(m)))]
    for n in [5,10,20,60]:
        for long in [120,252,504,756]:
            xs += [DIV(SD(T,n),SD(T,long)),DIV(SD(V,n),SD(V,long)),
                   DIV(MA(T,n),MA(T,long))]
    for k in [10,120,124,140,42]:
        for base in alpha191(k):
            xs.append(base)
            # Low-turnover transformations used as hypotheses, not recovered
            # formula assertions. All ranks are same-date cross-sections.
            for low in [op('sub',const(1),R(T)),op('sub',const(1),R(MA(T,20)))]:
                xs += [op('mul',R(base),low),op('add',R(base),low)]
    return signed(xs)


def named(seat):
    n=seat['name'].lower();xs=[]
    windows=[int(v)for v in re.findall(r'(?:rev|reversal|mom|vol|turn|corr|skew|kurt|bias|mean|ma)[_ -]?(\d+)',n)]
    windows=[v for v in windows if 1<=v<=120 or v in [180,252,504,756]]or[20]
    for w in windows:
        if any(k in n for k in ['mom','rev','反转','动量']):xs += [RET(w),REV(w)]
        if any(k in n for k in ['vol','波动']):xs += [SD(RET(1),w),LV(w)]
        if any(k in n for k in ['turn','换手']):xs += [MA(T,w),LOWT(w)]
        if any(k in n for k in ['corr','相关']):xs += [op('ts_corr',C,V,window=w),op('ts_corr',RET(1),V,window=w)]
        if 'skew'in n:xs += [op('ts_skew',RET(1),window=w)]
        if 'kurt'in n:xs += [op('ts_kurt',RET(1),window=w)]
    if 'davol'in n:
        w=20 if '20'in n else 5
        xs += [DIV(MA(T,w),MA(T,120)),op('sub',MA(T,w),MA(T,120))]
    if any(k in n for k in ['布林带宽','boll_width']):xs += [DIV(SD(C,20),MA(C,20))]
    if 'negvol120s20'in n:xs += [op('neg',MA(SD(RET(1),120),20)),op('neg',SD(SD(RET(1),120),20))]
    if 'pvcorr10'in n:xs += [op('ts_corr',C,V,window=10),op('neg',op('ts_corr',C,V,window=10))]
    if 'ep-size'in n:
        xs += [op('add',Z(field('ep')),Z(op('neg',M))),op('mul',R(field('ep')),R(op('neg',M)))]
    if 'rev60_lv60'in n:xs += [op('mul',R(REV(60)),R(LV(60))),op('add',Z(REV(60)),Z(LV(60)))]
    if 'val_rev'in n:xs += [op('mul',R(field('bm')),R(REV(20)))]
    if 'amtrev'in n:xs += [DIV(MA(A,5),MA(A,20)),DIV(A,D(A,20))]
    if '成交量变化'in n:xs += [DIV(V,D(V,20)),op('sub',DIV(V,D(V,20)),const(1))]
    for k in [10,120,124,140,42]:
        if f'alpha191_{k:03d}'in n:xs += alpha191(k)
    return signed(xs)


PROVENANCE=dict(
    davol='vendor/skill-pandaai-factor-online/references/fields-ma-indicators.md: VOLN/VOL120',
    alpha191='.cache/third_party/alpha191_reference.py:010,120,124,140,042; 010 MAX ambiguity retained',
    opponent_names='public/players/*/*.json, hypotheses only; private source unconfirmed',
    source_version='signed-source-hypotheses-v1',causal=True,target_terminals=False)
