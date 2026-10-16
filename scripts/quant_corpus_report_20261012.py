#!/usr/bin/env python3
"""Build source-linked offline results and decisions without running backtests."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
import quant_corpus_local_20261012 as q

CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'

def main():
    manifest=json.loads((q.OUT/'recipe_manifest.json').read_text())
    coverage=json.loads((CAT/'review_coverage.json').read_text())
    result=pd.read_csv(q.OUT/'results.csv')
    formal=result[result.window.eq('five_year')].set_index('key')
    recent=result[result.window.eq('recent')].set_index('key')
    residual=pd.DataFrame(json.loads((q.OUT/'size_reversal_rank_residual.json').read_text()))
    daily=pd.read_csv(q.OUT/'daily_old_anchor_correlations.csv')
    nearest=pd.read_csv(q.OUT/'nearest_old_top3_signal_grid.csv')
    assert len(manifest)==len(formal)==len(recent)==92
    assert set(nearest.candidate)==set(formal.index)
    decisions={
      'coin_team_eq':'保留行为机制资料；双控制后净额约零，暂不进池',
      'capm_residual_vol120_low':'已有低波动家族对照；保留风险腿，不能登记新簇',
      'amount_low_std20':'重复流动性/市值信息；双控制后为负，暂不进池',
      'volume_low_std20':'双控制后为负，暂不进池',
      'ma120_over_close':'重复筹码/反转信息；双控制后为负，暂不进池',
      'cgo100_low':'重复回撤/反转信息；双控制后为负，暂不进池',
      'rd_assets':'低相关待研究；近期为负且缺7期，暂不进池',
      'rd_market':'低相关待研究；近期为负且缺7期，暂不进池',
      'bank_doubletime250':'历史正、近期负；银行到全A适配，暂不进池',
      'rfscore7_source':'并列排序敏感且保留源代码分母缺陷，暂不进池',
      'rfscore7_lowpb':'小有效截面、并列排序敏感，暂不进池',
    }
    rows=[]
    for m in manifest:
        key=m['key'];f=formal.loc[key];r=recent.loc[key]
        period=pd.read_csv(q.OUT/'five_year'/f'{key}.periods.csv')
        ic=period.ic.dropna().to_numpy()
        p=float(ttest_1samp(ic,0).pvalue) if len(ic)>1 and np.std(ic)>0 else np.nan
        top=nearest[nearest.candidate.eq(key)].iloc[0]
        dx=daily[daily.candidate.eq(key)].copy()
        if len(dx):anchor=dx.loc[dx.rho.abs().idxmax()]
        sx=residual[residual.key.eq(key)&residual.window.eq('five_year')]
        rows.append({**m,**{k:f[k] for k in ['periods','rank_ic','gross_excess_pct','net_excess_pct','turnover_pct','annual_cost_pct','held_daily_max_drawdown_pct','size_neutral_net_excess_pct','jitter_net_excess_pct']},
          'recent_net_excess_pct':r.net_excess_pct,'recent_held_daily_max_drawdown_pct':r.held_daily_max_drawdown_pct,
          'size_reversal_rank_residual_net_pct':sx.iloc[0].net_excess_pct if len(sx) else np.nan,
          'nearest_daily_anchor':anchor.anchor if len(dx) else '', 'nearest_daily_rho':anchor.rho if len(dx) else np.nan,
          'nearest_saved_reference':top.old_key,'nearest_saved_cluster':top.cluster,'nearest_saved_rho':top.rho,
          'ic_p_uncorrected':p,'ic_bonferroni_threshold':.05/len(manifest),
          'decision':decisions.get(key,'已有家族对照，不能视为新alpha' if m['role']=='known_control' else ('原文冻结方向净额非正；保留失败记录' if f.net_excess_pct<=0 else '尚未通过完整新增信息/稳定性验证；暂不进池'))})
    table=pd.DataFrame(rows).sort_values('net_excess_pct',ascending=False)
    table.to_csv(q.OUT/'recipe_decisions.csv',index=False,encoding='utf-8-sig')
    lines=['# quant 策略库：因子提取与本地复现（2026-10-12）','',
      '已完成92个原文衍生因子/对照项的本地测试：71个候选、21个已有家族对照。没有发现足以直接加入因子池、并证明具有稳定新增信息的新簇。平台算力消耗为0。', '',
      '## 阅读与复现覆盖','',
      f"共{coverage['files']}个文件，{coverage['decoded_strategy_texts']}个可解码策略文本均建立逐文件证据、依赖和字段记录。详细公式/代码及手写语义核对共{sum(coverage['review_levels'].get(k,0) for k in ['formula_and_code_checked','core_logic_and_formula_checked'])}个来源，尚余{coverage['remaining_texts_without_detailed_review']}个待逐篇详细核验；累计本地完成{coverage['tested_specifications_total']}项规格，本报告只包含首轮92项。**扫描不等同于完整语义核验，提取因子测试不等同于复现全部完整策略。**", '',
      '57个 `.rzrk` 为不透明专有二进制，不能读取其中公式；2个Excel目录已导出，4张说明/通知图已查看。文件级指纹仅作导航，不作经济机制分簇。', '',
      '逐文件台账：[source_review.csv](../../literature/quant-corpus-factor-catalog-20261012/source_review.csv)。未验证字段/依赖：[unreproduced_field_recipes.csv](../../literature/quant-corpus-factor-catalog-20261012/unreproduced_field_recipes.csv)。分钟、竞价、股东人数、分析师预测、外部模型/权重、北向与龙虎榜等缺失数据不能用日线假冒。', '',
      '测试覆盖球队硬币、凸显度/惊恐/注意力变化、行业量价向股票的适配、日内/隔夜黄金律、HighOpen/CloseLow/VwapClose、CGO筹码、均线/动量/最大收益、路径强度、CAPM低特质波动、质量/估值/成长、研发强度、FScore/RFScore、银行翻倍和ROE/PB双排名。每个候选保留公式、方向、源路径、行号、SHA256及proxy标记。', '',
      '## 固定口径与实际日期','',
      f'读取仓库对齐规则后，使用隔离版本 `{q.VERSION}`，遵循本任务沪深全A/qfq/total_mv/算术年化契约，未套用仓库新增ST/上市天数筛选和几何收益头条。不同规则版本不能混排。', '',
      '暖机2018-01-01；正式请求窗口2021-09-07—2026-09-07，近期独立请求窗口2026-01-01—本地最新2026-09-07。沿用保存的平台信号网格：正式120期，近期15期；实际末次信号2026-08-10、末次退出2026-08-25。两份结果均没有覆盖其后的可交易期，不能称为测到今天。研发因子只有113个有效期，2025年缺7期，不与完整120期直接等同。', '',
      '10日持有、10组、高因子值持有第10组；标签close(t+1)→close(t+11)，因子有效截面等权基准，单边成本0.30%。表内“净超额”为算术年化毛超额扣年化换手成本；“回撤”为含成本持仓日度NAV最大回撤，不是超额净值回撤。近期数字同样是年化诊断，且与五年重叠，不是独立样本外。', '',
      '全A有效行情字段覆盖100%；高低价/成交额使用真实缓存，成交均价按成交额千元、成交量手换算后转qfq。财务使用公告日PIT、最近报告期和连续四季度TTM；源代码的行业中性、固定股票池、交易规则或训练模型未完整复现，已逐项标记适配/proxy。本地快照只做存在性检查，本轮未重新校验归档哈希。', '',
      '## 主要结果','',
      '| 因子 | 五年毛超额%/年 | 五年净超额%/年 | 日度回撤% | 换手%/次 | RankIC | 近期净超额%/年 | 市值+反转秩残差净额%/年 |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    shortlist=['small_size','amount_low_std20','coin_team_eq','capm_residual_vol120_low','rd_assets','rd_market','bank_doubletime250','rfscore7_source','rfscore7_lowpb','volume_low_std20','ma120_over_close','cgo100_low']
    for key in shortlist:
        t=table[table.key.eq(key)].iloc[0]
        vals=[t.gross_excess_pct,t.net_excess_pct,t.held_daily_max_drawdown_pct,t.turnover_pct,t.rank_ic,t.recent_net_excess_pct,t.size_reversal_rank_residual_net_pct]
        cells=[f'{v:.4f}' if i==4 else (f'{v:.2f}' if pd.notna(v) else '未测') for i,v in enumerate(vals)]
        lines.append('| '+t['name']+' | '+' | '.join(cells)+' |')
    lines += ['',
      '成交额稳定性原始净额11.58%，控制市值和反转后−1.09%；成交量稳定性、MA120/现价、CGO同样未通过双控制。球队硬币原始净额2.33%、年化成本约10.26pp，双控制后仅0.05%，2023和2025年为负；保留机制资料，不能凭近期正收益认定新簇。', '',
      '低特质波动双控制后4.93%、近期8.99%，值得保留为已知风险腿，但2025年控制后仍为负，不能说已经解决回撤。研发强度双控制后约1.38%/1.44%，近期仍负；银行翻倍历史5.25%、近期−7.62%，且原文银行池向全A的适配不证明银行策略本身。', '',
      'RFScore7原文源代码包含截面标量资产周转分母，当前源忠实版本保留此问题且标proxy。因子大量并列值，稳定代码排序得到+0.43%净额，固定随机并列排序变为−3.34%；低PB版本+0.96%变−3.09%。因此不能把低换手、低回撤与高近期收益直接视为稳健alpha。', '',
      '原始五年净超额为正：14/71候选、3/21对照。其余失败项全部保留。此数不是通过新增信息或入池门槛的数量。', '',
      '单独的log市值中性结果是因子秩对log(total_mv)的截面回归，它不足以剔除非线性市值信息：小市值自身该处理后仍有6.20%净额。因此结论以另存的“市值秩+20日反转秩”双控制诊断为补充；残差回测也不证明与所有风格正交。', '',
      '## 与旧簇相关性','',
      '主口径对8个领先候选逐交易日取交集股票计算Spearman，再对每日rho取算术平均；14个锚点覆盖12个旧簇/对照标签，财务BM/ROE标proxy。覆盖不完整，不据此新建U簇。', '',
      '| 候选 | 最相关旧锚点（主口径） | 日均rho | 另两个最相关锚点 |',
      '|---|---|---:|---|']
    for key,g in daily.assign(absrho=daily.rho.abs()).sort_values('absrho',ascending=False).groupby('candidate'):
        top=g.head(3);a=top.iloc[0]
        anchor_label=a.anchor.replace('|',r'\|')
        other='；'.join(f"{r.anchor.replace('|',chr(92)+'|')} ({r.rho:.3f})" for _,r in top.iloc[1:].iterrows())
        lines.append(f"| {formal.loc[key,'name']} | {anchor_label} | {a.rho:.3f} | {other} |")
    lines += ['',
      '此外92项均与54个旧因子的120个保存信号日比较，记录最相关前三项：[nearest_old_top3_signal_grid.csv](nearest_old_top3_signal_grid.csv)。这份较宽覆盖只用于诊断，不能替代主口径逐交易日相关性；旧参考的原有符号保留，按绝对rho排序，未映射项保留composite_or_unassigned。', '',
      '## 审计、判断与产物','',
      '通过54个日线候选和2个Sharpe补项的截断重算、未来公告追加不改变历史、老报告修订不覆盖最新季度、连续四季度TTM、label-1、10组、换手与成本、日度NAV/回撤核验；向量化相关性在缺失值/并列值/跨块条件下与独立逐日Spearman一致。详见[verification.json](verification.json)。这些检查验证所测实现，不证明供应商字段逐字节等价。', '',
      '原文叙述与代码方向冲突的HighOpen/CloseLow分别测试并标注；STV源代码100与论文1000分别保留；外部凸显权重函数缺失时按论文重建，不宣称精确代码复现。原文全窗口OLS等前视用法未直接移植。', '',
      '92次候选/对照检验对应Bonferroni示意门槛0.05/92≈0.000543。IC均值t检验p值保存在明细，仅作粗筛，尚未处理时间依赖；不能用显著IC代替成本后净收益或证明新增alpha。本轮存在多重检验和同样本筛选，没有真正提交后的样本外B，没有测试新腿加入现役整池的边际收益，也不预测官方排名。', '',
      '当前决策：暂不把这批结果直接纳入现役池或登记为已确认新簇。保留低特质波动作为已知对照，保留球队硬币和研发/银行公式档案；其它重复或成本不合格项记录原因。仍缺数据的源策略、未逐行核验的源码范围均保留在阅读台账，不宣称已测遍策略库。', '',
      '- [92项公式、源路径、相关性与决策CSV](recipe_decisions.csv)',
      '- [逐项结果CSV，五年与近期各92行](results.csv)',
      '- [公式和源哈希清单](recipe_manifest.json)',
      '- [主口径日均旧锚点相关性](daily_old_anchor_correlations.csv)',
      '- [市值+反转秩残差诊断](size_reversal_rank_residual.json)',
      '- [配置](config.json)、[数据审计](data_audit.json)、[实际完成状态](completion.json)', '',
      '每项逐期收益/持仓换手/Top20及持仓日度NAV在five_year/、recent/目录；signal_panels.pkl保存全部信号，market_arrays.pkl与财务缓存仅为本地续跑缓存。早期错误映射结果位于另一个目录并标记REJECTED_DIAGNOSTICS，未参与本报告统计。', '',
      '复现命令（仓库根目录运行；只本地计算）：', '',
      '```bash',
      'python scripts/quant_corpus_local_20261012.py',
      'python scripts/quant_corpus_verify_20261012.py',
      'python scripts/quant_corpus_correlations_20261012.py --scope daily',
      'python scripts/quant_corpus_correlations_20261012.py --scope saved --resume',
      'python scripts/quant_corpus_review_20261012.py',
      'python scripts/quant_corpus_report_20261012.py',
      '```', '',
      '## 全量候选净结果','',
      '| key | 因子 | 角色 | 五年净超额%/年 | 回撤% | 近期净超额%/年 | 判断 |',
      '|---|---|---|---:|---:|---:|---|']
    for _,r in table.iterrows():
        lines.append(f"| {r.key} | {r['name']} | {r.role} | {r.net_excess_pct:.2f} | {r.held_daily_max_drawdown_pct:.2f} | {r.recent_net_excess_pct:.2f} | {r.decision} |")
    (q.OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('report recipes',len(table),'coverage',coverage['review_levels'])

if __name__=='__main__':main()
