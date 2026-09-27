import os, sys, io, time, gc
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
T0 = time.time()
def log(msg):
    print("[%7.1fs] %s" % (time.time() - T0, msg), flush=True)

OUT = Path(os.environ["TEMP"]) / "side_conv"
wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]
T = wide["turnover"]; MV = wide["total_mv"]; CMV = wide.get("circ_mv")

tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"
base = C.iloc[-1]
d0 = pd.read_parquet(tmp_root / "daily" / "daily_20260907.parquet")
a0 = pd.read_parquet(tmp_root / "adj" / "adj_20260907.parquet")
d0 = d0.copy(); d0["instrument"] = d0["ts_code"].astype(str)
a0 = a0.copy(); a0["instrument"] = a0["ts_code"].astype(str)
raw0 = d0.set_index("instrument")["close"] * a0.set_index("instrument")["adj_factor"]
scale = base / raw0.reindex(base.index)
ext_rows = []
for ds in ["20260908", "20260909", "20260910"]:
    dd = pd.read_parquet(tmp_root / "daily" / ("daily_%s.parquet" % ds))
    aa = pd.read_parquet(tmp_root / "adj" / ("adj_%s.parquet" % ds))
    dd = dd.copy(); dd["instrument"] = dd["ts_code"].astype(str)
    aa = aa.copy(); aa["instrument"] = aa["ts_code"].astype(str)
    rawk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
    row = rawk.reindex(base.index) * scale
    row.name = pd.Timestamp(ds)
    ext_rows.append(row)
C = pd.concat([C, pd.DataFrame(ext_rows)], axis=0).astype("float32")
cal = C.index
positions = {d: i for i, d in enumerate(cal)}
log("panels loaded, close %s" % str(C.shape))

ret1 = C.pct_change(fill_method=None).astype("float32")
F = {}
F["bias10"] = C / C.rolling(10, min_periods=5).mean() - 1.0
F["bias20"] = C / C.rolling(20, min_periods=10).mean() - 1.0
F["bias60"] = C / C.rolling(60, min_periods=30).mean() - 1.0
F["ret10"] = C / C.shift(10) - 1.0
F["ret20"] = C / C.shift(20) - 1.0
F["disthigh20"] = C / C.rolling(20).max() - 1.0
F["disthigh60"] = C / C.rolling(60).max() - 1.0
F["maxret20"] = ret1.rolling(20).max()
F["amihud20"] = (ret1.abs() / A).rolling(20).mean()
F["amihud5"] = (ret1.abs() / A).rolling(5).mean()
F["amt60_log"] = np.log(A.rolling(60).mean())
F["size_total_mv"] = MV
F["size_circ_mv"] = CMV
F["pvcorr20"] = C.astype("float64").rolling(20).corr(V.astype("float64"))
F["volstd10_log"] = np.log(V).rolling(10).std()
F["volstd10_norm"] = V.rolling(10).std() / V.rolling(10).mean()
F["volstd10_ret"] = ret1.rolling(10).std()
F["volstd10_turn"] = T.rolling(10).std() / T.rolling(10).mean()
F["ema26_ratio"] = C / C.ewm(span=26, adjust=False).mean() - 1.0
intraday = (C - O) / O
for n in (40, 60, 90, 120):
    F["intradayma%d" % n] = intraday.rolling(n).mean()
F["vwap_prem60"] = ((A / V) / C - 1.0).rolling(60).mean()
F["stdvol20_raw"] = V.rolling(20).std()
F["stdvol20_rel5y"] = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()
F["stdvol20_normV"] = V.rolling(20).std() / V.rolling(20).mean()
F["stdret20"] = ret1.rolling(20).std()

GRIDS = {
    "G4_sx": (pd.Timestamp("2021-09-03"), 4, 301),
    "G5_lavine": (pd.Timestamp("2021-09-27"), 5, 241),
    "G5_dfkai": (pd.Timestamp("2021-09-07"), 5, 240),
    "G10_forests": (pd.Timestamp("2021-09-15"), 10, 119),
    "G10_shenren": (pd.Timestamp("2021-09-22"), 10, 120),
}
TARGETS = {
    "G4_sx": [("bias10", "c20-c01-rev-bias10", 0.0324, 0.204, 0.545, 301),
              ("bias20", "probe-rev-bias20", 0.0480, 0.288, 0.571, 301),
              ("bias60", "c20-c02-rev-bias60", 0.0648, 0.368, 0.601, 301),
              ("ret10", "c20-c03-rev-ret10", 0.0423, 0.261, 0.571, 301),
              ("disthigh20", "c20-c04-dist-high20", 0.0073, 0.040, 0.395, 301),
              ("disthigh60", "probe-dist-high60", 0.0136, 0.073, 0.449, 301)],
    "G5_lavine": [("maxret20", "ex1-maxret20", 0.0741, 0.479, 0.643, 241),
                  ("pvcorr20", "ex1-pvcorr20", 0.0532, 0.580, 0.643, 241),
                  ("amt60_log", "ex3-amt60", 0.0632, 0.404, 0.604, 240),
                  ("size_total_mv", "ex2-size", 0.0427, 0.220, 0.592, 240),
                  ("amihud5", "ex2-illiq5", 0.0582, 0.372, 0.610, 241),
                  ("amihud20", "ex2-illiq20n", 0.0514, 0.279, 0.596, 241)],
    "G5_dfkai": [("amihud20", "comp-full-Amihud-20d", 0.0537, 0.358, 0.608, 240),
                 ("size_total_mv", "comp-full-smallcap", 0.0455, 0.232, 0.588, 240)],
    "G10_forests": [("volstd10_log", "volume-vol-10d", 0.0764, 0.845, 0.697, 119),
                    ("volstd10_norm", "volume-vol-10d", 0.0764, 0.845, 0.697, 119),
                    ("volstd10_ret", "volume-vol-10d", 0.0764, 0.845, 0.697, 119),
                    ("volstd10_turn", "volume-vol-10d", 0.0764, 0.845, 0.697, 119),
                    ("ema26_ratio", "ema26-ratio", 0.0668, 0.402, 0.605, 119),
                    ("ret20", "short-term-reversal-20d", 0.0654, 0.409, 0.597, 119),
                    ("size_total_mv", "small-cap-baseline", 0.0571, 0.290, 0.597, 119)],
    "G10_shenren": [("intradayma40", "ex_intradayma40_low", 0.0950, 0.655, 0.714, 119),
                    ("intradayma60", "full_intradayma60_low", 0.0869, 0.565, 0.731, 119),
                    ("intradayma90", "ex_intradayma90_low", 0.0828, 0.553, 0.681, 119),
                    ("intradayma120", "ex_intradayma120_low", 0.0784, 0.538, 0.655, 119),
                    ("vwap_prem60", "intradayma-alt", 0.0869, 0.565, 0.731, 119),
                    ("stdvol20_raw", "fid5y_stdvol20_5y_low", 0.0704, 0.703, 0.692, 120),
                    ("stdvol20_rel5y", "fid5y_stdvol20_5y_low", 0.0704, 0.703, 0.692, 120),
                    ("stdvol20_normV", "fid5y_stdvol20_5y_low", 0.0704, 0.703, 0.692, 120),
                    ("stdret20", "fid5y_stdvol20_5y_low-alt", 0.0704, 0.703, 0.692, 120)],
}

lines = []
rows_out = []
for gname, (start, step, count) in GRIDS.items():
    p0 = positions.get(start)
    if p0 is None:
        p0 = int(cal.searchsorted(start))
    schedule = [cal[i] for i in range(p0, min(p0 + step * count, len(cal)), step)]
    fut = {}
    for d in schedule:
        i = positions[d]
        if i + 1 + step >= len(cal):
            continue
        fut[d] = (C.iloc[i + 1 + step].to_numpy(dtype="float64") /
                  C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
    lines.append("")
    lines.append("### %s start=%s step=%d requested=%d usable=%d (%s..%s)" % (
        gname, start.date(), step, count, len(fut), schedule[0].date(), schedule[-1].date()))
    for fname, opp, oic, oicir, owin, on in TARGETS.get(gname, []):
        values = F[fname]
        ics = np.full(len(schedule), np.nan)
        for k, d in enumerate(schedule):
            if d not in fut:
                continue
            x = values.iloc[positions[d]].to_numpy(dtype="float64")
            y = fut[d]
            valid = np.isfinite(x) & np.isfinite(y)
            if valid.sum() < 100:
                continue
            xr = pd.Series(x[valid]).rank().to_numpy()
            yr = pd.Series(y[valid]).rank().to_numpy()
            if np.std(xr) == 0 or np.std(yr) == 0:
                continue
            ics[k] = float(np.corrcoef(xr, yr)[0, 1])
        s = ics[np.isfinite(ics)]
        if len(s) < 30:
            lines.append("%-16s n=%d (too few)" % (fname, len(s)))
            continue
        m = float(np.mean(s)); sd = float(np.std(s, ddof=1))
        sign = 1.0 if m >= 0 else -1.0
        a = s * sign
        win = float(np.mean(a > 0.02))
        icir = abs(m) / sd
        si = abs(m) * icir * win
        line = "%-16s mine n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f | %-24s n=%d ic=%+.4f icir=%+.3f win=%.3f | d=%+.4f/%+.3f/%+.3f" % (
            fname, len(s), abs(m), icir, win, si, opp, on, oic, oicir, owin,
            abs(m) - oic, icir - oicir, win - owin)
        lines.append(line)
        log(line)
        rows_out.append(dict(grid=gname, candidate=fname, target=opp, n=len(s), ic_mean=abs(m), icir=icir, win=win, s_i=si,
                             opp_ic=oic, opp_icir=oicir, opp_win=owin))
pd.DataFrame(rows_out).to_csv(OUT / "repro_opp_cycles.csv", index=False, encoding="utf-8-sig")
(OUT / "repro_opp_cycles.txt").write_text("\n".join(lines), encoding="utf-8")
log("DONE")
