import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(r"D:\factor")
OUT = ROOT / "platform_pool_tests_20260926"

report = """# 两条换池候选平台实测（2026-09-27 凌晨，8.0 算力）

一句话：**PARTT10（现役 −BM −F + AGG + G13）桥 −602/月被换手判死（V4 翻版）；BM4seat（现役 −E −F + F-I10-01，4 席）
桥 +935/月为三条实测最高，但 4 席低于赛制"有效因子 ≥5"下限、不能直接进池**；两条平台实测净额都 ≥22%（+1.8 / +2.1pp）。

## 一、平台实测（各 4.0，合计 8.0）

| 指标 | 现役池 F-P260922-08 | PARTT10（5 席） | BM4seat（4 席） |
| --- | ---: | ---: | ---: |
| 毛超额 | 22.32% | 24.73% | 24.63% |
| **净超额** | **20.30%** | **22.08%（+1.78pp）** | **22.44%（+2.14pp）** |
| 换手/次 | 13.39% | **17.55%（月 36.9%，深入越线）** | 14.48%（k=2 分母 28.96% 贴线免费） |
| Sharpe | 1.0648 | 1.1043 | 1.0929 |
| 全期 MaxDD | 31.64% | 32.94% | 33.76% |
| 池级 RankIC / ICIR | 0.0919 / 0.3675 | 0.0921 / 0.3815 | 0.0844 / 0.3691 |
| 月胜率 / 单调性 | 65.0% / 0.99 | 65.0% / 0.97 | 65.0% / 0.97 |

- PARTT10：factor `6ab7eee79e9d797cfb2cf8ef`、run `6ab7eee99e9d797cfb2cf8f0`（110s）；脚本 `pool5_partial_t10.py`
- BM4seat：factor `6ab7f059cd820fa2a40a6d42`、run `6ab7f05bcd820fa2a40a6d43`；脚本 `pool4_bmt10_fi10.py`
- 均为 20210907–20260907 / 10 日调仓 / 10 组 / 0.30% 单边 / 沪深全A / 正向。

## 二、桥（与 V4/SWAPF 同口径，NB=0）

| 候选 | ΔNA | ΔNC（k 混合） | ΔComb k 混合 | flat | 月度DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| PARTT10 | +0.0131 | −0.0362 | **−602** | −774 | −162 |
| BM4seat | −0.0251 | +0.0584 | **+935** | +1078 | −133 |
| SWAPF（参照，09-26 已测） | −0.0196 | +0.0355 | +531 | +567 | −26 |

（含 NB：PARTT10 −334、BM4seat +419、SWAPF +128。桥脚本 `scripts/platform_pool_bridge_partt10_bm4seat_20260927.py`，数据 `platform_bridge_partt10_bm4seat.json`。）

## 三、结构解读

1. **PARTT10 死在换手**：AGG/G13 两席各 26.6%/次、各占 1/5 权重，实测池换手 **17.55%/次（模型 16.18%，+1.37pp，
   超出 +0.5~0.9pp 历史代理区间）** → 月换手 36.9% 深入越线；净额 +1.78pp 不够付 C 项折价。
2. **BM4seat 的热度全在 C 项**：净 +2.14pp、换手 +1.09pp/次（k=2 分母贴线未越），k 混合 NC +0.058 为三条实测最高；
   代价是 RankIC 0.0844 拉低 A 项（ΔNA −0.0251）。
3. **4 席违赛制**：`references/competition_rules.md`"有效因子少于 5 个时，当月积分冻结"→ BM4seat 不能直接进池；
   合规化方向 = 补第 5 席（+E 即 SWAPF、已测 +531；+F-verify10 未测，留待下一轮零算力枚举）。
4. **口径分歧仍在**：BM4seat 与 SWAPF 同样是"k 混合正 / 月度 DD 负"（+935 vs −133）；判据等 10 月首份平台快照。

## 四、过程与成本

- PARTT10 上批（09-26）被 300/300 上限拒；本批槽位释放后重提（新文件名 `-20260927`、全新 state）。
- 编码链已修复：`PYTHONUTF8=1` 下 batch 包装器不再 GBK 崩溃（预检 `preferredencoding=utf-8`）。
- PARTT10 提交中途会话被中断（run 已发出）；改为手动抓 `factor_result` + 补 state + `--report-only` 出报告，**未重跑**。
- 计费：各 4.0，合计 **8.0**；余额 **1616.120152**；到期礼包剩 **8.0**（09-30 23:16 作废）。

## 五、结论

- 10-01~03 删改窗口维持"不动作"为首选：三条实测候选没有一条在两个口径同时稳赢（SWAPF +531/−26、BM4seat +935/−133、PARTT10 双负）。
- 下一步（零算力、待批）：枚举"BM + F-I10-01 核心"的**合规 5/6 席**扩展（如 +F、+AGG、+G13 等组合），找 ΔNA/ΔNC 更均衡的版本再报批平台。
"""

(OUT / "summary-partt10-bm4seat.md").write_text(report, encoding="utf-8", newline="\n")
print("report written:", (OUT / "summary-partt10-bm4seat.md").stat().st_size, "bytes")

# ---- GOAL update ----
goal_path = ROOT / "GOAL.md"
raw = goal_path.read_bytes()
text = raw.decode("utf-8")
assert "\r" not in text, "GOAL has CR — stop"

anchor1 = "（09-30 23:16 前有效）。\n\n## 五、唯一可主动改变的杠杆"
assert text.count(anchor1) == 1, f"anchor1 count = {text.count(anchor1)}"
entry35 = """（09-30 23:16 前有效）。

35. **两条换池候选平台实测（2026-09-27 凌晨，实花 8.0）：PARTT10 桥 −602 被否决；BM4seat 桥 +935 但 4 席低于赛制下限**：
    - PARTT10（现役 −BM −F + AGG-IMPACT + G13，5 席；factor `6ab7eee79e9d797cfb2cf8ef`、run `6ab7eee99e9d797cfb2cf8f0`）：
      毛 24.73% / **净 22.08%（+1.78pp）** / **换手 17.55%/次（月 36.9%，深入越线）** / SR 1.1043 / DD 32.94% / RankIC 0.0921 / ICIR 0.3815；
      桥 ΔNA +0.0131、ΔNC −0.0362（k 混合）→ **−602/月**（flat −774；月度 DD −162）→ **不换**（V4 翻版：越线吃掉净额）。
      换手模型偏差：预估 16.18% vs 实测 17.55%（+1.37pp，超出 +0.5~0.9pp 历史代理区间——AGG/G13 两席各 26.6% 占 1/5 权重）。
    - BM4seat（现役 −E −F + F-I10-01，**4 席**；factor `6ab7f059cd820fa2a40a6d42`、run `6ab7f05bcd820fa2a40a6d43`）：
      毛 24.63% / **净 22.44%（+2.14pp）** / 换手 14.48%/次（k=2 分母 28.96% 贴线免费） / SR 1.0929 / DD 33.76% / RankIC 0.0844 / ICIR 0.3691；
      桥 ΔNA −0.0251、ΔNC +0.0584 → **+935/月**（k 混合为三条实测最高；flat +1078；月度 DD −133）。
    - **4 席 < 赛制"有效因子 ≥5"下限（低于则当月积分冻结）→ 不可直接进池**；合规化 = 补第 5 席（+E = SWAPF 已测 +531；+F 未测）。
    - 计费 8.0（2×4.0），余额 **1616.12**；到期礼包剩 8.0（09-30 23:16）。
      报告：`platform_pool_tests_20260926/summary-partt10-bm4seat.md`；桥数据 `platform_bridge_partt10_bm4seat.json`。

## 五、唯一可主动改变的杠杆"""
text = text.replace(anchor1, entry35)

anchor2 = "未计费 | 0 | 1624.12 |\n\n（平台计费有延迟"
assert text.count(anchor2) == 1, f"anchor2 count = {text.count(anchor2)}"
row = """未计费 | 0 | 1624.12 |
| 2026-09-27 凌晨 | 两条换池候选平台实测：PARTT10（桥 −602、否决）+ BM4seat（桥 +935、4 席不合规）各成功 4.0（第 35 条） | 8 | **1616.12** |

（平台计费有延迟"""
text = text.replace(anchor2, row)

new_bytes = text.encode("utf-8")
assert b"\r" not in new_bytes
assert not new_bytes.startswith(b"\xef\xbb\xbf")
goal_path.write_bytes(new_bytes)
print("GOAL updated:", len(raw), "->", len(new_bytes), "bytes")
print("entry35 present:", "35. **两条换池候选平台实测" in text)
print("ledger row present:", "2026-09-27 凌晨 | 两条换池候选平台实测" in text)