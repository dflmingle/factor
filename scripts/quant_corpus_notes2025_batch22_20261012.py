from quant_corpus_semantic_review_20261012 import add_authored
E={
'81搞':('11ETF14:50以近2昨收+现价相对前20附近3条收盘均值动量排序，最高且现价>21条前价1.001买，跌破.999卖或换强者。','smoothed return≈(sum(last2close)+current)/(sum(close[−23:−20]))−1; hysteresis .1%。','ETF日线与14:50实时价。','etf_smoothed_momentum_duplicate','set迭代与随机并列微扰未固定；单一ETF异常数据return中止全体；收益依赖盘中执行不是新股票簇。'),
'82回':('全沪深指数成分，正PB/PE/PCF与市值四项秩和升序，持仓按等差权重递减；价格对上次成交涨10%且超配、跌10%且低配才再平衡。','rank(mv)+rank(PB)+rank(PE)+rank(PCF), low; linear rank weights。','PIT估值/市值、成交时点与日线。','value_size_weight_buffer_method','最后名次权重为0；权重和1但持股数依赖g.choicenum；价格涨跌再平衡属于降低换手方法，无新原子。'),
'83大小':('与64同大/小20股10条均收益月开关，周调；大盘BOLL过滤后ROA低PB、大盘质量、100~900亿低PCF三池并集；小盘沿用质量小盘；弱市5ETF等权；15%止损补最弱幸存者。','relative size momentum × fundamental/BOLL universe gates。','PIT财务/成分、日线和分钟。','size_value_foreign_regime_variant','ROIC_BIG实际仅ROA无ROIC；大盘三腿并集set无稳定顺序；g.stock_num不是最终总持股上限；属于组合执行变体。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
