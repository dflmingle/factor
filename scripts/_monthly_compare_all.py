import io, json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
RUNS = {
    "base5": ROOT / "pool-candCD-20260922-candidates.results/6ab254c08b01f62dc5147d3a.json",
    "t2_six": ROOT / "platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json",
    "t4_six": ROOT / "platform_pool_tests_20260926/pool6-t4v6-20260926-candidates.results/6ab769dd6ee632ca3f97b59d.json",
}
frames = {}
for label, path in RUNS.items():
    fa = json.loads(path.read_text(encoding="utf-8"))["results"]["factor_analysis"]
    dates = pd.to_datetime([r["data"] if isinstance(r, dict) else r for r in fa["query_return_chart"]["x"][0]["data"]])
    series = next(s for s in fa["query_factor_excess_chart"]["y"] if s["name"] == "组10")
    cum = pd.Series(np.asarray(series["data"], dtype=float), index=dates)
    level = 1.0 + cum
    grouped = level.groupby([level.index.year, level.index.month]).last()
    prev, values, keys = 1.0, [], []
    for key, val in grouped.items():
        values.append(val / prev - 1.0); keys.append(key); prev = val
    idx = pd.to_datetime([f"{y:04d}-{m:02d}-01" for y, m in keys])
    frames[label] = pd.Series(values, index=idx)

for label, series in frames.items():
    print(f"{label:8s} months={len(series)} neg={int((series < 0).sum())} mean={series.mean()*100:6.3f}% "
          f"median={series.median()*100:6.3f}% std={series.std()*100:5.2f}% sharpe_m={series.mean()/series.std():.3f} "
          f"min={series.min()*100:6.2f}% max={series.max()*100:6.2f}%")
aligned = pd.concat(frames, axis=1).dropna()
for key in ("t2_six", "t4_six"):
    delta = aligned[key] - aligned.base5
    print(f"\n{key}: mean delta={delta.mean()*100:+.3f}%/月 median={delta.median()*100:+.3f}% "
          f"better months={int((delta>0).sum())}/{len(delta)}  "
          f"base- & {key}+: {int(((aligned.base5<0)&(aligned[key]>0)).sum())}  "
          f"base+ & {key}-: {int(((aligned.base5>0)&(aligned[key]<0)).sum())}")
    print((aligned.assign(delta=delta).sort_values(key).head(4)*100).round(2).to_string())