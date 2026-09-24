"""Shape test for the platform's saved RankIC chart series.

Local strict series: mean 0.0634, std 0.1944, corr 0.904, rank corr 0.895, OLS beta
0.696 against the platform chart.  After matching amplitude the mean absolute delta
falls from 0.072 to 0.052, so the residual is a scale/shape difference, not a
ranking-path difference.  Candidates tested here: chart smoothing (MA3/MA5), a
one-date lag in the chart axis, and mixture with the platform's own metric levels.

Output: research_reports/platform_alignment/fnet01-alignment-20260924/series_shape.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_aligned_factor_compare import read_platform_run  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
RUN_JSON = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json"
CYCLE = 5


def evaluate(local: pd.Series, plat: pd.Series) -> dict:
    frame = pd.DataFrame({"local": local, "platform": plat}).dropna()
    a, b = frame["local"].to_numpy(), frame["platform"].to_numpy()
    beta = float(np.polyfit(a, b, 1)[0]) if len(a) > 10 else float("nan")
    return {"n": len(a), "corr": float(np.corrcoef(a, b)[0, 1]) if len(a) > 10 else None,
            "rank_corr": float(pd.Series(a).corr(pd.Series(b), method="spearman")) if len(a) > 10 else None,
            "beta": beta, "std_ratio": float(a.std(ddof=1) / b.std(ddof=1)) if b.std(ddof=1) else None,
            "mean_abs_delta": float(np.mean(np.abs(a - b))),
            "delta_after_beta": float(np.mean(np.abs(a * beta - b)))}


def main() -> int:
    platform = read_platform_run(RUN_JSON)
    dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
    plat = pd.Series([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], index=dates)

    values = pd.read_parquet("/tmp/fnet01_wma_unfiltered.parquet")
    close = pd.read_parquet("/tmp/fnet01_close_unfiltered.parquet")
    close = close.reindex(columns=values.columns).ffill()
    # rebuild the strict local series (same rule as the formal compare run)
    calendar = list(close.index)
    position = {d: i for i, d in enumerate(calendar)}
    series = {}
    for date in dates:
        i = position.get(date)
        if i is None or i + 1 + CYCLE >= len(calendar):
            series[date] = np.nan; continue
        a = values.loc[date] if date in values.index else pd.Series(np.nan, index=values.columns)
        fwd = close.iloc[i + 1 + CYCLE] / close.iloc[i + 1] - 1.0
        ok = a.notna() & fwd.notna()
        series[date] = float(a[ok].rank().corr(fwd[ok].rank())) if ok.sum() > 100 else np.nan
    local = pd.Series(series)
    print("local mean %.4f std %.4f" % (local.mean(), local.std(ddof=1)), flush=True)

    report: dict[str, object] = {"platform": {"mean": float(plat.mean()), "std": float(plat.std(ddof=1))},
                                 "local_raw": evaluate(local, plat)}
    print("%-26s %s" % ("local_raw", json.dumps(report["local_raw"], default=float)), flush=True)

    for window in (2, 3, 5, 7):
        for mode in ("trailing", "centered"):
            if mode == "trailing":
                smooth = local.rolling(window).mean()
            else:
                smooth = local.rolling(window, center=True).mean()
            report[f"ma{window}_{mode}"] = evaluate(smooth, plat)
            print("%-26s %s" % (f"ma{window}_{mode}", json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in report[f"ma{window}_{mode}"].items()}, default=float)), flush=True)

    for lag in (-2, -1, 1, 2):
        shifted = local.shift(lag)
        report[f"lag{lag:+d}"] = evaluate(shifted, plat)
        print("%-26s %s" % (f"lag{lag:+d}", json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in report[f"lag{lag:+d}"].items()}, default=float)), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "series_shape.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "series_shape.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
