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
    def factor_attr(*a, **k):
        def deco(f): return f
        return deco
    lib = types.ModuleType("lib"); lib.__path__ = []
    sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object
    sys.modules["lib.base"] = base
    op = types.ModuleType("lib.ops"); op.__path__ = []
    sys.modules["lib.ops"] = op
    fo = types.ModuleType("lib.ops.factor_ops")
    for n, f in ops.OPS.items(): setattr(fo, n, f)
    sys.modules["lib.ops.factor_ops"] = fo
    ut = types.ModuleType("lib.utils"); ut.__path__ = []
    sys.modules["lib.utils"] = ut
    ma = types.ModuleType("lib.utils.method_attrs"); ma.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = ma
    ql = types.ModuleType("qlib"); ql.__path__ = []
    sys.modules["qlib"] = ql
    qd = types.ModuleType("qlib.data"); qd.__path__ = []
    sys.modules["qlib.data"] = qd
    qo = types.ModuleType("qlib.data.ops")
    for n in ("rolling_slope","rolling_rsquare","rolling_resi","expanding_slope","expanding_rsquare","expanding_resi"):
        setattr(qo, n, getattr(ops, n))
    sys.modules["qlib.data.ops"] = qo
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
    rk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
    r = rk.reindex(base.index) * scale; r.name = pd.Timestamp(ds); rows.append(r)
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
        if d not in fut: continue
        x = values.iloc[positions[d]].to_numpy(dtype="float64"); y = fut[d]
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100: continue
        xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
        if np.std(xr) == 0 or np.std(yr) == 0: continue
        ics[k] = float(np.corrcoef(xr, yr)[0, 1])
    s = ics[np.isfinite(ics)]
    if len(s) < 30: return None
    m = float(np.mean(s)); sd = float(np.std(s, ddof=1))
    sign = 1.0 if m >= 0 else -1.0; a = s * sign
    win = float(np.mean(a > 0.02)); icir = abs(m) / sd
    return len(s), abs(m), icir, win, abs(m) * icir * win

print("== LW = alpha x low-turnover overlay (pool6 grid) ==")
sch = grid("2021-09-29", 10, 119)
data = dict(open=O, close=C, high=np.maximum(O, C), low=np.minimum(O, C), volume=V,
            amount=A, turnover=T, total_mv=MV, circ_mv=CMV, vwap=(A / V), returns=ret1)
lowt = 1.0 - T.rank(axis=1, pct=True)
for code, target in [("alpha191_010", "010_LW target .1253/.980/.798"), ("alpha191_120", "120_LW .1021/.826/.765"), ("alpha191_140", "140_LW .0653/.845/.731")]:
    try:
        s = funcs[code](data).astype("float32")
    except Exception as exc:
        print(code, "FAIL", str(exc)[:60]); continue
    sr = s.rank(axis=1, pct=True)
    variants = {
        "rank_x_lowt": sr * lowt,
        "rank_plus_lowt": sr + lowt,
        "ma10_x_lowt": s.rolling(10).mean().rank(axis=1, pct=True) * lowt,
        "ma20_x_lowt": s.rolling(20).mean().rank(axis=1, pct=True) * lowt,
        "rank_div_turn": sr / T.rank(axis=1, pct=True),
    }
    print("  %s (%s)" % (code, target))
    for vname, v in variants.items():
        st = score(v, sch, 10)
        if st is None:
            print("     %-14s na" % vname); continue
        print("     %-14s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (vname, st[0], st[1], st[2], st[3], st[4]))

print()
print("== stdvol20_5y alt bases (shenren grid, target .0704/.703/.692) ==")
sch = grid("2021-09-22", 10, 120)
alt = {
    "stdA20_div_stdA1250": A.rolling(20).std() / A.rolling(1250, min_periods=400).std(),
    "stdT20_div_stdT1250": T.rolling(20).std() / T.rolling(1250, min_periods=400).std(),
    "stdret20_div_stdret1250": ret1.rolling(20).std() / ret1.rolling(1250, min_periods=400).std(),
    "stdV20_div_stdV1250_log": np.log(V).rolling(20).std() / np.log(V).rolling(1250, min_periods=400).std(),
}
for name, v in alt.items():
    st = score(v, sch, 10)
    if st is None:
        print("%-26s na" % name); continue
    print("%-26s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f" % (name, st[0], st[1], st[2], st[3], st[4]))
