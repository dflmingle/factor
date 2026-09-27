import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

base = Path(r"D:\factor\quantlab\.quantlab\cache\research\cn_equity")
qb = base / "tushare_factor_recheck" / "qfq" / "daily_batches"
files = [f for f in sorted(qb.glob("batch_*.parquet")) if "20201201" <= f.stem.split("_")[1] <= "20260907"]
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
ma40 = corr30.rolling(40).mean()
amt_ma20 = (close*volume).rolling(20).mean()
fwd = close.shift(-11) / close.shift(-1) - 1.0
print("derived panels done", flush=True)

dbdir = base / "tushare_factor_recheck" / "daily_basic_full_a"
sample_dates = close.index[::10]
mv = pd.concat([pd.read_parquet(dbdir/f"daily_basic_{d.strftime('%Y%m%d')}.parquet")
                for d in sample_dates if (dbdir/f"daily_basic_{d.strftime('%Y%m%d')}.parquet").exists()])
mv = mv.pivot_table(index="date", columns="instrument", values="total_mv").astype("float32")
mv.index = pd.to_datetime(mv.index.astype(str)); mv = mv.sort_index()

bs = pd.concat([pd.read_parquet(f, columns=["ts_code","ann_date","f_ann_date","end_date","total_hldr_eqy_exc_min_int","total_assets"])
                for f in sorted((base/"financial_full_a"/"balancesheet").glob("*.parquet"))], ignore_index=True)
bs = bs[bs["end_date"].astype(str).str.endswith("1231")].copy()
bs["f_ann_date"] = bs["f_ann_date"].fillna(bs["ann_date"]).astype(str)
bs = bs.sort_values("f_ann_date")

def asof(name):
    def f(d):
        sub = bs[bs["f_ann_date"] <= d.strftime("%Y%m%d")].groupby("ts_code", sort=False).tail(1).set_index("ts_code")[name]
        return sub.reindex(close.columns).astype("float32")
    return f
eq_asof, ta_asof = asof("total_hldr_eqy_exc_min_int"), asof("total_assets")

def k020(d):
    bm = eq_asof(d) / mv.loc[d]
    ratio = corr30.loc[d] / ma40.loc[d]
    return (bm / ratio / amt_ma20.loc[d] / ta_asof(d)).astype("float32")
def k020_no_bm(d):
    ratio = corr30.loc[d] / ma40.loc[d]
    return (1.0 / ratio / amt_ma20.loc[d] / ta_asof(d)).astype("float32")
def k020_bm_only(d):
    return (eq_asof(d) / mv.loc[d]).astype("float32")

for label, builder in [("K020_full", k020), ("K020_no_BM", k020_no_bm), ("K020_BM_only", k020_bm_only),
                       ("-1/(x/MA40)", lambda d: (-1.0/(corr30.loc[d]/ma40.loc[d])).astype("float32"))]:
    rics, med = [], []
    for d in sample_dates:
        if d not in mv.index: continue
        r = fwd.loc[d].dropna(); x = builder(d).replace([np.inf,-np.inf], np.nan).dropna()
        idx = x.index.intersection(r.index)
        if len(idx) < 100: continue
        rho, _ = spearmanr(x[idx].values, r[idx].values)
        if not np.isnan(rho): rics.append(rho); med.append(np.nanmedian(np.abs(x[idx].values)))
    arr = np.array(rics)
    print(f"{label:14s} dates={len(arr):4d}  mean RankIC={arr.mean():+.4f}  t={arr.mean()/arr.std(ddof=1)*np.sqrt(len(arr)):+.2f}  med|val|={np.median(med):.3g}", flush=True)
