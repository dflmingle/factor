#!/usr/bin/env python3
"""Report audited local proxies without claiming original numerical reproduction."""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from scipy.stats import norm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from wu_factor_timing_inputs_20261014 import OUT, ROOT, dump, sha
from wu_factor_timing_models_20261014 import accuracy
from wu_factor_timing_evaluate_20261014 import daily_ledger

def md(d):
    return d.to_markdown(index=False,floatfmt='.3f')

def main():
    allstats=pd.concat([pd.read_csv(OUT/f'{p}_accuracy.csv') for p in ('regression','cluster')],ignore_index=True)
    for window,ids in allstats.groupby('window').groups.items():
        good=allstats.loc[ids,'cw_hac_one_sided_p'].notna()
        ix=np.asarray(list(ids))[good.to_numpy()]
        allstats.loc[ix,'bh_fdr_q']=multipletests(allstats.loc[ix,'cw_hac_one_sided_p'],method='fdr_bh')[1]
    allstats.to_csv(OUT/'accuracy_with_multiple_testing.csv',index=False)
    forecast=pd.concat([pd.read_csv(OUT/f'{p}_forecasts.csv') for p in ('regression','cluster')],ignore_index=True)
    diagnostics=[]
    for group,d in forecast.groupby(['key','wing','family','model']):
        for window,lo,hi in [('pre2026_oos','2021-09','2025-12'),('recent','2026-01','2026-08')]:
            sub=d[d.target_month.between(lo,hi)]
            diagnostics.append(dict(zip(['key','wing','family','model'],group),window=window,**accuracy(sub)))
    pd.DataFrame(diagnostics).to_csv(OUT/'subperiod_accuracy.csv',index=False)
    paired=[];rng=np.random.default_rng(20241014)
    b=pd.read_pickle(OUT/'inputs.pkl')
    key='reversal_onemonthreturn'
    for wing in ('LS','L','S'):
        for family in ('portfolio','macro','macro_cluster'):
            for model,sub in forecast[(forecast.key==key)&(forecast.wing==wing)&(forecast.family==family)].groupby('model'):
                base=daily_ledger(b,key,wing,sub,'buy_hold',True,.003)
                for rule in ('sign_flip','long_cash'):
                    timed=daily_ledger(b,key,wing,sub,rule,True,.003)
                    for window,lo,hi in [('five_year','20210907','20260907'),('recent','20260101','20260907')]:
                        d=timed.loc[lo:hi];db=base.reindex(d.index)
                        if not len(d):continue
                        monthly=d.net_return.groupby(d.index.to_period('M')).apply(lambda x:np.prod(1+x)-1)
                        bm=db.net_return.groupby(db.index.to_period('M')).apply(lambda x:np.prod(1+x)-1)
                        # Window edges and the unfinished final month are not
                        # counted as complete monthly uncertainty observations.
                        counts=d.groupby(d.index.to_period('M')).size()
                        expected=pd.Series(1,index=b['calendar']).groupby(b['calendar'].to_period('M')).sum()
                        complete=counts==expected.reindex(counts.index)
                        if b['partial_last_month']:complete.loc[b['dates'][-1].to_period('M')]=False
                        monthly=monthly.reindex(complete[complete].index);bm=bm.reindex(monthly.index)
                        active=(monthly-bm).to_numpy();n=len(active)
                        if not n:continue
                        fitted=sm.OLS(active,np.ones((n,1))).fit(cov_type='HAC',cov_kwds={'maxlags':min(3,n-1)})
                        sims=[]
                        for _ in range(2000):
                            starts=rng.integers(0,n,size=int(np.ceil(n/3)))
                            ids=np.concatenate([(start+np.arange(3))%n for start in starts])[:n]
                            sims.append(active[ids].mean()*12*100)
                        paired.append(dict(wing=wing,family=family,model=model,rule=rule,window=window,n_months=n,
                            mean_monthly_active_pct=float(active.mean()*100),hac_t=float(fitted.tvalues[0]),
                            hac_p_one_sided=float(norm.sf(fitted.tvalues[0])),
                            bootstrap_annual_active_low95_pct=float(np.quantile(sims,.025)),
                            bootstrap_annual_active_high95_pct=float(np.quantile(sims,.975))))
    paired=pd.DataFrame(paired)
    for window,ids in paired.groupby('window').groups.items():
        valid=paired.loc[ids,'hac_p_one_sided'].notna()
        ix=np.asarray(list(ids))[valid.to_numpy()]
        paired.loc[ix,'bh_fdr_q']=multipletests(paired.loc[ix,'hac_p_one_sided'],method='fdr_bh')[1]
    paired.to_csv(OUT/'paired_monthly_active_uncertainty.csv',index=False)
    summary=pd.read_csv(OUT/'strategy_results.csv')
    rel=pd.read_csv(OUT/'strategy_vs_buy_hold.csv')
    keep=(summary.key==key)&(summary.wing=='LS')&(summary.family=='portfolio')&(summary.window=='five_year')&summary.delayed&(summary.one_way_cost==.003)
    table=summary[keep & summary.model.isin(['OLS','ElasticNet','PC','PLS']) & summary.rule.isin(['buy_hold','sign_flip'])]
    table=table[~((table.rule=='buy_hold')&(table.model!='OLS'))]
    table=table[['model','rule','annual_arithmetic_pct','cagr_pct','max_drawdown_pct','sharpe']].copy()
    table.columns=['模型','策略','算术年化%','CAGR%','最大回撤%','夏普']
    primary=allstats[(allstats.key==key)&(allstats.wing=='LS')&(allstats.family=='portfolio')&(allstats.window=='five_year_months')&allstats.model.isin(['OLS','ElasticNet','PC','PLS'])]
    ptable=primary[['model','n','r2_oos_pct','cw_hac_one_sided_p','bh_fdr_q']].copy()
    ptable.columns=['模型','完整月数','OOS_R²%','CW_HAC单侧p','全测试FDR_q']
    pre=pd.DataFrame(diagnostics);pre=pre[(pre.key==key)&(pre.wing=='LS')&(pre.family=='portfolio')&(pre.window=='pre2026_oos')&pre.model.isin(['OLS','ElasticNet','PC','PLS'])]
    pret=pre[['model','n','r2_oos_pct','cw_hac_one_sided_p']]
    bestclusters=allstats[(allstats.key==key)&(allstats.wing=='LS')&(allstats.family=='macro_cluster')&(allstats.window=='five_year_months')].sort_values('r2_oos_pct',ascending=False).head(5)
    ctable=bestclusters[['model','n','r2_oos_pct','cw_hac_one_sided_p','bh_fdr_q']]
    ltable=summary[(summary.key==key)&(summary.wing=='L')&(summary.family=='portfolio')&(summary.model.isin(['OLS','ElasticNet','PC','PLS']))&(summary.window=='five_year')&summary.delayed&(summary.one_way_cost==.003)&summary.rule.isin(['buy_hold','long_cash'])]
    ltable=ltable[~((ltable.rule=='buy_hold')&(ltable.model!='OLS'))][['model','rule','annual_arithmetic_pct','max_drawdown_pct','sharpe']]
    recent=summary[(summary.key==key)&(summary.wing=='LS')&(summary.family=='portfolio')&(summary.window=='recent')&summary.delayed&(summary.one_way_cost==.003)&summary.model.isin(['OLS','ElasticNet','PC','PLS'])&summary.rule.isin(['buy_hold','sign_flip'])]
    recent=recent[~((recent.rule=='buy_hold')&(recent.model!='OLS'))][['model','rule','annual_arithmetic_pct','compound_total_pct','max_drawdown_pct']]
    counts=[]
    for window in allstats.window.unique():
        s=allstats[(allstats.window==window)&(allstats.n>=24)]
        counts.append(dict(window=window,tests=len(s),nondegenerate_tests=int(s.cw_hac_one_sided_p.notna().sum()),positive_r2=int((s.r2_oos_pct>0).sum()),
            raw_p05_and_positive_r2=int(((s.cw_hac_one_sided_p<.05)&(s.r2_oos_pct>0)).sum()),
            fdr05_and_positive_r2=int(((s.bh_fdr_q<.05)&(s.r2_oos_pct>0)).sum()),
            factor_count_fdr05=int(s.loc[(s.bh_fdr_q<.05)&(s.r2_oos_pct>0),'key'].nunique())))
    selected=summary[(summary.wing=='LS')&(summary.rule=='sign_flip')&(summary.window=='five_year')&summary.delayed&(summary.one_way_cost==.003)]
    inventory=[]
    for factor,dd in selected.groupby('key'):
        top=dd.loc[dd.annual_arithmetic_pct.idxmax()]
        active=rel[(rel.key==factor)&(rel.wing=='LS')&(rel.window=='five_year')&rel.delayed&(rel.one_way_cost==.003)&(rel.rule=='sign_flip')]
        a=active[(active.family==top.family)&(active.model==top.model)].iloc[0]
        inventory.append(dict(key=factor,family=top.family,model=top.model,annual_net_pct=top.annual_arithmetic_pct,
                             improvement_pp=a.annual_improvement_pp,maxdd_pct=top.max_drawdown_pct,
                             status='descriptive best after 36 model tests; not held-out winner'))
    pd.DataFrame(inventory).to_csv(OUT/'all24_descriptive_best.csv',index=False)
    coeff=pd.read_csv(OUT/'regression_screening.csv'); coeff=coeff[(coeff.key==key)&(coeff.wing=='LS')&(coeff.family=='portfolio')&coeff.target_month.between('2021-09','2026-08')]
    screen=coeff[coeff.model.isna()].groupby('name').size().sort_values(ascending=False).head(15)
    screen.to_csv(OUT/'reversal_top_screened_features.csv',header=['selected_months'])
    # Scientific standalone artifact; no web product or generated bitmap art.
    fig,axs=plt.subplots(2,1,figsize=(11,8),sharex=True)
    display=['Buy & hold','OLS','ElasticNet','PC','PLS'];frame=None
    for label in display:
        model='OLS' if label=='Buy & hold' else label;rule='buy_hold' if label=='Buy & hold' else 'sign_flip'
        sub=forecast[(forecast.key==key)&(forecast.wing=='LS')&(forecast.family=='portfolio')&(forecast.model==model)]
        d=daily_ledger(b,key,'LS',sub,rule,True,.003).loc['20210907':'20260907']
        nav=(1+d.net_return).cumprod();axs[0].plot(nav.index,nav,label=label)
        running=nav.cummax().clip(lower=1.);axs[1].plot(nav.index,(nav/running-1)*100,label=label)
    axs[0].set_ylabel('Wealth (start = 1)');axs[0].legend(ncol=3)
    axs[0].set_title('Wu method proxy: monthly reversal LS / next-close execution / 30bp one-way')
    axs[1].set_ylabel('Drawdown (%)')
    for ax in axs:ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(OUT/'reversal_five_year.png',dpi=170);fig.savefig(OUT/'reversal_five_year.svg');plt.close(fig)
    verify=json.loads((OUT/'verification.json').read_text())
    manifest=json.loads((OUT/'input_manifest.json').read_text())
    text=f'''# Wu（2024）因子择时本地复现尝试

已取得并阅读出版全文，重建 §2–§6 中的核心24个因子、9类回归模型和5类聚类模型。
**结论：反转组合存在可预测性线索和部分回撤改善，但尚未复制原文完整数值结果，
也未证实能直接改善平台多头因子池。** 原始数据库、完整预测变量及调参设置不齐，
本报告一律为本地代理，不是 PandaAI 平台净超额或原文 CH-3 alpha。

## 方法与范围

- 24 个因子×多空/多头/空头3个目标×两类预测变量×9类模型；回归预测{len(forecast[forecast.family!='macro_cluster']):,}条。
- 24 个多空目标×5算法及ARI选择器×2/3/4簇；聚类预测{len(forecast[forecast.family=='macro_cluster']):,}条。
- 月末成分、最小30%市值剔除、非规模三档市值条件排序、档内市值加权。
- 月度扩展训练、训练期Pearson p≤.05筛选、训练期标准化；所有预测变量滞后。
- 原文同月末收盘假设与下一收盘执行分别报告；无成本与0.30%单边成本分别报告。
- 日度策略按整月固定持仓构造；多空组合1单位多头+1单位空头，不用日度再平衡多空差代替。
- 近五年收益/回撤窗口2021-09-07至2026-09-07；完整月预测统计2021-09至2026-08共60个月。
  2026-09仅有截至09-07路径，排除月度误差统计。近期2026-01-01至09-07独立报告。
- 历史扩展2006+，而原文2000+；本地 OOS 开始日期见 coverage 文件，不能宣称原文2013/2015窗口全部重现。

## 反转的近五年预测能力

{md(ptable)}

正R²说明比同期扩展历史均值的均方预测误差更小。p值和多重检验校正
仍须一起看；不能把一次最高R²当成稳定新alpha。完整结果包括差模型，未只保留赢家。

聚类前五个结果（按近五年结果事后排序，只作描述）：

{md(ctable)}

## 经济效果：近五年，延迟下一收盘执行，单边成本0.30%

{md(table)}

这是**假想可融券的市值条件中性多空组合绝对收益**，不是平台股票池净超额。
表中同时给算术年化与CAGR，不能混用。成本按底层股票实际权重变化、月内漂移、
方向反转计算；没有融券费、可借性、涨跌停冲击及退市现金赔付。
直接对照文件 `strategy_vs_buy_hold.csv`；每个策略只与相同可用日期的基准比较。

多头单腿迁移诊断（预测该多头自身，负信号切现金，下一收盘，30bp）：

{md(ltable)}

以上是单个反转多头/现金实验，未组合回真实平台池，也没有降低现金敞口却保留
同等股票风险的承诺。长期多空结果不能证明多头池的因子权重切换有效。

## 稳健性与近期

剔除2026之前后要区分：下表保留2021-09至2025-12所有原始月份，**不事后删极端月份**：

{md(pret)}

部分模型在2026前R²转负，说明近五年整体改善明显受2026样本影响。
近期只有8个完整月，不能据此证明预测稳定性。近期日度经济效果如下，短期算术
年化仅为诊断，同时列累计收益：

{md(recent)}

全测试多重检验统计（HAC CW；要求完整月数≥24；近期只有8个完整月，
下表近期0表示未达到这一统计样本门槛，并非未计算近期）：

{md(pd.DataFrame(counts))}

策略相对买入持有的月度收益差还给了HAC检验、三个月循环块bootstrap区间、FDR校正，
见 `paired_monthly_active_uncertainty.csv`。这是探索性多模型研究，未设置独立新数据盲测；
不得将事后最佳模型的改善写成可保证收益。

## 原文/本地差异与验证

详见 [逐项原文映射](../literature/wu-china-factor-timing-20261014/method_mapping.md)。
主要差异：Tushare代替Datastream/Worldscope、2006+代替2000+、财务字段代理、38组合
特征与宏观变量定义部分推断、模型调参细节未公开、无原始完整一年国债序列、
无法重现178列Realtime/Announcement数据、未复制CH-3 alpha。逐日252日beta中性化、
Hopkins检验及全部中间分位组预测表尚未重现；此次完成的是核心方法代理实验。
早期v1固定15交易日过滤会剔除春节短月，已修正为v2相对市场交易天数门槛并独立重跑。

验证通过{verify['tests']}项，含实际数据截断重算所有九模型、宏观/组合预测变量前缀一致、
改变当月实际收益不改变预测、三档权重与市值权重、月度多空固定持仓收益、执行延迟及成本。
输入SHA256、源文件SHA256、训练窗、每次筛选、年度内层验证选择均保留。
遵循项目平台对齐规则的代理/版本披露原则，但月度论文协议与平台10日等权协议分别保存。

## 下一步的研究判断

保留“反转组合历史波动/市场波动→反转溢价预测”路线，先固定PC、PLS及正负符号规则
做新的样本外观察；不能按本次结果继续挑最优阈值。
若迁移到平台，应先在现有真实多头池内测反转权重或现金敞口调整，核查收益、回撤、
池级换手共同变化。当前未创建平台因子、未发起平台回测、未修改真实因子池，平台算力消耗0。
'''
    (OUT/'summary.md').write_text(text)
    dump(OUT/'completion.json',dict(status='local_method_proxy_completed',original_numeric_replication=False,
        original_paper_read=True,paper_doi='10.1002/ise3.86',factors=24,regression_models=9,cluster_algorithms=5,
        regression_rows=int((forecast.family!='macro_cluster').sum()),cluster_rows=int((forecast.family=='macro_cluster').sum()),
        verification_tests=verify['tests'],input_sha256=sha(OUT/'inputs.pkl'),
        platform_compute_spent=0,live_pool_changed=False,statistical_counts=counts,
        original_result_not_claimed='20.4% CH-3 alpha / threefold original cumulative return',
        report='summary.md'))
    print('WU_REPORT_COMPLETE',len(forecast),flush=True)

if __name__=='__main__':main()
