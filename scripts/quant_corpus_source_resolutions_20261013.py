"""Precise exclusions and traces; preserve original review and test artifacts."""
import ast,hashlib,json
from pathlib import Path
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_semantic_review_20261012 import core
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'

def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text()) if (OUT/'precise_source_resolutions.json').exists() else []
 def add(group,prefix,state,decision,anchors,keys=None):
  paths=list((q.ROOT/'quant'/group).glob(prefix+'*'))
  assert len(paths)==1,(group,prefix,paths)
  p=paths[0];text=read_text(p);lines=text.splitlines();evidence=[]
  for anchor in anchors:
   found=[dict(line=i+1,text=s.strip()) for i,s in enumerate(lines) if anchor in s]
   assert found,(str(p),anchor)
   evidence.extend(found[:5])
  rows[:]=[r for r in rows if r['path']!=str(p.relative_to(q.ROOT))]
  rows.append(dict(path=str(p.relative_to(q.ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
   resolution=state,decision=decision,evidence=evidence,related_tested_keys=keys or [],
   full_strategy_reproduced=False,mechanical_exact_function_match_is_not_full_recipe_equivalence=True))
 # Previously read active wizard pipelines: empty sort input and pass-through
 # sort means filtered symbol order, not a financial ranking factor.
 for prefix in ['28 ','32 ','34 ','35 ','44 ','56 ','57 ','60 ','61 ','62 ','63 ','70 ','75 ']:
  p=next((q.ROOT/'quant/2020年度精选策略').glob(prefix+'*'))
  tree=ast.parse(core(p));funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
  n=funcs['get_check_stocks_sort_input_dict']
  assert any(isinstance(x,ast.Assign) and isinstance(x.value,ast.Dict) and len(x.value.keys)==0 for x in ast.walk(n))
  body=ast.unparse(funcs['check_stocks_sort'])
  assert 'len(input_dict) == 0' in body and 'return security_list' in body
  add('2020年度精选策略',prefix,'no_economic_ranking_in_active_wizard',
   '实际财务/技术条件是资格筛选；input_dict为空时排序函数原样返回股票代码顺序。不能把旧质量族备注或股票代码排序当已复现经济因子。持仓/买卖约束是策略执行层，未完整回测。',
   ['def financial_statements_filter','def get_check_stocks_sort_input_dict','len(input_dict) == 0'])
 add('2022年度精选策略','88.','no_economic_ranking_in_active_wizard',
  '实际筛选netprofit_yoy>5、TTM及LYR PE0..120、MA5>MA10，排序input_dict为空；卖出是MACD12/26/26且CDL3BLACKCROWS。不能误称未冻结全部过滤函数；源码已给出，但没有经济排序因子。',
  ['inc_net_profit_year_on_year','MA_judge_duotou','input_dict = {','CDL3BLACKCROWS_judge'],['macd12_26_26_cross_margin','candle_cdl3blackcrows'])
 add('2020年度精选策略','33 ','missing_PIT_industry_selection',
  '每个行业取最大总市值股票，再按ROE取10并排goodwill/equity>=.1。缺PIT行业不能用全A最大市值替换后称原式。',
   ['get_industry_stocks','good_will','roe'])
 add('2023年度精选策略','35.','missing_PIT_industry_selection',
  '五个指定行业，每行业市值前10内取首只。不是通用动量，缺PIT行业不能伪造行业龙头。',
  ['get_industry_stocks','market_cap'])
 for group,prefix in [('2021年度精选策略','3.'),('2023年度精选策略','10.')]:
  add(group,prefix,'missing_historical_index_weights',
   '沪深300指数权重前10的集中复制，不是新的个股alpha；缺历史权重，已有SIZE结果不等价。',
   ['get_index_weights'])
 add('2021年度精选策略','9.','insufficient_10year_asof_earnings_history',
  '按当前日期-k*365天查询10个历史asof净利润，要求严格9次增长。当前实际公告历史从2018开始，最新2026也不能覆盖最早2017asof；不把10年缩成4年。',
   ['365',"label('earn')"])
 for group,prefix,formula in [('2020年度精选策略','02 ','600887/600036固定价差z120阈值1'),('2020年度精选策略','13 ','603288/600036固定价差z120阈值.82，含保证金'),('2020年度精选策略','19 ','603288/600036固定价差z120阈值1')]:
  add(group,prefix,'fixed_two_stock_pair_not_100stock_crosssection',
   formula+'；仅两只固定标的，不能在>=100只股票的截面合同中充作完整全A新因子。选配对伙伴再推广属于新方法，尚未实现。',
   ['120','600036'])
 for prefix in ['65.','69.']:
  add('2022年度精选策略',prefix,'tested_atom_with_unreproduced_index_timing',
   '实际正PB/ROE下按rank(PB)+rank(1/ROE)低分优先，与已有roe_pb_equalrank的排序原子一致。指数RSRS不同窗口及状态、行业/持仓/交易并未完整复现。',
   ["df['point']",'roe','pb_ratio'],['roe_pb_equalrank'])
 add('2022年度精选策略','74.','tested_active_atom_plus_dormant_library',
  'active BP、factors=False和sort_rank=True组合实际选高BP；FACR只是库内可选字段。DP是应付股利，不能当现金股息率。',
  ['g.factor','g.sort_rank','dividend_payable'],['book_market','fixedassets_fraction_library_low'])
 add('2022年度精选策略','8.','library_atoms_tested_model_unreproduced',
  '全文1181行：最终LightGBM特征选择、随机拆分和SVC/GBDT网格示例，作者明言具体有效策略不分享；无冻结的因果模型。新增库比率在75批测试，PIT行业缺失，原始2013数据早于本地2018暖机。',
  ['具体有效的策略','train_test_split','SVC(max_iter','GridSearchCV'],['fcff_subtract_investing_ytd_ncl','calculated_roic_ytd_library','sales_fixedassets_ytd_library'])
 add('2024年度精选策略1','66.','literal_boolean_SVR_tested_missing_industry_index',
  '查询里的五项比较是特征列而非筛选；重命名log_NC等并不把布尔变量变成净资产金额。77批按实际五布尔特征单独测试；缺行业哑变量/指数择时，仍只是原子代理。',
  ['valuation.pb_ratio > 0','indicator.ocf_to_operating_profit > 5','df.columns =','SVR(kernel'],['svr_booleanquery5_undervaluation'])
 add('2023年度精选策略','41.','market_scalar_not_crosssectional_factor',
  '成交额前5%合计/全部成交额是每天一个标量；不产生个股截面排序，可研究为池择时门控，但不能当新股票alpha。',
   ['money','n_five_pct'])
 add('聚宽2025年精选','28','microcap_scalar_gate_missing_index_status',
  '最小5%市值的一致性比例是池级日标量；结合指数MA240与120日滚动阈值及收益中位数±2%状态。缺实际指数和历史ST/listing，未用假指数替换后称原式。',
  ['0.05','240','120'])
 add('2024年度精选策略2','29.','missing_industry_xlsx_sqlite_inputs',
  '行业趋势/拥挤/景气权重模型需点时行业及外部xlsx/sqlite。历史标准化只能到当前asof，不可全回测区间zscore。',
  ['xlsx','sqlite','0.51'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 import pandas as pd
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,scope='individually reviewed source exclusions/traces, not automated corpus completion',all_corpus_complete=False))
 print('PRECISE_SOURCE_RESOLUTIONS',len(rows))

if __name__=='__main__':main()
