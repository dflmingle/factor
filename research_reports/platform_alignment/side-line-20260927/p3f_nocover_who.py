# -*- coding: utf-8 -*-
"""P3f: who are the no-fundamental-coverage names, and does the pool hold them?"""
import os, sys, io, time, gc, pickle, glob
from pathlib import Path
import numpy as np
import pandas as pd
import psutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)
ROOT = Path(r"D:\factor"); OUT = Path(os.environ["TEMP"]) / "side_conv"
SEATS = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
FIN = ROOT / "quantlab/.quantlab/cache/research/cn_equity/financial/fina_indicator"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
def zscore(f):
    return f.sub(f.mean(axis=1), axis=0).div(f.std(axis=1, ddof=0).replace(0, np.nan), axis=0)
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; T = wide["turnover"]; MV = wide["total_mv"]
del wide; gc.collect()
payload = pickle.load(SEATS.open("rb"))
sched = [pd.Timestamp(d) for d in payload["dates"]]
FUT = payload["returns"].pivot(index="date", columns="instrument", values="forward_return").reindex(index=sched)
sf = payload["signal_frame"].reset_index(drop=True); sc = payload["scores"].reset_index(drop=True)
seat_frame = pd.concat([sf, sc], axis=1); seat_frame["date"] = pd.to_datetime(seat_frame["date"])
seat_frame = seat_frame[seat_frame["date"].isin(sched)]
cols = FUT.columns
seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k).reindex(index=sched, columns=cols) for k in POOL}
del payload, sf, sc, seat_frame; gc.collect()
FUT = FUT.astype("float32"); ELIG = FUT.notna()
seat_z = {k: zscore(p) for k, p in seat_panels.items()}
base_score = sum(seat_z.values()) / len(POOL)
log("universe=%d names | wide cols=%d" % (len(cols), C.shape[1]))

files = sorted(glob.glob(str(FIN / "*.parquet")))
fin = pd.concat([pd.read_parquet(f, columns=["ts_code", "ann_date", "op_yoy"]) for f in files], ignore_index=True)
fin = fin[fin["ts_code"].isin(cols)]
fin["ann_date"] = pd.to_datetime(fin["ann_date"].astype("string"), format="%Y%m%d", errors="coerce")
fin = fin[fin["ann_date"].notna()].sort_values(["ts_code", "ann_date"]).drop_duplicates(["ts_code", "ann_date"], keep="last")
left = pd.DataFrame([(d, c) for d in sched for c in cols], columns=["ann_date", "ts_code"])
merged = pd.merge_asof(left.sort_values("ann_date"), fin.sort_values("ann_date"), on="ann_date", by="ts_code", direction="backward")
op = merged.pivot(index="ann_date", columns="ts_code", values="op_yoy").reindex(index=sched, columns=cols).astype("float32")
del left, merged, fin; gc.collect()
cover = op.notna()

# 1) who is uncovered
share = cover.to_numpy().mean(axis=1)
never = (~cover).all(axis=0)
some = (~cover).any(axis=0)
print("coverage per date: min=%.3f median=%.3f max=%.3f" % (share.min(), np.median(share), share.max()))
print("names never covered: %d (%.1f%%) | sometimes: %d" % (never.sum(), 100 * never.mean(), some.sum()))
print("never-covered sample:", list(pd.Index(cols)[never])[:15])
# 2) characteristics on a few dates
C_s = C.reindex(index=sched, columns=cols); T_s = T.reindex(index=sched, columns=cols); MV_s = MV.reindex(index=sched, columns=cols)
for i in (0, 40, 80, 119):
    cv = cover.iloc[i].to_numpy(); ok = ELIG.iloc[i].to_numpy() & np.isfinite(MV_s.iloc[i].to_numpy())
    g = ok & cv; r = ok & ~cv
    print("  %s cov=%.3f | median MV covered=%.2fe9 uncovered=%.2fe9 | median turn cov=%.3f unc=%.3f | mean fwd cov=%+.4f unc=%+.4f" % (
        sched[i].date(), cv.mean(), np.nanmedian(MV_s.iloc[i].to_numpy()[g]) / 1e9, np.nanmedian(MV_s.iloc[i].to_numpy()[r]) / 1e9,
        np.nanmedian(T_s.iloc[i].to_numpy()[g]), np.nanmedian(T_s.iloc[i].to_numpy()[r]),
        np.nanmean(FUT.iloc[i].to_numpy()[g]), np.nanmean(FUT.iloc[i].to_numpy()[r])))
# 3) does the pool hold them?
hold_unc, hold_size, held_n = [], [], []
prev = set()
for i, d in enumerate(sched):
    f = base_score.iloc[i].to_numpy(dtype="float64"); y = FUT.iloc[i].to_numpy(dtype="float64")
    ok = np.isfinite(f) & np.isfinite(y) & ELIG.iloc[i].to_numpy()
    idx = np.where(ok)[0]
    order = idx[np.argsort(-f[idx])][: int(len(idx) * 0.1)]
    unc = (~cover.iloc[i].to_numpy())[order]
    hold_unc.append(float(unc.mean())); hold_size.append(len(order))
    prev = set(order.tolist())
print("pool top-decile: uncovered share = %.4f (universe share %.4f) | avg held names = %.0f" % (
    np.mean(hold_unc), 1 - np.mean(share), np.mean(hold_size)))
# 4) annualised: pool vs pool-with-holdings' uncovered part removed
print()
print("held-return contribution of uncovered names (mean over dates):")
wr, nr = [], []
for i, d in enumerate(sched):
    f = base_score.iloc[i].to_numpy(dtype="float64"); y = FUT.iloc[i].to_numpy(dtype="float64")
    ok = np.isfinite(f) & np.isfinite(y) & ELIG.iloc[i].to_numpy()
    idx = np.where(ok)[0]
    order = idx[np.argsort(-f[idx])][: int(len(idx) * 0.1)]
    cu = cover.iloc[i].to_numpy()
    a = y[order][cu[order]]; b = y[order][~cu[order]]
    if len(a) and len(b):
        wr.append(a.mean()); nr.append(b.mean())
print("  covered-held mean fwd=%+.4f | uncovered-held mean fwd=%+.4f (n dates=%d)" % (np.mean(wr), np.mean(nr), len(wr)))
