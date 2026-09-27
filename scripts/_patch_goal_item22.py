import io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = Path(r"D:\factor\GOAL.md")
lines = p.read_text(encoding="utf-8").splitlines()
target = "## 五、唯一可主动改变的杠杆"
idx = lines.index(target)
block = [
 "22. **第八轮全跑（5 条候选）+ 有符号分母规则推广（2026-09-25 深夜，22 算力）**：",
 "   - 结果：**K024 ✅**（平台 +6.51%，本地 8.63%，差 2.1pp，方向一致但 IC 弱：p=0.81、单调 0.31）；",
 "     **K031/K029 ❌** 平台端方向翻转 + 换手膨胀（分母含 `BBIBOLL_DOWN` / `ASI÷MA(ASI)`，同 K020 病理），",
 "     direction=0 反事后 ≈ +7.3% / +3.2% 仍不达标；**K013 ❌** k=34（×1e34）仍退化（换手 90.9%、IC≈0）；",
 "     **K030 ❌** 本地/平台两端均无 IC（rho 0.009 但属非单调尾部效应）。",
 "   - 规则升级：**「分母含相关系数」推广为「分母含相关系数/有符号近零序列」**——平台端共同表现【方向翻转 + 换手膨胀】，",
 "     方向必须实测；`scripts/platform_precheck.py` 已加 `signed_divisor` 标记（BBIBOLL_DOWN/ASI/DPO/ROC/TRIX/MACD_DIF/CCI/BIAS/MTM/ADTM 等）。",
 "   - **量级归一的可信区间 = 1e18 ~ 1e27**（k≥30 不可靠，K013 反例）。",
 "   - 复筛结论：kept 149 条里「旧门槛 + 非脆弱分母」**只剩 2 条**（K024 已通过、K030 无 IC）→ **本轮新簇池基本挖空**，",
 "     下一步要么换口径重新挖（新 GP 批次 / 放宽字段），要么从别处找独立信息。",
 "   - 运维：run 死亡率 50%（status=8、零节点、不计费），换全新 factor 重试 100% 恢复；单批花费 22.0（含 1 次部分计费）。",
 "   - 平台可复现清单更新：**K008 +13.71% ｜ K021 +11.27% ｜ K015 +10.36% ｜ K020 +13.28%（d=0）｜ K024 +6.51%（弱）**。",
 "",
]
out = lines[:idx] + block + lines[idx:]
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("inserted at", idx, "total lines", len(out))