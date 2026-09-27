import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
root = Path(r"D:\factor"); R = root/"research_reports"/"platform_alignment"; G = R/"gp-platform-tests-20260925"

loc = dict(net=0.1339, turn=0.399, rank_ic=0.0360)
gross = loc["net"] + loc["turn"]*0.006*25.2
plat = dict(gross=19.41, turn=40.51, net=19.41-40.51*0.006*25.2, rank_ic=-0.0352, mono=0.70,
            p=0.0004, ic_mean=-0.0084, ic_ir=-0.3346, win=65.0, ann=30.82, mdd=31.72,
            excess_mdd=10.5, ls=15.56, ls2=17.83,
            decile_excess=[19.41,10.02,4.13,-1.10,-3.81,-6.80,-7.92,-10.44,-7.80,3.84],
            decile_turn=[40.51,58.31,63.11,64.15,64.08,67.36,73.81,72.99,73.20,72.98])
print("plat net", round(plat["net"],2), "| local net", loc["net"]*100, "| delta", round(loc["net"]*100-plat["net"],2))

# registry
reg_path = R/"factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))
fu = reg["magnitude_remediation_evidence"]["follow_up_20260925"]
fu["K020_cand0110_S27_D0b"] = {
    "formula": "(POWER(10,27)*((((RATIO_BM_LYR/(CAL_30D_PRICE_VOL_CORR/MA(CAL_30D_PRICE_VOL_CORR,40)))/CAL_20D_AMT_MA)/BS_TOTAL_ASSETS)/BS_TOTAL_ASSETS))",
    "factor_direction": 0,
    "factor_id": "6ab66f9b9e9d797cfb2cf775", "run_id": "6ab66f9e9e9d797cfb2cf776",
    "platform_net_excess_pct": round(plat["net"], 4), "platform_gross_excess_pct": plat["gross"],
    "platform_turnover": plat["turn"]/100, "rank_ic": plat["rank_ic"], "monotonicity": plat["mono"],
    "p_value": plat["p"], "monthly_win_rate": plat["win"],
    "local_net_excess": loc["net"], "local_turnover": loc["turn"],
    "net_delta_pp": round(loc["net"]*100 - plat["net"], 4),
    "outcome": "RESOLVED_ACCEPTABLE_DIRECTION_0",
    "note": "同一公式、同一缩放，仅 factor_direction=0：net +13.28%（本地 13.39%，差 0.11pp）→ 平台端与本地差一个整体符号，"
            "方向修正后完全可用。已用 ×1e27 归一消除量级退化。",
}
for rec in reg["unacceptable_records"]:
    if rec["id"].endswith("K020-cand0110-S27"):
        rec["attribution"]["superseded_by"] = "magnitude_remediation_evidence:follow_up_20260925:K020_cand0110_S27_D0b"
        for fa in rec["attribution"].get("field_attribution", []):
            fa["avoid_by_default"] = False
reg["field_evidence_notes"]["direction_semantics"] = (
    "2026-09-25 round6b：K020 在平台端与本地**整体差一个符号**（|RankIC| 一致、分组收益反向），"
    "以 factor_direction=0 提交后 net +13.28% vs 本地 13.39%（差 0.11pp）。"
    "→ 依赖本地代理字段（如 RATIO_BM_LYR / CAL_30D_PRICE_VOL_CORR）的候选，**平台方向必须实测**，不能沿用本地 ic_mean 推断。")
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry updated | records:", len(reg["unacceptable_records"]))

# GOAL
gp = root/"GOAL.md"; g = gp.read_text(encoding="utf-8")
anchor5 = "## 五、唯一可主动改变的杠杆"
item19 = """19. **K020 方向修正成功 → 第 4 个平台验证通过（2026-09-25，4 算力）**：
   - 同一公式、同一 ×1e27 缩放，唯一改动是 `factor_direction 1 → 0`：平台净 **+13.28%**（本地 13.39%，差 **0.11pp**）、
     换手 40.51%、分组1 +19.41%、多空 +15.56%、单调性 0.70、p=0.0004、月度胜率 65%。
   - 起因：round5 发现平台端与本地**整体差一个符号**（|RankIC| 0.0352 ≈ 本地 0.0360、收益方向相反）。
   - **教训（已写入登记表 `field_evidence_notes.direction_semantics`）**：依赖本地代理字段的候选，
     **平台方向必须实测**，不能沿用本地 `ic_mean` 推断。
   - 运维记录：round6 前后两次运行平台侧卡死（status=8、零节点、未计费），**换全新 factor 后一次成功**
     （与 round4 同样现象）——遇到卡死先重试、再换新 factor。
   - **平台验证通过清单更新：K008 +13.71% ｜ K021 +11.27% ｜ K015 +10.36% ｜ K020 +13.28%**。

"""
assert g.count(anchor5) == 1
g = g.replace(anchor5, item19 + anchor5, 1)
bill_anchor = "| 2026-09-25 | round5：K015×1e24 + K020×1e27 量级归一复测（2 条成功） | 8 | 1684.12 |\n"
assert g.count(bill_anchor) == 1
g = g.replace(bill_anchor, bill_anchor +
  "| 2026-09-25 | round6：K020 direction=0 复测（两次平台卡死未计费；换新 factor 成功 4.0） | 4 | 1680.12 |\n", 1)
gp.write_text(g, encoding="utf-8"); print("GOAL.md updated (item19 + 1680.12)")

# round6 summary
r6 = """# GP 新簇候选平台复现 · 第六轮（2026-09-25 晚，K020 方向修正）——第 4 个验证通过

## 一、动机

round5 发现 K020 ×1e27 在平台端**不再是退化**（换手 40.5%~73.9%、单调性 0.70、RankIC -0.0352、p=0.0004），
但方向与本地**相反**：|RankIC| 0.0352 ≈ 本地 0.0360，平台分组1（最低值端）+19.44%。
→ 假设是**单一符号约定差异**，预期 `factor_direction=0` 后净额 ≈ +13.3%。

## 二、过程：平台侧两次卡死（均未计费）

| 时间 | 动作 | 结果 |
| --- | --- | --- |
| 20:31 | 复用原 factor 提交 direction=0 | status=8、零节点、卡死 ≥15 分钟（`scripts/_harvest_round6.py` 8 次轮询无果） |
| 20:47 | 同一 factor 重试 | 同样卡死（status=8、零节点） |
| 20:56 | **换全新 factor**（`-D0b`） | **一次成功**（100s） |

两次卡死均**未计费**（余额 1684.12 不变）。与 round4 的现象一致：**卡死的 factor 重试仍卡，换新 factor 即可**。

## 三、结果：方向修正后完全可用 ✅

| 指标 | 平台（direction=0） | 本地 | 差 |
| --- | ---: | ---: | ---: |
| 扣费净额 | **+13.28%** | 13.39% | **-0.11pp** |
| 多头端（分组1）年化超额 | +19.41% | 19.42%(gross) | -0.01pp |
| 换手 | 40.51% | 39.9% | +0.6pp |
| Rank_IC | -0.0352（p=0.0004） | +0.0360 | 符号相反，绝对值一致 |
| 单调性 | 0.70 | — | — |
| 多空组合 / 多空2 | +15.56% / +17.83% | — | — |
| 月度胜率 | 65.00% | — | — |

十组超额（分组1→10）：+19.41 / +10.02 / +4.13 / -1.10 / -3.81 / -6.80 / -7.92 / -10.44 / -7.80 / +3.84

- factor_id `6ab66f9b9e9d797cfb2cf775` / run_id `6ab66f9e9e9d797cfb2cf776`；计费 4.0（余额 1684.12 → **1680.12**）

## 四、结论

1. **K020 = 第 4 个平台验证通过候选**（方向需取 0）：net +13.28%，与本地差 0.11pp。
2. **平台方向必须实测**：依赖本地代理字段（`RATIO_BM_LYR` / `CAL_30D_PRICE_VOL_CORR`）的候选不能沿用本地 `ic_mean` 推断方向。
   已写入 `field_evidence_notes.direction_semantics`。
3. 运维规则补充：**卡死的 factor 换新 factor 重跑**（round4、round6 两次验证）。
4. 平台验证通过清单：**K008 +13.71% ｜ K021 +11.27% ｜ K015 +10.36% ｜ K020 +13.28%**。

## 五、复现入口

- 候选：`round6/candidates_panda.txt`（卡死两次）、`round6b/candidates_panda.txt`（成功）
- 原始响应：`round6b/candidates_panda.results/6ab66f9e9e9d797cfb2cf776.json`
- 卡死轮询脚本：`scripts/_harvest_round6.py`；解析：`scripts/_round6_parse.py`
"""
(G/"round6/summary.md").write_text(r6, encoding="utf-8")

ms = G/"summary.md"; s = ms.read_text(encoding="utf-8")
s += """

## 十二、第六轮（2026-09-25 晚，K020 方向修正，4 算力）——第 4 个验证通过

- K020 ×1e27 + `factor_direction=0`：平台净 **+13.28%** vs 本地 13.39%（差 **0.11pp**）、换手 40.51%、多空 +15.56%、p=0.0004。
- 过程：两次运行卡死（status=8、零节点，**均未计费**）→ **换全新 factor 一次成功**（与 round4 同一规律）。
- 教训：**平台方向必须实测**（依赖本地代理字段时不能沿用本地 `ic_mean` 推断）。
- 清单：**K008 +13.71% ｜ K021 +11.27% ｜ K015 +10.36% ｜ K020 +13.28%**。花费：1684.12 → **1680.12**（4.0）。
"""
ms.write_text(s, encoding="utf-8")
desk = Path(r"C:\Users\58302\Desktop\新簇候选平台验证-20260925.md")
desk.write_text(s + "\n\n---\n\n" + r6, encoding="utf-8")
print("docs updated; desktop bytes:", desk.stat().st_size)
