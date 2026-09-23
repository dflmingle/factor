"""Widened pool search: 54 local members, marginal-contribution shortlist.

Previous exhaustive search picked its 14-member shortlist by *standalone*
member score, which silently dropped the value seats (BM_SIZE / BM_ILLIQ) even
though they carry the most independent information in the pool.  This run:

1. ranks every member twice - by platform S_i and by its marginal effect when
   added to the current pool (Delta Comb);
2. builds the shortlist from the union of both rankings (so "quiet but
   independent" seats survive);
3. enumerates all 5/6/7-seat combinations of that shortlist;
4. scores each combination with the competition shape (A from platform S_i,
   C from local windows) plus a monthly-stability term.

Offline only.
"""
from __future__ import annotations

import itertools
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402

OUT = Path("research_reports/platform_alignment/widened-pool-search-20260923")
CACHE = Path("research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl")
SIGNALS = Path("research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl")
SEED = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
WINDOWS = (("5y", None), ("1y", pd.Timestamp("2025-09-01")), ("3m", pd.Timestamp("2026-06-01")))
SHORTLIST_BY_SI = 9
SHORTLIST_BY_MARGINAL = 8
SHORTLIST_CAP = 15
# 平台记录门槛：本地边际增益再大，也不让"平台实测就是负贡献"的席位进短名单
MIN_PLATFORM_NET = 10.0
MIN_PLATFORM_SI = 0.015


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sf, _raw, returns, dates = pickle.load(SIGNALS.open("rb"))
    cached = pickle.load(CACHE.open("rb"))
    built = list(cached["built"])
    keys = [m["key"] for m in built]
    scores = cached["scores"][keys]
    si = {m["key"]: float(m.get("si") or 0.0) for m in built}
    platform_net = {m["key"]: float(m.get("platform_net") or 0.0) for m in built}
    blocks = e._build_blocks(sf, scores, returns, dates, keys)
    ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))

    def evaluate(selection: list[str]) -> dict | None:
        idx = [keys.index(k) for k in selection]
        mask = np.zeros(len(keys), dtype=bool)
        mask[idx] = True
        held, gross, turn, counts, valid = e._evaluate_combinations_numba(
            fs, fr, fi, offsets, mask.reshape(1, -1), np.array([len(idx)], dtype=np.int64))
        rank_ics, ics = e._exact_period_ics(tuple(idx), blocks)
        out = dict(selection="+".join(selection), size=len(selection),
                   na=min(float(np.mean([si[k] for k in selection])) / 0.08, 0.7))
        combs = []
        for label, start in WINDOWS:
            wmask = np.ones(len(ds), bool) if start is None else ds >= start.to_datetime64()
            summary = e._summary(held[0], gross[0], turn[0], counts[0], valid[0].astype(bool),
                                 ds, 10, label, wmask)
            net = (summary["net_excess_pct"] or 0.0) / 100.0
            turnover = (summary["turnover_pct"] or 0.0) / 100.0
            sharpe = summary["sharpe_after_cost"] or 0.0
            dd = (summary["max_drawdown_pct"] or 0.0) / 100.0
            raw_c = max(net, 0.0) / max(2 * turnover, 0.3) * sharpe * (1 - 1.2 * dd)
            nc = min(max(raw_c / 0.6, 0.0), 1.0)
            comb = 0.20 * out["na"] + 0.45 * nc
            out[f"net_{label}"] = net * 100
            out[f"turn_{label}"] = turnover * 100
            out[f"sharpe_{label}"] = sharpe
            out[f"dd_{label}"] = dd * 100
            out[f"nc_{label}"] = nc
            out[f"comb_{label}"] = comb
            combs.append(comb)
            if start is None:
                out["win_rate_5y"] = (summary["monthly_win_rate_pct"] or 0.0) / 100.0
        out["comb_mean"] = float(np.mean(combs))
        out["comb_min"] = float(np.min(combs))
        out["objective"] = out["comb_mean"] + 0.10 * (out.get("win_rate_5y", 0.5) - 0.5)
        return out

    # ---- stage 1: marginal screen against the submitted pool -------------
    base = evaluate(SEED)
    print(f"seed: comb_mean {base['comb_mean']:.3f} (5y {base['comb_5y']:.3f} / "
          f"1y {base['comb_1y']:.3f} / 3m {base['comb_3m']:.3f})", flush=True)
    marginal_rows = []
    for key in keys:
        if key in SEED:
            continue
        trial = evaluate(SEED + [key])
        if trial is None:
            continue
        marginal_rows.append(dict(member=key, si=si[key], platform_net=platform_net[key],
                                  comb_mean=trial["comb_mean"],
                                  delta=trial["comb_mean"] - base["comb_mean"],
                                  na=trial["na"], turn_5y=trial["turn_5y"], net_5y=trial["net_5y"]))
    marginal = pd.DataFrame(marginal_rows).sort_values("delta", ascending=False)
    marginal.to_csv(OUT / "marginal_screen.csv", index=False)
    print(marginal.head(8)[["member", "si", "delta", "na", "net_5y", "turn_5y"]].round(4).to_string(index=False),
          flush=True)

    eligible = {
        m["key"] for m in built
        if float(m.get("platform_net") or 0.0) >= MIN_PLATFORM_NET
        or float(m.get("si") or 0.0) >= MIN_PLATFORM_SI
    }
    print(f"eligible members (platform net >= {MIN_PLATFORM_NET}% or S_i >= {MIN_PLATFORM_SI}): "
          f"{len(eligible)} / {len(keys)}", flush=True)
    rejected = [k for k in marginal["member"].head(8) if k not in eligible]
    if rejected:
        print(f"marginal-screen hits rejected by the platform floor: {rejected}", flush=True)
    by_si = sorted([k for k in keys if k in eligible], key=lambda k: si[k], reverse=True)
    by_marginal = [k for k in marginal["member"].tolist() if k in eligible]
    shortlist: list[str] = []
    for key in [k for k in SEED] + by_si[:SHORTLIST_BY_SI] + by_marginal[:SHORTLIST_BY_MARGINAL]:
        if key not in shortlist:
            shortlist.append(key)
    shortlist = shortlist[:SHORTLIST_CAP]
    print(f"shortlist ({len(shortlist)}): {shortlist}", flush=True)

    # ---- stage 2: exhaustive 5/6/7-seat enumeration over the shortlist ----
    rows = []
    for size in (5, 6, 7):
        count = 0
        for combo in itertools.combinations(shortlist, size):
            result = evaluate(list(combo))
            if result:
                rows.append(result)
                count += 1
        print(f"  size {size}: {count} combos", flush=True)
    frame = pd.DataFrame(rows).sort_values("objective", ascending=False)
    frame.to_csv(OUT / "search_results.csv", index=False)
    cols = ["size", "objective", "comb_mean", "comb_min", "na", "nc_5y", "nc_1y", "nc_3m",
            "net_5y", "turn_5y", "win_rate_5y", "selection"]
    print("\ntop 15 by objective:", flush=True)
    print(frame.head(15)[cols].round(4).to_string(index=False), flush=True)
    print(f"\ntotal combos scored: {len(frame)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
