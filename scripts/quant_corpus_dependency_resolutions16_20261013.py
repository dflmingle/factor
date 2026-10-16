"""Further complete-source reviews; trace atoms without claiming strategies."""
import ast,hashlib,json
from collections import defaultdict
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_dependency_resolutions10_20261013 import StripDoc
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012';OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence16';eout.mkdir(exist_ok=True)
 def save(path,state,decision,anchors=(),keys=(),extra=None):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 def find(folder,pattern):
  paths=list((q.ROOT/folder).glob(pattern));assert len(paths)==1,(folder,pattern,paths)
  return str(paths[0].relative_to(q.ROOT))
 for pat,n in [('5.*',223),('23.*',312)]:
  save(find('quant/2024年度精选策略1',pat),'tested_atom_with_fixed_priceprofit_inventory_coefficients_qfq_adapter',
   f'全{n}行：固定3负系数price_no_fq/totalprofitcost/inventoryturn，不是在回测中训练；前10%再EPS>0/circMV最小10。source148显式qfq价格替代及reportedinv_turn、PITTTMprofitcost供应商代理，原始raw未混入正式；另去价格财务扩展及同fullA支持SIZE资格优先对照均已测。source23取max(10%,10)、每日补缺以及旧涨停免卖/黑名单不同，训练来源不可见，不称独立样本外或完整股票路径。',
   ['-6.123355346008858e-05','-0.002579342458393642','-2.194257357346814e-06'],['linear5_qfq_profit_inventory_fixed','linear5_profit_inventory_sizefree_extension','linear5_positiveEPS_topscore_priority'])
 save(find('quant/2024年度精选策略2','24.*'),'tested_atom_with_all3_damped_RSRS_configs_29price_momentum',
  '全156行：29logprice趋势×R2原子150；RSRS18分别M700/800/500，原populationZ×R2^(2*sample18returnSTD最近M分位)，149三配置全测。KEEP不是买入，新标的只有BUY换入；旧持仓与所选标的不同时另测旧标的SELL，空仓511880。活跃池是三个INDEX代码不是ETF；2%两次盘中总值变化/10%历史高水位止损是账户路径，未充个股alpha；不因标题以为source83N16/M600同式。',
  ['g.momentum_day = 29',"g.M = {'000300.XSHG':700",'ret_std = data[','rsrs_score = zscore* r2**(2*ret_quantile)'],['damped24_logtrend29_atom',*[f'damped24_rsrs18_{m}_source' for m in [700,800,500]]])
 save(find('quant/2024年度精选策略2','1.*'),'tested_atom_with_nointercept_MA20_entry_and_missing_vendor_growth',
  '全261行：SG/MS/PEG三腿，MS=.1/.35/.15/.4、SG/MS/PEG都经同EPS>0helper/circMV小5，三腿union后先最多10。不同35，未加热门行业，PEG腿也有EPS；MA40prices rolling20.iloc20变20点，减首MA后sm.OLS(y,x)不带常数，100×斜率round1<−2只禁新仓、不卖既有。source150单测连续和entry门，不能误称带截距OLS或持仓退出；SG/5year/vendorPEG/turnvol/PIT实际涨停未重建。',
  ['sm.OLS(MA_N_Arr, X)','if slope < -2:','indicator.eps > 0'],['growth1_originMA20_slope20','growth1_originMA20_newentry_allowed'])
 save(find('quant/2024年度精选策略2','28.*SG-MS*'),'missing_vendor_SG_MS_PEG_turnvol_and_union_holdings',
  '全290行：SG最高10%/MS=.1/.35/.15/.4最高10%均EPS>0，PEG低20%再turnovervol低50%不加EPS，eachcircMV小5并集再小10；20日持仓涨停冷却。不同source35没有热门行业，亦不同source1的PEG正EPS和额外MAnoIntercept。供应商5yeargrowth/PEG/turnvol/circMV/分钟涨停缺等价；不以旧其它权重MS或source1资格代替。',
  ["'PEG', True, 0, 0.2",'0.1*df[','0.35*df[','0.15*df[','0.4*df['])
 save(find('quant/2024年度精选策略1','13.*'),'tested_atom_with_literal_ROE015_ROA010_missing_price_holdings',
  '全392行：叫get_peg但活动只ROE>.15和ROA>.10（原percentpoint，非15%/10%），PEG/PB/收益率门/股息筛注释。samequalitysize原子framework9_small_literal_quality已116测试，currentminute<10只对未持仓和highlimit*.97/lowlimit*1.04、月末force、30日买过且涨停冷却缺失。Aprilban代码注释，prepare直接False，不能声称四月空仓。全股回测不等于原十仓路径。',
  ['indicator.roe > 0.15','indicator.roa > 0.10','g.no_trading_today_signal =  False','current_data[stock].high_limit*0.97'],['framework9_small_literal_quality'])
 save(find('quant/2024年度精选策略1','9.*'),'missing_vendor_inc_return_and_ocf_ratio_qualification_size',
  '全94行：PB>0/inc_return>0/revenueYoY>0/netprofitYoY>0/ocf_to_operatingprofit>5，totalMV最小95每月首日，旧涨停保留。此处比较都是真查询filter，不同booleanSVR特征。inc_return含义不能任意同ROE，ocf比值单位不同不能用>5%无证替换；只旧SIZE排序，资格与完整持仓未等价。',
  ['indicator.inc_return >0','indicator.ocf_to_operating_profit>5','g.stock_num = 95'])
 save(find('quant/2024年度精选策略2','22.*'),'missing_registration_dividends_lowprice_monthly_size',
  '全约197行：最近365登记分红/totalMV，先仅有分红记录者内最高25%（非全A25%），再totalMV小，currentminute<9只约束未持仓，月初10只；月调旧股即使昨天涨停不在choice也正常卖，盘中开板另卖。缺登记分红/分钟/ST，不把应付股利或CFP冒充现金股息。源理想0滑点不代表可实现PnL。',
  ['finance.STK_XR_XD.a_registration_date','get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)',"last_prices[stock][-1] < 9"])
 save(find('quant/2024年度精选策略1','48.*'),'missing_PIT_index_floatMV_execution_bridge_not_new_ranking',
  '全146行：jqtrade/onequant迁移执行示例，399101成分内circMV最小100后ST/涨跌停过滤取5，09:40。250天新股判别写start_date-current_date<=250days，对既上市股票几乎总True，不能修好冒称原式。没有额外经济排序；缺PIT成分/circMV/分钟，totalMV只是已有控制，不当新因子。注释实盘调用/全局/认证未执行。',
  ['valuation.circulating_market_cap.asc()',"sdata.start_date - context.current_dt.date()"])
 save(find('quant/2024年度精选策略2','89.*'),'missing_PIT_industry_largestmember_ROE_source_library_not_riskparity',
  '全1050行逐段复核：每CSRC二级行业>5只时只取totalMV最大1只，再ROE高排序10，排goodwill/equity>.1/listing80days。非低PS（调用注释）；配置riskExposure.03和confidence1.96但assetallocationtype=0等权，fun_calPosition直接returnequity_ratio，未启用风险平价。真正止损是两指数RET20均<=1% AND 1/median(EP)>80。equitycurveprotect调用注释；季度财务/分红库函数无活动选择调用。缺PITindustry/指数/分钟，不能拿全A大盘ROE冒称行业龙头，也不当风控算法已回测。',
  ['if len(stock_list)>5:','valuation.market_cap.desc()).limit(1)','context.pe_ratio_median>80','trade_ratio = equity_ratio # 简化'])
 save(find('quant/2024年度精选策略2','53.*'),'tested_atom_with_KDJ_entry_missing_fixedbasket_grid_path',
  '全900行逐段复核：固定stock/ETF池按每季首月更新；14:50 reset/buy/cover/sell，active新仓只是KDJ9/3/3 J<0及90close.max>0，151连续lowJ/二值entry显式seedproxy已独立递归核验。EBIT/EV、5年/1年股息和FScore9都在注释选股调用内，未活动。网格lastoperation及每批lot日期/价格、连续买量×1.2、绝对额度、30到360日延长等路径缺分钟/T+1/ST/涨跌停，无原收益复现。sell last_price实际误取日期字符串，reset有stale stock键；不悄悄修订单。',
  ['if KDJ_condition(context,stock) < 0:','run_daily(dolsd2, time=','last_price = list(g.last_opt_price[stock].values())[0][0]'],['grid53_low_J9_3_3_proxy','grid53_J9_belowzero_entry_proxy'])
 # Exact complete executable modules only, retaining ALL financial, pool,
 # scheduling and order parameters. Standalone prose is the sole omission.
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
   save(r['path'],'tested_atom_with_complete_executable_AST_alias' if keys else 'missing_dependencies_complete_executable_AST_alias','完整可执行AST相同，仅去独立字符串；复用'+canonical['path']+'的原子/缺口，保留全参数/调度/订单，非整策略认证。'+(cr['decision'] if cr else ''),keys=keys,extra=dict(equivalent_source=canonical['path'],full_executable_ast_sha256=sha,normalization='standalone string Expr only'));aliases.append(dict(path=r['path'],canonical=canonical['path'],keys=keys))
 q.dump(eout/'new_exact_whole_AST_aliases.json',aliases);q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows),'NEWASTALIASES',len(aliases))
if __name__=='__main__':main()
