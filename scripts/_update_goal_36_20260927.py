import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/bm-core-extension-20260927"

report = """# "BM 核心"合规扩展枚举（2026-09-27 凌晨，零算力）

> 问题：BM4seat（SIZE + H03 + BM + F-I10-01，4 席、实测桥 +934/−133）是三条实测里 k 混合口径最高的，
> 但 4 席低于赛制"有效因子 ≥5"下限。给它补第 5/6 席，能不能找到"k 混合与月度 DD 两口径都为正"的合规版本？

**答案：不能。** 5 席（BM4+1）0/168 双正；6 席（BM4+2）仅 2/14,028 名义双正（+AGG+E +308/+3、+DOWNSIDE+E +203/+4，
月度 DD 优势在 ±100 噪声带内）。补席在两个口径下呈**系统性对立**：低换手席（E/F）dk>0 而 dkdd<0；
高 s_i 席（AGG/DOWNSIDE/FSCORE）dkdd>0 而 dk<0。

## 一、口径与校准

- 席位模型值取自 `rebuild-3window-20260926/seat_windows.csv`（172 席的 net_5y/turn/sr_5y/dd_5y/s_i_5y）。
- 用 5 个实测点标定"模型 → 实测"的平移（见 `calibration.csv`）：

| 池 | δnet | δturn | δsr | δdd | k_ra |
| --- | ---: | ---: | ---: | ---: | ---: |
| 现役 | +2.75 | +0.17 | +0.081 | +1.50 | 0.973 |
| SWAPF | +2.88 | +0.53 | +0.082 | +1.32 | 0.984 |
| V4 | +2.27 | +0.86 | +0.066 | +0.61 | 0.950 |
| PARTT10 | +3.28 | +1.37 | +0.096 | +1.47 | 0.967 |
| BM4seat | +3.09 | +0.70 | +0.083 | +1.12 | 0.964 |
| **中位（中心口径）** | **+2.88** | **+0.70** | **+0.082** | **+1.32** | **0.967** |

- 预桥 = 桥([席位均值]+δ 中心值)，基准 = 现役实测（20.30%/13.39%/1.0648/31.64%/0.025893）。
- **LOO 校验**（`loo_check.csv`）：dkdd 口径误差 sd ≈ 102 分/月（均值 +2）；dk 口径 sd ≈ 356（V4 上 +687——越线池非线性区失准）。
  → dkdd 口径的预测信用较好，dk 的绝对值当**排序参考**用。

## 二、枚举结果

- **5 席（BM4 + 1 席，168 组合）**：双正 0 个。最接近：E（+466/−104，即 SWAPF）、AGG（−107/+18）、F（+419/−134）、G13（−208/−33）。
- **6 席（BM4 + 2 席，14,028 组合）**：名义双正仅 2 个——+AGG+E（+308/+3）、+DOWNSIDE+E（+203/+4），
  但最坏端点（δnet min / δturn max / δsr min / δdd max）下分别为 −898/−199 与 −993/−197，不构成"稳"。
- 近双正的"交叉带"（两口径各差 100 内）：+FSCORE+F（−47/+101）、+FSCORE+E（−93/+129）、+DOWNSIDE+F（+261/−23）、+AGG+F（+368/−24）。
- 完整数据：`ext5_all.csv` / `ext6_all.csv`；双正筛后 `shortlist5.csv` / `shortlist6.csv`。

## 三、结构洞见

1. **两类补席的对立**：
   - 低换手席（VERIFY10-E/F 等）：把 dk 拉正（+400~+470）、但 dkdd 仍负（−100~−135）——因为 dkdd 口径下 NC 全员顶格，A 项（raw_a）主导，而 E/F 的 s_i 低。
   - 高 s_i 席（T10-ADD-FSCORE 0.0584 / DOWNSIDE 0.0463 / AGG 0.0453）：把 dkdd 拉正（+18~+180）、但把 dk 打负（−100~−509）——因为换手推高越线，k 混合口径下 C 分母实算。
2. 这解释了本轮 4 条实测的分布（dk 正者 dkdd 全负：SWAPF +528/−33、BM4 +934/−133；dk 负者 dkdd 也负：PARTT10、V4）。
   **两口径打架是结构性的，不是某条候选的偶然。**
3. 判别价值最高的实验对象：**BM4 + FSCORE + E（6 席）**（预桥 −93/+129）——FSCORE 从未上过平台，
   它是"高 s_i 席方向"的代表；该点若实测 dkdd 明确为正，则证明"若官方口径为 dkdd 类，高 s_i 补席可用"；
   若为负，则 dkdd 方向同样全灭、10 月核对的天平显著偏向 dk 口径。

## 四、结论

- 10-01~03 删改窗口：**无新增可报批的换池对象**（没有两口径稳健为正的组合）。
- 可选（待批）：为 10 月口径核对测 1 条判别实验 BM4+FSCORE+E（6 席，约 4.0）。

（脚本 `scripts/_bm_core_extension_20260927.py`、`scripts/_loo_check_20260927.py`；本目录另有 calibration/loo_check/ext5_all/ext6_all/shortlist5/shortlist6 六个 CSV。）
"""
(OUT / "summary.md").write_text(report, encoding="utf-8", newline="\n")
print("report:", (OUT / "summary.md").stat().st_size, "bytes")

goal = ROOT / "GOAL.md"
raw = goal.read_bytes(); text = raw.decode("utf-8")
assert "\r" not in text

a1 = "      报告：`platform_pool_tests_20260926/summary-partt10-bm4seat.md`；桥数据 `platform_bridge_partt10_bm4seat.json`。\n"
assert text.count(a1) == 1, text.count(a1)
entry = a1 + """
36. **"BM 核心"合规扩展枚举（2026-09-27 凌晨，零算力）：168+14,028 组合无两口径稳健正；补席呈"E/F 类 vs 高 s_i 类"系统性对立**：
    - 口径：席位均值 + 5 个实测点标定（δnet 中位 +2.88、δturn +0.70、δsr +0.082、δdd +1.32、k_ra 0.967）；LOO 校验
      dkdd 误差 sd ≈102 分/月、dk 误差 sd ≈356（越线池失准）→ dkdd 预测信用较好。
    - 结果：5 席（BM4+1）**双正 0/168**；6 席（BM4+2）**名义双正仅 2/14,028**（+AGG+E +308/+3、+DOWNSIDE+E +203/+4，
      最坏端点 −199/−197）。最近双正：5 席 E（+466/−104）、AGG（−107/+18）；6 席交叉带 +FSCORE+F（−47/+101）、+FSCORE+E（−93/+129）。
    - 结构：低换手席（E/F）把 dk 拉正、dkdd 仍负（s_i 低）；高 s_i 席（FSCORE/DOWNSIDE/AGG）把 dkdd 拉正、dk 打负（换手越线）。
      **两口径打架是系统性的，补席解不开**；本轮 4 条实测（SWAPF/BM4 dk 正 dkdd 负；PARTT10/V4 双负）与其一致。
    - 行动：10-01~03 窗口**无新增报批对象**；可选判别实验（待批）BM4+FSCORE+E（6 席；预桥 −93/+129；FSCORE 从未上过平台）。
    - 报告：`research_reports/platform_alignment/bm-core-extension-20260927/`（summary.md + 6 张 csv）。
"""
text = text.replace(a1, entry)

a2 = "| 2026-09-27 凌晨 | 两条换池候选平台实测：PARTT10（桥 −602、否决）+ BM4seat（桥 +935、4 席不合规）各成功 4.0（第 35 条） | 8 | **1616.12** |\n"
assert text.count(a2) == 1, text.count(a2)
text = text.replace(a2, a2 + "| 2026-09-27 凌晨 | \"BM 核心\"合规扩展枚举 + LOO 校准校验（第 36 条，全本地） | 0 | 1616.12 |\n")

nb = text.encode("utf-8")
assert b"\r" not in nb and not nb.startswith(b"\xef\xbb\xbf")
goal.write_bytes(nb)
print("GOAL:", len(raw), "->", len(nb))
print("entry36:", '36. **"BM 核心"合规扩展枚举' in text)
print("ledger:", '"BM 核心"合规扩展枚举 + LOO 校准校验（第 36 条，全本地）' in text)