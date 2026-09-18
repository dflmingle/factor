# AlphaPROBE Mainline Tushare Run

- method: `alphaprobe-mainline-tushare`
- alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
- universe: smoke subset of 沪深全A (300 instruments)
- generator: `ollama` / `goekdenizguelmez/JOSIEFIED-Qwen3:latest`
- semantic embedding: disabled because the local embedding model is unavailable
- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only

## Results

### `Rank($ratio_ep_ttm)`

topic: fundamental value; depth: 0

train: IC=0.0066, RankIC=0.0264, net=-0.0086
valid: IC=-0.0176, RankIC=0.0055, net=-0.1626
test: IC=0.0040, RankIC=0.0299, net=0.0174

### `Rank(Mul($ratio_ep_ttm,$book_to_market_ratio_lf))`

topic: fundamental value; depth: 1

train: IC=0.0060, RankIC=0.0307, net=-0.0311
valid: IC=-0.0170, RankIC=0.0065, net=-0.0888
test: IC=0.0019, RankIC=0.0289, net=0.0110

### `Rank($book_to_market_ratio_lf)`

topic: fundamental value; depth: 0

train: IC=0.0097, RankIC=0.0346, net=-0.0610
valid: IC=-0.0060, RankIC=0.0276, net=-0.0669
test: IC=-0.0039, RankIC=0.0291, net=-0.0264

### `TsRank($close,20)`

topic: interday price movements; depth: 0

train: IC=0.0150, RankIC=0.0353, net=-0.3662
valid: IC=0.0211, RankIC=0.0464, net=-0.2495
test: IC=0.0235, RankIC=0.0492, net=-0.2928

### `TsRank(Add($close,TsDelta($close,5)),20)`

topic: interday price movements; depth: 1

train: IC=0.0184, RankIC=0.0345, net=-0.4331
valid: IC=0.0165, RankIC=0.0392, net=-0.3456
test: IC=0.0181, RankIC=0.0415, net=-0.3086

### `TsRank(Mul($close,TsPctChange($close,10)),20)`

topic: interday price movements; depth: 1

train: IC=0.0112, RankIC=0.0199, net=-0.3534
valid: IC=0.0031, RankIC=0.0196, net=-0.3968
test: IC=0.0101, RankIC=0.0230, net=-0.3892
