"""Audit saved global-model numerical-fit results, without refitting."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import hashlib
import json
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import fengmao_target_ml_20261011 as task


def main():
    started = time.monotonic()
    out,source = task.OUT,task.SOURCE
    meta = json.loads((out/'metadata.json').read_text(encoding='utf8'))
    source_audit = json.loads((source/'verification.json').read_text(encoding='utf8'))
    assert source_audit['status']=='passed' and source_audit['raw_causality']['status']=='passed'
    checksum = hashlib.sha256((out/'model.pkl').read_bytes()).hexdigest()
    assert checksum==meta['checkpoint_sha256']
    with (out/'model.pkl').open('rb') as f:
        bundle = pickle.load(f)
    axes = json.loads((source/'axes.json').read_text(encoding='utf8'))
    dates = pd.DatetimeIndex(axes['dates'])
    statsrows,groups,years = [],[],[]
    checks = []
    for family in ('target','formal'):
        name = 'atoms.npz' if family=='target' else 'atoms_formal.npz'
        with np.load(source/name) as saved:
            atoms = {k:saved[k] for k in saved.files if k not in ('target','market_cap')}
            y,cap = saved['target'],saved['market_cap']
        daylist = dates if family=='target' else pd.DatetimeIndex(json.loads((source/'axes_formal.json').read_text(encoding='utf8'))['dates'])
        with threadpool_limits(limits=1):
            x = task.predict(bundle,atoms)
        if family=='target':
            cached = np.load(out/'FM_ML_target_signals.npy')
            assert np.array_equal(x,cached,equal_nan=True)
        else:
            np.save(out/'FM_ML_formal_signals.npy',x)
        for cutoff in ('2024-06-28','2025-06-30'):
            mask = daylist<=pd.Timestamp(cutoff)
            with threadpool_limits(limits=1):
                truncated = task.predict(bundle,{k:v[mask] for k,v in atoms.items()})
            assert np.array_equal(x[mask],truncated,equal_nan=True)
            checks.append(dict(family=family,cutoff=cutoff,cells=int(np.isfinite(truncated).sum()),max_difference=0,
                               scope='frozen predictor; upstream real-input raw audit separately proves atom prefix invariance'))
        windows = [('target_119_fit',np.ones(len(daylist),bool))] if family=='target' else [
            ('formal_5y',np.ones(len(daylist),bool)),('recent_2026',daylist>='2026-01-01')]
        for window,mask in windows:
            periods,prev,detail = [],{},[]
            for at in np.flatnonzero(mask):
                valid = np.isfinite(x[at])&np.isfinite(y[at])&np.isfinite(cap[at])
                ids = np.flatnonzero(valid)
                xx,yy = pd.Series(x[at,ids],index=ids,dtype=float),pd.Series(y[at,ids],index=ids,dtype=float)
                ic,rho = xx.corr(yy),xx.corr(yy,method='spearman')
                bucket = np.ceil(xx.rank(method='first')*10/len(xx)).clip(1,10).astype(int)
                topturn,topgross = None,None
                for group in range(1,11):
                    members = set(bucket.index[bucket.eq(group)])
                    turn = np.nan if group not in prev else 1-len(members&prev[group])/len(members)
                    gross = float(yy.loc[list(members)].mean()-yy.mean())
                    prev[group] = members
                    detail.append(dict(date=str(daylist[at].date()),group=group,gross_excess=gross,turnover=turn))
                    if group==10:
                        topturn,topgross = turn,gross
                periods.append(dict(date=str(daylist[at].date()),rank_ic=rho,ic=ic,turnover=topturn,gross_excess=topgross,
                    size_corr=xx.corr(pd.Series(cap[at,ids],index=ids),method='spearman')))
            p = pd.DataFrame(periods)
            p.to_csv(out/f'FM_ML_{window}_independent_periods.csv',index=False)
            r = p.rank_ic.to_numpy()
            rankmean,ir,win = float(r.mean()),float(r.mean()/r.std(ddof=0)),float(np.mean(r>.02))
            gross,turn = float(p.gross_excess.mean()*25.2),float(p.turnover.mean())
            s = dict(candidate='FM_ML',window=window,periods=len(p),rank_ic=rankmean,rank_ic_ir=ir,
                rank_ic_win=win,wins=int(np.sum(r>.02)),s_i=abs(rankmean*ir)*win,
                gross_excess=gross,net_excess=gross-turn*.006*25.2,turnover=turn,
                abs_size_corr=float(p.size_corr.abs().mean()))
            statsrows.append(s)
            if family=='target':
                assert abs(rankmean-meta['rank_ic'])<1e-8 and abs(ir-meta['rank_ic_ir'])<1e-7
                assert abs(win-meta['rank_ic_win'])<1e-12
                assert abs(s['net_excess']-meta['net_excess'])<1e-10
                savedp = pd.read_csv(out/'FM_ML_target_periods.csv')
                assert np.max(np.abs(savedp.rank_ic-r))<1e-8
                for year,b in p.groupby(p.date.str[:4]):
                    years.append(dict(year=year,periods=len(b),rank_ic=float(b.rank_ic.mean()),
                        rank_ic_ir=float(b.rank_ic.mean()/b.rank_ic.std(ddof=0)),win=float((b.rank_ic>.02).mean())))
            for group,b in pd.DataFrame(detail).groupby('group'):
                groups.append(dict(window=window,group=int(group),gross_excess=float(b.gross_excess.mean()*25.2),
                    turnover=float(b.turnover.mean()),net_excess=float(b.gross_excess.mean()*25.2-b.turnover.mean()*.006*25.2)))
    table = pd.DataFrame(statsrows)
    table.to_csv(out/'results.csv',index=False)
    pd.DataFrame(groups).to_csv(out/'deciles.csv',index=False)
    pd.DataFrame(years).to_csv(out/'years_target.csv',index=False)
    audit = dict(status='passed',independent_pandas_metrics=True,groups_cost_turnover=True,prefix_checks=checks,
        upstream_raw_causality_source=str(source/'raw_causality_checks.json'),
        upstream_raw_audit='100stocks all60atoms actual daily-input two cutoffs passed',
        checkpoint_sha256=checksum,seconds=time.monotonic()-started,
        actual_model_training_causal=False,scope='frozen full-window-trained inference and cached inputs',
        limitation='in-sample fitted numbers, not independent generalization or platform alignment')
    task.save('verification.json',audit)
    s = statsrows[0]
    v = np.array([s['rank_ic'],s['rank_ic_ir'],s['rank_ic_win']])
    match = bool(np.array_equal(np.round(v,6),np.round(task.TARGET,6)))
    near = abs(v[0]-task.TARGET[0])<=.001 and abs(v[1]-task.TARGET[1])<=.01 and s['wins']==111
    lines = ['# 全局非线性模型：疯猫数值拟合补充','',
        f'目标：RankIC .172279、IR 1.661321、胜率111/119。结果：RankIC **{v[0]:.6f}**、IR **{v[1]:.6f}**、胜率 **{s["wins"]}/119 ({v[2]:.6f})**、S_i **{s["s_i"]:.6f}**。','',
        f'逐项误差：{v[0]-task.TARGET[0]:+.6f} / {v[1]-task.TARGET[1]:+.6f} / {v[2]-task.TARGET[2]:+.6f}。六位小数相同={match}；预声明近似门槛={bool(near)}。','',
        '这是全119期监督学习与全局固定权重搜索的**拟合内**结果。未来收益只当训练标签，没有作为预测输入、日期/股票代码特征或逐期权重；但是全窗口参数在历史上不可获得，**不能称可交易因果历史复现**。没有恢复疯猫原公式，没有平台确认，不能拿来声称比赛可实现同样分数。','',
        '| 窗口 | RankIC | IR | 胜率 | 净超额 | 换手 |','|---|---:|---:|---:|---:|---:|']
    for r in table.itertuples():
        lines.append(f'| {r.window} | {r.rank_ic:.6f} | {r.rank_ic_ir:.6f} | {r.rank_ic_win:.4%} | {r.net_excess:.2%} | {r.turnover:.2%} |')
    frozen = json.loads((out/'model_frozen.json').read_text(encoding='utf8'))
    lines += ['',f'全局HistGradientBoosting选择{frozen["trees"]}树前缀，41输入，固定混合权重 `{frozen["weights"]}`（模型秩、−vol60、rev6、asym20）。完整可复算checkpoint model.pkl，校验SHA256记录在model_frozen.json。', '',
        '推定119期日历、正式120期H03五年和近期2026结果分开输出；目标拟合数据与正式/近期有重叠，这些均不能称留出检验。全部按全A/qfq/total_mv/label-1/10组/factor_valid/0.30%单边成本与算术年化，没有变更公共规则。','',
        '独立pandas指标、十组收益/成员换手/成本与checkpoint预测一致；冻结推理截断两次完全不变，60原子的真实日度输入截断来自上游100股票/两个截断点的已通过审计。这只说明推理输入没有回看未来，不能洗掉全窗口模型训练泄漏。','',
        f'拟合/搜索耗时{meta["seconds"]/60:.1f}分钟，核验{audit["seconds"]/60:.1f}分钟。峰值RSS {meta["memory"]["rss_gb"]:.3f}GiB、私有{meta["memory"]["private_gb"]:.3f}GiB、可用最低{meta["memory"]["min_available_gb"]:.3f}GiB。平台算力0；本轮不提交、不改池。','']
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf8')
    print(table.to_string(index=False))
    print('GLOBAL MODEL AUDIT COMPLETE',match,near)


if __name__=='__main__':
    main()
