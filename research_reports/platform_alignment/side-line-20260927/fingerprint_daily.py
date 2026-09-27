import os, sys, io, csv
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(os.environ["TEMP"]) / "side_conv"
tmp_root = Path(os.environ["TEMP"]) / "pandaai_sept25"

wide = pd.read_pickle(OUT / "wide_panels.pkl")
C = wide["close"]; O = wide["open"]; V = wide["volume"]; A = wide["amount"]; T = wide["turnover"]; MV = wide["total_mv"]

base = C.iloc[-1]
d0 = pd.read_parquet(tmp_root / "daily" / "daily_20260907.parquet").copy()
a0 = pd.read_parquet(tmp_root / "adj" / "adj_20260907.parquet").copy()
d0["instrument"] = d0["ts_code"].astype(str); a0["instrument"] = a0["ts_code"].astype(str)
raw0 = d0.set_index("instrument")["close"] * a0.set_index("instrument")["adj_factor"]
scale = base / raw0.reindex(base.index)
rows = []
for ds in ["20260908","20260909","20260910","20260911","20260914","20260915","20260916","20260917","20260918","20260921","20260922","20260923","20260924"]:
    dd = pd.read_parquet(tmp_root / "daily" / ("daily_%s.parquet" % ds)).copy()
    aa = pd.read_parquet(tmp_root / "adj" / ("adj_%s.parquet" % ds)).copy()
    dd["instrument"] = dd["ts_code"].astype(str); aa["instrument"] = aa["ts_code"].astype(str)
    rawk = dd.set_index("instrument")["close"] * aa.set_index("instrument")["adj_factor"]
    row = rawk.reindex(base.index) * scale; row.name = pd.Timestamp(ds)
    rows.append(row)
C = pd.concat([C, pd.DataFrame(rows)], axis=0).astype("float32")
cal = C.index; positions = {d: i for i, d in enumerate(cal)}
ret1 = C.pct_change(fill_method=None).astype("float32")

def day_stats(values, ds, step):
    d = pd.Timestamp(str(ds))
    if d not in positions:
        return None
    i = positions[d]
    if i + 1 + step >= len(cal):
        return None
    x = values.iloc[i].to_numpy(dtype="float64")
    y = (C.iloc[i + 1 + step].to_numpy(dtype="float64") / C.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 100:
        return None
    xr = pd.Series(x[valid]).rank().to_numpy(); yr = pd.Series(y[valid]).rank().to_numpy()
    return float(np.corrcoef(xr, yr)[0, 1]), float(np.corrcoef(x[valid], y[valid])[0, 1])

def read_feed1(p):
    raw = open(p, encoding="utf-8").read().strip()
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    raw = raw.replace('\\"', '"').replace('\\n', '\n')
    out = {}
    for r in csv.DictReader(io.StringIO(raw)):
        out.setdefault(r["factor_name"], []).append(
            (r["trade_date"], r["display_name"], int(r["cycle_days"]), r["period_rank_ic"], r["ic"]))
    return out

def read_feed2(p):
    out = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        out.setdefault(r["name"], []).append(
            (r["holding_date"], r["player"], int(r["cycle"]), r["rank_ic"], r["ic"]))
    return out

feed = {}
for k, v in read_feed1(r"D:\factor\research_reports\platform_alignment\daily-factors-feed-20260923.csv").items():
    feed.setdefault(k, []).extend(v)
for k, v in read_feed2(r"D:\factor\research_reports\platform_alignment\daily-factor-feed-20260923\daily_factors_20260917_18.csv").items():
    feed.setdefault(k, []).extend(v)

F = {}
F["ema26_ratio"] = C / C.ewm(span=26, adjust=False).mean() - 1.0
F["short-term-reversal-20d"] = C / C.shift(20) - 1.0
F["small-cap-baseline"] = MV
F["intradayma40"] = ((C - O) / O).rolling(40).mean()
F["intradayma60"] = ((C - O) / O).rolling(60).mean()
F["intradayma90"] = ((C - O) / O).rolling(90).mean()
F["intradayma120"] = ((C - O) / O).rolling(120).mean()
F["bias60"] = C / C.rolling(60, min_periods=30).mean() - 1.0
F["bias20"] = C / C.rolling(20, min_periods=10).mean() - 1.0
F["amihud20"] = (ret1.abs() / A).rolling(20).mean()
F["vv_std10_log"] = np.log(V).rolling(10).std()
F["vv_std10_norm"] = V.rolling(10).std() / V.rolling(10).mean()
F["vv_ratio_std10"] = (V / V.rolling(20).mean()).rolling(10).std()
F["vv_dev_ratio10"] = (V / V.rolling(20).mean() - 1.0).abs().rolling(10).mean()
F["vv_std10_div_mean60"] = V.rolling(10).std() / V.rolling(60).mean()
F["vv_std10_div_std120"] = V.rolling(10).std() / V.rolling(120).std()
F["vv_range10"] = V.rolling(10).max() / V.rolling(10).min()
F["vv_absdiff_mean10"] = V.diff().abs().rolling(10).mean() / V.rolling(10).mean()
F["vv_std10_amt"] = np.log(A).rolling(10).std()
F["vv_std10_turn"] = T.rolling(10).std() / T.rolling(10).mean()
F["vv_std10_ret"] = ret1.rolling(10).std()

GROUPS = [
    ("ema26-ratio", ["ema26_ratio"]),
    ("short-term-reversal-20d", ["short-term-reversal-20d"]),
    ("small-cap-baseline", ["small-cap-baseline"]),
    ("alpha191-042", ["__alpha191_042__"]),
    ("volume-vol-10d", ["vv_std10_log","vv_std10_norm","vv_ratio_std10","vv_dev_ratio10","vv_std10_div_mean60","vv_std10_div_std120","vv_range10","vv_absdiff_mean10","vv_std10_amt","vv_std10_turn","vv_std10_ret"]),
    ("ex_intradayma40_low", ["intradayma40"]),
    ("full_intradayma60_low", ["intradayma60"]),
    ("ex_intradayma90_low", ["intradayma90"]),
    ("ex_intradayma120_low", ["intradayma120"]),
    ("c20-c02-rev-bias60", ["bias60"]),
    ("probe-rev-bias20", ["bias20"]),
    ("comp-full-Amihud\u975e\u6d41\u52a8\u6027-20d", ["amihud20"]),
]

for feedname, cands in GROUPS:
    entries = feed.get(feedname)
    if not entries:
        print("== %s : not in feed ==" % feedname)
        continue
    uniq = {}
    for dt, pl, cyc, pr, ic in entries:
        uniq[(dt, cyc)] = (pl, pr, ic)
    print("== %s (%s) ==" % (feedname, uniq and list(uniq.values())[0][0]))
    for (dt, cyc), (pl, pr, ic) in sorted(uniq.items()):
        line = "   feed %s cyc=%d rank_ic=%s ic=%s" % (dt, cyc, str(pr)[:8], str(ic)[:8])
        for cname in cands:
            if cname == "__alpha191_042__":
                line += " | 042: (pending)"
                continue
            st = day_stats(F[cname], dt, cyc)
            if st is None:
                line += " | %s: na" % cname
            else:
                line += " | %s: %+.4f/%+.4f" % (cname, st[0], st[1])
        print(line)
