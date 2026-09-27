# -*- coding: utf-8 -*-
"""P3 side experiment (zero platform compute, memory-lean).

A) rank-residual orthogonalization: raw -> orth(pool) -> orth(pool+size)  [dual]
B) conditional reversal: rev20 x {lowT5, deep-DD20, deep-DD60, dual-DD, stack, hard-DD60}

Reuses ab-batch-20260925 seat panels + side_conv/wide_panels.pkl, same ledger/points
machinery as gate6_screen.py (calibrated on SIDE-NB60T5 / SIDE-IM40 platform runs).
Only close / turnover / total_mv are kept; rank ops run on the 120-date grid.
"""
import os, sys, io, time, gc, pickle
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
    print("%-24s sign=%+d s_i=%.4f turn=%.3f | add6 dnet=%+.3f dturn=%+.3f pts=%+.0f | swap dnet=%+.3f | corrMax=%.2f(%s) %s" % (
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


# ---------- A. dual orthogonalization ----------
print()
print("== A. rank-residual orthogonalization (vs pool / pool+size) ==")
ret1 = C.pct_change(fill_method=None).astype("float32")
size_neg = (-np.log(MV.clip(lower=1.0))).astype("float32")
negdev20 = (-(C / C.rolling(20, min_periods=10).mean() - 1.0)).astype("float32")
maxret20 = ret1.rolling(20).max().astype("float32")
del ret1; gc.collect()

base_rank = sched_rank(base_score)
size_rank = sched_rank(-MV)


def build_ndt5():
    rv = negdev20.reindex(index=sched, columns=cols).astype("float32")
    tv = T.rolling(5).mean().reindex(index=sched, columns=cols).astype("float32")
    v = (rv.rank(axis=1, pct=True) * (1.0 - tv.rank(axis=1, pct=True))).astype("float32")
    del rv, tv; gc.collect()
    return v


for name, panel in (("rev20", negdev20), ("maxret20", maxret20), ("sizeNegLog", size_neg), ("nb20xT5", build_ndt5())):
    rr = sched_rank(panel)
    evaluate(name + ":raw", rr, "rank of raw")
    o1 = orth_residual(rr, [base_rank])
    evaluate(name + ":orthP", o1, "resid vs pool")
    o2 = orth_residual(rr, [base_rank, size_rank])
    evaluate(name + ":orthPS", o2, "resid vs pool+size")
    del rr, o1, o2; gc.collect()

# ---------- B. conditional reversal ----------
print()
print("== B. conditional reversal ==")
dd20 = (C / C.rolling(20).max() - 1.0).astype("float32")
dd60 = (C / C.rolling(60).max() - 1.0).astype("float32")


def cond(panel, invert=False):
    p = panel.reindex(index=sched, columns=cols).astype("float32")
    r = p.rank(axis=1, pct=True).astype("float32")
    return (1.0 - r) if invert else r


rev_s = negdev20.reindex(index=sched, columns=cols).astype("float32")
lowt5 = cond(T.rolling(5).mean(), invert=True)
deep20 = cond(dd20, invert=True)
deep60 = cond(dd60, invert=True)
evaluate("rev20", rev_s, "base reversal (20d neg dev)")
evaluate("rev20_x_lowT5", (rev_s * lowt5).astype("float32"), "x low-turnover gate")
evaluate("rev20_x_deep20", (rev_s * deep20).astype("float32"), "x deep-DD20")
evaluate("rev20_x_deep60", (rev_s * deep60).astype("float32"), "x deep-DD60")
evaluate("rev20_x_deep20_deep60", (rev_s * deep20 * deep60).astype("float32"), "dual-window DD")
evaluate("rev20_x_stack", (rev_s * deep20 * deep60 * lowt5).astype("float32"), "DD x2 + lowT")
evaluate("rev20_x_hard60", (rev_s.where(dd60.reindex(index=sched, columns=cols) < -0.10, 0.0)).astype("float32"), "hard DD60<-10%")

df = pd.DataFrame(rows)
df.to_csv(OUT / "p3_orth_cond.csv", index=False, encoding="utf-8-sig")
print()
print("written:", OUT / "p3_orth_cond.csv", " rss=%.2fGB" % (proc.memory_info().rss / 1e9))
