import os, sys, io
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv"
tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; MV = wide["total_mv"]
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

F = {
    "ema26": C / C.ewm(span=26, adjust=False).mean() - 1.0,
    "size": MV,
    "ret20": C / C.shift(20) - 1.0,
    "vv_log": np.log(V).rolling(10).std(),
    "i40": ((C - O) / O).rolling(40).mean(),
    "i60": ((C - O) / O).rolling(60).mean(),
    "i120": ((C - O) / O).rolling(120).mean(),
}
CONV = {
    "same_shift1": (1, 1),   # corr(f(t), close(t+1)/close(t)-1)
    "fwd1_shift1": (1, 2),   # corr(f(t), close(t+2)/close(t+1)-1)
    "contemp": (0, 1),       # corr(f(t), close(t)/close(t-1)-1)
    "lag1_contemp": (-1, 0), # corr(f(t-1), close(t)/close(t-1)-1)
}
def ic_conv(values, t, ja, kb):
    i = positions[t]
    if i + kb >= len(cal) or i + ja < 0:
        return None
    x = values.iloc[i].to_numpy(dtype="float64")
    y = C.iloc[i + kb].to_numpy(dtype="float64") / C.iloc[i + ja].to_numpy(dtype="float64") - 1.0
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 100:
        return None
    xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
    return float(np.corrcoef(xr, yr)[0, 1]), float(np.corrcoef(x[valid], y[valid])[0, 1])

CHECKS = [("ema26", "2026-09-02", 0.232048, 0.178415),
          ("size", "2026-09-02", 0.242516, 0.042196),
          ("ret20", "2026-09-02", -0.000090, 0.073018),
          ("vv_log", "2026-09-02", 0.016354, -0.027930),
          ("i40", "2026-09-07", -0.234246, -0.192898),
          ("i60", "2026-09-07", -0.142097, -0.095540),
          ("i120", "2026-09-07", 0.116200, 0.147848)]
for cname, (ja, kb) in CONV.items():
    print("== convention %s (j=%+d k=%+d) ==" % (cname, ja, kb))
    for key, dt, frank, fpear in CHECKS:
        st = ic_conv(F[key], pd.Timestamp(dt), ja, kb)
        if st is None:
            print("   %-6s na" % key); continue
        print("   %-6s mine rank=%+.4f pear=%+.4f | feed rank=%+.4f pear=%+.4f | d_rank=%+.4f d_pear=%+.4f" % (
            key, st[0], st[1], frank, fpear, st[0] - frank, st[1] - fpear))
