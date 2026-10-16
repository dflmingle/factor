"""Source-verified corrections; no automatic semantic inference."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'research_reports/literature/quant-corpus-factor-catalog-20261012'
p=R/'semantic_reviews.json';notes=json.loads(p.read_text())
updates={
18:dict(factor_recipes='score=I(DELTA_ROE>0)+I(ROA2>0)+I(DELTA_MARGIN>0)+I(DELTA_CATURN>0)+I(DELTA_ROA2>0)+I(DLTA_LIQUID>0)；源码ROA2=total_profit+financial_expense/(current_assets+current_assets_1).mean()；mean默认axis=0，不能解释成两季资产平均；低行业中性PB约束。',warnings='原A池使用end_date != 2200-01-01，可能反向排除仍上市股票，须验证API哨兵；ROA2运算优先级和资产mean均偏离通常经济定义；空目标除零风险。原式与修复意图必须分开。'),
21:dict(logic='全市场剔除上市不足250日、科创板和ST后，sales_growth降序取最高10%，保留EPS>0，流通市值升序选5只，每周调仓。',factor_recipes='high sales_growth(top10%)∩EPS>0→low circulating_market_cap；False传入ascending表示降序。',warnings='此前低增长方向记录错误，已按完整源码修正；新增成长约束需与小市值簇去重。'),
29:dict(logic='HS300和CSI500两指数按30日对数回归年化斜率×R²选风格；价值腿依次高正EPS_TTM前10%、高正margin_stability前10%、大流通市值；成长腿低正PEG前10%、低正EBIT前20%、小流通市值。每日指数RSRS18/600与MA20趋势开关。',factor_recipes='style=(exp(slope30*250)-1)*R²；value=high positive EPS_TTM∩high positive margin_stability→large cap；growth=low positive PEG∩low positive EBIT→small cap；BUY=(z600(beta18)*R²>.7) OR MA20 rising3d；SELL=score<-.7 AND MA falling。',warnings='此前把ascending=False写为低值，现已纠正；与78同方向，比例/股票池/择时布尔条件不同；顺序分位相乘不能当作同时全池10%交集。'),
44:dict(logic='初始化沪深300成分，g.p55实际81；盘中价格突破前81日最高high且9观测收盘收益<0时候选，PE降序选1只满仓。按过去3日最大(high-low)/low设1倍止损、2倍止盈。',factor_recipes='entry=intraday_price>MAX81(previous high) AND (close[-1]/close[-9]-1)<0；rank PE descending；exit=price<=cost*(1-maxrange3) OR price>=cost*(1+2*maxrange3)。',warnings='此前55日突破/21日退出记录错误，源码未实现；日频close替代盘中属于adaptation；成分初始化未动态更新。'),
48:dict(logic='中证500每10交易日选股；流通市值升序截取[len/4:-1]，排除最小25%和最大1只；行业内低PEG70%→高利润增长70%→高ROE1/3，最后大流通市值前10；14:55以5日最高收盘/现价-1>=15%止损。',factor_recipes='industry quality growth=exclude smallest circMV25% and largest1 + low PEG70% + high profit_growth70% + high ROE33%；large cap final sort。',warnings='此前20%比例错误；空行业分支peg_list/npgr_list可能沿用上一轮或未定义；修复列表清空须标注adaptation。'),
52:dict(logic='中证500在5/9/11月调仓；最近两条披露的股东户数下降率和非自然人前十大流通股东合计持股比例增长分别降序前100取并集，再布尔PE排序和高ROA选20。',factor_recipes='holder_decline=(old_holders-new_holders)/old_holders；institution_growth=(new_share_ratio-old_share_ratio)/old_share_ratio；top100 lists union；股东户数>10000。',data_requirements='PIT股东户数和前十大流通股东公告/类别/持股比例、中证500历史成分、估值ROA。',status='ownership_change_external_pending',warnings='非筹码分布；全局累积表未清空，陈旧重复记录风险；查询无显式时间排序；order_by(pe_ratio<15,roa.desc())是布尔排序而非PE筛选。'),
57:dict(logic='全A价格>5、流通市值>50、0<PE<100、0<PB<10、上市>365日，排除ST/暂停/688；raw OLS60斜率>0，再raw OLS5斜率>2，四舍五入3位降序。盘中昨低买入、昨高卖出，14:55可卖仓平仓。',factor_recipes='slopeN=round(OLS(raw close over N),3)；slope60>0∩slope5>2；g.trenddays=5并非10日活动参数。',warnings='虽名fit_linear_nor，未归一化，斜率有价格尺度偏差；market_open和after_market_close未在initialize调度，后者含未来一天诊断查询，需检查引擎是否自动调用回调，不用于因子；T+1限价需要分钟执行。'),
78:dict(logic='沪深300内高EPS_TTM前25%后高margin_stability前25%，大流通市值选5；每日9:30交易。RSRS18/600 z×R²>.7且MA20上行BUY，双负SELL；KEEP仍调仓。',factor_recipes='high EPS_TTM25%→high margin_stability25%→large circMV；daily stock_num5；RSRS18/600+MA20 rising3d。',warnings='此前每周调仓和与29反方向记录错误；29同方向但10%顺序筛选/全A及OR买入，78为25%/HS300及AND买入。'),
79:dict(logic='中证500每20日重新筛选；turnover_volatility升序前50%，再BIAS10升序前50%，按ROA降序选10；jq_factor_filter末尾明确return security_list。',factor_recipes='high ROA∩low turnover_volatility50%→low BIAS10 50% within CSI500。',status='roa_turnover_bias_pending',warnings='此前缺少return的结论错误，已核对原始末尾；两个50%为顺序筛选；定义需与平台字段核对。')}
for n,u in updates.items():
 k=next(k for k in notes if '/2023年度精选策略/' in k and Path(k).name.startswith(f'{n}.'))
 notes[k].update(u);notes[k]['review_basis']='20261012 correction audit: complete rendered core reread; original expression, active calls and parameters checked'
p.write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n')
q=R/'pending_recipe_queue_20261012.md';body=q.read_text()
body=body.replace('低 EPS_TTM∩低 margin_stability','高正 EPS_TTM∩高正 margin_stability').replace('与 29 的低 EPS/低 MS 价值分支方向相反，应分开评估。','与29价值分支同方向，但池、筛选比例和择时条件不同。')
body=body.replace('source_bug_intended_roa_turnover_bias_pending','roa_turnover_bias_pending')
body=body.replace('中证 500 内意图为高 ROA∩低 turnover_volatility∩低 BIAS10，各保留前 50%；但原 `jq_factor_filter` 缺少 `return`，按原样执行会把股票列表置为 `None`。只可测试显式修复后的适配版，并保留源代码阻塞记录。','中证500每20日更新；先低turnover_volatility前50%，再低BIAS10前50%，最后高ROA。原函数末尾存在return，此前缺return记录已撤销。')
body=body.replace('沪深 300 中 `close>MAX55(high)` 突破买入、`close<MIN21(low)` 退出，另有 30 日收益和 PE 排序；需确认前一日窗口并和已有 breakout 簇去重。','沪深300盘中价格突破前81日最高high且9观测收益<0，PE降序买1只；3日最大振幅的1倍止损/2倍止盈。日线适配应独立标注。')
body=body.replace('剔除最小流通市值20%，各行业低PEG','剔除最小流通市值25%及最大1只，各行业低PEG')
body=body.replace('基本面和60日趋势过滤后，按5日或10日收盘线性回归斜率取正趋股票；可先拆为日频短趋势斜率，限价买入/T+1退出不混入因子本身。','基本面/价格筛选后raw OLS60斜率>0，raw OLS5斜率>2；斜率按3位小数舍入，价格尺度偏差需单独诊断。昨低买/昨高卖和T+1不混入日频因子。')
q.write_text(body)
