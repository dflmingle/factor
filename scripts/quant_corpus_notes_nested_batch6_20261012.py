from quant_corpus_semantic_review_20261012 import add_authored
E={
'01-涨停':('首板高开与炸板弱转强两模式，继承2025/13，参数化VWAP、成交额/市值、竞价3%和左压力窗量.9；盈利开板或MA5下方退出。','first-board/broken-board + VWAP + auction + left-volume-pressure。','竞价明细、分钟、涨停价、PIT市值。','auction_intraday_blocked','10函数AST证明d368de9a72eb1297；initialize未安排回调，依赖旧after_code_changed；auction[0]不保证最终竞价；1.1写死非20%板。'),
'02-首板':('只做昨日封板、前日非板高开腿：VWAP/收*1.1−1≥.07、额5.5~20亿、总值≥70亿/流通≤520亿、高开0~6%、竞价量≥3%、左窗量>.9最大。','first-board high-open + volume-pressure break。','竞价/分钟/涨停/PIT估值。','auction_intraday_blocked','dba46c9a1fb03fd3证明；g.n_days_limit_up_list依赖after_code_changed初始化；buy使用day_open市场保护价，需平台可用时点。'),
'03-首板':('只做昨天触板未封且前日未板：3间隔涨≤28%、昨实体≥−5%、VWAP/收≥.96、额3~19亿、估值/竞价/左压门槛。','broken board weak-to-strong auction setup。','竞价/分钟/涨停。','auction_intraday_blocked','134844099535b6bc证明；auction/当前high_limit*1.1口径必须审；无日线等价。'),
'04首板':('25日无旧封板、昨封板放量>MA20*2且价3~100、相对全120条均价.9~1.3；2~10交易日后回撤6~15%、量<首板*.6、昨收<MA20*.98且K线反转或止跌3条件≥2，距第4日最近优先。','first-board volume spike → delayed shrink-volume reversal setup。','PIT实际涨停价、qfq日线和09:45价。','daily_setup_atoms_candidate_with_bugs','所谓turnover=V*C/money不是换手率，MA60实际全120条均价；datetime类又调用datetime.datetime导致天数异常999，可能不买；失败订单仍删除事件；未来价分析仅末日事后报告，未馈入信号。'),
'05龙虎榜':('14函数AST精确重复已核验龙虎榜首二板策略，按上榜资金与涨停事件交易。','existing dragon-tiger net-flow first/second-board selection。','PIT龙虎榜、竞价/分钟、涨停数据。','exact_lhb_intraday_duplicate','d9cc877c0ae6e65b证明；缺龙虎榜细项不以moneyflow伪装。'),
'聚宽使用说明':('聚宽注册至回测模拟交易指南同文阅读。','无。','无。','platform_user_guide_no_factor','不计新候选。')}
if __name__=='__main__':add_authored(E,'量化策略/量化策略/首板向上趋势策略2026')
