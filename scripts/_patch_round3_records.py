import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = Path(r"D:\factor")
R = root / "research_reports" / "platform_alignment"
G = R / "gp-platform-tests-20260925"

local_net = 0.1164972790002823
local_turn = 0.4241988956928253
local_rank_ic = 0.0276839192956686
local_cost = local_turn * 2 * 0.003 * 25.2
local_gross = local_net + local_cost
plat_net = -14.51
plat_gross = -0.0078
plat_turn = 0.9083
print(f"local gross={local_gross*100:.2f}% cost={local_cost*100:.2f}%  net_delta={local_net*100-plat_net:.2f}pp  gross_delta={local_gross*100-plat_gross*100:.2f}pp")

# ---------- 1. registry ----------
reg_path = R / "factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))
rec = {
    "id": "gp-platform-tests-20260925:round3/candidates_panda:GP0924-K021-cand0013-ASIFIX",
    "name": "GP0924-K021-cand0013-ASIFIX",
    "report": "gp-platform-tests-20260925/round3/candidates_panda.txt.state.json",
    "handler": "gp_candidate_platform_syntax",
    "formula": "(((CORR(ASI(OPEN,CLOSE,HIGH,LOW,26,10),VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)",
    "platform_run_id": "6ab66330812a2a13b9644c76",
    "platform_net_excess_pct": plat_net,
    "local_net_excess": local_net,
    "local_net_delta_pp": round(local_net * 100 - plat_net, 6),
    "platform_gross_excess": plat_gross,
    "local_gross_excess": local_gross,
    "local_gross_delta_pp": round(local_gross * 100 - plat_gross * 100, 6),
    "platform_turnover": plat_turn,
    "local_turnover": local_turn,
    "turnover_alignment": "mismatch",
    "rank_ic_delta": round(0.0007 - local_rank_ic, 10),
    "period_coverage": 1.0,
    "alignment_quality": "field_or_path_mismatch",
    "alignment_quality_flags": ["large_net_delta", "turnover_not_comparable",
                                "degenerate_platform_panel", "unexplained_net_delta"],
    "attribution": {
        "acceptable_by_net_excess": False,
        "unacceptable_by_net_excess": True,
        "net_delta_pp": round(local_net * 100 - plat_net, 6),
        "gross_delta_pp": round(local_gross * 100 - plat_gross * 100, 6),
        "turnover_dominant": True,
        "cause_codes": ["degenerate_platform_factor_panel"],
        "cause_details": [
            "第三条同签名退化：十组年化超额全部落在 -1.97%~+2.03%、每组换手 90.78%~90.92%、多空组合 -2.82%(多空2 +1.72%)、RankIC 0.0007、IC_mean 0.0000、IC_std 0.0168、p=0.9847、单调性 0.04；本地同公式净超额 11.65%、换手 42.4%、RankIC 0.0277。",
            "关键增量证据：本轮唯一改动是把裸 ASI 换成算子形式 ASI(OPEN,CLOSE,HIGH,LOW,26,10)，构建节点（线性因子构建）通过、10000 类型错误消失 → 证明 2026-09-25 round2 的失败是算子名/字段名撞名，而退化与撞名无关。",
            "三条约化候选（K015/K020/K021-ASIFIX）共用 CAL_20D_AMT_MA 与 BS_TOTAL_ASSETS，且都在除法链末端除以 1e8~1e10 量级的成交额/总资产（因子值量级 1e-19~1e-28）；未退化的 K008 同样式除法量级 1e-10。疑似平台端数值表示/精度问题，未做单字段或放大数量级的反事实验证（平台不提供因子值面板下载）。",
            "cal_20d_amt_ma 至此 3 条 >5pp 且无 <=5pp 反例；自动拉黑门槛满足。",
        ],
        "formula_fields": ["asi", "vma3", "cal_20d_amt_ma", "qtyr_5_20", "bs_total_assets"],
        "formula_operators": ["corr", "div", "asi"],
        "field_attribution": [
            {"field": "cal_20d_amt_ma", "role": "local_proxy_field", "confidence": "high",
             "avoid_by_default": True,
             "reason": "三条退化记录（K015/K020/K021-ASIFIX）共用该字段；3 条 >5pp 且无 <=5pp 反例，自动拉黑门槛满足。"},
            {"field": "bs_total_assets", "role": "financial_leaf", "confidence": "medium",
             "avoid_by_default": False,
             "reason": "三条退化记录共用；量级 1e10，与成交额连乘后压低因子值量级。"},
            {"field": "qtyr_5_20", "role": "catalog_volume_field", "confidence": "low",
             "avoid_by_default": False, "reason": "首次进入平台公式；本组无独立证据。"},
            {"field": "vma3", "role": "catalog_technical_field", "confidence": "low",
             "avoid_by_default": False, "reason": "首次进入平台公式；本组无独立证据。"},
            {"field": "asi", "role": "operator_call", "confidence": "high",
             "avoid_by_default": False,
             "reason": "已改为算子形式 ASI(OPEN,CLOSE,HIGH,LOW,26,10)，构建通过；不再是嫌疑字段。"},
        ],
    },
}
reg["unacceptable_records"].append(rec)
notes = reg["field_evidence_notes"]
notes["cal_20d_amt_ma"] = ("三条平台退化记录（K015、K020、K021-ASIFIX，均 >5pp 且无 <=5pp 反例）的共用字段，自动拉黑门槛满足；"
                           "三组都在除法链末端除以 1e8~1e10 量级的成交额/总资产。未做放大数量级反事实验证。")
notes["asi"] = ("2026-09-25 round2：裸写 ASI 被解析成算子对象 → 10000 类型错误；round3 改为 ASI(OPEN,CLOSE,HIGH,LOW,26,10) 后构建通过。"
                "字段本身未被证伪，但公式里必须写成算子形式或等价展开。")
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry: records =", len(reg["unacceptable_records"]), "| notes =", len(notes))

# ---------- 2. GOAL.md ----------
goal = root / "GOAL.md"
g = goal.read_text(encoding="utf-8")
anchor5 = "## 五、唯一可主动改变的杠杆"
assert g.count(anchor5) == 1

tail15 = "（详见 `gp-platform-tests-20260925/round2/summary.md`）。\n"
assert g.count(tail15) == 1
g = g.replace(tail15, tail15 + "   - ✅ 2026-09-25 晚已用 4 算力验证：改成 `ASI(OPEN,CLOSE,HIGH,LOW,26,10)` 后构建节点通过（见第 16 条）。\n", 1)

item16 = """16. **K021 消解版平台复现（2026-09-25，4 算力）：撞名修复成功，但因子照旧退化**：
   - 唯一改动：裸 `ASI` → `ASI(OPEN,CLOSE,HIGH,LOW,26,10)`；10000 类型错误消失，100.07s 正常出结果 → **撞名根因确认**。
   - 结果仍是退化面板：十组年化超额 **-1.97%~+2.03%**、每组换手 **90.78%~90.92%**、多空 -2.82%、RankIC **0.0007**、
     单调性 0.04（本地对照：净 11.65%、换手 42.4%、RankIC 0.0277）→ net 差 **26.2pp**，已写入 failure registry
     （第 3 条 `degenerate_platform_factor_panel`）。
   - `cal_20d_amt_ma` 至此 **3 条 >5pp 且零反例**，自动拉黑门槛正式满足：**`CAL_*` 族候选（205 条里 114 条）在拿到字段级证据前不再进平台**。
   - 量级（1e18）假设仍未直接检验（平台不提供因子值面板下载）；验证只能靠零撞名候选的 ×1e18 反事实复跑。

"""
g = g.replace(anchor5, item16 + anchor5, 1)

bill_anchor = "| 2026-09-25 | round2：K021 消解尝试 2 条（`ASI` 撞名触发 10000 类型错误，均无结果；**失败也计费**） | 2 | 1700.12 |\n"
assert g.count(bill_anchor) == 1
g = g.replace(bill_anchor, bill_anchor + "| 2026-09-25 | round3：K021 消解版 1 条（撞名修复成功、结果仍退化；成功计费 4.0） | 4 | 1696.12 |\n", 1)
goal.write_text(g, encoding="utf-8")
print("GOAL.md: item16 added + billing row (1696.12)")

# ---------- 3. round3 summary ----------
r3 = """# GP 新簇候选平台复现 · 第三轮（2026-09-25 晚，K021 撞名消解版）

## 一、这轮跑了什么

用户批准"K021 消解版 1 条"（4 算力）。相对 round2 的改动只有一处：

| | 公式 |
| --- | --- |
| round2（失败） | `(((CORR(ASI,VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)` |
| round3（本轮） | `(((CORR(ASI(OPEN,CLOSE,HIGH,LOW,26,10),VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)` |

提交前静态检查：`scripts/_round3_precheck.py` 确认裸字段 token 与 137 个平台算子名**零冲突**。

- factor_id `6ab6632e812a2a13b9644c75` / run_id `6ab66330812a2a13b9644c76`
- 100.07s 成功，计费 **4.0**（余额 1700.12 → **1696.12**）

## 二、结果：构建通过，但平台端仍然退化

| 指标 | 平台（本轮） | 本地对照 | 差 |
| --- | ---: | ---: | ---: |
| 分组10 年化超额（=多头端） | **-0.78%** | — | — |
| 十组年化超额范围 | **-1.97% ~ +2.03%** | — | — |
| 多空组合 / 多空2 | -2.82% / +1.72% | — | — |
| 每组换手 | **90.78% ~ 90.92%** | 42.42% | 不匹配 |
| Rank_IC / IC_mean | **0.0007 / 0.0000** | 0.0277 | -0.0270 |
| IC_std / IC_IR / IR | 0.0168 / 0.0018 / 0.0085 | — | — |
| t统计量 / p-value | 0.0192 / 0.9847 | — | — |
| 单调性 | 0.04 | — | — |
| 扣费净额（0.3% 单边） | **-14.51%** | 11.65% | **-26.2pp** |

十组明细（年化 / 超额 / 换手）：

| 组 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 年化 | 13.41% | 10.32% | 11.39% | 10.44% | 9.40% | 12.96% | 11.04% | 12.39% | 12.04% | 10.59% |
| 超额 | +2.03% | -1.05% | +0.01% | -0.93% | -1.97% | +1.58% | -0.33% | +1.00% | +0.65% | -0.78% |
| 换手 | 90.81% | 90.92% | 90.80% | 90.85% | 90.84% | 90.81% | 90.79% | 90.78% | 90.87% | 90.83% |

## 三、结论

1. **撞名根因被证实**：同一候选、唯一改动是 `ASI` 写法，10000 类型错误消失。以后提交前跑撞名预检即可避免这一类失败。
2. **退化与撞名无关**：形态与 K015/K020 完全一致（换手锁死 ~90.8%、RankIC≈0、单调性 0.04、多空负），共性仍是
   `CAL_20D_AMT_MA` + `BS_TOTAL_ASSETS` 的多级除法链（因子值量级 1e-19~1e-28）。
3. **`cal_20d_amt_ma` 正式达标拉黑**：3 条 >5pp、零 ≤5pp 反例（登记表已更新，`avoid_by_default = true`）。
4. 量级假设**仍未直接检验**：平台没有因子值面板下载入口，只能靠"零撞名候选 ×1e18 反事实复跑"来分辨
   "数值量级问题"与"字段本身在平台端无语义/无区分度"。

## 四、复现入口

- 候选：`round3/candidates_panda.txt`；状态：`round3/candidates_panda.txt.state.json`
- 原始响应：`round3/candidates_panda.results/6ab66330812a2a13b9644c76.json`
- 提交日志：`round3/candidates_panda.submit.log`；解析：`scripts/_round3_parse.py`
- 提交前撞名预检：`scripts/_round3_precheck.py`（通用版：`scripts/_platform_name_collision_check.py`）
"""
(G / "round3" / "summary.md").write_text(r3, encoding="utf-8")

# ---------- 4. main summary + desktop ----------
ms = G / "summary.md"
s = ms.read_text(encoding="utf-8")
s += """

## 九、第三轮（2026-09-25 晚，K021 撞名消解版，4 算力）——构建通过，仍退化

- 唯一改动 `ASI` → `ASI(OPEN,CLOSE,HIGH,LOW,26,10)`；10000 类型错误消失，100.07s 出结果 → **撞名根因确认**。
- 结果是第三条同签名退化（换手锁死 90.8%、RankIC 0.0007、单调性 0.04、多空 -2.82%、扣费净 **-14.51%** vs 本地 11.65%，
  差 **26.2pp**）→ 已登记 failure registry。
- `cal_20d_amt_ma` 3 条 >5pp 零反例 → **正式拉黑**；`CAL_*` 族候选暂停进平台，直到有字段级证据。
- 花费：1700.12 → **1696.12**（4.0）。详情：`round3/summary.md`。
"""
ms.write_text(s, encoding="utf-8")

desk = Path(r"C:\Users\58302\Desktop\新簇候选平台验证-20260925.md")
desk.write_text(s + "\n\n---\n\n" + r3, encoding="utf-8")
print("summaries updated; desktop bytes:", desk.stat().st_size)
