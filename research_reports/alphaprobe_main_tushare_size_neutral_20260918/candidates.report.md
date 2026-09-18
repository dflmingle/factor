# AlphaPROBE Mainline Tushare Run

- method: `alphaprobe-mainline-tushare`
- alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
- universe: 沪深全A (.SH/.SZ) (5456 instruments)
- generator: `ollama` / `goekdenizguelmez/JOSIEFIED-Qwen3:latest`
- semantic embedding: disabled because the local embedding model is unavailable
- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only

## Results

### `TsRank($open,20)`

topic: interday price movements; depth: 1

train: IC=0.0192, RankIC=0.0338, net=-0.2355
valid: IC=0.0172, RankIC=0.0408, net=-0.2325
test: IC=0.0105, RankIC=0.0383, net=-0.1231

### `TsRank($close,20)`

topic: interday price movements; depth: 0

train: IC=0.0223, RankIC=0.0377, net=-0.2708
valid: IC=0.0198, RankIC=0.0475, net=-0.2255
test: IC=0.0093, RankIC=0.0377, net=-0.1805

### `TsRank($volume,20)`

topic: interday price movements; depth: 1

train: IC=0.0133, RankIC=0.0239, net=-0.2756
valid: IC=0.0226, RankIC=0.0403, net=-0.2182
test: IC=0.0108, RankIC=0.0265, net=-0.2226

### `TsRank($turnover,20)`

topic: interday price movements; depth: 1

train: IC=0.0132, RankIC=0.0196, net=-0.2762
valid: IC=0.0260, RankIC=0.0443, net=-0.2135
test: IC=0.0104, RankIC=0.0243, net=-0.2269

### `Div(TsMean($volume,20),Add($volume,1e-06))`

topic: volume movements; depth: 0

train: IC=0.0011, RankIC=-0.0018, net=-0.2506
valid: IC=0.0072, RankIC=0.0013, net=-0.2117
test: IC=0.0077, RankIC=0.0021, net=-0.2285

### `TsRank(Sub($turnover,$close),20)`

topic: interday price movements; depth: 2

train: IC=0.0038, RankIC=0.0025, net=-0.2875
valid: IC=0.0173, RankIC=0.0274, net=-0.3389
test: IC=0.0062, RankIC=-0.0027, net=-0.2533

### `TsRank(TsPctChange($volume,20),20)`

topic: interday price movements; depth: 2

train: IC=0.0055, RankIC=0.0062, net=-0.2469
valid: IC=0.0265, RankIC=0.0337, net=-0.1100
test: IC=0.0126, RankIC=0.0156, net=-0.2668

### `TsRank(TsPctChange($close,20),20)`

topic: interday price movements; depth: 3

train: IC=0.0088, RankIC=0.0146, net=-0.2574
valid: IC=0.0273, RankIC=0.0436, net=-0.1251
test: IC=0.0026, RankIC=0.0111, net=-0.3542

### `TsRank(TsPctChange($open,20),20)`

topic: interday price movements; depth: 3

train: IC=0.0073, RankIC=0.0131, net=-0.2553
valid: IC=0.0246, RankIC=0.0366, net=-0.1680
test: IC=0.0043, RankIC=0.0135, net=-0.3751
