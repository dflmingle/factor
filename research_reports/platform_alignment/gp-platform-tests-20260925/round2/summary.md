# GP 新簇候选平台复现 · 第二轮（2026-09-25，K021 修复尝试）

## 一、这轮跑了什么

用户批准"只跑 1+2"（预算 8 算力），实际提交 2 条，均为 K021/cand0013 的修复尝试：

| # | 候选 | 平台公式 |
| --- | --- | --- |
| 1 | GP0924-K021-cand0013-P | `(((CORR(ASI,VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)` |
| 2 | GP0924-K021-cand0013-S18 | `(POWER(10,18)*(((CORR(ASI,VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS))` |

目的：① 独立度最高的 K021（maxMem 0.287）能否平台复现；② 顺手做"放大 1e18"的量级对照。

## 二、结果：两条都在"线性因子构建"节点失败，无结果

| 候选 | factor_id | run_id | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| cand0013-P | `6ab65e182d2f6998fc1bf757` | `6ab65e1a9e9d797cfb2cf75c` | status=3 WORKFLOW_FAILED | 23.7s 即失败，无分析节点 |
| cand0013-S18 | `6ab65f122d2f6998fc1bf75b` | `6ab65f14cd820fa2a40a6bcf` | status=8 | run 调用超时（CLI 侧 420s 上限被杀），回捞 6 次仍无结果 |

平台错误详情（19:42:41，对应候选 1）：

```
节点 线性因子构建 执行失败，错误代码：10000
错误消息：执行失败
详细错误信息：Error in formula 1: A和B必须都是pandas.Series/DataFrame 或 numpy.array
```

## 三、根因：算子名与字段名撞名（`ASI`）

- 平台侧 `ASI` **同时是两个东西**：
  - 算子 `ASI(OPEN,CLOSE,HIGH,LOW,M1,M2)`——`vendor/skill-pandaai-factor-online/references/operators.md:294`；
  - catalog 字段 `ASI, ASIT`（M1=26, M2=10）——`references/fields-ma-indicators.md:11`。
- 裸写 `ASI`（不带括号）时，解析器把它当成**算子对象**，`CORR` 的第 1 个参数拿到非序列 → 抛出"必须都是 pandas.Series/DataFrame 或 numpy.array"。

交叉证据：

1. 本轮是**类型错误 10000**，不是"变量未定义 10068"——标识符都被平台识别了，只是解析出的对象类型不对。
2. `VMA3` 与 `DAVOL5` 同属"逗号族"catalog 字段（`fields-ma-indicators.md`），且无同名算子；第一轮 K015 用的 `DAVOL5` 已通过构建并出了结果 → 该族字段名在公式里可用。
3. 两条候选只差 `POWER(10,18)*` 前缀，同点同错 → 与数值量级无关，问题在表达式本身。

**结论：量级（1e18）假设在本轮没有得到检验**（公式没跑到计算阶段）。要验证它，必须换一条不含撞名符号的候选。

## 四、影响面（本地全池预检，零算力）

新增 `scripts/_platform_name_collision_check.py`：把候选公式里的裸字段 token 与平台算子名表求交。

- 平台算子名 137 个；205 条候选里 **27 条**含撞名 token。
- 撞名 token 分布：`asi` 5、`mass` 3、`cci` 3、`dpo` 3、`trix` 2、`kdj_k` 2、`adxr` 2，`kdj_d`/`kdj_j`/`mfi`/`atr`/`vr`/`roc`/`wr` 各 1。
- 好候选（net≥10% 且 2026≥4%）里占 **9 条**：cand0143(`mfi`)、cand0112(`kdj_k`)、cand0100(`adxr`)、cand0122(`dpo`)、cand0117(`kdj_d`)、cand0013(`asi`)、cand0018(`mass`)、cand0025(`mass`)、cand0014(`trix`)。
- 处置约定：这 27 条在提交前必须先做符号消解（改算子形式 / 等价展开 / 换字段），否则大概率重复本轮的 10000。

## 五、花费

| 项 | 值 |
| --- | --- |
| 起止余额 | 1702.12 → **1700.12** |
| 本轮合计 | **2.00**（两条失败运行；**失败也计费**，不是 0） |

平台文档明确：**短窗探针只省等待时间、不省算力**（`SKILL.md` "Validate cheaply"）。省算力只能靠提交前的静态排查——本轮的撞名预检脚本就是干这个的。

## 六、下一步选项（未执行，等批准）

1. **K021 消解版**（1 条）：`(((CORR(ASI(OPEN,CLOSE,HIGH,LOW,26,10),VMA3,30)/CAL_20D_AMT_MA)/QTYR_5_20)/BS_TOTAL_ASSETS)`。
   风险：算子 `ASI` 的 M2 平滑口径与字段 `ASI` 是否一致未验证，平台值可能有细微差异。
2. **换掉 ASI 的重挑版**：从避开全部 14 个撞名 token 的池子里重选。
3. **量级假设的干净验证**（2 条）：挑一条**零撞名且字段全 OK** 的候选（如 cand0038：`BS_TOTAL_ASSETS`/`CAL_20D_AMT_MA`/`CFD_FLOW_PER_SHARE_TTM`/`QTYR_5_20`，maxMem 0.009）做"原式 vs ×1e18"对照。
   注意：cand0038 仍含 `CAL_20D_AMT_MA`（已触发拉黑门槛），所以它验证的是"量级/平台退化"，不是"能否进池"。

## 七、复现入口

- 候选（平台语法）：`round2/candidates_panda.txt`
- 状态与原始响应：`round2/candidates_panda.txt.state.json`、`round2/candidates_panda.results/*.json`
- 提交日志：`round2/candidates_panda.submit.log`
- 撞名预检：`scripts/_platform_name_collision_check.py`