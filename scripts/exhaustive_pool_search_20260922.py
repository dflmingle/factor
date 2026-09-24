"""Exhaustive five/six/seven-seat pool search over the top members.

Members: the 54 locally reproducible ten-day handlers plus F-I10-01.  A member
shortlist is ranked by a standalone profile (recent and five-year IC quality,
standalone platform net excess, turnover), then every 5-, 6- and 7-seat
combination of that shortlist is scored on three windows with the competition
formula shape.  Offline only.
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

OUT = Path("research_reports/platform_alignment/pool-extended-search-20260922")
CACHE = OUT / "built_signals.pkl"
SIGNALS = Path("research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl")
SHORTLIST = 14
WINDOWS = (("5y", None), ("1y", pd.Timestamp("2025-09-01")), ("3m", pd.Timestamp("2026-06-01")))
MIN_CORE = ["size_only", "impact60", "t10_size_plus_impact_bm"]


def main() -> None:
    sf, _raw, returns, dates = pickle.load(SIGNALS.open("rb"))
    cached = pickle.load(CACHE.open("rb"))
    built = list(cached["built"])
    scores = cached["scores"].copy()
    rho = scores["size_only"].corr(scores["impact60"])
    scores["f_i10_01"] = (scores["size_only"] + scores["impact60"]) / np.sqrt(2 * (1 + rho))
    built.append(
        dict(key="f_i10_01", handler="f_i10_01", direction=1, name="size-impact-20260918-F-I10-01",
             platform_net=21.424008, si=0.0656 * 0.3205 * 0.65)
    )
    keys = [m["key"] for m in built]
    si = {m["key"]: m["si"] for m in built}
    turnover = {}
    for m in built:
        record = next((r for r in cached["built"] if r["key"] == m["key"]), None)
        turnover[m["key"]] = 0.30
    blocks = e._build_blocks(sf, scores, returns, dates, keys)
    ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))

    # member-level recent IC quality (own series)
    member_quality = {}
    for idx, key in enumerate(keys):
        rank_ics, ics = e._exact_period_ics((idx,), blocks)
        quality = {}
        for label, start in WINDOWS:
            wmask = np.ones(len(ds), bool) if start is None else ds >= start.to_datetime64()
            r = rank_ics[wmask]
            c = ics[wmask]
            r = r[np.isfinite(r)]
            c = c[np.isfinite(c)]
            s = 0.0
            if len(r) and len(c) > 2 and np.std(c, ddof=1) > 0:
                s = abs(float(np.mean(r))) * abs(float(np.mean(c) / np.std(c, ddof=1))) * float(np.mean(np.abs(c) > 0.02))
            quality[label] = s
        member_quality[key] = quality

    meta = {m["key"]: m for m in built}
    def member_score(key: str) -> float:
        q = member_quality[key]
        net = max(meta[key]["platform_net"] or 0.0, 0.0) / 100
        return (
            0.35 * min(q["1y"] / 0.06, 1)
            + 0.25 * min(q["5y"] / 0.08, 1)
            + 0.25 * min(net / 0.25, 1)
            + 0.15 * min(q["3m"] / 0.06, 1)
        )

    ranked = sorted(keys, key=member_score, reverse=True)
    shortlist = [k for k in MIN_CORE if k in ranked]
    shortlist += [k for k in ranked if k not in shortlist][: max(0, SHORTLIST - len(shortlist))]
    print("shortlist:", shortlist, flush=True)

    def evaluate(selection):
        idx = [keys.index(k) for k in selection]
        mask = np.zeros(len(keys), dtype=bool)
        mask[idx] = True
        held, gross, turn, counts, valid = e._evaluate_combinations_numba(
            fs, fr, fi, offsets, mask.reshape(1, -1), np.array([len(idx)], dtype=np.int64)
        )
        rank_ics, ics = e._exact_period_ics(tuple(idx), blocks)
        out = {}
        combs = []
        for label, start in WINDOWS:
            wmask = np.ones(len(ds), bool) if start is None else ds >= start.to_datetime64()
            summary = e._summary(held[0], gross[0], turn[0], counts[0], valid[0].astype(bool), ds, 10, label, wmask)
            r = rank_ics[wmask]
            c = ics[wmask]
            r = r[np.isfinite(r)]
            c = c[np.isfinite(c)]
            s = 0.0
            if len(r) and len(c) > 2 and np.std(c, ddof=1) > 0:
                s = abs(float(np.mean(r))) * abs(float(np.mean(c) / np.std(c, ddof=1))) * float(np.mean(np.abs(c) > 0.02))
            net = summary["net_excess_pct"] or 0.0
            turnp = summary["turnover_pct"] or 0.0
            sharpe = summary["sharpe_after_cost"] or 0.0
            dd = summary["max_drawdown_pct"] or 0.0
            rawc = max(net, 0) / 100 / max(2 * turnp / 100, 0.3) * sharpe * (1 - 1.2 * dd / 100)
            raw_a = float(np.mean([si[k] for k in selection]))
            comb = 0.20 * min(raw_a / 0.08, 1) + 0.35 * min(s / 0.06, 1) + 0.45 * min(max(rawc / 0.6, 0), 1)
            combs.append(comb)
            out[f"net_{label}"] = net
            out[f"turn_{label}"] = turnp
            out[f"comb_{label}"] = comb
        out["comb_mean"] = float(np.mean(combs))
        out["comb_min"] = float(np.min(combs))
        out["selection"] = "+".join(selection)
        out["size"] = len(selection)
        return out

    results = []
    for size in (5, 6, 7):
        count = 0
        for combo in itertools.combinations(shortlist, size):
            results.append(evaluate(list(combo)))
            count += 1
            if count % 20000 == 0:
                print(f"  size {size}: {count} evaluated", flush=True)
    table = pd.DataFrame(results).sort_values("comb_mean", ascending=False)
    table.to_csv(OUT / "exhaustive_search.csv", index=False)
    print(f"\ntotal pools {len(table)}")
    for size in (5, 6, 7):
        sub = table[table["size"] == size].head(5)
        print(f"\n== best {size}-seat ==")
        for _, row in sub.iterrows():
            print(
                f"  mean {row['comb_mean']:.3f} min {row['comb_min']:.3f} | "
                f"5y {row['comb_5y']:.3f}(net {row['net_5y']:5.2f}%,turn {row['turn_5y']:5.2f}%) "
                f"1y {row['comb_1y']:.3f}(net {row['net_1y']:5.2f}%) 3m {row['comb_3m']:.3f} | {row['selection']}"
            )
    best = table.iloc[0]
    print(f"\noverall best: {best['selection']} (mean {best['comb_mean']:.3f}, min {best['comb_min']:.3f})")


if __name__ == "__main__":
    main()
