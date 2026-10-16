from quant_corpus_semantic_review_20261012 import add_authored
E={
'48投':('市值>500亿、PE0~50、EPS>.12、ROA>.15、负债/权益<.5、两项营收增长>.3/.2、留存利润正，按留存利润降序前10，再ROIC_TTM>.08月调。','retained_profit descending × ROIC/quality/growth gates。','PIT财务、ROIC定义与市值。','large_quality_retained_profit_candidate','标题中等市值实际>500亿；先limit10再ROIC会不足10只；ROIC尺度与聚宽定义需核对，不能默认TTM ROE替代。'),
'49干':('月度2010~2024全A训练/测试表生成，5项Barra/价值增长特征，标签下月个股收益减上证综指，前120个月训练、后续测试，另超额>10%分类标签。','features=[non_linear_size,beta,BP,earnings_yield,growth]; next-month excess label。','聚宽Barra/因子定义、PIT成分、行业中性化。','conformal_title_training_code_missing','源码只有CSV样本生成，没有标题5折保形回归模型与校准代码；宽泛except静默丢日期；不能确认时间分组校准覆盖率或模型收益。'),
'4高':('14函数精确复用2024策略1/19：三年股息率前10%，低PE与ROE/营收/利润增长及PEG约束，月调10。','high dividend3y × growth/value constraints。','PIT分红与财务。','exact_dividend_growth_value_duplicate','a41f75cae1fe8e3e证明；仅参数名称与已审一致，无新增原子。')}
if __name__=='__main__':add_authored(E,'聚宽2025年精选')
