import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pyarrow.parquet as pq
from pathlib import Path
base = Path(r"D:\factor\quantlab\.quantlab\cache\research\cn_equity")
# daily bars
p = base / "tushare_factor_recheck" / "qfq" / "daily_batches" / "batch_20260814_20260907.parquet"
df = pq.read_table(p, columns=["date","instrument","close","volume"]).to_pandas()
last = df[df["date"] == df["date"].max()]
print("stocks on last date:", len(last))
for c in ["close","volume"]:
    q = last[c].quantile([0.05,0.5,0.95]).tolist()
    print(f"  {c:8s} p5/50/95 = " + "  ".join(f"{v:.4g}" for v in q))
# total assets
import glob
files = sorted((base/"financial_full_a"/"balancesheet").glob("*.parquet"))[:40]
import pandas as pd
frames = []
for f in files[:40]:
    t = pq.read_table(f, columns=["ts_code","end_date","total_assets","f_ann_date"]).to_pandas()
    frames.append(t)
bs = pd.concat(frames, ignore_index=True)
latest = bs.sort_values(["ts_code","end_date"]).groupby("ts_code").tail(1)
q = latest["total_assets"].quantile([0.05,0.5,0.95]).tolist()
print("total_assets p5/50/95 =", "  ".join(f"{v:.4g}" for v in q), "| n =", len(latest))
