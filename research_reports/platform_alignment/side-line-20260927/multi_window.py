import os, sys, io, time, gc, json, types
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(msg):
    print("[%7.1fs] %s" % (time.time() - T0, msg), flush=True)

try:
    import psutil
    _proc = psutil.Process()
    vm = psutil.virtual_memory()
    log("mem avail=%.1fGB total=%.1fGB" % (vm.available/1e9, vm.total/1e9))
    if vm.available < 5e9:
        log("LOW MEMORY -> abort"); sys.exit(1)
    def rss(): return _proc.memory_info().rss / 1e9
except Exception:
    def rss(): return float("nan")

OUT = Path(os.environ["TEMP"]) / "side_conv"
tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"
sys.path.insert(0, r"D:\factor\scripts")
import alpha191_ops_local as ops

def install_shim():
    def factor_attr(*a, **k):
        def deco(f): return f
        return deco
    lib = types.ModuleType("lib"); lib.__path__ = []; sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object; sys.modules["lib.base"] = base
    op = types.ModuleType("lib.ops"); op.__path__ = []; sys.modules["lib.ops"] = op
    fo = types.ModuleType("lib.ops.factor_ops")
    for n, f in ops.OPS.items(): setattr(fo, n, f)
    sys.modules["lib.ops.factor_ops"] = fo
    ut = types.ModuleType("lib.utils"); ut.__path__ = []; sys.modules["lib.utils"] = ut
    ma = types.ModuleType("lib.utils.method_attrs"); ma.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = ma
    ql = types.ModuleType("qlib"); ql.__path__ = []; sys.modules["qlib"] = ql
    qd = types.ModuleType("qlib.data"); qd.__path__ = []; sys.modules["qlib.data"] = qd
    qo = types.ModuleType("qlib.data.ops")
    for n in ("rolling_slope","rolling_rsquare","rolling_resi","expanding_slope","expanding_rsquare","expanding_resi"):
        setattr(qo, n, getattr(ops, n))
    sys.modules["qlib.data.ops"] = qo
install_shim()
ref = Path(r"D:\factor\.cache\third_party\alpha191_reference.py")
ns = {}
exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
funcs = {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}
log("alpha191 funcs: %d" % len(funcs))

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]; T = wide["turnover"]
MV = wide["total_mv"]; CMV = wide.get("circ_mv")
log("panels %s rss=%.2fGB" % (str(C.shape), rss()))

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
del rows, d0, a0, raw0, scale
gc.collect()
cal = C.index; positions = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")
log("close extended -> %s rss=%.2fGB" % (str(C.shape), rss()))

data = dict(open=O, close=C, high=np.maximum(O, C), low=np.minimum(O, C), volume=V,
            amount=A, turnover=T, total_mv=MV, circ_mv=CMV, vwap=(A / V), returns=ret1)
lowt_g = None

def grid(start, step, count):
    p0 = positions.get(pd.Timestamp(start))
    if p0 is None:
        p0 = int(cal.searchsorted(pd.Timestamp(start)))
    return [cal[i] for i in range(p0, min(p0 + step * count, len(cal)), step)]

def ic_series(values, schedule, step):
    fut = {}
    for d in schedule:
        i = positions[d]
        if i + 1 + step >= len(cal):
            continue
        fut[d] = (C.iloc[i + 1 + step].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
    ics = np.full(len(schedule), np.nan)
    for k, d in enumerate(schedule):
        if d > pd.Timestamp("2026-09-07"):
            continue
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
    return ics, max(fut) if fut else None

def wstats(ics, schedule, end, days):
    if end is None:
        return None
    cut = end - pd.Timedelta(days=days)
    idx = [k for k, d in enumerate(schedule) if cut <= d <= end]
    s = ics[idx]; s = s[np.isfinite(s)]
    if len(s) < 4:
        return dict(n=int(len(s)), ic=float("nan"), icir=float("nan"), win=float("nan"), s_i=float("nan"))
    m = float(np.mean(s)); sd = float(np.std(s, ddof=1))
    sign = 1.0 if m >= 0 else -1.0
    win = float(np.mean(s * sign > 0.02)); icir = abs(m) / sd if sd > 0 else float("nan")
    return dict(n=int(len(s)), ic=abs(m), icir=icir, win=win, s_i=abs(m) * icir * win)

POOLS = {
    "2 guoyu":   ("2021-09-08", 5, 240),
    "4 sx":      ("2021-09-03", 4, 301),
    "5 dfkai":   ("2021-09-07", 5, 240),
    "6 xinren":  ("2021-09-29", 10, 119),
    "7 lavine":  ("2021-09-27", 5, 241),
    "8 forests": ("2021-09-15", 10, 119),
    "10 shenren":("2021-09-22", 10, 120),
    "14 wangfu": ("2021-09-22", 5, 240),
}

def t3(n=20):
    e1 = C.ewm(span=n, adjust=False).mean()
    e2 = e1.ewm(span=n, adjust=False).mean()
    e3 = e2.ewm(span=n, adjust=False).mean()
    return C / e3 - 1.0

def pool_builders(pool):
    if pool == "2 guoyu":
        return {
            "20d-negdev_x_lowturn": lambda: (-(C / C.rolling(20, min_periods=10).mean() - 1.0)).rank(axis=1, pct=True) * (1.0 - T.rank(axis=1, pct=True)),
            "T3_bias20": t3,
        }
    if pool == "4 sx":
        return {
            "bias10": lambda: C / C.rolling(10, min_periods=5).mean() - 1.0,
            "bias20": lambda: C / C.rolling(20, min_periods=10).mean() - 1.0,
            "bias60": lambda: C / C.rolling(60, min_periods=30).mean() - 1.0,
            "ret10": lambda: C / C.shift(10) - 1.0,
            "disthigh20": lambda: C / C.rolling(20).max() - 1.0,
            "disthigh60": lambda: C / C.rolling(60).max() - 1.0,
        }
    if pool == "5 dfkai":
        return {
            "amihud20": lambda: (ret1.abs() / A).rolling(20).mean(),
            "size_total_mv": lambda: MV,
        }
    if pool == "6 xinren":
        out = {}
        for code in ("alpha191_010", "alpha191_120", "alpha191_140"):
            try:
                s = funcs[code](data).astype("float32")
            except Exception as exc:
                log("%s FAIL %s" % (code, str(exc)[:80])); continue
            sr = s.rank(axis=1, pct=True)
            out[code + "_raw"] = (lambda ss: (lambda: ss))(s)
            out[code + "_rank_x_lowt"] = (lambda rr: (lambda: rr * (1.0 - T.rank(axis=1, pct=True))))(sr)
            out[code + "_ma20_x_lowt"] = (lambda ss: (lambda: ss.rolling(20).mean().rank(axis=1, pct=True) * (1.0 - T.rank(axis=1, pct=True))))(s)
        return out
    if pool == "7 lavine":
        return {
            "maxret20": lambda: ret1.rolling(20).max(),
            "pvcorr20": lambda: C.astype("float64").rolling(20).corr(V.astype("float64")),
            "amt60_log": lambda: np.log(A.rolling(60).mean()),
            "amihud5": lambda: (ret1.abs() / A).rolling(5).mean(),
            "amihud20": lambda: (ret1.abs() / A).rolling(20).mean(),
            "size_total_mv": lambda: MV,
        }
    if pool == "8 forests":
        return {
            "vv10_div_mean250": lambda: V.rolling(10).std() / V.rolling(250).mean(),
            "ema26_ratio": lambda: C / C.ewm(span=26, adjust=False).mean() - 1.0,
            "ret20": lambda: C / C.shift(20) - 1.0,
            "size_total_mv": lambda: MV,
        }
    if pool == "10 shenren":
        intraday = (C - O) / O
        out = {
            "intradayma40": (lambda x: (lambda: x.rolling(40).mean()))(intraday),
            "intradayma60": (lambda x: (lambda: x.rolling(60).mean()))(intraday),
            "intradayma90": (lambda x: (lambda: x.rolling(90).mean()))(intraday),
            "intradayma120": (lambda x: (lambda: x.rolling(120).mean()))(intraday),
            "stdT20_div_stdT1250": lambda: T.rolling(20).std() / T.rolling(1250, min_periods=400).std(),
        }
        return out
    if pool == "14 wangfu":
        out = {}
        try:
            s = funcs["alpha191_042"](data).astype("float32")
            out["alpha191_042_official"] = (lambda ss: (lambda: ss))(s)
        except Exception as exc:
            log("042 FAIL %s" % (str(exc)[:80]))
        return out
    return {}

rows_out = []
for pool, (start, step, count) in POOLS.items():
    sch = grid(start, step, count)
    builders = pool_builders(pool)
    log("== %s grid %s..%s n=%d rss=%.2fGB" % (pool, sch[0].date(), sch[-1].date(), len(sch), rss()))
    for fname, build in builders.items():
        t0 = time.time()
        try:
            values = build()
        except Exception as exc:
            print("   %-28s BUILD FAIL %s" % (fname, str(exc)[:80])); continue
        ics, end = ic_series(values, sch, step)
        st5 = wstats(ics, sch, end, 36500)
        st1 = wstats(ics, sch, end, 365)
        st3 = wstats(ics, sch, end, 91)
        del values; gc.collect()
        print("   %-28s 5y n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.5f | 1y n=%2d ic=%+.4f icir=%+.3f win=%.3f s_i=%.5f | 3m n=%2d s_i=%.5f (%.1fs)" % (
            fname, st5["n"], st5["ic"], st5["icir"], st5["win"], st5["s_i"],
            st1["n"], st1["ic"], st1["icir"], st1["win"], st1["s_i"], st3["n"], st3["s_i"], time.time()-t0))
        for wname, st in (("5y", st5), ("1y", st1), ("3m", st3)):
            rows_out.append(dict(pool=pool, factor=fname, window=wname, n=st["n"], ic=st["ic"], icir=st["icir"], win=st["win"], s_i=st["s_i"]))
pd.DataFrame(rows_out).to_csv(OUT / "multi_window_stats.csv", index=False, encoding="utf-8-sig")
log("DONE rss=%.2fGB" % rss())

