# 读论文：Anomalies in the China A-share market

**Jansen, Swinkels & Zhou (2021)**, *Pacific-Basin Finance Journal* 68, 101607；DOI `10.1016/j.pacfin.2021.101607`；CC BY。
Robeco + Erasmus University Rotterdam。样本 2000–2019，CSMAR 数据（CF MOM 用 IBES），32 个异象、月度调仓、decile 多空。

## 0. 来源与获取

- 用户给的 ScienceDirect 预签名链接 5 分钟过期后 403；落库版取自 **EUR Research Repository** 的出版者 PDF
  （`pure.eur.nl/ws/portalfiles/portal/58642799/Anomalies_in_the_China_A_share_market.pdf`，CC BY）。
- 本目录：`jansen-swinkels-zhou-2021-anomalies-china-a-share.pdf`（原文 1.7MB）、
  `jansen-swinkels-zhou-2021-extracted.txt`（pypdf 抽文 146KB，供 grep）、
  `anomaly_returns_turnover.csv`（表 4+表 5 转录：32 异象 × 收益/t/换手/盈亏平衡成本）。

## 1. 一句话结论

A 股 **价值、低风险、交易（换手/流动性）三类异象成立；规模、质量、动量三类整体弱**——例外是 **残差动量（RES MOM）
与残差反转（RES REV）**；首次检验的 **季节性（同月/异月）** 有稳健样本外证据，**关联公司动量（CF MOM）不成立**。

## 2. 六类证据（表 4 摘要，EW，1 个月持有）

| 类别 | 结论 | 最强项（月均超额 / t） |
| --- | --- | --- |
| Size | 剔除最小 30% 后不显著 0.59/1.36（不剔除 1.56/2.67 ⇒ 微盘壳价值） | — |
| Value | 全部成立 | BM 1.12/3.02、EP 1.10/3.41、SP 0.93/3.34、OCP 0.78/2.78 |
| Quality | 盈利类弱正；**投资类符号相反**；应计类弱 | ROE 0.54/1.82、GP 0.63/2.18；**INV ASSET −0.55/−2.61**（资产扩张→高收益，与美股相反） |
| Risk | 全部成立（BETA 除外） | MAX 1.20/5.20、IVOL 1.19/3.93、VOL 1M 1.08/3.77、VOL 3Y 0.90/2.99 |
| Past returns | 动量不成立；残差动量/反转、长反转、季节性成立 | REV 1M 1.42/4.35、RES REV 1.18/4.72、SEAS DIFF 0.89/4.16、RES MOM 0.66/3.36；MOM 0.33/0.92、CF MOM 0.46/1.54 |
| Trading | 全部成立（VW 只剩 ABN TURN 显著） | **ABN TURN 1.72/5.50**、ILLIQ 1.24/3.35、TURN 0.88/3.26 |

价值类需注意：BM/EP/CP/OCP 剔除负值后更强（负值公司反而更受乐观对待）；GP/OP 用 TTM + 季度更新才有 0.5~0.6%/月。

## 3. 换手与盈亏平衡成本（表 5）——对我们最有用的一张表

口径：**两腿、双向、月度换手**（满仓换手上限 400%）；盈亏平衡成本 B-E = 月收益 ÷ 月换手。

- **慢信号（换手低 ⇒ 我们能承受）**：TURN 61%/月、SP 66、VOL 3Y 67、BM 77、DP 75、IVOL 82、EP 85、OCP 91、REV LT 97、ILLIQ 149。
  其中 BM/SP/VOL 3Y/IVOL/TURN 在 6/12 个月持有期收益几乎不衰减（B-E 升到 2~6%）。
- **快信号（换手高 ⇒ 我们的 C 段多半吃不下）**：MOM 149、RES MOM 180、CF MOM 300、ABN TURN 254、VOL 1M 265、MAX 323、REV 1M 355、RES REV 362、SEAS 367。
  长持有期收益衰减或翻负（SEAS、REV 1M 在 12 个月口径变负）。
- **换算到我们的口径**：我们的单腿单次换手 ≈ 论文月双向换手 ÷ 9.6（2 腿 × 2 向 × ≈2.4 次/月）。
  CSV 末列已算好：TURN 6.4%/次、VOL 3Y 6.9、SP 6.8、BM 8.0、IVOL 8.6、EP 8.9、INV ASSET 8.9、ILLIQ 15.5、RES MOM 18.8、ABN TURN 26.5、MAX 33.7、REV 1M 37.0、SEAS 38.2。
  我们池子现状参照：现役 5 席 14.2%/次、L6 34.4%/次、L1（K10 单换）22.1%/次。

## 4. 方法学细节（复现要点）

- Decile 多空，long 取预期高收益端；EW 与 VW 并列报告；Newey-West t；1/6/12 月重叠持有组合。
- 剔除最小 30% 以避开壳价值；市值用 A 股股本（不是总股本）。
- **涨跌停修正**：MAX 把触及涨停后连续收益累加；**停牌日收益置 −99**（否则停牌 0 收益会变成"月内最高收益"）。
- 财务用 TTM、季度更新（与我们 PIT/TTM 规则一致）；估值比率月度更新。
- Size-neutral / industry-neutral（CSRC 行业）后结论基本不变，小盘更强。
- 卖空受限检验：多空两腿收益量级相当；国企/非国企差异小；股改前后都成立。

## 5. 对上我们池子的映射（灵感清单）

我们已有：value（`bm_minus` / `bm_plus`）、size（`size_only`）、冲击/流动性（`impact60`）、加法类（`t10`）、
AlphaGen（`K10/K20`）、CAL 技术族（`TOPMIX/STD20/AMTDISP`）、行为族（`bhv3`）。
论文"慢而强"清单里我们**还没做**的：

| 优先级 | 候选 | 论文证据 | 折算换手/次 | 备注 |
| --- | --- | --- | ---: | --- |
| P1 | **EP**（TTM 净利/总市值） | 1.10/3.41（VW 2.53） | 8.9% | 与两张 BM 席同族，先查相关 |
| P1 | **SP**（TTM 营收/总市值） | 0.93/3.34，最便宜 | 6.8% | 同上；12 月持有 B-E 5.61 全场最高 |
| P1 | **RETVOL36**（36 月月收益波动，取负） | 0.90/2.99，12 月口径 0.85/2.87 不衰减 | 6.9% | 我们测过的 `fam_vol` 是成交量波动（vs250/500/756），**不是**收益波动 |
| P1 | **IVOL250**（250 日市场模型残差波动，取负） | 1.19/3.93 | 8.6% | 需回归，python 模式可做（注意 repaint） |
| P2 | **TURN250**（250 日平均换手，取负） | 0.88/3.26，最便宜 | 6.4% | 可能与 `size_only`/`impact60` 重叠 |
| P2 | **INV ASSET**（总资产环比增速，**中国取正号**） | −0.55/−2.61；size-neutral −0.70/−3.66 | 8.9% | 季度更新、慢；先查与我们 `t10` 是否同源 |
| P3 | **MAX20**（20 日最大日收益，取负，含涨跌停/停牌修正） | 1.20/5.20（全表最强 EW） | 33.7% | 换手高，只宜做复合腿/查理后定 |
| P3 | **RES MOM**（36 月 FF3 残差动量） | 0.66/3.36（VW 2.11） | 18.8% | 需 FF3 回归；对冲市场/规模/价值，分散性好 |

**不建议方向**：SEAS / SEAS REV / SEAS DIFF、REV 1M / RES REV（太"快"，折算 37~38%/次，会被 C 段吃掉）；
CF MOM（需 IBES 分析师覆盖，且不显著）；质量类 ACC / TOTAL ACC / NOA（弱）；MOM（中国无动量）；BETA（弱）。

## 6. 与既有结论的互证

- 我们 `size_only` 的 s_i 仅 .0091 → 与论文"剔除微盘后 size 不显著、不剔除才 1.56%"一致。
- 我们 `AMTDISP`（amount std / amount MA）≈ 论文 **ABN TURN 的金额版**：论文 s 强（EW t=5.50）但换手 254%/月 ≈ 26%/次；
  我们平台实测 s_i .0505、换手 27.4%/次 —— 两条独立证据都指向"**这类信号真强，但换手是主要约束**"。
- 论文"长持有期不衰减"清单（BM / SP / VOL 3Y / IVOL / TURN / ILLIQ / GP）几乎就是**C 段友好信号集**，
  下次挑候选先从这一列里选。

## 7. 复现（本目录产物）

- `anomaly_returns_turnover.csv`：32 行 × 23 列（类别、预期符号、EW/VW 的 1/6/12 月收益与 t、换手、B-E、折算换手/次）。
- `jansen-swinkels-zhou-2021-extracted.txt`：全文抽文，可用 `rg` 检索（如 `rg -n "break-even" ...`）。
- 原论文复现数据：Dataverse NL `doi:10.34894/ONJQ70`（未下载）。