# python-composite-audit（2026-09-29）：Python 模式池合成因子未来泄漏审计

## 0. 背景

`_date_level` 用 `str(v)[:4].isdigit()` 兜底探测日期层，在平台 [date, symbol] 索引下
把 symbol（"000001.SZ"）误判为日期层 → 席位做成按股票的**全样本**（含未来）时序 z-score，
净超额从真实 20.30% 虚高到 46.72%（归因见 `../lookahead-attrib-20260929/summary.md`）。
本审计回答：历史上还有哪些平台 Python 提交中招；并固化防线。

## 1. 审计方法与范围

- 扫描全部 **70 条平台 Python 模式运行**的内嵌代码（`*.results/*.json` → `nodes[*].code`），
  检索：① 取值格式探测索引层（`str(...).isdigit()`）；② `groupby(level=1)`/symbol 层全样本标准化。
- 动态"截断重算"自检：`scripts/repaint_check.py` 把面板截到 `2025-06-30` 重算候选，
  对比 `2024-06-30..2025-06-30` 历史值；因果因子必须逐位不变。

## 2. 审计结论

**中招的只有 09-28 / 09-29 两批、3 个唯一候选文件（4 条运行）**：

| 批次 | 候选 | factor_id | 平台实测（虚高，作废） | 费用 |
|---|---|---|---|---:|
| pool-live-20260928 | POOL5-LIVE | `6ab9da899e9d797cfb2d00eb` | RankIC .1678 / 净 46.72% / T 24.10% / SR 2.06 | 6.0 |
| pool-live-20260928 | POOL6-LEGMIX7 | `6ab9da8ab8f0d75493c83b10` | RankIC .1745 / 净 42.27% / T 32.88% / SR 1.96 | 6.0 |
| pool-live2-20260929-py | POOL5-CTRL（同文件重跑） | `6abb6f23b8f0d75493c84104` | 与 09-28 逐位一致（同一 bug） | 6.0 |
| pool-live2-20260929-py | POOL6-LAMD10-K5V2 | `6abb6fc32d2f6998fc1c03e5` | RankIC .1709 / 净 43.32% / T 28.45% / SR 1.99 | 6.0 |

另：09-29 首轮误用 formula 模式提交同一 .py（未加 `--mode python`），2 条即败扣 4.0（提交器用法问题，非本 bug）。

**未中招**：09-21～09-23 的 9 个 Python 合成池（pool-cand*/pool-6seat/pool-8seat/pool-alternatives/
pool-base4/pool-best/pool-replace-growth/pool-3win 等）归一化全部硬编码 `groupby(level=0)`，
平台 [date, symbol] 下 level 0 = 日期截面 → 几何正确。
佐证：pool-candCD（`6ab254bf8b01f62dc5147d39`）SR 1.0648 / RankIC .0919 与平台池记录 F-P260922-08 完全一致。

## 3. 本地修正与防线验证

| 文件 | precheck 静态 | repaint 截断自检（n=400） |
|---|---|---|
| `pool5-live-20260928.py` | OK | **PASS**（242 期，max|Δ|=0） |
| `pool6-legmix7-20260928.py` | OK | **PASS**（max|Δ|=0） |
| `pool6-lamd10k5v2-20260929.py` | OK | **PASS**（max|Δ|=0） |
| 旧 bug 版对照（从 09-28 raw 提取）`buggy_pool5_live_control.py` | FAIL | **FAIL**（逐日相关均值 .955 / 最低 .936，max|Δ| 2.9σ） |

**新增防线**：

1. `scripts/platform_precheck.py`：Python 候选静态拦截 (a) 取值格式探测索引层、(b) level=1/symbol 全样本标准化（注释/字符串不误报）。
2. `scripts/repaint_check.py`：提交前必跑的截断重算自检，PASS 才可提交（exit code 0/1）。
3. `AGENTS.md` 增补规则（见"Python 合成因子（提交前防未来泄漏）"）。

## 4. 重测（2026-09-29 已完成，16.0，余额 1542.12 → 1526.12）

| 候选 | 平台结果（正确几何） | 结论 |
|---|---|---|
| POOL5-CTRL-RETEST | 净 20.30% / 换手 13.39% / RankIC .0919 / ICIR .3675 / SR 1.0648 | **与池记录 F-P260922-08 逐位一致 ⇒ 修复验证通过** |
| POOL6-LAMD10K5V2-RETEST | 净 19.53% / 换手 18.16% / RankIC .1019 | C 免费门槛升到 rc≥.80；rc=.75 → ΔComb −469/月 ⇒ 不免费 |
| POOL6-LEGMIX7-RETEST | 净 19.44% / 换手 22.58% / RankIC .1048 | 门槛 rc≥.964 不可达 ⇒ 确定负面，放弃加席 |

详见 [`../python-composite-retest-20260929/summary.md`](../python-composite-retest-20260929/summary.md)。
