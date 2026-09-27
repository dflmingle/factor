import os, sys, io, csv, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv"
tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]
T = wide["turnover"]; MV = wide["total_mv"]

def extend_close(C, dates):
    base = C.iloc[-1]
    d0 = pd.read_parquet(tmp_root / "daily" / "daily_20260907.parquet").copy()
    a0 = pd.read_parquet(tmp_root / "adj" / "adj_20260907.parquet").copy()
    d0["instrument"] = d0["ts_code"].astype(str); a0["instrument"] = a0["ts_code"].astype(str)
    raw0 = d0.set_index("instrument")["close"] * a0.set_index("instrument")["adj_factor"]
    scale = base / raw0.reindex(base.index)
    rows = []
    for ds in dates:
        dd = pd.read_parquet(tmp_root / "daily" / ("daily_%s.parquet" % ds)).copy()
        aa = pd.read_parquet(tmp_root / "adj" / ("adj_%s.parquet" % ds)).copy()
        dd["instrument"] = dd["ts_code"].astype(str); aa["instrument"] = aa["ts_code"].astype(str)
        rawk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
        row = rawk.reindex(base.index) * scale
        row.name = pd.Timestamp(ds)
        rows.append(row)
    return pd.concat([C, pd.DataFrame(rows)], axis=0).astype("float32")

C = extend_close(C, ["20260908","20260909","20260910","20260911","20260914","20260915","20260916","20260917","20260918","20260921","20260922","20260923","20260924"])
cal = C.index; positions = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")
print("panel extended to", cal[-1].date(), C.shape)

def day_stats(values, ds, step):
    d = pd.Timestamp(ds)
    if d not in positions:
        return None
    i = positions[d]
    if i + 1 + step >= len(cal):
        return None
    x = values.iloc[i].to_numpy(dtype="float64")
    y = (C.iloc[i + 1 + step].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 100:
        return None
    xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
    rank_ic = float(np.corrcoef(xr, yr)[0, 1])
    pear = float(np.corrcoef(x[valid], y[valid])[0, 1])
    return rank_ic, pear

F = {}
F["ema26_ratio"] = C / C.ewm(span=26, adjust=False).mean() - 1.0
F["short-term-reversal-20d"] = C / C.shift(20) - 1.0
F["small-cap-baseline"] = MV
F["intradayma40"] = ((C - O) / O).rolling(40).mean()
F["intradayma60"] = ((C - O) / O).rolling(60).mean()
F["intradayma90"] = ((C - O) / O).rolling(90).mean()
F["intradayma120"] = ((C - O) / O).rolling(120).mean()
F["bias60"] = C / C.rolling(60, min_periods=30).mean() - 1.0
F["bias20"] = C / C.rolling(20, min_periods=10).mean() - 1.0
F["amihud20"] = (ret1.abs() / A).rolling(20).mean()
F["vv_std10_log"] = np.log(V).rolling(10).std()
F["vv_std10_norm"] = V.rolling(10).std() / V.rolling(10).mean()
F["vv_ratio_std10"] = (V / V.rolling(20).mean()).rolling(10).std()
F["vv_dev_ratio10"] = (V / V.rolling(20).mean() - 1.0).abs().rolling(10).mean()
F["vv_std10_div_mean60"] = V.rolling(10).std() / V.rolling(60).mean()
F["vv_std10_div_std120"] = V.rolling(10).std() / V.rolling(120).std()
F["vv_range10"] = (V.rolling(10).max() / V.rolling(10).min())
F["vv_absdiff_mean10"] = V.diff().abs().rolling(10).mean() / V.rolling(10).mean()
F["vv_std10_amt"] = np.log(A).rolling(10).std()
F["vv_std10_turn"] = T.rolling(10).std() / T.rolling(10).mean()
F["vv_std10_ret"] = ret1.rolling(10).std()
F["vv_neg_std10"] = ret1.clip(upper=0).rolling(10).std()
F["vv_vol_times_std"] = V.rolling(10).std() * ret1.rolling(10).std()

def load_feed(path, names, skip_header=False):
    raw = open(path, encoding="utf-8").read().strip()
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    raw = raw.replace('\\"', '"').replace('\\n', '\n')
    rd = list(csv.reader(io.StringIO(raw)))
    if skip_header:
        rd = rd[1:]
    out = {}
    for r in rd:
        if len(r) < 9:
            continue
        out.setdefault(r[1], []).append((r[0], r[2], r[6] if len(r) > 6 else "", r[7], r[8]))
    return out

feed23 = load_feed(r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv", None)
print("feed23 names:", len(feed23))
f1718_path = r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv"
head = open(f1718_path, encoding="utf-8").readline()[:200]
print("feed1718 first line:", head)
