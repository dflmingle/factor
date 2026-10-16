"""Literal call-path resolutions and strict whole executable AST aliases.

The alias check removes only standalone strings. Imports, symbol universes,
execution calls, global parameters and complete function bodies remain.
"""
import ast,hashlib,json
from collections import defaultdict
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
class StripDoc(ast.NodeTransformer):
 def visit_Expr(self,n):
  if isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):return None
  return self.generic_visit(n)
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence10';eout.mkdir(exist_ok=True)
 def save(path,state,decision,anchors,keys=(),extra=None):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 def early(pre):return str(next((q.ROOT/'quant/2020年度精选策略').glob(pre+'*')).relative_to(q.ROOT))
 save(early('18 '),'tested_atom_with_priorbar_timing_and_original_position_bugs',
  '全源码核对：价格离MA20差的60点样本STD Z与detrended_z60_low数学同轴，但原退出门槛>=1/前日时间与连续反转排序不同；只作为原子追溯，不声称原退出组合已测。买入循环引用上一卖出循环最后股票002415的close_data1来约束全部5只；holding_high_price全股票共享，更新新高后嵌套price<.93*新高永不可达；实际成本止损7%而注释15%。MACD使用current_dt/previous_date开盘供应商时点未知。5固定股/子账户持仓卖出/逐仓砍半/订单均未复现。',
  ['g.zscore_window = 60','g.ma_window = 20','ma_n1 = close_data1','price < g.holding_high_price * 0.93'],['detrended_z60_low'])
 save(early('29 '),'missing_external_KD9_seed_and_asof_fixed_single_stock',
  '完整源码：000016.XSHE是深康佳A股票，不是上证50索引后缀笔误。K1/D1调用当前开盘日期，K2/D2调用previous_date减1自然日：周一比较上周四、周二比较上周五，不能替成统一lag1。N9/M1=M2=3供应商KD种子及中国SMA/TA-Lib平滑未证实；缺datetime导入亦记录。固定单股不能做>=100股票截面，未杜撰KD复现或新簇；可待平台算子语义再做明确代理。',
  ["g.security = '000016.XSHE'",'N=9, M1=3, M2=3','context.previous_date-datetime.timedelta(days=1)','K1>D1 and K2 <=D2'])
 save(early('55 '),'fixed_two_stock_pair_missing_ETF_and_margin_execution',
  '全源码实际两ETF510220/510500，不是标题中两股票；120价点差price2-1*price1的populationSTD Z，系数固定1非滚动协整回归。进入严格+/-2.1，中带含+/-1.95，间隙返回None而非持仓重置。marginsec_open可能每bar重复100000借券、第二腿总资金，平仓又固定100000；资金/券源不可用。缺ETF行情和融券条件，不将对全A市场拟合残差称原配对因子。',
  ["g.security1 = '510220.XSHG'",'g.regression_ratio = 1','g.test_days = 120','if -1.95<= z_score <= 1.95','marginsec_open(g.security2, 100000'])
 save(early('25 '),'tested_atom_with_pure_size_and_everybar_execution_difference',
  '全源码只有totalMV升序最小10，不含新经济信号；SZ/SH综指成分代理全A不同历史证券定义。g.days每every_bar递增，所以分钟运行周期10是10bar不是10交易日。原先set差集随后被原buylist停牌过滤覆盖，使已持仓也可重复order_value；原现金按有效买单数分配。SIZE原子已测，完整10股订单路径不等于十组平台回测。',
  ['g.days += 1','g.days % g.period != 1','valuation.market_cap.asc()','buy_list = [stock for stock in buylist if not current_data[stock].paused]'],['size_only'])
 p='quant/2023年度精选策略/81.拥挤率指标-择时大盘顶底-Clone1-第二版.txt'
 save(p,'market_scalar_crowding_inclusive_cutoff_not_stock_alpha',
  '全部201行：每个日期按成交额降序、money>=位置floor(N*.05)阈值，所以通常纳入floor(N*.05)+1且含全部并列，不是精确5%或早期注释[:N/20]。round(100*比率,1)画1000天指标，不存在交易门槛或股票排序。get_all_securities(date=date_now)冻结末日股票池回看有存续偏差；禁止把此市场常数广播全A报alpha。',
  ['all_stocks = list(get_all_securities(date=date_now).index)',"df = df[df['money'] >= df.iloc[int(len(df) * 0.05)]['money']]",'round(crowd_rate*100,1)'])
 p='quant/2023年度精选策略/27.从相关系数角度探讨etf轮动的可行性.txt'
 save(p,'tested_atom_with_exact_momentum29_no_active_correlation',
  '全205行实际log价29点趋势250年化乘R2，数学映射已测etf4_logtrend29_r2_priorclose；标题相关系数不产生任何活跃corr排序。g.stock_pool三ETFtop1，止损实际-80%近似无效，缺math显式导入。股票全A只是已测原子适配；不说ETF配置/成交/退出完整复现。',
  ['g.momentum_day = 29','annualized_returns = math.pow(math.exp(slope), 250) - 1','score = annualized_returns * r_squared','if ret <=-80'],['etf4_logtrend29_r2_priorclose'])
 p='quant/2021年度精选策略/27.基于RSRS的趋势交易与网格交易相结合的尝试.txt'
 save(p,'tested_atom_with_RSRS1100_priorbar_and_grid_dependency',
  '全源码RSRS18/1100右偏z*beta*R2数学与rsrs18_rightdev1100已测同轴，但源码2005暖机且t-1，与本地2018暖机/currentbar差异明确，初段完整五年不可恢复。首日beta/r2留0使首评分0；无效H/L填0是源码异常处理，未用于修补本地正式数据。实际向上2ATR网格分3笔追涨、建仓时ATR20冻结、每档一次；订单判断误查函数order而不是orders，缺minutefill/state。不把静态价格余量说成原动态网格。',
  ['g.M = 1100','g.NATRstop = 2','zscore_rightdev= zscore*beta*r2','if order is None','g.Stop_price=g.buy_price+g.NATRstop*g.ATR_buy'],['rsrs18_rightdev1100'])
 p='quant/量化策略/量化策略/ETF轮动策略2026/09ETF动量轮动MA乖离择时-25年62.txt'
 save(p,'tested_atom_with_exact_momentum20_and_bias60_10_z30',
  '全170行核对：真实活跃池34主题ETF，注释4ETF池g.stock_pool2未用。get_rank原线性价/C_first20 slope映射etf7_linear20_firstprice_slope；bias60->MA10->populationZ30映射smoothed_bias60_10_z30，前日时间差保留。get_rank返回[code,score]直接传adjust_position，for stock可把score当代码；持仓10%成本止损和14:50执行不修饰为成功策略。',
  ['score = np.polyfit(np.arange(len(data)),data.close/data.close[0],1)[0]','data.bias.rolling(10).mean()','score = get_zscore(data.biasma[-30:])','return rank[0]'],['etf7_linear20_firstprice_slope','smoothed_bias60_10_z30'])
 # Strict complete AST comparison, unlike presentation/core function matching.
 coverage=pd.read_csv(OUT/'all_source_coverage.csv').fillna('');buckets=defaultdict(list)
 for r in coverage.to_dict('records'):
  p=q.ROOT/r['path']
  if p.suffix.lower() not in ['.py','.txt','.ipynb']:continue
  code=read_text(p).split('原文策略源码如下：',1)[-1].expandtabs(4)
  try:tree=ast.parse(code)
  except SyntaxError:continue
  norm=ast.dump(StripDoc().visit(tree),include_attributes=False);buckets[hashlib.sha256(norm.encode()).hexdigest()].append(r)
 aliases=[]
 for sha,group in buckets.items():
  prior=[r for r in group if r['actual_recipe_links']]
  if not prior:continue
  for r in group:
   if r['sweep_state']!='reviewed_family_duplicate_or_variant_needs_recipe_trace':continue
   canonical=prior[0];keys=[x.split(':',1)[1] for x in canonical['actual_recipe_links'].split(';')]
   save(r['path'],'tested_atom_with_exact_whole_executable_AST_alias',
    '完整模块可执行AST相同，仅去独立字符串说明；全局参数、固定标的、imports、运行时间、函数和订单调用均保留比较。对应'+canonical['path']+'已有原子产物可复用；未测策略层、缺字段及代理限制继承，不称全部策略回测或新因子。',[],keys,
    dict(equivalent_source=canonical['path'],full_executable_ast_sha256=sha,normalization='remove standalone string Expr only; no operational/call/parameter removals'))
   aliases.append(dict(path=r['path'],equivalent_source=canonical['path'],full_executable_ast_sha256=sha,keys=keys))
 q.dump(eout/'exact_whole_AST_aliases.json',aliases)
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows),'EXACT_MODULE_ALIASES',len(aliases))
if __name__=='__main__':main()
