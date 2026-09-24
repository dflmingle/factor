"""Why does the local WMA((((1/LOW)/LOW)/VOLUME),40) reconstruction miss the platform?

The saved platform run (6aa7cd283e7967143f8fb524, cycle 5) reports its last-date
top-20 and a per-date rank-IC series, so the mismatch can be attributed to the
price/vendor convention. Tests four local variants:

  qfq     1/low_qfq^2   / volume        (what the pipeline falls back to today)
  raw     1/raw_low^2   / raw_volume    (unadjusted low and volume, the documented reading)
  lowraw  1/raw_low^2   / volume        (only the price convention differs)
  volraw  1/low_qfq^2   / raw_volume

Output: research_reports/platform_alignment/fnet01-alignment-20260924/summary.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck"
PRICE_ROOT = CACHE / "qfq_rich/daily_batches"
CAP_ROOT = CACHE / "daily_basic_full_a"
RUN_JSON = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
WINDOW, CYCLE, LABEL_OFFSET = 40, 5, 1


def wma(values: pd.Series, frame: pd.DataFrame, window: int) -> pd.Series:
    """Linear weights 1..N, newest observation weighted N (pipeline convention)."""
    weights = np.arange(1.0, window + 1.0)

    def apply(window_values: np.ndarray) -> float:
        if np.isnan(window_values).any():
            return np.nan
        return float(np.dot(window_values, weights) / weights.sum())

    grouped = values.groupby(frame["instrument"], sort=False, observed=True)
    return grouped.rolling(window=window, min_periods=window).apply(apply, raw=True
        ).reset_index(level=0, drop=True).reindex(frame.index)


def rank_ic_series(panel: pd.DataFrame, forward: pd.DataFrame, dates: list[pd.Timestamp]) -> list[float]:
    out = []
    for date in dates:
        if date not in panel.index:
            out.append(np.nan); continue
        f = panel.loc[date].to_numpy(dtype="float64")
        r = forward.loc[date].to_numpy(dtype="float64") if date in forward.index else None
        if r is None:
            out.append(np.nan); continue
        ok = np.isfinite(f) & np.isfinite(r)
        if ok.sum() < 100:
            out.append(np.nan); continue
        a = pd.Series(f[ok]).rank().to_numpy()
        b = pd.Series(r[ok]).rank().to_numpy()
        out.append(float(np.corrcoef(a, b)[0, 1]))
    return out


def main() -> int:
    platform = read_platform_run(RUN_JSON)
    dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
    plat_rank_ic = platform["rank_ic_values"]
    plat_top = [str(row["symbol"]) for row in platform["top"]]
    print(f"platform dates={len(dates)} {dates[0].date()}..{dates[-1].date()} "
          f"top={len(plat_top)} last={platform['top'][0]['date'] if platform['top'] else None}", flush=True)
    print("platform rank_ic mean=%.4f n=%d" % (np.nanmean(plat_rank_ic), len(plat_rank_ic)), flush=True)

    start = pd.Timestamp("2018-01-01")
    top_date = pd.Timestamp(platform["top"][0]["date"]).normalize()
    end = max(dates[-1], top_date)
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, start, end, market_cap_field="total_mv")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print(f"rows={len(frame)} instruments={frame['instrument'].nunique()} "
          f"has_raw_low={'raw_low' in frame.columns} has_raw_volume={'raw_volume' in frame.columns}",
          flush=True)
    if "raw_low" not in frame.columns:
        print("!! rich columns missing from the loader output", flush=True)
        return 1

    variants = {
        "qfq": 1.0 / frame["low_qfq"].pow(2) / frame["volume"],
        "raw": 1.0 / frame["raw_low"].pow(2) / frame["raw_volume"],
        "lowraw": 1.0 / frame["raw_low"].pow(2) / frame["volume"],
        "volraw": 1.0 / frame["low_qfq"].pow(2) / frame["raw_volume"],
    }
    calendar = list(pd.Index(sorted(frame["date"].unique())))
    position = {value: index for index, value in enumerate(calendar)}
    close = frame.pivot(index="date", columns="instrument", values="close_qfq").reindex(calendar)

    forward = {}
    for horizon in (CYCLE,):
        rows = {}
        for date in dates:
            i = position.get(date)
            if i is None or i + 1 + horizon >= len(calendar):
                continue
            entry, exit_ = close.iloc[i + LABEL_OFFSET], close.iloc[i + LABEL_OFFSET + horizon]
            rows[date] = exit_ / entry - 1.0
        forward[horizon] = pd.DataFrame(rows).T.reindex(columns=close.columns)
    fwd = forward[CYCLE]
    fwd.index = pd.to_datetime(fwd.index)

    summary = []
    for name, values in variants.items():
        smoothed = wma(values, frame, WINDOW)
        panel = (frame.assign(_v=smoothed).pivot(index="date", columns="instrument", values="_v")
                 .reindex(calendar))
        ics = rank_ic_series(panel, fwd, dates)
        finite = np.isfinite(ics) & np.isfinite(plat_rank_ic[:len(ics)])
        corr = float(np.corrcoef(np.array(ics)[finite], np.array(plat_rank_ic[:len(ics)])[finite])[0, 1]) \
            if finite.sum() > 10 else float("nan")
        last = panel.loc[top_date].dropna()
        local_top = last.nlargest(20).index.tolist()
        overlap = len(set(local_top) & set(plat_top))
        summary.append(dict(variant=name, local_rank_ic=float(np.nanmean(ics)),
                            corr_with_platform_ic=corr, top20_overlap=overlap,
                            local_top20=",".join(local_top[:20])))
        print(f"  {name:8s} local RankIC={np.nanmean(ics):+.4f} "
              f"corr(platform IC series)={corr:+.3f} top20 overlap={overlap}/20", flush=True)

    print("\nplatform top20:", ",".join(plat_top), flush=True)
    for row in summary:
        print(f"{row['variant']:8s} {row['local_top20']}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "variant_comparison.json").write_text(json.dumps(
        dict(platform_top20=plat_top, platform_rank_ic_mean=float(np.nanmean(plat_rank_ic)),
             variants=summary), ensure_ascii=False, indent=2))
    print("saved", OUT / "variant_comparison.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
