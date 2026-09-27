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
print("alphas loaded:", len(funcs))

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

data = dict(open=O, close=C, high=np.maximum(O, C), low=np.minimum(O, C), volume=V,
            amount=A, turnover=T, total_mv=MV, circ_mv=CMV, vwap=(A / V), returns=ret1)
SIG = {}
for code in ["alpha191_042", "alpha191_010", "alpha191_120", "alpha191_140", "alpha191_124"]:
    fn = funcs.get(code)
    if fn is None:
        print("missing", code); continue
    try:
        v = fn(data)
        if v is None:
            print(code, "returned None"); continue
        SIG[code] = v.astype("float32")
        print(code, "ok", v.shape)
    except Exception as exc:
        print(code, "FAIL", type(exc).__name__, str(exc)[:120])

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

print()
print("== alpha191 on opponent grids ==")
for code, (gname, start, step, count, oic, oicir, owin, on) in {
    "alpha191_042": ("forests", "2021-09-15", 10, 119, 0.0957, 0.975, 0.773, 119),
    "alpha191_042b": ("MS3(14)", "2021-09-22", 5, 240, 0.0696, 0.589, 0.696, 240),
    "alpha191_010": ("F191-010(7)", "2021-09-27", 5, 241, 0.0947, 0.688, 0.730, 241),
    "alpha191_120": ("pool6", "2021-09-29", 10, 119, 0.1021, 0.826, 0.765, 119),
    "alpha191_140": ("pool6", "2021-09-29", 10, 119, 0.0653, 0.845, 0.731, 119),
    "alpha191_124": ("pool6", "2021-09-29", 10, 119, 0.0014, 0.012, 0.378, 119),
}.items():
    key = code.replace("b", "") if code.endswith("b") else code
    if key not in SIG:
        print("%-14s missing" % code); continue
    sch = grid(start, step, count)
    st = score(SIG[key], sch, step)
    if st is None:
        print("%-14s no result" % code); continue
    print("%-14s %-12s mine n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f | opp n=%d ic=%+.4f icir=%+.3f win=%.3f" % (
        code, gname, st[0], st[1], st[2], st[3], st[4], on, oic, oicir, owin))

print()
print("== volume-vol-10d family (forests grid, target .0764/.845/.697) ==")
sch = grid("2021-09-15", 10, 119)
vv = {}
vv["corr_absret_vol10"] = ret1.abs().astype("float64").rolling(10).corr(V.astype("float64"))
vv["corr_absret_lnvol10"] = ret1.abs().astype("float64").rolling(10).corr(np.log(V.astype("float64")))
vv["corr_sqret_vol10"] = (ret1 ** 2).astype("float64").rolling(10).corr(V.astype("float64"))
vv["corr_absret_vol20"] = ret1.abs().astype("float64").rolling(20).corr(V.astype("float64"))
vv["corr_absret_vol60"] = ret1.abs().astype("float64").rolling(60).corr(V.astype("float64"))
vv["corr_absret_volratio10"] = ret1.abs().astype("float64").rolling(10).corr((V / V.rolling(20).mean()).astype("float64"))
vv["std10_vol_div_std250"] = V.rolling(10).std() / V.rolling(250).std()
for name, v in vv.items():
    st = score(v, sch, 10)
    if st is None:
        print("%-24s na" % name); continue
    print("%-24s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))

print()
print("== stdvol20_5y family (shenren grid, target .0704/.703/.692) ==")
sch = grid("2021-09-22", 10, 120)
def z5y(x):
    m = x.rolling(1250, min_periods=400).mean()
    s = x.rolling(1250, min_periods=400).std()
    return (x - m) / s
sv = {}
sv["z5y_stdV20"] = z5y(V.rolling(20).std())
sv["z5y_stdret20"] = z5y(ret1.rolling(20).std())
sv["z5y_stdV20_div_mean"] = z5y(V.rolling(20).std() / V.rolling(20).mean())
sv["std20_div_std1250"] = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()
sv["std20_div_mean1250"] = V.rolling(20).std() / V.rolling(1250, min_periods=400).mean()
sv["z5y_stdA20"] = z5y(A.rolling(20).std())
for name, v in sv.items():
    st = score(v, sch, 10)
    if st is None:
        print("%-24s na" % name); continue
    print("%-24s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))

print()
print("== dist-high (sx grid, target 60d: .0136/.073/.449 | 20d: .0073/.040/.395) ==")
sch = grid("2021-09-03", 4, 301)
hi = np.maximum(O, C)
dh = {}
for n in (40, 50, 60, 70, 80):
    dh["close_max%d" % n] = C / C.rolling(n).max() - 1.0
    dh["high_max%d" % n] = C / hi.rolling(n).max() - 1.0
dh["close_max60_vs_highmax60"] = hi.rolling(60).max() / C.rolling(60).max() - 1.0
for name, v in dh.items():
    st = score(v, sch, 4)
    if st is None:
        print("%-26s na" % name); continue
    print("%-26s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))
