import io, sys, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

base = Path(r"D:\factor\quantlab\.quantlab\cache\research\cn_equity")
qb = base / "tushare_factor_recheck" / "qfq" / "daily_batches"
files = [f for f in sorted(qb.glob("batch_*.parquet"))
         if f.stem.split("_")[1] >= "20201201" and f.stem.split("_")[1] <= "20260907"]
print("batches:", len(files))
closes, volumes = [], []
for f in files:
    t = pd.read_parquet(f)
    closes.append(t[["date","instrument","close"]])
    volumes.append(t[["date","instrument","volume"]])
close = pd.concat(closes).pivot_table(index="date", columns="instrument", values="close").astype("float32")
volume = pd.concat(volumes).pivot_table(index="date", columns="instrument", values="volume").astype("float32")
del closes, volumes
close.index = pd.to_datetime(close.index.astype(str)); volume.index = pd.to_datetime(volume.index.astype(str))
close = close.sort_index(); volume = volume.sort_index()
print("panel:", close.shape, "| mem MB:", round(close.memory_usage().sum()/1e6,1), round(volume.memory_usage().sum()/1e6,1))

W = 30
def roll_corr(a, b, w):
    ma, mb = a.rolling(w).mean(), b.rolling(w).mean()
    maa, mbb = (a*a).rolling(w).mean(), (b*b).rolling(w).mean()
    mab = (a*b).rolling(w).mean()
    cov = mab - ma*mb
    va, vb = maa - ma*ma, mbb - mb*mb
    return cov / np.sqrt(va*vb).replace(0, np.nan)

corr30 = roll_corr(close, volume, W)
print("corr30 computed", corr30.shape)

# forward 10-day return: close(t+1) -> close(t+11)
fwd = close.shift(-11) / close.shift(-1) - 1.0

# daily_basic total_mv
dbdir = base / "tushare_factor_recheck" / "daily_basic_full_a"
sample_dates = close.index[::10]
mv_rows = []
for d in sample_dates:
    fp = dbdir / f"daily_basic_{d.strftime('%Y%m%d')}.parquet"
    if fp.exists():
        mv_rows.append(pd.read_parquet(fp))
mv = pd.concat(mv_rows).pivot_table(index="date", columns="instrument", values="total_mv")
mv.index = pd.to_datetime(mv.index.astype(str)); mv = mv.sort_index().astype("float32")
print("total_mv:", mv.shape)

# equity (annual, PIT)
bs = []
for f in sorted((base/"financial_full_a"/"balancesheet").glob("*.parquet")):
    bs.append(pd.read_parquet(f, columns=["ts_code","ann_date","f_ann_date","end_date","total_hldr_eqy_exc_min_int"]))
bs = pd.concat(bs, ignore_index=True)
bs = bs[bs["end_date"].astype(str).str.endswith("1231")].copy()
bs["f_ann_date"] = bs["f_ann_date"].fillna(bs["ann_date"]).astype(str)
bs = bs.sort_values("f_ann_date")
print("annual bs rows:", len(bs), "| cols sample:", bs.iloc[0][["ts_code","f_ann_date","end_date"]].tolist())

def equity_asof(inst, date_str):
    sub = bs[(bs["ts_code"] == inst) & (bs["f_ann_date"] <= date_str)]
    return sub["total_hldr_eqy_exc_min_int"].iloc[-1] if len(sub) else np.nan

results = {}
for label, field in [("corr30_close_vol", corr30), ("bm_lyr", None)]:
    rics = []
    used = 0
    for d in sample_dates:
        if d not in mv.index or d not in close.index: continue
        r = fwd.loc[d].dropna()
        if field is not None:
            x = field.loc[d].dropna()
        else:
            eq = pd.Series({inst: equity_asof(inst, d.strftime("%Y%m%d")) for inst in close.columns}, dtype="float32")
            x = (eq / mv.loc[d]).dropna()
        idx = x.index.intersection(r.index)
        if len(idx) < 100: continue
        rho, _ = spearmanr(x[idx].values, r[idx].values)
        if not np.isnan(rho): rics.append(rho); used += 1
    arr = np.array(rics)
    results[label] = arr
    print(f"{label:18s} dates={used:4d}  mean RankIC={arr.mean():+.4f}  t={arr.mean()/arr.std(ddof=1)*np.sqrt(len(arr)):+.2f}  "
          f"pos%={np.mean(arr>0)*100:.1f}%")
