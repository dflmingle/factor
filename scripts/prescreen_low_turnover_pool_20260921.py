"""Offline pre-screen of candidate pool compositions under the official A/B/C shape.

Extends the aligned representative set with three low-turnover members built
locally (book-to-market minus size, book-to-market plus Amihud illiquidity, and
pure Amihud illiquidity), evaluates every subset with at least five members, and
ranks them by the documented competition formula shape:

    Comb = 0.20 * min(rawA/0.08, 1) + 0.45 * min(rawC/0.6, 1)
    rawC = max(Rex,0)/max(2*turnover,0.3) * SR * (1 - 1.2*MaxDD)

The B component needs post-effective records that do not exist yet, so it is
excluded.  This is a local proxy, not an official pool score.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
import financial_factor_local as ffl  # noqa: E402

OUT = Path("research_reports/platform_alignment/low-turnover-prescreen-20260921")
SIGNALS = Path("research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl")
PRICE_ROOT = e.DEFAULT_PRICE_ROOT
CATALOG = Path(
    "quantlab/.quantlab/cache/research/cn_equity/reports/"
    "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
    "turnoverdiag1_qualitygate3/all_factor_local_compare.json"
)

# member key -> saved platform record name (cycle 10 preferred when several exist)
MEMBER_RECORDS = {
    "SIZE": "SIZE-ONLY-20260911",
    "H03": "H03-T10-SINGLE",
    "RET40": "OSR2-RET40",
    "DD120": "OSR2-DD120",
    "CHIP250": "NONHT-CHIP-COST-250",
    "DD60": "OSR2-DD60",
    "ASSET_GROWTH": "paper-derived-asset-growth",
    "BM_SIZE": "VERIFY10-E260910-04",
    "BM_ILLIQ": "VERIFY10-F260910-12",
    "ILLIQ": "VERIFY10-G260910-13",
}

# Platform-side A inputs (|RankIC| x |ICIR| x direction win rate), 10-day/5-year records.
PLATFORM_S = {
    "SIZE": 0.01024,
    "H03": 0.01579,
    "RET40": 0.01935,
    "CHIP250": 0.00927,
    "DD120": 0.00387,
    "DD60": 0.00242,
    "ASSET_GROWTH": 0.00095,
    "BM_SIZE": 0.01691,
    "BM_ILLIQ": 0.01540,
    "ILLIQ": 0.01119,
}


def build_amihud(dates: list[pd.Timestamp]) -> pd.Series:
    files = sorted(glob.glob(str(PRICE_ROOT / "*.parquet")))
    start = (dates[0] - pd.Timedelta(days=150)).strftime("%Y%m%d")
    end = (dates[-1] + pd.Timedelta(days=5)).strftime("%Y%m%d")
    use = [f for f in files if start <= Path(f).name.split("batch_")[1][:8] <= end]
    parts = [pd.read_parquet(f, columns=["date", "instrument", "close", "volume"]) for f in use]
    frame = pd.concat(parts, ignore_index=True).sort_values(["instrument", "date"], ignore_index=True)
    frame["turnover_value"] = frame["close"] * frame["volume"]
    frame["ret"] = frame.groupby("instrument", sort=False)["close"].transform(lambda s: s / s.shift(1) - 1.0)
    frame["illiq"] = frame["ret"].abs() / (frame["turnover_value"].fillna(0.0) + 1.0)
    frame["amihud"] = frame.groupby("instrument", sort=False)["illiq"].transform(
        lambda s: s.rolling(60, min_periods=45).sum() / 60.0
    )
    return frame.dropna(subset=["amihud"])[["date", "instrument", "amihud"]]


def load_member_tiers() -> dict[str, dict[str, object]]:
    """Return {member key: {tier, net_delta_pp, record}} from the local catalog."""
    if not CATALOG.exists():
        return {}
    payload = json.loads(CATALOG.read_text())
    by_name: dict[str, dict] = {}
    for row in payload.get("results", []):
        name = str(row.get("name") or "")
        current = by_name.get(name)
        if current is None or (row.get("cycle") == 10 and current.get("cycle") != 10):
            by_name[name] = row
    tiers: dict[str, dict[str, object]] = {}
    for key, record_name in MEMBER_RECORDS.items():
        row = by_name.get(record_name)
        if not row:
            tiers[key] = {"tier": "unknown", "net_delta_pp": None, "record": record_name}
            continue
        tiers[key] = {
            "tier": row.get("net_tier") or "unknown",
            "net_delta_pp": row.get("local_net_delta_pp"),
            "record": record_name,
        }
    return tiers


def main() -> None:
    import pickle

    with SIGNALS.open("rb") as fh:
        sf, raw, returns, dates = pickle.load(fh)

    _, base_candidates = e._load_candidates(e.DEFAULT_ALIGNMENT_REPORT)
    keep = {"SIZE", "H03", "RET40", "DD120", "CHIP250", "DD60", "ASSET_GROWTH"}
    candidates = [c for c in base_candidates if c["key"] in keep]

    print("loading full-A panel", flush=True)
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, e.DATA_START, e.END)
    frame = e.select_market_cap(frame, "total_mv").sort_values(["instrument", "date"], ignore_index=True)

    print("financial snapshot (book-to-market)", flush=True)
    cache = ffl.load_financial_cache(e.DEFAULT_FINANCIAL_ROOT)
    ffl._FINANCIAL_CACHE = cache
    selected = ffl._base_signal(frame, dates)
    selected["bm_rank"] = ffl._rank(selected["book_to_market_ratio_lf"], selected["date"])

    print("amihud", flush=True)
    amihud = build_amihud(dates)

    grid = sf[["date", "instrument"]].copy()
    grid = grid.merge(
        selected[["date", "instrument", "bm_rank", "total_mv"]], on=["date", "instrument"], how="left"
    )
    grid = grid.merge(amihud, on=["date", "instrument"], how="left")
    grid["mkt_rank"] = grid.groupby("date")["total_mv"].rank(pct=True)
    grid["illiq_rank"] = grid.groupby("date")["amihud"].rank(pct=True)
    coverage = grid[["bm_rank", "illiq_rank"]].notna().mean().round(3).to_dict()
    print("coverage", coverage, flush=True)

    raw = dict(raw)
    raw["bm_size"] = pd.Series((grid["bm_rank"] - grid["mkt_rank"]).to_numpy())
    raw["bm_illiq"] = pd.Series((grid["bm_rank"] + grid["illiq_rank"]).to_numpy())
    raw["illiq"] = pd.Series(grid["illiq_rank"].to_numpy())

    candidates += [
        dict(key="BM_SIZE", handler="bm_size", direction=1, name="VERIFY10-E260910-04"),
        dict(key="BM_ILLIQ", handler="bm_illiq", direction=1, name="VERIFY10-F260910-12"),
        dict(key="ILLIQ", handler="illiq", direction=1, name="VERIFY10-G260910-13"),
    ]
    keys = [c["key"] for c in candidates]
    print("members:", keys, flush=True)
    tiers = load_member_tiers()
    print("member net tiers:", {k: (v["tier"], round(v["net_delta_pp"], 2) if isinstance(v["net_delta_pp"], (int, float)) else None) for k, v in tiers.items()}, flush=True)

    scores = e._competition_cross_sectional_scores(sf, raw, candidates)
    blocks = e._build_blocks(sf, scores, returns, dates, keys)
    ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))
    bitmasks, masks, sizes, labels = e._combination_catalog(keys)
    print("evaluating %d subsets" % len(bitmasks), flush=True)
    held, gross, turn, counts, valid = e._evaluate_combinations_numba(fs, fr, fi, offsets, masks, sizes)

    windows = {
        "full": np.ones(len(ds), bool),
        "train": ds <= e.TRAIN_END.to_datetime64(),
        "test": ds > e.TRAIN_END.to_datetime64(),
        "recent": ds >= e.RECENT_START.to_datetime64(),
    }
    rows = []
    for j, mask in enumerate(masks):
        if sizes[j] < 5:
            continue
        row = {"components": "+".join(k for i, k in enumerate(keys) if mask[i]), "factor_count": int(sizes[j])}
        for name, window in windows.items():
            summary = e._summary(
                held[j], gross[j], turn[j], counts[j], valid[j].astype(bool), ds, 10, window, windows[name]
            )
            row.update({f"{name}_{k}": v for k, v in summary.items()})
        members = row["components"].split("+")
        member_tiers = [tiers.get(m, {"tier": "unknown", "net_delta_pp": None}) for m in members]
        proxy = [t for t, m in zip(member_tiers, members) if t["tier"] == "net_proxy"]
        row["net_close_count"] = sum(1 for t in member_tiers if t["tier"] == "net_close")
        row["net_proxy_count"] = len(proxy)
        row["net_other_count"] = sum(
            1 for t in member_tiers if t["tier"] not in {"net_close", "net_proxy"}
        )
        if proxy:
            worst = max(proxy, key=lambda t: abs(t["net_delta_pp"] or 0.0))
            row["worst_proxy_member"] = str(worst["record"])
            row["worst_proxy_delta_pp"] = worst["net_delta_pp"]
        else:
            row["worst_proxy_member"] = ""
            row["worst_proxy_delta_pp"] = None
        raw_a = float(np.mean([PLATFORM_S[m] for m in members]))
        net = row["full_net_excess_pct"] / 100.0
        turnover = row["full_turnover_pct"] / 100.0
        sharpe = row["full_sharpe_after_cost"]
        drawdown = row["full_max_drawdown_pct"] / 100.0
        raw_c = max(net, 0.0) / max(2 * turnover, 0.3) * sharpe * (1 - 1.2 * drawdown)
        row["raw_a"] = raw_a
        row["NA_proxy"] = min(raw_a / 0.08, 1.0)
        row["NC_proxy"] = min(max(raw_c / 0.6, 0.0), 1.0)
        row["comb_proxy"] = 0.20 * row["NA_proxy"] + 0.45 * row["NC_proxy"]
        rows.append(row)

    table = pd.DataFrame(rows).sort_values("comb_proxy", ascending=False)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "prescreen_all_combinations.csv", index=False)

    cols = ["components", "factor_count", "comb_proxy", "NA_proxy", "NC_proxy",
            "full_net_excess_pct", "full_turnover_pct", "test_net_excess_pct", "recent_net_excess_pct",
            "net_close_count", "net_proxy_count", "worst_proxy_member", "worst_proxy_delta_pp"]
    print("\nTOP 15 by official-shaped proxy")
    print(table[cols].head(15).to_string(index=False))
    print("\nbest by pool size")
    best = table.loc[table.groupby("factor_count")["comb_proxy"].idxmax()][cols].sort_values("factor_count")
    print(best.to_string(index=False))


if __name__ == "__main__":
    main()
