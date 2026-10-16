# 复刻改善自动归档

每5分钟检查；只归档与当前候选一致的验证结果。首次归档是基线，不是新增突破。

改进门槛：同源码和证据版本下，损失较上次归档下降至少1%，全持仓重合率下降不超过0.5个百分点，IC和RankIC MAE分别恶化不超过2%；或由未通过变为通过既定参照验收。

每个快照保留公式/AST、独立A与各榜验证、逐期指标、未通过项、源证据、评估源码及SHA256。这些仍是全部公开日期参与的回顾性拟合代理，没有严格样本外验证。

下表为本批归档。完整各路线基线见manifest.json，历史改进见snapshots/*/change.json。

|对手|类型|损失|平均持仓重合|参照验收|
|---|---|---:|---:|---|
|霖笙|initial_verified_baseline|231.582924|67.37%|False|
|云淡风轻|initial_verified_baseline|491.319626|75.04%|False|
|Alpha|initial_verified_baseline|27.724168|88.07%|False|
|gjh|initial_verified_baseline|207.652040|41.40%|False|
|c avant|initial_verified_baseline|181.513702|66.66%|False|
|不抵灼灼目光|initial_verified_baseline|289.836092|62.41%|False|
|GuoXIze|initial_verified_baseline|565.464840|57.89%|False|
|金豚|initial_verified_baseline|67.748168|77.29%|False|
|Sunny Yu|initial_verified_baseline|165.642558|45.61%|False|
|筱幽梦|initial_verified_baseline|394.167393|66.19%|False|
|Siuuuuuuuu|initial_verified_baseline|554.420734|27.63%|False|
|陈博杨|initial_verified_baseline|484.724116|40.34%|False|
|ljyinvader|initial_verified_baseline|240.395757|63.80%|False|
|QMuant|initial_verified_baseline|538.768611|74.01%|False|
|超骁|initial_verified_baseline|109.573478|79.07%|False|
|MINGJIE|initial_verified_baseline|188.717514|46.10%|False|
|衍神|initial_verified_baseline|256.706622|50.36%|False|
|sakuraly|initial_verified_baseline|428.347149|28.68%|False|
|何子兮|initial_verified_baseline|760.946005|68.96%|False|
|弈星|initial_verified_baseline|3133.557727|16.08%|False|
|西亚斯小牛|initial_verified_baseline|326.673543|45.55%|False|
|灵小犀|initial_verified_baseline|141.661886|63.02%|False|
|空白|initial_verified_baseline|476.270898|48.73%|False|
|神圣量化帝国|initial_verified_baseline|180.604078|60.48%|False|
|123321|initial_verified_baseline|128.377171|65.07%|False|
|我要得第一|initial_verified_baseline|103.801247|70.10%|False|
|FrankFang|initial_verified_baseline|198.618817|61.33%|False|
|Jimmy|initial_verified_baseline|248.619590|46.11%|False|
|hulai|initial_verified_baseline|140.423024|63.29%|False|
|cc|initial_verified_baseline|185.001286|57.34%|False|
|Alpha猎手|initial_verified_baseline|335.701321|59.25%|False|
|瑞瑞|initial_verified_baseline|96.537276|75.08%|False|
|小马珍珠|initial_verified_baseline|114.273835|68.91%|False|
|嚯哈哈也有春天|initial_verified_baseline|38.387164|79.71%|False|
|SphericalChicken|initial_verified_baseline|201.907083|51.70%|False|
|qingchen|initial_verified_baseline|154.531841|64.87%|False|
|了不起de阿斗|initial_verified_baseline|268.262723|44.82%|False|
|大福|initial_verified_baseline|386.092071|26.72%|False|
|进化论|initial_verified_baseline|103.376544|55.25%|False|
|ChenQiLong|initial_verified_baseline|2321.124115|30.72%|False|
|The Alpha (SCAU)|initial_verified_baseline|107.062862|71.31%|False|
|QuantLink|initial_verified_baseline|287.200739|46.81%|False|
|Alpha|initial_verified_baseline|24.351157|87.07%|False|
|金豚|initial_verified_baseline|56.855122|77.29%|False|
|Sunny Yu|initial_verified_baseline|107.822397|52.69%|False|
|嚯哈哈也有春天|initial_verified_baseline|22.492576|81.56%|False|
