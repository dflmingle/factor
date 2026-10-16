from quant_corpus_semantic_review_20261012 import add_authored
E = {
 '50.':('ETF池按20日动量和RSRS18/600 zscore择时，加入斜率zscore变化与阈值改写。','ETF momentum + RSRS adaptive timing。','ETF OHLCV、RSRS历史斜率。','etf_rsrs_duplicate','与既有ETF/RSRS路线重复。'),
 '51.':('按月计算申万一级行业收益，中心化为行业超额收益，用短期3月与中期6月滚动相关/反转系数预测下月行业超额收益，买入预测最差的5个行业；行业无ETF时在行业内取PB与1/ROE秩和最低的10只价值股。','industry short/mid-horizon reversal: correlation of current industry excess return with prior returns, prediction=(correlation coefficient×recent mean) averaged over 3m/6m; industry PB+1/ROE value sleeve。','历史行业成分、行业价格、PB、ROE、ETF映射；原始行业收益用成员收盘价简单求和而非市值加权，需修正。','industry_reversal_value_candidate','这是明确的行业反转轴，且与行业内PB×ROE价值腿结合，可能补充现有股票截面池；但原实现行业收益构造偏差较大，先记录候选，待按PIT行业成分重建。'),
 '52.':('统计全A股票收盘高于20日均线的比例，按日展示市场宽度和行业宽度。','market breadth = mean(I(CLOSE>MA20)) across all stocks and by industry。','全A日线收盘、行业历史成分。','market_breadth_macro_pending','市场宽度是已有行业广度/市场状态轴的简化版本，作为择时诊断，不直接纳入截面因子。'),
 '54.':('取sales_growth最低10%后按流通市值选10只，再统计各股10日成交量超过自身10日均值1.3倍的天数，按该次数降序选5只，并带指数均线空仓开关。','low sales_growth × count_{10d}(volume / mean_volume_10 > 1.3) × small cap。','sales_growth、日线成交量、指数短均线；成交量计数可本地重建。','growth_volume_burst_duplicate','仍是小市值成长轴叠加量能爆发计数，与已有成长/量价簇重复；不新增候选。'),
 '55.':('定义头肩、三角形、矩形等5点价格形态，在滚动窗口中统计形态事件及事件前后收益、胜率和盈亏比，覆盖个股和行业。','rolling 5-point chart-pattern event indicators (head-shoulder/triangle/rectangle) + event study returns。','日线收盘、行业价格；形态定义和事件窗口可本地实现，但并非现成平台字段。','technical_pattern_event_pending','有可编码的形态事件信息，但属于事件研究而非稳定截面因子；先留作技术形态候选，不自动回测。'),
 '56.':('对全A先取PEG最低10%，再取EBIT最低25%，再计算20日换手率标准差取最低50%，最后按流通市值升序；与策略2/39同一组合。','low PEG × low EBIT × low 20d turnover volatility × small cap。','PIT PE/TTM净利润增长、EBIT、20日turnover_ratio、流通市值。','value_quality_size_exact_duplicate','与策略2/39重复，不新增测试。'),
 '57.':('以股票池和债券ETF做股债切换，依据指数/市场状态及价格均线清仓或持股，属于资产配置。','equity-bond allocation regime switch。','股票/债券ETF价格、市场状态。','asset_allocation_not_stock_factor','不纳入股票因子池。'),
}
if __name__ == '__main__': add_authored(E, '2024年度精选策略2')
