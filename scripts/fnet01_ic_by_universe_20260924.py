"""F-NET01 per-date rank IC vs the saved platform series, by local universe variant.

The platform's saved display/charts keep ST names; the qualitygate3 local panel drops
them.  This script rebuilds the factor on the full unfiltered panel and compares the
per-date rank-IC series against each saved platform run under four universe masks.
Also caches the unfiltered factor/close panels for later diagnostics.

Output: research_reports/platform_alignment/fnet01-alignment-20260924/ic_by_universe.json
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

from full_a_local_data import NAMECHANGE_PATH, STOCK_BASIC_PATH, load_full_a_data  # noqa: E402
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import rolling_weighted_mean  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck"
PRICE_ROOT = CACHE / "qfq_rich/daily_batches"
CAP_ROOT = CACHE / "daily_basic_full_a"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
RUNS = {
    "cycle5": PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json",
    "cycle10": PROJECT_ROOT / "cluster-singletons-t10-20260921-candidates.results/6ab0f3d7ecb163ea7228ded7.json",
}
VALUE_CACHE = Path("/tmp/fnet01_wma_unfiltered.parquet")
CLOSE_CACHE = Path("/tmp/fnet01_close_unfiltered.parquet")


def st_mask(frame: pd.DataFrame) -> pd.Series:
    """Point-in-time ST flag (same logic as the loader's universe filter)."""
    history = pd.read_parquet(NAMECHANGE_PATH)
    history["is_st"] = history["name"].astype(str).str.upper().str.contains("ST")
    history = history[["ts_code", "start_date", "end_date", "is_st"]].sort_values(["ts_code", "start_date"])
    flags = np.zeros(len(frame), dtype=bool)
    dates = frame["date"].to_numpy()
    for instrument, rows in frame.groupby("instrument", sort=False).indices.items():
        records = history[history["ts_code"].eq(instrument)]
        if records.empty:
            continue
        starts, ends = records["start_date"].to_numpy(), records["end_date"].to_numpy()
        record_st = records["is_st"].to_numpy(dtype=bool)
        rows = np.asarray(rows, dtype=np.int64)
        slot = np.searchsorted(starts, dates[rows], side="right") - 1
        valid = slot >= 0
        st_now = np.zeros(len(rows), dtype=bool)
        if valid.any():
            picked = slot[valid]
            still_open = pd.isna(ends[picked]) | (ends[picked] > dates[rows][valid])
            st_now[valid] = record_st[picked] & still_open
        flags[rows] = st_now
    return pd.Series(flags, index=frame.index)


def main() -> int:
    platforms = {name: read_platform_run(path) for name, path in RUNS.items()}
    end = max(pd.Timestamp(d).normalize() for p in platforms.values() for d in p["dates"])
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, pd.Timestamp("2018-01-01"), end,
                             market_cap_field="total_mv")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print("rows", len(frame), flush=True)

    if VALUE_CACHE.exists():
        values = pd.read_parquet(VALUE_CACHE)
        print("cached factor panel", values.shape, flush=True)
    else:
        raw = 1.0 / frame["raw_low"].pow(2) / frame["raw_volume"]
        frame["_factor"] = rolling_weighted_mean(frame, raw, 40).to_numpy(dtype=float)
        values = frame.pivot_table(index="date", columns="instrument", values="_factor",
                                   aggfunc="last").sort_index()
        values.to_parquet(VALUE_CACHE)
        print("factor panel cached", values.shape, flush=True)
    if CLOSE_CACHE.exists():
        close = pd.read_parquet(CLOSE_CACHE)
    else:
        close = frame.pivot(index="date", columns="instrument", values="close_qfq").sort_index()
        close.to_parquet(CLOSE_CACHE)

    flags = st_mask(frame)
    listing = pd.to_datetime(
        pd.read_parquet(STOCK_BASIC_PATH).drop_duplicates("ts_code").set_index("ts_code")["list_date"],
        format="%Y%m%d", errors="coerce",
    )
    age_days = frame["date"] - frame["instrument"].map(listing)
    young = age_days.dt.days.lt(365).fillna(False).to_numpy()
    st = flags.to_numpy()
    masks = {
        "unfiltered": np.ones(len(frame), dtype=bool),
        "no_st": ~st,
        "no_young": ~young,
        "no_st_no_young": (~st) & (~young),
    }
    key = frame[["date", "instrument"]]
    report: dict[str, object] = {"universes": {}}
    calendar = list(close.index)
    position = {d: i for i, d in enumerate(calendar)}
    for universe, mask in masks.items():
        report["universes"][universe] = {"rows": int(mask.sum())}

    for run, platform in platforms.items():
        dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
        cycle = int(platform.get("cycle") or 5)
        plat = np.array([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], dtype=float)
        fwd_rows = {}
        for date in dates:
            i = position.get(date)
            if i is None or i + 1 + cycle >= len(calendar):
                continue
            fwd_rows[date] = close.iloc[i + 1 + cycle] / close.iloc[i + 1] - 1.0
        fwd = pd.DataFrame(fwd_rows).T
        fwd.index = pd.to_datetime(fwd.index)
        print(run, "cycle", cycle, "fwd rows", len(fwd), flush=True)
        for universe, mask in masks.items():
            keep_set = set(map(tuple, key[mask].to_numpy()))
            series = []
            for date in dates:
                if date not in values.index or date not in fwd.index:
                    series.append(np.nan); continue
                a, b = values.loc[date], fwd.loc[date].reindex(values.columns)
                ok = a.notna() & b.notna()
                idx = [i for i, (d_, s_) in enumerate(zip([date] * len(a), a.index)) if ok.iloc[i] and (pd.Timestamp(d_), s_) in keep_set]
                if len(idx) < 100:
                    series.append(np.nan); continue
                av = a.iloc[idx].to_numpy(dtype=float); bv = b.iloc[idx].to_numpy(dtype=float)
                series.append(float(pd.Series(av).rank().corr(pd.Series(bv).rank())))
            s = np.array(series, dtype=float)
            n = min(len(s), len(plat))
            m = np.isfinite(s[:n]) & np.isfinite(plat[:n])
            delta = np.abs(s[:n][m] - plat[:n][m])
            corr = float(np.corrcoef(s[:n][m], plat[:n][m])[0, 1]) if m.sum() > 10 else float("nan")
            entry = {"n_shared": int(m.sum()), "mean_rank_ic": float(np.nanmean(s[:n][m])),
                     "mean_abs_delta": float(delta.mean()), "corr": corr,
                     "ic_std": float(np.nanstd(s[:n][m]))}
            report.setdefault(f"{run}_variants", {})[universe] = entry
            print("   %-16s n=%3d meanIC=%.4f delta=%.4f corr=%.3f icStd=%.3f" % (
                universe, entry["n_shared"], entry["mean_rank_ic"], entry["mean_abs_delta"], corr, entry["ic_std"]), flush=True)
        report[f"{run}_platform"] = {"mean_rank_ic": float(np.nanmean(plat)), "ic_std": float(np.nanstd(plat)), "n": int(np.isfinite(plat).sum())}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ic_by_universe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "ic_by_universe.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
