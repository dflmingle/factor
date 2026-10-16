"""Exact decisions after reading macro/breadth/state code; no corpus execution."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence5';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);evidence=[]
  for anchor in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if anchor in l];assert found,(p,anchor);evidence.extend(found[:5])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=evidence,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 add('2021年度精选策略','33.','market_scalar_missing_bank_dividend_repo',
  '银行801780股息率*.92与GC182逆回购分别MA60，signal=-(股息MA60-回购MA60)，比较前1/前2日signal上涨才持有399300。不是高股息截面，实际逆回购非十年国债。缺真实三序列；summary shift(-1)仅交易统计不用于仓位，不能借此断言信号泄漏。',
  ["code=='801780'","name=='GC182'",'dividend_ratio"] = final_df["dividend_ratio"]*0.92','rolling(60)','pre1_date_value >pre2_date_value','shift(-1)'])
 add('2021年度精选策略','53.','market_scalar_missing_exchange_pe_average',
  '实际查询交易所322002 pe_average取log10；2500条历史中位数+.05sampleSTD/-.25sampleSTD，初始化1.5/1.2每周被覆盖，非普通均值±1.5STD。50周资金基准，高估卖出周数=50/((高线-当前)/高线*100)为负；低估50*(1-5相对低估)并<=0改1。外部交易所历史PE和基金现金注入/持仓账本缺，不能用个股PE排名代替。',
  ["exchange_code == '322002'",'np.log10(x.pe_average)','section = self.Q(2500).V','median+0.05*std,median-0.25*std','weeks = g.weeks /','inout_cash(5000'])
 add('2024年度精选策略1','97.','no_economic_ranking_missing_FED_macro_visualization',
  '历史HS300成分PE中位数未按注释排除负值，FED=100/PE-国债10Y，Graham=(100/PE)/国债。完整样本sort后10%/5%画常数带，仅图形无冻结因果交易规则；将其回填历史交易会泄漏。国债抓取分块n=n_days//244却步长n而非244；缺PIT成分和真实债券，未伪造截面。',
  ["get_index_stocks(my_security,date=csrq)","df['pe_ratio'].median()",'n = n_days // limit','pos1, pos2 = n * i',"np.sort(y)","(100/last_dataframe['pe'])/last_dataframe['ten_bond']"])
 add('2021年度精选策略','2.','missing_PIT_sector_breadth_dashboard',
  '历史行业分类和180自然日上市/ST筛选；N日收益>阈值组内平均收益*个数比例*1000取int，组股票<=10得0。returns_series最后列实际截止t-1，不是当前close；三行业分类示例5日/5%仅展示。缺PIT行业，不能把全A动量排名当行业热度。',
  ['timedelta(days=180)','get_industry(list(df_sec.index),date=date)','len(df)>10','int(len(df_ok)/len(df)*mean*10)','df_close.iloc[-(back_days+1-i)]','return_days=5,back_days=30'])
 add('2023年度精选策略','63.','missing_PIT_sw3_sector_momentum_dashboard',
  '静态today sw_l3行业展示，剔退市/150日新股/ST，五个涨幅阈值(1日5%、3日8%、5日10%、10日15%、20日20%)；行业分数=count合格²/行业总数并保留2位，非行业收益均值。30行情点滚动看10日最后取行业top6，无交易组合规则；历史缺PIT行业不可用当前标签回填。',
  ['industry_level = "sw_l3"','count * count / total_count','growth_limit = 0.08','growth_limit = 0.15','growth_limit = 0.2','[0:6]'])
 add('聚宽2025年精选','92','missing_PIT_five_sector_breadth_reversal',
  '000985历史成分内仅军工/食品/煤炭/银行/通信五行业，21价点dropna后前收盘>MA20比例round整数，最高行业内10价点实际9日收益最小5只，非20日个股反转。缺历史行业及成分；不把低RET9当完整行业宽度组合。',
  ["industry_code = ['801740','801120','801950','801780','801770']",'p_count + 20','df_close.iloc[:, -p_count:] > df_ma20','nlargest(g.num)','count=10','nsmallest(g.stock_num)'])
 add('聚宽2025年精选','30','microcap_scalar_missing_intraday_panic_basket_state',
  '399101前15小流通市值过滤后5股的动态人工指数，100日初始化用当期target倒灌历史有选择偏差，gen函数用今日价/前日pre_close而非今日/昨收。风险=盘中人工指数<最近10人工值*.78；状态函数每次重复乘昨日收益，close_account先has_risk再break_risk会二次推进。缺分钟及历史持仓；不以单股drawdown10替代此路径，未改源码冒称忠实。',
  ['g.stock_num * 3','initial_stock_series(100)','stock_index_cur += one_stock_vlu*(current_data[stock].last_price/stock_df.pre_close[-1])','stock_index_cur < max_value*0.78','val = has_risk_sig(context, 1)','break_risk_status(context) == 1'])
 add('2024年度精选策略2','42.','tested_atom_with_unreproduced_rank_buffers_and_filters',
  '五腿log(min/value)源码weights[5,5,8,4,10]与92批已复现排序相同；1200分钟成交量及实价替换日线proxy，源码floatcap100和PB .01..30、昨日涨幅<.087、上市300日、ST、新买9/持有10排名缓冲、5日禁买、MA10±.003牛熊与30%熊仓均未复现，不重复作新簇。',
  ['g.weights = [5,5,8,4,10]','g.sellrank = 10','g.buyrank = 9','g.buyagain = 5','g.threshold = 0.003',"attribute_history(stock, 1200, '1m'"],['quakecat_lowlog_price8_vol4_reversal10','quakecat_lowlog_full_size_proxy'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
