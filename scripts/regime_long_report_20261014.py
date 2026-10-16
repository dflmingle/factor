#!/usr/bin/env python3
"""Write the research report from saved audit and result files only."""
import json
import pandas as pd
import regime_long_history_data_20261014 as d
import regime_long_base_replay_20261014 as b
import shu_mulvey_long_base_20261014 as m

def main():
    out=d.OUT
    ap=out/'market_assembly_audit_aliasdedup_v3.json'
    if not ap.exists():ap=out/'market_assembly_audit.json'
    audit=json.loads(ap.read_text());download=json.loads((out/'download_verification.json').read_text());fin=json.loads((out/'financial_verification.json').read_text())
    text=f'''# 长历史训练数据与动态因子配置

数据已补齐并通过完整性检查。行情从{audit['history_start']}起，与原始2018年以后的快照衔接到{audit['latest']}，共{audit['calendar_rows']}个交易日、{audit['symbols']}只历史股票；新增{audit['historical_only_symbols']}只原快照未覆盖的历史股票。正式五年评估窗口、保存的信号日期和原始因子面板保持不变。

## 数据完成情况

- 2006—2017年{download['historical_trading_days']}个交易日，每日复权行情和全A daily_basic全部下载；{download['files']}份原始数据文件完成SHA-256与行数检查。
- 四类VIP财报接口、48个季度，共192份完整字段快照。接口默认字段缺少研发、现金流收入比和租赁负债等列，已显式补拉。原始默认快照保留。
- 公告连接取`max(ann_date,f_ann_date)`，按披露顺序更新季度，TTM使用连续季度还原；{fin['quarantined_rows']}条异常公告日期记录已隔离，保留原始记录。
- 上证、沪深300、中证500、深证成指、创业板指和SHIBOR按年下载至2026-10-14。创业板与SHIBOR早期可用范围不同，详见`environment_series_coverage.csv`。
- 中债收益率`yc_cb`无接口权限。SHIBOR不能被称为论文2年/10年国债收益率的等价字段；宏观修订指标未用于训练。

## 复权和正式窗口保护

三个2018年重叠日期可校准{audit['anchored_symbols']}只股票，按股票取固定比例衔接；最大锚点比例误差{audit['max_anchor_relative_error']:.8f}。原2018年后所有基础字段逐值相等，包括NaN。

{audit['unanchored_historical_symbols']}只历史股票没有重叠锚点，使用Tushare原生qfq并标记价格尺度代理，名单在`unanchored_historical_stocks.csv`。这会限制绝对价格类因子早期收益的解释；不能把它们称为平台字节等价数据。原生历史财务也缺少完整首次披露版本，按公告连接仍属PIT代理，重复公告不同update_flag的冲突已列出。

股票池按历史数据并集构建，含后来退市的股票，不使用当前名单倒推历史。只对收盘价前向填充，OHLC其余列、量额不填；活跃池由当日total_mv判定。退市处理沿用本地终止价格代理，不声称复现实际清算。

原始日线交叉检查发现旧代码000022/000043的复权历史映射到001872/001914，daily_basic同时保留相同市值的旧、新代码。训练视图只在历史日市值确实相等且旧代码缺复权价时剔除旧别名，避免同一公司重复影响截面；原始快照和正式窗口保留。明细见`historical_code_alias_dedup.csv`，覆盖率见`historical_active_field_coverage_aliasdedup_v3.csv`。

## 研究完成边界

592个主因子全部有重放清单；583个找到实现脚本。找到脚本不等于长历史复现完成，具体重算状态逐条记录。原始92条因子优先作同一集合的短/长训练对照，之后扩展可直接重放的量价和安全K线因子。未按历史收益正负筛选。

长训练目标为2016—3024个有效日观测（约8—12年），验证最多151个已完成持有期，至少126条已有预测的持有期才计算验证可靠性；未达门槛时默认lambda50。早期不能保证完整6个日历年验证，实际训练天数、验证退出日期及观测数逐条保存。

正式评价继续使用全A/qfq/total_mv/label-1/10组/factor_valid/单边0.30%成本、算术年化；近期2026年窗口独立。原正式保存网格末信号2026-08-10、末退出2026-08-25。增加早期训练历史不是增加当前正式评价的末日覆盖。

''' 
    study_out=m.OUT
    expanded=out.parent/'shu-mulvey-long-ready-20261014'
    if (expanded/'verification.json').exists() and json.loads((expanded/'verification.json').read_text()).get('completed'):study_out=expanded
    verification=study_out/'verification.json'
    if verification.exists() and json.loads(verification.read_text()).get('completed'):
        result=pd.read_csv(study_out/'results.csv');count=json.loads(verification.read_text())['replayed_factors']
        text+=f'## 已完成的长训练结果\n\n本表覆盖{count}条已成功重放、属于主比较清单的因子，不代表全部592条长模型完成。完整结果目录为`{study_out.name}`。以下为本地存档mingle的固定20%袖套诊断；存档池为代理，不是当前平台池。\n\n'
        text+='| 配置 | 五年净超额% | 每次换手% | 日频最大回撤% | 近期净超额% |\n| --- | ---: | ---: | ---: | ---: |\n'
        keys=['ARCHIVED_MINGLE','SHORT_TE2_POOL20','LONG_TE2_POOL20','SHORT_TE4_POOL20','LONG_TE4_POOL20','SHORT_TE2_TURN_POOL20','LONG_TE2_TURN_POOL20']
        for key in keys:
            a=result[(result.key==key)&(result.window=='five_year')].iloc[0];r=result[(result.key==key)&(result.window=='recent')].iloc[0]
            text+=f"| {key} | {a.net_excess_pct:.2f} | {a.turnover_pct:.2f} | {a.held_daily_max_drawdown_pct:.2f} | {r.net_excess_pct:.2f} |\n"
        text+='\n预测日期、已完成标签、截断重算和未来扰动检查通过；这仍是已挖掘历史上的探索性因果重放，不能称为未接触过的样本外结果。对照同时改变训练和验证长度，已下载的利率没有加入该比较；结果反映训练与验证历史扩展的联合影响，不能单独归因于训练长度。\n'
        coverage_file=out/'replay_coverage_latest.json'
        if coverage_file.exists():
            coverage=json.loads(coverage_file.read_text())
            text+=f"\n实际覆盖：592条主因子中已重放{coverage['replayed']}条，仍有{coverage['pending_replay']}条待适配；扩展长模型有{coverage['long_models_with_formal_forecasts']}条在正式窗口形成预测。其余已重放因子未产生预测，不按收益好坏删掉，原因写在`all_factor_replay_inventory_completed.csv`。本轮不能称为全部592条长历史模型已完成。\n"
        diagnostics=study_out/'factor_state_specialists_descriptive.csv'
        if diagnostics.exists():
            ss=pd.read_csv(diagnostics)
            if 'formal_global_net_excess_pct' in ss:
                specialists=ss[(ss.formal_global_net_excess_pct<0)&(ss.conditional_net_excess_pct>0)&(ss.formal_periods>=25)]
                text+=f"\n该集合中{specialists.key.nunique()}条因子在五年总体净超额为负的同时，至少一个线上识别状态下为正且至少25期。它们属于事后条件诊断，包括离散K线和并列敏感代理，不能称为同等可信的好alpha，不能用其正式期状态收益挑选参数或解释为新增独立簇。\n"
        eq=result[(result.key=='ARCHIVED_MINGLE')&(result.window=='five_year')].iloc[0];long=result[(result.key=='LONG_TE2_POOL20')&(result.window=='five_year')].iloc[0]
        text+=f"\n**本轮决策：暂不进池。** TE2%长训练固定20%叠加净超额{long.net_excess_pct:.2f}% vs 原池{eq.net_excess_pct:.2f}%，回撤改善{eq.held_daily_max_drawdown_pct-long.held_daily_max_drawdown_pct:.2f}pp，但每次换手增加{long.turnover_pct-eq.turnover_pct:.2f}pp。下一步研究应针对已完成标签的预测能力、因子簇重复权重和池级换手，不因个别状态的事后正收益自动加席。239条剩余重放任务有明确脚本/签名清单。\n"
    else:text+='首轮长训练尚未完成，暂不报告任何长历史收益提升。状态见`pipeline_status.json`，数据下载完成不能替代模型结果。\n'
    forward=out.parent/'shu-mulvey-forward-views-20261014'
    if (forward/'verification.json').exists() and json.loads((forward/'verification.json').read_text()).get('completed'):
        fr=pd.read_csv(forward/'results.csv');x=fr[(fr.key=='FORWARD_TE4')&(fr.window=='five_year')].iloc[0];y=fr[(fr.key=='FORWARD_TE4_POOL20')&(fr.window=='five_year')].iloc[0]
        text+=f'''\n## 额外的持有期观点校准（原始92条集合）

按已完成的10日label-1净超额校准SJM状态观点，最多151期、同状态至少12期，向全局均值收缩20个伪观测；半年选择参数，仅使用历史保存的校准预测。模型状态和长训练数据不变。它是本地论文扩展，不是论文原始算法，也是在观察失败后提出的探索性方案。

TE4%动态袖套五年净超额为{x.net_excess_pct:.2f}%，20%存档池叠加为{y.net_excess_pct:.2f}%，每次换手{y.turnover_pct:.2f}%，回撤{y.held_daily_max_drawdown_pct:.2f}%。已完成标签日期、未成熟未来标签扰动、截断配置和权重约束检查通过。原池净超额20.32%、换手14.28%、回撤39.96%，因此这个改善仍不足以证明进池收益增量。

原始92条中24条满足五年整体净超额为负、至少一个线上识别状态下净超额为正且至少25个持有期。该数量来自事后条件统计，用于研究诊断，**不等于24条可以事前稳定选择的赢家**；详见`shu-mulvey-long-base-20261014/factor_state_specialists_descriptive.csv`。\n'''
    text+='\n平台调用和平台算力消耗为0；未修改现役池。数据、规则、代理变化均保存在独立目录，没有覆盖原始五年产物。\n'
    incumbent=out.parent/'shu-mulvey-incumbent-prior-20261014'
    if (incumbent/'verification.json').exists() and json.loads((incumbent/'verification.json').read_text()).get('completed'):
        ir=pd.read_csv(incumbent/'results.csv');a=ir[(ir.key=='CORE_TE2')&(ir.window=='five_year')].iloc[0];c=ir[(ir.key=='ARCHIVED_MINGLE')&(ir.window=='five_year')].iloc[0];r=ir[(ir.key=='CORE_TE2')&(ir.window=='recent')].iloc[0]
        text+=f'''\n## 以存档池为配置基准并限制额外换手

额外适配固定存档mingle为Black–Litterman先验，至少80%核心权重，动态部分最多20%；因子相对池的观点只用已完成持有期收益校准。选股层面，每次额外替换不超过2个百分点，比较对象为从同一上期研究持仓出发的当前原池目标；这不是官方月度换手上限。

TE2%版五年净超额{a.net_excess_pct:.2f}%（基线{c.net_excess_pct:.2f}%，仅+{a.net_excess_pct-c.net_excess_pct:.2f}个百分点），换手{a.turnover_pct:.2f}%（基线{c.turnover_pct:.2f}%），五年回撤{a.held_daily_max_drawdown_pct:.2f}%（与基线相同）。近期净超额{r.net_excess_pct:.2f}%，低于原池12.02%；size截面秩相关{c.size_rank_rho:.4f}→{a.size_rank_rho:.4f}。差异太小，回撤未改善，且size相关上升，未通过项目池级准入要求。当前判断为保留研究、暂不进池。

截断的权重与股票分数重算、已完成核心标签日期、至少80%核心权重和额外2pp替换预算检查通过。现有核心历史不足时保持原池，未倒推早期原池收益。
'''
    (out/'summary.md').write_text(text)
    print('LONG_HISTORY_REPORT_WRITTEN',flush=True)

if __name__=='__main__':main()
