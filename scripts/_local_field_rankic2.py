import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

base = Path(r"D:\factor\quantlab\.quantlab\cache\research\cn_equity")
qb = base / "tushare_factor_recheck" / "qfq" / "daily_batches"
files = [f for f in sorted(qb.glob("batch_*.parquet")) if "20201201" <= f.stem.split("_")[1] <= "20260907"]
print("batches:", len(files), flush=True)
cs, vs = [], []
for f in files:
    t = pd.read_parquet(f)
    cs.append(t[["date","instrument","close"]]); vs.append(t[["date","instrument","volume"]])
close = pd.concat(cs).pivot_table(index="date", columns="instrument", values="close").astype("float32")
volume = pd.concat(vs).pivot_table(index="date", columns="instrument", values="volume").astype("float32")
del cs, vs
close.index = pd.to_datetime(close.index.astype(str)); volume.index = pd.to_datetime(volume.index.astype(str))
close, volume = close.sort_index(), volume.sort_index()
print("panel:", close.shape, flush=True)

W = 30
ma, mb = close.rolling(W).mean(), volume.rolling(W).mean()
maa, mbb = (close*close).rolling(W).mean(), (volume*volume).rolling(W).mean()
mab = (close*volume).rolling(W).mean()
corr30 = (mab - ma*mb) / np.sqrt((maa-ma*ma)*(mbb-mb*mb)).replace(0, np.nan)
print("corr30 done", flush=True)
fwd = close.shift(-11) / close.shift(-1) - 1.0

dbdir = base / "tushare_factor_recheck" / "daily_basic_full_a"
sample_dates = close.index[::10]
mv = pd.concat([pd.read_parquet(dbdir/f"daily_basic_{d.strftime('%Y%m%d')}.parquet")
                for d in sample_dates if (dbdir/f"daily_basic_{d.strftime('%Y%m%d')}.parquet").exists()])
mv = mv.pivot_table(index="date", columns="instrument", values="total_mv").astype("float32")
mv.index = pd.to_datetime(mv.index.astype(str)); mv = mv.sort_index()
print("total_mv:", mv.shape, flush=True)

bs = pd.concat([pd.read_parquet(f, columns=["ts_code","ann_date","f_ann_date","end_date","total_hldr_eqy_exc_min_int"])
                for f in sorted((base/"financial_full_a"/"balancesheet").glob("*.parquet"))], ignore_index=True)
bs = bs[bs["end_date"].astype(str).str.endswith("1231")].copy()
bs["f_ann_date"] = bs["f_ann_date"].fillna(bs["ann_date"]).astype(str)
bs = bs.sort_values("f_ann_date")
print("annual bs rows:", len(bs), flush=True)

def bm_panel(d):
    ds = d.strftime("%Y%m%d")
    sub = bs[bs["f_ann_date"] <= ds].groupby("ts_code", sort=False).tail(1).set_index("ts_code")["total_hldr_eqy_exc_min_int"]
    eq = sub.reindex(close.columns)
    return (eq / mv.loc[d]).astype("float32")

for label, builder in [("corr30_close_vol", lambda d: corr30.loc[d]),
                       ("bm_lyr", bm_panel)]:
    rics, used = [], 0
    for d in sample_dates:
        if d not in mv.index: continue
        r = fwd.loc[d].dropna(); x = builder(d).dropna()
        idx = x.index.intersection(r.index)
        if len(idx) < 100: continue
        rho, _ = spearmanr(x[idx].values, r[idx].values)
        if not np.isnan(rho): rics.append(rho); used += 1
    arr = np.array(rics)
    print(f"{label:18s} dates={used:4d}  mean RankIC={arr.mean():+.4f}  "
          f"t={arr.mean()/arr.std(ddof=1)*np.sqrt(len(arr)):+.2f}  pos%={np.mean(arr>0)*100:.1f}%", flush=True)
