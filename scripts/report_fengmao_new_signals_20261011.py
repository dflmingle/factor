"""Build final research report from saved, verified artifacts only."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/platform_alignment/fengmao-new-signals-20261011'


def main():
    meta = json.loads((OUT/'metadata.json').read_text(encoding='utf-8'))
    audit = json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
    assert meta['status']=='complete' and audit['status']=='passed'
    results = pd.read_csv(OUT/'results.csv')
    models = json.loads((OUT/'models_frozen.json').read_text(encoding='utf-8'))
    correlations = pd.read_csv(OUT/'reference_correlations.csv')
    full = results[results.window.eq('formal_5y')]
    passed = full[full.s_i_proxy.ge(.035)&full.net_excess.ge(.15)&full.turnover.le(.40)]
    lines = ['# 新信号条件搜索：下一轮结果（2026-10-11）','',
        f'完成 AlphaGen 改造版 PPO、交叉熵公式搜索、原生 AlphaPool 三种方法。共记录 {meta["training_unique_formulas"]} 个唯一公式（含被排除的纯旧信号），{meta["valid_formulas"]} 个有效公式；最终冻结 3 个模型。平台算力 **0**。', '',
        f'训练/搜索/正式评估耗时 {meta["seconds"]/60:.1f} 分钟，独立核验另用 {audit["verification_seconds"]/60:.1f} 分钟；没有修改池或提交平台。', '',
        f'满足 S_i≥.035、五年净≥15%、自身换手≤40% 三项初筛的模型：**{len(passed)}/3**。这只是本地单因子初筛；现役去重、池级 size/ΔComb、平台确认仍是准入要求。', '',
        '| 模型 | 方法 | 五年 S_i proxy | 五年净超额 | 训练净超额 | 2024–2025 验证净超额 | 2026 近期净超额 | 五年换手/次 | 五年绝对 size 相关均值 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    labels = ['AlphaGen PPO','交叉熵 CEM','原生 AlphaPool']
    for i,m in enumerate(models,1):
        name = f'FM_MORE_{i:02d}'
        r = results[results.candidate.eq(name)].set_index('window')
        a = r.loc['formal_5y']
        lines.append(f'| {name} | {labels[i-1]} | {a.s_i_proxy:.4f} | {a.net_excess:.2%} | {r.loc["training"].net_excess:.2%} | {r.loc["validation_2024_2025"].net_excess:.2%} | {r.loc["recent_2026"].net_excess:.2%} | {a.turnover:.1%} | {a.abs_size_corr:.3f} |')
    lines += ['', '训练只有 55 期，验证 47 期，近期 15 期，正式五年 120 期。公式/权重在读取本轮验证结果前冻结；2024–2025 已被此前研究查看，不能称未污染样本外，更不能等同官方 B。近期仅诊断，不用来换人或改权重。', '',
        '名义窗口 20210907..20260907，实际信号 2021-09-07..2026-08-10，最后真实标签退出 2026-08-25；本地行情截止 2026-09-07，无 9 月/10 月完整信号收益。全历史沪深全 A SH/SZ、qfq、total_mv、20180101 暖机、label-1、10 组、factor_valid、算术年化、0.30% 单边成本。分组并列值保持稳定代码排序，属执行代理。', '',
        f'对齐参考规则 `{meta["rule"]}`。新技术/条件组合均为本地诊断 proxy；真实 OPEN 不是分钟行情，MACD 采用价格归一化 DIF/柱形，不能冒称平台内置字段字节级等价。对手公式私有，不能称复现疯猫子单因子。', '',
        '## 冻结模型与信号来源','']
    for i,m in enumerate(models,1):
        lines.append(f'FM_MORE_{i:02d}（编号只在本轮目录内标识，未覆盖前轮）：')
        lines.append('')
        if 'formula' in m:
            lines += [f'`{m["formula"]}`','']
        else:
            lines += [f'AlphaPool L1={m["alpha"]}，当日截面 z-score 加权，缺失交集还原：','']
            for c in m['components']:
                lines.append(f'- {c["weight"]:+.6f} × `{c["formula"]}`')
            lines.append('')
        b = correlations[correlations.candidate.eq(f'FM_MORE_{i:02d}')].sort_values('mean_abs_spearman',ascending=False).iloc[0]
        lines += [f'与本轮信号原子及上轮三模型中最接近 `{b.reference}`：信号日截面平均 Spearman {b.mean_spearman:.3f}、绝对相关均值 {b.mean_abs_spearman:.3f}。这是归因诊断，不是与现役每席的日度去重证明。','']
    lines += ['## 核验、内存与决策','',
        f'独立 pandas 核验 {audit["period_records"]} 条逐期记录、{audit["summary_rows"]} 行汇总，IC 最大误差 {audit["ic_max_delta"]:.3g}。十组成员/收益/成本、真实成员换手、Top20、分年及训练标签退出边界均通过。真实日度输入在 100 个固定股票、两个截断点重算 36 个原子及三个冻结模型，历史掩码和值差异均为 0；截面排名使用该样本本身，因此这是因果性样本核验，不是全 A 新原子排名的独立复算。', '',
        f'累计保守搜索预算 {audit["conservative_test_denominator"]}，多重检验阈值 {audit["correction_threshold"]:.3g}；保留失败公式，未把训练最佳或普通 p 值当样本外优势。统计校正预算覆盖本系列已计入的 GP/PPO/GFN/CEM 搜索，并非项目所有历史研究的精确总次数。', '',
        f'训练/评估峰值 RSS {meta["memory"]["rss_gib"]:.3f} GiB、私有内存 {meta["memory"]["private_gib"]:.3f} GiB、系统可用内存最低 {meta["memory"]["min_available_gib"]:.3f} GiB。限制为 2.25 GiB / 可用底线 1.25 GiB，单进程单线程，192 股票分块，无爆内存。', '',
        ('本轮三个模型均未通过本地准入初筛，**不进入平台决赛候选、不改池**。新增技术/日内隔夜条件没有产生足以支持榜首目标的新席；不根据近期表现翻方向、另选公式或自动追加下一轮。' if len(passed)==0 else
         '初筛过线模型仍需现役逐日去重和池级四列全账验证；暂不修改池，不将本地单因子结果解释为比赛积分改善。'), '',
        '产物：`plan.json`、`search_train.jsonl`、`alphagen_ppo_20261201_result.json`、`cem_result.json`、`alphapool_alternatives.json`、`models_frozen.json`、`results.csv`、各窗逐期/十组/Top20、`deciles.csv`、`years.csv`、`reference_correlations.csv`、`raw_causality_checks.json`、`verification.json`、`metadata.json`。信号面板和训练 checkpoint 按仓库规则忽略。','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    print(full[['candidate','s_i_proxy','net_excess','turnover']].to_string(index=False))
    print('REPORT COMPLETE',OUT/'summary.md')


if __name__=='__main__':
    main()
