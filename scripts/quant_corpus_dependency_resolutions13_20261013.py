"""Precise source blockers; broad coverage must not masquerade as full testing."""
import hashlib,json
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'
def main():
 rows=json.loads((OUT/'precise_source_resolutions.json').read_text());eout=OUT/'dependency_source_evidence13';eout.mkdir(exist_ok=True)
 def save(folder,pattern,state,decision,anchors,keys=(),extra=None):
  p=next((q.ROOT/folder).glob(pattern));path=str(p.relative_to(q.ROOT));s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=eout/(sha+'.source.txt');ep.write_text(s)
  rows[:]=[r for r in rows if r['path']!=path];rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 save('quant/2024年度精选策略1','100.*','no_stockalpha_vendor_Barra_attribution_not_strategy',
  '全832行复核，Barra10暴露归因/绘图，不是新个股alpha：000985而非注释CSI500；2023-07-08至14极短示例；nextdayOPEN标签而非正式close。is_susp[is_susp==1]二维mask保留全部index；风险getter忽略传date而用globalend_date。sqrtMV的W未使用，SLSQP实际MV权重且bounds±1；行业缺失借相邻股票；50池每10证券取1非因子选股。IC用pct_next而RLM用pct_，2020-02-03旧日会与2023区间冲突；t3未来资格筛选。缺平台不支持的Barra/PIT行业/指数，不造字段或执行notebook。',
  ["index = '000985.XSHG'",'stockList = is_susp[is_susp==1].index.tolist()',"end_date = '2020-02-03'","['pct_next']"])
 save('quant/2024年度精选策略1','53.*','existing_size_atom_execution_only_variant',
  '全63行：纯totalMV最小400，daily0930，排68/4/8/ST；按目标持仓金额差升序先卖后买。没有新因子核，已有SIZE控制原子。400仓、不同源股票资格、实际委托没有独立账本，不称整策略回测。',
  ['g.stock_num = 400','valuation.market_cap.asc()','reverse=False'],extra=dict(related_control='existing totalMV SIZE control'))
 save('quant/2024年度精选策略1','28.*','missing_registration_dividends_and_currentminute_volume_exits',
  '全261行：一年登记日累计现金分红/totalMV最高25%，允许−1<PEG<3（负PEG可入），PB-ROE计算但未作排序/筛选，totalMV<=100亿最小、当前价<9。月初买入但不卖不在choice的旧仓（卖出段注释）；昨日涨停开板以及14:30 VOLT>3*MAVOL10且未封板才卖。源码零滑点只是跑分假设。缺现金分红登记/PIT实际涨停/14:30未完成volume及vendorVOL，不用财务proxy造现金股息，不称原仓位路径已测。',
  ['datetime.timedelta(days=365)','False, 0, 0.25','valuation.market_cap<=100','VOLT[stock]>MAVOL10[stock]*3','valuation.pe_ratio / indicator.inc_net_profit_year_on_year>-1'])
 save('quant/2024年度精选策略2','39.*','missing_positive_vendor_turnover_volatility_and_too_small_canonical_support',
  '全151行：PEG正值最低10% -> EBIT正值最低25% -> turnover_volatility正值最低50% -> circMV小5。不同source56不要求正数的前两腿，不能复用其信号当exact。切片每腿以输入池原长度floor，不按dropna长度重算。5456全A即使零缺失，最多floor(floor(floor(5456*.1)*.25)*.5)=68只，少于正式100最低有效股票，无法给正式五年观察。供应商相对换手波动定义与circMV又缺字节级对标，不随意用STD21替代，原小5策略不在全A十组代理内测试。',
  ["df = df[df['score']>0]","'PEG', True, 0.1","'EBIT', True, 0.25","'turnover_volatility', True, 0.5"],extra=dict(max_possible_canonical_support=68,minimum_required_support=100))
 save('quant/2024年度精选策略1','71.*','missing_vendor_netprofit_growth_and_signed_EBIT_sequential_filter',
  '全293行：vendor net_profit_growth_rate最高10%，EBIT最低40%，roe_ttm分位1仍dropna去无ROE值而非完全不起作用；helper正值筛被注释，负EBIT可入。EPS>0后circMV最小，周调10且20日持仓涨停冷却。不同PEG/EBITsource56：第一腿是vendor净利润增长，不把netprofit_yoy直接称等价，roe_ttm缺失筛不能省略，供应商字段/PIT实际涨停/分钟和circMV正式比较缺口保留。',
  ["'net_profit_growth_rate',0.1,False","'EBIT',0.4, True","'roe_ttm',1,False","#df = df[df['score']>0]","df = df[df['eps']>0]"])
 q.dump(OUT/'precise_source_resolutions.json',rows)
 pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
 q.dump(OUT/'precise_resolution_state.json',dict(records=len(rows),source_hashes_unchanged=True,all_corpus_complete=False));print('PRECISE_SOURCE_RESOLUTIONS',len(rows))
if __name__=='__main__':main()
