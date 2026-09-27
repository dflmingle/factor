import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
root = Path(r"D:\factor"); R = root/"research_reports"/"platform_alignment"; G = R/"gp-platform-tests-20260925"

reg_path = R/"factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))
reg["probe_evidence_20260925"] = {
    "purpose": "定位 K020（round5/6b）平台端整体方向反转的来源",
    "method": "单字段平台探针（direction=1）+ 本地自算单字段 RankIC（2021-09~2026-09，每 10 个交易日采样，全 A，10 日前瞻收益，scipy.spearmanr，≥100 名有效）",
    "probes": {
        "RATIO_BM_LYR": {"platform_rank_ic": 0.0659, "platform_monotonicity": 0.88, "platform_p_value": 0.0883,
                          "platform_turnover": 0.0582, "local_rank_ic": 0.0613, "local_t": 4.35,
                          "local_pos_ratio": 0.616, "verdict": "SAME_SIGN_NOT_FLIPPED",
                          "run_id": "6ab6745845ce44aed9d15652", "cost": 2.0},
        "CAL_30D_PRICE_VOL_CORR": {"platform_rank_ic": -0.0517, "platform_monotonicity": 0.80, "platform_p_value": 0.0061,
                                    "platform_turnover": 0.6139, "local_rank_ic": -0.0476, "local_t": -5.67,
                                    "local_pos_ratio": 0.296, "verdict": "SAME_SIGN_NOT_FLIPPED",
                                    "run_id": "6ab6777b812a2a13b9644c7b", "cost": 2.0,
                                    "note": "首次提交（factor 6ab67530…）平台卡死 status=8 零节点，未计费；换新 factor 一次成功。"},
    },
    "local_k020_rebuild": {"rank_ic": 0.0441, "t": 4.86, "dates": 131,
                            "note": "用原始 qfq/daily_basic/balancesheet 独立复算 K020（B/M ÷ (corr30/MA40(corr30)) ÷ 20日均额 ÷ 总资产），"
                                    "与本地管线 +0.0360 同号；平台 -0.0352 与之相反 → 反转发生在组合层，不在单字段。"},
    "conclusion": "两个嫌疑字段单独在平台与本地**同号同量级**，均未翻转；K020 的整体反转来自 "
                   "`1/(CAL_30D_PRICE_VOL_CORR/MA(CAL_30D_PRICE_VOL_CORR,40))` 这类**有符号且均值近零的序列做分母**的交互结构——"
                   "其排序对平台端滚动窗口/并列/数值处理极敏感，本地不可复现。",
    "action_rule": "候选公式中出现'相关系数等有符号近零序列做分母'的结构时：① 平台方向必须实测；② 优先避开该结构，"
                   "改用具明确符号含义或有界的量（如 |corr|、RANK、ZSCORE）替代。",
    "platform_display_note": "平台返回的 top 因子值统一归一化并四舍五入到 4 位小数（K021×1e18、K020 的 top20 全为同一显示值；"
                              "K015、corr30 探针显示值各异）→ top 列表并列属显示层现象，不能据此推断底层并列或钳制。",
    "billing_finding": "计费按公式复杂度分档：单字段简单公式一次 **2.0**（RATIO_BM_LYR 51.2s、CAL_30D_PRICE_VOL_CORR 各 2.0），"
                       "复杂多级公式 4.0；失败/卡死 0。",
}
for rec in reg["unacceptable_records"]:
    if rec["id"].endswith("K020-cand0110-S27"):
        rec["attribution"]["cause_codes"] = ["signed_denominator_interaction_not_reproducible"]
        rec["attribution"]["cause_details"].append(
            "2026-09-25 探针定位：两个嫌疑字段（RATIO_BM_LYR、CAL_30D_PRICE_VOL_CORR）单独在平台与本地同号，"
            "本地独立复算 K020 也得 +0.0441（与本地管线同号）→ 反转来自组合项（有符号近零序列做分母），非字段符号。"
            "平台方向以 direction=0 可用（net +13.28%），但结构脆弱，池内使用需谨慎。")
reg["field_evidence_notes"]["ratio_bm_lyr"] = (
    "2026-09-25 单字段探针：平台 RankIC +0.0659 vs 本地自算 +0.0613（同号同量级）→ 字段本身未翻转，可用。")
reg["field_evidence_notes"]["cal_30d_price_vol_corr"] = (
    "2026-09-25 单字段探针：平台 RankIC -0.0517 vs 本地自算 -0.0476（同号同量级）→ 字段本身未翻转。"
    "但它参与 `x/MA(x,40)` 作分母时，K020 在平台端整体反转（见 probe_evidence_20260925）→ 该结构脆弱，需实测方向。")
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry updated | records:", len(reg["unacceptable_records"]), "| keys:", len(reg.keys()))

gp = root/"GOAL.md"; g = gp.read_text(encoding="utf-8")
anchor5 = "## 五、唯一可主动改变的杠杆"
item20 = """20. **方向翻转源定位（2026-09-25，4 算力）：两个嫌疑字段都没翻转 → 反转发生在"组合项"，属平台不可复现的脆弱结构**：
   - 单字段平台探针 + 本地自算对照（135~138 个采样日、全 A、10 日前瞻）：
     `RATIO_BM_LYR` **+0.0659 vs +0.0613**（同号）；`CAL_30D_PRICE_VOL_CORR` **-0.0517 vs -0.0476**（同号）→ **均未翻转**。
   - 本地用原始数据独立复算 K020 因子：**RankIC +0.0441**（与本地管线 +0.0360 同号），平台却是 -0.0352
     → 反转在**组合层**：`1/(CAL_30D_PRICE_VOL_CORR/MA(…,40))` 这类**"有符号且均值近零"序列做分母**的结构，
     排序对平台端滚动/并列/数值处理极敏感，本地不可复现。
   - **新规则**：候选公式里若出现"相关系数等有符号近零序列做分母"，平台方向与排序都必须实测；**优先避开该结构**
     （改用具明确符号含义或有界的量，如 `|corr|`、`RANK`、`ZSCORE`）。
   - 计费发现：**单字段简单公式一次 2.0 算力**（复杂多级公式 4.0），失败/卡死 0。
   - 附注：平台返回的 top 因子值统一归一化到 4 位小数（多次运行 top20 并列属显示层现象，非钳制）。

"""
assert g.count(anchor5) == 1
g = g.replace(anchor5, item20 + anchor5, 1)
bill_anchor = "| 2026-09-25 | round6：K020 direction=0 复测（两次平台卡死未计费；换新 factor 成功 4.0） | 4 | 1680.12 |\n"
assert g.count(bill_anchor) == 1
g = g.replace(bill_anchor, bill_anchor +
  "| 2026-09-25 | round7：单字段探针 ×2（RATIO_BM_LYR 2.0 / CAL_30D_PRICE_VOL_CORR 2.0；含一次卡死未计费） | 4 | 1676.12 |\n", 1)
gp.write_text(g, encoding="utf-8"); print("GOAL.md updated (item20 + 1676.12)")

r7 = """# GP 新簇候选平台复现 · 第七轮（2026-09-25 晚，方向翻转源定位，4 算力）

## 一、目的与设计

round5/6b 发现 K020 在平台端整体方向与本地相反（|RankIC| 一致）。唯一用到、且未被 K015/K021 覆盖的字段是
`RATIO_BM_LYR` 与 `CAL_30D_PRICE_VOL_CORR`。因此各做一个**单字段探针**，并与本地自算 RankIC 对照。

本地对照口径：qfq 日线 + daily_basic(总市值) + balancesheet(年报名义值/总资产, PIT by f_ann_date)，
2021-09~2026-09 每 10 个交易日采样（135~138 个日期），全 A，10 日前瞻收益，scipy.spearmanr，≥100 名。

## 二、结果：两个字段都没翻转

| 探针 | 平台 RankIC | 本地 RankIC | 判定 |
| --- | ---: | ---: | --- |
| `RATIO_BM_LYR` | **+0.0659**（mono 0.88, p=0.0883, 换手 5.82%） | **+0.0613**（t=4.35, 61.6% 正） | **同号同量级，未翻转** |
| `CAL_30D_PRICE_VOL_CORR` | **-0.0517**（mono 0.80, p=0.0061, 换手 61.39%） | **-0.0476**（t=-5.67, 29.6% 正） | **同号同量级，未翻转** |

- 过程：`CAL_30D_PRICE_VOL_CORR` 首次提交平台卡死（status=8、零节点、**未计费**），换新 factor 一次成功。
- 计费：两个探针各 **2.0**（单字段公式比复杂公式便宜一半）→ 余额 1680.12 → **1676.12**。

## 三、那 K020 为什么反转？——组合项

本地用原始数据**独立复算** K020 因子（B/M ÷ (corr30/MA40(corr30)) ÷ 20日均额 ÷ 总资产）：

| 口径 | RankIC |
| --- | ---: |
| 平台（round5） | **-0.0352** |
| 本地管线（screened_candidates.csv） | +0.0360 |
| 本地独立复算（本轮） | **+0.0441**（t=4.86, 131 个日期） |

→ 两个本地实现彼此一致、平台相反：**反转发生在组合层**。

机制判断：`1/(CAL_30D_PRICE_VOL_CORR/MA(CAL_30D_PRICE_VOL_CORR,40))` 的分母是**有符号且均值近零**的序列
（相关系数在 0 附近摆动），该项的排序对平台端的滚动窗口、并列处理与数值细节极敏感，本地不可复现。

**新规则**：候选公式中若出现"相关系数等有符号近零序列做分母"，方向与排序**必须实测**，且**优先避开该结构**
（改用具明确符号或有界的量：`|corr|`、`RANK`、`ZSCORE`）。

## 四、附带发现

- 平台返回的 top 因子值**统一归一化并四舍五入到 4 位小数**（K021×1e18、K020 的 top20 全为同一显示值；K015、corr30 探针显示值各异）
  → top 列表并列属显示层现象，**不能**据此推断底层并列或钳制。
- 计费分档：**单字段公式 2.0**，复杂多级公式 4.0，失败/卡死 0。

## 五、复现入口

- 候选：`round7/candidates_panda.txt`（B/M + 卡死一次）、`round7b/candidates_panda.txt`（corr30 重跑成功）
- 原始响应：`round7/candidates_panda.results/*.json`、`round7b/candidates_panda.results/6ab6777b812a2a13b9644c7b.json`
- 本地对照：`scripts/_local_field_rankic2.py`（单字段）、`scripts/_local_k020_rebuild.py`（K020 复算）
"""
(G/"round7"/"summary.md").write_text(r7, encoding="utf-8")

ms = G/"summary.md"; s = ms.read_text(encoding="utf-8")
s += """

## 十三、第七轮（2026-09-25 晚，方向翻转源定位，4 算力）

- 两个嫌疑字段的单字段探针与本地对照**均为同号**：`RATIO_BM_LYR` +0.0659 vs +0.0613；`CAL_30D_PRICE_VOL_CORR` -0.0517 vs -0.0476
  → **字段都没翻转**；本地独立复算 K020 得 +0.0441（与本地管线同号）→ 反转在**组合层**。
- 机制：`1/(corr/MA(corr,40))` 这类**有符号近零序列做分母**的结构平台端不可复现 → 新规则：优先避开，方向必须实测。
- 计费发现：单字段公式 **2.0**、复杂公式 4.0。花费：1680.12 → **1676.12**（4.0）。
"""
ms.write_text(s, encoding="utf-8")
desk = Path(r"C:\Users\58302\Desktop\新簇候选平台验证-20260925.md")
desk.write_text(s + "\n\n---\n\n" + r7, encoding="utf-8")
print("docs updated; desktop bytes:", desk.stat().st_size)
