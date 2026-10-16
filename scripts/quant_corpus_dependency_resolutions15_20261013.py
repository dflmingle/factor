"""Record actual newly reviewed kernels and remaining strategy-layer gaps."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence15';eout.mkdir(exist_ok=True)
 def save(folder,pattern,state,decision,anchors,keys=(),extra=None):
  p=next((q.ROOT/folder).glob(pattern));path=str(p.relative_to(q.ROOT));s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 save('quant/2024年度精选策略2','43.*','tested_atom_with_all_six_normalizedslope_notebook_horizons',
  '全263行4ETF笔记本：已补测source142/143全部3/5/10/20/30/60价点首价归一斜率，当前已完成bar，非111priorbar时点等价。全stockday pooledPearson及前100日4ETFIC不是正式逐日Spearman，缺ETF原样本，方向HIGH提前冻结，不因图文挑方向或最佳窗口；不称完整策略/原ETF统计已复现。',
  ['for i in [3,5,10,20,30,60]:','x/x[0]'],[f'notebook43_normalized_slope{n}_current' for n in [3,5,10,20,30,60]],dict(partial_kernel_only=False,untested_notebook_windows=[]))
 save('quant/2024年度精选策略1','2.*','tested_atom_with_alternative_logweights_and_missing_minute_financial_qualifications',
  '全292行：weights[1,1,1.6,.8,2]非source32[2,1,1,4,4]；总MV/circMV/当前分钟价/1200分钟volume/当前比前60daily首价。PB>0/inc_return>0/营收同比>0/净利同比>0最小totalMV100，周调50。145仅新权重量价去size以及显式totalMV双替代诊断；缺minute/inc_return字节等价/涨跌停与完整50持仓路径，不称原式全回测。',
  ['g.weights = [1.0, 1.0, 1.6, 0.8, 2.0]','indicator.inc_return > 0',"attribute_history(stock, 1200, '1m', 'volume')"],['lowlog2_sizefree_weights1682','lowlog2_totalmv_weights1682_proxy'])
 save('quant/2024年度精选策略1','35.*','missing_PIT_hotindustry_and_vendor_fiveyear_growth_MSweights',
  '全348行：活跃行业预过滤是10日平均整数百分比(C>MA20)最高24个申万一级行业，成员asof昨天；SG vendor5年salesgrowth最高10%且EPS>0；MS=.1营业增长+.35利润总额增长+.15净利增长+.4五年earningsgrowth最高10%且EPS>0；PEG低20%->换手波动低50%不要求EPS>0。每腿circMV小5并集再小9，10日持仓涨停冷却。缺PIT行业/5年供应商口径/circMV/分钟涨停，不能沿用旧MS .35/.05权重当等价。',
  ['number=24','0.1*df[','0.35*df[','0.15*df[','0.4*df[',"'PEG', True, 0, 0.2"])
 save('quant/聚宽2025年精选','36快*','tested_atom_with_literal_motion19_raiser48_and_RSRS_slope8',
  '全312行：20点bias90首值归一OLS*10000，持仓score*1.04；score变化>19或ret>4.8%SELL。RSRS18/600 z*R2，8点斜率<0且RSRS>0优先SELL，再RSRS>−.68BUY；145/146已测两个guard和joint。GLOBALHS300/4ETF改个股均为proxy；初始化skipped斜率滚动seed不同，60minuteMA20×1.005盘中止损缺失。get_rank返回[code,score,adr]直接传订单循环缺陷，不修好后冒称原策略。',
  ['g.Motion_1diff = 19','g.raiser_thr = 4.8','if(rsrs_slope< 0 and rsrs_score >0):','return rank[0]'],['motion36_bias90_20_nonaccelerating','motion36_rsrs_slope8_nonsell','motion36_bias_joint_rsrs_motion'])
 save('quant/2024年度精选策略2','18.*','tested_atom_with_reset20_Kalman_RTS_not_wholehistory_smoothing',
  '全189行：每次取20priorclose首价归一再Kalman.smooth，R=.15/Q=.1/P0=.15/mean0首值；147以独立RTS和Gaussianprecision两方法核对，后向平滑仅在截至信号的历史20窗，没有全历史未来泄漏。RSRS>=−.7非SELL（KEEP也调仓）联合已测。ETF/全局HS300/订单[code,score]迭代错误/亏90%才止损未称整策略。旧notes“20日收益率”现更正为20价点归一。',
  ['pred_data = kalman_filter(np.array(data.close),0.15)','pre, cov = kf.smooth(observations)','transition_covariance = 0.1'],['kalman18_reset20_normalized_slope','kalman18_reset20_rsrs_nonsell'])
 save('quant/2024年度精选策略1','42.*','tested_atom_with_WRpriority_RSRS_branch_guard_missing_ETF_index_minute_paths',
  '全316行：bias90/20和motion19/4.8同核145；新guard147顺序WR14及21>=97强制BUY优先、RSRS斜率负且分正SELL、price8斜率负且RSRS斜率正且RSRS<−.43SELL、price8斜率>12且RSRS斜率正BUY、最后RSRS>−.68。12是指数绝对价点不能归一偷调，个股适配明确proxy；WR供应商算法未字节对标。hold1.04/指数/60min/消息/订单缺陷不执行，非原策略复现。',
  ['g.score_fall_thr = -0.43','g.idex_slope_raise_thr = 12','if WR1[g.ref_stock]>=97 and WR2[g.ref_stock] >=97:'],['guard42_WR_RSRS_slope8_nonsell','motion36_bias90_20_nonaccelerating'])
 save('quant/2024年度精选策略1','79.*','missing_vendor_default_technicals_and_under100_source_SVR_pool',
  '全257行：每月circMV0..30亿最小100，再主板/ST/listing375过滤所以往往<100；SVR()拟合当期totalMV，以PE/PB/PS/ROA/YTDtotalRevenue及默认DMA/HSL/MA/BIAS/MTM作特征，技术values按字典位置错接风险；fillna0。DataFrame sort_index(by=...)失效且list(DataFrame)返回列名而非股票，源残差选股运行缺陷。源码未给技术默认period/vendor定义，不能假默认或用21/60补成原式；<100也不合正式十组100底线。另April5..30现金退出，不等价旧signlog或booleanSVR。',
  ['valuation.circulating_market_cap.between(0,30)','svr = SVR()',"factor.sort_index(by='market_cap'","list(DMA(dataset.code,  yesterday)[0].values())"])
 save('quant/2024年度精选策略1','8.*','tested_atom_with_retainedps_leg_missing_8year_ROA_Barra_and_union_execution',
  '全274行：roa_ttm_8y低10%/retainedPS低10%/Barra non_linear_size低10%，每腿EPS>0/circMV小5并集再小10；250/125自然日新股和20日持仓涨停冷却。低留存source140已测，membership144同fullA支持诊断显示较SIZE五年−5.50pp近期−6.28pp，不支持强新资格价值。reportedROA2018起不能补2021前8年，Barra不造cubic；这两腿及union未复现。',
  ["'roa_ttm_8y', True, 0, 0.1","'retained_earnings_per_share', True, 0, 0.1","'non_linear_size', True, 0, 0.1"],['union37_low_reported_retainedps','union37_low_retainedps_positiveEPS','union37_bottom10_retainedps_small_partial','membership144_lowretained_positiveEPS_priority'])
 for r in rows:
  if r['path'].endswith('/100.全市场归因.txt'):r['resolution']='no_economic_ranking_vendor_Barra_attribution'
  if r['path'].endswith('/53.微盘400每日再平衡.txt'):r['resolution']='tested_atom_with_existing_SIZE_execution_only_variant';r['related_tested_keys']=['membership144_size_control']
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
