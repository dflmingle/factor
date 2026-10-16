"""Precise resolutions after complete readings; never count them as backtests."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence7';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if a in l];assert found,(p,a);ev.extend(found[:4])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 add('2021年度精选策略','20.','missing_actual_limitchain_index_and_intraday',
 '10日最高连板>2且上证3日原价OLS斜率round2>0，上午只买1只，14:51未涨停卖出。源码筛限价行后按原dataframe次序扫描，若未按code/time排序会破坏连板；停牌每条增量1-paused。指数斜率是全市场标量，不是个股alpha。缺真实涨停/停牌/指数/分钟，不拿收益阈值造限价或个股OLS冒称原策略。',
 ['fit_linear(3) > 0','review_days = 10','row.code != stock','ups[-1] + 1 - row.paused'])
 add('2021年度精选策略','36.','no_economic_ranking_marketbottom_dashboard',
 '全文件是底部探索和绘图，无买卖/排序规则。低于2元原价占比、PB<1占比、M2/中位市值、两指数成交额/扩展历史最高、每交易股额、个股原价/过去扩展峰值取中位、新IPO原价发行价等均为市场标量；当前股票池回填历史且M2发布时间猜中旬，不能认证PIT。f4pass/行业财务段注释，未发明择时阈值或把rawclose混入正式qfqalpha。',
 ["df.fillna(10,inplace=True)","valuation.pb_ratio<1","max_money.append(dfx['total_m'].max())",'def f7(count=3000)'])
 add('2024年度精选策略1','93.','missing_sector_index_external_GSISI_market_scalar',
 'GSISI为行业pct_change5收益与TA-LibBETA(这些收益,HS300收益,window)的截面Spearman，市场单一择时标量。BETA内部再对输入求变化，不能替换成普通收益cov/var；31申万价格/HS300/外部backtestengine缺失。全样本200次进化搜索后硬编码window35/pct15；全样本std图带只诊断。未把个股beta扩展冒称原行业择时回测。',
 ['from talib import BETA','lambda x: BETA(x, index_pct, window)','sw_pct.corrwith(beta_roll5',"best_params_window = {'window': 35, 'pct_window': 15}"])
 add('2024年度精选策略1','84.','missing_actual_limit_concept_research_outcome_panel',
 '2022Jan至March现有股票池回填事件面板、20日连板、概念拥挤及次日开盘溢价；open_valid1=shift(-1)是未来结果指标而非已经执行的因子。若同日将其3日均溢价交易会泄漏，原文件无完整交易回测。缺限价/PIT概念/ST/IPO，不把未来结果当输入，不用价格阈值编造连板。',
 ["start_date = '2022-01-01'","shift(-1)","rolling(20)","get_concept(security, date=date)"])
 add('2024年度精选策略2','13.','missing_actual_limitcount_research_outcomes',
 'wd_count10计算窗口内涨停次数而非连续涨停；keep_days3未来开高低收收益统计，emo_cycle3定义未执行完整择时。低流通市值为既有排序；缺实际high_limit和low_limit，源码无完整emu策略调用，不拿10%/20%涨幅造真实限价，亦不拿未来收益面板当alpha。',
 ['wd_count = 10','keep_days = 3','df_sub[df_sub.close==df_sub.limit].close.count()'],['small_size'])
 add('聚宽2025年精选','51','tested_atom_with_PIT_industry_switch_and_original_index_missing',
 '完整复核：21条价点最后C>MA20的行业比例round整数，行业最高1不在银行/有色/煤炭/钢铁时，002股票低市值且ROE>.15/ROA>.10；否则PB<1/经营现金流入>1e6/扣非利润>1e6/ROA>.15/净利同比>0按ROA最高持1。后者与source56相同财务资格和排序，单腿已有产物；原行业switch及真实1/5股持仓不复现，不能复制当前行业。',
 ['df_ratio = ((df_bias.groupby','indicator.roa > 0.15','indicator.adjusted_profit > 1e6','indicator.inc_net_profit_year_on_year > 0'],['lowpb_roa_cash_profit_source','framework9_small_literal_quality'])
 add('量化策略/量化策略/ETF轮动策略2026','04多标的版ETF策略-重构优化版-25年70','tested_atom_with_ETF_rank_retention_execution_unreproduced',
 '20条19间隔涨幅5..20%且MA5>MA20的排序原子与109已测；源码前3买、连续2日掉出前8卖、涨幅>20卖，买名单没有排已有持仓。重构主要交易/排名缓冲，不产生新的数学alpha，缺ETF状态和真实两日retention组合，不称完整策略回测。',
  ['g.etf_num = 3','g.rank_num = 8',"df['inc'] > g.min_inc"],['etf58_exact19_band5_20_ma5_20'])
 add('量化策略/量化策略/实盘2026/Ptrade','pt版01小市值精细风控策略','tested_atom_with_PTrade_size_trade_state_unreproduced',
 '399101流通市值最小15筛交易状态再取5，仅4月跳过所有交易（注释1/4不符），涨停不卖；实盘剩余现金*.1为每次目标总额，回测总资产等权，路径不同。唯一alpha低流通市值既有，总市值小盘原子只proxy；不能把四月暂停视为清仓，不冒称实盘风控已回测。',
 ["df.sort_values('float_value', ascending=True)",'if current_month ==4','context.portfolio.cash * g.position_pct'],['small_size'])
 add('量化策略/量化策略/小市值策略2026','实01','tested_atom_with_size_roundlot_execution_unreproduced',
 '399101流通市值最小15筛ST/停牌取5，周一等权、100股整手买卖，日志比较上次持仓。标题精细风控但无新的价格/止损公式，唯一小盘排序已测为totalMV代理；流通值/指数/订单状态与整手路径未复现，不把报告收益当因子alpha。',
 ['valuation.circulating_market_cap.asc()','g.buy_stock_count * 3','int(target_value / current_price / 100) * 100'],['small_size'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
