# -*- coding: utf-8 -*-
"""P3e: is the coverage effect real for the pool (platform-faithful split:
selection restricted to masked names, benchmark unchanged), and is it a
'listing age / 次新' effect?

select_mask limits what the top-decile can hold; the benchmark mean stays the
full eligible universe (like a fixed platform benchmark).
"""
import os, sys, io, time, gc, pickle, glob
from pathlib import Path
import numpy as np
import pandas as pd
import psutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)
def mem(tag, floor=None):
    a = psutil.virtual_memory().available / 1e9
    log("%s avail=%.2fGB" % (tag, a))
    if floor is not None and a < floor:
        log("LOW MEM -> abort"); sys.exit(1)
    return a

ROOT = Path(r"D:\factor"); OUT = Path(os.environ["TEMP"]) / "side_conv"
SEATS = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
FIN = ROOT / "quantlab/.quantlab/cache/research/cn_equity/financial/fina_indicator"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817, "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692, "book_to_market_lf_plus_impact": 0.01540}
CYCLE, COST, POINTS = 10, 0.006, 44000.0
mem("start", 2.2)
proc = psutil.Process()

def ledger(score, forward, eligible, select=None):
    held, gross, turnover, valid, share = [], [], [], [], []
    previous = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64"); y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y) & eligible.loc[date].to_numpy(dtype=bool)
        sel = ok if select is None else (ok & select.loc[date].to_numpy(dtype=bool))
        if sel.sum() < 100 or ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan); valid.append(False); share.append(np.nan); continue
        instruments = score.columns.to_numpy()
        order = np.argsort(-f[sel])[: int(sel.sum() * 0.1)]
        selected = set(instruments[sel][order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(y[sel][order].mean()))
        gross.append(float(y[sel][order].mean() - y[ok].mean()))
        share.append(float(sel.sum() / ok.sum()))
        valid.append(True)
    return pd.DataFrame({"date": list(score.index), "held": held, "gross": gross,
                         "turnover": turnover, "share": share, "valid": valid})

def pool_metrics(score, forward, eligible, seat_si, select=None):
    df = ledger(score, forward, eligible, select)
    d = df[df["valid"]].copy()
    if len(d) < 3:
        return {}, df
    held = d["held"].to_numpy(); gross = d["gross"].to_numpy(); turn = d["turnover"].to_numpy()
    years = len(d) * CYCLE / 252.0
    gross_annual = float(np.prod(1 + held) ** (1 / years) - np.prod(1 + (held - gross)) ** (1 / years))
    turn_mean = float(np.nanmean(turn))
    net = gross_annual - turn_mean * (252.0 / CYCLE) * COST
    after = held - np.where(np.isfinite(turn), turn * COST, 0.0)
    sr = float(after.mean() / after.std(ddof=1) * np.sqrt(252.0 / CYCLE)) if after.std(ddof=1) else 0.0
    curve = np.cumprod(1 + after)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    raw_c = max(net, 0.0) / max(2 * turn_mean, 0.30) * sr * (1 - 1.2 * dd)
    nc = min(max(raw_c / 0.6, 0.0), 1.0)
    return dict(pool_comb=0.20 * na + 0.45 * nc, pool_net=net, pool_turnover=turn_mean,
                pool_gross=gross_annual, pool_sr=sr, pool_dd=dd, share=float(np.nanmean(d["share"]))), df

def zscore(frame):
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; MV = wide["total_mv"]
del wide; gc.collect()
first_valid = C.notna().idxmax()          # first trading date per stock
age_days = pd.DataFrame(np.arange(len(C))[:, None] - C.notna().to_numpy().argmax(axis=0)[None, :],
                        index=C.index, columns=C.columns).astype("float32")   # 0 on first trading day
age_days = age_days.clip(lower=0)
log("age panel ready rss=%.2fGB" % (proc.memory_info().rss / 1e9))

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
base, base_df = pool_metrics(base_score, FUT, ELIG, SEAT_SI)
log("base net=%.5f turn=%.5f comb=%.5f gross=%.5f" % (base["pool_net"], base["pool_turnover"], base["pool_comb"], base["pool_gross"]))

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
log("cover ready rss=%.2fGB" % (proc.memory_info().rss / 1e9))

age_s = age_days.reindex(index=sched, columns=cols)
rows = []
def run(name, select=None, note=""):
    m, df = pool_metrics(base_score, FUT, ELIG, SEAT_SI, select)
    if not m:
        print("%-24s EMPTY" % name); return
    rows.append(dict(name=name, note=note, net=m["pool_net"], dnet=m["pool_net"] - base["pool_net"],
                     gross=m["pool_gross"], turn=m["pool_turnover"], dturn=m["pool_turnover"] - base["pool_turnover"],
                     sr=m["pool_sr"], dd=m["pool_dd"], share=m["share"]))
    print("%-24s select_share=%.3f | net=%.4f (dnet=%+.4f) gross=%.4f turn=%.4f sr=%.3f dd=%.3f" % (
        name, m["share"], m["pool_net"], m["pool_net"] - base["pool_net"], m["pool_gross"], m["pool_turnover"], m["pool_sr"], m["pool_dd"]), flush=True)

print()
print("== pool universe experiments (benchmark = full eligible universe) ==")
run("base", None, "all names selectable")
run("sel:cover", cover, "selectable = has op_yoy (fundamental coverage)")
run("sel:no_cover", ~cover, "selectable = no fundamentals")
run("sel:age>=60d", age_s >= 60, "listed >= 60 trading days")
run("sel:age>=250d", age_s >= 250, "listed >= 250 trading days")
run("sel:age>=500d", age_s >= 500, "listed >= 500 trading days")
run("sel:cover&age250", cover & (age_s >= 250), "both")

print()
print("== group diagnostics (forward 10d return, full eligible universe) ==")
for tag, m in (("cover", cover), ("no_cover", ~cover), ("age<250d", age_s < 250), ("age>=250d", age_s >= 250)):
    diffs, mvs, mvs2 = [], [], []
    for i, d in enumerate(sched):
        y = FUT.iloc[i].to_numpy(dtype="float64"); ok = ELIG.iloc[i].to_numpy(dtype=bool)
        g = m.iloc[i].to_numpy(dtype=bool) & ok
        if g.sum() < 50 or (~g & ok).sum() < 50:
            continue
        diffs.append(float(np.nanmean(y[g]) - np.nanmean(y[~g & ok])))
        mv = MV.iloc[C.index.get_loc(d)].to_numpy(dtype="float64") if d in C.index else None
        if mv is not None:
            mvs.append(float(np.nanmedian(mv[g]))); mvs2.append(float(np.nanmedian(mv[~g & ok])))
    print("  %-10s n=%3d  mean(grp)-mean(rest) per 10d = %+.4f  (ann~%+.1f%%)  median_mv grp=%.2fe9 rest=%.2fe9" % (
        tag, len(diffs), np.mean(diffs), np.mean(diffs) * 24 * 100, np.median(mvs) / 1e9, np.median(mvs2) / 1e9))

pd.DataFrame(rows).to_csv(OUT / "p3e_universe_mask.csv", index=False, encoding="utf-8-sig")
print()
print("written:", OUT / "p3e_universe_mask.csv")
