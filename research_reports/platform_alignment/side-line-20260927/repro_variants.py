import os, sys, io, json, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]; T = wide["turnover"]; MV = wide["total_mv"]

tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"
base = C.iloc[-1]
d0 = pd.read_parquet(tmp_root / "daily" / "daily_20260907.parquet").copy()
a0 = pd.read_parquet(tmp_root / "adj" / "adj_20260907.parquet").copy()
d0["instrument"] = d0["ts_code"].astype(str); a0["instrument"] = a0["ts_code"].astype(str)
raw0 = d0.set_index("instrument")["close"] * a0.set_index("instrument")["adj_factor"]
scale = base / raw0.reindex(base.index)
ext_rows = []
for ds in ["20260908", "20260909", "20260910"]:
    dd = pd.read_parquet(tmp_root / "daily" / ("daily_%s.parquet" % ds)).copy()
    aa = pd.read_parquet(tmp_root / "adj" / ("adj_%s.parquet" % ds)).copy()
    dd["instrument"] = dd["ts_code"].astype(str); aa["instrument"] = aa["ts_code"].astype(str)
    rawk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
    row = rawk.reindex(base.index) * scale; row.name = pd.Timestamp(ds)
    ext_rows.append(row)
C = pd.concat([C, pd.DataFrame(ext_rows)], axis=0).astype("float32")
cal = C.index; positions = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")

def grid_from(start, step, count):
    p0 = positions.get(pd.Timestamp(start))
    if p0 is None:
        p0 = int(cal.searchsorted(pd.Timestamp(start)))
    return [cal[i] for i in range(p0, min(p0 + step * count, len(cal)), step)]

def score(values, schedule, step):
    fut = {}
    for d in schedule:
        i = positions[d]
        if i + 1 + step >= len(cal):
            continue
        fut[d] = (C.iloc[i + 1 + step].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
    ics = np.full(len(schedule), np.nan)
    for k, d in enumerate(schedule):
        if d not in fut:
            continue
        x = values.iloc[positions[d]].to_numpy(dtype="float64"); y = fut[d]
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100:
            continue
        xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
        if np.std(xr) == 0 or np.std(yr) == 0:
            continue
        ics[k] = float(np.corrcoef(xr, yr)[0, 1])
    s = ics[np.isfinite(ics)]
    m = float(np.mean(s)); sd = float(np.std(s, ddof=1))
    sign = 1.0 if m >= 0 else -1.0
    a = s * sign
    win = float(np.mean(a > 0.02)); icir = abs(m) / sd
    return len(s), abs(m), icir, win, abs(m) * icir * win

print("== volume-vol-10d variants (forests, G10 start 2021-09-15, 119) ==")
sch = grid_from("2021-09-15", 10, 119)
variants = {
  "vv_ratio_std10": (V / V.rolling(20).mean()).rolling(10).std(),
  "vv_ratio_dev10": (V / V.rolling(20).mean() - 1.0).abs().rolling(10).mean(),
  "vv_pctchg_std10": V.pct_change(fill_method=None).rolling(10).std(),
  "vv_logdiff_std10": np.log(V).diff().rolling(10).std(),
  "vv_std10_div_mean60": V.rolling(10).std() / V.rolling(60).mean(),
  "vv_std10_log_minus_std120": np.log(V).rolling(10).std() - np.log(V).rolling(120, min_periods=60).std(),
}
for name, v in variants.items():
    n, m, ir, w, si = score(v, sch, 10)
    print("%-26s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f  (target .0764/.845/.697)" % (name, n, m, ir, w, si))

print()
print("== pool2 factors (T3 / 20d low-turnover reversal) ==")
det = json.load(open(os.path.join(os.environ["TEMP"], "top20_factor_details.json"), encoding="utf-8"))
for pool, info in det.items():
    if info.get("rank") == 2:
        cyc = info.get("cycle")
        for f in info["factors"]:
            print("  %-28s win=%s..%s n=%s" % (f["factor_name"], f.get("window_start"), f.get("window_end"), f.get("sample_count")))
        f2 = info["factors"]
        start2 = f2[0].get("window_start"); n2 = f2[0].get("sample_count")
        sch2 = grid_from(start2, cyc, n2)
        t3_variants = {}
        for n in (16, 20, 40, 60):
            e1 = C.ewm(span=n, adjust=False).mean()
            e2 = e1.ewm(span=n, adjust=False).mean()
            e3 = e2.ewm(span=n, adjust=False).mean()
            t3_variants["T3_bias%d" % n] = C / e3 - 1.0
        t3_variants["bias20_p2"] = C / C.rolling(20, min_periods=10).mean() - 1.0
        t3_variants["ret20_p2"] = C / C.shift(20) - 1.0
        for name, v in t3_variants.items():
            n_, m, ir, w, si = score(v, sch2, cyc)
            print("  %-22s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, n_, m, ir, w, si))
        print("  targets: 20d-neg-dev-lowturn .0776/.527/.621 | T3-smooth-dev .0676/.408/.617")
