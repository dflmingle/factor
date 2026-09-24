"""Summarize saved pool proxies without calling PandaAI."""
from pathlib import Path
import json
import pandas as pd
import platform_alignment_rules as rules
P=Path('research_reports/platform_alignment/pool-screen-20260921')
d=pd.read_csv(P/'all_subsets.csv').set_index('bitmask',drop=False)
c=pd.read_csv(P/'candidates.csv'); keys=c.key.tolist()
pools=pd.read_csv(P/'pools.csv')
winners=pools[pools.full_vs_best_single_pp>0].copy()
winners.to_csv(P/'positive_gain_pools.csv',index=False)
# Windows are separately exportable; the recent diagnostic is not part of selection ranking.
for w in ('full','recent'):
 cols=['components','factor_count']+[k for k in pools if k.startswith(w+'_')]
 pools[cols].to_csv(P/(w+'_window.csv'),index=False)
abl=[]
for _,r in winners.iterrows():
 for k in r.components.split('+'):
  parent=d.loc[int(r.bitmask)^(1<<keys.index(k))]
  abl.append({'pool':r.components,'removed':k,'remaining':parent.components,**{w+'_addition_pp':r[w+'_net_excess_pct']-parent[w+'_net_excess_pct'] for w in ('train','test','full','recent')}})
pd.DataFrame(abl).to_csv(P/'positive_pool_member_contributions.csv',index=False)
# Store the new hard failure separately from historical aggregate statistics.
reg=Path('research_reports/platform_alignment/factor_alignment_failure_registry.json')
r=json.loads(reg.read_text()); supplements=r.setdefault('supplemental_diagnostics',[])
for _,v in c[c.key.str.startswith('C') & (c.net_gap_pp.abs()>5)].iterrows():
 identity='pool-screen-20260921:'+v['name']
 if any(x.get('id')==identity for x in supplements):continue
 platform=pd.read_csv('cluster-blends-20260921-candidates.report.csv').set_index('name').loc[v['name']]
 local=d.loc[1<<keys.index(v.key)]
 supplements.append({'id':identity,'rule_version':rules.ALIGNMENT_RULE_VERSION,'formula':Path('cluster-blends-20260921-candidates.txt').read_text().splitlines()[int(v.key[-2:])-1].split(' ~ ')[1], 'fields':['CLOSE','VOLUME','OPEN','GR_TOTAL_ASSET_LYR'],'operators':['RANK','RETURNS','SUM','arithmetic'],'platform_net_excess_pct':v.platform_net,'local_net_excess_pct':v.local_net,'net_delta_pp':v.net_gap_pp,'gross_delta_pp':local.full_gross_excess_pct-float(platform.long_excess_pct),'turnover_delta_pp':local.full_turnover_pct-float(platform.turnover_pct),'classification':'provisional_net_alignment_failure','attribution':'Unresolved formula-level return-path/turnover difference; constituent fields have passing evidence; do not globally block them. Top20 and period-level audit pending.','source':str(P/'candidates.csv')})
reg.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
lines=['# 比赛池筛选（2026-09-21）','','## 范围与边界','',
'本次重新计算7个已对齐基础代表和3个新复合因子的1023个非空子集，其中638个满足至少5个因子。没有运行平台回测或提交比赛池。',
'每因子1%–99%缩尾、方向统一、Z-score、等权合成；10日调仓，10组，单边0.30%成本。收益/换手沿用当前本地对齐规则，基准为factor_valid。',
'正式窗口20210907–20260907，训练截至20240906；近期从20260101开始。行情缓存截至20260907，沿用保存平台公共调仓日，最后有效信号为20260810；不冒充更新至今天。近期与正式结果独立输出。',
'A使用保存的平台RankIC、ICIR、方向对应IC胜率计算rawA，未确认Decay；DD60和资产增长平台源周期为5日，因此含它们的A仅为源周期混合诊断。B无正式生效后记录，不能计算；C缺平台月度日账本与中证全指基准，不能计算官方NC或总积分。本表不以净超额代替官方总分。',
'新C01/C02/C03仅为公式级待审计代理，未因组件对齐而自动认定其对齐。C01净超额差超过5pp，已加入失败登记；C02/C03仍缺Top20等完整质量检查。TURN/EVEBITDA/BM/RESVOL/SP因原字段或路径问题未进入本地搜索；N34因缺有效本地信号未纳入。范围不是全平台所有因子的最优解。',
'本次有8个池五年超过自身最强组件，5个同时在验证段超过自身最强组件。近期均为负，单独展示，不以此否认历史增益。',
'', '## 有增益的全部池','', '| 池 | 五年净超额 | 比自身最强组件增加pp | 验证净超额 | 验证增量pp | 近期净超额 |', '|---|---:|---:|---:|---:|---:|']
for _,v in winners.sort_values('full_vs_best_single_pp',ascending=False).iterrows():
 lines.append(f'| {v.components} | {v.full_net_excess_pct:.2f}% | {v.full_vs_best_single_pp:+.2f} | {v.test_net_excess_pct:.2f}% | {v.test_vs_best_single_pp:+.2f} | {v.recent_net_excess_pct:.2f}% |')
lines += ['', '## 筛选意见','',
'1. 现有基础对齐证据最充分的有增益池：RET40+DD120+CHIP250+DD60+ASSET_GROWTH（5个）；五年4.48%，比最强组件2.63%增加1.84pp，验证5.24%，验证增量2.81pp。它是历史增益候选，不是官方分数最优池；DD60/增长仍需10日平台复测。',
'2. 若优先恰好5个且含新复合因子，关注RET40+DD120+CHIP250+ASSET_GROWTH+C03：五年5.29%，比最强组件4.02%增加1.26pp，验证增量0.73pp。但C03待完整对齐，且存在底层信号重复，只作为下一步平台池验证候选。',
'3. RET40+CHIP250+ASSET_GROWTH+C01+C02的五年6.13%、验证6.74%，全期删去任何成员均下降至少0.10pp；但相对最强组件仅增加0.16pp，含C01硬对齐失败且组件高度重叠，不推荐据此正式入池。',
'4. 不推荐为了满足5个而把市值/H03与其他因子硬凑：本轮含SIZE或H03的五因子及以上池均未超过自身最强单因子。',
'5. 没有池在训练、验证、全期三个窗口都满足“每个成员加入均提升净超额”；后者是额外严格诊断，不是用户要求或比赛硬门槛。',
'', '## A历史代理与候选质量','', '| 代号 | 平台源周期 | 平台净超额 | 本地净超额 | 差pp | 平台rawA |', '|---|---:|---:|---:|---:|---:|']
for _,v in c.iterrows():lines.append(f'| {v.key} | {v.source_cycle} | {v.platform_net:.2f}% | {v.local_net:.2f}% | {v.net_gap_pp:+.2f} | {v.platform_A_raw:.5f} |')
lines += ['', 'C01/02/03分别对应F-C260921-01/02/03。RET40=B03反转，DD120=B04长回撤，CHIP250=B05筹码，DD60=B09中回撤，ASSET_GROWTH=B10资产增长。', '', '完整明细见pools.csv；正增益池见positive_gain_pools.csv；逐成员加入增益见positive_pool_member_contributions.csv；五年与近期分别见full_window.csv、recent_window.csv。']
(P/'report.md').write_text('\n'.join(lines)+'\n')
print('report written; positive pools',len(winners),'validation-positive',sum(winners.test_vs_best_single_pp>0))
