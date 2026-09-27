import io, sys, json, shutil
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = Path(r"D:\factor")
R = root / "research_reports" / "platform_alignment"
main_sum = R / "gp-platform-tests-20260925" / "summary.md"
round2_sum = R / "gp-platform-tests-20260925" / "round2" / "summary.md"

# --- sanity: files readable as utf-8 ---
t = round2_sum.read_text(encoding="utf-8")
print("round2 summary first line:", t.splitlines()[0])
assert "ASI" in t and "1700.12" in t

# --- 1. GOAL.md ---
goal_path = root / "GOAL.md"
g = goal_path.read_text(encoding="utf-8")

anchor5 = "## 五、唯一可主动改变的杠杆"
assert g.count(anchor5) == 1, g.count(anchor5)

item15 = """15. **算子名/字段名撞名是平台提交的硬杀手（2026-09-25，2 算力 + 零算力全池预检）**：平台 `ASI` 既是算子
    `ASI(OPEN,CLOSE,HIGH,LOW,M1,M2)`（`references/operators.md:294`），又是 catalog 字段（`references/fields-ma-indicators.md:11`）。
    裸写 `ASI`（无括号）会被解析成**算子对象**，`CORR` 收到非序列参数 → 报错 10000 "A和B必须都是pandas.Series/DataFrame 或 numpy.array"。
    K021/cand0013 两条候选（原式 + ×1e18）同点同错，23.7s 失败；**失败运行也计费**（2 条共 2.0）。
   - 全池预检（`scripts/_platform_name_collision_check.py`）：205 条里 **27 条**含"字段名 = 平台算子名"的裸 token
     （`asi` 5、`mass` 3、`cci` 3、`dpo` 3、`trix` 2、`kdj_k` 2、`adxr` 2，`kdj_d`/`kdj_j`/`mfi`/`atr`/`vr`/`roc`/`wr` 各 1）；
     其中好候选（net≥10%、2026≥4%）**9 条**。
   - **提交前必须跑撞名预检**；撞名候选要么改用算子形式（如 `ASI(OPEN,CLOSE,HIGH,LOW,26,10)`）、要么等价展开、要么换字段。
   - 量级（1e18）假设**仍未检验**：本轮公式没跑到计算阶段，验证它必须换零撞名候选（详见 `gp-platform-tests-20260925/round2/summary.md`）。

"""

g = g.replace(anchor5, item15 + anchor5, 1)

bill_row = "| 2026-09-25 | round2：K021 消解尝试 2 条（`ASI` 撞名触发 10000 类型错误，均无结果；**失败也计费**） | 2 | 1700.12 |\n"
bill_anchor = "| 2026-09-25 | 其中：本地算子名提交失败 2（错误码 10068）+ 平台侧计费服务超时失败 2（未出结果） | （含上面 16 内） | 1702.12 |\n"
assert g.count(bill_anchor) == 1
g = g.replace(bill_anchor, bill_anchor + bill_row, 1)

goal_path.write_text(g, encoding="utf-8")
print("GOAL.md updated:", item15.splitlines()[0][:40], "| billing row added")

# --- 2. main summary.md ---
s = main_sum.read_text(encoding="utf-8")
assert "## 七、复现入口" in s
addendum = """

## 八、第二轮（2026-09-25 晚，K021 修复尝试，2 算力）——失败，根因是"算子名/字段名撞名"

- 2 条候选（cand0013 原式 + ×1e18）都在**线性因子构建**节点失败：错误码 10000，
  `Error in formula 1: A和B必须都是pandas.Series/DataFrame 或 numpy.array`。
- 根因：裸写 `ASI` 被平台解析成算子 `ASI(OPEN,CLOSE,HIGH,LOW,M1,M2)` 的对象，`CORR` 拿到非序列参数。
  `VMA3` 属无同名算子的"逗号族"catalog 字段（同族 `DAVOL5` 第一轮已通过）→ 嫌疑集中在 `ASI`。
- **量级（1e18）假设仍未检验**（没跑到计算阶段）；全池撞名预检：205 条里 27 条、好候选里 9 条。
- 花费：1702.12 → **1700.12**（2.00；失败也计费）。
- 详情与下一步选项：`round2/summary.md`；预检脚本：`scripts/_platform_name_collision_check.py`。
"""
main_sum.write_text(s + addendum, encoding="utf-8")
print("main summary.md updated, bytes:", main_sum.stat().st_size)

# --- 3. desktop copy ---
desk = Path(r"C:\Users\58302\Desktop\新簇候选平台验证-20260925.md")
merged = main_sum.read_text(encoding="utf-8") + "\n\n---\n\n" + t
desk.write_text(merged, encoding="utf-8")
print("desktop copy refreshed:", desk.stat().st_size)

# --- 4. failure registry field notes ---
reg_path = R / "factor_alignment_failure_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8"))
notes = reg.setdefault("field_evidence_notes", {})
notes["asi"] = ("2026-09-25 round2：平台侧 `ASI` 同时是算子 ASI(OPEN,CLOSE,HIGH,LOW,M1,M2) 和 catalog 字段；"
                "裸写 `ASI` 被解析为算子对象，CORR 收参报 10000 类型错误（A和B必须都是 Series/DataFrame 或 numpy.array）。"
                "字段本身未被证伪，但**公式里必须写成算子形式或等价展开**，不能裸用。")
reg.setdefault("platform_name_collision_policy", {
    "checked_at": "2026-09-25",
    "pool_size": 205,
    "colliding_candidates": 27,
    "colliding_tokens": ["asi", "mass", "cci", "dpo", "trix", "kdj_k", "adxr", "kdj_d", "kdj_j",
                         "mfi", "atr", "vr", "roc", "wr"],
    "rule": "候选公式里的裸字段 token 若与平台算子名相同，提交前必须改为算子形式/等价展开/换字段",
    "checker": "scripts/_platform_name_collision_check.py",
})
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("registry updated; notes keys:", len(notes), "| size:", reg_path.stat().st_size)
