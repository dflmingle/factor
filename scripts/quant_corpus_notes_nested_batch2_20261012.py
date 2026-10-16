from quant_corpus_semantic_review_20261012 import add_authored
E={
'02稳健型ETF策略-调优':('月线MACD防守ETF五腿，权重25/20/25/15/15%，红利YTD门槛−7%/第三腿−6%，每月合并重复标的后按目标值再平衡。','monthly MACD/YTD defensive allocation with monthly weight rebalance。','ETF月线/日线。','etf_allocation_rebalance_fix','相对85修复重复资产资金和再平衡，仍不是新alpha；all_stocks=set遍历无先卖后买保障，订单资金顺序需核查。'),
'03指数':('5函数精确匹配2025/81：三条均价动量排序、21条前价格±.1%开关、14:50ETF轮动。','smoothed ETF momentum21 × hysteresis。','ETF日线/14:50价。','exact_etf_momentum_duplicate','7cc72d5b0f48779c证明；无新公式。'),
'04多标的版ETF策略-25':('6函数匹配2025/58：ETF20条涨幅5~20%、MA5>MA20买前2、持至前4，日轮。','bounded momentum × MA gate × ranking buffer。','ETF日线。','exact_etf_buffer_duplicate','9c145951ee2ab2fd证明；保留重复ETF代码风险。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/ETF轮动策略2026')
