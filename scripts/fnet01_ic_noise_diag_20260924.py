"""Why is the local F-NET01 rank-IC series ~22% more volatile than the platform's?

Platform: Rank_IC 0.0577, IC_IR 0.3864 -> rank-IC std ~0.149.  Local: std ~0.19,
corr 0.92, mean |delta| 0.069.  Both the extra local volatility and the residual
correlation gap have to be explained before the record can be called aligned.

Tests (all local, cached panels, zero platform compute):
  * suspension gap: drop names with a missing bar inside the forward window
  * resumption/limit jumps: drop names with |forward return| above cutoff
  * extreme-tail names: drop the top/bottom q of the factor cross-section
  * scale structure: rank correlation, OLS slope, delta after matching variance

Output: research_reports/platform_alignment/fnet01-alignment-20260924/ic_noise.json
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
    "cycle5": PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json",
}
VALUE_CACHE = Path("/tmp/fnet01_wma_unfiltered.parquet")
CLOSE_CACHE = Path("/tmp/fnet01_close_unfiltered.parquet")


def stats(local: np.ndarray, plat: np.ndarray, dates) -> dict:
    n = min(len(local), len(plat))
    ok = np.isfinite(local[:n]) & np.isfinite(plat[:n])
    a, b = local[:n][ok], plat[:n][ok]
    delta = np.abs(a - b)
    beta = float(np.polyfit(a, b, 1)[0]) if len(a) > 10 else float("nan")
    scaled = a * beta
    rank_corr = float(pd.Series(a).corr(pd.Series(b), method="spearman"))
    worst = np.argsort(-delta)[:5]
    return {
        "n": int(ok.sum()),
        "mean_local": float(a.mean()), "mean_platform": float(b.mean()),
        "std_local": float(a.std(ddof=1)), "std_platform": float(b.std(ddof=1)),
        "corr": float(np.corrcoef(a, b)[0, 1]),
        "rank_corr": rank_corr,
        "ols_beta": beta,
        "mean_abs_delta": float(delta.mean()),
        "mean_abs_delta_after_beta": float(np.mean(np.abs(scaled - b))),
        "std_ratio": float(a.std(ddof=1) / b.std(ddof=1)) if b.std(ddof=1) else None,
        "worst_dates": [pd.Timestamp(dates[i]).strftime("%Y-%m-%d") for i in worst],
        "worst_deltas": [float(delta[i]) for i in worst],
        "sign_agreement": float(np.mean(np.sign(a) == np.sign(b))),
    }


def main() -> int:
    platform = read_platform_run(RUNS["cycle5"])
    dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
    plat = np.array([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], dtype=float)
    values = pd.read_parquet(VALUE_CACHE)
    close = pd.read_parquet(CLOSE_CACHE)
    calendar = list(close.index)
    position = {d: i for i, d in enumerate(calendar)}
    cycle = 5

    print("platform rank-ic std %.4f from saved IC/RankIC metrics: %.4f" % (
        np.nanstd(plat), float(platform["metrics"]["Rank_IC"]) / float(platform["metrics"]["IC_IR"]) if platform["metrics"].get("IC_IR") else float("nan")), flush=True)

    variants: dict[str, list[float]] = {}
    series = []
    for date in dates:
        i = position.get(date)
        if i is None or i + 1 + cycle >= len(calendar):
            series.append(np.nan); continue
        columns = values.columns
        window = close.iloc[i + 1:i + 2 + cycle].reindex(columns=columns)
        entry = close.iloc[i + 1].reindex(columns)
        exit_ = close.iloc[i + 1 + cycle].reindex(columns)
        fwd = exit_ / entry - 1.0
        a = values.loc[date].reindex(columns)
        base_ok = a.notna() & fwd.notna() & entry.notna() & exit_.notna()
        gap_free = base_ok & window.notna().all(axis=0)
        results = {
            "base": base_ok,
            "no_forward_gap": gap_free,
            "no_gap_no_big_jump": gap_free & fwd.abs().lt(0.30),
            "gap_free_drop_top1pct": None,
        }
        # drop the extreme 1% of the factor cross-section on top of gap_free
        cut = a[gap_free].quantile(0.99)
        results["gap_free_drop_top1pct"] = gap_free & a.lt(cut)
        for key, mask in results.items():
            idx = np.where(mask.to_numpy())[0]
            if len(idx) < 100:
                variants.setdefault(key, []).append(np.nan); continue
            av = pd.Series(a.iloc[idx].to_numpy(dtype=float))
            bv = pd.Series(fwd.iloc[idx].to_numpy(dtype=float))
            variants.setdefault(key, []).append(float(av.rank().corr(bv.rank())))
        series.append(np.nan)

    report = {"platform": {"rank_ic": platform["metrics"].get("Rank_IC"), "ic_ir": platform["metrics"].get("IC_IR"),
                           "ic_std": platform["metrics"].get("IC_std"), "n_dates": int(np.isfinite(plat).sum()),
                           "reported_rank_ic_std": float(platform["metrics"]["Rank_IC"]) / float(platform["metrics"]["IC_IR"])},
              "variants": {}}
    for key, values_list in variants.items():
        arr = np.array(values_list, dtype=float)
        if len(arr) != len(dates):
            pad = len(dates) - len(arr)
            arr = np.concatenate([arr, np.full(pad, np.nan)])
        report["variants"][key] = stats(arr, plat, dates)
        s = report["variants"][key]
        print("%-24s n=%3d mean=%.4f std=%.4f corr=%.3f rank_corr=%.3f beta=%.3f delta=%.4f delta@beta=%.4f" % (
            key, s["n"], s["mean_local"], s["std_local"], s["corr"], s["rank_corr"], s["ols_beta"],
            s["mean_abs_delta"], s["mean_abs_delta_after_beta"]), flush=True)
        print("      worst:", s["worst_dates"], ["%.3f" % d for d in s["worst_deltas"]], flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ic_noise.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "ic_noise.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
