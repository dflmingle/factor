"""Monthly excess comparison: 5-seat baseline pool vs the T2 6-seat pool, using the
platform's per-rebalance cumulative curves (the only period-level data the paste returns)."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")

RUNS = {
    "base5": ROOT / "pool-candCD-20260922-candidates.results/6ab254c08b01f62dc5147d3a.json",
    "t2_six": ROOT / "platform_pool_tests_20260926/pool6-t2t4-v2-20260926-candidates.results/6ab75e8fcd820fa2a40a6cbe.json",
}


def curves(path: Path) -> dict[str, pd.Series]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fa = payload["results"]["factor_analysis"]
    dates = pd.to_datetime([row["data"] if isinstance(row, dict) else row
                            for row in fa["query_return_chart"]["x"][0]["data"]])
    out = {}
    for chart_key in ("query_return_chart", "query_factor_excess_chart"):
        for series in fa[chart_key]["y"]:
            name = series["name"]
            if name not in {"组10", "组1", "多空组合"}:
                continue
            tag = "abs" if chart_key == "query_return_chart" else "exc"
            out[f"{tag}:{name}"] = pd.Series(np.asarray(series["data"], dtype=float), index=dates)
    return out


def monthly(series: pd.Series) -> pd.Series:
    """Compound cumulative (wealth-1) curve into calendar-month returns."""
    level = 1.0 + series
    grouped = level.groupby([level.index.year, level.index.month]).last()
    first = 1.0
    rows = {}
    keys = list(grouped.index)
    prev = first
    for key in keys:
        rows[key] = grouped[key] / prev - 1.0
        prev = grouped[key]
    idx = pd.to_datetime([f"{y:04d}-{m:02d}-01" for y, m in keys])
    return pd.Series(list(rows.values()), index=idx)


frames = {name: curves(path) for name, path in RUNS.items()}
summary = {}
for name, data in frames.items():
    for tag in ("abs:组10", "exc:组10"):
        monthly_series = monthly(data[tag])
        neg = int((monthly_series < 0).sum())
        summary[(name, tag)] = monthly_series
        print(f"{name} {tag}: months={len(monthly_series)} neg_months={neg} "
              f"mean={monthly_series.mean()*100:.2f}% median={monthly_series.median()*100:.2f}% "
              f"std={monthly_series.std()*100:.2f}% "
              f"sharpe_m={monthly_series.mean()/monthly_series.std():.3f} "
              f"min={monthly_series.min()*100:.2f}% max={monthly_series.max()*100:.2f}%")

base_exc = summary[("base5", "exc:组10")]
t2_exc = summary[("t2_six", "exc:组10")]
aligned = pd.concat([base_exc.rename("base5"), t2_exc.rename("t2_six")], axis=1).dropna()
print(f"\naligned months: {len(aligned)}")
print(f"  base5  neg months: {int((aligned.base5 < 0).sum())}   t2_six neg months: {int((aligned.t2_six < 0).sum())}")
print(f"  both positive: {int(((aligned.base5 > 0) & (aligned.t2_six > 0)).sum())} | "
      f"base+ t2-: {int(((aligned.base5 > 0) & (aligned.t2_six < 0)).sum())} | "
      f"base- t2+: {int(((aligned.base5 < 0) & (aligned.t2_six > 0)).sum())} | "
      f"both neg: {int(((aligned.base5 < 0) & (aligned.t2_six < 0)).sum())}")
delta = aligned.t2_six - aligned.base5
print(f"  mean monthly delta = {delta.mean()*100:.3f}%  median {delta.median()*100:.3f}%  "
      f"t2 better in {int((delta > 0).sum())}/{len(delta)} months")
print("\nworst 6 months for base5 (delta shown):")
print((aligned.assign(delta=delta).sort_values("base5").head(6) * 100).round(2).to_string())
print("\nworst 6 months for t2_six:")
print((aligned.assign(delta=delta).sort_values("t2_six").head(6) * 100).round(2).to_string())