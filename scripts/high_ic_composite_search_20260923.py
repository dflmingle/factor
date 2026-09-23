"""Offline search for high-IC composite pool seats (2026-09-23).

Motivation: the competition A component scores each seat as

    S_i^A = |RankIC| * |ICIR| * IC win rate

against a 0.08 anchor, so a pool full of 0.010-0.017 seats caps NA around
0.24.  Multi-signal composites already proved this point inside our own pool
(T10-ADD-BM scores 0.0373 while its parents score 0.010-0.017), because
averaging weakly correlated signals raises ICIR without hurting the mean IC.

This script searches 2- and 3-member composites built from the 54 aligned
ten-day handlers already reproduced locally, using the qualitygate3 rule set:

* every candidate is oriented by the sign of its own five-year mean IC,
* S_i is computed on the exact per-period IC series at the 10-day cycle,
* per-rebalance turnover is the group-overlap turnover of the top decile,
* candidates must keep per-rebalance turnover <= 14% so that a month with two
  or three unified rebalances stays at or below the 0.30 C denominator floor,
* each candidate is also scored as an extra pool seat and as a SIZE
  replacement inside the currently submitted pool.

Offline only: no platform calls, no new factor runs.
"""
from __future__ import annotations

import itertools
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402

OUT = Path("research_reports/platform_alignment/high-ic-composite-20260923")
SIGNALS = Path("research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl")
CACHE = Path("research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl")

RULE_VERSION = "full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate3"
CYCLE = 10
WINDOWS = (("5y", None), ("recent", pd.Timestamp("2026-01-01")))
RECENT = pd.Timestamp("2026-01-01")

# currently submitted pool (替换C): SIZE / H03 / T10-ADD-BM / VERIFY10-E / VERIFY10-F
POOL = [
    "size_only",
    "impact60",
    "t10_size_plus_impact_bm",
    "book_to_market_lf_minus_size",
    "book_to_market_lf_plus_impact",
]
WEAKEST_SEAT = "size_only"
TRIPLE_SHORTLIST_MIN_NET = 5.0
MAX_TURNOVER = 0.14


def _load() -> tuple[list[dict], pd.DataFrame, list[tuple]]:
    sf, _raw, returns, dates = pickle.load(SIGNALS.open("rb"))
    cached = pickle.load(CACHE.open("rb"))
    built = list(cached["built"])
    keys = [m["key"] for m in built]
    scores = cached["scores"][keys].copy()
    return built, scores, (sf, returns, dates)


def build_blocks(built: list[dict], scores: pd.DataFrame, payload) -> tuple[list[str], list[tuple]]:
    sf, returns, dates = payload
    keys = [m["key"] for m in built]
    # F-I10-01 = equal-weight standardised size + impact (a legal single formula).
    rho = scores["size_only"].corr(scores["impact60"])
    scores = scores.copy()
    scores["f_i10_01"] = (scores["size_only"] + scores["impact60"]) / np.sqrt(2 * (1 + rho))
    keys = keys + ["f_i10_01"]
    built = built + [
        dict(key="f_i10_01", handler="f_i10_01", direction="1", name="SIZE+IMPACT-EW", platform_net=None,
             si=None)
    ]
    blocks = e._build_blocks(sf, scores, returns, dates, keys)
    return keys, blocks


def ic_stats(rank_ics: np.ndarray, ics: np.ndarray, ds: np.ndarray, mask: np.ndarray) -> dict:
    r = rank_ics[mask]
    c = ics[mask]
    r = r[np.isfinite(r)]
    c = c[np.isfinite(c)]
    if len(r) == 0 or len(c) < 3:
        return dict(periods=0, rank_ic=None, ic_mean=None, ic_ir=None, win=None, s_i=None, direction=None)
    mean_r = float(np.mean(r))
    mean_c = float(np.mean(c))
    std_c = float(np.std(c, ddof=1)) if len(c) > 1 else 0.0
    direction = 1 if mean_c >= 0 else 0
    win = float(np.mean(c > 0.02)) if direction == 1 else float(np.mean(c < -0.02))
    ic_ir = mean_c / std_c if std_c > 0 else 0.0
    s_i = abs(mean_r) * abs(ic_ir) * win
    return dict(
        periods=len(c), rank_ic=mean_r, ic_mean=mean_c, ic_ir=ic_ir, win=win, s_i=s_i, direction=direction
    )


def evaluate(
    members: tuple[int, ...],
    keys: list[str],
    blocks: list[tuple],
    ds: np.ndarray,
    portfolio: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> dict:
    rank_ics, ics = e._exact_period_ics(members, blocks)
    held, gross, turn, counts, valid = portfolio
    out: dict = {"selection": "+".join(keys[i] for i in members), "size": len(members)}
    for label, start in WINDOWS:
        mask = np.ones(len(ds), bool) if start is None else ds >= start.to_datetime64()
        summary = e._summary(held, gross, turn, counts, valid.astype(bool), ds, CYCLE, label, mask)
        out.update({f"{label}_{k}": v for k, v in summary.items() if k != "period_label"})
        out.update({f"{label}_{k}": v for k, v in ic_stats(rank_ics, ics, ds, mask).items()})
    return out


def portfolio_for(mask_row: np.ndarray, flat) -> tuple[np.ndarray, ...]:
    fs, fr, fi, offsets = flat
    masks = mask_row.reshape(1, -1).astype(bool)
    sizes = np.array([int(mask_row.sum())], dtype=np.int64)
    held, gross, turn, counts, valid = e._evaluate_combinations_numba(fs, fr, fi, offsets, masks, sizes)
    return held[0], gross[0], turn[0], counts[0], valid[0]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    merge_mode = os.environ.get("HIC_MERGE", "") == "1"
    shard = os.environ.get("HIC_SHARD", "")
    built, scores, payload = _load()
    keys, blocks = build_blocks(built, scores, payload)
    ds, offsets, fs, fr, fi, _text = e._flatten_blocks(blocks, len(keys))
    flat = (fs, fr, fi, offsets)
    meta = {m["key"]: m for m in built}
    meta.setdefault("f_i10_01", dict(key="f_i10_01", name="SIZE+IMPACT-EW", platform_net=None, si=None))
    print(f"members: {len(keys)}, periods: {len(blocks)}", flush=True)

    # ---- singles -----------------------------------------------------------
    singles_path = OUT / "member_singles_shard0.csv"
    if merge_mode:
        singles = pd.read_csv(singles_path)
    else:
        single_rows = []
        for idx, key in enumerate(keys):
            mask = np.zeros(len(keys), bool)
            mask[idx] = True
            row = evaluate((idx,), keys, blocks, ds, portfolio_for(mask, flat))
            row["key"] = key
            row["platform_net"] = meta[key].get("platform_net")
            row["platform_si"] = meta[key].get("si")
            single_rows.append(row)
            if idx % 10 == 0:
                print(f"  single {idx+1}/{len(keys)}", flush=True)
        singles = pd.DataFrame(single_rows)
        singles.to_csv(singles_path if not shard else OUT / f"member_singles_shard{shard.split('/')[0]}.csv", index=False)
    both = singles.dropna(subset=["platform_si"])
    if len(both):
        corr = float(np.corrcoef(both["5y_s_i"], both["platform_si"].astype(float))[0, 1])
        mae = float(np.mean(np.abs(both["5y_s_i"] - both["platform_si"].astype(float))))
        print(f"local vs platform S_i: corr={corr:.3f} MAE={mae:.5f}", flush=True)
    else:
        corr = mae = None

    singles_index = {k: i for i, k in enumerate(keys)}
    sorted_singles = singles.sort_values("5y_s_i", ascending=False)
    pair_universe = [singles_index[k] for k in sorted_singles["key"]]
    shortlist = [
        singles_index[k]
        for k in sorted_singles["key"]
        if float(meta[k].get("platform_net") or -99.0) >= TRIPLE_SHORTLIST_MIN_NET
    ]
    print(f"pair universe {len(pair_universe)}, triple shortlist {len(shortlist)}", flush=True)

    combos = [tuple(sorted(c)) for c in itertools.combinations(pair_universe, 2)]
    combos += [tuple(sorted(c)) for c in itertools.combinations(shortlist, 3)]
    combos = list(dict.fromkeys(combos))
    limit = int(os.environ.get("HIC_LIMIT", "0") or 0)
    if limit:
        combos = combos[:limit]
    if shard and not merge_mode:
        index, total = (int(part) for part in shard.split("/"))
        combos = combos[index::total]
    if merge_mode:
        combos = []
    print(f"candidate composites: {len(combos)}", flush=True)

    if merge_mode:
        shards = sorted(OUT.glob("composite_search_shard*.csv"))
        search = pd.concat([pd.read_csv(p) for p in shards], ignore_index=True)
        print(f"merged {len(shards)} shards -> {len(search)} composites", flush=True)
    else:
        mask_matrix = np.zeros((len(combos), len(keys)), dtype=np.uint8)
        for row, members in enumerate(combos):
            mask_matrix[row, list(members)] = 1
        sizes = mask_matrix.sum(axis=1).astype(np.int64)
        held, gross, turn, counts, valid = e._evaluate_combinations_numba(
            fs, fr, fi, offsets, mask_matrix.astype(bool), sizes
        )
        rows = []
        for row, members in enumerate(combos):
            out: dict = {
                "selection": "+".join(keys[i] for i in members),
                "size": len(members),
                "members": "|".join(keys[i] for i in members),
            }
            rank_ics, ics = e._exact_period_ics(members, blocks)
            for label, start in WINDOWS:
                wmask = np.ones(len(ds), bool) if start is None else ds >= start.to_datetime64()
                summary = e._summary(
                    held[row], gross[row], turn[row], counts[row], valid[row].astype(bool),
                    ds, CYCLE, label, wmask,
                )
                out.update({f"{label}_{k}": v for k, v in summary.items() if k != "period_label"})
                out.update({f"{label}_{k}": v for k, v in ic_stats(rank_ics, ics, ds, wmask).items()})
            rows.append(out)
            if (row + 1) % 250 == 0:
                print(f"  composite {row+1}/{len(combos)}", flush=True)
        search = pd.DataFrame(rows)
        if shard:
            index, _ = (int(part) for part in shard.split("/"))
            search.to_csv(OUT / f"composite_search_shard{index}.csv", index=False)
            print("shard written", flush=True)
            return 0
    search["turnover_ok"] = search["5y_turnover_pct"].astype(float) / 100.0 <= MAX_TURNOVER
    search.to_csv(OUT / "composite_search.csv", index=False)
    print("composite search written", flush=True)

    # ---- pool scenarios ----------------------------------------------------
    pool_idx = tuple(singles_index[k] for k in POOL)
    pool_members = [singles_index[k] for k in POOL]
    base_si = float(np.mean([float(meta[k].get("si") or 0.0) for k in POOL]))

    def pool_metrics(member_idx: tuple[int, ...], seat_si: list[float]) -> dict:
        mask = np.zeros(len(keys), bool)
        mask[list(member_idx)] = True
        h, g, t, c, v = e._evaluate_combinations_numba(
            fs, fr, fi, offsets, mask.reshape(1, -1), np.array([len(member_idx)], dtype=np.int64)
        )
        rk, ic = e._exact_period_ics(member_idx, blocks)
        wmask = np.ones(len(ds), bool)
        summary = e._summary(h[0], g[0], t[0], c[0], v[0].astype(bool), ds, CYCLE, "5y", wmask)
        pool_ic = ic_stats(rk, ic, ds, wmask)
        na = min(float(np.mean(seat_si)) / 0.08, 0.7)
        nb = min((pool_ic["s_i"] or 0.0) / 0.06, 1.0)
        turn_period = float(summary["turnover_pct"] or 0.0) / 100.0
        rawc = (
            max(float(summary["net_excess_pct"] or 0.0), 0.0) / 100.0
            / max(2 * turn_period, 0.3)
            * float(summary["sharpe_after_cost"] or 0.0)
            * (1 - 1.2 * float(summary["max_drawdown_pct"] or 0.0) / 100.0)
        )
        nc = min(max(rawc / 0.6, 0.0), 1.0)
        return dict(na=na, nb=nb, nc=nc, comb=0.20 * na + 0.35 * nb + 0.45 * nc,
                    net=summary["net_excess_pct"], turnover=turn_period,
                    sharpe=summary["sharpe_after_cost"], dd=summary["max_drawdown_pct"],
                    pool_s=pool_ic["s_i"] or 0.0)

    base_row = pool_metrics(pool_idx, [float(meta[k]["si"]) for k in POOL])
    base_row["members"] = "+".join(POOL)
    base_row["tag"] = "seed(替换C)"
    base_row["seat_si"] = [float(meta[k]["si"]) for k in POOL]

    cand = search[search["turnover_ok"]].sort_values("5y_s_i", ascending=False).head(limit or 150)
    pool_rows = [base_row]
    for _, r in cand.iterrows():
        members = tuple(sorted(singles_index[k] for k in r["members"].split("|")))
        cand_si = float(r["5y_s_i"])
        # replace the weakest seat
        for drop, tag in ((WEAKEST_SEAT, "replace-SIZE"), (None, "add-6th")):
            pool_members2 = [singles_index[k] for k in POOL if k != drop] if drop else [singles_index[k] for k in POOL]
            combined = tuple(sorted(set(pool_members2) | set(members)))
            seat_si = [float(meta[k]["si"]) for k in POOL if k != drop] if drop else [float(meta[k]["si"]) for k in POOL]
            seat_si = seat_si + [cand_si]
            row = pool_metrics(combined, seat_si)
            row.update(dict(members="+".join(keys[i] for i in combined), tag=tag,
                            seat_si=[round(x, 5) for x in seat_si]))
            pool_rows.append(row)
    pool_frame = pd.DataFrame(pool_rows).sort_values("comb", ascending=False)
    pool_frame.to_csv(OUT / "pool_candidates.csv", index=False)

    meta_out = dict(
        rule_version=RULE_VERSION,
        cycle=CYCLE,
        windows=[w[0] for w in WINDOWS],
        members=len(keys),
        composites=len(combos),
        max_turnover_per_rebalance=MAX_TURNOVER,
        local_vs_platform_si_corr=corr,
        local_vs_platform_si_mae=mae,
        seed_pool=POOL,
        note="local proxies only; platform A uses its own IC series",
    )
    (OUT / "metadata.json").write_text(json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8")

    best = pool_frame.head(12)
    lines = ["# High-IC composite seat search (2026-09-23)", "",
             f"- rule version: `{RULE_VERSION}`",
             f"- members: {len(keys)}; composites searched: {len(combos)}; turnover cap {MAX_TURNOVER:.0%} per rebalance",
             f"- local vs platform S_i on the {len(both)} known singles: corr {corr:.3f}, MAE {mae:.5f}"
             if corr is not None else "- local vs platform S_i: not available",
             "", "## Pool scenarios (top 12 by proxy Comb)", "",
             "| tag | members | NA | NB | NC | Comb | net 5y | turnover/rebalance | pool S |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for _, r in best.iterrows():
        lines.append(
            f"| {r['tag']} | {r['members']} | {r['na']:.3f} | {r['nb']:.3f} | {r['nc']:.3f} | "
            f"{r['comb']:.3f} | {r['net']:.2f}% | {r['turnover']*100:.2f}% | {r['pool_s']:.5f} |"
        )
    lines += ["", "## Top single composites by local S_i (turnover <= cap)", "",
              "| selection | size | S_i 5y | S_i recent | rank_ic 5y | ic_ir 5y | win 5y | turnover/rebalance | net 5y |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for _, r in search[search["turnover_ok"]].sort_values("5y_s_i", ascending=False).head(15).iterrows():
        lines.append(
            f"| {r['selection']} | {int(r['size'])} | {r['5y_s_i']:.5f} | {r['recent_s_i']:.5f} | "
            f"{r['5y_rank_ic']:.4f} | {r['5y_ic_ir']:.4f} | {r['5y_win']:.3f} | "
            f"{r['5y_turnover_pct']:.2f}% | {r['5y_net_excess_pct']:.2f}% |"
        )
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-8:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
