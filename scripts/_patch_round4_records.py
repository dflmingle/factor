import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = Path(r"D:\factor")
R = root / "research_reports" / "platform_alignment"
G = R / "gp-platform-tests-20260925"

local_net, local_turn, local_rank_ic = 0.1164972790002823, 0.4241988956928253, 0.0276839192956686
local_gross = local_net + local_turn * 2 * 0.003 * 25.2
plat_long, plat_turn, plat_rank_ic = 16.74, 36.15, 0.0425
plat_net = plat_long - plat_turn * 0.006 * 25.2
print(f"plat_net={plat_net:.2f}%  net_delta={local_net*100-plat_net:.2f}pp  gross_delta={local_gross*100-plat_long:.2f}pp")

# ---------- registry ----------
reg_path = R / "factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))

reg["magnitude_remediation_evidence"] = {
    "discovered_at": "2026-09-25",
    "trigger": "round3（K021-ASIFIX 原式）在平台端退化；round4 用同一公式 ×POWER(10,18) 做量级反事实",
    "controlled_pair": {
        "base_formula": "(((CORR(ASI(OPEN,CLOSE,HIGH,LOW,26,10),VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)",
        "unscaled": {"platform_run_id": "6ab66330812a2a13b9644c76", "platform_net_excess_pct": -14.51,
                     "rank_ic": 0.0007, "monotonicity": 0.04, "decile_turnover_pct": [90.81, 90.92, 90.80, 90.85, 90.84, 90.81, 90.79, 90.78, 90.87, 90.83],
                     "decile_excess_pct": [2.03, -1.05, 0.01, -0.93, -1.97, 1.58, -0.33, 1.00, 0.65, -0.78]},
        "scaled_1e18": {"factor_id": "6ab664cacd820fa2a40a6bd1", "platform_run_id": "6ab665922d2f6998fc1bf75d",
                        "platform_net_excess_pct": round(plat_net, 4), "platform_gross_excess_pct": plat_long,
                        "rank_ic": plat_rank_ic, "ic_mean": 0.0288, "ic_ir": 0.3103, "ir": 2.0299,
                        "p_value": 0.0009, "monotonicity": 0.72, "decile_turnover_pct": [61.01, 52.66, 62.11, 68.14, 71.56, 73.11, 72.98, 70.26, 62.85, 36.15],
                        "decile_excess_pct": [3.16, -6.45, -10.26, -9.33, -9.09, -3.18, 1.41, 6.20, 10.99, 16.74],
                        "long_short_pct": 13.58, "long_short2_pct": 17.45},
        "local_reference": {"net_excess": local_net, "gross_excess": local_gross, "turnover": local_turn, "rank_ic": local_rank_ic},
        "deltas_pp": {"net": round(local_net * 100 - plat_net, 4), "gross": round(local_gross * 100 - plat_long, 4),
                      "rank_ic": round(local_rank_ic - plat_rank_ic, 6)},
    },
    "conclusion": "平台端的退化不是 CAL_* 字段语义错误，而是**因子值量级过小（1e-19~1e-28）在平台内部表示中失去区分度**（十组换手锁死 ~90.8%、RankIC≈0、单调性≈0）。同一公式乘一个正常数（×1e18）后各指标回到与本地一致的水平（net 差 0.38pp、单调性 0.72、p=0.0009）。正数缩放不改变任意截面的排序，因此缩放版与本地因子经济等价。",
    "action_rule": "含 CAL_* / 多级除法链的候选提交平台前，先做量级归一（乘 10^k 使 |因子值| 进入 O(1)），再提交；K015/K020 等历史退化记录可用同样方式重测。",
    "affected_prior_records": [
        "gp-platform-tests-20260925:candidates_panda:GP0924-K015-cand0003-P",
        "gp-platform-tests-20260925:candidates_panda:GP0924-K020-cand0110-P",
        "gp-platform-tests-20260925:round3/candidates_panda:GP0924-K021-cand0013-ASIFIX",
    ],
    "field_blacklist_effect": "cal_20d_amt_ma 的自动拉黑条件失效（现有 1 条 <=5pp 已评估记录），解除 avoid_by_default。",
}
reg["field_evidence_notes"]["cal_20d_amt_ma"] = (
    "2026-09-25 定论：平台端退化是**数值量级**问题（因子值 1e-19~1e-28 时失去区分度），不是字段语义错误。"
    "同一公式 ×POWER(10,18) 后平台 net +11.27% vs 本地 11.65%（差 0.38pp）、单调性 0.72、p=0.0009。"
    "自动拉黑条件失效，解除 avoid_by_default；提交前做量级归一即可（详见 magnitude_remediation_evidence）。")
for rec in reg["unacceptable_records"]:
    if rec["id"] in reg["magnitude_remediation_evidence"]["affected_prior_records"]:
        rec["attribution"]["superseded_by"] = "magnitude_remediation_evidence:2026-09-25"
        for fa in rec["attribution"].get("field_attribution", []):
            if fa["field"] == "cal_20d_amt_ma":
                fa["avoid_by_default"] = False
                fa["reason"] = ("量级问题已被 ×1e18 对照实验证实并解除拉黑（见 magnitude_remediation_evidence）；"
                                "提交前做量级归一即可，字段本身可用。")
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry updated; records:", len(reg["unacceptable_records"]),
      "| cal_20d_amt_ma avoid:", [fa["avoid_by_default"] for rec in reg["unacceptable_records"]
                                   if rec["id"].endswith("ASIFIX") for fa in rec["attribution"]["field_attribution"]
                                   if fa["field"] == "cal_20d_amt_ma"])

# ---------- GOAL.md ----------
goal = root / "GOAL.md"
g = goal.read_text(encoding="utf-8")
tail16 = "   - 量级（1e18）假设仍未直接检验（平台不提供因子值面板下载）；验证只能靠零撞名候选的 ×1e18 反事实复跑。\n"
assert g.count(tail16) == 1
g = g.replace(tail16, tail16.replace("仍未直接检验", "→ 见第 17 条，已证实并找到修复手段").replace(
    "；验证只能靠零撞名候选的 ×1e18 反事实复跑。", "。"), 1)

anchor5 = "## 五、唯一可主动改变的杠杆"
item17 = """17. **【关键突破】平台端退化 = 数值量级问题，×1e18 归一即可修复；K021 成为第 2 个平台验证通过的新簇（2026-09-25，4 算力）**：
   - 对照实验（唯一变量 = 乘 `POWER(10,18)`，同一公式）：
     | | 换手（十组） | RankIC | 单调性 | 扣费净额 |
     | --- | --- | --- | --- | --- |
     | 原式（round3） | 90.78%~90.92% | 0.0007 | 0.04 | **-14.51%**（退化） |
     | ×1e18（round4） | 61.0%~36.2% | **0.0425** | **0.72** | **+11.27%** |
     | 本地对照 | 42.4% | 0.0277 | — | 11.65% |
   - 结论：平台在因子值 **1e-19~1e-28** 量级失去区分度（十组换手锁死 ~90.8%）；正数缩放不改变截面排序 → 缩放版与本地**经济等价**且平台可正常评价。
   - **K021/cand0013-ASIFIX-S18**：net **+11.27%**、RankIC 0.0425、IC_IR 0.3103、p=0.0009、月度胜率 65%、
     与本地仅差 **0.38pp**；与已知簇成员最大相关 0.287 → **平台验证通过的第 2 个独立新簇**（第 1 个是 K008）。
   - `cal_20d_amt_ma` **解除拉黑**（拉黑条件失效）；新增动作规则：**含 CAL_* / 多级除法链的候选，提交前先做量级归一（乘 10^k 进 O(1)）**；
     K015/K020 等历史退化记录可用同法重测。
   - 复现：`round4/summary.md`；登记：`factor_alignment_failure_registry.json::magnitude_remediation_evidence`。

"""
g = g.replace(anchor5, item17 + anchor5, 1)

bill_anchor = "| 2026-09-25 | round3：K021 消解版 1 条（撞名修复成功、结果仍退化；成功计费 4.0） | 4 | 1696.12 |\n"
assert g.count(bill_anchor) == 1
g = g.replace(bill_anchor, bill_anchor +
              "| 2026-09-25 | round4：K021 ×1e18 量级反事实（首次 RUN_FAILED 未计费；重试成功 4.0） | 4 | 1692.12 |\n", 1)
goal.write_text(g, encoding="utf-8")
print("GOAL.md: item17 added + billing row (1692.12)")

# ---------- round4 summary ----------
r4 = """# GP 新簇候选平台复现 · 第四轮（2026-09-25 晚，K021 ×1e18 量级反事实）——决定性结果

## 一、实验设计

用户批准"量级反事实"1 条（4 算力）。**唯一变量**：给 round3 同一条公式乘常量 `POWER(10,18)`。

| | 平台公式 |
| --- | --- |
| round3（退化） | `(((CORR(ASI(OPEN,CLOSE,HIGH,LOW,26,10),VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)` |
| round4（本轮） | `(POWER(10,18)*(((CORR(ASI(OPEN,CLOSE,HIGH,LOW,26,10),VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS))` |

过程曲折：20:10:50 首次提交 RUN_FAILED（`last_run_id = null`，平台侧瞬时失败，**未计费**）；
20:14:08 用 `--keep-error` 复用同一 factor 重试成功（100s），计费 **4.0**（余额 1696.12 → **1692.12**）。

- factor_id `6ab664cacd820fa2a40a6bd1` / run_id `6ab665922d2f6998fc1bf75d`

## 二、结果：量级假设成立，且因子本身完全可用

| 指标 | round3 原式 | **round4 ×1e18** | 本地对照 | 平台(缩放) vs 本地 |
| --- | ---: | ---: | ---: | ---: |
| 十组换手 | 90.78%~90.92% | **61.0%→36.2%** | 42.4% | 同量级 |
| Rank_IC | 0.0007 | **0.0425** | 0.0277 | +0.0148 |
| IC_mean / IC_IR | 0.0000 / 0.0018 | **0.0288 / 0.3103** | — | — |
| IC_std / IR | 0.0168 / 0.0085 | 0.0930 / **2.0299** | — | — |
| t统计量 / p-value | 0.0192 / 0.9847 | **3.3987 / 0.0009** | — | — |
| 单调性 | 0.04 | **0.72** | — | — |
| 分组10 年化超额 | -0.78% | **+16.74%** | 18.06%(gross) | -1.32pp |
| 多空组合 / 多空2 | -2.82% / +1.72% | **+13.58% / +17.45%** | — | — |
| 月度胜率 | 56.67% | **65.00%** | — | — |
| 扣费净额 | **-14.51%** | **+11.27%** | 11.65% | **-0.38pp** |

十组明细（年化 / 超额 / 换手）：

| 组 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 年化 | 14.54% | 4.92% | 1.11% | 2.04% | 2.28% | 8.20% | 12.79% | 17.58% | 22.37% | 28.12% |
| 超额 | +3.16% | -6.45% | -10.26% | -9.33% | -9.09% | -3.18% | +1.41% | +6.20% | +10.99% | +16.74% |
| 换手 | 61.01% | 52.66% | 62.11% | 68.14% | 71.56% | 73.11% | 72.98% | 70.26% | 62.85% | 36.15% |

## 三、结论

1. **平台端退化 = 数值量级问题**：因子值在 1e-19~1e-28 时平台内部失去区分度（十组换手锁死 ~90.8%、RankIC≈0）；
   乘 `1e18` 后一切恢复正常且与本地一致 → **不是 CAL_* 字段语义错误**。
2. **正数缩放不改变任意截面的排序**，所以缩放版与本地因子经济等价；这是可长期使用的标准手法。
3. **K021/cand0013-ASIFIX-S18 = 平台验证通过的第 2 个独立新簇因子**：net **+11.27%**、RankIC 0.0425、
   单调性 0.72、p=0.0009、月度胜率 65%；与已知簇成员最大相关 **0.287**（H03-T10-SINGLE），|corr_size| 0.335。
4. `cal_20d_amt_ma` **解除拉黑**（拉黑条件失效）；K015/K020 等历史退化记录可用同法重测。
5. 动作规则：**提交前做量级归一**（乘 10^k 使 |因子值| 进 O(1)）——已并入提交前检查清单
   （`scripts/_collision_precheck_file.py` 负责撞名，量级归一在提交器里加）。

## 四、复现入口

- 候选：`round4/candidates_panda.txt`；状态：`round4/candidates_panda.txt.state.json`
- 原始响应：`round4/candidates_panda.results/6ab665922d2f6998fc1bf75d.json`；解析：`scripts/_round4_parse.py`
- 提交日志：`round4/candidates_panda.submit.log`
"""
(G / "round4" / "summary.md").write_text(r4, encoding="utf-8")

# ---------- main summary + desktop ----------
ms = G / "summary.md"
s = ms.read_text(encoding="utf-8")
s += """

## 十、第四轮（2026-09-25 晚，K021 ×1e18 量级反事实，4 算力）——【突破】量级问题定论

- 唯一变量 = 乘 `POWER(10,18)`：换手 90.8%→36.2%、RankIC 0.0007→**0.0425**、单调性 0.04→**0.72**、
  扣费净额 -14.51%→**+11.27%**（本地 11.65%，差 **0.38pp**）→ **平台端退化是数值量级问题，不是 CAL_* 字段语义错误**。
- **K021 成为第 2 个平台验证通过的独立新簇**（与已知簇最大相关 0.287）；`cal_20d_amt_ma` 解除拉黑。
- 新规则：含 CAL_* / 多级除法链的候选，提交前先做量级归一（×10^k 进 O(1)）；K015/K020 可用同法重测。
- 花费：1696.12 → **1692.12**（4.0；首次 RUN_FAILED 未计费）。详情：`round4/summary.md`。
"""
ms.write_text(s, encoding="utf-8")

desk = Path(r"C:\Users\58302\Desktop\新簇候选平台验证-20260925.md")
desk.write_text(s + "\n\n---\n\n" + r4, encoding="utf-8")
print("summaries updated; desktop bytes:", desk.stat().st_size)
