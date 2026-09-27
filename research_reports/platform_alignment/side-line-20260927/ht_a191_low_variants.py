import os, sys, time, gc, json, types
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)

try:
    import psutil
    vm = psutil.virtual_memory()
    log("mem avail=%.2fGB" % (vm.available / 1e9))
    if vm.available < 5e9:
        log("LOW MEM -> abort"); sys.exit(1)
except Exception:
    pass

TMP = Path(os.environ["TEMP"]) / "side_conv"
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
    for name, fn in ops.OPS.items():
        setattr(fo, name, fn)
    sys.modules["lib.ops.factor_ops"] = fo
    utils = types.ModuleType("lib.utils"); utils.__path__ = []
    sys.modules["lib.utils"] = utils
    ma = types.ModuleType("lib.utils.method_attrs"); ma.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = ma
    qlib = types.ModuleType("qlib"); qlib.__path__ = []
    sys.modules["qlib"] = qlib
    qd = types.ModuleType("qlib.data"); qd.__path__ = []
    sys.modules["qlib.data"] = qd
    qops = types.ModuleType("qlib.data.ops")
    for nm in ("rolling_slope", "rolling_rsquare", "rolling_resi",
               "expanding_slope", "expanding_rsquare", "expanding_resi"):
        setattr(qops, nm, getattr(ops, nm))
    sys.modules["qlib.data.ops"] = qops

def load_factors(path):
    ns = {}
    exec(compile(Path(path).read_text(encoding="utf-8"), str(path), "exec"), ns)
    return {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}

install_shim()
factors = load_factors(r"D:\factor\.cache\third_party\alpha191_reference.py")
log("factors=%d" % len(factors))

raw_dir = TMP / "a191_rich" / "raw_daily"
files = sorted(raw_dir.glob("raw_*.parquet"))
log("raw files=%d" % len(files))
raw = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
raw["date"] = pd.to_datetime(raw["trade_date"], format="%Y%m%d").dt.normalize()
raw["instrument"] = raw["ts_code"].astype(str)
raw = raw[raw["instrument"].str.endswith((".SH", ".SZ"))]
raw = raw.drop_duplicates(["date", "instrument"], keep="last")
log("raw rows=%d dates=%d instr=%d" % (len(raw), raw["date"].nunique(), raw["instrument"].nunique()))

def pivot(col):
    w = raw.pivot(index="date", columns="instrument", values=col)
    return w.sort_index().sort_index(axis=1).astype("float32")
open_r = pivot("open"); high_r = pivot("high"); low_r = pivot("low")
close_r = pivot("close"); vol = pivot("vol"); amt = pivot("amount")
del raw; gc.collect()
log("pivots %s" % (str(close_r.shape),))

wide = pd.read_pickle(TMP / "wide_panels.pkl")
T_all = wide["turnover"]
C_all = wide["close"]
del wide; gc.collect()

Tma21 = T_all.rolling(21).mean().astype("float32")
Tma504 = T_all.rolling(504, min_periods=200).mean().astype("float32")
lowturn_all = (1.0 - Tma21 / Tma504).astype("float32")
del Tma21, Tma504; gc.collect()

idx = close_r.index
cols = close_r.columns
C = C_all.reindex(index=idx, columns=cols)
T = T_all.reindex(index=idx, columns=cols)
lowturn = lowturn_all.reindex(index=idx, columns=cols)
del C_all, T_all, lowturn_all; gc.collect()

scale = (C / close_r).astype("float32")
log("scale median at first=%s last=%s" % (float(np.nanmedian(scale.iloc[0].to_numpy())), float(np.nanmedian(scale.iloc[-1].to_numpy()))))
open_q = (open_r * scale).astype("float32")
high_q = (high_r * scale).astype("float32")
low_q = (low_r * scale).astype("float32")
vwap_q = ((amt * 10.0 / vol) * scale).astype("float32")
del open_r, high_r, low_r, amt, scale; gc.collect()

data = {"open": open_q, "high": high_q, "low": low_q, "close": C, "volume": vol, "vwap": vwap_q}
del open_q, high_q, low_q, vwap_q; gc.collect()
log("data ready mem avail=%.2fGB" % (psutil.virtual_memory().available / 1e9))

s010 = factors["alpha191_010"](data); log("010 done")
s120 = factors["alpha191_120"](data); log("120 done")
s140 = factors["alpha191_140"](data); log("140 done")
gc.collect()
log("cores ready mem avail=%.2fGB" % (psutil.virtual_memory().available / 1e9))

rj = json.loads((Path(r"D:\factor") / "t10-additions-20260911-candidates.results" / "6aa3c6d25d52c44d2f55c45b.json").read_text(encoding="utf-8-sig"))
ch = rj["results"]["factor_analysis"]["query_rank_ic_sequence_chart"]
sched = None
for e in ch["x"]:
    if str(e["name"]).lower() == "date":
        sched = [pd.Timestamp(v) for v in e["data"]]
log("schedule n=%d %s..%s" % (len(sched), sched[0].date(), sched[-1].date()))

cal = C.index; pos = {d: i for i, d in enumerate(cal)}
STEP = 10
ret1 = C.pct_change(fill_method=None).astype("float32")
wg21 = ((T * ret1).rolling(21).sum() / T.rolling(21).sum()).astype("float32")
log("signals ready")

def rk(v):
    return pd.Series(v).rank(pct=True).to_numpy()

lt_rank = {}
for d in sched:
    if d in lowturn.index:
        lt_rank[d] = rk(lowturn.loc[d].to_numpy(dtype="float64"))

def rank_map(panel, sign):
    out = {}
    for d in sched:
        if d in panel.index:
            out[d] = rk(sign * panel.loc[d].to_numpy(dtype="float64"))
    return out

def window_stats(pairs, lo=None):
    d = np.array([p[0] for p in pairs]); v = np.array([p[1] for p in pairs], dtype=float)
    m = np.isfinite(v)
    if lo is not None:
        cut = sched[-1] - pd.Timedelta(days=lo)
        m &= (d >= cut)
    s = v[m]
    if s.size < 4:
        return None
    mean = float(s.mean()); std = float(s.std(ddof=1))
    sign = 1.0 if mean >= 0 else -1.0
    win = float(np.mean(s * sign > 0.02))
    ir = abs(mean) / std if std > 0 else float("nan")
    return s.size, abs(mean), ir, win, abs(mean) * ir * win

def evaluate(xmap, name):
    ics = []; to = []; prev = None
    for d in sched:
        x = xmap.get(d)
        i = pos.get(d)
        if x is None or i is None or i + 1 + STEP >= len(cal):
            prev = None; continue
        y = C.iloc[i + 1 + STEP].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100:
            prev = None; continue
        idxs = np.nonzero(valid)[0]
        xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
        ics.append((d, float(np.corrcoef(xr, yr)[0, 1])))
        s = x[valid]; thr = np.quantile(s, 0.9)
        cur = set(idxs[s >= thr].tolist())
        if prev is not None:
            to.append(1.0 - len(cur & prev) / max(1, len(cur)))
        prev = cur
    st5 = window_stats(ics); st1 = window_stats(ics, 365); st3 = window_stats(ics, 91)
    to5 = float(np.mean(to)) if to else float("nan")
    to1 = float(np.mean(to[-int(round(len(to) * 0.2)):])) if to else float("nan")
    return dict(name=name, st5=st5, st1=st1, st3=st3, to5=to5, to1=to1, ics=ics)

base_map = {}
for d in sched:
    if d in wg21.index and d in lt_rank:
        base_map[d] = 0.5 * rk(-wg21.loc[d].to_numpy(dtype="float64")) + 0.5 * lt_rank[d]

rows = [evaluate(base_map, "HT-WREV-LOWTURN-21D (base)")]
CORES = [("010", s010, -1.0), ("120", s120, 1.0), ("140", s140, 1.0)]
for tag, panel, sign in CORES:
    r = rank_map(panel, sign)
    rows.append(evaluate(r, "A191-%s core only" % tag))
    for wname, wc in [("1:1", 0.5), ("1:2", None)]:
        m = {}
        for d in r:
            if d in lt_rank:
                a = r[d]; b = lt_rank[d]
                m[d] = (0.5 * a + 0.5 * b) if wname == "1:1" else ((1.0 / 3.0) * a + (2.0 / 3.0) * b)
        rows.append(evaluate(m, "HT-A191-%s-LOW %s" % (tag, wname)))

# corr vs base composite
for row in rows:
    if row["name"] == "HT-WREV-LOWTURN-21D (base)":
        row["corr_base"] = 1.0; continue
    common = [d for d, _ in row["ics"] if d in base_map]
    vals = []
    for d in common:
        i = pos.get(d)
        pass
    row["corr_base"] = float("nan")

print()
hdr = "%-28s | %-34s | %-34s | %-9s | %s" % ("variant", "5y (n ic ir win s_i)", "1y (n ic ir win s_i)", "3m s_i", "turnover 5y/1y")
print(hdr); print("-" * len(hdr))
def f(st):
    return "n=%3d ic=%+.4f ir=%+.3f win=%.3f s_i=%.5f" % st if st else "n/a"
for row in rows:
    print("%-28s | %-34s | %-34s | %-9s | %.3f / %.3f" % (
        row["name"], f(row["st5"]), f(row["st1"]),
        ("%.5f" % row["st3"][4]) if row["st3"] else "n/a", row["to5"], row["to1"]))
print()
print("bar: our HT-WREV-LOWTURN-21D local 1y s_i .0330 (platform .0338); 5y local .0559 (platform .0571)")
print("target range (from the question): 5y .0404-.0980")

out = TMP / "ht_a191_low_variants_results.csv"
with out.open("w", encoding="utf-8") as fh:
    fh.write("variant,window,n,ic_abs,ir,win,s_i,turnover\n")
    for row in rows:
        for tag, st in [("5y", row["st5"]), ("1y", row["st1"]), ("3m", row["st3"])]:
            if st:
                fh.write("%s,%s,%d,%.6f,%.6f,%.6f,%.6f,%.4f\n" % (row["name"], tag, st[0], st[1], st[2], st[3], st[4], row["to5"] if tag != "1y" else row["to1"]))
log("wrote %s" % out)
