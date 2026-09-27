import io, sys, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def read(path):
    raw = Path(path).read_bytes()
    return raw.decode("utf-8-sig"), raw.startswith(b"\xef\xbb\xbf"), b"\r\n" in raw

def write(path, text, bom, crlf):
    data = (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    Path(path).write_bytes(data)
    print("saved", path)

# ---------- SCORE_RULES.md ----------
p = r"D:\factor\research_reports\platform_alignment\SCORE_RULES.md"
t, bom, crlf = read(p)
head = "## 候选边际评估（2026-09-26 固化：池级 IC 代理 + 换手地板）"
tail = "\n## 已知残差与未验证项"
i, j = t.find(head), t.find(tail)
assert i != -1 and j != -1 and i < j, (i, j)
new_section = """## 候选边际评估（2026-09-26 二次修正：回到官方 A 口径）

### A / B 项的官方口径（283 池验证到 1e-12，见 §公式）
- 每席 `s_i = |RankIC 均值| × IR(RankIC 序列) × win(对齐后 RankIC > +0.02 的硬计数占比)`；
  **不是**因子分析页表格里的 Pearson `IC_IR`（§口径陷阱 1），也**不是**池级复合 IC 的乘积；
- `raw_a = Σ s_i / 席位数`（算术平均，加席只改分母与新增项）；
- 汇率：`0.01 na = 88 分/月`、`0.01 nb = 154 分/月`（新池加成后）。

### 本地估计 s_i 的唯一正确做法（已对现役席校准）
从平台**单因子 run** 的 `query_rank_ic_sequence_chart`（120 期 RankIC 序列）重算：
`IR = mean/std(ddof=1)`；`win = #(sign(mean)·RankIC > +0.02)/N`（先按符号对齐再数）。
实现：`scripts/platform_si_scan_20260926.py`（扫全机 239 个 run）。
校准：T10-ADD-BM 席复现 **0.058864 vs 平台池记录 0.059267（−0.7%）**；其余四席 ±3%~±8%。

### 两个已发生的算术错误（2026-09-24 桥表；2026-09-26 修正）
1. 候选 `s_i` 用了 Pearson `IC_IR`（AGG 0.4379）与抄错的胜率（0.6167 vs 本 run 0.6917）
   → 四条候选（AGG/G13/DOWNSIDE/WC）的 `s_i` 被低估 **37%**；
2. 池 `raw_a` 用了本机重建面板席均 **0.01912**（T10 席 0.0373 vs 平台 0.0593）而不是平台池记录 **0.025893**
   → 「加席」边际被压低、「换掉 T10」被算成正号。
修正后的边际（`a-basis-correction-20260926/marginals.csv`）：**加第 6 席 ≈ +0.7~+1.0 千分/月**；
**换掉 T10-ADD-BM ≈ −0.9~−1.0 千分**；**换掉 SIZE-ONLY** 的 A+B 侧 +2.7 千分、C 未测。

### 池级复合 IC 的正确用法（不是 A 项）
池自身 Run 的 `RankIC / IC_IR / P(IC>0.02)` 只作**描述性诊断**（例如 T2 加席后
池级 RankIC 0.0919→0.0893、`P(IC>0.02)` 70.83%→63.87%，说明该席稀释了池的一致性），
**不能代入 A 项公式**。

### 换手地板（仍然有效）
`turn_month = turn_per_rebalance × 当月调仓次数`，与 `T*` 比之前先看有没有**跨过 0.30**：
基线 0.268（地板下，无惩罚）；加到 0.35 / 0.403 后 rawC 分母惩罚 ×0.857 / ×0.686。
**30–40% 换手档整档关闭**（2026-09-26 T2/T4 两条独立 6 席实测证伪）。

### 经验校准（仍然有效）
本地逐月 C 机器给候选边际**系统性偏高**——AGG 加席本地 +666 vs 平台实测池指标反解 ≈ −254
（旧 A 口径下）；T2 +482 vs ≈ −2,330；T4 +254 vs ≈ −4,960。C 侧排序可参考，绝对值与符号不可信。
"""
t = t[:i] + new_section + t[j:]
write(p, t, bom, crlf)

# ---------- turnover-relaxed-20260926/summary.md：加一节更正 ----------
p2 = r"D:\factor\research_reports\platform_alignment\turnover-relaxed-20260926\summary.md"
t2, bom2, crlf2 = read(p2)
assert "### 6.7 口径更正" not in t2
t2 = t2.rstrip("\n") + """

### 6.7 口径更正（2026-09-26 深夜，零算力）

§6.3 的 A 侧「池级 IC 代理」（`RankIC × IC_IR × P(IC>0.02)`）**不是平台 A 口径**：
平台 A 是各席位 `s_i = |RankIC| × IR(RankIC 序列) × win(对齐硬计数)` 的算术平均。
因此 **T2/T4 的 ΔNA（−0.031 / −0.0043）是启发式，不是平台量，T2/T4 的 A 侧实际未测**；
两条"不进池"的结论仍由实测支撑（净额 −2.37pp / −1.44pp、换手 +4.11pp / +5.81pp）。
同批审查还发现 09-24 桥表把**候选 s_i 低估 37%**、把池 `raw_a` 用成本机重建口径（0.01912 vs 平台 0.025893），
修正后「加第 6 席」的边际回到 **+0.7~+1.0 千分/月**。
详见 `research_reports/platform_alignment/a-basis-correction-20260926/summary.md`。
"""
write(p2, t2, bom2, crlf2)

# ---------- failure registry：给两条 09-26 记录加更正说明 ----------
p3 = r"D:\factor\research_reports\platform_alignment\factor_alignment_failure_registry.json"
raw3 = Path(p3).read_bytes()
bom3 = raw3.startswith(b"\xef\xbb\xbf")
reg = json.loads(raw3.decode("utf-8-sig"))
note = ("2026-09-26 深夜口径更正：本条的 dNA（池级 IC 代理）为启发式、非平台 A 口径"
        "（平台 A = 各席位 s_i 的算术平均），T2/T4 的 A 侧实际未测；"
        "结论由实测净额/换手支撑。另：09-24 桥表把候选 s_i 低估 37%、池 raw_a 用成本机重建口径 —— "
        "修正后「加第 6 席」边际回到 +0.7~+1.0 千分/月。见 a-basis-correction-20260926/summary.md。")
touched = 0
for rec in reg["unacceptable_records"]:
    if rec.get("id", "").startswith("platform_pool_tests_20260926"):
        rec["notes"] = (rec.get("notes", "") + " " + note).strip()
        touched += 1
print("registry records touched:", touched)
Path(p3).write_bytes((b"\xef\xbb\xbf" if bom3 else b"") + json.dumps(reg, ensure_ascii=False, indent=1).encode("utf-8"))
print("saved", p3)
