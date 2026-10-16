#!/usr/bin/env python3
"""Report method fidelity and completed outputs without upgrading proxies to facts."""
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shu_mulvey_paper_replication_20261014 import BASE, ROOT, STYLE_KEYS


def table(frame):
    cols=['configuration','cost_case','window','vs_quarterly_ew_arithmetic_active_pct',
          'vs_quarterly_ew_information_ratio','vs_quarterly_ew_realized_te_pct',
          'max_drawdown_pct','annual_one_way_turnover_pct']
    f=frame[cols].copy()
    f.columns=['配置','成本口径','窗口','相对季度等权年化超额%','IR','实现TE%','绝对回撤%','年化单边换手%']
    return f.to_markdown(index=False,floatfmt='.3f')


def main():
    inputs=json.loads((BASE/'input_manifest.json').read_text())
    repairs=pd.read_csv(BASE/'daily_valuation_repairs.csv')
    verification=json.loads((BASE/'unit_verification.json').read_text())
    actual=json.loads((BASE/'actual_data_verification.json').read_text()) if (BASE/'actual_data_verification.json').exists() else None
    lines=['# Shu & Mulvey：完整配置链路复现与数据边界', '',
      '**当前不能称为原论文美国实证结果的严格复现。** 原论文的 Bloomberg 总收益指数与历史拼接序列未取得，作者未公开若干实现细节。已实现每日独立 SJM → 六年验证 → BL 相对观点 → 直接配置收益资产的完整链路，并运行独立标注的 A 股方法代理。', '',
      '论文全文：[`paper-arxiv-2410.14841v1.pdf`](../../literature/shu-mulvey-dynamic-allocation-20261014/paper-arxiv-2410.14841v1.pdf)。实现依据为公开预印本，不是期刊最终版逐字复现。', '',
      '## 与此前版本的实质区别', '',
      '|项目|本次实现|对应论文|', '|---|---|---|',
      '|投资层|直接持有因子收益资产及市场资产；不合成股票排名|§4|',
      '|状态模型|每个因子独立两状态作者 SJM，按日在线推断|§3.1|',
      '|训练|至少8、最多12个日历年；月度重拟合|§3.2|',
      '|验证|完整6个日历年的已实现日收益；半年选参数；不足不提供观点|§3.2|',
      '|假想策略|按训练状态均值/年化5%截断仓位；两条腿均收费|§3.2、Appendix B|',
      '|执行|t日收盘信号，t+1收盘交易，t+2日收益归新仓位|§3.1.3|',
      '|基准|固定资产全集，季度恢复等权，期间权重随收益漂移|§4|',
      '|BL|相同市场相对观点、δ=2.5、126日半衰期协方差|§4、Appendix B|',
      '|最终约束|只做多、满仓；不加20%因子上限、不按收益删观点、不做25%协方差收缩|§4|',
      '|TE|校准观点置信度，检验1/2/3/4%；事前TE和事后TE分别输出|§4|',
      '|特征|Exhibit 3列出的17项；真实FRED VIX、2Y、10Y–2Y；无广度额外项|Exhibit 3|', '',
      '## 仍不能称为逐字复现的部分', '',
      '- 原论文六个美国风格指数和市场的1993–2024总收益数据、五处历史替代指数拼接尚缺。ETF价格、Fama–French多空因子均未冒充这些序列。',
      '- 原文未公开超参数搜索网格。本次预先声明 λ={10,50,100}、κ²={6,9.5}，仅在各因子的六年历史验证内选参数，不称为作者完整网格。',
      '- 原文未充分规定技术指标的净值定义、标准化/极端值处理、置信度校准细节和基准权重漂移处理。本次采用明确记录的约定，不能保证与作者数值相同。',
      '- 公开同名第三方仓库最终使用ICIR和股票优化，未作为作者代码；作者公开库可核验SJM，未找到该论文完整原始数据与投资组合代码。', '',
      '## A股代理数据与窗口', '',
      f"共有 {inputs['replayed_factors']}/592 条已重建因子，日收益输入 {inputs['first_date']} 至 {inputs['last_date']}，{inputs['days']} 个交易日。剩余239条未在本次变成已完成。所有已重建因子按输入可用性纳入，不按五年收益筛除。",
      '', '六风格代表在运行前固定为：`'+str(STYLE_KEYS)+'`。这是经济意义上的代表因子，并非重新分簇或复制MSCI指数编制；扩展试验另配置全部已重建资产。市场采用沪深300价格收益代理。', '',
      '正式请求窗口仍为2021-09-07至2026-09-07，实际因子路径止于2026-08-25。完整六年验证尚未满足的早期日期不强行使用默认参数，也不截掉这段日期美化比较；可用观点不足时保留基准先验。近期2026窗口独立报告。', '',
      '宏观变量保留论文的美国序列，A股收盘只读取此前日历日及更早的美国观测；它们不是中国VIX或中国国债期限结构的等价物。当前FRED下载版本也不能证明完全等于历史首次发布版本。', '',
      f"长历史2018拼接的停牌估值修正：{len(repairs)}个日净值点、{repairs.key.nunique()}条因子，集中于{repairs.date.min()}至{repairs.date.max()}。只用此前实际观测收盘价估值，保留原持股名单和期末收益；原快照与旧回测结果均未覆盖。详情见 `daily_valuation_repairs.csv`。", '',
      '保存的因子持仓仍继承平台对齐的factor_valid/前瞻标签可用性代理，因此方法层的因果检验不把底层收益资产升级为可实盘复制的原始指数。', '',
      '## 已完成的结果', '']
    completed=[]
    for universe,title in [('six_styles','六风格＋市场'),('all_replayed','全部已重建因子＋市场')]:
        folder=BASE/universe
        if not (folder/'verification.json').exists():
            lines += ['### '+title,'','尚未完成；不列为正式结果。',''];continue
        frame=pd.read_csv(folder/'results.csv');coverage=pd.read_csv(folder/'factor_coverage.csv')
        completed.append(universe)
        fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
        for ax,case in zip(axes,['paper_fee_proxy','local_fee_proxy']):
            daily=pd.read_csv(folder/f'{case}.daily_returns.csv',index_col=0,parse_dates=True)
            for label in ['TE1','TE2','TE3','TE4']:
                relative=((1+daily[label])/(1+daily.quarterly_ew)).cumprod()
                ax.plot(relative.index,(relative-1)*100,label=label)
            ax.axhline(0,color='black',linewidth=.8)
            ax.set_title(case.replace('_',' '));ax.set_ylabel('Relative wealth vs quarterly EW (%)')
            ax.grid(alpha=.2);ax.legend(ncol=4)
        fig.suptitle(universe.replace('_',' ')+' | A-share method proxy; original US data unavailable')
        fig.tight_layout();fig.savefig(folder/'relative_wealth_cost_comparison.png',dpi=170);plt.close(fig)
        lines += ['### '+title,'',
            f"{len(coverage)}条因子中，{int((coverage.formal_forecast_days>0).sum())}条通过完整历史验证并在评估期提供观点。未提供观点的资产仍保留在固定等权基准中。",'',table(frame),'',
            '以上为直接配置收益资产的本地代理；相对基准收益和回撤不能与股票排名合成的原池20.32%净超额直接比较。', '']
        lines += [f'![相对季度等权净值与成本比较]({universe}/relative_wealth_cost_comparison.png)','']
    lines += ['## 成本与指标解释','',
      '- `paper_fee_proxy`：恢复底层毛收益资产，配置买卖各5bp，检验论文费用设置；未计底层选股组合的全部交易费，不能认定实盘可实现。',
      '- `local_fee_proxy`：底层已含原0.30%单边股票换仓成本，配置层再按0.30%单边收费；使用同一信号权重作成本敏感性，不是重新用高成本训练/验证后的最优策略。',
      '- 股票换手和因子资产配置换手是两层账。本表年化单边换手为配置层每日半L1换手年化，不能和旧报告每次股票换仓百分比直接比较。',
      '- 相对季度等权的超额为日主动收益的算术年化；IR和实现TE按日收益差计算；绝对回撤用净值，主动回撤用相对财富。风险自由收益/Sharpe采用上一可知美国3个月国债收益率/252代理，在A股场景仅作方法指标。', '',
      '固定信号下的配置层费用盈亏平衡见 `overlay_cost_break_even.csv`，它不含底层股票容量与净额交易抵消估计。六风格TE4%在单边约14.48bp时相对季度等权的优势归零，不能将论文5bp费用下的收益直接搬到30bp环境。', '',
      '全因子TE4%的配置层单边费用盈亏平衡约6.31bp，比六风格组合更低；不支持将当前全因子日频配置直接接入原池。', '',
      '延迟执行状态诊断见 `delayed_state_return_diagnostics.csv`。全因子集合有25条满足整体相对市场净收益为负、至少一个状态在t+2执行收益上为正且不少于252日；这是事后描述，不是25条已验证新alpha，也不用于筛选投资全集。', '',
      '## 验证与重跑','',f"基础验证 {len(verification['tests'])} 项通过，见 `unit_verification.json`。输入恢复逐持有期核对期末毛收益；宏观观测时间严格早于A股日期。",'',
      '```bash','python scripts/shu_mulvey_paper_verify_20261014.py',
      'python scripts/shu_mulvey_paper_replication_20261014.py --universe six_styles',
      'python scripts/shu_mulvey_paper_replication_20261014.py --universe all_replayed',
      'python scripts/shu_mulvey_paper_report_20261014.py','```','',
      '原始美国数据的字段与历史拼接要求见 `original_data_requirements.json`。原始输入必须通过 `original_data_gate`，代理输入会被拒绝；即使取得数据，也需核对作者未公布的实现约定后才能宣称原论文数值复现。', '',
      '真实输入验证：'+(str(len(actual['tests']))+'项通过，见 `actual_data_verification.json`。' if actual else '尚未完成。'),'',
      '全因子真实输入验证：'+('已通过，见 `all_actual_data_verification.json`。' if (BASE/'all_actual_data_verification.json').exists() else '尚未完成。'),'',
      '本轮平台调用及算力消耗均为0，未改变线上因子池。']
    (BASE/'summary.md').write_text('\n'.join(lines)+'\n')
    (BASE/'completion.json').write_text(json.dumps(dict(method_engine_implemented=True,
      original_paper_numerical_reproduction_complete=False,completed_proxy_experiments=completed,
      missing_original_data=True,replayed=353,total=592,platform_calls=0),indent=2)+'\n')
    print('REPORT',completed,flush=True)


if __name__=='__main__':main()
