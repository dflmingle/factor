import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"D:\factor\GOAL.md"
text = open(p, encoding="utf-8").read()

new_items = """12. **平台算子/字段拼写 ≠ 本地 GP 拼写（2026-09-25，2 算力买到的教训）**：本地表达式直接提交会被平台
   工作流以 **错误码 10068（变量未定义）** 拒绝。必须先渲染：
   `Inv(X)→(1/(X))`、`Sub/Add/Mul/Div→中缀 - + * /`、`TsStd(X,N)→STDDEV(X,N)`、
   `TsMax(X,N)→TS_MAX(X,N)`、`TsDiv(X,N)→(X/MA(X,N))`、`TsCorr(X,Y,N)→CORR(X,Y,N)`，字段名写成大写
   （`a_share_market_val` → `A_SHARE_MARKET_VAL`）。渲染器：`scripts/alphaprobe_gp_tushare.py::expression_to_panda_formula`。
   方向语义：分组按因子值升序，`--factor-direction 1` 时多头=分组10=**因子值最高十分位**，与本地 `score()`
   的 topk 一致 → 本地 net 对应的平台方向就是 1。
   （`research_reports/platform_alignment/gp-platform-tests-20260925/summary.md`）

13. **新簇候选平台复现（2026-09-25，16 算力）：3 条只对上 1 条，CAL 字段族在平台端退化**：
   - ✅ K008/cand0000：平台净 **+13.71%**（本地 12.49%，Δ**1.2pp**）、换手 44.39%、RankIC 0.0501、
     IC_mean 0.0437、单调性 0.92、十组单调（-8.38% → +20.42%）→ **平台确认可用**。
   - ❌ K015/cand0003（Δ−24.3pp）与 K020/cand0110（Δ−27.8pp）：平台端**完全退化**——十组年化超额全落在
     ±0.8% 内、**每组换手都 ~90.3%**、多空组合≈0、RankIC≈0；本地对照是换手 45.3%/39.9%、RankIC 0.037/0.036。
     两条共有 `CAL_20D_AMT_MA` + `BS_TOTAL_ASSETS`，且多级除法链把因子值压到 **1e-19~1e-28**
     （未退化的 K008 只有 **1e-10**）；本地这些 CAL 字段**全部是 local_proxy**。
     两条已写入 `factor_alignment_failure_registry.json`（`cause_codes = degenerate_platform_factor_panel`）；
     `cal_20d_amt_ma` 因此已有 2 条 >5pp 且无 ≤5pp 反例，**已达自动拉黑门槛**。
   - 影响面：205 条候选 **114 条**用 `CAL_*`，106 个新簇 **86 个**的最好成员含 `CAL_*`。
     **在拿到字段级证据前，不要把 CAL 族候选当作平台可用候选。**

14. **"独立信息"池的现实（2026-09-25 本地复核，零算力）**：205 条候选里同时满足 net≥10% 且 2026≥4% 的有
   31 条，其中**除 K008/cand0000 外全部 |corr_size| ≥ 0.5**；净额最高的 17 条（19%~22%）`corr_max_seat`
   **全是 size_only**（印证第 7 条）。按"与现有成员最大相关"重排，最独立的一档
   （cand0038 maxMem 0.009、cand0026 0.146、cand0013 0.287）**全部属于同一结构族**：
   `…/cal_20d_amt_ma/…/bs_total_assets` 的多级除法链，正是本轮两条退化候选的同族。
   → **新簇里的"独立信息"目前集中在一个平台端未验证的字段族上**：先证实/证伪这个族（量级复跑），
   再谈加席；非 CAL 的高净额候选已被 size 订死，没有独立信息。
"""

anchor = "## 五、唯一可主动改变的杠杆"
assert anchor in text
text = text.replace(anchor, new_items + "\n" + anchor, 1)

budget_anchor = "| 2026-09-24 | 宽字段 GP 挖掘（374 字段）+ 放宽换手重筛（全本地） | 0 | 1752.12 |\n"
assert budget_anchor in text
budget_rows = budget_anchor + (
    "| 2026-09-25 | 3 条短名单候选平台复现（K008 成功 / K015 退化 / K020 先失败后退化） | 16 | 1702.12 |\n"
    "| 2026-09-25 | 其中：本地算子名提交失败 2（错误码 10068）+ 平台侧计费服务超时失败 2（未出结果） | （含上面 16 内） | 1702.12 |\n"
)
text = text.replace(budget_anchor, budget_rows, 1)
open(p, "w", encoding="utf-8").write(text)
print("GOAL.md updated, lines:", len(text.splitlines()))