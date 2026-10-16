"""Individually inspected framework, timing and allocation dependency decisions."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'

def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence3';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);evidence=[]
  for anchor in anchors:
   found=[dict(line=i+1,text=l.strip()) for i,l in enumerate(s.splitlines()) if anchor in l];assert found,(p,anchor);evidence.extend(found[:5])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path]
  rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=evidence,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 add('2022年度精选策略','17.','no_economic_ranking_factor_selection_framework',
  '八项已有基础因子2014—2019周频暴露、相关、IC分析；股本+换手率为文章解释结论，并无冻结组合权重或因果训练规则。历史指数成分与供应商股本/PIT数据不足，不把历史IC选择框架当新增可交易预测。',
  ["begin_date = '2014-01-01'",'valuation.capitalization','def factor_IC_analysis','st.pearsonr'],['small_size','roe','low_turn20'])
 add('2022年度精选策略','37.','no_economic_ranking_missing_vendor_Barra_attribution',
  '使用供应商十项Barra风险暴露、申万行业及SLSQP事后收益归因；45参数和x[-35:-1]行业切片硬编码。没有因果因子收益预测器，归因解释收益不等于alpha；行业及风险暴露缺，不能用自制IVOL冒称字节等价。',
  ['def get_barra_factor','get_factor_values','get_industry_exposure','x[-35:-1]','np.ones(45)',"method='SLSQP'"])
 add('2021年度精选策略','0.','no_economic_ranking_universe_filter_benchmark',
  '过滤ST/停牌/新股/科创板及API速度计时；两处同名函数不同签名覆盖，测试调用需核对实际版本。无收益预测排名，不向股票代码排序强加新簇。',
  ['def filter_st_paused_new','microseconds','g.total_count'])
 add('2020年度精选策略','37 ','no_economic_ranking_missing_wizard_stopprofit',
  '实际security_stopprofit(...,.2)是止盈调用，非标题所示自定义止损；筛选函数空壳、排序input_dict空时原顺序。供应商wizard执行函数未附，持仓成本依赖不能用20日收益替代。',
  ['security_stopprofit(context,0.2','len(input_dict) == 0','get_check_stocks_sort_input_dict','g.max_hold_stocknum = 5'])
 add('2024年度精选策略2','44.','no_economic_ranking_fixed_ETF_grid_execution',
  '固定510500、5%网格、每格2万、初始MA60±20%；网格本金/基准价随成交和分红成本调整，非截面因子。缺ETF分钟及成交账本，不以MA60因子回测替代策略。',
  ["g.ETF = ['510500.XSHG']",'g.net_range = 0.05','g.days = 60','g.base_price[etf] = order_res.price','g.pre_date_avg'])
 add('2024年度精选策略2','83.','market_scalar_missing_two_index_open_gaps',
  '399300与399303今日开盘/昨收比较，只交易510180；买入gap300>gap303 OR gap300>1，卖出两者均小且已持仓。指数开盘缺，不是普通个股gap因子的全策略复现。',
  ["g.security = '510180.XSHG'",'fudu_300 > fudu_303 or fudu_300 > 1','fudu_300 < fudu_303 and fudu_300 < 1'])
 add('2024年度精选策略1','52.','no_economic_ranking_missing_ETF_allocation',
  '实际w=1使相关矩阵变单位阵，anchored分支退化为给定逆方差锚点，均值signal不参与权重；1200价点1199收益，仅四ETF月调仓。缺ETF日线，低风险资产预算不是新股票alpha。',
  ['count=1200','a = (1/d) / (1/d).sum()','method = "anchored", w = 1','w * I @ V @ a'])
 add('聚宽2025年精选','32','no_economic_ranking_missing_ETF_covariance_allocation',
  '十ETF250价点249收益，逆方差a作为simple信号，w=.6收缩协方差求权重；shrunk_cov计算后未被使用，solve仍用cov_tilde。配置算法需真实ETF协方差，不是独立个股收益信息。',
  ['count=250','signal = a','w = 0.6','shrunk_cov =','solve(cov_tilde, I)'])
 add('聚宽2025年精选','67','missing_dividend_registration_and_historical_name',
  'PB<1、现金经营流入/扣非利润>1e5、利润同比>0后按过去1095自然日登记分红/市值高半，最后名称含爱我中华；逐字循环可重复股票，不是爱国经济因子。缺登记分红及PIT名称，不用财报dividend_payable替代已付分红。',
  ["keywords = ['爱','我','中','华']",'365*3','finance.STK_XR_XD.a_registration_date','False, 0, 0.5','LIST.append(stock)'])
 add('量化策略/量化策略/首板回调买入策略2026','07','missing_actual_limit_prices_and_intraday_asof',
  'buy_days=3由datetime.days算自然日；回调-12%到-8%且C>MA10。14:50读取end_date=current_dt日线存在收盘数据时点风险，固定主板1.1等涨停推算不等于实际PIT高限价。资格/时间不能忠实复现，已有MA10原子不足以证明完整策略。',
  ['g.buy_days = 3','g.callback_min = -0.12',"run_daily(check_signals, '14:50')",').days > g.buy_days','close_price > ma10','limit_ratio = 1.1'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
