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
if vm.available < 2.5e9:
    log("LOW MEM -> abort"); sys.exit(1)
proc = psutil.Process()
def rss(): return proc.memory_info().rss / 1e9

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
log("funcs loaded")

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C0 = wide["close"]
T = wide["turnover"]
del wide; gc.collect()
log("wide %s rss=%.2fGB" % (str(C0.shape), rss()))

tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"
base = C0.iloc[-1]
d0 = pd.read_parquet(tmp_root / "daily" / "daily_20260907.parquet")
a0 = pd.read_parquet(tmp_root / "adj" / "adj_20260907.parquet")
d0 = d0.copy(); d0["instrument"] = d0["ts_code"].astype(str)
a0 = a0.copy(); a0["instrument"] = a0["ts_code"].astype(str)
raw0 = d0.set_index("instrument")["close"] * a0.set_index("instrument")["adj_factor"]
scale = base / raw0.reindex(base.index)
ext_rows = []
for ds in ["20260908","20260909","20260910","20260911","20260914","20260915","20260916",
           "20260917","20260918","20260921","20260922","20260923","20260924"]:
    dd = pd.read_parquet(tmp_root / "daily" / ("daily_%s.parquet" % ds)).copy()
    aa = pd.read_parquet(tmp_root / "adj" / ("adj_%s.parquet" % ds)).copy()
    dd["instrument"] = dd["ts_code"].astype(str); aa["instrument"] = aa["ts_code"].astype(str)
    rawk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
    row = rawk.reindex(base.index) * scale; row.name = pd.Timestamp(ds)
    ext_rows.append(row)
C = pd.concat([C0, pd.DataFrame(ext_rows)], axis=0).astype("float32")
del C0; gc.collect()
log("C extended %s" % str(C.shape))
cal = C.index; positions = {d: i for i, d in enumerate(cal)}

rj = json.loads((Path(r"D:\factor") / "t10-additions-20260911-candidates.results" / "6aa3c6d25d52c44d2f55c45b.json").read_text(encoding="utf-8-sig"))
ch = rj["results"]["factor_analysis"]["query_rank_ic_sequence_chart"]
sched5y = None
for e in ch["x"]:
    if str(e["name"]).lower() == "date":
        sched5y = [pd.Timestamp(v) for v in e["data"]]

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
log("grid6 n=%d %s..%s | sched5y n=%d" % (len(grid6), grid6[0].date(), grid6[-1].date(), len(sched5y)))

# ---------- rich panels (real high/low/amount) ----------
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
open_r = build_pivot("open")
high_r = build_pivot("high")
low_r = build_pivot("low")
close_r = build_pivot("close")
vol_r = build_pivot("vol")
amt_r = build_pivot("amount")
idxr = close_r.index; colr = close_r.columns
log("rich %s rss=%.2fGB avail=%.2fGB" % (str(close_r.shape), rss(), psutil.virtual_memory().available / 1e9))
Cq = C.reindex(index=idxr, columns=colr).astype("float32")
sc = (Cq / close_r).astype("float32")
open_r *= sc; high_r *= sc; low_r *= sc
amt_r *= (10.0 * sc)
amt_r /= vol_r
data_rich = {
    "open": open_r,
    "high": high_r,
    "low": low_r,
    "close": Cq,
    "volume": vol_r,
    "vwap": amt_r,
}
del close_r, sc; gc.collect()
log("data_rich ready rss=%.2fGB avail=%.2fGB" % (rss(), psutil.virtual_memory().available / 1e9))

S = {}
s010 = funcs["alpha191_010"]({"close": C}).astype("float32")
log("010 done")
s120r = funcs["alpha191_120"](data_rich).astype("float32")
log("120 done")
s140r = funcs["alpha191_140"](data_rich).astype("float32")
log("140 done")
del data_rich; gc.collect()
S["010"] = -s010
S["120"] = s120r.reindex(index=cal, columns=C.columns).astype("float32")
S["140"] = s140r.reindex(index=cal, columns=C.columns).astype("float32")
del s010, s120r, s140r; gc.collect()
log("signals oriented rss=%.2fGB" % rss())

TARGETS = {"010": (0.12527526, 0.98027350, 0.79831933),
           "120": (0.10208956, 0.82637552, 0.76470588),
           "140": (0.06529943, 0.84523040, 0.73109244)}

rkT = T.rank(axis=1, pct=True).reindex(index=cal).astype("float32")
lowt = (1.0 - rkT).astype("float32")
rkT5 = T.rolling(5).mean().rank(axis=1, pct=True).reindex(index=cal).astype("float32")
rkT21 = T.rolling(21).mean().rank(axis=1, pct=True).reindex(index=cal).astype("float32")

def cs_rank(df):
    return df.rank(axis=1, pct=True).astype("float32")

def resid_on(df, t):
    z = df.to_numpy(dtype="float64"); tt = t.to_numpy(dtype="float64")
    mz = np.nanmean(z, axis=1)[:, None]; mt = np.nanmean(tt, axis=1)[:, None]
    cz = z - mz; ct = tt - mt
    den = np.nansum(ct * ct, axis=1)[:, None]
    b = np.nansum(cz * ct, axis=1)[:, None] / np.where(den == 0, np.nan, den)
    out = cz - b * ct + mz
    return pd.DataFrame(out, index=df.index, columns=df.columns).astype("float32")

def smooth(df, kind):
    if kind == "raw": return df
    if kind == "ma5": return df.rolling(5).mean()
    if kind == "ma10": return df.rolling(10).mean()
    if kind == "ma20": return df.rolling(20).mean()
    if kind == "ema10": return df.ewm(span=10, adjust=False).mean()
    if kind == "tsr20": return df.rolling(20).rank(pct=True)
    raise ValueError(kind)

def apply_overlay(r1, name):
    if name == "none": return r1
    if name == "mul": return r1 * lowt
    if name == "mulrk": return cs_rank(r1 * lowt)
    if name == "add50": return 0.5 * r1 + 0.5 * lowt
    if name == "add67": return (2.0 / 3.0) * r1 + (1.0 / 3.0) * lowt
    if name == "div": return r1 / (rkT + 0.02)
    if name == "resid": return resid_on(r1, rkT)
    if name == "uni50": return r1.where(rkT <= 0.5)
    if name == "uni70": return r1.where(rkT <= 0.7)
    if name == "mulT5": return r1 * (1.0 - rkT5)
    if name == "mulT21": return r1 * (1.0 - rkT21)
    if name == "add50T21": return 0.5 * r1 + 0.5 * (1.0 - rkT21)
    raise ValueError(name)

SMOOTHS = ["raw", "ma5", "ma10", "ma20", "ema10", "tsr20"]
OVERLAYS = ["none", "mul", "mulrk", "add50", "add67", "div", "resid", "uni50", "uni70", "mulT5", "mulT21", "add50T21"]

rows = []
for tag in ["010", "120", "140"]:
    base_sig = S[tag]
    tic, ticir, twin = TARGETS[tag]
    for sm in SMOOTHS:
        smv = smooth(base_sig, sm) if sm != "raw" else base_sig
        r1 = cs_rank(smv)
        for ov in OVERLAYS:
            v = apply_overlay(r1, ov)
            st = score(v, grid6, 10)
            if st is None:
                continue
            n, ic, icir, win, si = st
            d = abs(ic - tic) + abs(icir - ticir) + abs(win - twin)
            rows.append(dict(base=tag, smooth=sm, overlay=ov, n=n, ic=ic, icir=icir, win=win, s_i=si, dist=d))
            del v
        del smv, r1
        gc.collect()
    log("%s search done rss=%.2fGB" % (tag, rss()))

df = pd.DataFrame(rows)
df.to_csv(OUT / "p0_lw_search.csv", index=False, encoding="utf-8-sig")
print()
print("== P0: best matches per base (target = opponent ic/icir/win) ==")
for tag in ["010", "120", "140"]:
    sub = df[df["base"] == tag].sort_values("dist").head(10)
    tic, ticir, twin = TARGETS[tag]
    print("-- base %s target ic=%.4f icir=%.3f win=%.3f (s_i=%.4f)" % (tag, tic, ticir, twin, tic * ticir * twin))
    for _, r in sub.iterrows():
        print("   %-6s x %-8s ic=%.4f icir=%.3f win=%.3f s_i=%.4f dist=%.4f" % (
            r["smooth"], r["overlay"], r["ic"], r["icir"], r["win"], r["s_i"], r["dist"]))

best = df.sort_values("dist").head(12)
print()
print("== top-12 overall re-scored on our 5y grid ==")
for _, r in best.iterrows():
    tag = r["base"]
    v = apply_overlay(cs_rank(smooth(S[tag], r["smooth"]) if r["smooth"] != "raw" else S[tag]), r["overlay"])
    st5 = score(v, sched5y, 10)
    if st5 is None:
        print("   %s %s %s -> na" % (tag, r["smooth"], r["overlay"])); continue
    print("   %s %-5s x %-8s dist6=%.4f | 5y n=%3d ic=%.4f icir=%.3f win=%.3f s_i=%.4f" % (
        tag, r["smooth"], r["overlay"], r["dist"], st5[0], st5[1], st5[2], st5[3], st5[4]))
log("DONE rss=%.2fGB" % rss())
