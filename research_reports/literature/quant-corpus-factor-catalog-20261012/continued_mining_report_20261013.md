# 继续挖掘与本地复现（2026-10-13）

本轮继续从策略库中筛选尚未正式复现的候选，仍使用统一全 A/qfq/`total_mv`/label-1/10 日调仓/10 组/0.30% 单边成本口径。未调用平台。

## 新增结果

| 候选 | 五年净超额 | 市值/反转残差五年 | 近期净超额 | 结论 |
|---|---:|---:|---:|---|
| 质量评分九因子 | −2.35% | +0.67% | +0.50% | 不通过 |
| 流动性盈利现金流约束 | −4.34% | −1.93% | +9.29% | 近期强、五年不稳 |
| 基本面三角变化 | +0.44% | +1.37% | +6.36% | 增量不足 |
| APARP | 无有效期 | 无有效期 | 无有效期 | 账面字段覆盖不足 |
| 低存货压力 | −2.93% | −1.15% | −4.37% | 淘汰 |
| 营运资本×现金流质量 | 无有效期 | 无有效期 | 无有效期 | APARP 字段阻塞 |
| 小盘+PB+PE+PCF | **+8.61%** | −4.85% | **+7.64%** | 主要是市值暴露 |
| 低 PB/PE/PCF | +1.30% | −4.35% | +4.70% | 独立增量不足 |
| 低估值×ROE | −1.22% | −2.13% | +4.27% | 不通过 |
| 低估值×低换手 | +2.56% | +0.33% | +5.60% | 独立增量不足 |

## 当前判断

新发现的“小盘+PB+PE+PCF”是本轮唯一达到五年 +5% 的新公式，但拆掉市值腿后只剩 +1.30%，市值/反转残差为负。因此它可以作为已有市值/价值簇的增强版本留在候选池，暂不能定义为独立新簇，也不建议直接上平台。

APARP 方向的账面字段在现有缓存中有效覆盖不足，连续评分没有达到 100 个有效标的，已标记为阻塞；没有用普通 PB 或 ROE 偷换该定义。

## 结果目录

- [source21](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source21-20261013/results.csv)
- [source22](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source22-20261013/results.csv)
- [source23](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source23-20261013/results.csv)
- [source24](/data/games/factor_/research_reports/platform_alignment/quant-corpus-semantic-source24-20261013/results.csv)

所有候选和失败结果均保留在各自的 `recipe_manifest.json` 与双窗口明细中。
