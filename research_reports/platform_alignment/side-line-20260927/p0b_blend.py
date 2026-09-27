import os, sys, io, types, time, gc, json
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)

import psutil
vm = psutil.virtual_memory()
log("mem avail=%.2fGB" % (vm.available / 1e9))
if vm.available < 2.4e9:
    log("LOW MEM -> abort"); sys.exit(1)
proc = psutil.Process()

OUT = Path(os.environ["TEMP"]) / "side_conv"
sys.path.insert(0, r"D:\factor\scripts")
import alpha191_ops_local as ops

def install_shim():
    def factor_attr(*_a, **_k):
        def deco(fn): return fn
        return deco
    lib = types.ModuleType("lib"); lib.__path__ = []
    sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object
    sys.modules["lib.base"] = base
    pkg = types.ModuleType("lib.ops"); pkg.__path__ = []
    sys.modules["lib.ops"] = pkg
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
C = wide["close"]; T = wide["turnover"]; V = wide["volume"]
del wide; gc.collect()
cal = C.index; positions = {d: i for i, d in enumerate(cal)}

def grid(start, step, count):
    p0 = positions.get(pd.Timestamp(start))
    if p0 is None:
        p0 = int(cal.searchsorted(pd.Timestamp(start)))
    return [cal[i] for i in range(p0, min(p0 + step * count, len(cal)), step)]

def score(values, schedule, step):
    fut = {}
    for d in schedule:
        i = positions.get(d)
        if i is None or i + 1 + step >= len(cal):
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

grid6 = grid("2021-09-29", 10, 119)
log("grid6 %s..%s n=%d" % (grid6[0].date(), grid6[-1].date(), len(grid6)))

raw_dir = OUT / "a191_rich" / "raw_daily"
files = sorted(raw_dir.glob("raw_*.parquet"))
def build_pivot(col):
    parts = []
    for f in files:
        df = pd.read_parquet(f, columns=["trade_date", "ts_code", col])
        df.columns = ["date", "instrument", "v"]
        parts.append(df)
    long = pd.concat(parts, ignore_index=True)
    del parts
    long["date"] = pd.to_datetime(long["date"], format="%Y%m%d").dt.normalize()
    long["instrument"] = long["instrument"].astype(str)
    long = long.drop_duplicates(["date", "instrument"], keep="last")
    p = long.pivot(index="date", columns="instrument", values="v").astype("float32")
    p = p.sort_index().sort_index(axis=1)
    del long; gc.collect()
    return p
open_r = build_pivot("open"); high_r = build_pivot("high"); low_r = build_pivot("low")
close_r = build_pivot("close"); vol_r = build_pivot("vol"); amt_r = build_pivot("amount")
idxr = close_r.index; colr = close_r.columns
Cq = C.reindex(index=idxr, columns=colr).astype("float32")
sc = (Cq / close_r).astype("float32")
open_r *= sc; high_r *= sc; low_r *= sc
amt_r *= (10.0 * sc); amt_r /= vol_r
data_rich = {"open": open_r, "high": high_r, "low": low_r, "close": Cq, "volume": vol_r, "vwap": amt_r}
del close_r, sc; gc.collect()
log("rich ready rss=%.2fGB" % (proc.memory_info().rss / 1e9))

S = {}
S["010"] = (-funcs["alpha191_010"]({"close": C})).astype("float32")
S["120"] = funcs["alpha191_120"](data_rich).astype("float32")
S["140"] = funcs["alpha191_140"](data_rich).astype("float32")
del data_rich; gc.collect()
for k in S: log("signal %s done" % k)

# ---- lowturn definitions on grid6 ----
LT = {}
LT["lvl1mT"] = 1.0 - T.rank(axis=1, pct=True)
LT["rel_T21_T504"] = 1.0 - (T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()).rank(axis=1, pct=True)
LT["rel_T5_T252"] = 1.0 - (T.rolling(5).mean() / T.rolling(252, min_periods=100).mean()).rank(axis=1, pct=True)
LT["lvl1mT21"] = 1.0 - T.rolling(21).mean().rank(axis=1, pct=True)
LT["rel_T21_T252"] = 1.0 - (T.rolling(21).mean() / T.rolling(252, min_periods=100).mean()).rank(axis=1, pct=True)
LT["rank_rel"] = (T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()).rank(axis=1, pct=True) * -1.0
STD_RET = C.pct_change(fill_method=None).astype("float32")
LT["volret"] = (1.0 - STD_RET.rolling(20).std().rank(axis=1, pct=True)).astype("float32")
LT["volT5y"] = (1.0 - (T.rolling(20).std() / T.rolling(1250, min_periods=400).std()).rank(axis=1, pct=True)).astype("float32")
LT["volV5y"] = (1.0 - (V.rolling(10).std() / V.rolling(1250, min_periods=400).std()).rank(axis=1, pct=True)).astype("float32")
print()
print("== LT definition calibration (pool6 grid, targets: F-A07 .0846/.454/.630 | F-B09 .0587/.627/.664) ==")
lt_targets = {"F-A07": (0.08461577, 0.45392932, 0.63025210), "F-B09": (0.05866934, 0.62657058, 0.66386555)}
lt_rows = []
for name, v in LT.items():
    st = score(v, grid6, 10)
    if st is None:
        print("%-14s na" % name); continue
    dA = abs(st[1]-lt_targets["F-A07"][0]) + abs(st[2]-lt_targets["F-A07"][1]) + abs(st[3]-lt_targets["F-A07"][2])
    dB = abs(st[1]-lt_targets["F-B09"][0]) + abs(st[2]-lt_targets["F-B09"][1]) + abs(st[3]-lt_targets["F-B09"][2])
    lt_rows.append((name, st, dA, dB))
    print("%-14s ic=%.4f icir=%.3f win=%.3f s_i=%.4f | dA07=%.4f dB09=%.4f" % (name, st[1], st[2], st[3], st[4], dA, dB))

# ---- blend sweep ----
TARGETS = {"010": (0.12527526, 0.98027350, 0.79831933),
           "120": (0.10208956, 0.82637552, 0.76470588),
           "140": (0.06529943, 0.84523040, 0.73109244)}
print()
print("== LW = w*rank(alpha) + (1-w)*rank(LT) sweep (pool6 grid) ==")
best_rows = []
for tag in ["010", "120", "140"]:
    ra = S[tag].reindex(index=cal, columns=C.columns).rank(axis=1, pct=True).astype("float32")
    tic, ticir, twin = TARGETS[tag]
    print("-- %s target ic=%.4f icir=%.3f win=%.3f s_i=%.4f" % (tag, tic, ticir, twin, tic*ticir*twin))
    for ltname in ["lvl1mT", "rel_T5_T252", "volret", "volT5y", "volV5y"]:
        rl = LT[ltname].reindex(index=cal).astype("float32")
        line = "   %-14s" % ltname
        for w in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            v = w * ra + (1.0 - w) * rl
            st = score(v, grid6, 10)
            if st is None:
                line += "  w=%.1f na" % w; continue
            d = abs(st[1]-tic) + abs(st[2]-ticir) + abs(st[3]-twin)
            best_rows.append(dict(base=tag, lt=ltname, w=w, ic=st[1], icir=st[2], win=st[3], s_i=st[4], dist=d))
            line += " | w=%.1f ic=%.4f ir=%.3f win=%.3f s=%.4f d=%.3f" % (w, st[1], st[2], st[3], st[4], d)
        print(line, flush=True)

bdf = pd.DataFrame(best_rows)
bdf.to_csv(OUT / "p0b_blend_sweep.csv", index=False, encoding="utf-8-sig")
print()
print("== best blends overall ==")
for tag in ["010", "120", "140"]:
    sub = bdf[bdf["base"] == tag].sort_values("dist").head(4)
    print("-- %s" % tag)
    print(sub[["lt", "w", "ic", "icir", "win", "s_i", "dist"]].to_string(index=False))
log("DONE rss=%.2fGB" % (proc.memory_info().rss / 1e9))
