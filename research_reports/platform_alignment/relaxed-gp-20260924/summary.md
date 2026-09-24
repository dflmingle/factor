# 宽字段 GP 挖掘 + 放宽换手重筛（2026-09-24，本地零平台算力）

目标：用**因子挖掘算法**（AlphaPROBE GP）在**显著更宽的字段集**上找新的好因子，筛选口径
按用户新规定——**不以低换手本身为目标**，按净额/近段净额/S_i 看单因子，换手分档保留。

## 一、先修了两个真卡点（都不改结果口径）

1. **字段失败登记表版本错位**。规则已升 `qualitygate4`，登记表仍写 `qualitygate3`，
   `load_field_exclusion_policy` 直接抛错，所有走 `resolve_terminal_fields` 的 GP 都起不来。
   处理：`--allow-stale-failure-registry`（默认**仍严格拒绝**），不一致会写进 `gp_run.json`
   的 `search.failure_registry_policy`。两个版本的 `blocked_fields` 都是空（拉黑规则是
   "≥2 条 >5pp 且没有任何 ≤5pp 证据"），所以本次放宽不改变可搜字段集。
2. **命名字段面板缓存只有 24 槽（真正的规模瓶颈）**。实测：单个命名字段首次物化
   **>3 秒**（`probe/cache_probe.log`），而字段集有 374–1152 个 → 每次求值都在重算字段。
   首轮用 1,152 字段满预算（pop 1000 × 40 代）跑了 25 分钟**一代都没出**，只能杀掉。
   处理：把缓存拆成两层——CPU 数组缓存（`--field-array-cache-size`，默认 512）与
   GPU 面板缓存（`--field-cache-size`，默认 24）。改完后同一批 374 字段 pop 1000 × 40 代
   约 30 分钟跑完（含一次性冷启动），单代从 >25 分钟降到秒级。
   另外 `from_aligned_frame` 是 `cls.__new__` 建对象、没有 `field_cache_size` 属性，
   已改成 `getattr(..., 24)` 兜底。
   （`scripts/field_cache_probe_20260924.py`、`probe/cache_probe.log`）

## 二、批次

字段集：`wider-field-search-20260923/fields.txt`（**374 个**本地可算字段；此前所有满预算跑法
都只用 **19 个** verified 字段）。去 size 对照用 `fields_nosize.txt`（357 个，剔掉
`market_cap*` / `*market_val*` / `a_share_mv*` / `amv*` / `ratio_market_cap_*` 共 17 个）。

通用参数：`full_a` + qfq、`20210907..20260907`、10 日调仓、10 组、0.30% 单边成本、
`--aligned-min-periods 100`、novelty registry 排除历史 51,783 条签名。

| run | 目标函数 | pop × 代 | 说明 |
| --- | --- | ---: | --- |
| `net_wide_s9801..s9804` | `aligned_net_excess` | 1000 × 40 | 净额导向 |
| `net_nosize_s9831/9832` | `aligned_net_excess`（357 字段） | 1000 × 40 | **去 size 对照** |
| `front_wide_s9841` | `aligned_ic_frontier` | 1000 × 40 | IC 前沿 |
| `eff40_s9811` | `aligned_ic_efficiency`（换手上限 40%、净额下限 15%） | 800 × 30 | 放宽换手 |
| `eff60_s9851` | `aligned_ic_efficiency`（换手上限 60%） | 800 × 30 | 更宽换手 |
| `sizeneut_wide_s9821` | `aligned_size_neutral_net` | 800 × 30 | size 中性化目标 |

共 **42,293 条公式**（去重后），健康口径（有效期 ≥100、覆盖率 ≥50%）**40,511 条** →
`records_healthy.csv`。`launch.sh` / `launch2.sh` / `launch3.sh` 可复现。

## 三、筛选口径（重要：不能用记录里的 turnover 直接分档）

记录里的 `turnover/net` 是**各目标函数自己的口径**：`aligned_size_neutral_net` 记录的是
**中性化之后**的换手/净额，直接分档会把中性化噪声当成"低换手"。所以
`scripts/relaxed_gp_screen_20260924.py` 对 253 个候选**逐个重算**，且组合构造/换手/成本/年度化
全部调用 GP 内部同一条代码路径（`AlignedNetExcessContext.score / ic_series_stats`，
含可交易域掩码、头部十分位、10 日调仓、0.30% 单边）。

复算验证：五席基线池 → `NA 0.239 / NC 1.0 / Comb 0.4978 / 净额 23.8% / 池换手 14.3%`，
与 `GOAL.md` 记录的基线一致。

额外补了两件平台口径相关的事：
* **S_i 口径**：GP 内部用 Pearson IC 序列算 ICIR/胜率，253 个候选里 179 个 S_i 恰为 0
  （日度 Pearson IC 长期贴 ±0.02，但秩 IC 有 0.05–0.11，收益集中在头部十分位）。
  平台口径的 ICIR 来自 RankIC 序列，因此批内另算 `s_i_rank`（RankIC 的 ICIR × 胜率）。
* **size 防作弊**：与 SIZE 席位的日截面秩相关 `corr_size`，以及桶内（20 桶）size 中性化净额
  `neu_net`。

输出：`screen2/screened_candidates.csv`（253 行，含分档、全期/近段净额、S_i、corr_size、
`neu_net`、加第 6 席的池级 ΔComb 参考列）。8 路并行脚本 `run_screen_shards.sh`。

## 四、结果

| 档位 | 全期净额 | 近段 2026 净额 | 最近 12 期 | size 相关 |
| --- | ---: | ---: | ---: | ---: |
| ≤30%（63 条） | 19.4–22.0% | 13–19% | 6–8% | **0.99–1.00** |
| 30–40%（35 条） | 13.2–16.0% | 12–23% | 8–19% | 0.38–0.84 |
| 40–60%（90 条） | 4.8–14.5% | 9–28% | 4–25% | 0.02–0.85 |
| >60%（65 条） | 1–11% | ≤14% | ≤14% | 0.0–0.48 |

代表候选（完整表见 CSV）：

| 档位 | 公式 | 净额 | 换手 | 近段2026 | S_i(RankIC口径) | corr_size | neu_net | ΔComb/月 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 40–60% | `Inv(Sub(a_share_market_val,TsStd(TsMax(is_operate_profit,10),30)))` | 12.5% | 43.7% | **27.7%** | 0.0039 | 0.33 | 3.7% | −2303 |
| 30–40% | `Inv(Sub(market_cap_3,TsDelta(TsVar(TsWMA(bs_accu_depr,10),20),10)))` | 15.6% | 33.5% | 22.9% | 0.0075 | 0.63 | 4.9% | −5012 |
| 40–60% | `Div(Div(Div(Div(Div(TsSkew(oper_total_asset_turnover_ttm,50),cal_20d_amt_ma),bs_total_assets),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)` | 4.8% | 48.6% | 12.9% | 0.0000 | **0.03** | 3.6% | — |
| ≤30% | `Inv(Greater(a_share_market_val,Log(Sub(Greater(lma20,TsVar(Greater(oper_total_asset_turnover_ttm,net_profit),40)),is_oth_affecting_np))))` | **22.0%** | 17.0% | 19.1% | 0.0129 | **1.00** | 7.3% | −7752 |

## 五、结论

1. **"净额被 size 订死"在低换手区成立，且有对照实验证据**：≤30% 档净额前列
   `corr_size` 全是 0.99–1.00；把 17 个市值/股数字段整组删掉重跑（同目标同预算），
   该档最好记录从 **25.2% 掉到 20.4%**，且仍是"账面价值 ÷ 成交额缩放"这类隐式 size 替代。
   即：低换手区能持续付钱的横截面结构就是市值水平本身，不是搜索范围不够。
2. **放宽换手确实能挖到不一样的东西**：40–60% 档出现 `corr_size 0.33` 且近段净额 **27.7%**
   的候选，以及 `corr_size 0.03` 的 size 无关候选（代价是全期净额只有 4.8%）。
   这正是用户"换手放宽些、牺牲换手换 NC 上限"的路线。
3. **单因子口径与池级口径分离**：253 个候选作为第 6 席的池级 ΔComb **全为负**（最好 −2303 分/月），
   原因是它们要么与现有席位高相关、要么换手抬升池换手。按用户新口径，这只作参考列，
   不当作一票否决。
4. **待办**：候选公式大量使用 catalog/未验证字段名（`cal_20d_amt_ma`、`bs_*`、
   `is_operate_profit`、`a_share_market_val` 等），平台可能拒收或口径不同——
   上平台测试本身就是这道字段验证。已按项目规矩把候选与算力预算报给用户等待批准，
   **本轮未消耗任何平台算力**。

## 六、文件

- `launch*.sh`、`run_screen_shards.sh`、`fields_nosize.txt`：可复现的启动脚本与字段集
- `records_healthy.csv`：40,511 条健康记录的合并表（含 run/objective 标记）
- `screen2/screened_candidates.csv`：253 个候选的重算结果（本批次交付物）
- `screen2/shard*.log`：分片筛选日志
- `probe/cache_probe.log`：字段面板冷/热取用实测
- `*/run.log`：各 run 的完整日志（含 `active=374` 与逐代 cache 统计）
- 未入库（体积大、可重建）：`*/gp/field_coverage.json`、`gp_run.json`、`generation_*.json`、
  逐 run 的 `aligned_ic_records.json`、`bench/`、`smoke*/`、`screen/`、`screen_wave2/`
