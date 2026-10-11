"""Render verified results of the bounded numerical-fit experiment."""
import json
import pandas as pd
from fengmao_rankboost_round2_20261011 import OUT, KINDS, prior


def main():
    meta=json.loads((OUT/'metadata.json').read_text(encoding='utf8'))
    audit=json.loads((OUT/'verification.json').read_text(encoding='utf8'))
    frozen=json.loads((OUT/'models_frozen.json').read_text(encoding='utf8'))
    assert audit['status']=='passed'
    table=pd.read_csv(OUT/'independent_results.csv')
    full=table[(table.window=='target_119_fit')&(~table.candidate.str.startswith('TEMP_'))]
    best=full[full.candidate=='FM_RB_BLEND'].iloc[0]
    errors=[float(best.rank_ic-prior.TARGET[0]),float(best.rank_ir-prior.TARGET[1]),int(best.wins)-111]
    strict=round(best.rank_ic,6)==round(prior.TARGET[0],6) and round(best.rank_ir,6)==round(prior.TARGET[1],6) and best.wins==111
    near=abs(errors[0])<=.001 and abs(errors[1])<=.01 and errors[2]==0
    lines=['# 疯猫数值复现：第二轮非线性方法结果','',
        f'结果：六位小数一致 **{strict}**；预声明近似门槛（均值误差≤.001、IR≤.01、胜率111/119）**{near}**。', '',
        f'最终全局混合：RankIC `{best.rank_ic:.9f}`、IR `{best.rank_ir:.9f}`、胜率 `{int(best.wins)}/119`、S_i `{best.s_i:.9f}`。', '',
        f'与公开目标误差：RankIC `{errors[0]:+.9f}`、IR `{errors[1]:+.9f}`、胜期 `{errors[2]:+d}`。', '',
        '**这只评估数值拟合程度，不是疯猫私有公式复现，也不是历史可交易验证。** 全窗口模型及混合权重使用全部119期标签；没有未来收益输入、日期/股票代码特征、逐期标签拟合权重、缩小股票池或修改真实统计，但模型参数在历史时点不可得。不得将此候选提交平台或加入现役池。','',
        '| 路线（同一119期） | RankIC | IR | 胜期 | S_i | 净超额代理 |',
        '|---|---:|---:|---:|---:|---:|',
        '| 疯猫公开目标 | .172279 | 1.661321 | 111/119 | .266970 | 未公开 |',
        '| 上一轮 GP/CEM | .108192 | .811999 | 97/119 | .071611 | 9.27% |',
        '| 上一轮 HistGB 400树 | .174628 | 1.170335 | 106/119 | .182046 | 29.62% |']
    for row in full.itertuples():
        lines.append(f'| {row.candidate} | {row.rank_ic:.6f} | {row.rank_ir:.6f} | {row.wins}/119 | {row.s_i:.6f} | {row.net_excess:.2%} |')
    p=pd.read_csv(OUT/'FM_RB_BLEND_target_119_fit_independent_periods.csv')
    sigma=float(p.rank_ic.std(ddof=0))
    boundary=p.assign(distance=(p.rank_ic-.02).abs()).sort_values('distance').head(8)
    lines += ['', f'混合候选实际RankIC总体标准差 `{sigma:.9f}`（疯猫公开均值/IR隐含 `{prior.TARGET[0]/prior.TARGET[1]:.9f}`）。', '',
        '胜率使用实际RankIC序列在固定0.02阈值上的硬计数。离阈值最近的8期如下；没有更换阈值、修改数据或丢失效期。','',
        '| 日期 | RankIC | 是否超过0.02 |', '|---|---:|---|']
    for r in boundary.itertuples():
        lines.append(f'| {r.date} | {r.rank_ic:.9f} | {r.rank_ic>.02} |')
    lines += ['', '三条 LightGBM 路线均实际训练到2400树，300树一个固定检查点，共24个检查点；原始模型按最高IR冻结树前缀。随后六个输入使用一套全局固定权重作DE搜索；后续细化沿用同一模型和六个输入，不新建按日期定价的权重。全部搜索日志及未匹配结果保留。','',
        '| 冻结原始模型 | 输入数 | 树数 |', '|---|---:|---:|']
    for m in frozen['models']:
        lines.append(f'| {m["kind"]} | {len(m["features"])} | {m["trees"]} |')
    lines += ['', '时间对照使用同种模型新训练800树，仅使用收益到期日不晚于2023-12-31的训练标签；不从全窗口模型热启动。该对照采用已被项目研究过的数据与参数，不是未经查看的留出，也不是平台官方B。', '',
        '| 时间对照（正式日期模板） | 窗口 | RankIC | IR | 胜率 | 净超额 |',
        '|---|---|---:|---:|---:|---:|']
    controls=table[table.candidate.str.startswith('TEMP_')&table.window.isin([
        'formal_5y_temporal_validation_2024_2025','formal_5y_temporal_2026'])]
    for row in controls.itertuples():
        window='2024–2025' if 'validation' in row.window else '2026（15期）'
        lines.append(f'| {row.candidate} | {window} | {row.rank_ic:.6f} | {row.rank_ir:.6f} | {row.win_rate:.2%} | {row.net_excess:.2%} |')
    lines += ['', '目标拟合与正式五年/近期诊断分开；以下混合候选的另外两窗口也与训练标签重叠，不能当样本外。','',
        '| 混合候选窗口 | RankIC | IR | 胜率 | 净超额 | 换手/次 |',
        '|---|---:|---:|---:|---:|---:|']
    for row in table[(table.candidate=='FM_RB_BLEND')].itertuples():
        lines.append(f'| {row.window} | {row.rank_ic:.6f} | {row.rank_ir:.6f} | {row.win_rate:.2%} | {row.net_excess:.2%} | {row.turnover:.2%} |')
    lines += ['',
        '推定119期日期仅匹配公开首尾和期数，中间日期并未取得。正式五年使用保存的120期模板；本地数据截至2026-09-07，最后可结算信号2026-08-10，近期2026不是10月实时成绩。没有恢复疯猫逐股信号，也没有平台确认；S_i是前三项的派生分数，不是第四份独立证据。','',
        '同伴收益的原始单因子此前已失败，本轮只检验它与量价分组/非线性模型的交互；保留时间对照以判断是否产生增量，不拿旧失败结果包装成新复现。','',
        '所有输出使用全沪深A/qfq/total_mv/2018暖机/label-1/10组/factor_valid/0.30%单边成本/算术年化。没有更改规则或覆盖旧轮；`strict_six_decimals`不表示恢复原公式。','',
        f'独立核验通过：{len(audit["independent_pandas_metrics"])}组窗口的逐期IC/RankIC、十组成员换手与成本重算；{len(audit["frozen_input_prefix_checks"])}次完整股票面板的冻结输入/模型预测截断检查历史差异0。checkpoint SHA-256在verification.json。上游价格原子和同伴网络实际日度输入截断出处亦保留；这些检查不能消除全窗口训练泄漏。','',
        f'训练/搜索/输出主过程{meta["seconds"]/60:.1f}分钟，独立核验{audit["seconds"]/60:.1f}分钟；主过程RSS峰值{meta["memory"]["rss_gb"]:.3f}GiB、私有{meta["memory"]["private_gb"]:.3f}GiB，最低系统可用{meta["memory"]["min_available_gb"]:.3f}GiB。2.25GiB/1.25GiB watchdog未突破；平台算力0。早期检查点重复预测的实现已改成增量，旧部分检查点日志保存在stages_before_prediction_optimization.json。','',
        '材料：[独立结果](independent_results.csv)、[24个检查点](stages.json)、[全局混合配置](models_frozen.json)、[DE抽样](blend_trials.jsonl)、[细化日志](refinement.json)、[十组](deciles.csv)、[分年](years.csv)、[Top20](top20.csv)、[核验](verification.json)。模型txt与npy保留本地供复算。','']
    (OUT/'summary.md').write_text('\n'.join(lines),encoding='utf8')
    print('STRICT',strict,'NEAR',near,'ERRORS',errors)
    print(full.to_string(index=False))
    print(controls.to_string(index=False))


if __name__=='__main__':
    main()
