import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def load(path):
    raw = Path(path).read_bytes()
    return raw, raw.decode("utf-8-sig"), raw.startswith(b"\xef\xbb\xbf"), b"\r\n" in raw

def save(path, text, bom, crlf):
    out = text.replace("\n", "\r\n") if crlf else text
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    Path(path).write_bytes(data)
    print("saved", path)

def replace(text, old, new, label):
    assert text.count(old) == 1, (label, text.count(old))
    return text.replace(old, new)

# ---------------- GOAL.md ----------------
p = r"D:\factor\GOAL.md"
_, t, bom, crlf = load(p)

t = replace(t,
 "| rawA → NA | 0.0191 → **0.239**（新池上限 0.70） | 本地代理，对平台 corr 0.982 |",
 "| rawA → NA | **平台实测 0.0259 → 0.3237**；本机重建口径 0.0191 → 0.239 | 2026-09-26 修正：两口径差 26%，T10 席被重建面板低估 37%（见 `research_reports/platform_alignment/a-basis-correction-20260926/summary.md`） |",
 "goal-baseline-row")

t = replace(t,
"""以 NA 0.239、NC 1.00 为基准折算：

| NB | 折算积分 | 当前榜上位置 |
| ---: | ---: | --- |
| 0 | 21,903 | ≈第 24 名 |
| 0.3 | 26,523 | ≈第 4 名 |
| 0.5 | 29,603 | 第 4 名档 |
| 1.0 | 37,303 | 第 1 名档 |""",
"""以**平台实测 NA 0.3237**、NC 1.00 为基准折算（2026-09-26 修正；此前误用本地口径 0.239，
系统性低估约 +745 分/月，据同榜快照反推名次档位）：

| NB | 折算积分 | 当前榜上位置 |
| ---: | ---: | --- |
| 0 | 22,649 | 第 10~20 名之间（23,047 第 10 / 22,121 第 20） |
| 0.3 | 27,269 | ≈第 4 名（25,917） |
| 0.5 | 30,349 | 第 3 名档（30,318） |
| 1.0 | 38,049 | 第 1 名档（35,517） |""",
 "goal-projections")

t = replace(t,
 "| NA 0.239 → 0.70 | +4,048 分/月 | 需要**新信号族**：高 IC（换手须 **≤30%/次**；30–40% 档已于 2026-09-26 被平台证伪，见第 25 条） |",
 "| NA 0.3237 → 0.70 | +3,311 分/月 | 需要**新信号族**：高 IC（换手须 **≤30%/次**；30–40% 档已于 2026-09-26 被平台证伪，见第 25 条；A 基准 2026-09-26 修正，见第 26 条） |",
 "goal-lever")

t = replace(t,
 "     胜率 70.83%→63.87%）→ **ΔNA = −0.031（−269 分/月）**。本地 A 项假设\"池 rawA 上移 (s6−rawA)/6\"是错的：\n      候选自己的 `s_i_rank` 高 ≠ 池级 IC 改善。",
 "     胜率 70.83%→63.87%）→ **ΔNA = −0.031（−269 分/月）**。本地 A 项假设\"池 rawA 上移 (s6−rawA)/6\"是错的：\n      候选自己的 `s_i_rank` 高 ≠ 池级 IC 改善。\n      **【2026-09-26 深夜修正】该「池级 IC 代理」不是平台 A 口径**——平台 A 用各席位 s_i 的算术平均，\n      池级复合 IC 的乘积只是启发式；T2/T4 的 A 侧实际未测。本条结论靠**净额与换手两项实测**支撑，ΔNA 不要再被引用。\n      见第 26 条与 `research_reports/platform_alignment/a-basis-correction-20260926/summary.md`。",
 "goal-item25-anei")

t = replace(t,
"""     **损失全部来自换手，不是信号质量**；失败登记表第 14 条 `platform_pool_tests_20260926:pool6-t4v6:POOL6-T4V6-20260926`。""",
"""     **损失全部来自换手，不是信号质量**；失败登记表第 14 条 `platform_pool_tests_20260926:pool6-t4v6:POOL6-T4V6-20260926`。""",
 "goal-noop")

# 新增第 26 条，插在 §五 之前
anchor = "\n## 五、唯一可主动改变的杠杆"
item26 = """
26. **A 侧口径修正（2026-09-26 深夜，零算力）——「加席不值得」是两处算术错误的产物**：
   - 09-24 桥表把候选 `s_i` 用了因子分析页的 **Pearson `IC_IR`**（AGG 0.4379）而不是 RankIC 序列 IR（0.5778），
     胜率也抄错（0.6167 vs 本 run 的 0.6917）→ 四条候选的 `s_i` 被低估 **37%**；
   - 同表池 `raw_a` 用了本机重建面板席均 **0.01912**（T10 席 0.0373 vs 平台 0.0593，−37%）而不是平台池记录 **0.025893**；
   - 修正后（平台实测 s_i + 同结构 B 模型 + 实测 C 锚）：**加第 6 席 AGG ≈ +0.7~+1.0 千分/月**
     （A +355 / B 长期 +829 / C −212~−427），DOWNSIDE、G13 同档；WC 的 C 实测 −0.074 nc，仍排除；
   - **换掉 T10-ADD-BM ≈ −0.9~−1.0 千分**（T10 是全池最强席，s_i 0.0593）——此前「换席 +227~+507」是错误 2 的产物；
     **换掉 SIZE-ONLY** 的 A+B 侧 +2.7 千分但 C 侧从未测过，是唯一未被证伪的换席路线（要上平台才能定）；
   - 本机估计 s_i 的正确做法（已对 T10 席校准到 −0.7%）：`scripts/platform_si_scan_20260926.py`
     扫描 239 个平台 run 的 RankIC 序列重算，见 `research_reports/platform_alignment/a-basis-correction-20260926/summary.md`。
"""
t = replace(t, anchor, item26 + anchor, "goal-item26")

# 算力账本加一行（零算力）
t = replace(t,
 "| 2026-09-26 | 对账：第 5 轮读数 1654.12 → 收尾读数 1648.12（差额 2.0；V6 的 run 快照 `balance` 即 1648.12，无法区分「补扣 2.0 + V6 4.0」与「V6 按 6.0 计」） | 2 | **1648.12** |",
 "| 2026-09-26 | 对账：第 5 轮读数 1654.12 → 收尾读数 1648.12（差额 2.0；V6 的 run 快照 `balance` 即 1648.12，无法区分「补扣 2.0 + V6 4.0」与「V6 按 6.0 计」） | 2 | **1648.12** |\n| 2026-09-26 | A 侧口径修正（候选 s_i 与池 raw_a 两处算术错误，见第 26 条） | 0 | 1648.12 |",
 "goal-ledger-row")

save(p, t, bom, crlf)
print("GOAL.md patched")
