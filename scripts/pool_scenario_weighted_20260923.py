"""Seat-weighted pool scenarios for the high-IC composite search.

The composite search scored each candidate as a standalone factor, but a pool
seat is only one of five equal weights: a 2-member composite seat contributes
1/5 * 1/2 to each of its member signals.  This script rebuilds the pool score
with those weights, recomputes the competition C proxy (net, turnover, Sharpe,
drawdown) and the A/B proxies, and ranks replacement / addition scenarios.

Offline only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
import high_ic_composite_search_20260923 as hic  # noqa: E402

OUT = Path("research_reports/platform_alignment/high-ic-composite-20260923")
CYCLE = 10
GROUPS = 10
TOP_FRACTION = 0.1

POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
WEAKEST = "size_only"
MIN_CANDIDATE_SI = float(os.environ.get("PSS_MIN_SI", "0.033"))


def block_values(scores: np.ndarray, members: tuple[int, ...]) -> np.ndarray:
    """Mean z-score inside one seat (NaN propagates)."""
    return scores[:, list(members)].mean(axis=1)


def evaluate_seats(blocks, seats: list[tuple[tuple[int, ...], float]]) -> dict:
    """seats = [((member indices), weight)], weights must sum to 1."""
    periods = len(blocks)
    held = np.full(periods, np.nan)
    gross = np.full(periods, np.nan)
    turn = np.full(periods, np.nan)
    counts = np.zeros(periods, dtype=np.int32)
    valid_period = np.zeros(periods, dtype=np.uint8)
    rank_ics = np.full(periods, np.nan)
    ics = np.full(periods, np.nan)
    previous: set[int] = set()
    for p, (_date, instruments, forward, scores) in enumerate(blocks):
        value = np.zeros(len(instruments))
        ok = np.isfinite(forward)
        for members, weight in seats:
            seat = block_values(scores, members)
            ok &= np.isfinite(seat)
            value = value + weight * np.nan_to_num(seat)
        idx = np.flatnonzero(ok)
        if len(idx) < GROUPS * 10:
            continue
        v = value[idx]
        r = forward[idx]
        if np.std(v) == 0 or np.std(r) == 0:
            continue
        top_n = int(len(idx) * TOP_FRACTION)
        order = np.argsort(-v)[:top_n]
        selected = set(instruments[idx][order].tolist())
        if previous:
            turn[p] = 1.0 - len(selected & previous) / len(selected)
        previous = selected
        held[p] = float(r[order].mean())
        gross[p] = held[p] - float(r.mean())
        counts[p] = len(idx)
        valid_period[p] = 1
        rank_ics[p] = float(np.corrcoef(rankdata(v), rankdata(r))[0, 1])
        ics[p] = float(np.corrcoef(v, r)[0, 1])
    return dict(held=held, gross=gross, turn=turn, counts=counts, valid=valid_period,
                rank_ics=rank_ics, ics=ics)


def main() -> int:
    built, scores, payload = hic._load()
    keys, blocks = hic.build_blocks(built, scores, payload)
    meta = {m["key"]: m for m in built}
    meta.setdefault("f_i10_01", dict(key="f_i10_01", name="SIZE+IMPACT-EW", platform_net=None, si=None))
    index = {k: i for i, k in enumerate(keys)}
    ds = np.asarray([b[0].to_datetime64() for b in blocks], dtype="datetime64[ns]")
    singles = pd.read_csv(OUT / "member_singles_shard0.csv").set_index("key")
    search = pd.concat([pd.read_csv(p) for p in sorted(OUT.glob("composite_search_shard*.csv"))],
                       ignore_index=True)

    def seat_si(key: str) -> float:
        platform = meta.get(key, {}).get("si")
        return float(platform) if platform else float(singles.loc[key, "5y_s_i"])

    def pool_metrics(seat_members: list[tuple[int, ...]], seat_keys: list[str]) -> dict:
        weight = 1.0 / len(seat_members)
        seats = [(m, weight) for m in seat_members]
        res = evaluate_seats(blocks, seats)
        mask = np.ones(len(ds), bool)
        summary = e._summary(res["held"], res["gross"], res["turn"], res["counts"],
                             res["valid"].astype(bool), ds, CYCLE, "5y", mask)
        pool_ic = hic.ic_stats(res["rank_ics"], res["ics"], ds, mask)
        seat_values = [seat_si(k) for k in seat_keys]
        na = min(float(np.mean(seat_values)) / 0.08, 0.7)
        nb = min((pool_ic["s_i"] or 0.0) / 0.06, 1.0)
        turnover_ratio = float(summary["turnover_pct"] or 0.0) / 100.0
        rawc = (max(float(summary["net_excess_pct"] or 0.0), 0.0) / 100.0
                / max(2 * turnover_ratio, 0.3)
                * float(summary["sharpe_after_cost"] or 0.0)
                * (1 - 1.2 * float(summary["max_drawdown_pct"] or 0.0) / 100.0))
        nc = min(max(rawc / 0.6, 0.0), 1.0)
        return dict(na=na, nb=nb, nc=nc, comb=0.20 * na + 0.35 * nb + 0.45 * nc,
                    net=summary["net_excess_pct"], turnover=turnover_ratio,
                    monthly_turnover=2 * turnover_ratio,
                    sharpe=summary["sharpe_after_cost"], dd=summary["max_drawdown_pct"],
                    pool_s=pool_ic["s_i"] or 0.0, seat_si=[round(v, 5) for v in seat_values])

    rows = []
    base_members = [(index[k],) for k in POOL]
    rows.append(dict(tag="seed(替换C)", members="+".join(POOL), **pool_metrics(base_members, POOL)))

    for key in [k for k in keys if k not in POOL and seat_si(k) >= MIN_CANDIDATE_SI]:
        for tag, keep in (("replace-SIZE", [k for k in POOL if k != WEAKEST]), ("add-6th", POOL)):
            seat_keys = keep + [key]
            seat_members = [(index[k],) for k in keep] + [(index[key],)]
            rows.append(dict(tag=tag, members="+".join(seat_keys),
                             **pool_metrics(seat_members, seat_keys)))

    composites = search[search["size"] >= 2].sort_values("5y_s_i", ascending=False)
    composites = composites[composites["5y_s_i"] >= MIN_CANDIDATE_SI]
    shard = os.environ.get("PSS_SHARD", "")
    if shard:
        index_part, total = (int(part) for part in shard.split("/"))
        composites = composites.iloc[index_part::total]
    print(f"composite candidates: {len(composites)}", flush=True)
    for n, (_, row) in enumerate(composites.iterrows()):
        members = tuple(index[k] for k in row["members"].split("|"))
        cand_si = float(row["5y_s_i"])
        for tag, keep in (("replace-SIZE", [k for k in POOL if k != WEAKEST]), ("add-6th", POOL)):
            seat_keys = keep + [row["selection"]]
            seat_members = [(index[k],) for k in keep] + [members]
            metrics = pool_metrics(seat_members, keep + [keep[0]])
            seat_values = [seat_si(k) for k in keep] + [cand_si]
            na = min(float(np.mean(seat_values)) / 0.08, 0.7)
            metrics["na"] = na
            metrics["seat_si"] = [round(v, 5) for v in seat_values]
            metrics["comb"] = 0.20 * na + 0.35 * metrics["nb"] + 0.45 * metrics["nc"]
            rows.append(dict(tag=tag, members="+".join(seat_keys), **metrics))
        if (n + 1) % 100 == 0:
            print(f"  {n+1}/{len(composites)}", flush=True)
    frame = pd.DataFrame(rows).sort_values("comb", ascending=False)
    if shard:
        index_part, _ = (int(part) for part in shard.split("/"))
        frame.to_csv(OUT / f"pool_scenarios_shard{index_part}.csv", index=False)
        print("shard written", flush=True)
        return 0
    frame.to_csv(OUT / "pool_scenarios_weighted.csv", index=False)
    seed = frame[frame["tag"].str.startswith("seed")].iloc[0]
    print("seed: NA %.3f NB %.3f NC %.3f Comb %.3f net %.2f%% monthly turnover %.1f%%"
          % (seed["na"], seed["nb"], seed["nc"], seed["comb"], seed["net"],
             seed["monthly_turnover"] * 100))
    for _, r in frame.head(18).iterrows():
        print(f"{r['tag']:12s} {r['members'][:92]:92s} NA {r['na']:.3f} NB {r['nb']:.3f} "
              f"NC {r['nc']:.3f} Comb {r['comb']:.3f} net {r['net']:.2f}% "
              f"mturn {r['monthly_turnover']*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
