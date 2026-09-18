# AlphaPROBE Mainline Tushare Run

- method: `alphaprobe-mainline-tushare`
- alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
- universe: 沪深全A (.SH/.SZ) (5456 instruments)
- generator: `ollama` / `goekdenizguelmez/JOSIEFIED-Qwen3:latest`
- semantic embedding: disabled because the local embedding model is unavailable
- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only

## Results

### `Rank(Div($book_to_market_ratio_lf,$market_cap))`

topic: fundamental value; depth: 1

train: IC=0.0444, RankIC=0.0621, net=0.1808
valid: IC=0.0366, RankIC=0.0661, net=0.1820
test: IC=0.0112, RankIC=0.0403, net=0.0307

### `Rank($ratio_ep_ttm)`

topic: fundamental value; depth: 0

train: IC=0.0057, RankIC=0.0246, net=0.0313
valid: IC=-0.0195, RankIC=0.0034, net=-0.2433
test: IC=-0.0037, RankIC=0.0182, net=-0.0497

### `Rank($book_to_market_ratio_lf)`

topic: fundamental value; depth: 0

train: IC=0.0310, RankIC=0.0612, net=0.0604
valid: IC=0.0006, RankIC=0.0356, net=-0.1099
test: IC=0.0004, RankIC=0.0321, net=-0.0637

### `TsRank($close,20)`

topic: interday price movements; depth: 0

train: IC=0.0223, RankIC=0.0377, net=-0.2708
valid: IC=0.0198, RankIC=0.0475, net=-0.2255
test: IC=0.0093, RankIC=0.0377, net=-0.1805

### `TsRank(Add($close,TsMean($close,20)),20)`

topic: interday price movements; depth: 1

train: IC=0.0246, RankIC=0.0443, net=-0.2244
valid: IC=0.0173, RankIC=0.0508, net=-0.1899
test: IC=0.0074, RankIC=0.0420, net=-0.2126

### `TsRank($volume,20)`

topic: interday price movements; depth: 1

train: IC=0.0133, RankIC=0.0239, net=-0.2756
valid: IC=0.0226, RankIC=0.0403, net=-0.2182
test: IC=0.0108, RankIC=0.0265, net=-0.2226

### `TsRank(Sub($turnover,TsMean($turnover,20)),20)`

topic: interday price movements; depth: 2

train: IC=0.0073, RankIC=0.0072, net=-0.2503
valid: IC=0.0106, RankIC=0.0208, net=-0.2472
test: IC=0.0077, RankIC=0.0091, net=-0.2227

### `TsRank($turnover,20)`

topic: interday price movements; depth: 1

train: IC=0.0132, RankIC=0.0196, net=-0.2762
valid: IC=0.0260, RankIC=0.0443, net=-0.2135
test: IC=0.0104, RankIC=0.0243, net=-0.2269

### `TsRank(Add($close,TsCov($close,$volume,20)),20)`

topic: interday price movements; depth: 2

train: IC=0.0153, RankIC=0.0256, net=-0.1708
valid: IC=0.0329, RankIC=0.0487, net=-0.0579
test: IC=0.0079, RankIC=0.0158, net=-0.2628

### `TsDelta(Rank($ratio_ep_ttm),2)`

topic: fundamental value; depth: 1

train: IC=0.0131, RankIC=0.0111, net=-0.2863
valid: IC=0.0176, RankIC=0.0261, net=-0.2766
test: IC=0.0029, RankIC=0.0054, net=-0.2855

### `TsDelta($book_to_market_ratio_lf,2)`

topic: fundamental value; depth: 1

train: IC=0.0104, RankIC=0.0153, net=-0.3065
valid: IC=0.0154, RankIC=0.0297, net=-0.2977
test: IC=0.0055, RankIC=0.0144, net=-0.3060

### `TsDelta(Rank($ratio_sp_ttm),2)`

topic: fundamental value; depth: 3

train: IC=0.0170, RankIC=0.0149, net=-0.3319
valid: IC=0.0254, RankIC=0.0411, net=-0.2430
test: IC=0.0022, RankIC=0.0075, net=-0.3283

### `TsDelta(Rank($book_to_market_ratio_lf),2)`

topic: fundamental value; depth: 2

train: IC=0.0180, RankIC=0.0159, net=-0.2970
valid: IC=0.0252, RankIC=0.0401, net=-0.2685
test: IC=0.0037, RankIC=0.0084, net=-0.3288

### `TsRank(Div($close,$open),20)`

topic: interday price movements; depth: 1

train: IC=0.0112, RankIC=0.0103, net=-0.3231
valid: IC=0.0139, RankIC=0.0201, net=-0.3541
test: IC=0.0049, RankIC=0.0049, net=-0.4704

### `TsPctChange(Rank($book_to_market_ratio_lf),2)`

topic: fundamental value; depth: 2

train: IC=0.0101, RankIC=0.0071, net=-0.3897
valid: IC=0.0154, RankIC=0.0226, net=-0.2937
test: IC=0.0022, RankIC=0.0017, net=-0.4949

### `TsPctChange($book_to_market_ratio_lf,2)`

topic: fundamental value; depth: 1

train: IC=0.0090, RankIC=0.0058, net=-0.4270
valid: IC=0.0175, RankIC=0.0285, net=-0.3349
test: IC=0.0021, RankIC=0.0027, net=-0.6299
