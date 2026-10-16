from quant_corpus_semantic_review_20261012 import add_authored
E={
'8国':('中小板市值10~100亿且归母/净利正、营收>1亿、价≤50，最小3~6；持股数由指数−MA10绝对点差分段；1/4月指数两日微跌约束允许重开，9%止损/市场跌5%。','quality small size × index point-bias/seasonal gates。','PIT财务/成分、市值、分钟与指数。','smallcap_index_bias_variant','审计默认关且df_audit不返回；市场止损先append(stock)可能残留或未定义；这里绝对点差不是百分比乖离，不能混记。'),
'90固':('红利8%、纳指8%、黄金14%、国债70%，每日检查偏离目标15%以上且>100股才按目标调，先卖再买。','fixed defensive allocation × rebalance threshold。','ETF日线与可交易状态。','fixed_asset_allocation_method','纯固定权重配置无选股因子；可以借鉴偏离缓冲，不能当新增量价alpha。'),
'91ETF':('德国ETF513030开盘价−昨收在.003~.5元买，14:59清仓，T0日内。','absolute opening price gap band on one T0 ETF。','ETF开盘、分钟、T0规则与汇率/时差。','etf_T0_gap_intraday_blocked','门槛是元非0.3%~50%；绝对价差不可跨价格尺度推广，非全A股票T+1可执行信号。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
