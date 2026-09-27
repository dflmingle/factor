from pathlib import Path

p = Path("D:/factor/research_reports/platform_alignment/turnover-relaxed-20260926/summary.md")
text = p.read_text(encoding="utf-8")

old = """桥表：`platform_pool_tests_20260926/platform_bridge.{json,csv}`；
月度对比脚本：`scripts/pool_monthly_compare_20260926.py`；桥脚本：`scripts/platform_pool_bridge_20260926.py`。"""
new = """**口径说明（本轮新增确认）**：平台的 `excessAnnualized` 是**毛值**——`--round-trip` 只在本地
`batch.py` 里用于折算 net%，从不传给平台 CLI（`factor_create` 只收 start/end/cycle/group/direction/pool）。
所以净值一律用「毛超额 − 换手 × 2 × 0.30% × 252/10」自算，基线净 20.30% = 22.32% − 2.02%。

桥表 `platform_pool_tests_20260926/platform_bridge.{json,csv}` 里 A/NB 仍按**本地座位 S_i** 口径
（得 −172 / +910 分/月），本节 headline 的 −2,330 改按**平台池级 IC 代理**口径；两者差异全在 A 侧假设，
而池级 IC 代理已被 base 池 0.02589 fixture 与 AGG 案例双向校验 → 采信 −2,330 一侧。
月度对比脚本：`scripts/pool_monthly_compare_20260926.py`；桥脚本：`scripts/platform_pool_bridge_20260926.py`。"""
assert old in text
p.write_text(text.replace(old, new, 1), encoding="utf-8")

desk = Path("C:/Users/58302/Desktop/放宽换手平台实测-20260926.md")
dt = desk.read_text(encoding="utf-8")
assert old in dt
desk.write_text(dt.replace(old, new, 1), encoding="utf-8")
print("clarified cost convention + bridge bases in both copies")