"""F-NET01 local reproduction alignment by universe and annualisation convention.

Findings this script tests (zero platform compute):
  * the platform's 2026-09-07 top-20 is 14 ST names pinned on one identical value
    (8.1244 / 8.1326 across two runs) -> the platform's ranking universe keeps ST;
  * the qualitygate3 local panel drops ST + recent listings, so for a factor whose
    extreme decile is ST-heavy the local rank-IC series and top-20 cannot match;
  * qualitygate3 also switched to compounded annualisation.

Output: research_reports/platform_alignment/fnet01-alignment-20260924/universe_fix.json
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
from platform_alignment_rules import annualized_turnover_cost  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    GROUPS,
    assign_groups,
    forward_returns,
    rolling_weighted_mean,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck"
PRICE_ROOT = CACHE / "qfq_rich/daily_batches"
CAP_ROOT = CACHE / "daily_basic_full_a"
OUT = PROJECT_ROOT / "research_reports/platform_alignment/fnet01-alignment-20260924"
RUNS = {
    "cycle5": (PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.results/6aa7cd283e7967143f8fb524.json", 5),
    "cycle10": (PROJECT_ROOT / "cluster-singletons-t10-20260921-candidates.results/6ab0f3d7ecb163ea7228ded7.json", 10),
}


def pit_st_flags(frame: pd.DataFrame, path: Path = NAMECHANGE_PATH) -> pd.Series:
    """Point-in-time ST flag per row, same rule as the loader's universe filter."""
    history = pd.read_parquet(path)
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
    platforms = {name: read_platform_run(path) for name, (path, _) in RUNS.items()}
    last_date = pd.Timestamp("2026-09-07")
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, pd.Timestamp("2018-01-01"), last_date,
                             market_cap_field="total_mv")
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    print("unfiltered rows", len(frame), flush=True)

    frame["_st"] = pit_st_flags(frame).to_numpy()
    listing = pd.to_datetime(
        pd.read_parquet(STOCK_BASIC_PATH).drop_duplicates("ts_code").set_index("ts_code")["list_date"],
        format="%Y%m%d", errors="coerce",
    )
    age_days = (frame["date"] - frame["instrument"].map(listing)).dt.days
    frame["_young"] = age_days.lt(365).fillna(False).to_numpy()
    print("st rows", int(frame["_st"].sum()), "young rows", int(frame["_young"].sum()), flush=True)

    raw = 1.0 / frame["raw_low"].pow(2) / frame["raw_volume"]
    frame["_factor"] = rolling_weighted_mean(frame, raw, 40).to_numpy(dtype=float)
    print("factor built", flush=True)
    calendar = list(pd.Index(sorted(frame["date"].unique())))
    close = frame.pivot(index="date", columns="instrument", values="close_qfq").reindex(calendar)

    universes = {
        "unfiltered": np.ones(len(frame), dtype=bool),
        "no_st": ~frame["_st"].to_numpy(),
        "no_young": ~frame["_young"].to_numpy(),
        "gate3_no_st_no_young": (~frame["_st"].to_numpy()) & (~frame["_young"].to_numpy()),
    }
    report: dict[str, object] = {
        "universe_rows": {name: int(mask.sum()) for name, mask in universes.items()},
        "st_share_rows": float(frame["_st"].mean()),
    }

    for name, (_, cycle) in RUNS.items():
        platform = platforms[name]
        dates = [pd.Timestamp(d).normalize() for d in platform["dates"]]
        direction = int(platform.get("direction") or 1)
        selected_group = GROUPS if direction == 1 else 1
        top_rows = [row for row in platform.get("top", []) if row.get("date")]
        top_date = max(pd.Timestamp(row["date"]).normalize() for row in top_rows)
        platform_top = sorted(str(row["symbol"]) for row in top_rows
                              if pd.Timestamp(row["date"]).normalize() == top_date)
        plat_series = np.array([np.nan if v is None else float(v) for v in platform["rank_ic_values"]], dtype=float)
        returns = forward_returns(close, calendar, dates, cycle, 1)
        base = frame[["date", "instrument", "_factor", "_st", "_young"]][frame["date"].isin(dates)]
        data = base.merge(returns, on=["date", "instrument"], how="left")
        entry: dict[str, object] = {
            "cycle": cycle,
            "platform": {
                "rank_ic": platform["metrics"].get("Rank_IC"),
                "ic_mean": platform["metrics"].get("IC_mean"),
                "gross": platform["group_metrics"].get(selected_group, {}).get("excessAnnualized"),
                "turnover": platform["group_metrics"].get(selected_group, {}).get("turnoverRate"),
                "top20": platform_top,
                "top20_date": top_date.strftime("%Y-%m-%d"),
                "top20_distinct_values": len({str(row["factor1"]) for row in top_rows}),
            },
            "universes": {},
        }
        p = entry["platform"]
        p["net"] = p["gross"] - annualized_turnover_cost(p["turnover"], cycle) if p["gross"] and p["turnover"] else None

        for universe, mask in universes.items():
            mask_series = pd.Series(mask, index=frame.index)
            # _st / _young are carried through the merge, so rebuild the mask on data
            if universe == "unfiltered":
                keep = np.ones(len(data), dtype=bool)
            elif universe == "no_st":
                keep = ~data["_st"].to_numpy()
            elif universe == "no_young":
                keep = ~data["_young"].to_numpy()
            else:
                keep = (~data["_st"].to_numpy()) & (~data["_young"].to_numpy())
            sub = data[keep].dropna(subset=["_factor", "forward_return"])
            previous: dict[int, set[str]] = {}
            excess_arith, held_comp, bench_comp, turnovers, rank_ics = [], [], [], [], []
            for date in dates:
                current = sub[sub["date"].eq(date)]
                if len(current) < GROUPS * 10:
                    continue
                current = current.copy()
                current["group"] = assign_groups(current["_factor"], None)
                held = current[current["group"].eq(selected_group)]
                bench_return = float(current["forward_return"].mean())
                held_return = float(held["forward_return"].mean())
                excess_arith.append(held_return - bench_return)
                held_comp.append(1.0 + held_return)
                bench_comp.append(1.0 + bench_return)
                members = set(held["instrument"])
                old = previous.get(selected_group)
                if old:
                    turnovers.append(1.0 - len(members & old) / len(members))
                previous[selected_group] = members
                rank_ics.append(float(current["_factor"].rank().corr(current["forward_return"].rank())))
            years = len(excess_arith) * cycle / 252.0
            gross_arith = float(np.sum(excess_arith)) / years
            gross_comp = float(np.prod(held_comp)) ** (1 / years) - float(np.prod(bench_comp)) ** (1 / years)
            turnover = float(np.mean(turnovers)) if turnovers else None
            cost = annualized_turnover_cost(turnover, cycle)
            series = np.array(rank_ics, dtype=float)
            n = min(len(series), len(plat_series))
            ok = np.isfinite(series[:n]) & np.isfinite(plat_series[:n])
            entry["universes"][universe] = {
                "n_periods": len(excess_arith),
                "stocks_per_date_mean": float(sub.groupby("date").size().mean()),
                "mean_rank_ic": float(np.nanmean(series)),
                "ic_series_corr": float(np.corrcoef(series[:n][ok], plat_series[:n][ok])[0, 1]) if ok.sum() > 10 else None,
                "ic_series_mean_abs_delta": float(np.mean(np.abs(series[:n][ok] - plat_series[:n][ok]))),
                "gross_arithmetic": gross_arith,
                "gross_compounded": gross_comp,
                "turnover": turnover,
                "annual_cost": cost,
                "net_arithmetic": gross_arith - cost if cost else None,
                "net_compounded": gross_comp - cost if cost else None,
                "platform_net_delta_pp_compounded": (gross_comp - cost - p["net"]) * 100 if cost and p["net"] else None,
            }
            # top-20 diagnostic at the platform's saved top date
            if top_date in set(frame["date"].unique()):
                cross = frame[frame["date"].eq(top_date)]
                if universe == "no_st":
                    cross = cross[~cross["_st"]]
                elif universe == "no_young":
                    cross = cross[~cross["_young"]]
                elif universe == "gate3_no_st_no_young":
                    cross = cross[(~cross["_st"]) & (~cross["_young"])]
                cross = cross.dropna(subset=["_factor"])
                local_top = cross.sort_values(["_factor", "instrument"], ascending=[False, True]).head(20)["instrument"].tolist()
                entry["universes"][universe]["local_top20"] = local_top
                entry["universes"][universe]["top20_overlap"] = len(set(local_top) & set(platform_top))
            u = entry["universes"][universe]
            print("%-7s %-22s n=%3d stocks=%6.0f rankIC=%.4f corr=%.3f delta=%.4f grossA=%.4f grossC=%.4f turn=%.4f netC=%.4f overlap=%s" % (
                name, universe, u["n_periods"], u["stocks_per_date_mean"], u["mean_rank_ic"],
                u["ic_series_corr"] or float("nan"), u["ic_series_mean_abs_delta"], u["gross_arithmetic"],
                u["gross_compounded"], u["turnover"] or float("nan"), u["net_compounded"],
                u.get("top20_overlap")), flush=True)
        print("   platform %s: gross=%.4f turnover=%.4f net=%.4f rankIC=%.4f top20=%s distinct=%d" % (
            name, p["gross"], p["turnover"], p["net"], p["rank_ic"], None, p["top20_distinct_values"]), flush=True)
        report[name] = json.loads(json.dumps(entry, default=float))

        if name == "cycle5":
            st_of_top = frame[frame["date"].eq(top_date)].set_index("instrument")["_st"]
            report["platform_top20_st_flags"] = {
                "date": top_date.strftime("%Y-%m-%d"),
                "n_st": int(pd.Series({s: bool(st_of_top.get(s, False)) for s in platform_top}).sum()),
                "n": len(platform_top),
            }
            print("   platform top20 ST count:", report["platform_top20_st_flags"], flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "universe_fix.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    print("saved", OUT / "universe_fix.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
