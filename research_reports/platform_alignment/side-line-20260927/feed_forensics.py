import os, sys, io
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv"
tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]; T = wide["turnover"]; MV = wide["total_mv"]
base = C.iloc[-1]
d0 = pd.read_parquet(tmp_root / "daily" / "daily_20260907.parquet").copy()
a0 = pd.read_parquet(tmp_root / "adj" / "adj_20260907.parquet").copy()
d0["instrument"] = d0["ts_code"].astype(str); a0["instrument"] = a0["ts_code"].astype(str)
raw0 = d0.set_index("instrument")["close"] * a0.set_index("instrument")["adj_factor"]
scale = base / raw0.reindex(base.index)
rows = []
for ds in ["20260908","20260909","20260910","20260911","20260914","20260915","20260916","20260917","20260918","20260921","20260922","20260923","20260924"]:
    dd = pd.read_parquet(tmp_root / "daily" / ("daily_%s.parquet" % ds)).copy()
    aa = pd.read_parquet(tmp_root / "adj" / ("adj_%s.parquet" % ds)).copy()
    dd["instrument"] = dd["ts_code"].astype(str); aa["instrument"] = aa["ts_code"].astype(str)
    rawk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
    row = rawk.reindex(base.index) * scale; row.name = pd.Timestamp(ds); rows.append(row)
C = pd.concat([C, pd.DataFrame(rows)], axis=0).astype("float32")
cal = C.index; positions = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")

def ic_at(values, t, horizon, mode):
    i = positions[t]
    x = values.iloc[i].to_numpy(dtype="float64")
    if mode == "fwd":
        j, k = i + 1, i + 1 + horizon
    else:
        j, k = i - horizon, i
    if k >= len(cal) or j < 0:
        return None
    y = C.iloc[k].to_numpy(dtype="float64") / C.iloc[j].to_numpy(dtype="float64") - 1.0
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 100:
        return None
    xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
    return float(np.corrcoef(xr, yr)[0, 1])

F = {
    "ema26": C / C.ewm(span=26, adjust=False).mean() - 1.0,
    "size": MV,
    "ret20": C / C.shift(20) - 1.0,
    "vv_log": np.log(V).rolling(10).std(),
    "i40": ((C - O) / O).rolling(40).mean(),
    "i60": ((C - O) / O).rolling(60).mean(),
    "i120": ((C - O) / O).rolling(120).mean(),
}
# feed values to explain: (factor key, feed date, feed rank_ic)
TARGETS = [
    ("ema26", "2026-09-02", 0.232048),
    ("size", "2026-09-02", 0.242516),
    ("ret20", "2026-09-02", -0.000090),
    ("vv_log", "2026-09-02", 0.016354),
    ("i40", "2026-09-07", -0.234246),
    ("i60", "2026-09-07", -0.142097),
    ("i120", "2026-09-07", 0.116200),
]
dates = [d for d in cal[(cal >= pd.Timestamp("2026-07-20")) & (cal <= pd.Timestamp("2026-09-04"))]]
print("scan dates:", dates[0].date(), "..", dates[-1].date(), "n=", len(dates))
for h in (1, 2, 3, 5, 10):
    for mode in ("fwd", "bwd"):
        errs = []
        for key, fdate, fval in TARGETS:
            best = None
            for d in dates:
                v = ic_at(F[key], d, h, mode)
                if v is None:
                    continue
                if best is None or abs(v - fval) < abs(best[1] - fval):
                    best = (d, v)
            if best is not None:
                errs.append((key, best[0].date(), best[1], fval, best[1] - fval))
        worst = max(abs(e[4]) for e in errs)
        if worst < 0.12:
            print("h=%2d %s  worst|d|=%0.4f" % (h, mode, worst))
            for key, d, v, fval, dv in errs:
                print("     %-6s best date=%s mine=%+.4f feed=%+.4f d=%+.4f" % (key, d, v, fval, dv))
