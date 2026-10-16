"""Full readings: exact dividend/ETF construction decisions, not fake backtests."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence6';eout.mkdir(exist_ok=True)
 def add(group,prefix,state,decision,anchors,keys=None):
  ps=list((q.ROOT/'quant'/group).glob(prefix+'*'));assert len(ps)==1,(group,prefix)
  p=ps[0];s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if a in l];assert found,(p,a);ev.extend(found[:4])
  path=str(p.relative_to(q.ROOT));sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=keys or [],full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 add('2024年度精选策略2','94.','no_economic_ranking_missing_FoF_fund_history',
  'ETF/FoF静态配置研究，上市365日、份额乘价格>1亿、MIN21money>HS300MEAN21money*1e-6；241价点240log收益sampleSTD*100sqrt241，1%<波动<HS300波动，逆波动权重合计.95。不是未来收益alpha；当期选池回填241历史仅展示，缺ETF份额及指数，不拿全A低波冒称完整FoF。',
  ['nday = 241','value = price*shares','hm = h.min()','V = 100*rday*r.std()','weight = 0.95*w/w.sum()'])
 add('聚宽2025年精选','100','no_economic_ranking_fund_cluster_dashboard',
  '243价点242log收益，上市365日，MEAN243money>1e6；KMeans10未设seed，fit后fit_predict重新拟合；各簇成交额最大5只，Rf=2未用。提供去重/分组方法而非收益方向，当前池回填历史存在选择偏差，无冻结历史alpha规则。',
  ['nday = 243','n_cluster = 10','cluster.fit_predict','sort_values(ascending=False).head(n_class)'])
 add('聚宽2025年精选','66','no_economic_ranking_ETF_pool_clustering',
  '当前ETF池上市<20230101，MEAN1000money>5000万，240价格239简单收益，KMeans30seed42取各簇最早上市者；corr>.85再按日期删除，union未正确合并所有重叠连通分量。可选删除2020后上市。静态候选池去重而非alpha，不能回填历史选股。',
  ['count=1000','n_clusters = 30','corr.loc[i, j] > 0.85',"df.groupby('cluster_id').first()"])
 add('聚宽2025年精选','86','no_economic_ranking_ETF_pool_clustering_variant',
  '66变体：上市<20210101且当前未退市，MEAN300money>1000万（注释5000万不准确），450价格449简单收益，KMeans24seed42，各簇最早ETF，再corr>.85去重；2020新股删除已注释。没有alpha排序，当前存续池不能回填正式历史。',
  ['count=300','money\'].mean() > 1e7','count=450','n_clusters = 24',"df['end_date'] >="])
 add('聚宽2025年精选','40','missing_PIT_fiveyear_registration_dividend_sector',
  '五个365自然日登记窗口均有记录者，营业利润同比>0，各行业股息前2；保留>3%新买>4%。不是连续分红增长，df.index.levels可能含未使用股票。缺登记分红及PIT行业，不用财务现金流替代派息，也不宣称完整可跑。',
  ['a_registration_date','0.03','0.04','levels[1]'])
 add('聚宽2025年精选','42','missing_PIT_dividend_policy_paid1year',
  '标题三年，实际365日派息>三年平均净利30% OR >5000万元；5月后年报anchor去年，否则前年，watch_date=None未认证PIT；股息排序和p1/p2切片都注释，返回全部。后续5..50亿市值/最低100再50，10持仓与盘中状态。缺分红记录，不能以高股息因子替代原筛选。',
  ['timedelta(days=365)','time1.month>=5',"DR['bonus_amount_rmb']>5000",'final_list = list(DR.index)'])
 add('聚宽2025年精选','44','missing_PIT_audit_bonus_smallsize44',
  '正归母/净利、营收>1亿、ROE/ROA>0，MV10..10000亿最小3倍股数；近三年报告期审计意见>2且!=6剔除；指定月今年预案已公布按bonus_ratio升序，余月排已知不分配，人数不足补回原小盘。MA10乖离调3..6股，不是高股息排序，缺审计/预案/原持仓状态。',
  ['opinion_type_id >2','opinion_type_id != 6','board_plan_pub_date<=end_date',"sort_values(by='bonus_ratio',ascending=True)",'bias =100*'])
 add('聚宽2025年精选','79','missing_PIT_audit_bonus_smallsize79',
  '质量正值低市值5倍股数；按pub_date近三年排opinion3/4/5/7，未复用44的report_type/end_date规则；分红已实施公告<=前日后低股息升序，不足补原市值排序。MA10绝对指数点差500/200/-200/-500调3..6股，与44百分比乖离不同。缺审计/分红实施和真实指数，不能当相同完整策略。',
  ['values_to_check = [3, 4, 5, 7]','implementation_pub_date<=end_date',"sort_values(by='bonus_ratio',ascending=True)",'diff = last_row'])
 add('2021年度精选策略','4.','fixed_two_stock_pair_missing_bank_dividends',
  '固定四家银行每年5月更新1股，PE/PB>0，近1095自然日董事会预案金额累计*.33*.01/市值降序（单位比例不影响rank）；不是每日全A截面。缺预案历史，股数仅4低于100有效支持门槛，不把四银行收益当全Aalpha。',
  ['days=3*365','board_plan_pub_date > dt_3y','0.33 * 1e-2','month in [5]'])
 add('2021年度精选策略','70.','missing_PIT_reportdate_dividend_threebands',
  'HS300positivePE；按最新财报季度回溯12季度分红report_date，未限定分红pub_date有时点泄漏风险。逐年派息/现市值>.02/.016/.0128，合计>.10；股息1/2/3/1年序贯80/40/20/10，然后5/10保留买入缓冲及盘中价>=前30MA新买。不是简单红利乘均线。缺PIT分红和成分；不补造历史记录。',
  ['report_date<=statDate','comp_value=market_cap*0.02','market_cap*0.1','thirty_mean'])
 add('2024年度精选策略1','19.','missing_PIT_dividend_growth_eligibility',
  '1095日登记股息率最高10%后actual PE(0,25)、扣非ROEinc_return>3、营收同比>5、净利同比>11、PE/净利同比(.08,1.9)；源码查询后无继续股息降序，按返回行序前10。原分红首筛缺失，不把单独质量门槛冒称完整高红利排序。',
  ['days=365*3','valuation.pe_ratio.between(0,25)','indicator.inc_return >3','<1.9'])
 for group,prefix in [('2024年度精选策略1','6.'),('2024年度精选策略2','15.')]:
  add(group,prefix,'missing_PIT_dividend_turnover_MLEV',
   '实际365日股息最高50%而非标题/旧笔记三年；turnover_volatility降序80%保留高波，MLEV升序半池，再最小流通市值15/持仓10。turnovervol供应商定义和MLEV未字节对齐，登记分红缺失。可复现低换手STD控制已保存，但方向/配方不同，不能认证原复合。',
   ['timedelta(days=365)',"'turnover_volatility', False, 0, 0.8","'MLEV', True, 0, 0.5"],['low_turn_std20'])
 add('聚宽2025年精选','11','tested_atom_with_missing_vendor_quality_and_holdbuffer',
  '399317市值底10%后PB/inc_return扣非ROE/ocf_to_revenue>0，最小36然后原仓优先保留30；单股1%名义仓和3固定ETF吸余钱。纯低市值原子已测，扣非ROE字段和PIT指数/持仓缓冲仍缺，不能当100股等权也不能称完整复现。',
  ['nposition = 100','m = int(0.1*len(stocks))','df.inc_return > 0','stocks_0 + stocks_1'],['small_size'])
 add('量化策略/量化策略/小市值策略2026','03','tested_atom_with_unreproduced_index_execution_threshold',
  '399101最小流通市值15/ST停牌过滤取5，每周等权；5%阈值只限制已选股票持仓价值再平衡，不降低换标的时全卖出的换手。唯一alpha排序是原低市值，无新指标；本地小市值原子已测，指数/交易状态/实际阈值账本未复现。',
  ['valuation.circulating_market_cap.asc()','g.buy_stock_count * 3','> 0.05'],['small_size'])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
