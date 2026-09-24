"""Final pool search scored on three windows with the competition formula.

Members: every locally reproducible ten-day factor already cached by the
extended search, plus F-I10-01 (size+impact, never before screened) rebuilt as
the standardised average of its two components.

Each candidate pool is scored per window as

    Comb_w = 0.20*NA + 0.35*min(S_w/0.06, 1) + 0.45*min(rawC_w/0.6, 1)

with NA from the members' saved platform A inputs, S_w the composite's
IC-quality statistics inside that window, and rawC_w the composite's return /
turnover / Sharpe / drawdown inside that window.  The final metric is the mean
of the five-year, one-year and three-month scores, and the worst window is
reported as a robustness check.  Offline only.
"""
from __future__ import annotations

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
SEED = [
    "size_only",
    "impact60",
    "t10_size_plus_impact_bm",
    "book_to_market_lf_minus_size",
    "book_to_market_lf_plus_impact",
]
WINDOWS = (
    ("5y", None),
    ("1y", pd.Timestamp("2025-09-01")),
    ("3m", pd.Timestamp("2026-06-01")),
)


def main() -> None:
    sf, _raw, returns, dates = pickle.load(SIGNALS.open("rb"))
    cached = pickle.load(CACHE.open("rb"))
    built = list(cached["built"])
    scores = cached["scores"].copy()
    keys = [m["key"] for m in built]

    # F-I10-01 = (RANK(-MARKET_CAP) + RANK(impact60)) / 2, standardised.
    rho = scores["size_only"].corr(scores["impact60"])
    scores["f_i10_01"] = (scores["size_only"] + scores["impact60"]) / np.sqrt(2 * (1 + rho))
    built.append(
        dict(
            key="f_i10_01",
            handler="f_i10_01",
            direction=1,
            name="size-impact-20260918-F-I10-01",
            platform_net=21.424008,
            si=0.0656 * 0.3205 * 0.65,
        )
    )
    keys = [m["key"] for m in built]
    si = {m["key"]: m["si"] for m in built}
    print(f"members {len(keys)}; corr(size, impact) = {rho:.3f}; F-I10-01 S_i = {si['f_i10_01']:.5f}")

    blocks = e._build_blocks(sf, scores, returns, dates, keys)
    ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))

    def evaluate(selection: list[str]) -> dict | None:
        idx = [keys.index(k) for k in selection]
        if not idx:
            return None
        mask = np.zeros(len(keys), dtype=bool)
        mask[idx] = True
        held, gross, turn, counts, valid = e._evaluate_combinations_numba(
            fs, fr, fi, offsets, mask.reshape(1, -1), np.array([len(idx)], dtype=np.int64)
        )
        rank_ics, ics = e._exact_period_ics(tuple(idx), blocks)
        out = dict(selection=selection, size=len(selection))
        combs = []
        for label, start in WINDOWS:
            wmask = np.ones(len(ds), bool) if start is None else ds >= start.to_datetime64()
            summary = e._summary(
                held[0], gross[0], turn[0], counts[0], valid[0].astype(bool), ds, 10, label, wmask
            )
            r = rank_ics[wmask]
            c = ics[wmask]
            r = r[np.isfinite(r)]
            c = c[np.isfinite(c)]
            s = 0.0
            if len(r) and len(c) > 2 and np.std(c, ddof=1) > 0:
                s = abs(float(np.mean(r))) * abs(float(np.mean(c) / np.std(c, ddof=1))) * float(np.mean(np.abs(c) > 0.02))
            net = summary["net_excess_pct"] or 0.0
            turnover = summary["turnover_pct"] or 0.0
            sharpe = summary["sharpe_after_cost"] or 0.0
            dd = summary["max_drawdown_pct"] or 0.0
            rawc = max(net, 0) / 100 / max(2 * turnover / 100, 0.3) * sharpe * (1 - 1.2 * dd / 100)
            raw_a = float(np.mean([si[k] for k in selection]))
            comb = (
                0.20 * min(raw_a / 0.08, 1)
                + 0.35 * min(s / 0.06, 1)
                + 0.45 * min(max(rawc / 0.6, 0), 1)
            )
            combs.append(comb)
            out.update(
                {
                    f"net_{label}": net,
                    f"turn_{label}": turnover,
                    f"s_{label}": s,
                    f"comb_{label}": comb,
                }
            )
        out["comb_mean"] = float(np.mean(combs))
        out["comb_min"] = float(np.min(combs))
        return out

    best = evaluate(SEED)
    print(f"\nseed: mean {best['comb_mean']:.3f} min {best['comb_min']:.3f} | "
          f"5y {best['comb_5y']:.3f} 1y {best['comb_1y']:.3f} 3m {best['comb_3m']:.3f}")
    current = list(SEED)
    history = [dict(best, change="seed")]
    for round_id in range(1, 4):
        trials = []
        for seat in current:
            for member in built:
                if member["key"] in current:
                    continue
                trial = [k for k in current if k != seat] + [member["key"]]
                outcome = evaluate(trial)
                if outcome:
                    trials.append(dict(outcome, change=f"R{round_id} swap {seat} -> {member['key']}"))
        for member in built:
            if member["key"] in current:
                continue
            outcome = evaluate(current + [member["key"]])
            if outcome:
                trials.append(dict(outcome, change=f"R{round_id} add {member['key']}"))
        trials.sort(key=lambda r: -r["comb_mean"])
        history.extend(trials)
        best_trial = trials[0]
        base = evaluate(current)
        print(f"round {round_id}: best trial mean {best_trial['comb_mean']:.3f} "
              f"(current {base['comb_mean']:.3f}) -> {best_trial['change']}")
        if best_trial["comb_mean"] <= base["comb_mean"] + 1e-4:
            break
        current = list(best_trial["selection"])

    history.sort(key=lambda r: -r["comb_mean"])
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(history).to_csv(OUT / "final_search.csv", index=False)
    print("\nTop 12 by mean of the three window scores:")
    for row in history[:12]:
        print(
            f"  mean {row['comb_mean']:.3f} min {row['comb_min']:.3f} | "
            f"5y {row['comb_5y']:.3f}(net {row['net_5y']:5.2f}%,turn {row['turn_5y']:5.2f}%) "
            f"1y {row['comb_1y']:.3f}(net {row['net_1y']:5.2f}%) "
            f"3m {row['comb_3m']:.3f}(net {row['net_3m']:5.2f}%) | {row['change']}"
        )
    print(f"\nselected: {'+'.join(current)}")


if __name__ == "__main__":
    main()
