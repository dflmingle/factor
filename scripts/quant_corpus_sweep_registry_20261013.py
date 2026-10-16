"""Reconcile every corpus file with actual recipe artifacts; never infer tested
coverage from titles, keyword families, or a reading-complete flag.
"""
import hashlib
import json
from pathlib import Path
import pandas as pd
import quant_corpus_local_20261012 as q

CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
KNOWN_ERRORS={
 'quant-corpus-semantic-source18-20261013':'ROA difference duplicated, incorrect FFScore6; corrected structure source32',
 'quant-corpus-semantic-source21-20261013':'quality_score9 substitutes negativeROE for turnover; triangle cashflow formula differs from manifest; corrected turnover source32',
 'quant-corpus-semantic-source22-20261013':'APARP wrong field names; correct earlier APARP source7, not a genuine field blocker',
 'quant-corpus-semantic-source23-20261013':'small_value_rank4 missing source positive filters and actual weights(size1,value1/3); corrected source50; not faithful source recipe',
 'quant-corpus-semantic-source24-20261013':'lowturn recipe contains unnecessary asset_turnover*0 coverage gate',
 'quant-corpus-semantic-source17-20261013':'high_open/close_low/vwap already tested in source1; duplicate specifications, not new mechanisms',
 'quant-corpus-semantic-source42-20261013':'earlier prose described low size/RD/ROE, actual source favors HIGH values; saved source42 recipe rank direction is high and source derivation must govern',
 'quant-corpus-semantic-source65-20261013':'superseded semantic diagnostic: source initializes199 stateflags and append/pop preserves199, not200; bottom second-green branch compares LASTgreens price not SECONDgreens; corrected source66 independently checked against four original pure math functions on11448 observations',
 'quant-corpus-semantic-source89-20261013':'superseded semantic diagnostic: bottom decile used9*floor(N/10), not source floor(N/10*9); finite-label removal occurred before universe slicing; probability quantile ties differed from source exact floor(N/5) slice. Corrected source90; original artifacts preserved.',
}
GATED_CORRECTIONS={
 'slater_annual_eps_peg','lynch_pit_eps_peg','slater_pb20_eps_peg',
 'crosssection_ols5_source','pb_deducted_roe_scaled_source','smallvalue4_source_weights_gates',
 'svr_signlog_default6_undervaluation',
}
SEMANTIC_SUPERSEDED={'quant-corpus-semantic-source65-20261013','quant-corpus-semantic-source89-20261013'}
EQUIVALENT_RETESTS={'value75_roa_actual_intersection':'lowpb_roa_cash_profit_source'}
SUPERSEDED_KEYS={'auction10_weak3ret_body_amount_margin':'amount cache unit is thousand yuan; literal yuan threshold applied without x1000; corrected source160'}

def review_note(directory):
 name=directory.name
 if name.startswith('quant-corpus-candle-') and not name.startswith('quant-corpus-candle-safe-'):
  return 'superseded unsafe diagnostic: constant ranked factors produced floating-point dual residual ranks; corrected candle-safe directories, original outputs retained, not additional hypotheses'
 return KNOWN_ERRORS.get(name,'')

def main():
 OUT.mkdir(exist_ok=True);source=json.loads((CAT/'source_review.json').read_text());links={};recipes=[];results=[]
 for manifest in sorted((q.ROOT/'research_reports/platform_alignment').glob('quant-corpus*/recipe_manifest.json')):
  directory=manifest.parent;meta=json.loads(manifest.read_text())
  if not isinstance(meta,list):continue
  completion=directory/'completion.json';done=json.loads(completion.read_text()) if completion.exists() else {}
  finished=any(done.get(k,False) for k in ['completed','all_candidates_completed','all_recipes_completed'])
  for r in meta:
   note=review_note(directory)
   x=dict(r);x.update(batch=directory.name,output=str(directory.relative_to(q.ROOT)),saved_results_complete=finished,
                    equivalent_retest_of=EQUIVALENT_RETESTS.get(r['key'],''),
                    implementation_review_note=note,
                    research_audit_complete=(directory/'audit_complete.json').exists(),
                    superseded_unsafe=note.startswith('superseded unsafe'),
                    superseded_semantic=directory.name in SEMANTIC_SUPERSEDED or r['key'] in SUPERSEDED_KEYS)
   if r['key'] in SUPERSEDED_KEYS:x['implementation_review_note']=SUPERSEDED_KEYS[r['key']]
   if x['key'] in GATED_CORRECTIONS:
    x['effective_gated']=True;x['coverage_interpretation_note']='qualification subset; old saved gated=False metadata corrected here without altering frozen outputs'
   else:x['effective_gated']=x.get('gated',False)
   recipes.append(x)
   for src in r.get('source_paths',[]):links.setdefault(src,[]).append(x)
  csv=directory/'results.csv'
  if csv.exists():
   frame=pd.read_csv(csv);frame['batch']=directory.name;frame['implementation_review_note']=review_note(directory)
   frame['superseded_unsafe']=review_note(directory).startswith('superseded unsafe')
   frame['superseded_semantic']=(directory.name in SEMANTIC_SUPERSEDED)|frame['key'].isin(SUPERSEDED_KEYS)
   frame['effective_gated']=frame['key'].isin(GATED_CORRECTIONS)|frame.get('gated',False)
   results.append(frame)
 sha_links={}
 for x in source:
  if x['path'] in links:sha_links.setdefault(x['sha256'],[]).extend(links[x['path']])
 resolution_path=OUT/'precise_source_resolutions.json'
 precise={r['path']:r for r in json.loads(resolution_path.read_text())} if resolution_path.exists() else {}
 rows=[]
 for x in source:
  row=dict(x);p=q.ROOT/x['path'];row['current_hash_matches_inventory']=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
  direct=links.get(x['path'],[]);alias=[] if direct else sha_links.get(x['sha256'],[])
  row['actual_recipe_links']=';'.join(f"{r['batch']}:{r['key']}" for r in direct)
  row['identical_source_recipe_links']=';'.join(f"{r['batch']}:{r['key']}" for r in alias)
  row['implementation_review_notes']=';'.join(sorted(set(r['implementation_review_note'] for r in direct if r['implementation_review_note'])))
  st=x.get('semantic_status','')
  resolution=precise.get(x['path'])
  if resolution and resolution['sha256']!=x['sha256']:raise ValueError('precise resolution hash mismatch: '+x['path'])
  row['precise_resolution']=resolution['resolution'] if resolution else ''
  row['precise_resolution_decision']=resolution['decision'] if resolution else ''
  row['precise_atom_trace_keys']=';'.join(resolution['related_tested_keys']) if resolution else ''
  if x['source_kind'] in ['directory_or_instruction_asset']:state='supporting_asset_no_factor'
  elif p.suffix=='.rzrk':state='unparsed_binary_no_source'
  elif direct:state='has_tested_atoms_full_strategy_not_reproduced'
  elif alias:state='byte_identical_source_has_tested_atoms'
  elif resolution and resolution['resolution'].startswith('tested_atom_with_'):state='precise_existing_atom_trace_strategy_layers_unreproduced'
  elif resolution and any(k in resolution['resolution'] for k in ['no_economic_ranking','missing_','insufficient_','fixed_two_stock_pair','market_scalar','microcap_scalar']):state='precise_dependency_or_applicability_resolution'
  elif any(k in st for k in ['duplicate','known_']):state='reviewed_family_duplicate_or_variant_needs_recipe_trace'
  elif any(k in st for k in ['blocked','unreproducible','missing','broken','no_factor','not_equity','not_stock','not_cross_sectional','tool_only']):state='reviewed_dependency_or_applicability_blocker'
  else:state='unimplemented_recipe_or_execution_frontier'
  row['sweep_state']=state;row['full_strategy_tested']=False;rows.append(row)
 pd.DataFrame(rows).to_csv(OUT/'all_source_coverage.csv',index=False)
 pd.DataFrame(recipes).to_csv(OUT/'all_saved_recipes.csv',index=False)
 if results:pd.concat(results,ignore_index=True).to_csv(OUT/'all_saved_results.csv',index=False)
 frontier=[r for r in rows if r['sweep_state']=='unimplemented_recipe_or_execution_frontier']
 pd.DataFrame(frontier).to_csv(OUT/'unimplemented_source_frontier.csv',index=False)
 remaining=[r for r in rows if r['sweep_state'] in ['unimplemented_recipe_or_execution_frontier','reviewed_family_duplicate_or_variant_needs_recipe_trace','reviewed_dependency_or_applicability_blocker']]
 pd.DataFrame(remaining).to_csv(OUT/'remaining_source_review_queue.csv',index=False)
 summary=dict(corpus_files=len(rows),all_corpus_hashes_unchanged=all(r['current_hash_matches_inventory'] for r in rows),
   source_states=pd.Series([r['sweep_state'] for r in rows]).value_counts().to_dict(),
   saved_specification_rows=len(recipes),unique_saved_keys=len(set(r['key'] for r in recipes)),
   complete_saved_specification_rows=sum(r['saved_results_complete'] for r in recipes),
   superseded_unsafe_saved_rows=sum(r['superseded_unsafe'] for r in recipes),
   superseded_semantic_saved_rows=sum(r['superseded_semantic'] for r in recipes),
   unique_complete_nonsuperseded_keys=len(set(r['key'] for r in recipes if r['saved_results_complete'] and not r['superseded_unsafe'] and not r['superseded_semantic'])),
   unique_complete_nonsuperseded_canonical_keys=len(set(EQUIVALENT_RETESTS.get(r['key'],r['key']) for r in recipes if r['saved_results_complete'] and not r['superseded_unsafe'] and not r['superseded_semantic'])),
   count_warning='Specification rows include controls, alternative directions, proxies and duplicate/incorrect older implementations; not independent factor clusters',
   platform_compute_this_sweep=0,user_authorization='continue local rounds without repeated confirmation; no platform or pool writes',
   full_corpus_reproduction_complete=False,unimplemented_sources=len(frontier),
   source_coverage_warning='A tested atom does not establish reproduction of a complete strategy or every recipe inside it',
   known_implementation_errors=KNOWN_ERRORS)
 q.dump(OUT/'progress.json',summary)
 q.dump(OUT/'research_state.json',dict(status='active',objective='exhaust corpus runnable factor recipes and validate useful independent information',
   pending='remaining_source_review_queue.csv',remaining_source_reviews=len(remaining),latest_results='all_saved_results.csv',platform_compute_spent=0,
   completion_criterion='all independent runnable source recipes resolved; genuine survivor subjected to incrementality and pool checks; inability to find alpha is recorded honestly'))
 print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
 status=f'''# quant 策略因子研究状态

用户已授权连续多轮本地提取、复现与筛选，无需逐轮再确认。任务仍在进行，尚未穷尽所有可执行配方，也尚未认证新的独立 alpha 簇。

以下数字由实际产物生成，旧版“104/157 项已完成”和“所有策略已复现”的表述撤回。

| 内容 | 当前证据 |
|---|---|
| 文件清单 | {summary['corpus_files']} 个，源文件哈希全部一致：{summary['all_corpus_hashes_unchanged']} |
| 保存的规格行 | {summary['saved_specification_rows']}；包括对照、重复配方、代理和旧实现错误 |
| 已完成且未被不安全实现替代的唯一 key | {summary['unique_complete_nonsuperseded_keys']}；不是独立因子或簇数量 |
| 有直接本地原子产物的来源 | {summary['source_states'].get('has_tested_atoms_full_strategy_not_reproduced',0)}；不等于完整策略复现 |
| 尚无本地配方的执行前沿 | {summary['unimplemented_sources']} 个来源 |
| 需精确配方关联的重复/变体 | {summary['source_states'].get('reviewed_family_duplicate_or_variant_needs_recipe_trace',0)} 个来源 |
| 数据/适用性障碍 | {summary['source_states'].get('reviewed_dependency_or_applicability_blocker',0)} 个；障碍记录不是回测失败 |
| .rzrk 专有二进制 | 57 个未解码、未阅读、未复现 |
| 本次持续研究平台算力 | 0；全部本地 |

正式近五年与近期窗口分别保存。股票池、复权、市值、标签、成本沿用仓库对齐口径；ETF、缺字段和技术指标适配明确标为 proxy。近期正收益不代替五年结论。

已剔除 K 线稀疏事件/并列排名造成的假阳性。旧双残差在常数面板上产生浮点排名的缺陷已定位，6 项旧 K 线产物被安全版本替代并保留历史。源码35/54/55的财务交集少于100只时结果为无有效期，不能写作零收益。

明细：[覆盖台账](exhaustive_sweep_20261013/all_source_coverage.csv)、[全部保存规格](exhaustive_sweep_20261013/all_saved_recipes.csv)、[双窗口结果](exhaustive_sweep_20261013/all_saved_results.csv)、[未完成队列](exhaustive_sweep_20261013/remaining_source_review_queue.csv)、[进度 JSON](exhaustive_sweep_20261013/progress.json)。

最近三项相关簇目前按已保存信号日计算；幸存者还须补完整日频相关、稳健性和池级增量验证，才能讨论纳入。当前不存在新簇已获入池认证的结论。
'''
 (CAT/'TASK_STATUS.md').write_text(status,encoding='utf-8')

if __name__=='__main__':main()
