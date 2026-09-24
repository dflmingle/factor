"""Does a forward-filled (stale-bar) cross-section reproduce the platform IC amplitude?

Platform rank-IC std ~0.149 / level 0.0577; local strict 40-of-40 window gives
std 0.1935 / level 0.062 on ~4950 names.  A platform that keeps stale bars keeps
roughly the whole listed pool in the cross-section.  This builds the same factor on
a forward-filled low/volume panel (full 40-of-40 window, weights 1..40) and compares.

Output: research_reports/platform_alignment/fnet01-alignment-20260924/ffill_probe.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FACTOR_LOCAL_UNIVERSE_FILTER", "off")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
RUN_JSON = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json"
WINDOW, CYCLE = 40, 5
LEVEL = Path("/tmp/fnet01_lowvol_unfiltered.parquet")


def wma_linear(panel: pd.DataFrame, window: int) -> pd.DataFrame:
    """Linear weights 1..window with the newest row heaviest, full window required."""
    values = panel.to_numpy(dtype="float64")
    positions = np.arange(len(panel), dtype="float64")[:, None]
    filled = np.where(np.isfinite(values), values, 0.0)
    valid = np.isfinite(values).astype("float64")
    counts = np.cumsum(valid, axis=0)
    sums = np.cumsum(filled, axis=0)
    weighted = np.cumsum(filled * positions, axis=0)
    counts_w = counts[window - 1:].copy()
    sums_w = sums[window - 1:].copy()
    weighted_w = weighted[window - 1:].copy()
    counts_w[1:] -= counts[:-window]
    sums_w[1:] -= sums[:-window]
    weighted_w[1:] -= weighted[:-window]
    t = positions[window - 1:]
    numerator = (window - t) * sums_w + weighted_w
    denominator = float(window * (window + 1) / 2.0)
    result = numerator / denominator
    result[counts_w < window] = np.nan
    out = pd.DataFrame(result, index=panel.index[window - 1:], columns=panel.columns)
    return out.reindex(panel.index)


def main() -> int:
    platform = read_platform_run(RUN_JSON)
    dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
    plat = np.array([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], dtype=float)

    if LEVEL.exists():
        levels = pd.read_parquet(LEVEL)
        print("cached low/volume panel", levels.shape, flush=True)
    else:
        frame = load_full_a_data(CACHE / "qfq_rich/daily_batches", CACHE / "daily_basic_full_a",
                                 pd.Timestamp("2018-01-01"), pd.Timestamp("2026-09-07"),
                                 market_cap_field="total_mv")
        low = frame.pivot_table(index="date", columns="instrument", values="raw_low", aggfunc="last").sort_index()
        volume = frame.pivot_table(index="date", columns="instrument", values="raw_volume", aggfunc="last").sort_index()
        levels = low.ffill() if False else pd.concat({"low": low, "volume": volume}, axis=1)
        levels.to_parquet(LEVEL)
        print("built low/volume panel", levels.shape, flush=True)

    low = levels["low"].ffill()
    volume = levels["volume"].ffill()
    close = pd.read_parquet("/tmp/fnet01_close_unfiltered.parquet").reindex(low.index).ffill()
    values = wma_linear(1.0 / low.pow(2) / volume, WINDOW)
    print("ffilled factor built; non-null on last date:", int(values.iloc[-1].notna().sum()), flush=True)
    values = values.reindex(columns=close.columns)

    calendar = list(close.index)
    position = {d: i for i, d in enumerate(calendar)}
    series, series_strict = [], []
    strict = pd.read_parquet("/tmp/fnet01_wma_unfiltered.parquet").reindex(columns=close.columns)
    for date in dates:
        i = position.get(date)
        if i is None or i + 1 + CYCLE >= len(calendar):
            series.append(np.nan); series_strict.append(np.nan); continue
        entry, exit_ = close.iloc[i + 1], close.iloc[i + 1 + CYCLE]
        fwd = exit_ / entry - 1.0
        for panel, sink in ((values, series), (strict, series_strict)):
            a = panel.loc[date] if date in panel.index else pd.Series(np.nan, index=close.columns)
            ok = a.notna() & fwd.notna()
            av, bv = a[ok], fwd[ok]
            sink.append(float(av.rank().corr(bv.rank())) if len(av) > 100 else np.nan)

    report = {"platform": {"rank_ic": platform["metrics"].get("Rank_IC"), "rank_ic_std_implied":
                           float(platform["metrics"]["Rank_IC"]) / float(platform["metrics"]["IC_IR"])}}
    for key, arr in (("ffilled_full_window", np.array(series, dtype=float)),
                     ("strict_full_window", np.array(series_strict, dtype=float))):
        n = min(len(arr), len(plat))
        ok = np.isfinite(arr[:n]) & np.isfinite(plat[:n])
        a, b = arr[:n][ok], plat[:n][ok]
        beta = float(np.polyfit(a, b, 1)[0])
        report[key] = {"n": int(ok.sum()), "mean": float(a.mean()), "std": float(a.std(ddof=1)),
                       "corr": float(np.corrcoef(a, b)[0, 1]),
                       "rank_corr": float(pd.Series(a).corr(pd.Series(b), method="spearman")),
                       "beta": beta, "mean_abs_delta": float(np.mean(np.abs(a - b))),
                       "delta_after_beta": float(np.mean(np.abs(a * beta - b)))}
        r = report[key]
        print("%-20s n=%d mean=%.4f std=%.4f corr=%.3f rank_corr=%.3f beta=%.3f delta=%.4f delta@beta=%.4f" % (
            key, r["n"], r["mean"], r["std"], r["corr"], r["rank_corr"], r["beta"], r["mean_abs_delta"], r["delta_after_beta"]), flush=True)
    # cross-section size of the ffilled panel on the last date vs the strict panel
    last = close.index[-1]
    report["cross_section_last_date"] = {"ffilled": int(values.loc[last].notna().sum()),
                                         "strict": int(strict.loc[last].notna().sum())}
    print("cross-section on", last.date(), report["cross_section_last_date"], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ffill_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "ffill_probe.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
