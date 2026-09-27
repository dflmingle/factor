import os, sys, io, types
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
OUT = Path(os.environ["TEMP"]) / "side_conv"
tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"
import alpha191_ops_local as ops

def install_shim():
    def factor_attr(*_args, **_kwargs):
        def decorator(function):
            return function
        return decorator
    lib = types.ModuleType("lib"); lib.__path__ = []
    sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object
    sys.modules["lib.base"] = base
    ops_pkg = types.ModuleType("lib.ops"); ops_pkg.__path__ = []
    sys.modules["lib.ops"] = ops_pkg
    factor_ops = types.ModuleType("lib.ops.factor_ops")
    for name, function in ops.OPS.items():
        setattr(factor_ops, name, function)
    sys.modules["lib.ops.factor_ops"] = factor_ops
    utils = types.ModuleType("lib.utils"); utils.__path__ = []
    sys.modules["lib.utils"] = utils
    method_attrs = types.ModuleType("lib.utils.method_attrs")
    method_attrs.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = method_attrs
    qlib = types.ModuleType("qlib"); qlib.__path__ = []
    sys.modules["qlib"] = qlib
    qlib_data = types.ModuleType("qlib.data"); qlib_data.__path__ = []
    sys.modules["qlib.data"] = qlib_data
    qlib_ops = types.ModuleType("qlib.data.ops")
    for name in ("rolling_slope", "rolling_rsquare", "rolling_resi",
                 "expanding_slope", "expanding_rsquare", "expanding_resi"):
        setattr(qlib_ops, name, getattr(ops, name))
    sys.modules["qlib.data.ops"] = qlib_ops

install_shim()
ref = Path(r"D:\factor\.cache\third_party\alpha191_reference.py")
ns = {}
exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
funcs = {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]; T = wide["turnover"]
MV = wide["total_mv"]; CMV = wide["circ_mv"]
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

def grid(start, step, count):
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
    if len(s) < 30:
        return None
    m = float(np.mean(s)); sd = float(np.std(s, ddof=1))
    sign = 1.0 if m >= 0 else -1.0
    a = s * sign
    win = float(np.mean(a > 0.02)); icir = abs(m) / sd
    return len(s), abs(m), icir, win, abs(m) * icir * win

print("== volume-vol-10d refinement (forests grid, target .0764/.845/.697) ==")
sch = grid("2021-09-15", 10, 119)
cand = {}
for n in (60, 120, 250):
    cand["std10_div_std%d" % n] = V.rolling(10).std() / V.rolling(n).std()
cand["std10_div_mean250"] = V.rolling(10).std() / V.rolling(250).mean()
cand["std10_div_mean120"] = V.rolling(10).std() / V.rolling(120).mean()
cand["std10_div_std120"] = V.rolling(10).std() / V.rolling(120).std()
cand["std10_log_div_std250"] = np.log(V).rolling(10).std() / np.log(V).rolling(250).std()
cand["std10_div_sum250"] = V.rolling(10).std() * 10.0 / V.rolling(250).sum()
cand["std10_div_std60"] = V.rolling(10).std() / V.rolling(60).std()
cand["std10_z_5y"] = (V.rolling(10).std() - V.rolling(1250, min_periods=400).mean()) / V.rolling(1250, min_periods=400).std()
for name, v in cand.items():
    st = score(v, sch, 10)
    if st is None:
        print("%-24s na" % name); continue
    print("%-24s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))

print()
print("== stdvol20 5y: percentile-style (shenren grid, target .0704/.703/.692) ==")
sch = grid("2021-09-22", 10, 120)
x = V.rolling(20).std()
rmin = x.rolling(1250, min_periods=400).min()
rmax = x.rolling(1250, min_periods=400).max()
cand = {}
cand["pct_minmax_stdV20"] = (x - rmin) / (rmax - rmin)
cand["std20_div_max1250_std"] = x / (V.rolling(1250, min_periods=400).std() * 1.0)
cand["std20_norm_by_median"] = x / V.rolling(1250, min_periods=400).median()
for name, v in cand.items():
    st = score(v, sch, 10)
    if st is None:
        print("%-26s na" % name); continue
    print("%-26s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))

print()
print("== dist-high variants (sx grid, 60d target .0136/.073/.449) ==")
sch = grid("2021-09-03", 4, 301)
cand = {}
cand["range_pos60"] = (C - C.rolling(60).min()) / (C.rolling(60).max() - C.rolling(60).min())
cand["neg_range_pos60"] = -cand["range_pos60"]
cand["dist_high60_div_std60"] = (C / C.rolling(60).max() - 1.0) / C.pct_change(fill_method=None).rolling(60).std()
cand["dist_high60_div_biasstd"] = (C / C.rolling(60).max() - 1.0) / (C / C.rolling(60, min_periods=30).mean() - 1.0).abs()
for name, v in cand.items():
    st = score(v, sch, 4)
    if st is None:
        print("%-26s na" % name); continue
    print("%-26s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))

print()
print("== pool2 composite: 20d neg-dev + low turnover (cyc5, target .0776/.527/.621) ==")
sch = grid("2021-09-08", 5, 240)
negdev = -(C / C.rolling(20, min_periods=10).mean() - 1.0)
cand = {}
cand["turnover_raw"] = T
xx = T.rank(axis=1, pct=True)
yy = negdev.rank(axis=1, pct=True)
cand["rank_negdev_plus_lowturn"] = yy + (1.0 - xx)
cand["rank_negdev_times_lowturn"] = yy * (1.0 - xx)
mask = T.rank(axis=1, pct=True) <= 0.5
cand["negdev_lowturn_universe"] = negdev.where(mask)
cand["negdev_only"] = negdev
for name, v in cand.items():
    st = score(v, sch, 5)
    if st is None:
        print("%-28s na" % name); continue
    print("%-28s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))

print()
print("== LW transforms of official alpha191 (pool6 grid, targets 010 .1253/.980/.798 | 120 .1021/.826/.765 | 140 .0653/.845/.731) ==")
sch = grid("2021-09-29", 10, 119)
data = dict(open=O, close=C, high=np.maximum(O, C), low=np.minimum(O, C), volume=V,
            amount=A, turnover=T, total_mv=MV, circ_mv=CMV, vwap=(A / V), returns=ret1)
base_sig = {}
for code in ["alpha191_010", "alpha191_120", "alpha191_140"]:
    try:
        base_sig[code] = funcs[code](data).astype("float32")
    except Exception as exc:
        print(code, "FAIL", str(exc)[:80])
for code, sig in base_sig.items():
    variants = {"raw": sig,
                "ma5": sig.rolling(5).mean(),
                "ma10": sig.rolling(10).mean(),
                "ma20": sig.rolling(20).mean(),
                "ma60": sig.rolling(60).mean()}
    for vname, v in variants.items():
        st = score(v, sch, 10)
        if st is None:
            print("%-14s %-6s na" % (code, vname)); continue
        print("%-14s %-6s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (code, vname, st[0], st[1], st[2], st[3], st[4]))
