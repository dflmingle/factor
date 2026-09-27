# -*- coding: utf-8 -*-
"""P3b: (A) partial-orthogonalization lambda sweep, (B) fundamental-conditioned reversal.

Zero platform compute. Same harness as p3_orth_cond.py / gate6_screen.py.
Fundamental PIT panel: D:\factor\quantlab\.quantlab\cache\research\cn_equity\financial\fina_indicator
(ann_date = availability date; op_yoy / roe / grossprofit_margin).
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

ROOT = Path(r"D:\factor")
OUT = Path(os.environ["TEMP"]) / "side_conv"
SEATS = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
FIN = ROOT / "quantlab/.quantlab/cache/research/cn_equity/financial/fina_indicator"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692, "book_to_market_lf_plus_impact": 0.01540}
CYCLE, COST, POINTS = 10, 0.006, 44000.0
WEAKEST = "size_only"

mem("start", 2.2)
proc = psutil.Process()


def ledger(score, forward, eligible):
    held, gross, turnover, valid = [], [], [], []
    previous = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y) & eligible.loc[date].to_numpy(dtype=bool)
        if ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan); valid.append(False); continue
        x, r = f[ok], y[ok]
        instruments = score.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); gross.append(float(r[order].mean() - r.mean()))
        valid.append(True)
    return pd.DataFrame({"date": list(score.index), "held": held, "gross": gross,
                         "turnover": turnover, "valid": valid})


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
    return dict(pool_na=na, pool_nc=nc, pool_comb=0.20 * na + 0.45 * nc, pool_net=net,
                pool_gross=gross_annual, pool_turnover=turn_mean, pool_sr=sr, pool_dd=dd), df


def _block_nc(group):
    held = group["held"].to_numpy(); turn = group["turnover"].to_numpy()
    rex = float(np.prod(1 + held) ** (252.0 / CYCLE / len(group)) - 1)
    after = held - np.where(np.isfinite(turn), turn * COST, 0.0)
    sr = float(after.mean() / after.std(ddof=1) * np.sqrt(252.0 / CYCLE)) if after.std(ddof=1) else 0.0
    curve = np.cumprod(1 + after)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    threshold = float(np.nanmean(turn)) * 2
    return min(max(max(rex, 0.0) / max(threshold, 0.30) * sr * (1 - 1.2 * dd) / 0.6, 0.0), 1.0)


def monthly_dcomb(base_df, cand_df, min_periods=2):
    def grouped(frame):
        data = frame[frame["valid"]].copy()
        data["_key"] = data["date"].dt.to_period("M").astype(str)
        return {str(k): g for k, g in data.groupby("_key")}
    base_groups, cand_groups = grouped(base_df), grouped(cand_df)
    out = []
    for key in sorted(set(base_groups) & set(cand_groups)):
        left, right = base_groups[key], cand_groups[key]
        if len(left) < min_periods or len(right) < min_periods:
            continue
        out.append(0.45 * (_block_nc(right) - _block_nc(left)))
    return out


def zscore(frame):
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def daily_rank_corr(left, right):
    values = []
    for date in left.index:
        x = left.loc[date].to_numpy(dtype="float64")
        y = right.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        a, b = pd.Series(x[ok]).rank(), pd.Series(y[ok]).rank()
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(values)) if values else float("nan")


def rank_ic_stats(panel, forward, eligible):
    values = []
    for date in panel.index:
        x = panel.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
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
        return dict(n=int(s.size), rank_ic=np.nan, ic_ir=np.nan, ic_win=np.nan, s_i=np.nan)
    mean = float(s.mean()); std = float(s.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    win = float((s > 0.02).mean()) if mean >= 0 else float((s < -0.02).mean())
    return dict(n=int(s.size), rank_ic=mean, ic_ir=ir, ic_win=win, s_i=abs(mean) * abs(ir) * win)


# ---------- load ----------
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; T = wide["turnover"]; MV = wide["total_mv"]
del wide; gc.collect()
log("wide loaded %s rss=%.2fGB" % (str(C.shape), proc.memory_info().rss / 1e9))

payload = pickle.load(SEATS.open("rb"))
sched = [pd.Timestamp(d) for d in payload["dates"]]
FUT = payload["returns"].pivot(index="date", columns="instrument", values="forward_return").reindex(index=sched)
sf = payload["signal_frame"].reset_index(drop=True)
sc = payload["scores"].reset_index(drop=True)
seat_frame = pd.concat([sf, sc], axis=1)
seat_frame["date"] = pd.to_datetime(seat_frame["date"])
seat_frame = seat_frame[seat_frame["date"].isin(sched)]
cols = FUT.columns
seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k).reindex(index=sched, columns=cols) for k in POOL}
del payload, sf, sc, seat_frame; gc.collect()
FUT = FUT.astype("float32")
ELIG = FUT.notna()
log("seats ready %s rss=%.2fGB" % (str(FUT.shape), proc.memory_info().rss / 1e9))

seat_z = {k: zscore(p) for k, p in seat_panels.items()}
base_score = sum(seat_z.values()) / len(POOL)
base, base_df = pool_metrics(base_score, FUT, ELIG, SEAT_SI)
log("base: " + str({k: round(v, 5) for k, v in base.items()}))

rows = []


def evaluate(name, panel, note=""):
    mem("  eval %s" % name, 1.2)
    p = panel.reindex(index=sched, columns=cols).astype("float32")
    st = rank_ic_stats(p, FUT, ELIG)
    sign = 1.0 if (not np.isfinite(st["rank_ic"])) or st["rank_ic"] >= 0 else -1.0
    oriented = p if sign > 0 else -p
    sm, sdf = pool_metrics(oriented, FUT, ELIG, {"x": 1.0})
    corrs = {k: daily_rank_corr(oriented, seat_panels[k]) for k in POOL}
    cmax = max(corrs, key=lambda k: abs(corrs[k]))
    oz = zscore(oriented)
    out = dict(cand=name, note=note, sign=int(sign), n=st["n"], rank_ic=st["rank_ic"], ic_ir=st["ic_ir"],
               win=st["ic_win"], s_i=st["s_i"], seat_turn=sm.get("pool_turnover"), seat_net=sm.get("pool_net"),
               corr_max=float(np.nanmax(np.abs(list(corrs.values())))), corr_max_seat=cmax)
    for tag, keep in (("add6", POOL), ("swapSIZE", [k for k in POOL if k != WEAKEST])):
        score = (sum(seat_z[k] for k in keep) + oz) / (len(keep) + 1)
        si = {k: SEAT_SI[k] for k in keep}; si["candidate"] = st["s_i"]
        m, df = pool_metrics(score, FUT, ELIG, si)
        out[tag + "_net"] = m["pool_net"]; out[tag + "_turn"] = m["pool_turnover"]
        out[tag + "_comb"] = m["pool_comb"]
        out[tag + "_dnet"] = m["pool_net"] - base["pool_net"]
        out[tag + "_dturn"] = m["pool_turnover"] - base["pool_turnover"]
        out[tag + "_dpoints"] = POINTS * (m["pool_comb"] - base["pool_comb"])
        if tag == "add6":
            md = monthly_dcomb(base_df, df)
            out["dcomb_month_mean"] = float(np.mean(md)) if md else float("nan")
            out["dcomb_pos_share"] = float(np.mean([x > 0 for x in md])) if md else float("nan")
    out["gate"] = "PASS" if (out["seat_turn"] is not None and out["seat_turn"] <= 0.20 and out["add6_dnet"] >= 0) else "fail"
    rows.append(out)
    print("%-26s sign=%+d s_i=%.4f turn=%.3f | add6 dnet=%+.3f dturn=%+.3f pts=%+.0f | swap dnet=%+.3f | corrMax=%.2f(%s) %s" % (
        name, out["sign"], st["s_i"], out["seat_turn"], out["add6_dnet"], out["add6_dturn"], out["add6_dpoints"],
        out["swapSIZE_dnet"], out["corr_max"], cmax, out["gate"]), flush=True)
    del p, oriented, oz; gc.collect()
    return out


def sched_rank(panel):
    p = panel.reindex(index=sched, columns=cols).astype("float32")
    return p.rank(axis=1, pct=True).astype("float32")


def orth_residual(raw_rank, ref_ranks):
    Y = raw_rank.to_numpy(dtype="float64")
    Xs = [r.to_numpy(dtype="float64") for r in ref_ranks]
    out = np.full(Y.shape, np.nan, dtype="float32")
    for i in range(Y.shape[0]):
        y = Y[i]
        m = np.isfinite(y)
        for x in Xs:
            m &= np.isfinite(x[i])
        n = int(m.sum())
        if n < 200:
            continue
        A = np.empty((n, len(Xs) + 1))
        A[:, 0] = 1.0
        for j, x in enumerate(Xs):
            A[:, j + 1] = x[i][m]
        beta, *_ = np.linalg.lstsq(A, y[m], rcond=None)
        out[i, m] = (y[m] - A @ beta).astype("float32")
    return pd.DataFrame(out, index=raw_rank.index, columns=raw_rank.columns)


# ---------- fundamental PIT panel ----------
print()
print("== building fundamental PIT panel ==")
files = sorted(glob.glob(str(FIN / "*.parquet")))
fin = pd.concat([pd.read_parquet(f, columns=["ts_code", "ann_date", "end_date", "op_yoy", "roe", "grossprofit_margin"])
                 for f in files], ignore_index=True)
fin = fin[fin["ts_code"].isin(cols)]
fin["ann_date"] = pd.to_datetime(fin["ann_date"].astype("string"), format="%Y%m%d", errors="coerce")
fin = fin[fin["ann_date"].notna()]
fin = fin.sort_values(["ts_code", "ann_date"]).drop_duplicates(["ts_code", "ann_date"], keep="last")
log("fin rows=%d stocks=%d ann %s..%s rss=%.2fGB" % (len(fin), fin["ts_code"].nunique(),
    fin["ann_date"].min().date(), fin["ann_date"].max().date(), proc.memory_info().rss / 1e9))

left = pd.DataFrame([(d, c) for d in sched for c in cols], columns=["ann_date", "ts_code"])
merged = pd.merge_asof(left.sort_values("ann_date"), fin.sort_values("ann_date"),
                       on="ann_date", by="ts_code", direction="backward")
fund = {}
for field in ["op_yoy", "roe", "grossprofit_margin"]:
    fund[field] = merged.pivot(index="ann_date", columns="ts_code", values=field).reindex(index=sched, columns=cols).astype("float32")
del left, merged, fin; gc.collect()
cov = {k: float(np.isfinite(v.to_numpy()).mean()) for k, v in fund.items()}
log("fund panels ready coverage=%s rss=%.2fGB" % (str({k: round(v, 3) for k, v in cov.items()}), proc.memory_info().rss / 1e9))

# ---------- A. lambda sweep ----------
print()
print("== A. partial orthogonalization (lambda) vs pool rank ==")
ret1 = C.pct_change(fill_method=None).astype("float32")
maxret20 = ret1.rolling(20).max().astype("float32")
negdev20 = (-(C / C.rolling(20, min_periods=10).mean() - 1.0)).astype("float32")
del ret1; gc.collect()
base_rank = sched_rank(base_score)
size_rank = sched_rank(-MV)

T5s = T.rolling(5).mean().reindex(index=sched, columns=cols).astype("float32")
nb20xT5 = (negdev20.reindex(index=sched, columns=cols).astype("float32").rank(axis=1, pct=True) * (1.0 - T5s.rank(axis=1, pct=True))).astype("float32")
del T5s; gc.collect()

for name, panel in (("maxret20", maxret20), ("nb20xT5", nb20xT5)):
    rr = sched_rank(panel)
    o1 = orth_residual(rr, [base_rank])
    for lam in (0.0, 0.25, 0.5, 0.75, 1.0):
        blend = (rr + lam * (o1 - rr)).astype("float32")
        evaluate("%s:lam%.2f" % (name, lam), blend, "lambda=%s" % lam)
        del blend; gc.collect()
    del rr, o1; gc.collect()

# ---------- B. fundamentals ----------
print()
print("== B. fundamental seats / fundamental-conditioned reversal ==")
rev_s = negdev20.reindex(index=sched, columns=cols).astype("float32")
op_r = fund["op_yoy"].rank(axis=1, pct=True).astype("float32")
roe_r = fund["roe"].rank(axis=1, pct=True).astype("float32")
gpm_r = fund["grossprofit_margin"].rank(axis=1, pct=True).astype("float32")
evaluate("op_yoy", fund["op_yoy"], "operating-profit YoY (PIT)")
evaluate("roe", fund["roe"], "ROE (PIT)")
evaluate("gpm", fund["grossprofit_margin"], "gross margin (PIT)")
evaluate("rev20_x_basic", (rev_s * gpm_r).astype("float32"), "reversal x quality (MATRIX-style)")
evaluate("rev20_x_basic_op", (rev_s * op_r).astype("float32"), "reversal x op-profit improvement")
evaluate("rev20_x_basic_roe", (rev_s * roe_r).astype("float32"), "reversal x ROE")

df = pd.DataFrame(rows)
df.to_csv(OUT / "p3b_orth_lambda_fund.csv", index=False, encoding="utf-8-sig")
print()
print("written:", OUT / "p3b_orth_lambda_fund.csv", " rss=%.2fGB" % (proc.memory_info().rss / 1e9))
