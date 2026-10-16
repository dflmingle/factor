# star_coin_prediction 原生平台整池持仓诊断方案

## 目的

把冻结的 `v20+m02w18` 十腿复刻池一次性放到 PandaAI 原生字段上，比较平台返回的最新一期 Top20 与对手 `20261009` 持仓的 Top20 和排序；同时保留本地复现的 502 只持仓重合率作为基线。该回测是 peer-aligned diagnostic，不改现役比赛池，也不把结果当成官方完整持仓重合。

## 唯一候选

- 候选名：`F-SCH1016-01`
- 代码：[star_coin_frozen_pool.py](star_coin_frozen_pool.py)
- 候选清单：[candidates.txt](candidates.txt)
- 来源：`star-coin-alpha-transfer-20261016-v2/candidate.json`, `v20+m02w18`
- 席位：10，方向 `[-1,-1,-1,-1,+1,-1,-1,-1,-1,+1]`，等权平均；第 6、7 席均为 `MARKET_CAP`，按冻结池保留
- 原始公式：见 [manifest.json](manifest.json) 的 `formulas`
- 原生字段：`close/open/high/low/volume/amount/turnover/market_cap/book_to_market_ratio_lf/ratio_ep_ttm/ratio_cfp_ttm/ratio_sp_ttm`

## 回测参数

- 窗口：`20211008..20261008`（信号日五年，专门对齐对手 `20261008` 信号、`20261009` 生效）
- 调仓：5 日
- 分组：10 组
- 成本：单边 0.30%，提交参数 `--round-trip 0.003`
- 候选数：1
- 预估消耗：约 4–8 点，预算上限 8 点

## 预提交检查

- `platform_precheck.py`：通过
- `repaint_check.py`：通过；242 个截断后信号日，逐日相关均值/最小值均为 1.0，最大差 0
- 独立 AST/端口等价：10/10 腿通过，组合最大绝对差 0
- 本地同日基线：ST 过滤后前 20 与对手重合 9/20；完整 487/502 = 78.0876%（只能作为本地基线）

## 结果解释边界

此前平台返回没有完整持仓 CSV，只给最新一期 Top20，因子节点也可能为空。因此本轮即使成功，也只能回答“平台原生字段下 Top20/排序是否更接近”；不能宣称得到 502 只完整重合率。若平台仍不提供 CSV，就不把 Top20 外推为全持仓。
