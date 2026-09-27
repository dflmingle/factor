# -*- coding: utf-8 -*-
"""P3d diagnostics for the fundamental-seat anomaly (+4pp dnet with s_i ~ 0).

Tests:
  1. forced sign (+/- op_yoy) -> symmetric gain means artifact
  2. median-filled op_yoy (full coverage) -> isolates the within-portfolio tilt from coverage
  3. sticky random tilt, same coverage & full coverage -> no-info sticky control
  4. per-year decomposition of the op_yoy gain
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

def ledger(score, forward, eligible):
    held, gross, turnover, valid = [], [], [], []
    previous = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64"); y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y) & eligible.loc[date].to_numpy(dtype=bool)
        if ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan); valid.append(False); continue
        x, r = f[ok], y[ok]
        instruments = score.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); gross.append(float(r[order].mean() - r.mean())); valid.append(True)
    return pd.DataFrame({"date": list(score.index), "held": held, "gross": gross, "turnover": turnover, "valid": valid})

def pool_metrics(score, forward, eligible, seat_si):
    df = ledger(score, forward, eligible)
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
    return dict(pool_comb=0.20 * na + 0.45 * nc, pool_net=net, pool_turnover=turn_mean, pool_gross=gross_annual), df

def zscore(frame):
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)

def rank_ic_stats(panel, forward, eligible):
    values = []
    for date in panel.index:
        x = panel.loc[date].to_numpy(dtype="float64"); y = forward.loc[date].to_numpy(dtype="float64")
        flag = eligible.loc[date].to_numpy(dtype=bool)
        ok = np.isfinite(x) & np.isfinite(y) & flag
        if ok.sum() < 100:
            continue
        a = pd.Series(x[ok]).rank().to_numpy(); b = pd.Series(y[ok]).rank().to_numpy()
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    s = np.asarray(values, dtype="float64")
    if s.size < 3:
        return dict(rank_ic=np.nan, s_i=np.nan)
    mean = float(s.mean()); std = float(s.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    win = float((s > 0.02).mean()) if mean >= 0 else float((s < -0.02).mean())
    return dict(rank_ic=mean, s_i=abs(mean) * abs(ir) * win)

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; MV = wide["total_mv"]
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
base, base_df = pool_metrics(base_score, FUT, ELIG, SEAT_SI)
log("base net=%.5f turn=%.5f comb=%.5f" % (base["pool_net"], base["pool_turnover"], base["pool_comb"]))

files = sorted(glob.glob(str(FIN / "*.parquet")))
fin = pd.concat([pd.read_parquet(f, columns=["ts_code", "ann_date", "end_date", "op_yoy", "roe"])
                 for f in files], ignore_index=True)
fin = fin[fin["ts_code"].isin(cols)]
fin["ann_date"] = pd.to_datetime(fin["ann_date"].astype("string"), format="%Y%m%d", errors="coerce")
fin = fin[fin["ann_date"].notna()].sort_values(["ts_code", "ann_date"]).drop_duplicates(["ts_code", "ann_date"], keep="last")
left = pd.DataFrame([(d, c) for d in sched for c in cols], columns=["ann_date", "ts_code"])
merged = pd.merge_asof(left.sort_values("ann_date"), fin.sort_values("ann_date"), on="ann_date", by="ts_code", direction="backward")
op = merged.pivot(index="ann_date", columns="ts_code", values="op_yoy").reindex(index=sched, columns=cols).astype("float32")
del left, merged, fin; gc.collect()
log("op_yoy ready rss=%.2fGB" % (proc.memory_info().rss / 1e9))

rows = []
def evaluate(name, panel, note="", force=None):
    p = panel.reindex(index=sched, columns=cols).astype("float32")
    st = rank_ic_stats(p, FUT, ELIG)
    sign = force if force is not None else (1.0 if (not np.isfinite(st["rank_ic"])) or st["rank_ic"] >= 0 else -1.0)
    oriented = p if sign > 0 else -p
    sm, sdf = pool_metrics(oriented, FUT, ELIG, {"x": 1.0})
    oz = zscore(oriented)
    keep = POOL
    score = (sum(seat_z[k] for k in keep) + oz) / (len(keep) + 1)
    si = {k: SEAT_SI[k] for k in keep}; si["candidate"] = st["s_i"]
    m, df = pool_metrics(score, FUT, ELIG, si)
    if not m:
        print("%-22s EMPTY" % name); return None
    out = dict(cand=name, note=note, sign=int(sign), rank_ic=st["rank_ic"], s_i=st["s_i"],
               dnet=m["pool_net"] - base["pool_net"], dturn=m["pool_turnover"] - base["pool_turnover"],
               pts=POINTS * (m["pool_comb"] - base["pool_comb"]))
    rows.append(out)
    print("%-22s sign=%+d ic=%+.4f s_i=%.4f turn=%.3f | dnet=%+.4f dturn=%+.4f pts=%+.0f" % (
        name, out["sign"], st["rank_ic"], st["s_i"], sm.get("pool_turnover", float("nan")),
        out["dnet"], out["dturn"], out["pts"]), flush=True)
    del p, oriented, oz; gc.collect()
    return out, df

print()
print("== 1. forced signs ==")
evaluate("op_yoy:auto", op, "auto sign")
evaluate("op_yoy:forced+", op, "long high op_yoy", force=+1)
evaluate("op_yoy:forced-", op, "long low op_yoy", force=-1)

print()
print("== 2. median-filled (full coverage, no universe change) ==")
op_fill = op.apply(lambda row: row.fillna(row.median()), axis=1).astype("float32")
evaluate("op_yoy:medfill+", op_fill, "long high", force=+1)
evaluate("op_yoy:medfill-", op_fill, "long low", force=-1)
del op_fill; gc.collect()

print()
print("== 3. sticky random controls ==")
rng = np.random.default_rng(7)
cover = np.isfinite(op.to_numpy())
sticky = rng.standard_normal(cover.shape[1]).astype("float32")
sticky_mask = np.where(cover, sticky[None, :], np.nan).astype("float32")
evaluate("sticky_rand:mask", pd.DataFrame(sticky_mask, index=sched, columns=cols), "fixed tilt, same coverage", force=+1)
sticky_full = np.repeat(sticky[None, :], len(sched), axis=0).astype("float32")
evaluate("sticky_rand:full", pd.DataFrame(sticky_full, index=sched, columns=cols), "fixed tilt, full coverage", force=+1)
del sticky_mask, sticky_full; gc.collect()

print()
print("== 4. per-year decomposition (op_yoy auto) ==")
res = evaluate("op_yoy:auto2", op, "for decomposition")
if res:
    _, df = res
    left_ = base_df[base_df["valid"]][["date", "gross", "held", "turnover"]].rename(
        columns={"gross": "g_base", "held": "h_base", "turnover": "t_base"})
    right_ = df[df["valid"]][["date", "gross", "held", "turnover"]].rename(
        columns={"gross": "g_cand", "held": "h_cand", "turnover": "t_cand"})
    mg = left_.merge(right_, on="date")
    mg["year"] = mg["date"].dt.year
    for y, g in mg.groupby("year"):
        print("  %d n=%2d  gross base=%+.4f cand=%+.4f diff=%+.4f | turn base=%.3f cand=%.3f" % (
            y, len(g), g["g_base"].mean(), g["g_cand"].mean(), (g["g_cand"] - g["g_base"]).mean(),
            g["t_base"].mean(), g["t_cand"].mean()))
    d = mg["g_cand"] - mg["g_base"]
    print("  monthly diff: mean=%+.4f median=%+.4f pos=%d/%d" % (d.mean(), d.median(), int((d > 0).sum()), len(d)))

pd.DataFrame(rows).to_csv(OUT / "p3d_fund_diag.csv", index=False, encoding="utf-8-sig")
print()
print("written:", OUT / "p3d_fund_diag.csv")
