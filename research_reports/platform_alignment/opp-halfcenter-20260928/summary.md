# 对手因子定向挖掘：半厘米搜索 / 慢腿探针 / 第六席评估（2026-09-28）

本地零平台算力。目标：把榜单上"好的因子"对应的构造挖出来，并判断其对现役池的边际。

## 1. 半厘米混权网格（3192 组）
`opp_halfcenter_search_20260928.py`（22 基底 × 10 稳定性腿 × 19 档 w，119 个信号日，
2021-09-29 起，label 1+10）。

- 结果：**IC 与 win 可以精确命中，ICIR 命中不了**。
  全网格在 IC≥0.09 时 ICIR 上限 **0.857**（retrev5×volV5y w=0.15）。
  榜单头部的 ICIR 目标：010_LW 0.980 / 042 0.975 / R03 0.944（平台口径）。
- 目标级就近度（平台口径 d，越大越远）：ks91 0.059、E13 0.162、G16 0.170、
  G17 0.246、E5 0.223、R03 0.507、042 0.773、010_LW 1.591。

## 2. 平台↔本地标定（关键口径修正）
`score-rules-20260924/verification.json` 五席平台值/本地值中位比：
**ic ×0.981、icir ×1.052、win ×0.975**（±2~5%）。

换算后本地等价的榜单目标与命中判定（容差 ic 0.005 / icir 0.03 / win 0.02）：

| 目标 | 本地等价 (ic/icir/win) | 最优构造 | 判定 |
|---|---|---|---|
| G17-zscore3 | .1089/.820/.787 | amihud20×volV5y w=.20 | 16 组可行 |
| E13-P2+skew | .1070/.779/.796 | 042_ref×volV5y w=.30 | 可行 |
| ks91-acf-3y | .1021/.676/.724 | intr40×rel_T5_T252 w=.60 | 可行（d=0.23） |
| C260912-B01 | .0954/.826/.795 | retrev5×volV5y w=.20 | 可行 |
| R03 | .0981/.897/.833 | retrev5×volV5y w=.10 | 差 ICIR −0.04 |
| 042 | .0975/.927/.793 | retrev5×volV5y w=.20 | 差 ICIR −0.08 |
| 010_LW | .1277/.932/.819 | amt60×volV5y w=.25 | 差 IC −0.018 / ICIR −0.11 |

## 3. 慢腿探针：找到 ICIR 破 0.90 的腿
`opp_slowleg_probe_20260928.py`（27 条慢变量腿）→ `opp_volv5_refine_20260928.py`
（k×基准窗口网格）：

**`VV6 = −STD(VOLUME,6)/STD(VOLUME,1250)`：IC 0.0980 / ICIR 0.926 / win 0.815 / s_i 0.0740**
（旧库版本 volV5y 是 k=10 → ICIR 0.843；本腿是同一 volstab 家族的新参数化）

- k 扫描：k=3→0.883、k=4→0.905、k=5→0.917、**k=6→0.926**、k=8→0.895（基准 1250）。
- 与 relT5_504（−MA(TURNOVER,5)/MA(TURNOVER,504)，ICIR 0.844）混权无增益。
- 否证两条机制：**时间平滑**（span 2/3/5/10 单调变差）与**多腿集成**（3/5/8 腿 ≤0.857）。

## 4. 池级边际（第六席评估，`opp_vv6_delta_20260928.py`）
本地代理：VV6_500（2y 基准）/VV6_750（3y，本地数据 2018 起 + max_backtrack 756 限制，
1250 无法复现）/VV6_MIX500（与换手率 5/500 混）。

| 候选 | s_i | ΔE | ΔT | ΔNC | ΔC | ΔComb(up) |
|---|---|---|---|---|---|---|
| VV6_500 | .0454 | −0.424 | +0.332 | −0.095 | −1,887 | **−1,234** |
| VV6_750 | .0450 | −0.461 | +0.328 | −0.116 | −2,303 | **−1,660** |
| VV6_MIX500 | .0472 | −0.208 | +0.207 | −0.063 | −1,250 | **−553** |

- 与五席平均 Spearman：T10-ADD-BM **+0.50**、B2M_lf−size +0.19、B2M_lf+impact +0.15、
  impact60 +0.11、SIZE-ONLY −0.15 → 与 T10 半冗余。
- 结论：**签名可复刻，但作为第六席没有分**——gross E 大负 + 换手 +0.21~0.33 的双重打击。
  榜单头部用同一家族，但他们的池结构（多因子数 / 组合构造）与我方五席等权不同。

## 5. 复现
```bash
python3 scripts/opp_halfcenter_search_20260928.py --phase validate   # 建缓存 ~1.3GB
python3 scripts/opp_halfcenter_search_20260928.py --phase sweep
python3 scripts/opp_halfcenter_smooth_20260928.py
python3 scripts/opp_halfcenter_ens_20260928.py
python3 scripts/opp_slowleg_probe_20260928.py
python3 scripts/opp_volv5_refine_20260928.py
python3 scripts/opp_vv6_delta_20260928.py        # 池级 ΔComb（约 8 分钟）
```
产物：`matches_top.csv`(180) / `smooth_probe.csv` / `ens_probe.csv` / `slowleg_probe.csv` /
`volv5_probe.csv` / `vv6_seat_corr.csv`；`e-decomp-20260928/cand_summary.csv` 追加 3 行。
