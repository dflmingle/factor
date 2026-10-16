"""Source-by-source resolutions after batches153--155; no corpus execution."""
import ast,hashlib,json
from collections import defaultdict
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_dependency_resolutions10_20261013 import StripDoc
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012';OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence17';eout.mkdir(exist_ok=True)
 def find(folder,pat):
  paths=list((q.ROOT/folder).glob(pat));assert len(paths)==1,(folder,pat,paths)
  return str(paths[0].relative_to(q.ROOT))
 def save(path,state,decision,anchors=(),keys=(),extra=None):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 save(find('quant/2024年度精选策略1','26.*'),'missing_registered_cashdividend_and_conditional_price_quantile',
  '全386行：登记日365天现金分红/totalMV最高25%之后-3<PEG<3，再按totalMV小并严格price<资格池价格floor(.75N)；不是固定9元、10元，也不是正PEG。月初20仓，上市180天、分钟限价缺失。现金分红缺数据，不能拿应付股利或现金流代替；单独PEG/价格为旧风格，只能显式声明删去关键股息后的新部分，未称原完整信号已测。',
  ['get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)','price_list[int(0.75*len(df.T))]'])
 save(find('quant/2024年度精选策略1','36.*'),'missing_registered_dividends_negativePEG_PBupper_and_holdings',
  '全285行：登记日365天现金股息top25%后PEG<0、PB<3（没有PB>0），totalMV升序，未持有股票分钟price<10。04-01..04-30空仓实际活动；每月5仓，刚卖出黑名单及涨停保留。不能用普通低正PEG或正PB代替；分红/分钟数据缺失，不把删去股息门的结果称原策略。',
  ['valuation.pb_ratio < 3',"today_is_between(context, '04-01', '04-30')"])
 save(find('quant/2024年度精选策略2','14.*'),'tested_atom_with_positive_multiple_logweights_and_distinct_PB_gate',
  '全336行：weights[5,5,8,4,10]恰为source2[1,1,1.6,.8,2]的5倍，排序原子映射145，不是source32[2,1,1,4,4]。源资格PB.5..3.5、circMV.01..1000、最小100、IPO300、RET1<.087，minute1200V与当前报价缺等价。rankBUY9/SELL10、MA10±.003、bear30%现金、5天冷却、浮亏6.5%、账户DD30%均是未复现持仓路径；coldinitialize缺部分after_code_changed全局变量，不自动修好后称原策略。',
  ['g.weights = [5,5,8,4,10]','g.pbmin = 0.5','g.pbmax = 3.5'],['lowlog2_sizefree_weights1682','lowlog2_totalmv_weights1682_proxy'])
 save(find('quant/2024年度精选策略2','50.*'),'tested_atom_with_literal_m07_RSRSslope8_and_bias_joint',
  '全237行：RSRS18/600zR2，8点slope<0且rs>0优先SELL，否则严格rs>-.7 BUY；153二值和bias90/20联合已测。单独bias90/20前收盘数学为112已测。初始600+8序列不同明确rollingseedproxy，无Motion19/4.8条件；13:00 60minuteMA20缺失、checktime2未调度，get_rank返回[code,score]错误被订单当迭代；-90%stop打印未定义value。',
  ['if(rsrs_slope< 0 and rsrs_score >0):','g.score_threshold = 0.7'],['source50_rsrs_slope8_guard_m07','source50_bias90_joint_rsrs_slope8_m07','bias90_linear20_first_priorclose'])
 save(find('quant/2024年度精选策略2','64.*'),'tested_atom_with_exact_RET12_MA10_and_intraday_missing',
  '全320行：21:00取14价的[-13]实际12交易日差，RET12>0且C>MA10，数学及收盘时点映射100两原子，未重复跑。local_stocks含海外/商品、512760映射与515760池不符；13:30 60minMA20止损无数据。消息/邮件函数未执行，无ETF完整收益认证。',
  ['g.moment_period = 13','g.ma_period =10'],['etf16_return12_offbyone','etf16_return12_above_ma10'])
 save(find('quant/2024年度精选策略2','38.*'),'tested_atom_with_linear20_RSRS_missing_northbound_stopstate',
  '全214行：normalized20priceOLS原子111；rsrs18/600 nonSELL>=-.7原子111，MA30/gap5读但未活动。真实北向link310001/310002最近两记录净买入总和缺失，不能以成交量伪造。持仓-4%浮亏之后momentum_day_t=5，全球参考5点normalizedslope<0禁买、转正复位；非注释-80%止损。该状态及北向/ETF/分钟路径未复现。',
  ['finance.STK_ML_QUOTA','g.momentum_day'],['etf7_linear20_firstprice_slope','etf7_rsrs_nonsell_no_ma'])
 save(find('quant/2024年度精选策略2','58.*'),'tested_atom_with_bias90_clippedvol_missing_northbound_allocation',
  '全363行：bias90/20数学原子112；实际选中ETF+513100+511260按priors[20,20,.5]/winsorized39logreturn_samplevar配置，95同clippedvol数学。北向两记录sum>=0时rsrs>+.7BUY、<-.7SELL否则KEEP，BUY和KEEP均rebalance；SELL只有持仓数量>1才清风险仓且三保护ETF不卖，非简单全仓风控。40postqfq价格/波动全历史窗口为每次过去40因果，不是全样本zscore。缺北向/ETF/分钟、5%rebalance及订单资金，未伪造组合收益。',
  ['g.weights= pd.Series(stocksdata,index=g.stocks)','stocksdata=[20,20,0.5]','if g.north_money>=0:'],['bias90_linear20_first_priorclose','allocation_clipped_logvol39_low'])
 save(find('quant/2024年度精选策略2','25.*'),'tested_atom_with_mixedendpoint_globalOLSintercept_and_fourchanges',
  '全609行：100根120mclose上29点端点slope/29，截距来自该窗OLS但x保留100全局索引，abs伪R2；五错位score取最近排序，四score差负数>=2就SELL而非必须连续下降。RSRS14/600和MA7/10只算不进门，source79首价截距不是同式。154三原子显式dailyproxy已独立核验globalxpolyfit，不冒称120m复现；concept30..1000亿、top5到1、15%成本止损/订单缺失。',
  ["frequency=\"120m\"",'_, intercept = np.polyfit','if sig < 2:'],['day25_mixedendpoint_OLSintercept100_daily','day25_negativechanges_lt2_daily','day25_mixedendpoint_joint_lt2_daily'])
 save(find('quant/2024年度精选策略2','27.*'),'tested_atom_with_assetquality_cascade_EMA6_notEMA5_futures_missing',
  '全469行：股端与137同low70%lev→middle10..90%badassets→top75%goodassetturn→latestROA-minus4mean top20%→PB>.7 PS<3，最后低PB20仓。取1200天前CSI500成员，缺实际PIT成分。CTA当前11:15指数C<EMA6优先-1 else C>EMA2 +1 else0，与source45EMA5不同，155单测6/2。ATR20/50配置及prev5high-5ATR数学120同轴，实际期货保证金/到期/转账/shortsignal==0平仓路径缺失，不称CTA已复现。',
  ['g.long_days = 6','g.short_days = 2','valuation.pb_ratio > 0.7','valuation.ps_ratio < 3'],['asset60_reported_roa_delta4','asset60_cascade_roa_partial','asset60_cascade_lowPB_source','cta27_ema6_2_priority_daily','hedge45_lowatr20_50_ratio','hedge45_longatr5_boundary_margin'])
 for pat,key,decision in [
  ('34*','small34_size5_50_priority_fullA','全324行：totalMV5..50亿，375天、399101主板ST、price<=80、top100→50→5，周二。空仓日期04-05..04-30、01-05..02-05，非整月；5%abs(mean(C/O-1))上涨也触发市场止损，持仓7%stop，涨停打开后补仓、止损隔日。155仅同fullA支持的市值区间资格优先，与SIZE对照，不把路径胜率/十年标题当新alpha。'),
  ('43*','small43_size5_300_priority_fullA','全307行：totalMV5..300亿最小27→9，不是5..30亿；375天主板ST/涨停、周二，1/4整月511880。10%持仓stop、5%abs市场日均幅，上涨也清仓；prepare每日清limitup_stocks，并非永久黑名单。155仅fullA资格优先与SIZE对照，未测原9仓及ETF路径。')]:
  save(find('quant/聚宽2025年精选',pat),'tested_atom_with_literal_sizeband_fullsupport_membership',decision,['valuation.market_cap.between'],[key])
 save(find('quant/量化策略/量化策略/实盘2026/Ptrade','pt版05*'),'tested_atom_with_same_valid80trend_and_corr244_changed_execution',
  '全271行：逐函数AST核对除了initialize其它函数与pt版01一致，valid80volume>0后二十日动量/六十均线秩和top40和244logreturn低peerabs数学映射121；initialize改ETFpool39只，不是全modulealias，所有数据及订单语义保留检查。月冻结强势池、corr取4再2、T0sellable等缺ETF行情，不声称完整策略收益。',
  ['g.top_percent = 0.4','g.corr_window = 245'],['ptrade01_valid80_trend20_bias60','ptrade01_top40_lowabs_corr244'])
 save(find('quant/量化策略/量化策略/小市值策略2026','实02*'),'tested_atom_with_MA5_orderentry_not_active_prefilter',
  '全247行：circMV最小9后选3，filter_ma_stock调用注释但open_position实际nowprice<MA5禁买（等于允许）；旧持仓不受门且不在choice即卖，sellMA1整段字符串不运行。数学partial136已测同门但总MV/完成收盘及priorMA5是明确proxy；新增日志和context修补不是新alpha，不把完整module说ASTalias。399101/分钟MA供应商/ST/limit持仓仍缺失。',
  ['if now_price < MA1[security]:','#check_out_lists = filter_ma_stock'],['small15_activeMA5_entry_partial'])
 save(find('quant/聚宽2025年精选','62*'),'missing_ETF_NAV_open_discount_not_stock_bookvalue',
  '全300行：前日成交额>1e7 ETF按开盘/unitNAV-1折价升序、abs<20%、factor==1，门槛初2.5%无买入减.15至1.5%而非注释.1；限价±2%、最低5/fee金额。historicalNAV与live网页现值分支不同，基金净值非股票BPS，不能以BM充ETF折价。未执行网页/发信/交易模块，缺ETF/PITNAV/竞价数据。',
  ["get_extras('unit_net_value'",'g.least_premium=max(g.least_premium-0.15,1.5)'])
 # Exact full-module aliases retain every executable parameter and call.
 coverage=pd.read_csv(OUT/'all_source_coverage.csv').fillna('');buckets=defaultdict(list)
 for r in coverage.to_dict('records'):
  p=q.ROOT/r['path']
  if p.suffix.lower() not in ['.py','.txt','.ipynb']:continue
  try:tree=ast.parse(read_text(p).split('原文策略源码如下：',1)[-1].expandtabs(4))
  except SyntaxError:continue
  buckets[hashlib.sha256(ast.dump(StripDoc().visit(tree),include_attributes=False).encode()).hexdigest()].append(r)
 resolved={r['path']:r for r in rows};aliases=[]
 for sha,group in buckets.items():
  prior=[r for r in group if r['actual_recipe_links'] or r['path'] in resolved]
  if not prior:continue
  canonical=prior[0];cr=resolved.get(canonical['path']);keys=[x.split(':',1)[1] for x in canonical['actual_recipe_links'].split(';') if x] or (cr['related_tested_keys'] if cr else [])
  for r in group:
   if r['path'] in resolved or r['actual_recipe_links'] or r['path']==canonical['path'] or r['sweep_state']!='reviewed_family_duplicate_or_variant_needs_recipe_trace':continue
   save(r['path'],'tested_atom_with_complete_executable_AST_alias' if keys else 'missing_dependencies_complete_executable_AST_alias',
    '只去独立字符串后完整可执行AST相同，复用'+canonical['path']+'全部精确缺口/已测原子；非完整策略认证。'+(cr['decision'] if cr else ''),keys=keys,
    extra=dict(equivalent_source=canonical['path'],full_executable_ast_sha256=sha,normalization='standalone string Expr only'))
   aliases.append(dict(path=r['path'],canonical=canonical['path'],keys=keys))
 q.dump(eout/'new_exact_whole_AST_aliases.json',aliases);q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows),'NEWASTALIASES',len(aliases))
if __name__=='__main__':main()
