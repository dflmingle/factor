# VV6_1250 平台实测（2026-09-29）

批准：用户批准 1 条平台因子分析（预检费用 4.0）；实际扣费 4.0（首次因算子名失败扣 2.0 + 修正后成功扣 2.0），末余额 1588.12。

## 结果

- 提交（成功版）：`(0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,1250)))`，direction=1，cycle=10，组数 10，窗口 20210907–20260907，成本 0.30%。
- 平台：IC_mean **+0.1793** / Rank_IC **+0.2236** / ICIR **0.9232** / p **0.1620** / mono 0.96；
  long +63.71% / turn 65.98% / cost 9.98% / **net +53.73%** / 多头 SR 3.63 / DD 0% / 月胜率 100%。
- **有效期数 = 4 期**（IC 序列 2026-07-03、07-17、07-31、08-14）：`STDDEV(VOLUME,1250)` 的暖机 ~1250 交易日
  把 5 年回测吃掉 4.8 年，平台因子分析仅在回测区间内暖机 → 只剩最后 4 期。
- **方向与本地一致（正）**；ICIR 0.9232 与本地探针 0.926 数值巧合，但两口径有效期不同（本地探针 ~119 期，
  平台 4 期），不能互证。
- p=0.162 不显著；+53.73% net / 100% 月胜率 / 0% DD 全部来自最后 2 个月，不可作候选依据。

## 结论

1. **平台可跑，但 1250 基准在比赛 5 年窗口下不可用**：有效样本仅 4 期，任何池级边际测算都没有意义。
2. volstab 家族若要进池，基准窗口必须 ≤750（本机 max_backtrack=756 的限制与平台行为一致，本地 500/750 代理是对的方向）。
3. 算子名教训：平台无 `TSSTD`，标准名为 `STDDEV`/`STD`（`vendor/skill-pandaai-factor-online/references/operators.md:100-101`）。本地 GP 签名不能直接当平台公式，提交前除了撞名预检还要过**算子表存在性检查**（本次 platform_precheck 未覆盖 `TSSTD`，已暴露缺口）。

## 复现

```bash
python scripts/platform_precheck.py research_reports/platform_alignment/vv6-1250-platform-20260929/candidates_v2.txt
python scripts/pandaai.py batch research_reports/platform_alignment/vv6-1250-platform-20260929/candidates_v2.txt \
  --start 20210907 --end 20260907 --cycle 10 --group-number 10 --round-trip 0.003
```

产物：`candidates_v2.report.md` / `candidates_v2.results/6abb22809e9d797cfb2d067b.json`（raw）/ `submit_v2.log`（首次失败版见 `submit.log`）。

## 对手侧对照（2026-09-29 补，零算力）：对手没有用严格 1250 窗口

`side-line-20260927/pool_factors_dump.txt` 里对手因子的 IC 样本数 `n` 是公开字段：

- 换手反转|新人报道（cycle=10）：F-I01_Alpha191_010_LW **n=119**（20210929..20260814）、F-J06 n=119、F-J08 n=119；
- Lavine X（cycle=5）：G17/E13 等 n=241；价值质量精选（cycle=1）n=1209。

对手这些因子在 5 年窗口里有**完整期数**；若用严格 `STD(x,1250)` 一类暖机，平台只会给 n=4
（本次 VV6_1250 实测）。因此：

1. `opp-signature-match-20260928` 的"对手用 volstab 族"只是三维签名（ic/icir/win）最近邻
   （283/297 hit，报告自警"签名碰撞廉价"），**不是窗口/公式复刻**；
2. 对手的"波动稳定性形状"必然用短暖机实现（或非日频长窗），目标签名是 119 期口径
   ic≈.125 / icir≈.980 / win≈.798；
3. 下一步全在本地零算力：在 ≤500/750 窗口重构能到 119 期 icir≈.98 的构造
   （本地当前短期最好 volV6_504/.915、volV6_756/.922、慢腿探针 .926——仍有差距）。
