"""Independent per-leg five-year A, all boards and reference-level acceptance."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engine import correlation
from objective import clean

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent
PUBLIC=PARENT/'public'
FROZEN=HERE.parents[3]/'research_reports/platform_alignment/peer-evidence-continuation-20261013/advanced_search_v2/expression_tree_upgrade/refinement_v2/platform_confirmation_20261013'


def reference():
    r=json.loads((FROZEN/'frozen_best.json').read_text())
    a=json.loads((PARENT/'peer1_fiveleg_A_v1/comparison.json').read_text())
    board=json.loads((PARENT/'不知所云队-全榜对照.json').read_text())
    lookup={x['metric']:x for x in board['metrics']}
    return dict(reference='F-PC1013-01 frozen reconstruction of 不知所云队',
        ic_mae=float(np.mean(r['ic_abs_error'])),ic_max=float(np.max(r['ic_abs_error'])),
        rankic_mae=float(np.mean(r['rankic_abs_error'])),rankic_max=float(np.max(r['rankic_abs_error'])),
        min_holdings_overlap=min(x['overlap']for x in r['checks']),
        mean_holdings_overlap=float(np.mean([x['overlap']for x in r['checks']])),
        top1_fraction=float(np.mean([x['top1_exact']for x in r['checks']])),
        missing_numeric_fraction=sum(x['missing_numeric_predictions']for x in r['checks'])/sum(x['numeric_labels']for x in r['checks']),
        composite_observed_rmse_max=max(x['observed_composite_rmse']for x in r['checks']),
        raw_b_relative=max(abs(m['relative_delta']['raw_b'])for m in r['months']),
        raw_c_relative=max(abs(m['relative_delta']['raw_c'])for m in r['months']),
        raw_a_relative=abs(a['aggregate']['peer_A_inferred_return_end_grid_proxy']['relative_raw_a_gap']),
        rex_relative=abs(lookup['超额榜分数（年化超额均值）']['relative_delta']),
        robust_relative=abs(lookup['稳健榜分数']['relative_delta']),
        quality_relative=abs(lookup['质量榜分数（对手窗口日期代理）']['relative_delta']),
        points_relative=abs(lookup['综合积分（对手窗口日期代理）']['relative_delta']),
        scope='same relative-error level as accepted reference; identification not claimed; all public dates retrospectively fitted')


def mean(values):
    x=[v for v in values if v is not None and np.isfinite(v)]
    return float(np.mean(x))if x else None


def relative(x,y,floor=1e-8):return abs(x-y)/max(abs(y),floor)if x is not None and y is not None else None


def A_for_grid(market,expr,start,end,count,cycle,cache):
    key=hashlib.sha256((expr.key()+f'|{start}|{end}|{count}|{cycle}|return-end-v3-valid-count-const64').encode()).hexdigest()
    path=cache/(key+'.json')
    if path.exists():return json.loads(path.read_text())
    lo,hi=market.cal.get_indexer([pd.Timestamp(start),pd.Timestamp(end)])
    if lo<0 or hi<0 or hi<lo:
        return dict(status='missing historical calendar')
    ends=np.arange(lo,hi+1,cycle)
    if len(ends)<count or ends[-1]!=hi or np.min(ends)-cycle-1<0:
        return dict(status='public endpoints/count do not identify cadence',expected_count=count,grid_count=len(ends))
    signals=ends-cycle-1;native=market.engine.evaluate(expr);rics=[];ics=[]
    for p,endpos in zip(signals,ends):
        y=market.prices[endpos].astype(float)/market.prices[p+1]-1
        f=np.where(market.capmask[p],native[p],np.nan)
        ric=correlation(f,y,True);ic=correlation(f,y)
        if np.isfinite(ric):rics.append(ric);ics.append(ic)
    if len(rics)<2:return dict(status='insufficient valid five-year IC')
    if len(rics)!=count:
        return dict(status='candidate valid IC count differs from public count',expected_count=count,
                    grid_count=len(ends),valid_count=len(rics))
    x=np.array(rics);mu=float(x.mean());sd=float(x.std(ddof=1));ir=mu/max(sd,1e-12)
    win=float(np.mean(np.sign(mu)*x>.02));si=abs(mu)*abs(ir)*win
    out=dict(status='local A proxy; public endpoint return-date role inferred',sample_count=len(x),
        ic_mean=mu,icir=ir,ic_win_rate=win,s_i_a=si,pearson_ic=mean(ics),
        first_signal=market.cal[signals[0]].strftime('%Y%m%d'),last_signal=market.cal[signals[-1]].strftime('%Y%m%d'),
        public_window_start=start,public_window_end=end,expected_sample_count=count,date_role_confirmed=False,
        rule_reference=market.context['rule_reference'],financial_proxy=bool(expr.fields & {'bm','ep','cfp','sp','roe','gm','roic','leverage','assets_growth','current_ratio'}))
    path.write_text(json.dumps(clean(out),ensure_ascii=False,indent=2)+'\n')
    return out


def verify(e,row=None):
    row=e.evaluate(e.best,True)if row is None else row
    if not row.get('valid'):return row
    cache=HERE/'A_cache';cache.mkdir(exist_ok=True)
    seatA=[];months=[];missing=[]
    for j,(expr,seat)in enumerate(zip(e.best,e.seats)):
        bymonth={}
        for period,s in seat['A'].items():
            if not s.get('counted'):
                continue
            r=A_for_grid(e.market,expr,s['window_start'],s['window_end'],int(s['sample_count']),e.cycle,cache)
            bymonth[period]=dict(local=r,public=s)
            if r.get('s_i_a')is None:missing.append(dict(seat_id=seat['id'],period=period,reason=r['status']))
        seatA.append(dict(seat_id=seat['id'],name=seat['name'],formula=row['formulas'][j],by_month=bymonth))
    for m in row['months']:
        p=m['period'];target=e.targets[p]
        counted=[s['by_month'][p]['local'].get('s_i_a')for s in seatA if p in s['by_month']]
        if counted and all(v is not None for v in counted)and len(counted)==target['denominator_a']:
            rawa=sum(counted)/target['denominator_a']
            na=min(max(rawa/target['anchor_a'],0),target['new_pool_cap'])
        else:rawa=None;na=None
        nb=min(max(m['raw_b']/target['anchor_b'],0),1)
        nc=min(max(m['raw_c']/target['anchor_c'],0),1)
        comb=.2*na+.35*nb+.45*nc if na is not None else None
        points=min(40000.,40000*comb*target['newbie_factor']*target['decay'])if comb is not None else None
        months.append(dict(**m,raw_a=rawa,na=na,nb=nb,nc=nc,comb=comb,points=points,
            raw_a_relative=relative(rawa,target['raw_a']),
            raw_b_relative=relative(m['raw_b'],target['raw_b'],.001),
            raw_c_relative=relative(m['raw_c'],target['raw_c'],.1)))
    pool=e.evidence['target']['pool_id']
    boards={}
    for k in ['quality','rex','robust','points']:
        b=json.loads((PUBLIC/'boards'/f'{k}.json').read_text())
        boards[k]=next((r for r in b['rows']if r['pool_id']==pool),{})
    quality=mean([m['na']+m['nb']if m['na']is not None else None for m in months])
    rex=mean([m['annual_rex']for m in months]);sr=mean([m['annual_sr']for m in months])
    dd=max((m['max_dd']for m in months),default=None)
    robust=sr-2*dd if sr is not None and dd is not None else None
    points=sum(m['points']for m in months)if len(months)==2 and all(m['points']is not None for m in months)else None
    boardcomparison={k:dict(local=v,public=boards[k].get('score'),relative_error=relative(v,boards[k].get('score')))
                     for k,v in [('quality',quality),('rex',rex),('robust',robust),('points',points)]}
    ref=reference();checks=row['checks'];tot=sum(c['numeric_labels']for c in checks)
    actual=dict(ic_mae=row['ic_mae'],ic_max=row['ic_max'],rankic_mae=row['rankic_mae'],rankic_max=row['rankic_max'],
        min_holdings_overlap=min((c['overlap']for c in checks),default=None),
        mean_holdings_overlap=mean([c['overlap']for c in checks]),top1_fraction=mean([float(c['top1_exact'])for c in checks]),
        missing_numeric_fraction=sum(c['missing_numeric_predictions']for c in checks)/tot if tot else None,
        composite_observed_rmse_max=max((c['observed_composite_rmse']for c in checks if c['observed_composite_rmse']is not None),default=None),
        raw_a_relative=max((m['raw_a_relative']for m in months if m['raw_a_relative']is not None),default=None),
        raw_b_relative=max((m['raw_b_relative']for m in months),default=None),
        raw_c_relative=max((m['raw_c_relative']for m in months),default=None),
        **{k+'_relative':boardcomparison[k]['relative_error']for k in boardcomparison})
    failures=[]
    for key,value in actual.items():
        if value is None:failures.append(dict(metric=key,reason='evidence missing'));continue
        limit=ref[key]
        larger=key in ['min_holdings_overlap','mean_holdings_overlap','top1_fraction']
        if (value<limit-1e-8 if larger else value>limit+1e-8):failures.append(dict(metric=key,actual=value,limit=limit))
    if len(months)!=2:failures.append(dict(metric='month_coverage',reason='monthly ledger incomplete'))
    if e.membership_mismatch:failures.append(dict(metric='historical_seat_membership',reason='not fully reconstructed',details=e.membership_mismatch))
    if missing:failures.append(dict(metric='A_coverage',reason='missing/incompatible dates',details=missing))
    if any(s['revision_conflicts']for s in e.seats):failures.append(dict(metric='revision_consistency',reason='public path revisions unresolved'))
    passed=not failures
    result=dict(**{k:v for k,v in row.items()if k not in ['months','status','A_status']},
        months=months,seat_A=seatA,boards=boardcomparison,acceptance=dict(reference=ref,actual=actual,failures=failures,passed=passed),
        A_status='independent five-year legs; target-date role proxy',
        status='达到不知所云队的本地接近程度；平台确认待批准'if passed else '继续搜索，未达到参照标准',
        platform_confirmed=False,exact_identity_confirmed=False,public_date_role_confirmed=False)
    e.atomic('verified_best.json',result)
    e.atomic('verification_status.json',dict(target=e.evidence['target'],passed=passed,status=result['status'],
        failures=failures,actual=actual,evaluations=e.evaluations,platform_compute=0))
    lines=[f"# {e.evidence['target']['display_name']}：复刻档案",'',result['status'],'',
        f"综合积分名次 {e.evidence['target']['rank']}，周期 {e.cycle} 日，历史与现役合计 {e.seat_count} 个因子版本。",'',
        '## 候选公式','', '|因子|方向|候选|','|---|---|---|']
    for s,f in zip(e.seats,row['formulas']):lines.append(f"|{s['name']}|{s['direction']}|`{f}`|")
    lines+=['','## 各榜误差','','|榜单|本地代理|对手|相对绝对差|','|---|---:|---:|---:|']
    for k,b in boardcomparison.items():
        v='待核验'if b['local']is None else f"{b['local']:.9f}"
        er='待核验'if b['relative_error']is None else f"{b['relative_error']:.4%}"
        lines.append(f"|{k}|{v}|{b['public']}|{er}|")
    lines+=['','所有公开日期已参与回顾性搜索；财务字段和平台内部执行是代理。五年A按每条腿独立计算，公开端点日期角色按收益结束日推算，尚未确认。近期指标与五年A分别保存。当前未创建平台因子或运行付费回测。', '',
            '逐期误差、持仓、月度账本和未通过项见 verified_best.json。']
    (e.out/'README.md').write_text('\n'.join(lines)+'\n')
    return result
