# AGP 平台实测（2026-10-02，12 算力）

批次 `platform/candidates.txt`（3 条，formula 模式），窗口 `20210907..20260907`、cycle 10、
10 组、单边成本 0.30%、方向 1。费用 4.0×3 = **12.0**（<120s 档；78.5s/73.0s/69.7s），
余额 1512.12 → **1500.12**，账户因子 114 → 117。

提交前检查：
- `scripts/platform_precheck.py`：无撞名 / 无脆弱结构 / 量级 OK（预估 12.0，与实际一致）。
- `scripts/_alphagen_formula_verify_20261002.py`：三条公式仿真 vs 本地 W 复合，逐期截面秩相关
  mean ≥0.999999、min ≥0.999993 ⇒ **PASS**（W→平台公式转写无误）。

公式口径（沿用 v2 已验证写法）：`0-(...)` 避免一元负号、`/` 不用 `DIV`；
AGP03W 的 drift20 腿平台无 VWAP 字段，改用 v2 已验证的 `MA(CLOSE*VOLUME/AMOUNT,20)`
（与本地代理 vwap=10A/V 单调等价）。

## 一、平台结果（120 期，net 已扣 0.30% 单边成本）

| 因子 | factor_id | RankIC | ICIR(P) | mono | long% | turn%/次 | cost% | net% | SR | DD% | 月胜率 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AGP01W-20261002 | `6abf3c58cd820fa2a40a830f` | .1208 | .4993 | 0.97 | 21.32 | 51.49 | 7.79 | **+13.53** | 1.0646 | 30.81 | 66.67 |
| AGP03W-20261002 | `6abf3cbb2d2f6998fc1c0d30` | .1031 | .4543 | 0.99 | 19.17 | 38.40 | 5.81 | **+13.36** | 0.9662 | 31.74 | 66.67 |
| AGP05W-20261002 | `6abf3d186ee632ca3f97be1c` | .1084 | .4319 | 0.99 | 20.18 | 47.95 | 7.25 | **+12.93** | 1.0858 | 25.47 | 63.33 |

（SR/DD/月胜率为方向选中单因子多头诊断，非池级 C 指标；IC_p 均 0.0000。）

## 二、平台 s_i 对账（RankIC 序列口径，120 期）

| id | 平台 s_i | 本地 s_i（账本） | 本地×1.044 预测 | 偏差 vs 本地 |
|---|---:|---:|---:|---:|
| AGP05W | **.0479** | .0496 | .0518 | **−3.4%** |
| AGP01W | .0670 | .0736 | .0768 | −9.0% |
| AGP03W | .0461 | .0663 | .0692 | −30.5% |

- AGP05W 落在既有标定范围内（≥5 腿复合本地 s_i 略保守），平台复现最好。
- AGP01W 略低于预测；AGP03W 明显掉档，与 drift20 腿的字段替换（VWAP→CLOSE*VOLUME/AMOUNT）
  同源——**该腿平台/本地不可逐位对齐**，AGP03W 的平台结果按"替换后腿集"解读。

## 三、池级含义（平台标定；ΔA=18333×(s_i_plat−.025893)，ΔC 取本地账本）

加第 6 席（seed = swapf 5 席，第 45 条版本）：

| 候选 | ΔNC/月 | ΔC 分 | ΔA 分 | **ΔComb 分/月** |
|---|---:|---:|---:|---:|
| **AGP05W** | **+.0102** | +202 | +404 | **+606** |
| AGP01W | −.0166 | −329 | +754 | +424 |
| AGP03W | −.0100 | −198 | +370 | +173 |

换席形态（本地账本 × 平台 s_i，全部弱于加席）：

| 形态 | ΔNC/月 | ΔC 分 | ΔA 分 | ΔComb 分/月 |
|---|---:|---:|---:|---:|
| AGP01W 换 size_only | −.0276 | −547 | +754 | +206 |
| AGP01W 换 impact60 | −.0294 | −582 | +754 | +172 |
| AGP05W 换 size_only | −.0198 | −391 | +404 | +12 |
| AGP05W 换 impact60 | −.0215 | −426 | +404 | −23 |
| AGP03W 换 impact60 | −.0210 | −416 | +370 | −45 |
| AGP03W 换 size_only | −.0346 | −686 | +370 | −316 |

## 四、结论

1. 三条候选全部通过平台验证（单调性 .97~.99、单因子净额 +12.9%~+13.5%）。
2. **AGP05W 是唯一"加第 6 席"三口径一致为正的候选**：平台 s_i 复现最好（−3.4%）、
   ΔNC 唯一为正、平台标定 ΔComb ≈ +606 分/月；风险：与现役某席相关 .75、自身换手 48%/次。
3. 换席形态（size_only / impact60）平台标定下全部弱或为负，不如加席形态。
4. 待决策：10-01~03 低成交换/加席窗口内是否执行"加 AGP05W 为第 6 席"
   （影响 B 累积时点；执行需用户确认后另行提交池版本）。

## 五、产物

- `candidates.txt` / `candidates.txt.state.json` / `candidates.results/*.json`（raw payload）
- `candidates.report.md` / `candidates.report.csv` / `submit.log`

## 六、复现

```bash
python scripts/platform_precheck.py research_reports/platform_alignment/alphagen-pool-opt-20261002/platform/candidates.txt
D:\anaconda3\envs\easyrl4rec\python.exe scripts/_alphagen_formula_verify_20261002.py research_reports/platform_alignment/alphagen-pool-opt-20261002/platform/candidates.txt
# 提交（本机注意：不要预设 PYTHONIOENCODING）
python scripts/pandaai.py batch research_reports/platform_alignment/alphagen-pool-opt-20261002/platform/candidates.txt --start 20210907 --end 20260907 --cycle 10 --group-number 10 --round-trip 0.003
```
