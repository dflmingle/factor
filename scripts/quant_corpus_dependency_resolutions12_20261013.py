"""Specific reviewed exclusions and strict complete executable AST reuse."""
import ast,hashlib,json
from collections import defaultdict
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_dependency_resolutions10_20261013 import StripDoc
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence12';eout.mkdir(exist_ok=True)
 def find(folder,pattern):return str(next((q.ROOT/folder).glob(pattern)).relative_to(q.ROOT))
 def save(path,state,decision,anchors,keys=(),extra=None):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 p=find('quant/2023年度精选策略','40.*')
 save(p,'tested_atom_with_exact_prior_smooth120_and_inverted_market_guard',
  '全140行：120raw-price slope降序，slope/intercept>.005且r_value>.9(不是注释R²>.8)，prior30high/C<=1.1，VMA7/VMA180<=1.5,C<=500。与source71两个原子同核但源取priorbar，本地旧71currentbar明确不同。未将二者宣称逐值相等。新增沪指MA10滞回.005，is_bull True时直接return禁止买入，实际熊市才买，注释反向；卖出在择时前执行。指数/2仓/订单缺失，未假造策略收益。',
  ['target_dict[stock] = slope','slope / intercept > 0.005 and r_value > 0.9','if g.is_bull:','close_data[-1] * (1 + g.threshold) <= ma_old'],['smooth_price_slope120_source','smooth_price_slope120_qualified'])
 p=find('quant/2021年度精选策略','56.*')
 save(p,'missing_actual_limit_price_and_industrypool_leader_execution',
  '全168行：prior11根数据只对昨日close==high_limit且low<high_limit的非一字板逐日倒查最长连板，再取全池最高板。要求max>3且上证指数3点价格OLS斜率round2>0，非原子独立股票alpha。上午11点前买1只，14:51后未封板卖，T+1closeable限制；缺实际涨停/行业证券定义/分钟盘口，不用固定10%收益伪造连板。',
  ['count = 11','g.low[security][-1] < g.high_limit[security][-1]','fit_linear(context,3)>0 and g.max_zt_days>3','m1 = round(float(m),2)'])
 p=find('quant/2024年度精选策略1','11.*')
 save(p,'missing_rawprice_circMV_and_limit_holdings_paths',
  '全219行：主动price_no_fq最低10%，另算qfq收盘最低10%但未用；EPS>0后流通MV最小前15，三停过滤再取10仓。不能把未用qfq分支称原active排名，也不能在正式totalMV结果混入raw/circMV。250自然日/688/北交/ST/日内涨停豁免需源数据；价格与市值旧风格，无新增独立因子证据。',
  ["'price_no_fq', True, 0, 0.1",'valuation.circulating_market_cap.asc()',"df['eps']>0",'final_list = list(df.code)[:15]'])
 p=find('quant/2024年度精选策略1','87.*')
 save(p,'missing_dividend_registration_history_not_one_year',
  '全102行：实际注册日期回看365*3天累计现金分红/当前totalMV，非注释近一年，不按3年平均但倍数不影响排名。PB>0和扣非ROE>0后股息top10%前100，三停再取30，每月首日1000；只补新仓不均衡已有仓位。缺公告/股权登记分红历史，不用利润分配/现金流替代。',
  ['time0 = time1 - datetime.timedelta(days=365*3)','finance.STK_XR_XD.a_registration_date',"DR['dividend_ratio'] = (DR['bonus_amount_rmb']/10000) / DR['market_cap']"])
 p=find('quant/聚宽2025年精选','4高*')
 save(p,'missing_three_year_dividends_with_exact_PEG_quality_gates',
  '全202行：三年登记日现金股息/totalMV前10%，然后0<=PE<=25、扣非ROE>3、收入增长>5、NET利润增长>11、严格.08<PEG<1.9；与序言0-20、净资产增长11%、上限2不同。金融查询无排序，保留原股息代码顺序可能受API返回影响。昨日价>=.98实际涨停列为开板检查，不等于真正涨停。缺现金分红/分钟成交，未复现整策略。',
  ['time1 - datetime.timedelta(days=365*3)','valuation.pe_ratio.between(0,25)','indicator.inc_net_profit_year_on_year>11','valuation.pe_ratio / indicator.inc_net_profit_year_on_year<1.9'])
 p=find('quant/2024年度精选策略1','55.*')
 save(p,'tested_atom_with_exact_lowpb_roa_quality_no_actual_size_sort',
  '全293行：实际PB<1、经营现金流入YTD>1e6、扣非利润>1e6、ROA>.15、NETprofitYoY>0后ROA降序，不是标题大市值排序。与source56 lowpb_roa_cash_profit_source资格原子同核，非source116 PB.98且营业利润增长。源API当天财务/公告时点仍代理，200自然日旧股、科创创业过滤、5仓/开板退出未测。邮件模块默认False且未执行/发信。',
  ['valuation.pb_ratio < 1','indicator.inc_net_profit_year_on_year > 0','indicator.roa.desc()','g.open_gmail = False'],['lowpb_roa_cash_profit_source'])
 p=find('quant/2024年度精选策略2','70.*')
 save(p,'missing_vendor_composite_growth_not_sales_growth',
  '全180行主动jqfactor=growth，尽管注释sales_growth；排名降序前10%边界按原initial_list长度，dropna后不改分母。EPS>0+流通MV升序，周一5仓。growth可能供应商复合成长，不视为单独tr_yoy或sales_growth，未作字段名猜测；外部库/历史股票/三停需求明确。',
  ["jqfactor = 'growth'",'int(0.1*len(initial_list))','valuation.circulating_market_cap.asc()'])
 p=find('quant/量化策略/量化策略/ETF轮动策略2026','08*')
 save(p,'tested_atom_with_literal_return12_and_vendor_MA10_asof_difference',
  '完整322行：moment_period13取14价[-13]产生RET12，均线实际10非注释13；after21:00信号包含当日完成收盘，对应source100 return12与MA10资格数学同核但原时点不同。混合ETF池local_stocks含海外/商品，map512760而pool515760不一致。13:30的60minuteMA20止损缺数据，消息/邮件函数未执行；不把日频股票原子说成单ETF策略已测。',
  ['previous_close = price_data[\'close\'][-g.moment_period]','g.ma_period =10',"run_daily(get_signal, time='21:00')"],['etf16_return12_offbyone','etf16_return12_above_ma10'])
 p=find('quant/聚宽2025年精选','69*')
 save(p,'tested_atom_with_weighted25_exact_safezone_and_cashETF',
  '全93行weighted polyfit w平方而R2仅一次w、非加权mean中心，与source60两个原子同核；严格score>0且<=5安全区，不合格返回511880货币ETF非零权空仓。4ETF/top1/0930、math缺导入、真实资金/收益未测试。',
  ['weights = np.linspace(1,2, n)',"(df['score'] > 0) & (df['score'] <= 5)",'rank_list=["511880.XSHG"]'],['weighted_logtrend25_literal','weighted_logtrend25_safezone'])
 # Exact full executable modules may reuse a precisely reviewed dependency
 # decision, too. Matching only title or a function body is forbidden here.
 coverage=pd.read_csv(OUT/'all_source_coverage.csv').fillna('');buckets=defaultdict(list)
 for r in coverage.to_dict('records'):
  p=q.ROOT/r['path']
  if p.suffix.lower() not in ['.py','.txt','.ipynb']:continue
  code=read_text(p).split('原文策略源码如下：',1)[-1].expandtabs(4)
  try:tree=ast.parse(code)
  except SyntaxError:continue
  normalized=ast.dump(StripDoc().visit(tree),include_attributes=False);buckets[hashlib.sha256(normalized.encode()).hexdigest()].append(r)
 resolved={r['path']:r for r in rows};aliases=[]
 for sha,group in buckets.items():
  prior=[r for r in group if r['actual_recipe_links'] or r['path'] in resolved]
  if not prior:continue
  canonical=prior[0];cr=resolved.get(canonical['path'])
  keys=[x.split(':',1)[1] for x in canonical['actual_recipe_links'].split(';') if x] or (cr['related_tested_keys'] if cr else [])
  for r in group:
   if r['path'] in resolved or r['actual_recipe_links'] or r['path']==canonical['path']:continue
   if r['sweep_state']!='reviewed_family_duplicate_or_variant_needs_recipe_trace':continue
   state='tested_atom_with_exact_complete_executable_AST' if keys else 'missing_dependencies_exact_complete_executable_AST_alias'
   decision='完整可执行模块AST相同，只去独立说明字符串，imports/参数/证券池/调度/订单全部保留。复用'+canonical['path']+'的精确原子/障碍证据；不称完整策略已测。'+(cr['decision'] if cr else '')
   save(r['path'],state,decision,[],keys,dict(equivalent_source=canonical['path'],full_executable_ast_sha256=sha,normalization='standalone string Expr only'))
   aliases.append(dict(path=r['path'],equivalent_source=canonical['path'],sha=sha,keys=keys))
 q.dump(eout/'new_exact_whole_AST_aliases.json',aliases)
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows),'NEW_MODULE_ALIASES',len(aliases))
if __name__=='__main__':main()
