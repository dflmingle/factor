# 疯猫公开RankIC目标：数值拟合结果

目标 xplr-d3c-r6-grpvol：RankIC .1722791715386185、RankIC IR 1.6613206049954048、胜率111/119=.9327731092436975、S_i .2669698660608367。此前将其解释为Pearson IC的比较无效；本轮按项目已验证的竞技场RankIC规则更正。

本轮两seed遗传树搜索记录 1633 个唯一表达式（602 有效），另384次稀疏混合CEM。平台算力0。搜索/评估 27.1 分钟，独立核验 1.2 分钟。

三个冻结候选：**六位小数一致 0/3，预声明近似门槛通过 0/3**。只有数字全部达到标准才称近似匹配；不能用训练收益替代目标。

| 模型 | RankIC | IR(RankIC) | 胜率 | S_i | RankIC差 | IR差 | 胜率差 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FM_TARGET_01 | 0.103731 | 0.833789 | 95/119 (79.8319%) | 0.069046 | -0.068548 | -0.827532 | -13.4454% |
| FM_TARGET_02 | 0.102014 | 0.829319 | 97/119 (81.5126%) | 0.068961 | -0.070265 | -0.832002 | -11.7647% |
| FM_TARGET_03 | 0.108192 | 0.811999 | 97/119 (81.5126%) | 0.071611 | -0.064087 | -0.849322 | -11.7647% |

全部119期参与了目标拟合，所以前80/后39期和分年表是拟合内诊断，不是独立样本外。仅汇总值不足以恢复原公式/逐股票信号；即便匹配，也只能说数字匹配。胜率不能靠改变阈值、丢掉亏损期或缩窄股票池制造。

日期为2021-09-17起每10本地交易日，最后2026-08-06、退出2026-08-21，恰119期。中间日期是推定，不是对手已保存逐期日期。标签与行情口径固定，正式近五年20210907..20260907的120期H03模板结果独立保存，近期2026单独保存；未混排。

| 模型 | 目标119期净超额 | 正式五年净超额 | 2026近期净超额 | 目标绝对size相关 |
|---|---:|---:|---:|---:|
| FM_TARGET_01 | 8.40% | 7.33% | 2.32% | 0.479 |
| FM_TARGET_02 | 7.87% | 6.88% | -0.95% | 0.488 |
| FM_TARGET_03 | 9.27% | 7.81% | -1.39% | 0.534 |

冻结公式/组合：

FM_TARGET_01，elite genetic tree mutation and crossover：

`Add(Add(Add(vstab20,Add(size,Neg(vol6))),lowvolume3),Add(vstab20,Add(Neg(Resid5(vstab20,asym60)),Neg(rvcor20))))`

FM_TARGET_02，elite genetic tree mutation and crossover：

`Add(Add(Add(gapcor20,Add(size,Neg(vol6))),lowvolume1),Add(vstab20,Add(Neg(Rank(Grp5(gapcor20,asym20))),Neg(rvcor20))))`

FM_TARGET_03，sparse_rank_mixture_CEM：

- +0.55163860 × RANK(`Add(Add(Add(gapcor20,Add(size,Neg(vol6))),lowvolume1),Add(vstab20,Add(Neg(Rank(Grp5(gapcor20,asym20))),Neg(rvcor20))))`)
- +0.30249059 × RANK(`Add(Add(Add(vstab20,Add(size,Neg(vol6))),lowvolume3),Blend5(Neg(vstab20),Mul(rev10,idvol20)))`)
- +0.14587081 × RANK(`Add(Add(Grp5(Add(lowturn,idvol20),Neg(smoothvol20)),Blend3(signedflow20,vol20)),Add(Add(Add(vstab20,Add(size,Neg(vol6))),lowvolume3),Add(Grp3(tug20,Neg(macdslowhist)),Add(asym20,Neg(vol6)))))`)

独立pandas核验 1119 条逐期/15行汇总、十组成员/换手/成本与Top20。RankIC目标指标使用总体std（ddof=0），Pearson IC列仅诊断。真实日度输入在100只固定股票、两个截断点重算全部60原子及冻结模型，历史掩码和值差异0。该检查不证明全样本拟合参数在过去可知；候选筛选本身使用了全窗口标签，仍有过拟合。

峰值RSS 0.789 GiB，私有内存 0.779 GiB，最低可用 2.534 GiB；2.25GiB/1.25GiB watchdog未触发。全A、qfq、total_mv、20180101暖机、label-1、10组、factor_valid、算术年化、0.30%单边；代理规则未改。

本轮仍未复现同样数值。记录最接近结果和逐项差距，不声称成功，不提交平台或改池。
