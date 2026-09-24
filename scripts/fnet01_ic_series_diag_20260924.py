"""Attribute the F-NET01 per-date rank-IC gap (local 0.067 vs platform 0.0577).

Local top tail is made of tradable, actively-quoted names; the platform's last-date
top-20 sits on a single identical value (8.1244) and 12/20 names have no local bar
that day.  So the residual per-date IC gap is a tail-convention difference.  Tests:

  base            local raw factor, all names, label t+1 -> t+1+cycle (current rule)
  label_offset0   same, but labels close(t) -> close(t+cycle)
  cap_q           per-date winsorise at quantile q, then rank IC
  drop_top1       drop the top 1% of factor values per date before ranking
  drop_absent     drop names whose 40d window has any missing bar (already strict)

Output: research_reports/platform_alignment/fnet01-alignment-20260924/ic_series_diag.json
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
WINDOW, CYCLE = 40, 5


def wma(values: pd.Series, frame: pd.DataFrame, window: int) -> pd.Series:
    weights = np.arange(1.0, window + 1.0)

    def apply(w: np.ndarray) -> float:
        if np.isnan(w).any():
            return np.nan
        return float(np.dot(w, weights) / weights.sum())

    grouped = values.groupby(frame["instrument"], sort=False, observed=True)
    return (grouped.rolling(window=window, min_periods=window).apply(apply, raw=True)
            .reset_index(level=0, drop=True).reindex(frame.index))


def rank_ic(values: np.ndarray, fwd: np.ndarray) -> float:
    if values.shape != fwd.shape:
        raise ValueError(f"shape mismatch {values.shape} vs {fwd.shape}")
    ok = np.isfinite(values) & np.isfinite(fwd)
    if ok.sum() < 100:
        return np.nan
    a = pd.Series(values[ok]).rank(method="average").to_numpy()
    b = pd.Series(fwd[ok]).rank(method="average").to_numpy()
    if a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def pearson_ic(values: np.ndarray, fwd: np.ndarray) -> float:
    ok = np.isfinite(values) & np.isfinite(fwd)
    if ok.sum() < 100:
        return np.nan
    a, b = values[ok], fwd[ok]
    if a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def main() -> int:
    platform = read_platform_run(RUN_JSON)
    dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
    plat_ic = np.array([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], dtype=float)
    print("platform dates", len(dates), dates[0].date(), dates[-1].date(), "mean rank ic %.4f" % np.nanmean(plat_ic), flush=True)

    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, pd.Timestamp("2018-01-01"), max(dates),
                             market_cap_field="total_mv")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    frame["_val"] = 1.0 / frame["raw_low"].pow(2) / frame["raw_volume"]
    print("rows", len(frame), flush=True)
    frame["_wma"] = wma(frame["_val"], frame, WINDOW)
    print("wma done", flush=True)
    calendar = list(pd.Index(sorted(frame["date"].unique())))
    position = {v: i for i, v in enumerate(calendar)}
    close = frame.pivot(index="date", columns="instrument", values="close_qfq").reindex(calendar)

    panels = {}
    for offset in (1, 0):
        rows = {}
        for date in dates:
            i = position.get(date)
            if i is None or i + offset + CYCLE >= len(calendar):
                continue
            rows[date] = (close.iloc[i + offset + CYCLE] / close.iloc[i + offset] - 1.0)
        fwd = pd.DataFrame(rows).T
        fwd.index = pd.to_datetime(fwd.index)
        panels[offset] = fwd
    print("forward panels ready", flush=True)

    values = frame.assign(dt=frame["date"]).pivot_table(index="dt", columns="instrument",
                                                        values="_wma", aggfunc="last").reindex(calendar)
    values.to_parquet("/tmp/fnet01_wma_panel.parquet")

    def aligned_pair(date, panel):
        """Return (factor, forward) arrays on the panel's own column order."""
        a = panel.loc[date]
        b = fwd.loc[date].reindex(a.index)
        return a, b
    variants: dict[str, list[float]] = {}
    for label, offset in (("base", 1), ("label_offset0", 0)):
        fwd = panels[offset]
        series = []
        for date in dates:
            if date not in values.index or date not in fwd.index:
                series.append(np.nan); continue
            a, b = aligned_pair(date, values)
            series.append(rank_ic(a.to_numpy(dtype=float), b.to_numpy(dtype=float)))
        variants[label] = series
        print(label, "done", flush=True)

    fwd = panels[1]
    for q in (0.999, 0.995, 0.99, 0.98, 0.95, 0.90):
        series = []
        for date in dates:
            if date not in values.index or date not in fwd.index:
                series.append(np.nan); continue
            cross = values.loc[date].dropna()
            cap = cross.quantile(q)
            series.append(rank_ic(np.minimum(cross, cap).to_numpy(dtype=float),
                                  fwd.loc[date].reindex(cross.index).to_numpy(dtype=float)))
        variants[f"cap_q{q}"] = series
        print("cap", q, "done", flush=True)

    for frac in (0.01, 0.02, 0.05):
        series = []
        for date in dates:
            if date not in values.index or date not in fwd.index:
                series.append(np.nan); continue
            cross = values.loc[date].dropna()
            cut = cross.quantile(1 - frac)
            keep = cross[cross < cut]
            series.append(rank_ic(keep.to_numpy(dtype=float),
                                  fwd.loc[date].reindex(keep.index).to_numpy(dtype=float)))
        variants[f"drop_top{int(frac*100)}pct"] = series
        print("drop", frac, "done", flush=True)

    pearson = []
    for date in dates:
        if date not in values.index or date not in fwd.index:
            pearson.append(np.nan); continue
        a, b = aligned_pair(date, values)
        pearson.append(pearson_ic(a.to_numpy(dtype=float), b.to_numpy(dtype=float)))
    variants["pearson_base"] = pearson

    report = {"platform_mean_rank_ic": float(np.nanmean(plat_ic)),
              "platform_rank_ic_std": float(np.nanstd(plat_ic)),
              "platform_ic_mean_pearson": platform["metrics"].get("IC_mean"),
              "n_platform_dates": len(dates), "variants": {}}
    for label, series in variants.items():
        s = np.array(series, dtype=float)
        n = min(len(s), len(plat_ic))
        mask = np.isfinite(s[:n]) & np.isfinite(plat_ic[:n])
        delta = np.abs(s[:n][mask] - plat_ic[:n][mask])
        corr = float(np.corrcoef(s[:n][mask], plat_ic[:n][mask])[0, 1]) if mask.sum() > 10 else float("nan")
        worst = np.argsort(-delta)[:5]
        report["variants"][label] = {
            "n_shared": int(mask.sum()),
            "mean_local_ic": float(np.nanmean(s[:n][mask])),
            "mean_abs_delta": float(delta.mean()),
            "corr": corr,
            "ic_std": float(np.nanstd(s[:n][mask])),
            "worst_dates": [dates[i].strftime("%Y-%m-%d") for i in worst],
            "worst_deltas": [float(delta[i]) for i in worst],
            "mean_delta_signed": float(np.mean(s[:n][mask] - plat_ic[:n][mask])),
        }
        r = report["variants"][label]
        print("%-16s meanIC=%.4f meanAbsDelta=%.4f corr=%.3f icStd=%.3f signed=%.4f" %
              (label, r["mean_local_ic"], r["mean_abs_delta"], r["corr"], r["ic_std"], r["mean_delta_signed"]), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ic_series_diag.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "ic_series_diag.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
