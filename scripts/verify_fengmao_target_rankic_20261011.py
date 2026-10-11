"""Independent pandas score/decile audit and actual-input prefix checks."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
import json
from pathlib import Path
import threading
import time
import numpy as np
import pandas as pd
import fengmao_target_rankic_20261011 as task

OUT = task.OUT


def independent_periods():
    stats = pd.read_csv(OUT/'results.csv')
    maximum,checked = 0.,0
    deciles,years,gaprows = [],[],[]
    for i in range(1,4):
        name = f'FM_TARGET_{i:02d}'
        for family in ('target','formal'):
            axes = json.loads((OUT/('axes.json' if family=='target' else 'axes_formal.json')).read_text(encoding='utf8'))
            dates = pd.DatetimeIndex(axes['dates'])
            with np.load(OUT/('atoms.npz' if family=='target' else 'atoms_formal.npz')) as saved:
                y,cap = saved['target'],saved['market_cap']
            x = np.load(OUT/f'{name}_{family}_signals.npy')
            windows = (['target_119_fit','target_first80_diagnostic','target_last39_diagnostic'] if family=='target' else ['formal_5y','recent_2026'])
            for window in windows:
                p = pd.read_csv(OUT/f'{name}_{window}_periods.csv')
                prev = {}
                group_rows = []
                independent_rho = []
                for row in p.itertuples():
                    at = dates.get_loc(pd.Timestamp(row.date))
                    valid = np.isfinite(x[at])&np.isfinite(y[at])&np.isfinite(cap[at])
                    ids = np.flatnonzero(valid)
                    xx,yy = pd.Series(x[at,ids],index=ids,dtype=float),pd.Series(y[at,ids],index=ids,dtype=float)
                    ic,rho = xx.corr(yy),xx.corr(yy,method='spearman')
                    independent_rho.append(rho)
                    maximum = max(maximum,abs(ic-row.ic),abs(rho-row.rank_ic))
                    assert len(ids)==row.stocks
                    assert abs(ic-row.ic)<1e-8 and abs(rho-row.rank_ic)<1e-8
                    bucket = np.ceil(xx.rank(method='first')*10/len(xx)).clip(1,10).astype(int)
                    for group in range(1,11):
                        members = set(bucket.index[bucket.eq(group)])
                        turn = np.nan if group not in prev else 1-len(members&prev[group])/len(members)
                        prev[group] = members
                        gross = float(yy.loc[list(members)].mean()-yy.mean())
                        group_rows.append(dict(candidate=name,window=window,date=row.date,group=group,
                                               gross_excess=gross,turnover=turn,stocks=len(members)))
                        if group==10:
                            assert abs(gross-row.gross_excess)<1e-10
                            assert (np.isnan(turn) and np.isnan(row.turnover)) or abs(turn-row.turnover)<1e-12
                    checked += 1
                s = stats[(stats.candidate==name)&(stats.window==window)].iloc[0]
                rho = np.array(independent_rho)
                rankmean,ir,win = rho.mean(),rho.mean()/rho.std(ddof=0),float(np.mean(rho>.02))
                assert abs(rankmean-s.rank_ic)<1e-8 and abs(ir-s.rank_ic_ir)<1e-7
                assert abs(win-s.rank_ic_win)<1e-12
                assert abs(abs(rankmean*ir)*win-s.s_i_rank)<1e-7
                group_table = pd.DataFrame(group_rows)
                group_table.to_csv(OUT/f'{name}_{window}_group_periods.csv',index=False)
                for group,g in group_table.groupby('group'):
                    gross,turn = float(g.gross_excess.mean()*25.2),float(g.turnover.mean())
                    net = gross-turn*.006*25.2
                    deciles.append(dict(candidate=name,window=window,group=int(group),gross_excess=gross,
                                        turnover=turn,net_excess=net))
                    if group==10:
                        assert abs(net-s.net_excess)<1e-10 and abs(turn-s.turnover)<1e-12
                if window=='target_119_fit':
                    metric = np.array([rankmean,ir,win])
                    target = task.TARGET
                    gaprows.append(dict(candidate=name,rank_ic=rankmean,rank_ic_ir=ir,rank_ic_win=win,
                        rank_ic_error=rankmean-target[0],ir_error=ir-target[1],win_error=win-target[2],
                        wins=int(np.sum(rho>.02)),periods=len(rho),s_i=abs(rankmean*ir)*win,
                        scaled_distance=float(np.sum(((metric-target)/task.SCALE)**2)),
                        near_target=bool(abs(rankmean-target[0])<=.001 and abs(ir-target[1])<=.01 and np.sum(rho>.02)==111),
                        same_at_six_decimals=bool(np.array_equal(np.round(metric,6),np.round(target,6)))))
                    for year,b in p.groupby(p.date.str[:4]):
                        r = b.rank_ic.to_numpy()
                        years.append(dict(candidate=name,year=year,periods=len(b),rank_ic=float(r.mean()),
                            rank_ic_ir=float(r.mean()/r.std(ddof=0)),win=float(np.mean(r>.02)),
                            net_excess=float(b.gross_excess.mean()*25.2-b.turnover.mean()*.006*25.2)))
            if family=='target':
                top = pd.read_csv(OUT/f'{name}_top20.csv')
                for day,b in top.groupby('date'):
                    at = dates.get_loc(pd.Timestamp(day))
                    ids = np.flatnonzero(np.isfinite(x[at]))
                    selected = pd.Series(x[at,ids],index=ids).sort_values(ascending=False,kind='stable').index[:20]
                    assert b.symbol.tolist()==[axes['symbols'][j] for j in selected]
    pd.DataFrame(deciles).to_csv(OUT/'deciles.csv',index=False)
    pd.DataFrame(years).to_csv(OUT/'years_target.csv',index=False)
    pd.DataFrame(gaprows).to_csv(OUT/'target_errors.csv',index=False)
    return dict(status='passed',period_records=checked,summary_rows=len(stats),correlation_max_delta=maximum,
                independent_pandas_rankic_population_IR_and_win=True,top20_groups_turnover_cost=True)


def raw_check():
    base = task.base
    axes = json.loads((OUT/'axes.json').read_text(encoding='utf8'))
    symbols = pd.Index([axes['symbols'][i] for i in np.linspace(0,len(axes['symbols'])-1,100,dtype=int)])
    dates = pd.DatetimeIndex(axes['dates'])
    cache = base.CACHE
    f = pd.concat([pd.read_parquet(p,columns=['trade_date','is_open']) for p in (cache/'trade_calendar').glob('*.parquet')],ignore_index=True)
    d = pd.to_datetime(f.trade_date.astype(str),format='mixed').dt.normalize()
    cal = pd.DatetimeIndex(sorted(d[f.is_open.eq(1)&d.between('2018-01-01','2026-09-07')].unique()))
    pos = cal.get_indexer(dates)
    assert np.array_equal(np.diff(pos),np.full(118,10))
    fields = {k:np.full((len(cal),100),np.nan,np.float32) for k in ('close','volume','turnover','cap')}
    filters = [('instrument','in',symbols.tolist())]
    for p in sorted((cache/'tushare_factor_recheck/qfq/daily_batches').glob('batch_*.parquet')):
        base.memory_guard()
        f = pd.read_parquet(p,columns=['date','instrument','close','volume'],filters=filters)
        di,si = cal.get_indexer(pd.to_datetime(f.date).dt.normalize()),symbols.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)
        for k in ('close','volume'):
            fields[k][di[ok],si[ok]] = f[k].to_numpy(np.float32)[ok]
    for i,p in enumerate(sorted((cache/'tushare_factor_recheck/daily_basic_full_a').glob('daily_basic_*.parquet'))):
        base.memory_guard()
        f = pd.read_parquet(p,columns=['date','instrument','total_mv','turnover'],filters=filters)
        di,si = cal.get_indexer(pd.to_datetime(f.date).dt.normalize()),symbols.get_indexer(f.instrument)
        ok = (di>=0)&(si>=0)&f.total_mv.gt(0).to_numpy()&f.turnover.notna().to_numpy()
        for k,col in (('cap','total_mv'),('turnover','turnover')):
            fields[k][di[ok],si[ok]] = f[col].to_numpy(np.float32)[ok]
        if (i+1)%600==0:
            print('raw audit daily_basic',i+1,flush=True)
    active = np.isfinite(fields['cap'])
    for k in ('close','volume'):
        fields[k][~active|(fields[k]<=0)] = np.nan
    fields['close'] = pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    task.new.load_open(cal,symbols,fields,filters)
    ids = pd.Index(axes['symbols']).get_indexer(symbols)
    with np.load(OUT/'atoms.npz') as saved:
        y = fields['close'][pos+11].astype(float)/fields['close'][pos+1].astype(float)-1
        assert np.allclose(y,saved['target'][:,ids],equal_nan=True,rtol=0,atol=1e-12)
        assert np.array_equal(fields['cap'][pos],saved['market_cap'][:,ids],equal_nan=True)
    def build(f,p):
        a = base.build_atoms(f,p)
        a.update(task.old.long_atoms(f,p));a.update(task.new.build_new_atoms(f,p))
        return a
    full = build(fields,pos)
    models = json.loads((OUT/'models_frozen.json').read_text(encoding='utf8'))
    rows = []
    for cutoff in ('2024-06-28','2025-06-30'):
        end = int(cal.searchsorted(pd.Timestamp(cutoff),side='right'))
        mask = dates<=cal[end-1]
        cut = build({k:v[:end] for k,v in fields.items()},pos[mask])
        cells = 0
        for k in full:
            assert np.array_equal(full[k][mask],cut[k],equal_nan=True),k
            cells += int(np.isfinite(cut[k]).sum())
        for m in models:
            assert np.array_equal(task.model_value(m,full)[mask],task.model_value(m,cut),equal_nan=True)
        rows.append(dict(cutoff=cutoff,status='passed',stocks=100,atoms=len(full),atom_cells=cells,
                         models=len(models),historical_max_difference=0))
        print('raw input prefix PASS',cutoff,flush=True)
        del cut
        gc.collect()
    task.save('raw_causality_checks.json',dict(status='passed',checks=rows,label1_cap_parity=True,
        limit='100-stock input-causality sample, same-date ranks recomputed within sample; not proof of full-A new-atom parity or model generalization'))
    return dict(status='passed',stocks=100,cutoffs=2,atoms=len(full),memory=dict(base.PEAK))


def report():
    errors = pd.read_csv(OUT/'target_errors.csv')
    results = pd.read_csv(OUT/'results.csv')
    models = json.loads((OUT/'models_frozen.json').read_text(encoding='utf8'))
    meta = json.loads((OUT/'metadata.json').read_text(encoding='utf8'))
    audit = json.loads((OUT/'verification.json').read_text(encoding='utf8'))
    lines = ['# 疯猫公开RankIC目标：数值拟合结果','',
        '目标 xplr-d3c-r6-grpvol：RankIC .1722791715386185、RankIC IR 1.6613206049954048、胜率111/119=.9327731092436975、S_i .2669698660608367。此前将其解释为Pearson IC的比较无效；本轮按项目已验证的竞技场RankIC规则更正。','',
        f'本轮两seed遗传树搜索记录 {meta["unique_formulas"]} 个唯一表达式（{meta["valid_formulas"]} 有效），另384次稀疏混合CEM。平台算力0。搜索/评估 {meta["seconds"]/60:.1f} 分钟，独立核验 {audit["seconds"]/60:.1f} 分钟。','',
        f'三个冻结候选：**六位小数一致 {int(errors.same_at_six_decimals.sum())}/3，预声明近似门槛通过 {int(errors.near_target.sum())}/3**。只有数字全部达到标准才称近似匹配；不能用训练收益替代目标。','',
        '| 模型 | RankIC | IR(RankIC) | 胜率 | S_i | RankIC差 | IR差 | 胜率差 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in errors.itertuples():
        lines.append(f'| {r.candidate} | {r.rank_ic:.6f} | {r.rank_ic_ir:.6f} | {r.wins}/119 ({r.rank_ic_win:.4%}) | {r.s_i:.6f} | {r.rank_ic_error:+.6f} | {r.ir_error:+.6f} | {r.win_error:+.4%} |')
    lines += ['', '全部119期参与了目标拟合，所以前80/后39期和分年表是拟合内诊断，不是独立样本外。仅汇总值不足以恢复原公式/逐股票信号；即便匹配，也只能说数字匹配。胜率不能靠改变阈值、丢掉亏损期或缩窄股票池制造。','',
        '日期为2021-09-17起每10本地交易日，最后2026-08-06、退出2026-08-21，恰119期。中间日期是推定，不是对手已保存逐期日期。标签与行情口径固定，正式近五年20210907..20260907的120期H03模板结果独立保存，近期2026单独保存；未混排。','',
        '| 模型 | 目标119期净超额 | 正式五年净超额 | 2026近期净超额 | 目标绝对size相关 |','|---|---:|---:|---:|---:|']
    for name in errors.candidate:
        r = results[results.candidate.eq(name)].set_index('window')
        lines.append(f'| {name} | {r.loc["target_119_fit"].net_excess:.2%} | {r.loc["formal_5y"].net_excess:.2%} | {r.loc["recent_2026"].net_excess:.2%} | {r.loc["target_119_fit"].abs_size_corr:.3f} |')
    lines += ['', '冻结公式/组合：','']
    for i,m in enumerate(models,1):
        lines.append(f'FM_TARGET_{i:02d}，{m["engine"]}：')
        lines.append('')
        if 'formula' in m:
            lines += [f'`{m["formula"]}`','']
        else:
            for c in m['components']:
                lines.append(f'- {c["weight"]:+.8f} × RANK(`{c["formula"]}`)')
            lines.append('')
    lines += [f'独立pandas核验 {audit["periods"]["period_records"]} 条逐期/15行汇总、十组成员/换手/成本与Top20。RankIC目标指标使用总体std（ddof=0），Pearson IC列仅诊断。真实日度输入在100只固定股票、两个截断点重算全部60原子及冻结模型，历史掩码和值差异0。该检查不证明全样本拟合参数在过去可知；候选筛选本身使用了全窗口标签，仍有过拟合。','',
        f'峰值RSS {meta["memory"]["rss_gb"]:.3f} GiB，私有内存 {meta["memory"]["private_gb"]:.3f} GiB，最低可用 {meta["memory"]["min_available_gb"]:.3f} GiB；2.25GiB/1.25GiB watchdog未触发。全A、qfq、total_mv、20180101暖机、label-1、10组、factor_valid、算术年化、0.30%单边；代理规则未改。','',
        ('本轮仍未复现同样数值。记录最接近结果和逐项差距，不声称成功，不提交平台或改池。' if not errors.near_target.any() else
         '出现近似匹配的数值，但仍须独立历史留出、平台确认和池级决策；本轮不自动提交或改池。'),'']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf8')
    print(errors.to_string(index=False))


def main():
    started = time.monotonic()
    task.base.OUT = OUT
    threading.Thread(target=task.base.watchdog,daemon=True).start()
    periods = independent_periods()
    raw = raw_check()
    task.save('verification.json',dict(status='passed',periods=periods,raw_causality=raw,
        seconds=time.monotonic()-started,metric='RankIC; population IR; threshold .02',
        limit='all target periods fitted; temporal slices not out-of-sample'))
    task.base.DONE.set()
    report()
    print('INDEPENDENT AUDIT AND REPORT COMPLETE')


if __name__=='__main__':
    main()
