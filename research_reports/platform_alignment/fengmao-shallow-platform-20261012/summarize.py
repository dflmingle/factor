"""Summarize this single completed paid run and its saved local reference."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'research_reports/platform_alignment/fengmao-nested-causal-20261011'


def main():
    entry = json.loads((HERE/'candidates.txt.state.json').read_text())['Q131-20261012']
    raw = json.loads((HERE/entry['raw_result']).read_text())
    analysis = raw['results']['factor_analysis']
    m = entry['metrics']
    g = next(x for x in analysis['query_group_return_analysis'] if x['group']=='分组10')
    dates = pd.to_datetime(analysis['query_ic_sequence_chart']['x'][0]['data'])
    frame = pd.DataFrame({'date': dates})
    for key, name, col in (
        ('query_ic_sequence_chart', 'IC', 'ic'),
        ('query_rank_ic_sequence_chart', 'Rank_IC', 'rank_ic'),
        ('query_factor_excess_chart', '组10', 'gross_excess'),
        ('query_return_chart', '组10', 'gross_return')):
        chart = analysis[key]
        assert pd.DatetimeIndex(pd.to_datetime(chart['x'][0]['data'])).equals(dates)
        values = np.asarray(next(x['data'] for x in chart['y'] if x['name']==name), float)
        frame[col] = np.diff(np.r_[0, values]) if 'sequence' not in key else values
    # Saved platform return charts accumulate arithmetic period returns. Verify
    # that interpretation against the official full-window group headline.
    assert abs(frame.gross_excess.mean()*25.2*100 - m['long_excess']) < .01
    frame.to_csv(HERE/'platform_periods.csv', index=False)
    local = pd.read_csv(SOURCE/'FM_CAUSAL_SHALLOW_formal_5y_periods.csv', parse_dates=['date'])
    paired = frame.merge(local, on='date', suffixes=('_platform','_local'))
    assert len(paired)==len(frame)==len(local)==120
    paired.to_csv(HERE/'paired_periods.csv', index=False)
    table = pd.read_csv(SOURCE/'results.csv')
    reference = table[(table.candidate=='FM_CAUSAL_SHALLOW') & (table.window=='formal_5y')].iloc[0]
    comparisons = {}
    for col in ('ic','rank_ic','gross_excess'):
        comparisons[col] = dict(
            pearson_corr=float(paired[col+'_platform'].corr(paired[col+'_local'])),
            mean_abs_delta=float(np.mean(np.abs(paired[col+'_platform']-paired[col+'_local']))))
    platform_net = m['long_excess']-m['turnover']*.006*25.2
    subsets = {}
    for name, mask in (
        ('post_training', frame.date>='2025-08-22'),
        ('recent_2026', frame.date>='2026-01-01')):
        f = frame[mask]
        subsets[name] = dict(periods=len(f), first_signal=str(f.date.min().date()),
                             last_signal=str(f.date.max().date()), rank_ic=float(f.rank_ic.mean()),
                             pearson_ic=float(f.ic.mean()),
                             gross_excess_annual_pct=float(f.gross_excess.mean()*25.2*100),
                             net_excess_annual_pct=None,
                             note='Segment turnover is unavailable; do not use full-window turnover to claim segment net excess.')
    result = dict(factor_id=entry['factor_id'], run_id=entry['run_id'], candidate_count=1,
                  paid_runs=1, deducted=raw['billing']['deducted'], duration_seconds=raw['duration_seconds'],
                  platform_metrics=m, platform_net_excess_pct=platform_net,
                  platform_excess_max_drawdown_pct=float(g['excessMaxDrawdown'].rstrip('%')),
                  local_net_excess_pct=float(reference.net_excess*100),
                  platform_minus_local_net_pp=float(platform_net-reference.net_excess*100),
                  paired_periods=len(paired), period_alignment=comparisons, segments=subsets,
                  five_year_contains_training=True, genuine_unseen_holdout=False,
                  decision='Retain as a platform-supported frozen research candidate; historical post-training evidence is weaker than the full-window headline. No new-cluster or competition-pool claim.',
                  hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          (HERE/'candidate.py', ROOT/json.loads((HERE/'manifest.json').read_text())['source_model'])})
    (HERE/'execution_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    balance = json.loads((HERE/'balance_after.json').read_text())
    post=subsets['post_training']; recent=subsets['recent_2026']
    report = f'''# 原冻结浅层树：平台五年确认

2026-10-12，仅测试 1 个候选、1 次付费运行。原 60 输入、3 叶 × 200 棵 LightGBM，计算其中 32 个实际使用特征，保留原阈值与叶权重。平台 Python 运行成功。

| 指标 | 平台五年 | 原本地五年代理 |
|---|---:|---:|
| RankIC | {float(m['rank_ic']):.4f} | {reference.rank_ic:.6f} |
| Pearson IC | {float(m['ic_mean']):.4f} | {reference.pearson_ic:.6f} |
| Pearson ICIR | {float(m['ic_ir']):.4f} | {reference.pearson_ir_sample:.6f} |
| 年化多头毛超额 | {m['long_excess']:.2f}% | {reference.gross_excess*100:.2f}% |
| 每次成员换手 | {m['turnover']:.2f}% | {reference.turnover*100:.2f}% |
| 估算年化成本 | {m['turnover']*.006*25.2:.2f}% | {reference.turnover*.006*25.2*100:.2f}% |
| 扣成本年化多头超额 | {platform_net:.2f}% | {reference.net_excess*100:.2f}% |

平台多头组最大回撤 {m['long_max_drawdown']:.2f}%，超额最大回撤 {result['platform_excess_max_drawdown_pct']:.2f}%，多头 Sharpe {m['long_sharpe']:.3f}，月胜率 {m['long_monthly_win_rate']:.2f}%，单调性 {m['monotonicity']}。回撤/Sharpe 为平台组收益原始诊断；净超额是按换手扣费估算，不能把原始回撤声称为同一条扣费路径的回撤。净超额差 {result['platform_minus_local_net_pp']:+.2f}pp，小于 5pp 登记门槛。以上均为单因子结果。

窗口 20210907–20260907，沪深全 A，10 日调仓、10 组、方向 1，单边 0.30% 成本，买卖各计一次。平台保存 120 个信号期，首日 {frame.date.min().date()}、末日 {frame.date.max().date()}，与原本地 120 个信号日期完全对应。逐期 RankIC 相关 {comparisons['rank_ic']['pearson_corr']:.6f}，IC 相关 {comparisons['ic']['pearson_corr']:.6f}，毛超额相关 {comparisons['gross_excess']['pearson_corr']:.6f}。配对明细见 paired_periods.csv；全 A 正式收益引用原保存结果，本次真实股票子集仅用于特征/预测等价检查。

## 训练期后的诊断

五年窗口包含训练样本，模型重训截止于 2025-08-22 前已到期标签。平台训练截止后 {post['periods']} 个信号期的 RankIC 为 {post['rank_ic']:.6f}，年化毛超额 {post['gross_excess_annual_pct']:.2f}%。平台没有逐段换手，无法可靠给出这段净超额；原本地同段净超额为 4.55%。历史末段此前已看过，不是全新盲测。

独立近期 2026 段 {recent['periods']} 期，平台 RankIC {recent['rank_ic']:.6f}、年化毛超额 {recent['gross_excess_annual_pct']:.2f}%；原本地近期净超额 6.81%。近期诊断与五年结果分别报告。

## 等价检查与费用

提交前静态预检和 500 股票、242 期截断重算均通过。5296 行树预测输入（含 1200 行分裂边界）、11520 行合成特征输入、7936 行真实股票子集输入均与原 LightGBM 预测逐值一致。原特征生成源独立抽取执行，32 个使用特征逐值一致。双精度阈值比较修正避免 NumPy 隐式 float32 阈值舍入；零阈值测试使用可实现的截面排名值。

截断重算只证明冻结推理不随未来行情变化，不能证明训练期内的模型参数是当时可获得的。原内部研究共 475 个比较，粗略多重检验门槛 0.05/475；平台 p 值仅显示 0.0000，不能当精确零，也不能据此消除选型偏差。

实际运行 {raw['duration_seconds']:.1f} 秒，扣除 {raw['billing']['deducted']:.0f} 算力。临期礼包从 6 降至 {balance['giftBalance']:.0f}，常规余额 {balance['rechargeBalance']:.6f} 未减少；剩余礼包到期 {balance['nextExpireAt']}。创建 factor_id `{entry['factor_id']}`，run_id `{entry['run_id']}`。

决定：保留为平台支持的冻结研究候选。平台与本地五年表现接近，但训练后表现较弱且小市值暴露明显（本地后段 size rho −0.588），目前不足以认定新的稳定信息簇。最高相关的其他簇尚未在本轮重算。新增因子池的决定需另行评估相关性和池级增益。本轮完成后停止回测。

审计产物：manifest.json、protocol.json、verification.json、execution_summary.json、candidates.txt.state.json、candidates.results/、平台与配对逐期 CSV。候选与源模型 SHA-256 见 manifest.json / execution_summary.json。
'''
    (HERE/'summary.md').write_text(report)
    print(json.dumps({'net_excess_pct': platform_net, 'net_gap_pp':result['platform_minus_local_net_pp'],
                      'alignment':comparisons,'segments':subsets,'cost':raw['billing']['deducted'],
                      'gift_remaining':balance['giftBalance']},indent=2))


if __name__=='__main__':
    main()
