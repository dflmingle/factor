"""Further precisely read dependencies plus strict full-executable AST aliases."""
import ast,hashlib,json
from collections import defaultdict
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_dependency_resolutions10_20261013 import StripDoc
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence14';eout.mkdir(exist_ok=True)
 def save(path,state,decision,anchors=(),keys=(),extra=None):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 def find(folder,pat):return str(next((q.ROOT/folder).glob(pat)).relative_to(q.ROOT))
 save(find('quant/2021年度精选策略','52.*'),'missing_northbound_top_active_netflow_not_full_stockflows',
  '全145行：原nday2取previous_date减2自然日到当日的交易日（可达3日，非固定2交易日），STK_EL_TOP_ACTIVATE活跃榜买卖净额累加，排link_id310003/310004，再除1e8和流通MV，持4/60交易日。是活跃榜样本净额，非所有北向持仓变化；缺原表及PIT范围，不用volume/amount估北向，不以totalMV冒充circMV。分钟涨停豁免和订单未测。',
  ['g.nday=2','startdate=date-datetime.timedelta(g.nday)','finance.STK_EL_TOP_ACTIVATE',"df_cap['rate']=(df_cap['net']/100000000/df_cap['circulating_market_cap'])"])
 save(find('quant/2021年度精选策略','58.*'),'non_stockalpha_missing_minute_IF_calendar_spread',
  '全166行：IF季度跨期套利，近减远300分钟差价，90分位正时乘1.1、负时乘.9上穿开近空远多，差价<30分位平。tt=hour+minute/60>=9.55实际09:33非09:55；margin分期20/15/10%，仓位cash/(两合约价)/300/margin/1.2，1.2意味着保留约1/6现金非文字20%。实际合约季换硬编码，缺分钟期货/展期/保证金/多空成交，不属于平台股票横截面，不造股票排名。',
  ['gap=IF1-IF2','tt = ho+mi/60','if tt>=9.55:','gap.quantile(0.9)*0.9','ss=cash/(IF1_now+IF2_now)/300/g.futures_margin_rate/1.2'])
 save(find('quant/2024年度精选策略2','6.*'),'tested_RSRS_guard_with_missing_vendor_netprofitgrowth_PEG_circMV',
  '全248行：net_profit_growth_rate正值高10%->PEG正值低50%->circMV小4，每日0945非原周调，EBIT/turnover腿注释。RSRS18/600仅z*R2，MA30/gap5取而未用；BUY和KEEP都adjust，SELL清。已测etf7_rsrs_nonsell_no_ma数学同核，不乘beta，rollingseed代理保留。vendor净利增长不能随意替netprofit_yoy；完整财务选股/源分钟/持仓未测。',
  ["'net_profit_growth_rate', False, 0.1","'PEG', True, 0.5",'rsrs_score = get_zscore(g.slope_series[-g.M:]) * r2',"elif g.timing_signal == 'BUY' or g.timing_signal == 'KEEP':"],['etf7_rsrs_nonsell_no_ma'])
 save(find('quant/2024年度精选策略2','43.*'),'tested_normalized20slope_atom_ETF_notebook_statistics_not_newalpha',
  '全263行4ETF2013..2021笔记本：100*OLS_N(C/Cfirst)六个窗口3/5/10/20/30/60；source111 normalized20 exact正倍数原子已测，只是该20bar分支源码当前bar与111priorbar时点不同明确保留，不称逐值等价。全stockday pooledPearson不是正式逐日Spearman；日IC只前100天且4ETF，最强20斜率选1做跨日相关并非IC胜率。future shift(-N)仅label可用，不可输入因子。6窗口不因图文最佳方向倒推新alpha或未跑窗口全称已测试，缺ETF行情/原统计样本。',
  ['for i in [3,5,10,20,30,60]:','x/x[0]','cdata.shift(-i)/cdata','for date in cdata.index[:100]:'],['etf7_linear20_firstprice_slope'],dict(partial_kernel_only=True,untested_notebook_windows=[3,5,10,30,60]))
 # Correct the source directory reference in older prose without altering its
 # frozen factor results. The exact formula/key was already correct.
 for r in rows:
  if '与source112已测etf22_unweighted_logtrend25_priorclose' in r['decision']:
   r['decision']=r['decision'].replace('与source112已测etf22_unweighted_logtrend25_priorclose','与source109已测etf22_unweighted_logtrend25_priorclose');r['prose_directory_correction']='112->109; formula/key unchanged'
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
  canonical=prior[0];cr=resolved.get(canonical['path']);keys=[x.split(':',1)[1] for x in canonical['actual_recipe_links'].split(';') if x] or(cr['related_tested_keys'] if cr else [])
  for r in group:
   if r['path'] in resolved or r['actual_recipe_links'] or r['path']==canonical['path']:continue
   if r['sweep_state']!='reviewed_family_duplicate_or_variant_needs_recipe_trace':continue
   save(r['path'],'tested_atom_with_exact_complete_executable_AST' if keys else 'missing_dependencies_exact_complete_executable_AST_alias',
    '完整可执行AST相同，只去独立字符串，imports/全参数/池/调度/委托保留；复用'+canonical['path']+'精确原子或依赖障碍。不称完整策略测试。'+(cr['decision'] if cr else ''),keys=keys,extra=dict(equivalent_source=canonical['path'],full_executable_ast_sha256=sha,normalization='standalone string Expr only'))
   aliases.append(dict(path=r['path'],canonical=canonical['path'],sha=sha,keys=keys))
 q.dump(eout/'new_exact_whole_AST_aliases.json',aliases);q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows),'NEW_MODULE_ALIASES',len(aliases))
if __name__=='__main__':main()
