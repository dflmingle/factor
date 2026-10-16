"""Build reviewable, version-separated supplement without rewriting old cohort."""
import json
import pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'research_reports/platform_alignment'
B=R/'quant-corpus-accounting-completion-20261014'
I=R/'quant-corpus-accounting-interactions-20261014'
A=R/'quant-corpus-accounting-selected-audit-20261014'
OUT=R/'strategy-factor-mining-supplement-20261014'

def table(frame):return frame.to_markdown(index=False,floatfmt='.2f')
def main():
 OUT.mkdir(exist_ok=True);records=[];metas=[]
 for root in [B,I]:
  r=pd.read_csv(root/'results.csv');r['batch']=root.name;records.append(r)
  for m in json.loads((root/'recipe_manifest.json').read_text()):
   m.update(batch=root.name,output=str(root.relative_to(ROOT)),research_audit_complete=True,
     pool_validation='legacy shared-support only; not official live DeltaComb',independent_oos=False,
     new_cluster_confirmed=False);metas.append(m)
 allresults=pd.concat(records,ignore_index=True);allresults.to_csv(OUT/'all_new_cohort_results.csv',index=False)
 pd.DataFrame(metas).to_csv(OUT/'candidate_inventory.csv',index=False)
 raw=allresults[allresults.form.eq('raw')].pivot(index='key',columns='window',values='net_excess_pct')
 dual=allresults[allresults.form.eq('size_reversal_rank_residual')].pivot(index='key',columns='window',values='net_excess_pct')
 triples=pd.read_csv(I/'incremental_information.csv').pivot(index='key',columns='window',values='net_excess_pct')
 stats=allresults[allresults.form.eq('raw')&allresults.window.eq('five_year')].set_index('key')
 review=pd.DataFrame(metas)[['key','name','formula','source_paths','output']].set_index('key')
 for window in ['five_year','recent']:
  review[f'raw_{window}_net_pct']=raw[window];review[f'dual_{window}_net_pct']=dual[window];review[f'triple_{window}_net_pct']=triples[window]
 review['raw_five_year_dd_pct']=stats.held_daily_max_drawdown_pct
 review['raw_five_year_turnover_pct']=stats.turnover_pct
 review['decision']='reject_or_archive_weak'
 review.loc['coherent_seasonal_revenue_sue3','decision']='retain_weak_incremental_existing_recipe_audit'
 review.loc['quarter_deducted_roa_yoy_change','decision']='retain_conditional_growth_diagnostic_not_new_cluster'
 review.to_csv(OUT/'candidate_review.csv')
 for filename in ['daily_anchor_correlations.csv','nearest_old_top3_signal_grid.csv']:
  rs=[]
  for root in [B,I]:
   x=pd.read_csv(root/filename);x['batch']=root.name;rs.append(x)
  combined=pd.concat(rs,ignore_index=True);combined.to_csv(OUT/filename,index=False)
  if filename.startswith('daily'):
   nearest=combined.assign(abs_rho=combined.rho.abs()).sort_values('abs_rho',ascending=False).groupby('candidate').head(3)
   nearest.to_csv(OUT/'daily_nearest_three_available_anchors.csv',index=False)
 nearest=pd.concat([pd.read_csv(root/'old_reference_signal_grid_correlations.csv') for root in [B,I]],ignore_index=True)
 nearest['abs_rho']=nearest.rho.abs()
 # Top3 factors can contain the same cluster; save distinct labelled clusters
 # separately and never convert signal-grid diagnostics to daily correlations.
 nearest=nearest[~nearest.cluster.eq('composite_or_unassigned')].sort_values('abs_rho',ascending=False)
 nearest=nearest.drop_duplicates(['candidate','cluster']).groupby('candidate').head(3)
 nearest.to_csv(OUT/'nearest_available_distinct_cluster_labels_signal_grid.csv',index=False)
 selected=pd.read_csv(A/'results.csv');selected.to_csv(OUT/'selected_extra_controls.csv',index=False)
 pool=pd.read_csv(I/'shared_support_pool_scenarios.csv')
 pick=pool[pool.candidate.isin(['coherent_seasonal_revenue_sue3','quarter_deducted_roa_yoy_change'])]
 pick.to_csv(OUT/'selected_pool_diagnostics.csv',index=False)
 display=review.reset_index()[['name','raw_five_year_net_pct','raw_recent_net_pct','triple_five_year_net_pct','triple_recent_net_pct']]
 display.columns=['候选','原始五年净超额%','原始近期净超额%','三控制五年%','三控制近期%']
 pooldisplay=pick[['candidate','scenario','window','net_excess_pct','held_daily_max_drawdown_pct','turnover_pct','corr_size','size_reversal_residual_net']]
 summary='''# 策略库挖掘补研究：财务单季化与增量审计（2026-10-14）

本轮实际完成14条本地候选测试，保留2条弱研究线索，尚无达到GOAL.md准入标准的强新因子。14条包括1条旧季节收入惊喜的同机制审计重算与13条新适配/交互规格，不能称14个新独立因子。旧193条待审队列不因本轮被整体标记完成。

最有价值的补充是确认**季节收入惊喜有小幅新增信息**：同时控制市值、20日反转、已知低IVOL后，五年净超额6.02%、近期5.94%；加ROE和BM后4.70%/4.30%，再控制利润同比增长后4.91%/5.60%。它的原始公式此前已研究，本轮新增的是更完整的财务、风格和池级审计，**不是新簇发现**。

扣非盈利同比资产增量原始五年−2.69%、近期16.21%，但三控制后仅1.46%/4.67%，加全部成长质量控制后0.32%/1.58%。它与已有N02成长簇相近，保留状态诊断用途，不列为强新alpha。

## 固定口径与完成工作

- 沪深全A `.SH/.SZ`、qfq、total_mv、20180101暖机、平台保存的120个10日信号期、10组、label `close(t+1)→close(t+11)`、factor_valid、0.30%单边成本、算术年化。
- 五年请求20210907–20260907，近期请求20260101–缓存最新20260907；实际信号20210907–20260810、最终退出20260825。近期15期与五年重叠，不是独立OOS。
- 报表按 `max(ann_date,f_ann_date)` 公告顺序接入，旧报告修订只在公布后影响计算；以已公布最新收入报告期为锚，其它报表匹配同一季度，缺季保持NaN。收入、成本、现金流YTD还原单季，扣非盈利使用q_dtprofit。
- 复核4篇完整源文件、保存文本和SHA256；收入惊喜来源是可转债策略，EPS/MS来源是沪深300蓝筹策略，本轮只适配全A选股原子。行业、债券溢价、分红、交易执行未复现，不称完整策略。
- 12只实际股票原始公告重放与两个截断重算通过；独立字典重放与数值实现一致；晚到旧季修订、YTD差分的人工案例通过。1211个交易日主口径相关性与54条旧因子保存信号网格相关性分别记录。
- 单季毛利稳定性与现金净增加额替代假设实际被证伪：前者五年−3.77%、近期−2.62%；后者五年−0.45%、近期1.05%。未以经营现金流冒充净现金增量。
- 没有调用新平台回测、修改线上因子池；本轮平台算力0。独立新目录沿用规则qualitygate4并带本轮arithmetic/fullA研究后缀，旧结果不覆盖、不合成跨版本总榜。

## 全部候选结果

三控制是横截面同时回归市值、20日反转、已有CAPM低IVOL的秩残差，只是归因诊断；并非已获平台验证的因子。

'''+table(display)+'''

60日未定价与反转乘积没有改善：多条换手达35%–54%，扣费后的结果弱或负。不得因毛收益或低相关而晋级。

## 季节收入惊喜的分年与相关簇

六控制残差逐年度净超额：2021片段14.79%、2022 6.80%、2023 2.58%、2024 0.58%、2025 6.01%、2026片段5.65%。全窗口按初期换手排除规则计算4.91%，与片段单独平均不要求相等；六控制五年持仓日频回撤34.71%、换手14.13%。分年均正仍是搜索后的样本内证据。

季节收入惊喜与旧季节配方公式相同，日值精度从float32累计差分改为float64再输出，有限掩码相同；保存信号网格秩相关0.99999999985。历史配方未删除，新目录独立保存数值差异审计。

原始季节收入惊喜的每日最近三个**可用锚点**：N27 ROE代理+0.3758、B01 SIZE−0.2005、H03 IMPACT代理−0.1553（按绝对相关排序）。在54个保存信号网格参考中，最近因子为N30资产周转历史秩+0.3955、未归簇资产增长+0.3856、N10 ROIC+0.3695；这是120信号期诊断，不能称完整日频全簇归属。

扣非盈利增量的保存信号网格最近三簇为N02成长+0.6919、N29净利率历史秩+0.5433、N10 ROIC+0.3132，已有成长信息占比大。不创建U编号。

## 加入保存旧五席的诊断

每个候选的基线和加席在同一有效支持集上重建；采用每个日期横截面zscore等权，保留成本和实际组成员换手。本表为旧qualitygate3保存席位研究诊断，**不代表当前线上池或官方DeltaComb**，不同候选基线支持集略不同。

'''+table(pooldisplay)+'''

季节收入惊喜加第六席：五年净超额+0.17pp、回撤−0.77pp、换手+0.39pp/次；近期净超额+0.50pp、回撤−0.51pp。扣非增量加席五年净超额+0.52pp、回撤−0.27pp；近期+2.57pp。两条的池size相关下降、size/反转残差净额上升，但仍须正式池与积分全账验证。

按6个调仓期的圆形块bootstrap做4000次探索性配对检查：季节收入五年加席收益路径增量95%区间约[−0.63,+1.00]pp，扣非增量[−0.47,+1.56]pp。区间包含零，尚未证实稳定组合改善；此检查也没有校正全库多重搜索。

## 市场状态与竞赛门槛

状态用当时可观测全A等权市场120日收益正负、60日波动高于过去252日滚动中位数分组，参数未搜索。季节收入惊喜原始信号在上涨高波动34期净超额11.09%，下跌高波动38期0.78%，上涨低波动43期−3.47%，下跌低波动仅5期−12.56%。这支持后续状态研究，不能事后按赢家部署。明细留存observable_regime_diagnostics.csv。

本地RankIC席位代理S_i：季节收入原始约0.000020、三控制残差0.00191；扣非增量原始约0.000018、三控制0.00306，均低于0.035门槛，亦无15%五年净额。残差收益较好不等于比赛席位高分，暂不占用平台算力或纳入正式池。

本轮最值得保留的是季节收入惊喜的弱独立信息；扣非增量仅作成长/状态补充。下一阶段应验证这条弱增量在未触碰日期及正式池中的作用，而非扩大这些已证伪的毛利稳定/反转乘积变体。

## 产物索引

- [14条候选审阅表](candidate_review.csv)、[独立批次结果](all_new_cohort_results.csv)、[候选公式与源路径](candidate_inventory.csv)。
- [每日最近三个可用锚点](daily_nearest_three_available_anchors.csv)、[保存信号日最近三个旧参考](nearest_old_top3_signal_grid.csv)、[去重簇标签参考](nearest_available_distinct_cluster_labels_signal_grid.csv)。
- [财务重放与第一批8条](../quant-corpus-accounting-completion-20261014/)、[第二批6条、三控制、组合与状态](../quant-corpus-accounting-interactions-20261014/)、[额外成长质量控制与不确定性](../quant-corpus-accounting-selected-audit-20261014/)。
'''
 (OUT/'summary.md').write_text(summary,encoding='utf-8')
 (OUT/'completion.json').write_text(json.dumps(dict(completed=True,local_specs=14,old_recipe_audited_retest=1,new_adaptation_specs=13,
   local_form_window_rows=56,extra_triple_control_rows=28,extra_quality_control_rows=8,legacy_pool_scenario_window_rows=54,
   strong_new_factors=0,weak_lines_retained=2,confirmed_new_clusters=0,platform_compute_spent=0,
   independent_oos=False,formal_live_pool_validation=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('REPORT_COMPLETE',flush=True)
if __name__=='__main__':main()
