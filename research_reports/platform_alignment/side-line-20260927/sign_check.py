import os, sys, io, json
from pathlib import Path
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; T = wide["turnover"]
del wide
cal = C.index; pos = {d: i for i, d in enumerate(cal)}
rj = json.loads((Path(r"D:\factor") / "t10-additions-20260911-candidates.results" / "6aa3c6d25d52c44d2f55c45b.json").read_text(encoding="utf-8-sig"))
ch = rj["results"]["factor_analysis"]["query_rank_ic_sequence_chart"]
sched = None
for e in ch["x"]:
    if str(e["name"]).lower() == "date": sched = [pd.Timestamp(v) for v in e["data"]]
FUT = {}
for d in sched:
    i = pos.get(d)
    if i is not None and i + 11 < len(cal):
        FUT[d] = C.iloc[i+11].to_numpy(dtype="float64") / C.iloc[i+1].to_numpy(dtype="float64") - 1.0
cands = {}
cands["nb60_x_T5"] = ((1.0 - C/C.rolling(60, min_periods=30).mean()).rank(axis=1, pct=True) * (1.0 - T.rolling(5).mean().rank(axis=1, pct=True))).astype("float32")
cands["im40_raw"] = ((C-O)/O).rolling(40).mean().astype("float32")
cands["im40_neg"] = (-((C-O)/O).rolling(40).mean()).astype("float32")
for nm, v in cands.items():
    ics = []
    for d in sched:
        i = pos.get(d)
        if i is None or d not in FUT: continue
        x = v.iloc[i].to_numpy(dtype="float64"); y = FUT[d]
        m = np.isfinite(x) & np.isfinite(y)
        if m.sum() < 100: continue
        xr = pd.Series(x[m]).rank().to_numpy(); yr = pd.Series(y[m]).rank().to_numpy()
        ics.append(float(np.corrcoef(xr, yr)[0,1]))
    a = np.array(ics)
    print("%-12s signed mean RankIC 5y = %+.4f  (n=%d, sign=%s)" % (nm, a.mean(), a.size, "+" if a.mean() >= 0 else "-"))
