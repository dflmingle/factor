"""Precise Chan applicability and wizard call-path exclusions, with AST evidence."""
import ast,hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_semantic_review_20261012 import core
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence9';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None,fnames=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(p,a);ev.extend(found[:4])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  funcs=[]
  if fnames:
   tree=ast.parse(core(p));fs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
   for name in fnames:
    n=fs[name];funcs.append(dict(name=name,ast_sha256=hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest(),code=ast.unparse(n)))
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),reviewed_functions=funcs))
 add('2021年度精选策略','16.','no_economic_ranking_Chan_repainting_tool',
 '全部1887行分块完整复核：仅300058最近1000日笔/线段工具和画图，无交易/排序/因子方向。standardize合并及删除包含K线；3根分型把中心历史日标记，首尾强制逆向；defineBi同向极值删除/回溯、defineXD六/八笔确认，pop_gap和最终猜末段会取消过去xd_tb并替换历史极值。因此整窗口曲线不能回填当历史可交易值；可开发逐asof前缀重算且仅取当时最后状态的新假设，但不是原策略。trend_type int写±.5截断风险亦保留。未执行源码、未捏造分型方向alpha或报完整回测。',
 ['[float, float, int, int]','self.kDataFrame_standardized[-1][tb] = TopBotType.reverse(last_tb).value','working_df[previous_gap_loc][xd_tb] = TopBotType.noTopBot.value','We could make an assumption based on assumption','stock_df_fenduan = kc.getFenDuan()'])
 decisions={
 '24 ':'净利润同比>10与营业利润率>10、IPO100是资格，未排序；没有技术条件。',
 '80 ':'PE5.5..11.5/ROE>5/ROA>.5/PB.7..5.4是资格，365交易日刷新，未排序。',
 '84 ':'营收同比>5/利润同比>8/净利率>4/流通市值>2及high>12为资格；high12绝对价格不是12日新高。',
 '87 ':'市值>25/ROE>20/营业利润率>4，全部为资格，不是高质量排序。',
 '88 ':'净利同比>18/PE>15/市值>100/ROE>4，高PE大盘方向，非低估值小盘。',
 '94 ':'PB3..10、PE_LYR10..20为资格，PB不是低于3。',
 '99 ':'只有600030单标的、MV>0/PB<1.5，n_day_chg_dayu(5,.5)只是外部卖出函数，无法构成100股票排序。'}
 for pre,decision in decisions.items():
  p=next((q.ROOT/'quant/2020年度精选策略').glob(pre+'*'));fs={n.name:n for n in ast.parse(core(p)).body if isinstance(n,ast.FunctionDef)}
  n=fs['get_check_stocks_sort_input_dict'];assert any(isinstance(a,ast.Assign) and isinstance(a.value,ast.Dict) and not a.value.keys for a in ast.walk(n))
  assert 'len(input_dict) == 0' in ast.unparse(fs['check_stocks_sort'])
  add('2020年度精选策略',pre,'no_economic_ranking_active_wizard_exact_callpath',
   decision+' 已逐函数核对财务、技术、形态、situations、buy/sell及排序空input_dict->原代码序；没有凭既有质量族称原排序已测。PIT指数/行业/ST/持仓及外部wizard执行未复现。',
   ['def get_check_stocks_sort_input_dict','len(input_dict) == 0'],fnames=['financial_statements_filter','situation_filter','technical_indicators_filter','pattern_recognition_filter','get_check_stocks_sort_input_dict','check_stocks_sort','buy','sell'])
 add('2020年度精选策略','58 ','no_economic_ranking_missing_PIT_bank_and_external_MACD_exit',
 '实际technical_indicators_filter原样return，buy没有MACD金叉条件，与标题/旧摘要不符；仅HS300银行PE0..30的资格列表按原代码顺序，sell MACD_judge_sicha12/26/9。缺点时银行指数及kuanke.wizard外部金死叉调用语义，不能把退出技术函数当独立入场排序。20%成本风控属于持仓状态，不发明新的买入金叉。',
   ['def get_check_stocks_sort_input_dict','MACD_judge_sicha(security, 12, 26, 9)'],fnames=['financial_statements_filter','technical_indicators_filter','get_check_stocks_sort_input_dict','buy','sell'])
 for pre,description in [('26 ','净利同比>20和MA5/10筛选，circulating_market_cap desc权重1，最终总分desc'),('47 ','流通市值<100/营业利润率>20/IPO20..300，利润增长与ROE desc各50最终总分desc'),('53 ','无财务资格，market_cap asc权重50最终总分desc')]:
  add('2020年度精选策略',pre,'missing_external_wizard_sort_score_semantics',
   description+'；get_sort_dataframe只从kuanke.wizard导入，整个quant/scripts/vendor无定义。字段asc/desc与score输出的双重方向无法凭注释确定；不冒称大小盘方向或rank等权已是原式，待外部实现/保存分值验证。源码活跃调用/权重/过滤完整核对，并不称全部策略已测。',
   ['from kuanke.wizard import *','get_sort_dataframe(security_list, i, input_dict[i])'],fnames=['financial_statements_filter','technical_indicators_filter','get_check_stocks_sort_input_dict','check_stocks_sort'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
