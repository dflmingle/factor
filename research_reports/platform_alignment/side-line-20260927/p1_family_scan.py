import os, sys, io, time, gc, json
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)

import psutil
vm = psutil.virtual_memory()
log("mem avail=%.2fGB" % (vm.available / 1e9))
if vm.available < 3.2e9:
    log("LOW MEM -> abort"); sys.exit(1)
proc = psutil.Process()

OUT = Path(os.environ["TEMP"]) / "side_conv"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; T = wide["turnover"]; MV = wide["total_mv"]
del wide; gc.collect()
log("wide %s rss=%.2fGB" % (str(C.shape), proc.memory_info().rss / 1e9))

cal = C.index; positions = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")

rj = json.loads((Path(r"D:\factor") / "t10-additions-20260911-candidates.results" / "6aa3c6d25d52c44d2f55c45b.json").read_text(encoding="utf-8-sig"))
ch = rj["results"]["factor_analysis"]["query_rank_ic_sequence_chart"]
sched = None
for e in ch["x"]:
    if str(e["name"]).lower() == "date":
        sched = [pd.Timestamp(v) for v in e["data"]]
log("sched n=%d %s..%s" % (len(sched), sched[0].date(), sched[-1].date()))

FUT = {}
for d in sched:
    i = positions[d]
    if i + 11 < len(cal):
        FUT[d] = (C.iloc[i + 11].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)

def score(values):
    ics = np.full(len(sched), np.nan)
    for k, d in enumerate(sched):
        if d not in FUT:
            continue
        x = values.iloc[positions[d]].to_numpy(dtype="float64"); y = FUT[d]
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

def mean_corr(v, w):
    cs = []
    for d in sched:
        i = positions[d]
        if i >= len(cal):
            continue
        x = v.iloc[i].to_numpy(dtype="float64"); y = w.iloc[i].to_numpy(dtype="float64")
        m = np.isfinite(x) & np.isfinite(y)
        if m.sum() < 100:
            continue
        xr = pd.Series(x[m]).rank().to_numpy(); yr = pd.Series(y[m]).rank().to_numpy()
        if np.std(xr) == 0 or np.std(yr) == 0:
            continue
        cs.append(float(np.corrcoef(xr, yr)[0, 1]))
    return float(np.mean(cs)) if cs else float("nan")

lowturn = (1.0 - T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()).astype("float32")
wg21 = ((T * ret1).rolling(21).sum() / T.rolling(21).sum()).astype("float32")
prox_low = lowturn.rank(axis=1, pct=True).astype("float32")
prox_size = (-np.log(MV.clip(lower=1.0))).astype("float32")
prox_wrev = (0.5 * (-wg21).rank(axis=1, pct=True) + 0.5 * prox_low).astype("float32")
log("proxies ready rss=%.2fGB" % (proc.memory_info().rss / 1e9))

rows = []
def add(name, v):
    st = score(v)
    if st is None:
        rows.append(dict(cand=name, n=0, ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan, c_low=np.nan, c_size=np.nan, c_wrev=np.nan))
        print("%-30s na" % name, flush=True)
        return
    c1 = c2 = c3 = np.nan
    if st[4] >= 0.030:
        c1 = mean_corr(v, prox_low); c2 = mean_corr(v, prox_size); c3 = mean_corr(v, prox_wrev)
    rows.append(dict(cand=name, n=st[0], ic=st[1], icir=st[2], win=st[3], s_i=st[4], c_low=c1, c_size=c2, c_wrev=c3))
    flag = " <== PASS" if st[4] >= 0.035 else ""
    print("%-30s n=%3d ic=%.4f icir=%.3f win=%.3f s_i=%.4f  corr[low=%+.2f size=%+.2f wrev=%+.2f]%s" % (
        name, st[0], st[1], st[2], st[3], st[4], c1, c2, c3, flag), flush=True)

print()
print("== F1: intradayma nudged windows (raw rep of shenren family) ==")
intraday = ((C - O) / O).astype("float32")
for n in [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 75, 90, 120, 150, 180, 240]:
    v = intraday.rolling(n).mean()
    add("F1-intradayma%d" % n, v)
    del v; gc.collect()

print()
print("== F1b: intradayma x lowturn overlays (best windows) ==")
for n in [20, 30, 40, 60]:
    r1 = intraday.rolling(n).mean().rank(axis=1, pct=True)
    add("F1b-im%d_mul" % n, r1 * prox_low)
    add("F1b-im%d_add50" % n, 0.5 * r1 + 0.5 * prox_low)
    del r1; gc.collect()

print()
print("== F2: neg-dev x low-turnover (guoyu family), scan windows ==")
for n in [5, 10, 15, 20, 25, 30, 40, 60]:
    negdev = (-(C / C.rolling(n, min_periods=max(3, n // 2)).mean() - 1.0)).astype("float32")
    nd_r = negdev.rank(axis=1, pct=True)
    for tname, tk in [("T", T), ("T5", T.rolling(5).mean()), ("T21", T.rolling(21).mean()),
                      ("Tr", T.rolling(21).mean() / T.rolling(252, min_periods=100).mean())]:
        v = nd_r * (1.0 - tk.rank(axis=1, pct=True))
        add("F2-nb%d_x_%s" % (n, tname), v)
        del v; gc.collect()
    del negdev, nd_r; gc.collect()

print()
print("== F3: vol-of-turnover/volume z-vs-5y (stdvol family), scan windows ==")
for n in [10, 20, 30, 60]:
    for bname, xx in [("T", T), ("V", V)]:
        v = xx.rolling(n).std() / xx.rolling(1250, min_periods=400).std()
        add("F3-std%s%d_div5y" % (bname, n), v)
        del v; gc.collect()

df = pd.DataFrame(rows)
df.to_csv(OUT / "p1_family_scan.csv", index=False, encoding="utf-8-sig")
print()
print("== P1 PASS list (s_i>=0.035, our 5y grid 10d) ==")
hits = df[df["s_i"] >= 0.035].sort_values("s_i", ascending=False)
print(hits[["cand", "n", "ic", "icir", "win", "s_i", "c_low", "c_size", "c_wrev"]].to_string(index=False))
print()
print("== top 15 by s_i ==")
print(df.sort_values("s_i", ascending=False).head(15)[["cand", "s_i", "ic", "icir", "win"]].to_string(index=False))
log("DONE rss=%.2fGB" % (proc.memory_info().rss / 1e9))
