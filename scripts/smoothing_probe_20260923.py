"""Probe: does time-smoothing a member score keep S_i while cutting turnover?

The composite search showed that every high-S_i seat in the library also
carries 27-70% per-rebalance turnover, and the submitted pool already sits just
under the 0.30 monthly turnover floor.  A cheap way out would be to smooth the
signal: a rolling mean keeps the cross-sectional ranking information but
stabilises the top-decile membership, which is exactly what turnover measures.

Each smoothed score is re-standardised cross-sectionally before scoring, and
scored with the same A inputs and C proxy as the pool scenarios.  Offline only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
import high_ic_composite_search_20260923 as hic  # noqa: E402
import pool_scenario_weighted_20260923 as pss  # noqa: E402

OUT = Path("research_reports/platform_alignment/high-ic-composite-20260923")
MEMBERS = [
    "t10_size_plus_impact_bm", "t10_size_plus_impact_fscore", "t10_size_plus_impact",
    "t10_size_plus_impact_aggregate", "t10_size_plus_impact_g13", "t10_size_plus_impact_downside",
    "reversal_chip_turn_paper", "reversal_turn_paper", "reversal_chip_turn_size_eq",
    "book_to_market_lf_minus_size", "impact60", "size_only",
]
WINDOWS = (2, 3, 6, 10)
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
WEAKEST = "size_only"


def smooth_column(frame: pd.DataFrame, values: pd.Series, window: int) -> pd.Series:
    wide = pd.DataFrame({
        "date": frame["date"], "instrument": frame["instrument"], "v": values.to_numpy(),
    }).pivot(index="date", columns="instrument", values="v")
    smoothed = wide.rolling(window=window, min_periods=1).mean()
    long = smoothed.stack(dropna=False)
    key = pd.MultiIndex.from_arrays([frame["date"], frame["instrument"]])
    return pd.Series(long.reindex(key).to_numpy(), index=frame.index)


def zscore_by_date(frame: pd.DataFrame, values: pd.Series) -> pd.Series:
    tmp = pd.DataFrame({"date": frame["date"].to_numpy(), "v": values.to_numpy()})
    grouped = tmp.groupby("date", sort=False)["v"]
    mean = grouped.transform("mean")
    std = grouped.transform(lambda s: s.std(ddof=0))
    return (tmp["v"] - mean) / std.replace(0, np.nan)


def main() -> int:
    built, scores, payload = hic._load()
    sf, returns, dates = payload
    frame = sf[["date", "instrument"]].reset_index(drop=True)
    scores = scores.reset_index(drop=True)
    extra = {}
    for member in MEMBERS:
        if member not in scores.columns:
            continue
        for window in WINDOWS:
            smoothed = smooth_column(frame, scores[member], window)
            extra[f"{member}__s{window}"] = zscore_by_date(frame, smoothed)
    scores2 = pd.concat([scores, pd.DataFrame(extra)], axis=1)
    built2 = list(built) + [
        dict(key=k, handler=k, direction="1", name=k.upper(), platform_net=None, si=None)
        for k in extra
    ]
    keys, blocks = hic.build_blocks(built2, scores2, payload)
    index = {k: i for i, k in enumerate(keys)}
    ds = np.asarray([b[0].to_datetime64() for b in blocks], dtype="datetime64[ns]")
    mask5 = np.ones(len(ds), bool)

    def single_metrics(members: tuple[int, ...]) -> dict:
        res = pss.evaluate_seats(blocks, [(members, 1.0)])
        summary = e._summary(res["held"], res["gross"], res["turn"], res["counts"],
                             res["valid"].astype(bool), ds, 10, "5y", mask5)
        ic = hic.ic_stats(res["rank_ics"], res["ics"], ds, mask5)
        return dict(s_i=ic["s_i"], rank_ic=ic["rank_ic"], ic_ir=ic["ic_ir"], win=ic["win"],
                    turnover=(summary["turnover_pct"] or 0.0) / 100.0,
                    net=summary["net_excess_pct"], sharpe=summary["sharpe_after_cost"],
                    dd=summary["max_drawdown_pct"])

    def pool_metrics(seat_members: list[tuple[int, ...]], seat_si: list[float]) -> dict:
        weight = 1.0 / len(seat_members)
        res = pss.evaluate_seats(blocks, [(m, weight) for m in seat_members])
        summary = e._summary(res["held"], res["gross"], res["turn"], res["counts"],
                             res["valid"].astype(bool), ds, 10, "5y", mask5)
        ic = hic.ic_stats(res["rank_ics"], res["ics"], ds, mask5)
        na = min(float(np.mean(seat_si)) / 0.08, 0.7)
        nb = min((ic["s_i"] or 0.0) / 0.06, 1.0)
        turn = (summary["turnover_pct"] or 0.0) / 100.0
        rawc = (max(summary["net_excess_pct"] or 0.0, 0.0) / 100.0 / max(2 * turn, 0.3)
                * (summary["sharpe_after_cost"] or 0.0)
                * (1 - 1.2 * (summary["max_drawdown_pct"] or 0.0) / 100.0))
        nc = min(max(rawc / 0.6, 0.0), 1.0)
        return dict(na=na, nb=nb, nc=nc, comb=0.20 * na + 0.35 * nb + 0.45 * nc,
                    net=summary["net_excess_pct"], monthly_turnover=2 * turn,
                    sharpe=summary["sharpe_after_cost"], dd=summary["max_drawdown_pct"])

    platform_si = {m["key"]: m.get("si") for m in built2}
    rows = []
    seed_si = [float(platform_si[k]) for k in POOL]

    def seat_si_of(key: str, fallback: float) -> float:
        value = platform_si.get(key)
        return float(value) if value else fallback

    base = pss.evaluate_seats(blocks, [((index[k],), 0.2) for k in POOL])
    base_summary = e._summary(base["held"], base["gross"], base["turn"], base["counts"],
                              base["valid"].astype(bool), ds, 10, "5y", mask5)
    rows.append(dict(key="SEED-POOL", window=0, pool_na=0.239,
                     pool_net=base_summary["net_excess_pct"],
                     pool_monthly_turnover=2 * (base_summary["turnover_pct"] or 0) / 100.0,
                     pool_nc=1.0, pool_comb=0.637, s_i=float("nan"),
                     turnover=float("nan"), net=float("nan"), sharpe=float("nan")))

    for key in list(extra):
        member_key = key.split("__s")[0]
        window = int(key.split("__s")[1])
        single = single_metrics((index[key],))
        seat_si = [float(platform_si[k]) for k in POOL if k != WEAKEST] + [single["s_i"]]
        seats = [(index[k],) for k in POOL if k != WEAKEST] + [(index[key],)]
        pool = pool_metrics(seats, seat_si)
        rows.append(dict(key=member_key, window=window, pool_na=pool["na"], pool_net=pool["net"],
                         pool_monthly_turnover=pool["monthly_turnover"], pool_nc=pool["nc"],
                         pool_comb=pool["comb"], s_i=single["s_i"], turnover=single["turnover"],
                         net=single["net"], sharpe=single["sharpe"]))
    frame_out = pd.DataFrame(rows)
    frame_out.to_csv(OUT / "smoothing_probe.csv", index=False)
    show = frame_out[frame_out["key"] != "SEED-POOL"].sort_values("s_i", ascending=False)
    print(show[["key", "window", "s_i", "turnover", "net", "sharpe", "pool_na", "pool_nc",
                "pool_monthly_turnover", "pool_comb"]].to_string(index=False))
    print()
    print(frame_out[frame_out["key"] == "SEED-POOL"][
        ["pool_na", "pool_net", "pool_monthly_turnover", "pool_nc", "pool_comb"]].to_string(index=False))
    best = show.sort_values("pool_comb", ascending=False).head(8)
    print()
    print("best pool scenarios (replacing SIZE):")
    print(best[["key", "window", "s_i", "turnover", "pool_na", "pool_nc",
                "pool_monthly_turnover", "pool_comb"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
