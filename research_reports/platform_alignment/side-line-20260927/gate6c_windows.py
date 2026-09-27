# -*- coding: utf-8 -*-
import os, sys, io, time, gc, pickle
from pathlib import Path
import numpy as np, pandas as pd, psutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0=time.time()
def log(m): print("[%7.1fs] %s" % (time.time()-T0, m), flush=True)
vm=psutil.virtual_memory(); log("avail=%.2fGB" % (vm.available/1e9))
if vm.available < 2.5e9: log("LOW MEM"); sys.exit(1)

OUT = Path(os.environ["TEMP"]) / "side_conv"
SEATS = Path(r"D:\factor\research_reports\platform_alignment\ab-batch-20260925\seat_panels_rebuilt.pkl")
wide = pd.read_pickle(OUT/"wide_panels.pkl")
C = wide["close"]; T = wide["turnover"]; V = wide["volume"]
del wide; gc.collect()
cal = C.index; pos = {d:i for i,d in enumerate(cal)}
payload = pickle.load(SEATS.open("rb"))
sched = [pd.Timestamp(d) for d in payload["dates"]]
FUT = payload["returns"].pivot(index="date", columns="instrument", values="forward_return").reindex(index=sched)
cols = FUT.columns
del payload; gc.collect()

Ts5 = T.rolling(1250, min_periods=400).std().astype("float32")
Vs5 = V.rolling(1250, min_periods=400).std().astype("float32")
t20r = (T.rolling(20).std() / Ts5)
t60r = (T.rolling(60).std() / Ts5).astype("float32")
t20sm63 = t20r.rank(axis=1, pct=True).rolling(63, min_periods=21).mean()
mix = (-(0.5 * t20sm63 + 0.5 * t60r.rank(axis=1, pct=True))).astype("float32")
t60 = (-t60r).astype("float32")
t20sm63n = (-t20sm63).astype("float32")
v10sm63 = (-(V.rolling(10).std() / Vs5)).rank(axis=1, pct=True).rolling(63, min_periods=21).mean().astype("float32")
del Ts5, Vs5, t20r, t60r; gc.collect()

def stats(panel, lo=None):
    vals=[]
    for d in sched:
        if lo is not None and d < lo: continue
        i=pos[d]
        if i+11 >= len(cal): continue
        x=panel.iloc[i].reindex(cols).to_numpy(dtype="float64")
        y=FUT.loc[d].to_numpy(dtype="float64")
        m=np.isfinite(x)&np.isfinite(y)
        if m.sum()<100: continue
        xr=pd.Series(x[m]).rank().to_numpy(); yr=pd.Series(y[m]).rank().to_numpy()
        if xr.std()==0 or yr.std()==0: continue
        vals.append(float(np.corrcoef(xr,yr)[0,1]))
    s=np.asarray(vals)
    if s.size<2: return (np.nan,np.nan,np.nan,s.size)
    mean=float(s.mean()); sd=float(s.std(ddof=1)); sign=1.0 if mean>=0 else -1.0
    win=float((s*sign>0.02).mean()); ir=abs(mean)/sd if sd>0 else np.nan
    return (abs(mean), ir, win, abs(mean)*ir*win if np.isfinite(ir) else np.nan, s.size)

last = sched[-1]
for nm, panel in [("HT-VOLSTAB-MIXsms", mix), ("HT-VOLSTAB-T60", t60), ("HT-VOLSTAB-T20sm63", t20sm63n), ("HT-VOLSTAB-V10sm63(ref)", v10sm63)]:
    r5=stats(panel); r1=stats(panel, lo=last-pd.Timedelta(days=365)); r3=stats(panel, lo=last-pd.Timedelta(days=91))
    print("%-26s 5y ic=%.4f si=%.4f | 1y ic=%.4f si=%.4f | 3m ic=%.4f si=%.4f (n=%d)" % (
        nm, r5[0], r5[3], r1[0], r1[3], r3[0], r3[3], r3[4]), flush=True)
    # yearly
    yr={}
    for d in sched:
        i=pos[d]
        if i+11>=len(cal): continue
        x=panel.iloc[i].reindex(cols).to_numpy(dtype="float64"); y=FUT.loc[d].to_numpy(dtype="float64")
        m=np.isfinite(x)&np.isfinite(y)
        if m.sum()<100: continue
        xr=pd.Series(x[m]).rank().to_numpy(); yr_=pd.Series(y[m]).rank().to_numpy()
        if xr.std()==0 or yr_.std()==0: continue
        yr.setdefault(d.year, []).append(float(np.corrcoef(xr,yr_)[0,1]))
    parts=[]
    for y in sorted(yr):
        a=np.asarray(yr[y]); mean=float(a.mean()); sd=float(a.std(ddof=1)); sign=1.0 if mean>=0 else -1.0
        win=float((a*sign>0.02).mean()); ir=abs(mean)/sd if sd>0 else float("nan")
        parts.append("%d:si=%.3f" % (y, abs(mean)*(ir if np.isfinite(ir) else 0)*win))
    print("      yearly:", " ".join(parts), flush=True)
del mix, t60, t20sm63n, v10sm63, T, V, C; gc.collect()
log("done")
