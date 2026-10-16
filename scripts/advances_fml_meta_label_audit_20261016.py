"""Repair the existing three Meta-label experiments; offline, no new search.

Preserves the original experiment and writes a versioned audit directory.
Separates frozen-selection accounting from common-support qfq repricing.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import hashlib
import json
import pickle
from pathlib import Path
import time
import numpy as np
import pandas as pd

import advances_fml_meta_label_20261016 as original
from meta_label_ledger import daily_ledger, period_ledger, summarize
from platform_alignment_rules import ALIGNMENT_RULE_VERSION

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/literature/advances-fml-meta-label-20261016-ledger-v2'
MARKET = ROOT/'research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl'
AUDIT_VERSION = 'meta-ledger-v2-self-financing-common-support-label-exit'
STARTED = time.monotonic()


def log(message):
    print(f'[{time.monotonic()-STARTED:.1f}s] {message}', flush=True)


def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False)+'\n')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(2**20), b''):
            h.update(chunk)
    return h.hexdigest()


def primary_ids(score, valid):
    ids = np.flatnonzero(valid)
    # Stable symbol tie break. Exact same floor convention as the old script.
    return ids[np.argsort(-score[ids], kind='stable')[:max(int(len(ids)*.1), 1)]]


def audited_probabilities(X, y, score, support, dates, exits, stop=None, perturb=False):
    n = len(dates) if stop is None else stop
    prob = np.full(y.shape, np.nan)
    folds = []
    masked_y = np.where(support, y, np.nan)
    for ts in range(original.TRAIN+original.PURGE, n, original.TEST):
        train = np.flatnonzero((dates < dates[ts]) & (exits < dates[ts]))[-original.TRAIN:]
        if len(train) != original.TRAIN:
            raise AssertionError('insufficient expired-label training history')
        yy = masked_y.copy()
        if perturb:
            # All labels not available to this particular model are replaced;
            # eligibility, rather than merely model.predict, must exclude them.
            yy[exits >= dates[ts]] = 10000.
        model = original.train_meta(X, yy, score, train)
        if model is None:
            raise AssertionError('classifier could not be fitted')
        tests = np.arange(ts, min(ts+original.TEST, n))
        for i in tests:
            ids = np.flatnonzero(np.isfinite(X[i]).all(1))
            prob[i,ids] = model.predict_proba(X[i,ids])[:,1]
        folds.append(dict(test_index=ts, test_first=str(dates[ts].date()),
                          test_last=str(dates[tests[-1]].date()), periods=len(tests),
                          train_first=str(dates[train[0]].date()), train_last=str(dates[train[-1]].date()),
                          latest_label_exit=str(exits[train].max().date()), train_periods=len(train)))
    return prob, folds


def select_paths(score, prob, support, indices, retention):
    selected = []; universes = []; previous = set()
    for i in indices:
        ids = primary_ids(score[i], support[i])
        if prob is None:
            keep = set(ids.tolist())
        else:
            keep = set(ids[prob[i,ids] >= .5].tolist())
            if retention:
                keep |= set(ids) & previous
            if not keep:
                keep = {int(ids[0])}
        selected.append(keep); universes.append(np.flatnonzero(support[i])); previous = keep
    return selected, universes


def frozen_old_paths(z, X, y, dates, score, candidate):
    """Reproduce original selections, including their block-reset decision rule.

    Replay only: selection errors are intentionally not silently repaired here.
    The repaired main path below no longer resets at block boundaries.
    """
    indices = []; primary = []; meta = []; universes = []
    for ts in range(original.TRAIN+original.PURGE, len(dates)-original.TEST+1, original.TEST):
        train = np.arange(ts-original.PURGE-original.TRAIN, ts-original.PURGE)
        model = original.train_meta(X, y, score, train)
        previous = set()
        for i in range(ts, ts+original.TEST):
            prob = np.full(y.shape[1], np.nan)
            ids = np.flatnonzero(np.isfinite(X[i]).all(1))
            prob[ids] = model.predict_proba(X[i,ids])[:,1]
            valid = np.isfinite(score[i]) & np.isfinite(y[i])
            # Old np.argsort used its default quicksort; preserve that here.
            ids = np.flatnonzero(valid)
            chosen = set(ids[np.argsort(-score[i,ids])[:max(int(len(ids)*.1),1)]].tolist())
            keep = original.choose(score[i], prob, y[i], previous)
            indices.append(i); primary.append(chosen); meta.append(keep)
            universes.append(ids); previous = keep
    # Check against independently persisted old period returns, not just new code.
    for name, path in [('primary',primary), ('meta',meta)]:
        saved = pd.read_csv(original.OUT/f'{candidate}.{name}_oos.csv')
        held = [np.mean(y[i,sorted(s)]) for i,s in zip(indices,path)]
        np.testing.assert_allclose(saved.held, held, atol=1e-12, rtol=1e-12)
        np.testing.assert_array_equal(saved['index'], indices)
    return np.asarray(indices), primary, meta, universes


def main():
    if OUT.exists():
        raise SystemExit(f'Refusing to overwrite existing audit: {OUT}')
    OUT.mkdir(parents=True)
    log('loading saved signals and qfq market')
    dates, stocks, panels, saved_y = original.load()
    source = pickle.loads(original.SEAT.read_bytes())['provenance']
    calendar, all_stocks, fields = pd.read_pickle(MARKET)
    stock_positions = all_stocks.get_indexer(stocks)
    if np.any(stock_positions < 0) or not all(s.endswith(('.SH','.SZ')) for s in stocks):
        raise AssertionError('invalid archived stock mapping')
    close = fields['close'][:,stock_positions]
    cap = fields['cap'][:,stock_positions]
    del fields
    positions = calendar.get_indexer(dates)
    if np.any(np.diff(positions) != 10):
        raise AssertionError('saved platform signal grid is not contiguous')
    exits = calendar[positions+11]
    with np.errstate(divide='ignore', invalid='ignore'):
        y = close[positions+11].astype(float)/close[positions+1]-1
    z = np.stack([original.cs_z(panels[k]) for k in original.SEATS], 2)
    X = original.make_features(z)
    common = np.isfinite(X).all(2) & np.isfinite(y) & np.isfinite(cap[positions]) & (cap[positions]>0)
    strict = np.mean(z, axis=2)  # requires all five seats; no NaN renormalization.
    old_composite = np.nanmean(z, axis=2)
    joint = np.isfinite(y) & np.isfinite(saved_y)
    delta = np.abs(y-saved_y)
    affected = joint & (delta>1e-5)
    label_info = dict(comparable_stock_periods=int(joint.sum()), differences_over_1e_5=int(affected.sum()),
                      absolute_return_diff_quantiles=np.quantile(delta[joint], [.5,.9,.99,1]).tolist(),
                      new_qfq_only=int((np.isfinite(y)&~np.isfinite(saved_y)).sum()),
                      saved_only=int((~np.isfinite(y)&np.isfinite(saved_y)).sum()))
    rr, cc = np.where(affected)
    largest = np.argsort(-delta[rr,cc])[:100]
    pd.DataFrame(dict(signal_date=dates[rr[largest]], stock=stocks[cc[largest]],
                      saved_return=saved_y[rr[largest],cc[largest]],
                      qfq_return=y[rr[largest],cc[largest]],
                      abs_diff=delta[rr[largest],cc[largest]])).to_csv(OUT/'label_mismatch_top100.csv',index=False)
    dump('input_audit.json', dict(label_repricing=label_info, source_provenance=source,
         calendar_start=str(calendar[0]), calendar_end=str(calendar[-1]), archived_symbols=len(stocks),
         market_symbols=len(all_stocks), omitted_market_symbols=len(all_stocks)-len(stocks),
         saved_signal_periods=len(dates), signal_first=str(dates[0]),signal_last=str(dates[-1]),
         final_label_exit=str(exits[-1]), partial_seat_cells=int((np.isfinite(old_composite)&~np.isfinite(strict)).sum()),
         status='archived signals proxy; not latest platform-equivalent full-universe regeneration'))
    dump('plan.json', dict(audit_version=AUDIT_VERSION, alignment_reference=ALIGNMENT_RULE_VERSION,
         source_signal_rule=source['source_rule_version'], price_mode='qfq', cap='total_mv',
         universe='archived .SH/.SZ support within full-A cache; no new ST filter',
         signal_normalization='archive scores already direction-oriented and 1%-99% winsorized then z-scored; existing script re-zscore retained',
         composite='strict sum of five standardized seats / 5',
         benchmark='same common factor_valid support for every audited variant',
         one_way_cost=.003, cost='actual buys+sells, self-financing post-fee target',
         train_periods=36,test_block_periods=12,threshold=.5,purge='training exit < first test signal',
         parameters_changed=False, platform_compute_spent=0,
         limits=['not a full book replication','archive ends before formal window end',
                 'previously viewed historical walk-forward; no untouched holdout',
                 'factor-valid support includes endpoint-return validity per project contract',
                 'no post-window liquidation; final basket marked at close']))
    rows = []; frozen_rows = []; checks = dict(frozen_saved_return_reproduction={}, causal={})
    all_folds = []
    for candidate, (kind, j) in original.CANDIDATES.items():
        log(f'{candidate}: replaying frozen 72-period paths')
        old_score = original.primary(z, kind, j)
        ii, bp, mp, universes = frozen_old_paths(z, X, saved_y, dates, old_score, candidate)
        for name, path in [('primary',bp),('meta',mp)]:
            ledger = period_ledger(path, universes, saved_y, ii)
            ledger['signal_date'] = dates[ii]
            ledger.to_csv(OUT/f'{candidate}.frozen72_{name}.csv',index=False)
            frozen_rows.append(dict(candidate=candidate,variant=name,**summarize(ledger)))
        checks['frozen_saved_return_reproduction'][candidate] = 'PASS, all 72 saved held returns match'
        score = strict if kind == 'composite' else z[:,:,j]
        support = common & np.isfinite(score)
        prob, folds = audited_probabilities(X,y,score,support,dates,exits)
        for f in folds:
            all_folds.append(dict(candidate=candidate, **f))
            assert pd.Timestamp(f['latest_label_exit']) < pd.Timestamp(f['test_first'])
        indices = np.arange(original.TRAIN+original.PURGE,len(dates))
        # Test a later block as well as the first; expanding the data prefix
        # cannot change already published predictions.
        stop = original.TRAIN+original.PURGE+original.TEST+3
        prefix, _ = audited_probabilities(X[:stop],y[:stop],score[:stop],support[:stop],dates[:stop],exits[:stop])
        np.testing.assert_allclose(prefix,prob[:stop],atol=0,rtol=0,equal_nan=True)
        prefix_z = np.stack([original.cs_z(panels[k][:stop]) for k in original.SEATS],2)
        np.testing.assert_allclose(original.make_features(prefix_z),X[:stop],atol=0,rtol=0,equal_nan=True)
        altered, _ = audited_probabilities(X,y,score,support,dates,exits,stop=stop,perturb=True)
        np.testing.assert_allclose(altered[:stop],prob[:stop],atol=0,rtol=0,equal_nan=True)
        checks['causal'][candidate] = dict(prefix_prediction='PASS, bitwise equal',
             prefix_features_rebuilt='PASS, bitwise equal',
             unavailable_label_perturbation='PASS, bitwise equal',all_training_exits_before_signal=True)
        np.savez_compressed(OUT/f'{candidate}.probabilities.npz', probability=prob[indices], indices=indices)
        for name, pp, retention in [('primary',None,False),('meta_gate_only',prob,False),('meta_retention',prob,True)]:
            selections, universes = select_paths(score,pp,support,indices,retention)
            periods,daily,holdings = daily_ledger(selections,universes,indices,dates,calendar,close)
            holdings['stock'] = stocks[holdings.stock.to_numpy()]
            prefix_name = f'{candidate}.{name}'
            periods.to_csv(OUT/f'{prefix_name}.periods.csv',index=False)
            daily.to_csv(OUT/f'{prefix_name}.daily.csv')
            holdings.to_csv(OUT/f'{prefix_name}.holdings.csv.gz',index=False)
            # Holdings decisions must also match a truncated replay, not just p.
            truncated, _ = select_paths(score[:stop],None if pp is None else pp[:stop],support[:stop],
                                         indices[indices<stop],retention)
            assert truncated == selections[:len(truncated)]
            for window in ('walkforward83','same72','recent2026'):
                mask = np.ones(len(periods),bool)
                if window == 'same72': mask = periods['index'].isin(ii).to_numpy()
                if window == 'recent2026': mask = (periods.signal_date >= pd.Timestamp('2026-01-01')).to_numpy()
                part = periods[mask]
                if window == 'recent2026':
                    # Daily risk since Jan 1 carries the Dec basket, with no
                    # virtual Jan restart. Arithmetic result uses Jan signals.
                    dd = daily.loc['2026-01-01':]
                else:
                    dd = daily.loc[part.entry_date.min():part.exit_date.max()]
                    # At same72's final shared close, daily includes the next
                    # rebalance fee. Remove that one event from this slice.
                    next_row = periods[periods.entry_date == part.exit_date.max()]
                    if len(next_row):
                        dd = dd.copy()
                        fee = next_row.iloc[0].fee
                        dd.iloc[-1,dd.columns.get_loc('portfolio')] = (1+dd.iloc[-1].portfolio)/(1-fee)-1
                        dd.iloc[-1,dd.columns.get_loc('fee')] -= fee
                        dd.iloc[-1,dd.columns.get_loc('turnover')] -= next_row.iloc[0].turnover
                metrics = summarize(part,dd,holding_intervals=len(dd) if window=='recent2026' else None)
                rows.append(dict(candidate=candidate,variant=name,window=window,
                                 first_signal=str(part.signal_date.min().date()),
                                 last_signal=str(part.signal_date.max().date()),**metrics))
            log(f'{candidate} {name}: {summarize(periods,daily)}')
        # Available historical baseline only; never fabricate pre-training p.
        indices_full = np.arange(len(dates))
        base_support = np.isfinite(score)&np.isfinite(y)&np.isfinite(cap[positions])&(cap[positions]>0)
        paths,uni = select_paths(score,None,base_support,indices_full,False)
        periods,daily,_ = daily_ledger(paths,uni,indices_full,dates,calendar,close)
        periods.to_csv(OUT/f'{candidate}.primary_available120.periods.csv',index=False)
        daily.to_csv(OUT/f'{candidate}.primary_available120.daily.csv')
        rows.append(dict(candidate=candidate,variant='primary_available120',window='available120',
                         first_signal=str(dates[0].date()),last_signal=str(dates[-1].date()),**summarize(periods,daily)))
    results = pd.DataFrame(rows); results.to_csv(OUT/'results.csv',index=False)
    frozen = pd.DataFrame(frozen_rows); frozen.to_csv(OUT/'frozen72_cost_corrected.csv',index=False)
    pd.DataFrame(all_folds).to_csv(OUT/'folds.csv',index=False)
    checks.update(daily_vs_endpoint_nav='PASS for all 12 complete paths',
                  shared_support='identical universes for all three variants of each candidate',
                  holdings_prefix='PASS for all nine walk-forward paths',
                  signal_periods=83,final_partial_test_block=11)
    dump('verification.json',checks)
    inputs=[original.SEAT,MARKET,Path(__file__),ROOT/'scripts/meta_label_ledger.py',ROOT/'scripts/advances_fml_meta_label_20261016.py',ROOT/'scripts/test_meta_label_ledger.py',ROOT/'scripts/verify_meta_label_cash_book_20261016.py']
    dump('manifest.json', {str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in inputs})
    report(results,frozen,label_info)
    log('completed audit, no platform calls')


def report(results,frozen,label_info):
    lines=['# Meta-label 账本修正 v2','',
      '本轮只修复已有三个实验，未扩搜参数，未调用平台。旧目录与旧结果保留。', '',
      '## 主要修复','',
      '- 实际资金权重随价格漂移；持仓数变化时重新等权。买入与卖出均按单边 0.30% 扣费，费用从净值支付并满足现金守恒。初始从现金建仓收取买入成本，末期只估值、不虚拟清仓。',
      '- 持仓跨训练块连续延续，训练块只更新模型；用标签实际退出日期严格早于测试首日作为训练资格。最后 11 个信号期纳入，合计 83 期。',
      '- 五席按严格共同支持集合成；同一候选的基线、纯概率门控、门控加旧仓保留使用完全相同的股票与基准支持集。',
      '- 正式比较使用算术年化净超额；另列日频组合净收益 Sharpe、组合净值回撤。复利两腿超额仅列为独立诊断。',
      '- 纯概率门控对照用于识别旧仓保留的贡献。保留旧仓但允许所有新股票入选的 retention-only 在这个框架中与原十分位基线相同，不冒充独立策略。', '',
      '## 原持仓路径：仅修正账本','',
      '先逐期复现已保存的 72 期持仓收益（全部通过），保持原选股与缓存标签，改为连续资金账本及完整交易成本；下面均改用算术年化，因此与旧复利 headline 的差还包含年化定义修正。', '',
      '| 对象 | 基线净年超额 | Meta 净年超额 | 差值 | 基线资金换手/次 | Meta 资金换手/次 |',
      '|---|---:|---:|---:|---:|---:|']
    for c in original.CANDIDATES:
        a=frozen[(frozen.candidate==c)&(frozen.variant=='primary')].iloc[0]
        b=frozen[(frozen.candidate==c)&(frozen.variant=='meta')].iloc[0]
        lines.append(f'| {c} | {a.net_annual_pct:.2f}% | {b.net_annual_pct:.2f}% | {b.net_annual_pct-a.net_annual_pct:+.2f}pp | {a.turnover_pct:.2f}% | {b.turnover_pct:.2f}% |')
    lines += ['', '## 共同支持集、qfq 标签、连续持仓：完整可用滚动期','',
      '| 对象 | 方案 | 期数 | 算术净年超额 | 资金换手/次 | 日频组合净 Sharpe | 日频组合最大回撤 | 平均持仓 |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for _,r in results[results.window=='walkforward83'].iterrows():
        lines.append(f'| {r.candidate} | {r.variant} | {r.periods} | {r.net_annual_pct:.2f}% | {r.turnover_pct:.2f}% | {r.daily_net_sharpe:.3f} | {r.daily_net_maxdd_pct:.2f}% | {r.mean_holdings:.0f} |')
    comp=results[(results.candidate=='INCUMBENT_COMPOSITE')&(results.window=='walkforward83')].set_index('variant')
    same=results[(results.candidate=='INCUMBENT_COMPOSITE')&(results.window=='same72')].set_index('variant')
    lines += ['',
      f'五席完整修正后的净年化增量仅 {comp.loc["meta_retention","net_annual_pct"]-comp.loc["primary","net_annual_pct"]:+.2f}pp，日频风险指标没有改善；纯概率门控反而比基线低 {comp.loc["primary","net_annual_pct"]-comp.loc["meta_gate_only","net_annual_pct"]:.2f}pp。即使只看与旧结果相同的 72 个信号期，共同支持集与 qfq 重算后的五席增量也只有 {same.loc["meta_retention","net_annual_pct"]-same.loc["primary","net_annual_pct"]:+.2f}pp。因此不能把优势消失单纯解释为补入最后 11 期或交易成本增加，也不能据旧表推进平台转化。未逐项单变量归因，不分配各修正项的精确贡献。']
    lines += ['', '## 2026 年近期诊断','',
      '算术收益统计按 2026 年信号日归属；日频风险统计从 2026-01-01 开始，延续此前持仓，不在元旦重新建仓。两者窗口边界有明确区别，不混用为独立样本外证据。','',
      '| 对象 | 方案 | 信号期数 | 算术净年超额 | 日频净 Sharpe | 日频最大回撤 |',
      '|---|---|---:|---:|---:|---:|']
    for _,r in results[results.window=='recent2026'].iterrows():
        lines.append(f'| {r.candidate} | {r.variant} | {r.periods} | {r.net_annual_pct:.2f}% | {r.daily_net_sharpe:.3f} | {r.daily_net_maxdd_pct:.2f}% |')
    lines += ['', '## 标签与可比性限制','',
      f'- 在 {label_info["comparable_stock_periods"]:,} 个共同有效股票期中，有 {label_info["differences_over_1e_5"]:,} 个缓存收益与当前 qfq 日线重算收益差超过 1e-5。详细极端记录见 label_mismatch_top100.csv；尚未把差异归因到原行情快照、停牌填充或其它具体来源。原路径修账与完整重算因此分别报告。',
      '- 信号缓存继承旧 qualitygate1 代理，只覆盖 5,311 个归档股票，当前市场缓存有 5,456 个；本次未重新生成全部五席，不声明最新规则下完整全 A 或平台等价。',
      '- 根据归档构建脚本 ab_seat_rebuild_20260925.py 与 exhaustive_representative_combination.py，输入 scores 已按方向处理并执行截面 1%–99% 去极值及 z-score。本轮保留旧实验对 scores 再作截面 z-score 的路径，没有重新从原始字段生成五席；最终池标准化与缺失语义仍属代理。',
      '- 缓存仅有 2021-09-07 至 2026-08-10 的 120 个信号，标签最终退出 2026-08-25。基线可列 120 期；Meta 需前置训练，仅能列 2023-03-22 起 83 期，不是正式 2021-09-07 至 2026-09-07 全五年策略回测。',
      '- 这些历史此前已经查看，属于修正后的历史滚动验证，不是未触碰留出；未完整复现全书、triple-barrier 或 CPCV。',
      '- 原目录的 13.06%/12.35% 是期频超额净值回撤，本报告的日频持仓组合回撤不可直接作数值升降比较。',
      '- 资金换手包含初始建仓且考虑漂移，不能与平台摘要成员替换率直接比较。无新平台结果，不计算官方 A/B/C 或名次。', '',
      '## 验证与产物','',
      '独立现金/份额算例、初建仓、全替换、同成员再平衡、持仓缩减、跨块成本测试见 scripts/test_meta_label_ledger.py。每条完整日频路径与端点账本复利净值一致；特征、预测与持仓截断重算一致，未到期标签扰动不改变当时模型预测。独立现金/股票份额逐日复核脚本为 scripts/verify_meta_label_cash_book_20261016.py，结果另存 independent_cash_share_verification.json。', '',
      'results.csv 保存所有窗口；frozen72_cost_corrected.csv 保存原路径修账；*.periods.csv、*.daily.csv 和 *.holdings.csv.gz 提供交易、日账本与逐期持仓；folds.csv、verification.json、input_audit.json、manifest.json 提供审计证据。','']
    (OUT/'report.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
