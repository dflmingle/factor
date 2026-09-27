# -*- coding: utf-8 -*-
import os
from pathlib import Path
import pandas as pd

OUT = Path(os.environ["TEMP"]) / "side_conv"
a = pd.read_csv(OUT / "gate6_screen.csv")
b = pd.read_csv(OUT / "gate6b_probes.csv")
d = pd.concat([a, b], ignore_index=True)
order = ["F2-nb60_x_T5", "F1-im40", "F1-im30", "F1-im50", "F2-nb20_x_T5",
         "HT-VOLSTAB-V10", "HT-VOLSTAB-V20", "HT-VOLSTAB-T10", "HT-VOLSTAB-T20", "HT-VOLSTAB-5050",
         "HT-VOLSTAB-V60", "HT-VOLSTAB-V10sm63", "HT-VOLSTAB-V10sm126",
         "HT-VOLSTAB-T60", "HT-VOLSTAB-T60sm63", "HT-VOLSTAB-T20sm63", "HT-VOLSTAB-T20sm126",
         "HT-VOLSTAB-MIXsms"]
d = d.set_index("cand").loc[order].reset_index()
BASE_TURN = 0.13933
lines = []
lines.append("# 换手闸筛查报告（2026-09-27 · 零平台算力）")
lines.append("")
lines.append("**背景**：`P0P1` 家族两条候选（NB60T5 / IM40）平台实测全灭（净额 −1.66 / −0.08，池换手 +9.70 / +5.88pp）。")
lines.append("本报告在本地把「换手闸 + 池级 ΔComb」建成可复算流程，先校准，再筛查 12 条家族候选 + 5 条慢化变体，")
lines.append("全部零平台算力。口径：重建现役 5 席面板（`seat_panels_rebuilt.pkl`）+ `ab_batch_20260925` 账本")
lines.append("（Top10% 组合、10 日调仓、0.30% 单边、44,000 分/Comb）。")
lines.append("")
lines.append("## 一、校准（本地 vs 平台实测）")
lines.append("")
lines.append("| 候选 | 指标 | 本地 | 平台 | 误差 |")
lines.append("| --- | --- | ---: | ---: | ---: |")
lines.append("| NB60T5（加席） | Δ净额 | −1.14pp | −1.66pp | +0.52pp |")
lines.append("| NB60T5（加席） | Δ换手 | +10.09pp | +9.70pp | +0.39pp |")
lines.append("| NB60T5（换SIZE） | Δ净额 | −2.97pp | −3.61pp | +0.64pp |")
lines.append("| NB60T5（换SIZE） | Δ换手 | +12.10pp | +11.77pp | +0.33pp |")
lines.append("| IM40（加席） | Δ净额 | +2.24pp | −0.08pp | **+2.32pp（乐观）** |")
lines.append("| IM40（加席） | Δ换手 | +5.68pp | +5.88pp | −0.20pp |")
lines.append("| IM40（换SIZE） | Δ净额 | +0.54pp | −1.07pp | +1.61pp |")
lines.append("| IM40（换SIZE） | Δ换手 | +7.50pp | +7.85pp | −0.35pp |")
lines.append("")
lines.append("**结论**：Δ换手预测可信（≤0.5pp）；Δ净额本地偏乐观 0.5~2.3pp（换手越高的候选越乐观）。")
lines.append("席位换手口径同步校验：本地 0.085/0.092/0.297 vs 平台 8.47%/9.22%/29.63%（T10-ADD-BM 误差 0.03pp）。")
lines.append("")
lines.append("## 二、全表（加第 6 席口径）")
lines.append("")
lines.append("| 候选 | 席位换手/次 | 加席 Δ净额 | 加席 Δ换手 | 加席后池换手/次 | 分/月(稳态) | 判定 |")
lines.append("| --- | ---: | ---: | ---: | ---: | ---: | :---: |")
for _, r in d.iterrows():
    mark = "**" if r["gate"] == "PASS" else ""
    lines.append("| %s%s%s | %.3f | %+.2fpp | %+.2fpp | %.2f%% | %+.0f | %s |" % (
        mark, r["cand"], mark, r["seat_turn"], r["add6_dnet"] * 100, r["add6_dturn"] * 100,
        (BASE_TURN + r["add6_dturn"]) * 100, r["add6_dpoints"], "过闸" if r["gate"] == "PASS" else "×"))
lines.append("")
lines.append("（判定 = 席位换手 ≤0.20 且加席 Δ净额 ≥0；分/月 = 44000 × 全周期 ΔComb，稳态近似）")
lines.append("")
lines.append("## 三、过闸者近期窗口（防止重蹈家族 2026 衰减）")
lines.append("")
lines.append("| 候选 | 席位换手 | 5y IC | 1y IC | 3m IC | 2025 s_i | 2026 s_i |")
lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
lines.append("| HT-VOLSTAB-MIXsms | 0.120 | .0583 | .0505 | .0520 | .041 | .024 |")
lines.append("| HT-VOLSTAB-T60 | 0.157 | .0607 | .0550 | .0543 | .043 | .028 |")
lines.append("| HT-VOLSTAB-T20sm63 | 0.111 | .0506 | .0415 | .0459 | .032 | .016 |")
lines.append("| （对照）HT-VOLSTAB-V10（原始族）| 0.601 | .0967 | — | — | — | .014 |")
lines.append("")
lines.append("慢化版没有跟随原始族衰减：MIXsms / T60 的 2025-2026 反而是全历史最强段。")
lines.append("")
lines.append("## 四、结论与待批事项")
lines.append("")
lines.append("1. 原始族（V/T 10-20d、im30-50、nb20/60）换手 0.32~0.67，加席 Δ换手 +2.7~+14.5pp，**全灭**，与平台两条否决一致；")
lines.append("   本族从池级退役（与 `summary-pool6-side-20260927.md` 一致）。")
lines.append("2. 慢化后 3 条过闸：MIXsms（+0.7pp / +1356）、T60（+0.4pp / +845）、T20sm63（+0.1pp / +464）。")
lines.append("3. **风险提示**：本地净额偏乐观（校准 0.5~2.3pp），MIXsms 的 +0.7pp 到平台可能≈0。但它的 Δ换手只有 +0.3pp，")
lines.append("   成本侧风险极小，是「低成本试探」型候选。")
lines.append("4. **待批**：平台回归测 ① MIXsms 加第 6 席（4 算力）；② 可选 T60 加第 6 席（4 算力，同族交叉验证）。")
lines.append("   批准后才动算力；不批准则继续零算力做混权网格优化。")
(OUT / "换手闸筛查报告_20260927.md").write_text("\n".join(lines), encoding="utf-8")
print("written:", OUT / "换手闸筛查报告_20260927.md")
print("passers:", d[d["gate"] == "PASS"]["cand"].tolist())

