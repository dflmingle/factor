import os, sys, json, time, gc
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)
try:
    import psutil
    vm = psutil.virtual_memory()
    log("mem avail=%.1fGB" % (vm.available / 1e9))
    if vm.available < 5e9:
        log("LOW MEM -> abort"); sys.exit(1)
except Exception:
    pass

OUT = Path(os.environ["TEMP"]) / "side_conv"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; T = wide["turnover"]
del wide; gc.collect()
log("panels %s" % (str(C.shape),))

rj = json.loads((Path(r"D:\factor") / "t10-additions-20260911-candidates.results" / "6aa3c6d25d52c44d2f55c45b.json").read_text(encoding="utf-8-sig"))
ch = rj["results"]["factor_analysis"]["query_rank_ic_sequence_chart"]
sched = None
for e in ch["x"]:
    if str(e["name"]).lower() == "date":
        sched = [pd.Timestamp(v) for v in e["data"]]
log("schedule n=%d %s..%s" % (len(sched), sched[0].date(), sched[-1].date()))
cal = C.index; pos = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")
STEP = 10

Tma21 = T.rolling(21).mean().astype("float32")
Tma504 = T.rolling(504, min_periods=200).mean().astype("float32")
lowturn = (1.0 - Tma21 / Tma504).astype("float32")
wg21 = ((T * ret1).rolling(21).sum() / T.rolling(21).sum()).astype("float32")
wg60 = ((T * ret1).rolling(60).sum() / T.rolling(60).sum()).astype("float32")
wg120 = ((T * ret1).rolling(120).sum() / T.rolling(120).sum()).astype("float32")
ret20 = (C / C.shift(20) - 1.0).astype("float32")
ret40 = (C / C.shift(40) - 1.0).astype("float32")
lowhalf = Tma21.le(Tma21.median(axis=1), axis=0)
log("signals built")

def rk(x):
    return pd.Series(x).rank(pct=True).to_numpy()

VAR = {}
def add(name, fn): VAR[name] = fn
add("HT-WREV-LOWTURN-21D (base)", lambda i: 0.5 * rk(-wg21.iloc[i].to_numpy(dtype="float64")) + 0.5 * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
add("WREV21 x LOWTURN 1:2",      lambda i: (1/3.) * rk(-wg21.iloc[i].to_numpy(dtype="float64")) + (2/3.) * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
add("WREV21 x LOWTURN 1:4",      lambda i: 0.2 * rk(-wg21.iloc[i].to_numpy(dtype="float64")) + 0.8 * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
add("WREV21 only",               lambda i: rk(-wg21.iloc[i].to_numpy(dtype="float64")))
add("WREV60 x LOWTURN 1:1",      lambda i: 0.5 * rk(-wg60.iloc[i].to_numpy(dtype="float64")) + 0.5 * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
add("WREV120 x LOWTURN 1:1",     lambda i: 0.5 * rk(-wg120.iloc[i].to_numpy(dtype="float64")) + 0.5 * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
add("REV20 x LOWTURN 1:1",       lambda i: 0.5 * rk(-ret20.iloc[i].to_numpy(dtype="float64")) + 0.5 * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
add("REV40 x LOWTURN 1:1",       lambda i: 0.5 * rk(-ret40.iloc[i].to_numpy(dtype="float64")) + 0.5 * rk(lowturn.iloc[i].to_numpy(dtype="float64")))
def gated(i, sig):
    v = sig.iloc[i].to_numpy(dtype="float64")
    m = lowhalf.iloc[i].to_numpy()
    v = np.where(m & np.isfinite(v), v, np.nan)
    return rk(v)
add("WREV21 low-universe",       lambda i: gated(i, -wg21))
add("REV20 low-universe",        lambda i: gated(i, -ret20))

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

rows = []
for name, fn in VAR.items():
    ics = []; to = []; prev = None
    for d in sched:
        i = pos.get(d)
        if i is None or i + 1 + STEP >= len(cal):
            prev = None
            continue
        x = fn(i)
        y = C.iloc[i + 1 + STEP].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100:
            prev = None
            continue
        idx = np.nonzero(valid)[0]
        xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
        ics.append((d, float(np.corrcoef(xr, yr)[0, 1])))
        s = x[valid]
        thr = np.quantile(s, 0.9)
        cur = set(idx[s >= thr].tolist())
        if prev is not None:
            to.append(1.0 - len(cur & prev) / max(1, len(cur)))
        prev = cur
    st5 = window_stats(ics); st1 = window_stats(ics, 365); st3 = window_stats(ics, 91)
    to5 = float(np.mean(to)) if to else float("nan")
    to1 = float(np.mean(to[-int(round(len(to) * 0.2)):])) if to else float("nan")
    rows.append((name, st5, st1, st3, to5, to1))
    log("done %s" % name)

print()
print("%-28s | %-22s | %-22s | %-14s | %s" % ("variant", "5y (n/ic/ir/win/s_i)", "1y", "3m s_i", "turnover 5y/1y"))
for name, st5, st1, st3, to5, to1 in rows:
    def f(st):
        return "n=%3d ic=%+.4f ir=%+.3f win=%.3f s_i=%.5f" % st if st else "n/a"
    print("%-28s | %-22s | %-22s | %-14s | %.3f / %.3f" % (
        name, f(st5), f(st1), ("%.5f" % st3[4]) if st3 else "n/a", to5, to1))
print()
print("reference (platform, our own runs): HT-WREV-LOWTURN-21D 5y .0571 / 1y .0338 / 3m .0466, turnover 61%/rebalance")
