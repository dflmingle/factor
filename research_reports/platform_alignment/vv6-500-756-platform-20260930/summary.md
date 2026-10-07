# VV6_500 / VV6_756 平台实测（2026-09-30）

背景：消耗当晚 23:59:59 到期的 GIFT 额度（4.0）。用户批准测 2 条：S01 簇（VV6 volstab 族）
里从未上过平台的两个窗口版本（与既有簇最高 |rho| 仅 0.52），对标 09-29 的 VV6_1250
（1250 窗在 5 年窗内只剩 4 期，被判不可用）。

## 结果（direction=1，cycle=10，10 组，20210907–20260907，0.30% 单边）

| 候选 | 公式 | IC_mean | Rank_IC | ICIR | IC_p | mono | long% | turn% | cost% | net% | SR | DD% | 月胜率 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VV6-500-platform | `(0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,500)))` | 0.0503 | 0.0917 | 0.5595 | 0.0000 | 0.92 | 13.22 | 67.02 | 10.13 | **+3.09** | 0.93 | 34.57 | 65.00 |
| VV6-756-platform | `(0-(STDDEV(VOLUME,6)/STDDEV(VOLUME,756)))` | 0.0428 | 0.0825 | 0.4362 | 0.0025 | 0.90 | 9.28 | 67.12 | 10.15 | **-0.87** | 1.49 | 21.15 | 70.37 |

（SR / DD / 月胜率为方向选中单因子多头诊断，非池级 C 指标。）

## 结论

1. **≤756 窗口可在 5 年窗内完整回补期数**：500/756 都跑满（对比 1250 只剩 4 期），
   09-29 的"窗格结论"落实。
2. **方向正确**（direction=1 下 net 与本地同号），但**换手 ~67% 是共同短板**：年成本 ~10.1%，
   吃掉大头；500 净剩 +3.1%，756 直接转负（-0.9%）。
3. 756 vs 500：毛超额更低但风险更好（DD 21.2% vs 34.6%，SR 1.49 vs 0.93，月胜率 70.4% vs 65.0%）
   —— 作为低换手改造 / 池组合素材，756 形态更优；单席直接进池两条都不够（换手太高）。
4. 两条 p 值（0.0000 / 0.0025）过 0.025 阈值，但 p 检验对单因子 IC 序列意义有限，
   不单独作为入选依据。

## 事故与修复（重要，记录在案）

- `batch.py` 连续两次崩在解码：本机 `pandaai-cli` 在 `PYTHONIOENCODING=utf-8` 时输出 UTF-8、
  未设置时输出 GBK；而 `batch.py` 固定按 locale（GBK）解码 → 只要设了 `PYTHONIOENCODING` 就必崩。
- **客户端崩了但服务端 run 照常执行并扣费**（A 遭遇一次；B 的第一次 run 因瞬时"未登录"失败、
  未扣费，重试成功）。
- 修复产物：`scripts/_recover_vv6_batch_20260930.py` —— `factor_info` 查 `last_run_id` →
  `factor_result` 取回已完成结果（免费）→ 按 `cache_result` 格式落盘并回写 state；
  之后 `batch.py` 只出报告、零重跑。
- **以后在本机跑 batch.py 的守则：不要预设 `PYTHONIOENCODING`**（让 CLI 走 GBK、与 batch.py 的
  locale 解码匹配），或直接走 recover 脚本路径。

## 费用

- 总扣 4.0（A 2.0 + B 2.0），全部来自 09-30 到期的 GIFT；余额 1530.12 → 1526.12；
  `nextExpireAmount` 归零 → 下一档 118.0 @ 2026-10-07 23:16:43。

## 产物

- `candidates.txt`、`candidates.txt.state.json`、`candidates.results/*.json`（raw payload）
- `candidates.report.md` / `candidates.report.csv`
- `submit.log`（首次崩溃）、`submit_resume.log`（二次崩溃）、`submit_recover.log`（最终报告）

## 复现

```bash
python scripts/platform_precheck.py research_reports/platform_alignment/vv6-500-756-platform-20260930/candidates.txt
# 提交（本机注意：不要预设 PYTHONIOENCODING）
python scripts/pandaai.py batch research_reports/platform_alignment/vv6-500-756-platform-20260930/candidates.txt \
  --start 20210907 --end 20260907 --cycle 10 --group-number 10 --round-trip 0.003
```
