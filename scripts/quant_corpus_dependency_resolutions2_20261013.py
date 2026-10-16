"""Individually reviewed unavailable data and scalar/asset-allocation recipes.
No keyword-only completion and no deletion of previous evidence.
"""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'

def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text())
 evidenceout=OUT/'dependency_source_evidence2';evidenceout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  paths=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(paths)==1,(group,prefix)
  p=paths[0];s=read_text(p);evidence=[]
  for anchor in anchors:
   found=[dict(line=i+1,text=l.strip()) for i,l in enumerate(s.splitlines()) if anchor in l]
   assert found,(p,anchor);evidence.extend(found[:5])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest()
  (evidenceout/(sha+'.source.txt')).write_text(s)
  rows[:]=[r for r in rows if r['path']!=path]
  rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=evidence,
   related_tested_keys=keys or [],full_strategy_reproduced=False,
   mechanical_exact_function_match_is_not_full_recipe_equivalence=True,
   decoded_evidence=str((evidenceout/(sha+'.source.txt')).relative_to(q.ROOT))))
 add('2021年度精选策略','49.','missing_northbound_active_buy_sell_history',
  '实际nday=2是两个自然日跨度内交易日，而非固定2交易日；STK_EL_TOP_ACTIVATE买卖额按股累加、排310003/4，再除1e8与流通市值。缓存没有北向买卖表，不能用总成交额替代。',
  ['g.nday=2','STK_EL_TOP_ACTIVATE','df.buy - df.sell','circulating_market_cap'])
 add('2021年度精选策略','62.','missing_northbound_market_scalar',
  '实际EMA6-EMA71除STD71北向净流，开仓阈值-.499低于平仓-.160；if先判开仓，区间分支不是常规迟滞。每天一个标量且只交易510300，缺STK_ML_QUOTA；不是股票截面排序。',
  ['STK_ML_QUOTA',"'long_period': 71","'short_period': 6",'if north_factor.iloc[-1] >', 'elif north_factor.iloc[-1] <'])
 add('2023年度精选策略','20.','missing_northbound_holdings_and_quota',
  '前三交易日沪深净流<-10清仓；前日北向持股share_ratio降序15只是水平排序，非股数变化。两项原始表均缺；不要借rank(turnover)或BM冒充北向因子。',
  ['STK_ML_QUOTA','range(0, 3)','STK_HK_HOLD_INFO',"sort_values(by='share_ratio',ascending=False)"])
 add('2023年度精选策略','74.','missing_northbound_ownership_delta',
  '北向占比>3的前日记录与上次缓存记录相减，±.3个百分点交易，RSI14区间40..80；当前缓存无真实持股占比。RSI只是辅助门槛，不能把该策略结果归给RSI。',
  ['STK_HK_HOLD_INFO','trade_limit=0.3,ratio=3','change = bx_dict','talib.RSI'])
 add('2023年度精选策略','52.','missing_shareholder_counts_and_top10_PIT',
  '按发布窗口挑股东户数>10000的减少比例前100，以及非自然人前十流通股东占比增长前100并集；关键两个公告表均缺。没有total_share等价替代。最终order_by(PE<15,ROA.desc)是排序表达式，非PE筛选；g.shareholder_table跨轮未清空也会积累。',
  ['STK_HOLDER_NUM','STK_SHAREHOLDER_FLOATING_TOP10','a_share_holders>10000',"shareholder_class!='自然人'",'valuation.pe_ratio < 15'])
 add('2023年度精选策略','53.','missing_fund_portfolio_and_indexweights',
  '2020Q4公告区间基金持仓金额占比减HS300历史权重；同期价格和持仓统计是描述性研究，区间内公告不能回填到区间起点，缺两个点时数据源。',
  ['FUND_PORTFOLIO_STOCK','pub_date > dt_start','get_index_weights','fweight[s] - index_weight.weight[s]'])
 add('2024年度精选策略1','95.','missing_fund_portfolio_and_indexweights',
  '固定2023Q1报告期403001持仓金额占比减399311指数权重，不是基金自身收益动量；原文按period_end未连接pub_date，不能历史回填。缺报告持仓和PIT权重。',
  ['FUND_PORTFOLIO_STOCK.period_end','reportId = 403001','get_index_weights','fweight[s] - index_weight.weight[s]'])
 add('2023年度精选策略','30.','missing_fund_portfolio_indexweights_timing',
  '180自然日公告窗口基金持仓金额汇总减当前指数权重；排序语句fdelta.sort(delta)在Series不兼容，未把叙述标题等同实际可执行排序。缺基金/指数权重及指数OHLC，原RSRS与持仓不能完成。',
  ['FUND_PORTFOLIO_STOCK','datetime.timedelta(180)','get_index_weights',"fdelta.sort('delta'"])
 add('2023年度精选策略','58.','missing_northbound_quota_holding_strategy',
  'Boll来自北向日额度减余额而非真实逐股成交量；股票排序share_ratio并排前三、取[3:max_stock_count]，还有指数RSRS及波动分位。没有北向表，不能用合成全A资金流替换后称原式。',
  ['STK_ML_QUOTA',"money_df['quota_daily'] - money_df['quota_daily_balance']",'STK_HK_HOLD_INFO',"ascending=False)[3:g.max_stock_count]"])
 add('2020年度精选策略','65 ','missing_index_PE_fund_allocation_calibration',
  '八基金分别按指数PE固定min/max区间配置8子账户；各min/max如14.10/44.42未给校准日期。缺历史指数成分和PE，不把这些常数当无偏五年因子或股票alpha。',
  ["'hs300':['000300.XSHG','510300.XSHG'",'14.10,44.42','def PeRatio'])
 add('2020年度精选策略','72 ','missing_index_PE_history_fund_allocation',
  '160706基金定投按从指数成立至asof的月末PE分位，.4/.75/.8控制投资额与清仓；仅市场单值及固定基金，没有股票排序。缺历史成分/PE和基金申赎。',
  ["g.buy_index = '160706.XSHE'",'pd.date_range(start,end', 'df_pe.quantile', 'g.pe_now >= 0.8'])
 add('2021年度精选策略','6.','no_economic_ranking_static_eight_funds',
  '八只固定基金目标总资产/8，偏离>max(.1position,100股成本)再平衡。没有预测或截面经济排序，缺ETF行情和状态；不能把8基金分散收益列为新因子。',
  ['g.funds = [','total_value / len(g.funds)','abs(delta) > max(0.1*position'])
 add('2021年度精选策略','84.','no_economic_ranking_fixed_ETF_grid',
  '单只512900，固定.9..1.5六档的.1价格格，每次实际现金变动后平移买卖阈值；持仓路径与单ETF执行，不提供可推广股票排名。',
  ["g.security = '512900.XSHG'",'g.initial_buy','g.initial_sell','g.unitprice'])
 add('2021年度精选策略','85.','missing_openfund_NAV_redemption_timing',
  '110011与000217场外基金切换；60条累计净值的平均被变量名MA22误导，低于均值3%赎回，黄金7日后返回；申赎3日延迟，缺净值/确认账本。不用股票MA60假称复现基金策略。',
  ["get_extras('acc_net_value'",'MA22=np.array(df).mean()','set_redeem_latency(3','g.day>=7'])
 add('聚宽2025年精选','90','no_economic_ranking_fixed_defensive_allocation',
  '红利8%、纳指8%、黄金14%、国债70%固定目标权重偏差再平衡；缺ETF行情，且完全没有个股收益预测排名。',
  ["g.weights = {'510880.XSHG':0.08",'"511010.XSHG":0.7','def trade'])
 add('2024年度精选策略2','52.','market_scalar_missing_industry_breadth',
  '源码3种总体汇总：行业MA20及格率求和、行业均值、全股票及格比例，图形展示且固定enddate行业回填历史。没有个股排序；PIT行业缺。未来可做池级门控，非新股票因子。',
  ['df_close.rolling(20).mean()','get_industry_stocks(idx, date=end_date)',"df_3['总体']"])
 add('2021年度精选策略','45.','market_scalar_missing_industry_breadth',
  '逐日查询000902成分和行业、BIAS20>0比例热力图；index_all=round(fraction)*100会把比例提前四舍五入，实际接近0/100二值。无个股经济排序，缺PIT成分和行业。',
  ['get_index_stocks(index_,date=day)','BIAS(index_stocks_list', 'round((len(stock_df[stock_df["bias"]>0])/len(stock_df))*100)'])
 add('2021年度精选策略','61.','market_scalar_missing_index_membership_floatcap',
  '000300内100价点=99日ROC正部分按circulating_market_cap加权求和，MA90再MA30择时，只交易510300；原作者全样本优化。不是每日每股因子，缺PIT成分及floatcap合同。',
  ['g.N = 100','g.N1 = 90','g.N2 = 30','roc_ser[roc_ser>0] * weights','g.target ='])
 add('2022年度精选策略','59.','missing_index_relative_return_execution',
  '最小50股票，126价点=125日相对上证跌幅<-0.5abs(indexReturn)，权重为超跌距离除indexReturn后封顶.3。指数回报为零存在除零；缺实际指数与分钟，50股不足100截面门槛。去掉指数阈值后的排名是普通125日反转，不能假称新独立簇。',
  ['g.small_cap_num = 50','g.win_length = 126','g.rel_return = -0.5','rel_return[stock]<abs(index_return)','index_return) )'])
 add('2023年度精选策略','21.','missing_vendor_fiveyear_sales_growth',
  '实际高sales_growth前10%后正EPS最小流通市值5；sales_growth供应商五年回归定义尚未核实，不能用最新营收同比冒充；本地原子只能覆盖规模，不代表成长约束已复现。',
  ["'sales_growth', False, 0, 0.1","df['eps']>0",'circulating_market_cap.asc()'],['small_size'])
 add('2024年度精选策略2','74.','missing_vendor_MAC_and_salesgrowth',
  '高sales_growth前10%、小流通市值30且EPS正，再4*(MAC120-1)/6+(MAC20-1)降序持10；MAC不能直接改RET120/20或日均线比，原字段定义未证实。',
  ['sales_growth','MAC120','MAC20','4*'])
 add('聚宽2025年精选','31','market_scalar_coherence_gate_not_newrank',
  '最小20的日收益做单位L2范数标准化，var<.02且mean>0是当日一个标量；正持仓盈利之和0..0.4为持仓账本状态。股票排名仍是ROE>.15、ROA>.10和价格<10内小市值，不是get_peg函数名所暗示的PEG。未完成实际指数/PIT/分钟/账本，现有规模原子有覆盖。',
  ['np.linalg.norm(A1)','variance<0.02 and mean>0','indicator.roe > 0.15','indicator.roa > 0.10','valuation.market_cap.asc()'],['small_size'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,scope='individual source evidence, unavailable field is not tested failure; original strategy untested',all_corpus_complete=False))
 print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
