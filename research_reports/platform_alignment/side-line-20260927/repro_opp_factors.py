import os, sys, io, time, gc, json
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\factor\scripts")
from full_a_local_data import load_full_a_data

T0 = time.time()
def log(msg):
    print("[%7.1fs] %s" % (time.time() - T0, msg), flush=True)

try:
    import psutil
    _proc = psutil.Process()
    def rss():
        return _proc.memory_info().rss / 1e9
except Exception:
    def rss():
        return float("nan")

OUT = Path(os.environ["TEMP"]) / "side_conv"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = Path(r"D:\factor\quantlab\.quantlab\cache\research\cn_equity\tushare_factor_recheck")
PRICE = CACHE / "qfq" / "daily_batches"
CAP = CACHE / "daily_basic_full_a"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-09-07")
PANEL = OUT / "wide_panels.pkl"

if PANEL.exists():
    log("loading cached wide panels")
    wide = pd.read_pickle(PANEL)
    log("panels %s rss=%.2fGB" % (sorted(wide), rss()))
else:
    log("loading long frame rss=%.2fGB" % rss())
    frame = load_full_a_data(PRICE, CAP, START, END)
    log("frame=%s rss=%.2fGB" % (str(frame.shape), rss()))
    fields = [("close", "close_qfq"), ("open", "open_qfq"), ("volume", "volume"),
              ("amount", "amount"), ("turnover", "turnover"), ("total_mv", "total_mv"),
              ("circ_mv", "circ_mv")]
    wide = {}
    for name, col in fields:
        if col not in frame.columns:
            log("MISSING %s" % col)
            continue
        w = frame.pivot(index="date", columns="instrument", values=col)
        wide[name] = w.astype("float32").sort_index()
        wide[name].columns.name = None
        log("wide %-9s %s rss=%.2fGB" % (name, str(wide[name].shape), rss()))
    del frame
    gc.collect()
    log("released long frame rss=%.2fGB" % rss())
    pd.to_pickle(wide, PANEL)
    log("panels cached to %s" % PANEL)

C = wide["close"]
O = wide["open"]
V = wide["volume"]
A = wide["amount"]
MV = wide["total_mv"]
CMV = wide.get("circ_mv")

try:
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
    wide["close"] = C
    log("close extended -> %s" % str(C.shape))
except Exception as exc:
    log("close extension failed (%s); final period will be dropped" % exc)

cal = C.index
positions = {d: i for i, d in enumerate(cal)}

first = pd.Timestamp("2021-09-27")
last = pd.Timestamp("2026-08-26")
p0 = positions.get(first)
p1 = positions.get(last)
log("grid check pos0=%s pos1=%s diff=%s" % (p0, p1, (p1 - p0) if (p0 is not None and p1 is not None) else "NA"))
if p0 is None:
    p0 = int(cal.searchsorted(first))
if p1 is None:
    p1 = int(cal.searchsorted(last))
schedule = [cal[i] for i in range(p0, p1 + 1, 10)]
log("schedule n=%d %s .. %s" % (len(schedule), schedule[0].date(), schedule[-1].date()))

CYCLE = 10
future_rets = {}
for d in schedule:
    i = positions[d]
    if i + 1 + CYCLE >= len(cal):
        continue
    future_rets[d] = (C.iloc[i + 1 + CYCLE].to_numpy(dtype="float64") /
                      C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
log("periods with label: %d" % len(future_rets))

def rank_ic_series(values):
    out = np.full(len(schedule), np.nan)
    for k, d in enumerate(schedule):
        if d not in future_rets:
            continue
        x = values.iloc[positions[d]].to_numpy(dtype="float64")
        y = future_rets[d]
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100:
            continue
        xr = pd.Series(x[valid]).rank().to_numpy()
        yr = pd.Series(y[valid]).rank().to_numpy()
        if np.std(xr) == 0 or np.std(yr) == 0:
            continue
        out[k] = float(np.corrcoef(xr, yr)[0, 1])
    return out

def aligned_stats(series):
    s = series[np.isfinite(series)]
    if len(s) < 30:
        return dict(n=len(s), ic_mean=float("nan"), icir=float("nan"), win=float("nan"), s_i=float("nan"))
    m = float(np.mean(s))
    sd = float(np.std(s, ddof=1))
    sign = 1.0 if m >= 0 else -1.0
    a = s * sign
    win = float(np.mean(a > 0.02))
    icir = abs(m) / sd if sd > 0 else 0.0
    return dict(n=len(s), ic_mean=abs(m), icir=icir, win=win, s_i=abs(m) * icir * win)

ret1 = C.pct_change(fill_method=None).astype("float32")

factors = {}
factors["bias10"] = C / C.rolling(10, min_periods=5).mean() - 1.0
factors["bias20"] = C / C.rolling(20, min_periods=10).mean() - 1.0
factors["bias60"] = C / C.rolling(60, min_periods=30).mean() - 1.0
factors["ret10"] = C / C.shift(10) - 1.0
factors["ret20"] = C / C.shift(20) - 1.0
factors["volstd10_log"] = np.log(V).rolling(10).std()
factors["volstd10_norm"] = V.rolling(10).std() / V.rolling(10).mean()
factors["ema26_ratio"] = C / C.ewm(span=26, adjust=False).mean() - 1.0
factors["size_total_mv"] = MV
if CMV is not None:
    factors["size_circ_mv"] = CMV
factors["amihud20"] = (ret1.abs() / A).rolling(20).mean()
factors["amihud5"] = (ret1.abs() / A).rolling(5).mean()
factors["maxret20"] = ret1.rolling(20).max()
factors["amt60_log"] = np.log(A.rolling(60).mean())
factors["disthigh20"] = C / C.rolling(20).max() - 1.0
factors["disthigh60"] = C / C.rolling(60).max() - 1.0
intraday = (C - O) / O
for n in (40, 60, 90, 120):
    factors["intradayma%d" % n] = intraday.rolling(n).mean()
factors["vwap_prem60"] = ((A / V) / C - 1.0).rolling(60).mean()
factors["stdvol20_raw"] = V.rolling(20).std()
factors["stdvol20_rel5y"] = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()
factors["stdret20"] = ret1.rolling(20).std()
try:
    factors["pvcorr20"] = C.astype("float64").rolling(20).corr(V.astype("float64"))
except Exception as exc:
    log("pvcorr20 failed: %s" % exc)

TARGETS = {
    "bias10": [("4 sx", "c20-c01-rev-bias10", 0.0324, 0.204, 0.545)],
    "bias20": [("4 sx", "probe-rev-bias20", 0.0480, 0.288, 0.571)],
    "bias60": [("4 sx", "c20-c02-rev-bias60", 0.0648, 0.368, 0.601)],
    "ret10": [("4 sx", "c20-c03-rev-ret10", 0.0423, 0.261, 0.571)],
    "ret20": [("8 forests", "short-term-reversal-20d", 0.0654, 0.409, 0.597)],
    "volstd10_log": [("8 forests", "volume-vol-10d", 0.0764, 0.845, 0.697)],
    "volstd10_norm": [("8 forests", "volume-vol-10d", 0.0764, 0.845, 0.697)],
    "ema26_ratio": [("8 forests", "ema26-ratio", 0.0668, 0.402, 0.605)],
    "size_total_mv": [("8 forests", "small-cap-baseline", 0.0571, 0.290, 0.597),
                      ("5 dfkai", "comp-full-smallcap", 0.0455, 0.232, 0.588),
                      ("7 LavineX", "ex2-size", 0.0427, 0.220, 0.592)],
    "size_circ_mv": [("8 forests", "small-cap-baseline", 0.0571, 0.290, 0.597)],
    "amihud20": [("5 dfkai", "comp-full-Amihud-20d", 0.0537, 0.358, 0.608)],
    "amihud5": [("7 LavineX", "ex2-illiq5", 0.0582, 0.372, 0.610)],
    "maxret20": [("7 LavineX", "ex1-maxret20", 0.0741, 0.479, 0.643)],
    "amt60_log": [("7 LavineX", "ex3-amt60", 0.0632, 0.404, 0.604)],
    "disthigh20": [("4 sx", "c20-c04-dist-high20", 0.0073, 0.040, 0.395)],
    "disthigh60": [("4 sx", "probe-dist-high60", 0.0136, 0.073, 0.449)],
    "intradayma40": [("10 shenren", "ex_intradayma40_low", 0.0950, 0.655, 0.714)],
    "intradayma60": [("10 shenren", "full_intradayma60_low", 0.0869, 0.565, 0.731)],
    "intradayma90": [("10 shenren", "ex_intradayma90_low", 0.0828, 0.553, 0.681)],
    "intradayma120": [("10 shenren", "ex_intradayma120_low", 0.0784, 0.538, 0.655)],
    "vwap_prem60": [("10 shenren", "intradayma* alt", 0.0869, 0.565, 0.731)],
    "stdvol20_raw": [("10 shenren", "fid5y_stdvol20_5y_low", 0.0704, 0.703, 0.692)],
    "stdvol20_rel5y": [("10 shenren", "fid5y_stdvol20_5y_low", 0.0704, 0.703, 0.692)],
    "stdret20": [("10 shenren", "fid5y_stdvol20_5y_low(alt)", 0.0704, 0.703, 0.692)],
    "pvcorr20": [("7 LavineX", "ex1-pvcorr20", 0.0532, 0.580, 0.643)],
}

rows = []
lines = []
for name, values in factors.items():
    t0 = time.time()
    ics = rank_ic_series(values)
    st = aligned_stats(ics)
    rows.append(dict(candidate=name, **st))
    line = "%-18s n=%3d ic=%+.4f icir=%+.3f win=%.3f s_i=%.4f (%.1fs)" % (
        name, st["n"], st["ic_mean"], st["icir"], st["win"], st["s_i"], time.time() - t0)
    lines.append(line)
    log(line)
    del values
    gc.collect()

df = pd.DataFrame(rows)
df.to_csv(OUT / "repro_opp_factors.csv", index=False, encoding="utf-8-sig")
lines.append("")
lines.append("=== vs opponent ===")
for name, targets in TARGETS.items():
    mine = df[df["candidate"] == name]
    if mine.empty:
        continue
    r = mine.iloc[0]
    for pool, opp, oic, oicir, owin in targets:
        lines.append("%-16s mine ic=%+.4f icir=%+.3f win=%.3f | %-10s %-26s ic=%+.4f icir=%+.3f win=%.3f | d=%+.4f/%+.3f/%+.3f" % (
            name, r["ic_mean"], r["icir"], r["win"], pool, opp, oic, oicir, owin,
            r["ic_mean"] - oic, r["icir"] - oicir, r["win"] - owin))
(OUT / "repro_opp_summary.txt").write_text("\n".join(lines), encoding="utf-8")
log("DONE rss=%.2fGB" % rss())
