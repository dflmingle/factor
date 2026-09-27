import os, sys, io, json, time, gc
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time()-T0, m), flush=True)

import psutil
vm = psutil.virtual_memory()
log("mem avail=%.2fGB" % (vm.available/1e9))
if vm.available < 3.0e9:
    log("LOW MEM -> abort"); sys.exit(1)
proc = psutil.Process()

OUT = Path(os.environ["TEMP"]) / "side_conv"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; T = wide["turnover"]
del wide; gc.collect()
log("wide %s rss=%.2fGB" % (str(C.shape), proc.memory_info().rss/1e9))

cal = C.index; pos = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")

rj = json.loads((Path(r"D:\factor") / "t10-additions-20260911-candidates.results" / "6aa3c6d25d52c44d2f55c45b.json").read_text(encoding="utf-8-sig"))
ch = rj["results"]["factor_analysis"]["query_rank_ic_sequence_chart"]
sched = None
for e in ch["x"]:
    if str(e["name"]).lower() == "date":
        sched = [pd.Timestamp(v) for v in e["data"]]
log("sched n=%d %s..%s" % (len(sched), sched[0].date(), sched[-1].date()))
STEP = 10
ncol = C.shape[1]

FUT = {}
for d in sched:
    i = pos.get(d)
    if i is not None and i + 1 + STEP < len(cal):
        FUT[d] = C.iloc[i+1+STEP].to_numpy(dtype="float64") / C.iloc[i+1].to_numpy(dtype="float64") - 1.0

Tma21 = T.rolling(21).mean().astype("float32")
Tma504 = T.rolling(504, min_periods=200).mean().astype("float32")
lowturn = (1.0 - Tma21/Tma504).astype("float32")
del Tma21, Tma504; gc.collect()
wg21 = ((T*ret1).rolling(21).sum()/T.rolling(21).sum()).astype("float32")
SEAT = (0.5*(-wg21).rank(axis=1, pct=True) + 0.5*lowturn.rank(axis=1, pct=True)).astype("float32")
del wg21, lowturn; gc.collect()
log("seat ready rss=%.2fGB" % (proc.memory_info().rss/1e9))

def window_stats(pairs, lo=None):
    d = np.array([p[0] for p in pairs]); v = np.array([p[1] for p in pairs], dtype=float)
    m = np.isfinite(v)
    if lo is not None:
        cut = sched[-1] - pd.Timedelta(days=lo)
        m &= (d >= cut)
    s = v[m]
    if s.size < 3:
        return None
    mean = float(s.mean()); std = float(s.std(ddof=1)) if s.size > 1 else float("nan")
    sign = 1.0 if mean >= 0 else -1.0
    win = float(np.mean(s*sign > 0.02))
    ir = abs(mean)/std if std and std > 0 else float("nan")
    return s.size, abs(mean), ir, win, abs(mean)*ir*win

STORE = {}
ROWS = []

def run(name, v):
    arr = np.full((len(sched), ncol), np.nan, dtype="float32")
    ics = []; to = []; prev = None
    for k, d in enumerate(sched):
        i = pos.get(d)
        if i is None or d not in FUT:
            prev = None; continue
        x = v.iloc[i].to_numpy(dtype="float64"); y = FUT[d]
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100:
            prev = None; continue
        idx = np.nonzero(valid)[0]
        xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
        if np.std(xr) > 0 and np.std(yr) > 0:
            ics.append((d, float(np.corrcoef(xr, yr)[0,1])))
        arr[k, idx] = x[valid].astype("float32")
        thr = np.quantile(x[valid], 0.9)
        cur = set(idx[x[valid] >= thr].tolist())
        if prev is not None:
            to.append(1.0 - len(cur & prev)/max(1, len(cur)))
        prev = cur
    st5 = window_stats(ics); st1 = window_stats(ics, 365); st3 = window_stats(ics, 91)
    to5 = float(np.mean(to)) if to else float("nan")
    to1 = float(np.mean(to[-int(round(len(to)*0.2)):])) if len(to) >= 5 else float("nan")
    months = {}
    for d, vv in ics:
        months.setdefault(d.strftime("%Y-%m"), []).append(vv)
    mneg = sum(1 for kk in months if np.mean(months[kk]) < 0)
    ROWS.append(dict(cand=name, n5=(st5[0] if st5 else 0),
        ic5=(st5[1] if st5 else np.nan), ir5=(st5[2] if st5 else np.nan), win5=(st5[3] if st5 else np.nan), si5=(st5[4] if st5 else np.nan),
        ic1=(st1[1] if st1 else np.nan), ir1=(st1[2] if st1 else np.nan), win1=(st1[3] if st1 else np.nan), si1=(st1[4] if st1 else np.nan),
        n3=(st3[0] if st3 else 0), ic3=(st3[1] if st3 else np.nan), si3=(st3[4] if st3 else np.nan),
        turn5=to5, turn1=to1, mneg=mneg, mtotal=len(months)))
    STORE[name] = arr
    r = ROWS[-1]
    print("%-18s 5y[ic=%.4f ir=%.3f win=%.3f si=%.4f] 1y[ic=%.4f ir=%.3f win=%.3f si=%.4f] 3m[n=%d si=%.4f] turn=%.2f/%.2f mneg=%d/%d" % (
        name, r["ic5"], r["ir5"], r["win5"], r["si5"], r["ic1"], r["ir1"], r["win1"], r["si1"],
        r["n3"], r["si3"], to5, to1, mneg, len(months)), flush=True)

Vs = V.rolling(1250, min_periods=400).std()
Ts = T.rolling(1250, min_periods=400).std()
gc.collect(); log("5y std ready rss=%.2fGB" % (proc.memory_info().rss/1e9))

v10 = (-(V.rolling(10).std()/Vs)).astype("float32"); run("HT-VOLSTAB-V10", v10)
v20 = (-(V.rolling(20).std()/Vs)).astype("float32"); run("HT-VOLSTAB-V20", v20)
del Vs; gc.collect()
t10 = (-(T.rolling(10).std()/Ts)).astype("float32"); run("HT-VOLSTAB-T10", t10)
t20 = (-(T.rolling(20).std()/Ts)).astype("float32"); run("HT-VOLSTAB-T20", t20)
del Ts; gc.collect()
blend = (0.5*v10.rank(axis=1, pct=True) + 0.5*t20.rank(axis=1, pct=True)).astype("float32")
run("HT-VOLSTAB-5050", blend)
del v10, v20, t10, t20, blend; gc.collect()

negdev60 = (-(C/C.rolling(60, min_periods=30).mean() - 1.0)).astype("float32")
nd60r = negdev60.rank(axis=1, pct=True)
v = (nd60r * (1.0 - T.rolling(5).mean().rank(axis=1, pct=True))).astype("float32")
run("F2-nb60_x_T5", v); del v, nd60r, negdev60; gc.collect()
negdev20 = (-(C/C.rolling(20, min_periods=10).mean() - 1.0)).astype("float32")
nd20r = negdev20.rank(axis=1, pct=True)
v = (nd20r * (1.0 - T.rolling(5).mean().rank(axis=1, pct=True))).astype("float32")
run("F2-nb20_x_T5", v); del v, nd20r, negdev20; gc.collect()

intraday = ((C-O)/O).astype("float32")
for n in [30, 40, 50]:
    v = intraday.rolling(n).mean()
    run("F1-im%d" % n, v); del v; gc.collect()
del intraday; gc.collect()

run("REF-SEAT", SEAT)

print()
print("== correlation with REF-SEAT (mean spearman over dates) ==")
seat_arr = STORE["REF-SEAT"]
for nm in [r["cand"] for r in ROWS]:
    if nm == "REF-SEAT": continue
    cs = []
    a = STORE[nm]
    for k in range(len(sched)):
        xa = a[k]; xs = seat_arr[k]
        m = np.isfinite(xa) & np.isfinite(xs)
        if m.sum() < 100: continue
        xr = pd.Series(xa[m]).rank().to_numpy(); sr = pd.Series(xs[m]).rank().to_numpy()
        if np.std(xr) > 0 and np.std(sr) > 0:
            cs.append(float(np.corrcoef(xr, sr)[0,1]))
    val = float(np.mean(cs)) if cs else np.nan
    for r in ROWS:
        if r["cand"] == nm: r["c_seat"] = val
    print("%-18s c_seat=%+.3f" % (nm, val))

bdf = pd.DataFrame(ROWS)
bdf.to_csv(OUT / "p2_robust.csv", index=False, encoding="utf-8-sig")
print()
print("== monthly IC (top by si5 + ref) ==")
for r in sorted(ROWS, key=lambda z: -(z["si5"] if np.isfinite(z["si5"]) else -1))[:6]:
    print("-- %s" % r["cand"])
print()
log("DONE rss=%.2fGB" % (proc.memory_info().rss/1e9))
