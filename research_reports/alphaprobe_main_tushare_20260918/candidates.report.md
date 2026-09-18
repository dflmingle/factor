# AlphaPROBE Mainline Tushare Run

- method: `alphaprobe-mainline-tushare`
- alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
- universe: 沪深全A (.SH/.SZ) (5456 instruments)
- generator: `ollama` / `goekdenizguelmez/JOSIEFIED-Qwen3:latest`
- semantic embedding: disabled because the local embedding model is unavailable
- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only

## Results

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

### `TsPctChange($book_to_market_ratio_lf,20)`

topic: fundamental value; depth: 1

train: IC=0.0182, RankIC=0.0433, net=-0.1641
valid: IC=0.0274, RankIC=0.0749, net=-0.0882
test: IC=0.0190, RankIC=0.0414, net=-0.0840

### `TsRank($close,20)`

topic: interday price movements; depth: 0

train: IC=0.0223, RankIC=0.0377, net=-0.2708
valid: IC=0.0198, RankIC=0.0475, net=-0.2255
test: IC=0.0093, RankIC=0.0377, net=-0.1805

### `Div(TsMean($volume,20),Add($volume,1e-06))`

topic: volume movements; depth: 0

train: IC=0.0011, RankIC=-0.0018, net=-0.2506
valid: IC=0.0072, RankIC=0.0013, net=-0.2117
test: IC=0.0077, RankIC=0.0021, net=-0.2285

### `TsRank(Mul($close,$volume),20)`

topic: interday price movements; depth: 1

train: IC=0.0162, RankIC=0.0278, net=-0.2667
valid: IC=0.0254, RankIC=0.0456, net=-0.2136
test: IC=0.0122, RankIC=0.0301, net=-0.2297

