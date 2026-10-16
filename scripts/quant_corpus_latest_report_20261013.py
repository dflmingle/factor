"""Artifact-derived continuation report; incomplete coverage cannot rank as five years."""
import json,re
import pandas as pd
import numpy as np
import quant_corpus_local_20261012 as q
from quant_corpus_sweep_registry_20261013 import main as refresh,KNOWN_ERRORS,SEMANTIC_SUPERSEDED,EQUIVALENT_RETESTS,SUPERSEDED_KEYS
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'continuation_results_20261013'

def main():
 refresh();OUT.mkdir(exist_ok=True);rows=[];specrows=[]
 for p in sorted((q.ROOT/'research_reports/platform_alignment').glob('quant-corpus-semantic-source*-20261013/recipe_manifest.json')):
  number=int(re.search(r'source(\d+)',p.parent.name).group(1))
  if number<25:continue
  root=p.parent
  if not (root/'audit_complete.json').exists():continue
  specs=json.loads(p.read_text());meta={s['key']:s for s in specs}
  raw=pd.read_csv(root/'results.csv');tri=pd.read_csv(root/'incremental_information.csv')
  for _,r in pd.concat([raw,tri],ignore_index=True).iterrows():
   x=r.to_dict();x.update(batch=root.name,source_batch=number,output=str(root.relative_to(q.ROOT)),
    source_paths=meta[r['key']]['source_paths'],formula=meta[r['key']]['formula'],fidelity=meta[r['key']]['fidelity'],
    effective_gated=meta[r['key']].get('gated',False) or r['key']=='svr_signlog_default6_undervaluation',
    semantic_superseded=root.name in SEMANTIC_SUPERSEDED or r['key'] in SUPERSEDED_KEYS,
    equivalent_retest_of=EQUIVALENT_RETESTS.get(r['key'],''),
    sufficient_periods=r['periods']>=(114 if r['window']=='five_year' else 14))
   # Evaluator's empty-result0 is not a return observation.
   if r['periods']==0:
    for k in ['net_excess_pct','gross_excess_pct','held_daily_max_drawdown_pct','turnover_pct','rank_ic','ic','rank_icir']:x[k]=np.nan
   rows.append(x)
  specrows.extend([{**s,'batch':root.name,'source_batch':number,'semantic_superseded':root.name in SEMANTIC_SUPERSEDED or s['key'] in SUPERSEDED_KEYS} for s in specs])
 f=pd.DataFrame(rows);f.to_csv(OUT/'all_results.csv',index=False);q.dump(OUT/'all_recipes.json',specrows)
 decisions=[]
 for (batch,key),g in f.groupby(['batch','key'],sort=False):
  s=g[g.form.eq('raw')&g.window.eq('five_year')].iloc[0]
  d=dict(batch=batch,key=key,source_paths=s.source_paths,formula=s.formula,fidelity=s.fidelity,effective_gated=s.effective_gated,semantic_superseded=s.semantic_superseded)
  for form,label in [('raw','raw'),('size_reversal_rank_residual','dual'),('size_reversal_IVOL_simultaneous_residual','triple')]:
   for win,wlabel in [('five_year','five'),('recent','recent')]:
    r=g[g.form.eq(form)&g.window.eq(win)]
    if r.empty:continue
    r=r.iloc[0]
    for col,outcol in [('net_excess_pct','net'),('periods','periods'),('held_daily_max_drawdown_pct','dd'),('turnover_pct','turn')]:d[f'{label}_{wlabel}_{outcol}']=r[col]
  reasons=[]
  if s.equivalent_retest_of:reasons.append('与旧配方信号逐值一致的复测，不是新信息')
  if s.semantic_superseded:reasons.append('旧语义实现已被纠正版本替代')
  if s.periods<114:reasons.append(f'五年有效期不足：{int(s.periods)}/120')
  if d.get('triple_five_periods',0)<114:reasons.append('三风格残差五年覆盖不足，不能认证独立信息')
  if s.effective_gated:reasons.append('资格子集基准，不代表无约束全A超额')
  if not np.isfinite(s.net_excess_pct) or s.net_excess_pct<15:reasons.append('未达五年净超额15%门槛')
  if d.get('dual_recent_net',-1)<=0 or d.get('triple_recent_net',-1)<=0:reasons.append('剥离旧风格后的近期表现非正')
  if d.get('triple_five_net',-1)<=0:reasons.append('剥离市值反转低IVOL后的五年表现非正')
  d['decision']='不晋级' if reasons else '待进一步验证，不是已认证alpha'
  d['reason']='；'.join(reasons);decisions.append(d)
 decision=pd.DataFrame(decisions);decision.to_csv(OUT/'candidate_decisions.csv',index=False)
 daily=CAT.parent.parent/'platform_alignment/quant-corpus-cashdebt-incrementality-20261013'
 pool=pd.read_csv(daily/'pool_scenarios.csv')
 add=pool[pool.scenario.eq('add6')][['candidate','form','window','delta_net_excess_pct','delta_held_daily_max_drawdown_pct','delta_turnover_pct']]
 add.to_csv(OUT/'cashdebt_pool_add6_diagnostics.csv',index=False)
 full=decision[decision.raw_five_periods.ge(114)&~decision.semantic_superseded]
 columns=['key','raw_five_net','raw_recent_net','dual_five_net','dual_recent_net','triple_five_net','triple_recent_net','raw_five_dd']
 top=full.sort_values('raw_five_net',ascending=False).head(15)
 matched_rows=[]
 for num in [144,148,152,155,157,158]:
  p=q.ROOT/f'research_reports/platform_alignment/quant-corpus-semantic-source{num}-20261013/matched_size_control_deltas.csv'
  if not p.exists():continue
  m=pd.read_csv(p)
  if 'form' in m:m=m[m.form.eq('raw')]
  for _,r in m.iterrows():
   key=r.get('key', 'linear5_positiveEPS_topscore_priority' if num==148 else 'FROEC28_finalmembership_priority')
   matched_rows.append(dict(key=key,window=r.window,delta_net_pp=r.delta_net_excess_pct,
    delta_dd_pp=r.get('delta_held_daily_max_drawdown_pct',r.get('delta_dd_pct',np.nan)),
    delta_turn_pp=r.get('delta_turnover_pct',r.get('delta_turn_pct',np.nan))))
 matched=pd.DataFrame(matched_rows);matched.to_csv(OUT/'matched_size_controls.csv',index=False)
 def md(df):
  out='| '+' | '.join(map(str,df.columns))+' |\n|'+ '|'.join(['---']*len(df.columns))+'|\n'
  for _,r in df.iterrows():out+='| '+' | '.join('—' if pd.isna(v) else f'{v:.2f}' if isinstance(v,(float,np.floating)) else str(v) for v in r)+' |\n'
  return out
 progress=json.loads((CAT/'exhaustive_sweep_20261013/progress.json').read_text())
 report=f'''# 2026-10-13 持续本地复现，按实际产物汇总

任务仍在进行，尚未穷尽可执行配方，尚未认证新的独立 alpha。用户已授权连续本地研究，无需逐轮确认；平台算力消耗0，正式池未改动。

本表纳入源码批次25起已完成审计的{decision.batch.nunique()}个目录、{len(decision)}条规格记录，其中{int(decision.semantic_superseded.sum())}条旧语义实现保留但排除有效排名。这是规格记录数量，包含代理、对照、窗口变体和重复项，不能解释为同数量独立因子或新簇。全库818文件源哈希一致；直接存在原子产物的来源{progress['source_states'].get('has_tested_atoms_full_strategy_not_reproduced',0)}，不等于完整策略已回测。粗粒度执行前沿{progress['unimplemented_sources']}个，不能据此判断已经跑完；仍有{progress['source_states'].get('reviewed_family_duplicate_or_variant_needs_recipe_trace',0)}个来源需要精确关联或补测、{progress['source_states'].get('reviewed_dependency_or_applicability_blocker',0)}个来源需要复核数据障碍与可用部分；57个rzrk未解码。

各列是扣除单边0.30%成本的算术年化多头净超额百分比，DD为多头扣费日频最大回撤。dual同时剥离市值和20日反转秩，triple再剥离既有低IVOL；两者是独立信息诊断，不是平台已验证公式。

{md(top[columns])}

布尔查询SVR五年约15.92%，dual约1.32%，近期dual约−9.01%，且仍有资格/市值暴露；不能当作强新簇。正PB微盘资格等原始正收益较高的新增条目仍按市值排序，属于旧风格的资格变体；纯市值残差退化不是资格无效的证据，也不能证明新独立信息。部分原始财务模型五年正收益也未在独立信息诊断中稳定保留。原先FF3风格解释比例/低IVOL稳定组合仍是既有研究候选，没有因为增加新批次而获得进池认证。

补充共同全A支持与相同基准下的资格增益，以下为相对纯SIZE的变化（pp）。正PB优先五年仅增加约0.99pp，近期减少约1.49pp；低留存正EPS、固定线性评分资格、报告ROE资格均未同时改善两个窗口。来源140资格子集的15.16%/25.31%不能作为优于全A SIZE的证据。残差退化不用于否定资格价值，此处使用实际同支持组合对照；仍未取得当前规则的正式池ΔComb证明。

{md(matched)}

现金流/净债务及现金流/总债务日频最近其它锚点已保存，覆盖1211日、13个旧锚点，未覆盖主簇全集。原始值与来源67保存信号面板逐值核对通过。加6席与换各旧席的56行双窗口诊断全部留档；加6席五年净超额均下降。旧五席来自qualitygate3保存档案，只是同支持集探索，不是当前规则的正式池重建，不推断官方Comb或排名。

{md(add)}

质量交集70/74以及Boll事件76无有效期或仅少数有效期，结果不能称五年收益，也不能把evaluate返回的0称零收益。最新CSV把0有效期的收益/回撤/换手设为缺失。有效期少于114/120的记录明确标记覆盖不足；资格子集即使期数足够，也仍单独标记基准。

65号MACD背离的199状态项与LASTgreens分支错误，已用66号更正；89号滚动XGB分组边界及概率并列门槛，已用90号更正；原文件和旧结果保留，替代标记可审计。68号SVR原gated=False元数据，在汇总中更正为True，未修改冻结历史输出。新增财务字段按原始公告截断重放，技术数据按完整日序列截断重算；未使用全样本个股标准化。

正式窗口20210907—20260907，近期窗口20260101—最新缓存20260907；保存信号最后20260810、退出20260825。全沪深A/qfq/total_mv/20180101暖机/label1/10组/factor_valid成本口径固定。行业、指数、分钟、ETF及供应商内部字段不等价部分逐条写在fidelity内；没有独立未触碰的研究样本外。大量探索之后的正收益只作待证假设。

完整结果：[all_results.csv](all_results.csv)；逐项决策：[candidate_decisions.csv](candidate_decisions.csv)；公式和来源：[all_recipes.json](all_recipes.json)。完整覆盖及未完成队列在上级exhaustive_sweep_20261013目录。
'''
 (OUT/'report.md').write_text(report,encoding='utf-8')
 q.dump(OUT/'report_state.json',dict(status='active_unfinished',complete_audited_batches=decision.batch.nunique(),specification_rows=len(decision),certified_new_alpha=0,platform_compute=0,full_corpus_complete=False))
 print(OUT/'report.md')

if __name__=='__main__':main()
