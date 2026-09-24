"""Tail probe for F-NET01: platform shows 20 identical values 8.1244 on 2026-09-07.

Checks whether the platform's last-date top-20 corresponds to a degenerate tail
(0-volume / inf / winsor cap) instead of the genuine extreme factor values.
Zero platform compute; local data only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck"
PRICE_ROOT = CACHE / "qfq_rich/daily_batches"
CAP_ROOT = CACHE / "daily_basic_full_a"
RUN_JSON = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
CACHE_PANEL = Path("/tmp/fnet01_panel_cache.parquet")
WINDOW = 40
LAST_DATE = pd.Timestamp("2026-09-07")
PREV_DATE = pd.Timestamp("2026-08-24")


def wma(values: pd.Series, frame: pd.DataFrame, window: int) -> pd.Series:
    weights = np.arange(1.0, window + 1.0)

    def apply(window_values: np.ndarray) -> float:
        if np.isnan(window_values).any():
            return np.nan
        return float(np.dot(window_values, weights) / weights.sum())

    grouped = values.groupby(frame["instrument"], sort=False, observed=True)
    return (grouped.rolling(window=window, min_periods=window).apply(apply, raw=True)
            .reset_index(level=0, drop=True).reindex(frame.index))


def main() -> int:
    platform = json.loads(RUN_JSON.read_text())
    top_rows = platform["results"]["factor_analysis"]["query_last_date_top_factor"]
    plat_top = [str(r["symbol"]) for r in top_rows]
    plat_vals = [str(r["factor1"]) for r in top_rows]

    if CACHE_PANEL.exists():
        panel = pd.read_parquet(CACHE_PANEL)
        print("loaded cached panel", panel.shape, flush=True)
    else:
        frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, pd.Timestamp("2018-01-01"), LAST_DATE,
                                 market_cap_field="total_mv")
        frame = frame.sort_values(["instrument", "date"], ignore_index=True)
        print("rows", len(frame), "cols", list(frame.columns), flush=True)
        panel = frame[["date", "instrument"]].copy()
        variants = {
            "qfq": 1.0 / frame["low_qfq"].pow(2) / frame["volume"],
            "raw": 1.0 / frame["raw_low"].pow(2) / frame["raw_volume"],
        }
        for name, values in variants.items():
            panel[name] = wma(values, frame, WINDOW).to_numpy()
            print("computed", name, flush=True)
        panel["low_qfq"] = frame["low_qfq"].to_numpy()
        panel["raw_low"] = frame["raw_low"].to_numpy()
        panel["volume"] = frame["volume"].to_numpy()
        panel["raw_volume"] = frame["raw_volume"].to_numpy()
        panel.to_parquet(CACHE_PANEL, index=False)
        print("cached", CACHE_PANEL, flush=True)

    report: dict[str, object] = {"platform_top20": list(zip(plat_top, plat_vals))}

    for date in (LAST_DATE, PREV_DATE):
        cross = panel[panel["date"] == date]
        report[str(date.date())] = {"n_rows": int(len(cross))}
        for name in ("qfq", "raw"):
            vals = cross[["instrument", name]].dropna()
            finite = vals[np.isfinite(vals[name])]
            desc = {
                "n": int(len(vals)),
                "n_finite": int(len(finite)),
                "p50": float(finite[name].quantile(0.50)),
                "p99": float(finite[name].quantile(0.99)),
                "p999": float(finite[name].quantile(0.999)),
                "max": float(finite[name].max()),
                "n_within_1pct_of_8.1244": int(((finite[name] - 8.1244).abs() <= 8.1244e-4).sum()),
                "top20": finite.nlargest(20, name)["instrument"].tolist(),
                "top20_values": [float(v) for v in finite.nlargest(20, name)[name]],
            }
            report[str(date.date())][name] = desc
            print(date.date(), name, "n=%d max=%.4g p999=%.4g p99=%.4g" %
                  (desc["n"], desc["max"], desc["p999"], desc["p99"]), flush=True)

        sub = cross[cross["instrument"].isin(plat_top)][["instrument", "qfq", "raw", "low_qfq", "raw_low", "volume", "raw_volume"]]
        sub = sub.assign(qfq_rank=sub["qfq"].rank(ascending=False), raw_rank=sub["raw"].rank(ascending=False))
        report[str(date.date())]["platform_top20_local"] = json.loads(sub.to_json(orient="records"))
        print(date.date(), "platform top20 local values:\n", sub.sort_values("qfq", ascending=False).to_string(index=False), flush=True)

    # zero-volume diagnostics over the WMA window ending 2026-09-07
    win = panel[(panel["date"] <= LAST_DATE) & (panel["date"] > LAST_DATE - pd.Timedelta(days=70))]
    z = win.groupby("instrument").agg(zero_vol=("raw_volume", lambda s: int((s == 0).sum())),
                                     n=("raw_volume", "size"))
    z = z[z["n"] >= 20]
    z["zero_frac"] = z["zero_vol"] / z["n"]
    halted = z[z["zero_frac"] > 0.5]
    report["halted_symbols_last_70d"] = {"n_symbols": int(len(halted)),
                                         "platform_top20_halted": sorted(set(halted.index) & set(plat_top))}
    cross = panel[panel["date"] == LAST_DATE].set_index("instrument")
    print("\nplatform top20 rows on last date:")
    print(cross.reindex(plat_top)[["low_qfq", "raw_low", "volume", "raw_volume", "qfq", "raw"]].to_string(), flush=True)
    print("\nhalted (zero volume >50% of last 70d):", len(halted), "of", len(z),
          "| platform top20 halted:", sorted(set(halted.index) & set(plat_top)), flush=True)
    print("qfq max on last date:", float(cross["qfq"].replace([np.inf, -np.inf], np.nan).dropna().max()),
          "| raw max:", float(cross["raw"].replace([np.inf, -np.inf], np.nan).dropna().max()), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tail_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "tail_probe.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
