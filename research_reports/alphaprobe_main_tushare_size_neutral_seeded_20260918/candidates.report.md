# AlphaPROBE Mainline Tushare Run

- method: `alphaprobe-mainline-tushare`
- alignment rule: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`
- universe: 沪深全A (.SH/.SZ) (5456 instruments)
- generator: `ollama` / `goekdenizguelmez/JOSIEFIED-Qwen3:latest`
- semantic embedding: disabled because the local embedding model is unavailable
- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only

## Results

### `Div(Div($amount,$volume),$high)`

topic: intraday price-volume; depth: 0

train: IC=0.0099, RankIC=0.0345, net=0.0586
valid: IC=0.0169, RankIC=0.0283, net=0.1540
test: IC=0.0263, RankIC=0.0501, net=0.1450

### `Div(Rank(Div($amount,$volume)),Rank($high))`

topic: intraday price-volume; depth: 1

train: IC=0.0108, RankIC=-0.0008, net=0.1364
valid: IC=0.0036, RankIC=0.0014, net=0.1354
test: IC=0.0075, RankIC=0.0040, net=0.0533

### `Sub(Div(Div($amount,$volume),$high),TsMean($high,2))`

topic: intraday price-volume; depth: 1

train: IC=0.0243, RankIC=0.0537, net=0.0338
valid: IC=0.0063, RankIC=0.0261, net=0.0646
test: IC=-0.0095, RankIC=0.0145, net=-0.0238

### `Sub(Div(Div($amount,$volume),$high),TsPctChange(TsMean($high,2),2))`

topic: intraday price-volume; depth: 3

train: IC=0.0200, RankIC=0.0216, net=-0.0801
valid: IC=0.0324, RankIC=0.0418, net=-0.0469
test: IC=0.0093, RankIC=0.0142, net=-0.0889

### `TsRank($open,20)`

topic: interday price movements; depth: 1

train: IC=0.0192, RankIC=0.0338, net=-0.2355
valid: IC=0.0172, RankIC=0.0408, net=-0.2325
test: IC=0.0105, RankIC=0.0383, net=-0.1231

### `TsRank(SLog1p(TsSum($amount,15)),20)`

topic: interday price movements; depth: 3

train: IC=0.0188, RankIC=0.0310, net=-0.1328
valid: IC=0.0296, RankIC=0.0571, net=-0.0810
test: IC=0.0135, RankIC=0.0379, net=-0.1292

### `Div(Div($amount,TsSum($volume,2)),$high)`

topic: intraday price-volume; depth: 1

train: IC=0.0034, RankIC=0.0032, net=-0.0860
valid: IC=0.0023, RankIC=-0.0028, net=-0.0826
test: IC=0.0032, RankIC=0.0063, net=-0.1567

### `TsRank($close,20)`

topic: interday price movements; depth: 0

train: IC=0.0223, RankIC=0.0377, net=-0.2708
valid: IC=0.0198, RankIC=0.0475, net=-0.2255
test: IC=0.0093, RankIC=0.0377, net=-0.1805

### `TsRank(Mul($amount,TsPctChange($close,5)),20)`

topic: interday price movements; depth: 3

train: IC=0.0158, RankIC=0.0111, net=-0.3229
valid: IC=0.0273, RankIC=0.0396, net=-0.2880
test: IC=0.0039, RankIC=0.0042, net=-0.2204

### `TsRank($volume,20)`

topic: interday price movements; depth: 1

train: IC=0.0133, RankIC=0.0239, net=-0.2756
valid: IC=0.0226, RankIC=0.0403, net=-0.2182
test: IC=0.0108, RankIC=0.0265, net=-0.2226

### `TsRank($amount,20)`

topic: interday price movements; depth: 2

train: IC=0.0156, RankIC=0.0233, net=-0.2656
valid: IC=0.0278, RankIC=0.0487, net=-0.2222
test: IC=0.0112, RankIC=0.0277, net=-0.2229

### `Div(TsMean($volume,20),Add(Add($volume,1e-06),TsMean($volume,20)))`

topic: volume movements; depth: 1

train: IC=0.0143, RankIC=0.0210, net=-0.2506
valid: IC=0.0436, RankIC=0.0453, net=-0.2117
test: IC=0.0185, RankIC=0.0241, net=-0.2285

### `Div(TsMean($volume,20),Add($volume,1e-06))`

topic: volume movements; depth: 0

train: IC=0.0011, RankIC=-0.0018, net=-0.2506
valid: IC=0.0072, RankIC=0.0013, net=-0.2117
test: IC=0.0077, RankIC=0.0021, net=-0.2285

### `Div(TsMean($volume,20),Add(Add(Add($volume,1e-06),TsPctChange($volume,20)),TsMean($volume,20)))`

topic: volume movements; depth: 2

train: IC=0.0186, RankIC=0.0265, net=-0.2493
valid: IC=0.0321, RankIC=0.0415, net=-0.2106
test: IC=0.0173, RankIC=0.0264, net=-0.2297

### `Sub(Div(Div($amount,$volume),$high),TsPctChange($high,2))`

topic: intraday price-volume; depth: 2

train: IC=0.0182, RankIC=0.0152, net=-0.1376
valid: IC=0.0279, RankIC=0.0333, net=-0.1151
test: IC=0.0080, RankIC=0.0101, net=-0.2301

### `Sub(Div(Div($amount,$volume),$high),TsPctChange($open,2))`

topic: intraday price-volume; depth: 4

train: IC=0.0149, RankIC=0.0124, net=-0.1276
valid: IC=0.0249, RankIC=0.0312, net=-0.0629
test: IC=0.0035, RankIC=0.0070, net=-0.2320

### `TsRank(Greater($amount,TsMean($volume,10)),20)`

topic: interday price movements; depth: 3

train: IC=0.0166, RankIC=0.0256, net=-0.1733
valid: IC=0.0266, RankIC=0.0495, net=-0.1896
test: IC=0.0087, RankIC=0.0273, net=-0.2369

### `TsRank(Add($amount,TsDelta($volume,10)),20)`

topic: interday price movements; depth: 3

train: IC=0.0109, RankIC=0.0142, net=-0.2818
valid: IC=0.0217, RankIC=0.0371, net=-0.2592
test: IC=0.0091, RankIC=0.0181, net=-0.2488

### `Sub(Div(Div($amount,$volume),$high),TsPctChange($low,2))`

topic: intraday price-volume; depth: 3

train: IC=0.0158, RankIC=0.0171, net=-0.0839
valid: IC=0.0261, RankIC=0.0372, net=-0.0546
test: IC=0.0027, RankIC=0.0076, net=-0.3178

### `Sub(Div(Div($amount,$volume),$high),TsPctChange($close,2))`

topic: intraday price-volume; depth: 3

train: IC=0.0166, RankIC=0.0135, net=-0.1149
valid: IC=0.0253, RankIC=0.0330, net=-0.1329
test: IC=0.0084, RankIC=0.0099, net=-0.5142
