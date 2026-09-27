# -*- coding: utf-8 -*-
"""P3g: can the delisting/no-coverage exclusion be expressed as a factor VALUE
(platform-implementable) instead of a NaN mask? Compare oracle select-mask vs
formula blocker seats."""
import os, sys, io, time, gc, pickle, glob
from pathlib import Path
import numpy as np
import pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(m): print("[%7.1fs] %s" % (time.time() - T0, m), flush=True)
ROOT = Path(r"D:\factor"); OUT = Path(os.environ["TEMP"]) / "side_conv"
SEATS = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
FIN = ROOT / "quantlab/.quantlab/cache/research/cn_equity/financial/fina_indicator"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817, "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692, "book_to_market_lf_plus_impact": 0.01540}
CYCLE, COST, POINTS = 10, 0.006, 44000.0

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
        held.append(float(y[sel][order].mean())); gross.append(float(y[sel][order].mean() - y[ok].mean()))
        share.append(float(sel.sum() / ok.sum())); valid.append(True)
    return pd.DataFrame({"date": list(score.index), "held": held, "gross": gross, "turnover": turnover,
                         "share": share, "valid": valid})

def metrics(score, forward, eligible, seat_si, select=None):
    df = ledger(score, forward, eligible, select)
    d = df[df["valid"]].copy()
    if len(d) < 3:
        return {}, df
    held = d["held"].to_numpy(); gross = d["gross"].to_numpy(); turn = d["turnover"].to_numpy()
    years = len(d) * CYCLE / 252.0
    ga = float(np.prod(1 + held) ** (1 / years) - np.prod(1 + (held - gross)) ** (1 / years))
    tm = float(np.nanmean(turn)); net = ga - tm * (252.0 / CYCLE) * COST
    after = held - np.where(np.isfinite(turn), turn * COST, 0.0)
    sr = float(after.mean() / after.std(ddof=1) * np.sqrt(252.0 / CYCLE)) if after.std(ddof=1) else 0.0
    curve = np.cumprod(1 + after); dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    nc = min(max(max(net, 0.0) / max(2 * tm, 0.30) * sr * (1 - 1.2 * dd) / 0.6, 0.0), 1.0)
    return dict(net=net, gross=ga, turn=tm, sr=sr, dd=dd, comb=0.20 * na + 0.45 * nc, share=float(np.nanmean(d["share"]))), df

def zscore(f):
    return f.sub(f.mean(axis=1), axis=0).div(f.std(axis=1, ddof=0).replace(0, np.nan), axis=0)

def rank_ic_stats(panel, forward, eligible):
    vals = []
    for d in panel.index:
        x = panel.loc[d].to_numpy(dtype="float64"); y = forward.loc[d].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y) & eligible.loc[d].to_numpy(dtype=bool)
        if ok.sum() < 100: continue
        a = pd.Series(x[ok]).rank().to_numpy(); b = pd.Series(y[ok]).rank().to_numpy()
        if a.std() == 0 or b.std() == 0: continue
        vals.append(float(np.corrcoef(a, b)[0, 1]))
    s = np.asarray(vals)
    if s.size < 3: return np.nan, np.nan
    m = float(s.mean()); sd = float(s.std(ddof=1)); ir = m / sd if sd else 0.0
    win = float((s > 0.02).mean()) if m >= 0 else float((s < -0.02).mean())
    return m, abs(m) * abs(ir) * win

wide = pd.read_pickle(OUT / "wide_panels.pkl"); del wide
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
base, base_df = metrics(base_score, FUT, ELIG, SEAT_SI)
log("base net=%.4f gross=%.4f turn=%.4f sr=%.3f dd=%.3f" % (base["net"], base["gross"], base["turn"], base["sr"], base["dd"]))

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
log("cover ready")

rows = []
def report(name, m, note=""):
    rows.append(dict(name=name, note=note, net=m["net"], dnet=m["net"] - base["net"], gross=m["gross"],
                     turn=m["turn"], sr=m["sr"], dd=m["dd"], comb=m["comb"], dcomb_pts=POINTS * (m["comb"] - base["comb"])))
    print("%-26s select=%.3f | net=%.4f (%+.4f) gross=%.4f turn=%.4f sr=%.3f dd=%.3f | comb_pts=%+.0f" % (
        name, m["share"], m["net"], m["net"] - base["net"], m["gross"], m["turn"], m["sr"], m["dd"], POINTS * (m["comb"] - base["comb"])), flush=True)

print()
print("== oracle (select mask) ==")
m, _ = metrics(base_score, FUT, ELIG, SEAT_SI, cover); report("ORACLE select=cover", m, "no-uncovered-selection")

print()
print("== formula blocker seats (0 for covered, k for uncovered) ==")
for k in (-2.0, -6.0, -1e6):
    blk = np.where(cover.to_numpy(), 0.0, k).astype("float32")
    blk_panel = pd.DataFrame(blk, index=sched, columns=cols)
    ic, si = rank_ic_stats(blk_panel, FUT, ELIG)
    oz = zscore(blk_panel)
    keep = POOL
    score = (sum(seat_z[x] for x in keep) + oz) / (len(keep) + 1)
    si_map = {x: SEAT_SI[x] for x in keep}; si_map["blocker"] = si
    mm, _ = metrics(score, FUT, ELIG, si_map)
    report("blocker k=%.0f (ic=%+.4f)" % (k, ic), mm, "formula version")

print()
print("== blocker on top of the best existing add-seat (t10 family check) ==")
for k in (-6.0,):
    blk = np.where(cover.to_numpy(), 0.0, k).astype("float32")
    blk_panel = pd.DataFrame(blk, index=sched, columns=cols)
    oz = zscore(blk_panel)
    keep = POOL
    score = (sum(seat_z[x] for x in keep) + oz) / (len(keep) + 1)
    si_map = {x: SEAT_SI[x] for x in keep}; si_map["blocker"] = 0.0
    mm, _ = metrics(score, FUT, ELIG, si_map)
    report("blocker k=%.0f (si=0)" % k, mm, "conservative NA")

pd.DataFrame(rows).to_csv(OUT / "p3g_blocker_seat.csv", index=False, encoding="utf-8-sig")
print()
print("written:", OUT / "p3g_blocker_seat.csv")
