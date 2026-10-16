"""Full-read final family queue and precise new-batch provenance."""
import ast,hashlib
from quant_corpus_resolution_store_20261013 import Store,q,read_text

def main():
 s=Store(18);find=s.find;save=s.save
 save(find('quant/2023年度精选策略','85.*'),'tested_atom_with_multima_gate_missing_actual_limit_execution',
  '全298行：priorC>MA5>MA10>MA20>MA60门与120原子同数学，但85实际代码序取前3，不含120小市值排序，不能声称原因子逐值相同；source85仅高limit==C资格后均线多头，没有额外经济排序。行业union/ST/IPO30、09:33买、09:40现价较开盘-.03、成本/昨收-.04、+.60stopwin及T+1路径缺失，不因简单多头原子称完整复现。',
  ['pre_close_price>ma_5[stock]','g.max_number_stock=3'],['leader02_multima_lowcap_partial'],dict(shared_mathematical_gate_only=True))
 p=find('quant/2023年度精选策略','90.*');base=find('quant/2023年度精选策略','18.*')
 def cls(path):return [n for n in ast.parse(read_text(q.ROOT/path)).body if isinstance(n,ast.ClassDef) and n.name=='F13_Score'][0]
 a,b=[ast.dump(cls(x),include_attributes=False) for x in [p,base]];assert a==b
 save(p,'tested_atom_with_exact_F13class_missing_intraday_T_overlay',
  '全469行：F13_Score整个类AST与2023/18精确相同，六sign财务及错误括号ROA2结构映射32正确proxy，不是旧18错误实现。source>.4实际f>4最高200交正PB去极值标准化sw_l1中性低20%最高200，行业金融剔除/PIT行业缺失。Rbreaker用priorHLCpivot、今9:31起maxH/minL、成交订单状态反复买回及持仓T+1，不能以日线范围猜真实路径；未新增FFScore簇。',
  ['g.sel_fields','f[f > 4]','sSetup = pivot + (high - low)'],['ffscore6_literal_repaired'],dict(shared_F13class_ast_sha256=hashlib.sha256(a.encode()).hexdigest()))
 for folder,pat in [('quant/聚宽2025年精选','1首*'),('quant/聚宽2025年精选','68wy*')]:
  save(find(folder,pat),'tested_atom_with_range60_openband_missing_firstlimit_and_intraday',
   '完整逐行读取：prior涨停且不连板10，range60<=.5，当前open/priorC .96..97（含边界），数学119lastvalid区间+低开带已测试；IPO250/ST/pause/actualhigh_limit和空仓状态缺失。1号09:30与68号09:26时点不同，68加prepare09:15/message和slippage.003，不是全module同AST，但同日线原子；68休眠低limit过滤及14:55封板函数未活动，不执行发送信息。',
   ["get_relative_position_df(stock_list, date, 60)","0.96 <= df['open_pct']"],['firstboard72_lowrange60_lastvalid','firstboard72_openband_range60_partial'])
 save(find('quant/聚宽2025年精选','2连*'),'tested_atom_with_VOL5_missing_highest_chain20_selection',
  '全399行：20日最高连续涨停M内VOL5升序，119prior5日低换手数学proxy已测；原目标[:10-持仓]，开盘排板、2交易日或盈利且非上下limit退出。极端一字板最少/热点/情绪周期代码全独立字符串休眠，不能当新候选；真实链数/竞价/分钟/T+1缺失，没有新独立簇。',
  ["g.jqfactor = 'VOL5'","g.sort = True","get_continue_count_df(hl_list, date, 20)"],['leader88_lowturn5_priorclose'])
 save(find('quant/聚宽2025年精选','57韶*'),'tested_atom_with_RET4_volume20ceil_missing_201auction',
  '全487行：首次初始化仅after_code_changed；source20唯一涨停且prior封板，排一字和近60分钟弱封板，active L是5价4间隔涨幅<10%，V<=5mean20V（含lastV）为upperceil。159部分RET4量资格已核验双窗口；竞价.945<price/priorC<.985、半账户及14:55可卖非涨停退出缺失。120day.9持仓volume inactive，+.05profit handle_data字符串休眠，未来stock_analysis调用注释，未执行未来分析。',
  ['g.volume_control = 2','g.sell_mode = 0',"change_5 = df_price['close'][-1]/df_price['close'][-5]"],['series57_RET4_volume20_partial'])
 for pat,keys,note in [
  ('50分享*',['smallstep50_lowreturn15_nearhigh60_margin','smallstep50_size25_dailygate_priority'],'全561行：circMV<25，实际近300曾涨停（纠正旧摘要排除错误）；30日没有C>.95high_limit；15日abs(close/preclose)每日<=2.5%不是H/L振幅，priorC==MAX15C且>.92MAX60H。158continuous及totalMV资格明确NEW部分已测。currentprice在.945..975high_limit、15minute尖峰/10minute放量卖缺失；bigvolume平均实际13条[-15:-2]，6天+<5%或利润15%路径；-6%check_lose注释，do_buy未定义s等执行缺陷保留。'),
  ('55怎么*',['first55_nearhigh_ranges300_50_10_margin'],'全188行：前日非板，300/50最高C<1.2preC，10最高C<1.1preC，300幅<2、10幅<=.5。158NEW连续余量已测；50上限在同序300约束下数学冗余但保留。circMV<150/IPO30/ST/board、1minute连续两价首次封板、match_by_signal强制撮合及十项持仓exit路径缺失，不能认证原20仓策略收益。')]:
  save(find('quant/聚宽2025年精选',pat),'tested_atom_with_daily_consolidation_missing_limits_minute',note,keys=keys)
 save(find('quant/聚宽2025年精选','96首*'),'tested_atom_with_exact_volume3_prior15_missing_Longhu_concepts',
  '全280行：Longhu net_value>0,buy_rate>4排序去重，概念至少两票但HY_sum第二循环误用上轮stock；18日1或2封板、last3均量/先15均量严格4..6，与摘要20日2倍不同。159NEWband核验已测；turn<50后大circMV降序，开盘>=1.04priorhigh_limit非今limit，1仓，每天8次只要非limit且closeable便卖。真实龙虎榜/概念/PIT流通/limit/分钟缺失，未猜净流数据。',
  ['days=18','avg_volume_20_days*4 <avg_volume_3_days < avg_volume_20_days*6'],['longhu96_volume3_prior15_band_margin'])
 save(find('quant/聚宽2025年精选','59追*'),'tested_atom_with_pressure100_105V_VWAP_money_missing_firstlimitauction',
  '全439行：先前两日H曾触limit剔除的昨日封板；priorVWAP/C>=.96、money7..19亿、totalMV>=70而circMV<=520，turn28注释；左压取100H跳过[-2]反序最近>=lastH，fallback100+5另取105V，不是7号101条截断版本。160两个新部分已测且currency千元转元/volume手转股核验。auction[0]量3%、open严格0..6%与原9:26，11:25盈利或14:50退出；完整撮合/筹码不可用，不执行写文件或发送信息。',
  ['count=100','zyts = zyts_0 + 5','avg_price_increase_value < 96'],['chase59_pressure100_external105_volume_ratio','chase59_pressure_vwap_money_daily_margin'])
 save(find('quant/量化策略/量化策略/首板回调买入策略2026','实10*'),'tested_atom_with_three_auction_modes_corrected_dailyweakpart',
  '全508行：实际高开VWAP*1.1-1>=.07，注释<7%反向错误；amount5.5..20亿，总值>=70流通<=520，101H左压clamped101volume同114，竞价3%和open1..1.06。低开range60<=.5 money>=1亿竞价.955..97（未把.955版本冒称119.96同式）。弱转强4closes3intervals<=.28,body>=-.05,VWAP>=.96,3..19亿及size；160千元转元修正版部分已测，159原单位错误已作废。真实first/brokenboard与竞价、MA5现价出场及初始化after_code_changed缺失，原union未测，低开amount带单独仍未测试。',
  ['avg_price_increase_value < 0.07','history_data = attribute_history(s, 60','100'],['auction10_weak3ret_body_amount_yuan_margin','firstboard7_leftpressure101_volume_ratio'],dict(untested_partial_recipes=['sbdk money1e8/open.955..97 joint']))
 save(find('quant/聚宽2025年精选','65搭*'),'tested_atom_with_five_log_fixedbranches_missing_stylefinancialgate',
  '全约500行：unitweights[1,1,1,1,1],currentTurn/price/prior21Vsum/prior55firstreturn/circMV logarithms，156去size/固定小盘/固定大盘三分支已测；quarterly叙述错误，实际每第13次my_select调用依144barlow233trend最佳index翻sizeweight，daily3sell+Wednesday3buy，未重置positive显式，缺指数state不猜路径。PB>1、PE0..200、revYoy>30、profitYoy>50,vendorOCF/opprofit>10和OHLCZ50lotallocation未复现，fixedbranches不是完整模型。',
  ['g.j = 12','g.w = 12'],['lowlog65_turn_price_V21_return55_sizefree','lowlog65_small_totalMV_fixedregime','lowlog65_large_totalMV_fixedregime'])
 save(find('quant/聚宽2025年精选','6国*'),'tested_atom_with_positive_YTD_qualification_sameSIZEcontrol',
  '全358行：实际10..1e8亿非上限100；parentNI>0,totalNI>0,operatingrevenue>1亿最新YTD，157fullA资格优先已核验且同SIZE双窗口下降；audit=False，即True得到df_audit也未接返回。price<=50只新hold；399101绝对MA10差门200/-200/-500控制3..6仓，min3使newnum0unreachable；Jan/Apr511880、cost9%及abs市场5%stop不是新财务因子，原PIT成分/分钟/限制/T+1未测。',
  ['g.filter_audit = False','income.net_profit > 0'],['guojiu6_positiveYTDNI_revenue_size_priority'])
 aliases=s.aliases();s.commit();print('NEWASTALIASES',len(aliases))
if __name__=='__main__':main()
