"""Full-read precise exclusions and source traces, never full-strategy claims."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence8';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if a in l];assert found,(p,a);ev.extend(found[:4])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 add('聚宽2025年精选','71','missing_dividend_ETF_NAV_allocation_data',
 '全571行复核。股票40%实际raw低价10%正EPS再低流通市值15，另365日股息前10%且PE0..25/扣非ROE>3/总营收同比>5/净利同比>11/PEG.08..1.9；缺分红原排序不能替造。商品/QDII各30%是249收益最小方差SLSQP，约束1/N²..0.9；price/NAV降序0..1.1非低折价，成交量mask未删索引、free_stock_position等于ETF候选数可能0除。缺ETF/NAV/公告分红，rawprice禁止混正式qfq，未冒称整策略或新alpha。',
 ['free_stock_position = position_count-hold_stock_num',"val['score'] = val['close'] / val['unit_net_value']",'indicator.inc_total_revenue_year_on_year>5','return result.x'])
 add('聚宽2025年精选','76','tested_size_family_missing_staleindex_and_execution',
 '全293行复核。active初始池是previous_date-375自然日的399101成分，不等于IPO375过滤；5..50亿低市值50取5，原价80持仓例外。现役市值原子已测，范围只是资格变体；过去2close成分均收益<=-5%全卖、成本-7%、五天禁买，1月及4月5日后货基。缺PIT历史成分/实际限价/分钟与状态，不以qfq全A伪称原风控收益。',
 ['datetime.timedelta(days=375)','valuation.market_cap.between(5,50)','g.stoploss_limit = 0.07',"'04-05' <= today"],['small_size'])
 add('聚宽2025年精选','84','missing_dividend_ranking_with_known_size_PEG_qualification',
 '全231行复核。365日股息前25%再-3<PE/净利增速<3，允许负PEG；ROE/PB仅查询未筛，最后低市值10。补买在卖出之前调用，今日卖后补仓可能等下一日。缺PIT分红收益排名、actual限价/交易状态。不能以PEG资格替代股息主排序后称完整策略，市值/盈利增长已有原子。',
 ['get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)','indicator.inc_net_profit_year_on_year>-3','indicator.roe / valuation.pb_ratio'],['small_size'])
 add('聚宽2025年精选','12','tested_helpers_plus_missing_vendor_dividend_unlock_portfolio_layers',
 '全738行四子账户复核。PB.98/营业利润同比ROA及25/200趋势+229beta20下带已有116/117。XSZ第二组Price1Y/利润成本/VOL120系数与84variant1逐字一致；第一组ARBR/SGAI/利润营收/留存每股为-2.3425/-694.7936/-170.0463/-1362.5762但供应商ARBR和SGAI年度季度语义未验，第三组含正式禁止rawprice及未验证5年salesgrowth，不能称全线性组已测。每组top10%正EPS并集再小流通值；缺120日未来已知解禁表和365股息前26%，子账户止损成本-20%后20自然日停默是状态，不是独立alpha。',
 ["'SGAI'",'-0.0647128120839873',"'price_no_fq'",'filter_locked_shares(context, initial_list, 120)','False, 0, 0.26'],['subportfolio12_pb098_opgrowth_roa','subportfolio12_dualtrend25_200_priorclose','subportfolio12_beta18_20lowerband','fixedlinear_priceprofitturn_variant1'])
 add('聚宽2025年精选','64','tested_helpers_with_redundant_union_index_temperature_missing',
 '全546行复核。小盘资格第二列5..30亿正YTD归母/净利/营收>1e8已118；但先无条件低市值50再资格50拼接取9，第二列往往被第一列覆盖，不得当独立策略收益。White_Horse冷/温/热PB-ROA/扣非ROE/inc_return三个财务分支与source80已测，220指数温度MEANlast5位置<.2/>.9及max60/minall>1.2并保留旧状态缺真实指数。Boll定义未调用，不能加到64；ETF/风控状态不复现。',
 ['target_list_1 + target_list_2','g.market_temperature == "cold"','market_height > 0.90','max(index300[-60:]) / min(index300) > 1.20'],['sizeprofit64_mv5_30_ytd'])
 add('量化策略/量化策略/实盘2026/Ptrade','pt版07ETF动量加EPO平衡策略','tested_trend_atom_missing_ETF_EPO_allocation',
 '全375行复核。正34log趋势×R2前3已有104；1000价点最多999简单收益，anchor=归一inverseSTD（与JQ17inverseVAR不同）。actual s=returns.mean，gamma以s与invCovtilde定义，lambda10在anchored分支不使用，不能说预期收益未用。covshrink20%、负权剪0再归一属三个ETF配置；列缺失后仍以原target顺序配权存在错配。缺ETF、真实调仓/现金实盘状态，无全A新alpha或完整配置回测之称。',
 ['g.optim_window = 1000','inv_std = 1.0 / np.sqrt(d)','signal = returns.mean()','gamma = np.sqrt(a.T @ cov_tilde @ a)','total_buy_cash = context.portfolio.cash * g.position_pct'],['epo17_logtrend34_priorclose','epo17_positive34_qualified'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
