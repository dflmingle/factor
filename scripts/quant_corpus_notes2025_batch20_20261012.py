from quant_corpus_semantic_review_20261012 import add_authored
E={
'75大':('上市200天非ST池，PB<1、经营流入和调整利润>100万、ROA>.15、利润增长正，ROA降序只持1，月调；余钱国债ETF。','high ROA × lowPB positive profit/growth。','PIT财务、市值与盘中涨停。','value_quality_concentration_variant','没有大市值约束；经营流入不是净现金流；单股集中风险不靠标题判断回撤。'),
'76小':('取375自然日前中小板成分而非单纯新股过滤，市值5~50亿最小5；个股跌7%或成分昨日前日均收益跌5%退出，卖出黑名单5日；1月/4月5日后货基。','bounded small size × stale index membership × market/individual stop。','历史成分、市值、日线与盘中。','smallcap_execution_variant','历史成分滞后375天会排/留不同股票，不等于上市375天；市场信号是收盘对收盘，不是开收绝对变动。'),
'77研':('高一年股息前10%、最高PE前10%、最高sales_growth前10%三腿各最小市值取6，合并再最小市值10，正EPS，周调且4/8~4/30空仓。','dividend / highPE / growth gated small size union。','PIT分红、PE、供应商sales_growth与市值。','three_leg_size_composite_variant','PE.desc选最高PE，不能按价值标题误记低PE；各腿先6再合并，最终仍规模排序，需增量验证。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
