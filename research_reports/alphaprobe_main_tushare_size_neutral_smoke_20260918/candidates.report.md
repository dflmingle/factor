# AlphaPROBE Mainline Tushare Run

- method: `alphaprobe-mainline-tushare`
- alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
- universe: smoke subset of 沪深全A (100 instruments)
- generator: `ollama` / `goekdenizguelmez/JOSIEFIED-Qwen3:latest`
- semantic embedding: disabled because the local embedding model is unavailable
- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only

## Results

### `TsRank($close,20)`

topic: interday price movements; depth: 0

train: IC=0.0027, RankIC=0.0185, net=n/a
valid: IC=0.0249, RankIC=0.0435, net=n/a
test: IC=0.0322, RankIC=0.0484, net=n/a

### `TsRank(Mul($close,TsPctChange($close,20)),20)`

topic: interday price movements; depth: 1

train: IC=0.0034, RankIC=0.0022, net=n/a
valid: IC=0.0349, RankIC=0.0410, net=n/a
test: IC=0.0216, RankIC=0.0291, net=n/a
