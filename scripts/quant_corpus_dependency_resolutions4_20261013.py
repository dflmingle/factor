"""Additional actual formula traces and missing industry/vendor recipes."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'

def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence4';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);evidence=[]
  for anchor in anchors:
   found=[dict(line=i+1,text=l.strip()) for i,l in enumerate(s.splitlines()) if anchor in l];assert found,(p,anchor);evidence.extend(found[:5])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path]
  rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=evidence,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 add('聚宽2025年精选','82','tested_atom_with_unreproduced_portfolio_weights',
  '正PB/PE/PCF交集，point=rank(MV)+(rankPB+rankPE+rankPCF)/3低分优先，数学排名与50批正值权重修正版相同。100股线性递减配置最后一股零权重，成交后±10%再平衡门控未复现；不能重复登记为新簇。',
  ['return X[0] + (X[1] + X[2] + X[3])/3','valuation.pb_ratio>0','valuation.pe_ratio>0','valuation.pcf_ratio>0','g.choicenum = 100','generate_arithmetic_series','np/p>1.1'],['smallvalue4_source_weights_gates'])
 add('2023年度精选策略','48.','missing_PIT_industry_sequential_growth_selection',
  '中证500市值剔除实际最低25%并漏最大1股，逐行业低PEG70%→高利润增长70%→高ROE三分一序贯筛选，最后高流通市值；缺PIT行业/成分，不能全A平替。止损名close30实际5close，15%阈值为max/price-1。',
  ['num_1 = int(len(shizhi_list)/4)','shizhi_list[num_1:-1]','if x in peg_all','if x in npgr_all','circulating_market_cap.desc()','history(5','ret >= 0.15'])
 add('2024年度精选策略2','98.','missing_PIT_industry_parallel_growth_selection',
  '与48批来源不同：低PEG70%、高利润增长70%、高ROE三分一在同一市值池独立求集合后交集；不是48的序贯删减。最后仍高流通市值，真实PIT行业缺，无忠实资格测试。标题股息排序代码未出现，不制造股息因子。',
  ['num_1 = int(len(shizhi_list)/4)','hyshizhi_list','PNR_all','if((i in npgr_all)and(i in roe_all))','circulating_market_cap.desc()'])
 add('2024年度精选策略1','30.','missing_PIT_four_industry_and_vendor_growth',
  '固定事后央国企名单，growth高80%（注释剔15%实际20%），只四个申万行业；行业内PB最低并列method=min百分位*.8+全池PE最低并列百分位*.2。缺PIT行业及供应商growth定义，全球PB/PE混合秩不等价；持仓4不足截面100门槛。',
  ['growth_list[:int(len(growth_list)*0.80)]',"['801180','801780','801790','801720']","rank(method='min',ascending=True,pct=True)","df['dense'] * 0.8",'g.stock_num = 4'])
 add('聚宽2025年精选','53','missing_vendor_inc_return_and_index_membership',
  '399317成分内PB>0、inc_return>0、ocf_to_revenue>0后最小120市值、实际每股1/100配置和现金1.5份门槛。inc_return不是已核实ROE同义字段；不要去掉两项约束仅跑SIZE并冒称微盘三正。',
  ["index = '399317.XSHE'",'valuation.pb_ratio > 0','indicator.inc_return > 0','indicator.ocf_to_revenue > 0','nchoice = 120','cash_size = 1.5'],['small_size'])
 add('2024年度精选策略2','9.','missing_limit_prices_and_vendor_multirecipe_fields',
  '串接四组initialize及同名选股函数，原始整文件执行会覆盖前定义；逐配方分别记录：①小流通市值+市场股数*.005，②涨停次数<.2均值且250日超额>池均值（指数常数抵消但涨停表缺），③低PEG10%→低EBIT25%→低turnover_volatility半池→小市值，④.1营收/.35总利/.15净利/.35五年盈利/.05五年销售加权高10%→正EPS小市值。56批仅覆盖③前两筛，turnover_volatility、两项5年字段未核实，不能声称全配方跑完。',
  ['g.p = 0.005','filter_high_limit_count_stock','high_limit_days','gap = stock_ret - MKT_ret',"'turnover_volatility', True, 0.5", "0.35*df['earnings_growth']"],['lowpeg_lowebit_small_source','small_size'])
 add('2024年度精选策略2','21.','missing_intraday_index_BBI_and_market_gate',
  '行业指数30分钟BBI21/34/55/89除当前盘中价最小者；七指数当前日涨幅最大者>0才买对应ETF。原始前周期涨幅列误填当前increase；缺30分钟指数及ETF。不可把21/34/55/89当日线原式；周三11:15与EMA5状态依赖未复现。',
  ["g.unit = '30m'",'timeperiod1=21, timeperiod2=34, timeperiod3=55, timeperiod4=89','BBI2[index]/df_close[0]','weekday=3',"'前周期涨幅': increase"])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
