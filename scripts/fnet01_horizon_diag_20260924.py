"""Does the platform's saved RankIC chart use a longer label than the configured cycle?

Local IC series is 1.30x more volatile than the saved platform chart at the same mean
level, for both the RankIC and the IC chart -- a common scale factor.  A 2x horizon
label (overlapping windows) shrinks the series by roughly that factor while keeping
the shape.  Tests horizons 5/10/15/20 at both saved runs' dates.

Output: research_reports/platform_alignment/fnet01-alignment-20260924/horizon_diag.json
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
RUNS = {
    "cycle5": (PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json", 5),
    "cycle10": (PROJECT_ROOT / "cluster-singletons-t10-20260921-candidates.results/6ab0f3d7ecb163ea7228ded7.json", 10),
}


def main() -> int:
    values = pd.read_parquet("/tmp/fnet01_wma_unfiltered.parquet")
    close = pd.read_parquet("/tmp/fnet01_close_unfiltered.parquet")
    close = close.reindex(columns=values.columns).ffill()
    calendar = list(close.index)
    position = {d: i for i, d in enumerate(calendar)}

    report: dict[str, object] = {}
    for run, (path, configured) in RUNS.items():
        platform = read_platform_run(path)
        dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
        plat = pd.Series([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], index=dates)
        print("== %s configured cycle %d: platform mean %.4f std %.4f (implied std %.4f)" % (
            run, configured, plat.mean(), plat.std(ddof=1),
            float(platform["metrics"]["Rank_IC"]) / float(platform["metrics"]["IC_IR"])), flush=True)
        report[run] = {"configured_cycle": configured, "platform_mean": float(plat.mean()),
                       "platform_std": float(plat.std(ddof=1)), "horizons": {}}
        for horizon in (configured, configured * 2, configured * 3):
            rank_series, pearson_series = {}, {}
            for date in dates:
                i = position.get(date)
                if i is None or i + 1 + horizon >= len(calendar):
                    rank_series[date] = np.nan; pearson_series[date] = np.nan; continue
                a = values.loc[date] if date in values.index else pd.Series(np.nan, index=values.columns)
                fwd = close.iloc[i + 1 + horizon] / close.iloc[i + 1] - 1.0
                ok = a.notna() & fwd.notna()
                rank_series[date] = float(a[ok].rank().corr(fwd[ok].rank())) if ok.sum() > 100 else np.nan
                pearson_series[date] = float(a[ok].corr(fwd[ok])) if ok.sum() > 100 else np.nan
            for label, series in (("rank", rank_series), ("pearson", pearson_series)):
                s = pd.Series(series)
                frame = pd.DataFrame({"local": s, "platform": plat}).dropna()
                if len(frame) < 20:
                    continue
                a, b = frame["local"].to_numpy(), frame["platform"].to_numpy()
                beta = float(np.polyfit(a, b, 1)[0])
                entry = {"n": len(frame), "mean": float(a.mean()), "std": float(a.std(ddof=1)),
                         "corr": float(np.corrcoef(a, b)[0, 1]),
                         "rank_corr": float(pd.Series(a).corr(pd.Series(b), method="spearman")),
                         "beta": beta, "std_ratio": float(a.std(ddof=1) / b.std(ddof=1)),
                         "mean_abs_delta": float(np.mean(np.abs(a - b))),
                         "delta_after_beta": float(np.mean(np.abs(a * beta - b)))}
                report[run]["horizons"][f"{label}_h{horizon}"] = entry
                print("   %-10s h=%-3d n=%3d mean=%.4f std=%.4f corr=%.3f rank=%.3f beta=%.3f delta=%.4f delta@beta=%.4f" % (
                    label, horizon, entry["n"], entry["mean"], entry["std"], entry["corr"], entry["rank_corr"],
                    entry["beta"], entry["mean_abs_delta"], entry["delta_after_beta"]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "horizon_diag.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "horizon_diag.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
