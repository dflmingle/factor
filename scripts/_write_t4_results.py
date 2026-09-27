from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
OUT = ROOT / "research_reports/platform_alignment/turnover-relaxed-20260926"
DESKTOP = Path("C:/Users/58302/Desktop")

T4_SECTION = """
### 6.6 T4 补测（用户批准补 4 算力，run `6ab769dd…`）

| 指标 | 基线 5 席 | 6 席 + T2 | 6 席 + T4 |
| --- | ---: | ---: | ---: |
| 毛超额 | 22.32% | 20.58% | **21.76%** |
| 每次调仓换手 | 13.39% | 17.50% | **19.20%** |
| 净超额 | 20.30% | 17.93% | **18.86%（−1.44pp）** |
| Sharpe | 1.0648 | 1.1509 | **1.0395（−0.025）** |
| MaxDD（全期） | 31.64% | 26.28% | **32.28%（+0.64pp）** |
| 月胜率 | 65.00% | 68.33% | 65.00% |
| RankIC / IC_IR | 0.0919 / 0.3675 | 0.0893 / 0.3764 | 0.0927 / 0.3722 |
| P(IC>0.02) | 70.83% | 63.87% | 68.33% |

- **池级 IC 代理**：rawA 0.02392 → 0.02358，`ΔNA = −0.0043` → **−38 分/月**（A 侧基本打平）。
- **C 侧**：`ΔNC = −0.2485` → **−4,920 分/月**——换手 19.20%/次 使月换手 0.403（深在地板上方），
  且 Sharpe 与 MaxDD 都退到基线之下（与 T2 相反，T4 连"Sharpe/DD 改善"这个正项都没有）。
- 合计（不含 NB）≈ **−4,960 分/月**；本地预估 A +254/+381、C −106 → 同样反号，且低估 C 侧一个数量级。
- 月度超额复核：月均 1.218%（基线 1.240%）、负月 14/60（基线 15）、占优 26/60 → 月频超额与基线**无差别**，
  它损失的不是 Rex 而是**换手**。
"""

REVISED_CONCLUSION = """### 6.5 结论与建议

1. **T2、T4 都不进池**（平台端均为负，T4 更差）："放宽换手档有可用候选"这条假设按证伪处理；
   失败登记表新增两条（第 13、14 条）。
2. **两条的失败机制相同、程度不同**：换手从 13.39% 抬到 17.50%（T2）/ 19.20%（T4）后，
   月换手 0.268（地板下）→ 0.35 / 0.403（地板上），rawC 分母惩罚 ×0.857 / ×0.686；
   T2 还有池级 IC 胜率 −7pp，T4 则是 Sharpe、MaxDD 双双退到基线之下。
   **T4 的月度超额与基线几乎相同（1.218% vs 1.240%）→ 它损失的全部来自换手，不是信号质量。**
3. **方法学修正（已验证两次）**：本地候选边际评估必须同时给「池级 IC 代理」
   （`RankIC×IC_IR×P(IC>0.02)`）与「加席后是否跨过 0.30 换手地板」两项；
   只看候选自己的 `s_i_rank` + 逐月 C 会给出反号结论（T2 +482 vs 实测 ≈ −2,330；T4 +254 vs ≈ −4,960）。
4. **30–40% 换手档整档关闭**；换手约束回到 ≤30%/次，即 5 席池的 13.4% 附近最多再加 1 席低换手因子。
5. 真正的约束回到 `GOAL.md` 的 A/NB 主线：A 分项已饱和（本次两条的池级 A 项分别 −270 / −38 分/月），
   NB 需要样本外 IC 样本积累，**把换手从 13% 抬到 17-19% 只会同时打坏 Rex 与 C 分母**。
"""

path = OUT / "summary.md"
text = path.read_text(encoding="utf-8")
# replace the earlier conclusion block with the revised one
start = text.index("### 6.5 结论与建议")
end = text.index("4. 真正的约束回到 `GOAL.md` 的 A/NB 主线")
end = text.index("\n", end) + 1
text = text[:start] + REVISED_CONCLUSION + T4_SECTION + text[end:]

# also update the 6.1 billing table row 4 -> add the retry
old_row = "| 4 | `POOL6-T4V5` | 跑了 126s、平台返回「获取运行详情失败」→ 无可用结果 | 6.0 |"
new_row = (old_row + "\n| 5 | `POOL6-T4V6`（补测，用户批准） | **T4 成功** | 4.0 |")
assert old_row in text
text = text.replace(old_row, new_row, 1)
text = text.replace(
    "余额 1664.12 → **1654.12**（花 10.0：T2 可用 4.0 + T4 白付 6.0）。",
    "余额 1664.12 → **1650.12**（花 14.0：T2 4.0 + T4 白付 6.0 + T4 补测 4.0）。", 1)
text = text.replace(
    "run id：T2 `6ab75e8fcd820fa2a40a6cbe`（factor `6ab75e8d9e9d797cfb2cf878`）。",
    "run id：T2 `6ab75e8fcd820fa2a40a6cbe`（factor `6ab75e8d9e9d797cfb2cf878`）、"
    "T4 `6ab769dd6ee632ca3f97b59d`（factor `6ab769dbb8f0d75493c83313`）。", 1)
path.write_text(text, encoding="utf-8")
print("summary.md updated")

# desktop copy: rebuild from the updated section 六
desktop = DESKTOP / "放宽换手平台实测-20260926.md"
header = """# 放宽换手假设 · 平台实测结论（2026-09-26）

> 一句话：**T2、T4 作第 6 席都被平台证伪**——净超额 −2.37pp / −1.44pp，换手 13.39%→17.50% / 19.20%，
> 全期 MaxDD 与 Sharpe 的改善在月频 C 里不换分；T4 的月度超额与基线几乎相同，损失全部来自换手。
> 花费：14.0 算力（T2 4.0 + T4 白付 6.0 + T4 补测 4.0），余额 1650.12。
"""
section = text[text.index("## 六、平台实测"):]
desktop.write_text(header + section, encoding="utf-8")
print("desktop copy rewritten")

# registry: add the T4 record
import json
REG = ROOT / "research_reports/platform_alignment/factor_alignment_failure_registry.json"
record = {
    "id": "platform_pool_tests_20260926:pool6-t4v6:POOL6-T4V6-20260926",
    "name": "POOL6-T4V6-20260926",
    "kind": "pool_level_seat_addition",
    "report": "platform_pool_tests_20260926/pool6-t4v6-20260926-candidates.txt.state.json",
    "handler": "pool6_seat_addition",
    "formula": "(((SUM(EV_LYR,40)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)",
    "platform_run_id": "6ab769dd6ee632ca3f97b59d",
    "platform_factor_id": "6ab769dbb8f0d75493c83313",
    "baseline_pool_run_id": "6ab254c08b01f62dc5147d3a",
    "platform_pool_gross_excess": 0.2176,
    "platform_pool_net_excess": 0.1886,
    "platform_pool_turnover_per_rebalance": 0.192,
    "platform_pool_sharpe": 1.0395,
    "platform_pool_max_drawdown": 0.3228,
    "baseline_pool_net_excess": 0.2030,
    "baseline_pool_turnover_per_rebalance": 0.1339,
    "net_delta_pp": -1.44,
    "local_pool_delta_points_local": 254.0,
    "local_pool_delta_points_uplifted": 381.0,
    "platform_pool_delta_points_ex_nb": -4958.0,
    "local_net_delta_pp": 23.1,
    "alignment_quality": "pool_level_marginal_seat_mismatch",
    "alignment_quality_flags": ["overstated_local_C_proxy", "turnover_floor_crossing"],
    "attribution": {
        "acceptable_by_net_excess": False,
        "unacceptable_by_net_excess": True,
        "net_delta_pp": -1.44,
        "turnover_dominant": True,
        "cause_codes": ["turnover_floor_crossing", "pool_level_C_proxy_understated", "no_NB_model_in_local_sim"],
        "cause_details": [
            "本地逐月机器给 T4 加席 +254（local）/ +381（uplifted）分/月（A +254/+381、C −106）；平台实测为负一个数量级：ΔNC = −0.2485（−4,920 分/月）、ΔNA = −0.0043（−38 分/月）。",
            "换手 13.39%→19.20%/次 → 月换手 0.268→0.403，rawC 分母惩罚 ×0.686（T2 为 ×0.857）。",
            "与 T2 不同：T4 连 Sharpe（1.0648→1.0395）与全期 MaxDD（31.64%→32.28%）都退到基线之下，没有任何正项。",
            "月度超额复核（平台每期净值→月）：月均 1.218% vs 基线 1.240%、负月 14/60 vs 15/60、占优 26/60 → 月频超额与基线无差别，损失全部来自换手，不是信号质量。",
            "本地 C 代理低估一个数量级的原因：本地逐月账本里 T4 的 T* 抬得动（Rex/SR 略优），平台端 Sharpe 反而下降。",
        ],
        "formula_fields": ["ev_lyr", "cal_20d_amt_ma", "qtyr_5_20", "bs_total_assets"],
        "formula_operators": ["sum", "div"],
        "field_attribution": [],
    },
    "platform_group_excess": {"分组1": -14.94, "分组10": 21.76, "多空组合": 36.82},
    "platform_monotonicity": 0.98,
    "platform_p_value": 0.0001,
    "notes": "字段名 EV_LYR/CAL_20D_AMT_MA/QTYR_5_20/BS_TOTAL_ASSETS 在 Python 模式下全部可用（本次成功运行即为证据）。",
}
payload = json.loads(REG.read_text(encoding="utf-8"))
if record["id"] in {r.get("id") for r in payload["unacceptable_records"]}:
    print("T4 record already present")
else:
    payload["unacceptable_records"].append(record)
    payload["summary"]["unacceptable_records"] = len(payload["unacceptable_records"])
    REG.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("registry now has", len(payload["unacceptable_records"]), "unacceptable records")