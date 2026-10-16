"""Reviewed literal kernels, model-file blockers and allocation limitations."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence11';eout.mkdir(exist_ok=True)
 def find(folder,pattern):return str(next((q.ROOT/folder).glob(pattern)).relative_to(q.ROOT))
 def save(path,state,decision,anchors,keys=()):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT))))
 p=find('quant/聚宽2025年精选','81*')
 save(p,'tested_atom_with_exact_threeprice_smooth21',
  '全139行：prior30[-23:-20]三价和对比prior[-2:]+实时价的三价和，base为prior[-21]。买严格>1.001base，只有持仓仍排名第一才用<.999卖；不同排名但新第一未满足门槛则保留旧仓。source128单股完整bar代理保留公式，而第三项是明确NEW逐股滞回适配；未复现11ETF实时价/top1/订单。随机并列jitter非平台已知隐藏排序。',
  ['his_n_price = sum(close_data1[-23:-20])/3','R = (close_data1[-2]+close_data1[-1]+curr_price-sum(close_data1[-23:-20]))','SEC_LIST[0][3]*1.001','SEC_LIST[0][3]*0.999'],['etf03_smooth3_ret21_literal','etf03_smooth3_ret21_entry_partial','etf03_ret21_hysteresis_stock_adapter'])
 for folder,pattern in [('quant/2024年度精选策略1','3.*'),('quant/2024年度精选策略1','43.*'),('quant/量化策略/量化策略/ETF轮动策略2026','10*')]:
  p=find(folder,pattern)
  save(p,'tested_atom_with_exact_unweighted_logtrend25_priorbar',
   '完整源码：g.m_days=25，prior25 logC无权OLS，expm1(250*slope)*R2；与source112已测etf22_unweighted_logtrend25_priorclose精确数学同核。固定ETF池、0930/0940、top1只影响配置路径，缺ETF行情不称全策略复现；math未显式导入、record(round(Series))版本兼容问题保留。不是加权25公式或新簇。',
   ['g.m_days = 25','slope, intercept = np.polyfit(x, y, 1)','score = annualized_returns * r_squared'],['etf22_unweighted_logtrend25_priorclose'])
 p=find('quant/聚宽2025年精选','38*')
 save(p,'tested_atom_with_exact_weighted25_mixed_weight_semantics',
  '全86行：polyfit w=linspace(1,2,25)实际平方权重最小二乘，而R2残差仅乘一次w、中心为不加权mean(y)，原混合定义与source60 weighted_logtrend25_literal相同。无source60安全区间0<score<=5门槛，故只关联literal。4ETFtop1/0930/缺math未称已测策略。',
  ['weights = np.linspace(1, 2, n)','np.polyfit(x, y, 1, w=weights)','weights * (y - np.mean(y))**2'],['weighted_logtrend25_literal'])
 p=find('quant/量化策略/量化策略/ETF轮动策略2026','07*')
 save(p,'tested_atom_with_exact_trend34_missing_ETF1200_EPO_allocation',
  '全178行：prior34无权log趋势×R2且正score门槛映射source100已有两原子。EPO为选中最多3ETF的1200价点收益1199条complete-case样本协方差，.2向对角收缩，anchor逆方差归一。默认endogenous=True anchored分支不使用lambda10；gamma先计算后对负权重钳0再归一，全负时分母0无防御。每月首日0930，不是日频。缺ETF历史/实际组合，不能把原股票因子收益代表EPO配置表现；未用全窗均值拟合历史信号。',
  ['g.m_days = 34','count=1200','method = \'anchored\'','if endogenous:','epo = epo / np.sum(epo)'],['epo17_logtrend34_priorclose','epo17_positive34_qualified'])
 p=find('quant/2023年度精选策略','96.*')
 save(p,'market_scalar_missing_PITindustry_and_future_selection',
  '全116行仅宽度热图，行业/全市场高于MA20比例四舍五入整数，合计是行业比例直接求和无市值权重。最早p_count+20股票池却用末日行业映射，并dropna完整价格窗，历史宽度会随未来存在性/分类改变；缺PIT行业，未把市场常数广播成股票alpha。无经济股票排名或交易规则。',
  ['p_day=p_end_date',"pivot(index='code', columns='date', values='close').dropna(axis=0)",'s_mkt_sum = df_ratio.sum()'])
 for folder,pattern in [('quant/2024年度精选策略2','68.*'),('quant/量化策略/量化策略/小市值策略2026','07*')]:
  p=find(folder,pattern)
  save(p,'missing_PIT399101_circulatingMV_execution_not_newalpha',
   '全126行原排序circulating_market_cap升序前100，再去ST/涨跌停取前5。全市场去停牌列表只计算未用于实际候选；股票池399101历史成分、circMV正式口径和分钟成交缺失，不映射totalMV冒充原策略。已研究市值族但不是有精确全策略结果；周一0930现金/已持仓路径未测。',
   ['g.security_universe_index = "399101.XSHE"','valuation.circulating_market_cap.asc()','stock_num = 5'])
 p=find('quant/2024年度精选策略2','5.*')
 save(p,'missing_precomputed_RF_predictions_and_training_provenance',
  '全89行只pickle读取test_predict_300_q.pkl，按score降序取0-10%并月末换仓。未含训练、特征、标签或预测时间约束，源评分不能重建或验证未来泄漏；未加载不可信pickle/调用策略代码。相同股票order_target_value连续两次，不把标题低换手当新因子。',
  ["pickle.loads(read_file('test_predict_300_q.pkl'))",'df.sort_values(by=\'score\', ascending=False)','g.quantile = (0, 10)'])
 p=find('quant/聚宽2025年精选','27*')
 save(p,'missing_DQN_checkpoint_and_training_fixed_single_stock',
  '全137行6输入32hidden3actions网络，只提供7先前bar的6收益率输入与推理，没有tgt_net.pt权重或训练样本/标签/时点；固定北方国际000065，不能形成>=100股票截面。外层if action==2 else导致买入也打印持有，空仓卖时访问positions可能报错；未执行torch.load/read_file，未冒充重新训练原模型。',
  ["model_path1 = r'tgt_net.pt'",'model_t1 = DQN(6,3)',"initial_list ='000065.XSHE'",'attribute_history(initial_list, 7'])
 p=find('quant/2024年度精选策略1','59.*')
 save(p,'missing_circulating_sharecount_decile_and_execution',
  '全170行真正主动筛选是流通股数经过离散IQR去极值后分10桶，严格首两边界内，PB>0,ROE>0,ROA>.45后总市值最小10选5。股数是circulating_cap，不是circulating_market_cap或totalMV，不杜撰字段替换；splitrange步长floor(N/10)可能额外尾桶，N<10步0报错。20%仓位带只调持仓权重，不能凭此宣称低换手alpha。',
  ["circulating_cap_factor_list=valuation_df['circulating_cap'].tolist()",'valuation.circulating_cap < circulating_cap_factor_list[1]','indicator.roa>0.45','lm_value = 0.8 * position_size'])
 p=find('quant/2024年度精选策略2','3.*')
 save(p,'missing_vendor_sales_growth_regression_and_circMV',
  '全197行主动sales_growth降序前10%，slice边界用原stock_list长度而不是dropna后长度，再流通MV升序且EPS>0。sales_growth供应商5年趋势定义不可视为单季tr_yoy或简单收入同比，circMV亦非totalMV；250自然日次新/688/ST/涨跌停/周一交易需原数据，字段语义未验证不说精确原子已测。',
  ["'sales_growth', False, 0, 0.1",'int(p2*len(stock_list))','valuation.circulating_market_cap.asc()',"df['eps']>0"])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
