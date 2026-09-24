"""Rank saved eligible competition pools horizontally; no live runs or invented score."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
P=Path('research_reports/platform_alignment/pool-screen-20260921')
O=Path('research_reports/platform_alignment/pool-horizontal-selection-20260921');O.mkdir(exist_ok=True)
d=pd.read_csv(P/'pools.csv');c=pd.read_csv(P/'candidates.csv');allsub=pd.read_csv(P/'all_subsets.csv').set_index('components')
base=d[~d.contains_new_proxy].copy()
# Fixed ranking: existing eligibility evidence first, training net return second;
# validation/recent are shown as diagnostics, never used as a hidden sort key.
for frame,name in [(base,'aligned_base_pools'),(d,'all_diagnostic_pools')]:
 frame=frame.sort_values(['train_net_excess_pct','components'],ascending=[False,True]).copy()
 frame.insert(0,'train_rank',range(1,len(frame)+1))
 frame.to_csv(O/(name+'.csv'),index=False)
# Training Pareto frontier. It is not an approximation of the official weighted score.
objectives=['train_net_excess_pct','train_sharpe_after_cost','train_max_drawdown_pct','train_turnover_pct','platform_A_raw_mean']
x=base[objectives].to_numpy()*np.array([1,1,-1,-1,1]);keep=[]
for i in range(len(x)):
 keep.append(not np.any(np.all(x>=x[i],axis=1)&np.any(x>x[i],axis=1)))
base['training_pareto']=keep
base[base.training_pareto].sort_values('train_net_excess_pct',ascending=False).to_csv(O/'training_pareto.csv',index=False)
primary='SIZE+H03+RET40+CHIP250+ASSET_GROWTH'
ready='SIZE+H03+RET40+DD120+CHIP250'
lowturn='SIZE+H03+DD120+CHIP250+ASSET_GROWTH'
primary_row=d[d.components.eq(primary)].iloc[0]
# Exact equal-count substitutions: these diagnose relative choices, not only component synergy.
changes=[];pool=set(primary.split('+'))
for old in pool:
 for new in set(c.key)-pool:
  target=(pool-{old})|{new}
  match=d[d.components.map(lambda s:set(s.split('+'))==target)]
  if match.empty:continue
  r=match.iloc[0]
  changes.append({'remove':old,'add':new,'pool':r.components,'new_proxy':r.contains_new_proxy,**{w+'_net_pct':r[w+'_net_excess_pct'] for w in ('train','test','full','recent')},**{w+'_delta_pp':r[w+'_net_excess_pct']-primary_row[w+'_net_excess_pct'] for w in ('train','test','full','recent')},'turnover_delta_pp':r.full_turnover_pct-primary_row.full_turnover_pct,'drawdown_delta_pp':r.full_max_drawdown_pct-primary_row.full_max_drawdown_pct})
pd.DataFrame(changes).sort_values('train_net_pct',ascending=False).to_csv(O/'one_seat_replacements.csv',index=False)
selected=[primary,ready,lowturn,'SIZE+H03+CHIP250+ASSET_GROWTH+C03','SIZE+H03+CHIP250+ASSET_GROWTH+C02','SIZE+H03+CHIP250+ASSET_GROWTH+C01','H03+RET40+DD120+CHIP250+ASSET_GROWTH','RET40+DD120+CHIP250+DD60+ASSET_GROWTH']
rows=pd.concat([d[d.components.eq(k)] for k in selected]);rows.to_csv(O/'shortlist.csv',index=False)

def table(frame):
 lines=['| 因子池 | 训练净超额 | 验证净超额 | 五年净超额 | 近期净超额 | 换手率 | 最大回撤 | 成本后夏普 |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for _,r in frame.iterrows():lines.append(f'| {r.components} | {r.train_net_excess_pct:.2f}% | {r.test_net_excess_pct:.2f}% | {r.full_net_excess_pct:.2f}% | {r.recent_net_excess_pct:.2f}% | {r.full_turnover_pct:.2f}% | {r.full_max_drawdown_pct:.2f}% | {r.full_sharpe_after_cost:.3f} |')
 return lines
lines=['# 比赛因子池横向筛选与提交建议','', '日期：2026-09-21。替代此前“必须超过自身最强组件”的提交推荐；保留此前结果作历史诊断。','',
'## 结论','',
'当前有条件首选：**SIZE + H03 + RET40 + CHIP250 + ASSET_GROWTH**，共5个独立入池条目。它在本次7个已对齐基础代表的29个合格池中，训练期净超额第一；验证期15.00%、五年13.62%，也为本轮全部638个池中的最高值。近期6.83%。这支持其作为当前搜索范围内优先验证的提交方案，而不是官方总分最优的保证。',
'如果要求五个条目均已保存10日平台回测，则采用备选 **SIZE + H03 + RET40 + DD120 + CHIP250**：五年11.33%、验证12.99%、近期3.41%。首选中的资产增长源记录是5日，需要在10日平台验证后才能把首选称为配置已准备齐全。',
'首选同时保留SIZE和H03是横向池比较得到的结果，不是凭同簇本地二因子结果直接推定。该池重复加重小市值/冲击暴露，应披露，不作为自动淘汰理由。',
'', '## 1. 规则与筛选方法','',
'- 规则依据：vendor/skill-pandaai-factor-online/references/competition_rules.md，用户提供的0811版本；没有在线核实后台变更。至少5个有效因子，最多50个。A/B/C权重20%/35%/45%。',
'- 以至少5个有效条目的完整池作横向比较，不要求超过自身最强单因子，不强制每簇只留一个。超过单因子、逐成员增益只作为归因。',
'- 范围：7个基础代表SIZE/H03/RET40/DD120/CHIP250/DD60/ASSET_GROWTH，及3个新复合因子C01/C02/C03；共1023个非空子集，638个满足5个及以上；其中29个不含未完成公式对齐的新复合因子。没有新平台调用。',
'- 主排序预先采用：对齐证据分层，然后按训练期成本后净超额降序；同时展示训练期风险与A代理的Pareto前沿。验证段与近期仅用于稳健性审阅，不作为暗中调整权重或排序的输入。既往已经看过这些区间，因此它们不是未接触的最终样本外。',
'- 组合规则为每个因子方向统一、截面1%–99%缩尾、Z-score后等权。单个新复合因子先按其原公式形成信号，再整体标准化，不拆成多个等权席位。',
'- 收益口径：沪深全A .SH/.SZ、qfq、total_mv、20180101暖机、保存的平台公共调仓日、10日调仓/10组、label-1、factor_valid基准、0.30%单边成本。规则版本full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1。',
'- 正式窗口20210907–20260907；训练截至20240906，之后为验证；近期20260101起。缓存至20260907，公共调仓日最后有效信号20260810；不代表最新至9月21日。近期是五年窗口的子集，独立展示，不能当作独立新增样本。',
'- 风险指标是10日持有期账本代理，最大回撤可能漏掉期内跌幅，不能直接当作官方月度日频C。',
'', '## 2. 已对齐基础池：横向前十名','']
lines+=table(base.sort_values('train_net_excess_pct',ascending=False).head(10))
lines+=['','## 3. 首选的五个提交条目','','| 条目 | 方向 | 源平台周期 | 平台单因子净超额 | 作用 |','|---|---:|---:|---:|---|']
roles={'SIZE':'市值核心','H03':'冲击/流动性；与SIZE同B01','RET40':'B03反转','CHIP250':'B05筹码','ASSET_GROWTH':'B10低资产增长'}
for k in primary.split('+'):
 r=c[c.key.eq(k)].iloc[0];lines.append(f'| {r["name"]} | {int(r.direction)} | {int(r.source_cycle)}日 | {r.platform_net:.2f}% | {roles[k]} |')
lines+=['','单因子平台净超额不相加、不平均作为池净超额。首选条目不含本轮三个新复合因子，并不是它们单独无效，而是它们在完整池中没有取得更好的验证/全期收益证据。','','## 4. 为什么这样选：关键横向对照','']
lines+=table(rows)
lines+=['',
'- 把首选的H03替换为DD120，得到SIZE+RET40+DD120+CHIP250+ASSET_GROWTH：五年从13.62%降至9.73%。把SIZE替换为DD120：降至9.70%。因而不能仅因SIZE与H03同簇就强行删去一个。它们共同入池仍未经过平台池级确认。',
'- 把首选中的RET40替换成C03：训练13.54%较好、换手23.08%较低，但验证降至12.80%、全期13.25%，近期4.78%；C03还缺完整公式对齐，因此保留为风险/换手备选，不能认定全面优于首选。',
'- 同一席替换成C02：训练13.54%、验证13.26%、全期13.43%、近期2.96%、换手22.54%；同样是降低换手的折中，不是无条件升级。',
'- 同一席替换成C01：全期13.57%、验证13.82%，仍未超过首选；C01本地单因子净超额与平台相差-5.21pp，已登记对齐失败，当前只作诊断。',
'- 在首选加入DD120成为6因子池：全期降至11.94%、验证12.97%、换手升至30.39%；七个基础全放入后全期10.54%。此范围内没有为数量增加席位的必要。',
'- 旧推荐RET40+DD120+CHIP250+DD60+ASSET_GROWTH虽然相对自身最强组件增加1.84pp，但池全期只有4.48%、近期-7.65%。横向明显弱于首选，不再推荐它作为比赛提交首选。',
'', '## 5. A/B/C能算什么，不能算什么','',
'**A历史代理**：用保存的平台摘要计算每条目的abs(RankIC)*abs(ICIR)*方向对应IC胜率，再求池均值。首选rawA约0.01104，不计Decay的归一化代理约0.1380；全10日源记录备选rawA约0.01171、归一化约0.1463。资产增长在首选中改善本地池收益，却稀释A代理，正体现评分目标间的取舍。首选的资产增长源周期为5日，混周期A只能作诊断；不能宣称该值就是正式NA。',
'**B**：只有正式生效后新增记录才算官方B，本次无该数据，保持缺失。历史验证段不能冒充NB。',
'**C**：官方基于月度日频账本、月累计换手、中证全指和月最大回撤。本次只有canonical本地持有期收益代理，不能把全期净超额/换手/夏普代入官方C公式，也不能生成可信20/35/45总分。本报告按多指标给出池级候选，不编造综合积分。',
'首选不是风险各项都第一；若只追求低换手，DD120替换RET40的基础备选换手22.75%、回撤33.45%，但全期12.49%、验证12.35%、近期2.76%，收益与A代理更弱。该权衡已保留，不以随意加权的“总分”掩盖。',
'', '## 6. 提交路径与条件','',
'1. 优先准备SIZE/H03/RET40/CHIP250/ASSET_GROWTH五条目的10日池；不改动成熟因子的公式来重新开始样本外积累。先确认现有池状态、固定周期、有效条目数及平台修改窗口。',
'2. 补齐资产增长10日平台验证。当前5日单因子0.76%不能当10日平台成绩；只需补齐这一关键缺口，不自动重测全部五条。',
'3. 有平台池级预览时，用同一口径与全10日备选SIZE/H03/RET40/DD120/CHIP250比较。没有官方池级接口时，等权标准化复合公式平台回测只能是池信号代理，不能冒称官方池C。',
'4. 未完成上述验证前，结论是“本地优先验证名单”，不是“已确认平台最优提交”。本次没有创建新平台因子、运行新平台回测或提交比赛池。',
'', '## 7. 范围限制与复现材料','',
'本地质量门槛排除了TURN、EVEBITDA、BM、RESVOL、SP字段/路径不一致记录；N34无可用本地信号。因此未把平台单因子成绩好但不能可靠本地合成的条目硬凑进池。首选只在本轮候选范围成立，不是穷尽全部平台因子的全局最优。',
'已有的训练/验证/近期曾参与历史研究，本轮638个池也带来多重选择偏差；将差别很小的两个结果解释为确定优势不恰当。',
'文件：aligned_base_pools.csv（29池）、all_diagnostic_pools.csv（638池）、training_pareto.csv（训练多指标前沿）、one_seat_replacements.csv（同数量替换差值）、shortlist.csv（重点候选）。源数据与计算脚本分别位于../pool-screen-20260921/、scripts/screen_competition_pool_20260921.py；本报告生成器为scripts/report_pool_horizontal_20260921.py。']
(O/'report.md').write_text('\n'.join(lines)+'\n')
(O/'decision.json').write_text(json.dumps({'primary_conditional':primary,'all_platform_sources_10d_alternative':ready,'universe_pool_count':len(d),'base_pool_count':len(base),'selection':'alignment-tier then training net excess; risk and A proxy reviewed; no gain-vs-single gate','official_score':None,'new_platform_runs':0},ensure_ascii=False,indent=2)+'\n')
assert len(base)==29 and len(d)==638
assert base.loc[base.train_net_excess_pct.idxmax(),'components']==primary
assert d.loc[d.full_net_excess_pct.idxmax(),'components']==primary
assert d.loc[d.test_net_excess_pct.idxmax(),'components']==primary
assert len(pd.DataFrame(changes))==25
print('Written',O/'report.md','; 29 base pools, 638 diagnostic pools, 25 equal-count substitutions; checks passed.')
