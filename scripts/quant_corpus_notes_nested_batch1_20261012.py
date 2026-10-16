from quant_corpus_semantic_review_20261012 import add_authored
E={
'01趋势筛选后相关性最小etf轮动-调优':('ETF月更20日动量与60日乖离百分位和最高40%池，245日收益绝对相关均值最小4中取最小2持有，日轮。','rank(momentum20)+rank(bias60) universe × low mean abs corr245 selection。','ETF日线。','etf_trend_corr_allocation_variant','实际不调用get_rank做最后趋势排序，持有相关最小2；select_etf未调用，min_scale未使用；固定池与存续偏差需审计。'),
'01趋势筛选后相关性最小etf轮动25':('9函数AST匹配已审趋势持续/低相关ETF轮动，证明0e4b8e53ee6e892f。','trend run age × low abs correlation × trend25。','ETF长日线。','exact_etf_trend_corr_duplicate','沿用2025/97缓存更新逻辑，不新增原子。'),
'02稳健型ETF策略-25':('5函数AST复用2025/85稳健ETF：月线MACD与红利年内回撤切换，5腿防守配置。','monthly MACD × YTD gate × fixed defensive sleeves。','ETF月线/日线与账本。','exact_etf_defensive_duplicate','363b3083ba573a8a证明；无新选股因子。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/ETF轮动策略2026')
