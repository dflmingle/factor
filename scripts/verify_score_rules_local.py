#!/usr/bin/env python3
"""Recompute the pool A-component seats locally and check them against the platform.

Reads the saved local panels, computes each live seat's RankIC series with the
frozen rules in ``scripts/platform_score_rules.py``, and compares the resulting
``s_i_a`` with the platform ``factor_pool_details`` fixture.

Usage:
    python scripts/verify_score_rules_local.py
    python scripts/verify_score_rules_local.py --rank-all --write

Exit code is 1 when the seat-level or pool-level deviation exceeds tolerance.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_score_rules import (  # noqa: E402
    LOCAL_SEAT_COLUMNS,
    PLATFORM_POOL_FIXTURE,
    PLATFORM_SEAT_FIXTURE,
    SCORE_RULE_VERSION,
    comb,
    marginal_points,
    mean_s_i,
    monthly_points,
    rank_ic_series,
    raw_a,
    score_na,
    seat_stats,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIGNALS = (
    ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
)
DEFAULT_SCORES = (
    ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
)
DEFAULT_OUTPUT = ROOT / "research_reports/platform_alignment/score-rules-20260924"

SEAT_TOLERANCE = 0.15
MEAN_TOLERANCE = 0.05

# Our pool's platform state on the 2026-09-24 snapshot: no out-of-sample month
# yet, so B and C are gated to zero and only the A component is comparable.
POOL_AGE_MONTHS = float(PLATFORM_POOL_FIXTURE["pool_age_months"])


def load_panel(signals_path: Path, scores_path: Path) -> pd.DataFrame:
    universe, _panels, labels, _dates = pickle.loads(signals_path.read_bytes())
    scores = pickle.loads(scores_path.read_bytes())["scores"]
    merged = universe.merge(labels, on=["date", "instrument"], how="left")
    if len(merged) != len(scores):
        raise SystemExit(f"panel length mismatch: {len(merged)} vs {len(scores)}")
    return pd.concat([merged.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)


def ic_series(frame: pd.DataFrame, column: str) -> pd.Series:
    probe = frame.rename(columns={column: "score"})
    return rank_ic_series(probe[["date", "score", "forward_return"]])


def format_row(row: dict[str, float], name: str) -> str:
    return (
        f"{name:44s} ic {row['ic_platform']:.4f}->{row['ic_local']:.4f} "
        f"ir {row['ir_platform']:.4f}->{row['ir_local']:.4f} "
        f"win {row['win_platform']:.3f}->{row['win_local']:.3f} "
        f"s_i {row['s_i_platform']:.5f}->{row['s_i_local']:.5f} "
        f"({row['s_i_rel_error'] * 100:+.1f}%)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--rank-all", action="store_true", help="rank every score column as a 6th seat")
    parser.add_argument("--write", action="store_true", help=f"write JSON under {DEFAULT_OUTPUT}")
    args = parser.parse_args(argv)

    frame = load_panel(args.signals, args.scores)
    seats: dict[str, pd.Series] = {}
    rows: list[dict[str, float]] = []
    for seat in PLATFORM_SEAT_FIXTURE:
        name = str(seat["factor_name"])
        column = LOCAL_SEAT_COLUMNS[name]
        seats[column] = ic_series(frame, column)
        stats = seat_stats(seats[column])
        rows.append(
            {
                "factor_name": name,
                "column": column,
                "ic_platform": float(seat["ic_mean"]),
                "ic_local": stats.ic_mean,
                "ir_platform": float(seat["icir"]),
                "ir_local": stats.icir,
                "win_platform": float(seat["ic_win_rate"]),
                "win_local": stats.win_rate,
                "s_i_platform": float(seat["s_i_a"]),
                "s_i_local": stats.s_i_a,
                "s_i_rel_error": stats.s_i_a / float(seat["s_i_a"]) - 1.0,
            }
        )

    local_s_i = [row["s_i_local"] for row in rows]
    raw_a_local = raw_a(local_s_i)
    na_local = score_na(raw_a_local)
    points_local = monthly_points(comb(na_local, 0.0, 0.0))

    print(f"score rule version: {SCORE_RULE_VERSION}")
    print(f"panel: {args.signals.parent.name} x {args.scores.parent.name}")
    for row in rows:
        print("  " + format_row(row, str(row["factor_name"])))

    mean_rel_error = float(np.mean([abs(row["s_i_rel_error"]) for row in rows]))
    print(f"  seats: local mean s_i {mean_s_i(local_s_i):.6f} vs platform "
          f"{PLATFORM_POOL_FIXTURE['raw_a']:.6f}; mean |rel err| = {mean_rel_error * 100:.2f}%")
    print(f"  pool : raw_a {raw_a_local:.6f} vs {PLATFORM_POOL_FIXTURE['raw_a']:.6f}; "
          f"na {na_local:.4f} vs {PLATFORM_POOL_FIXTURE['na']:.4f}; "
          f"points/month {points_local:.1f} vs {PLATFORM_POOL_FIXTURE['monthly_points']:.1f}")

    payload: dict[str, object] = {
        "score_rule_version": SCORE_RULE_VERSION,
        "seats": rows,
        "pool": {
            "raw_a_local": raw_a_local,
            "raw_a_platform": float(PLATFORM_POOL_FIXTURE["raw_a"]),
            "na_local": na_local,
            "na_platform": float(PLATFORM_POOL_FIXTURE["na"]),
            "points_local": points_local,
            "points_platform": float(PLATFORM_POOL_FIXTURE["monthly_points"]),
            "mean_abs_s_i_rel_error": mean_rel_error,
            "pool_age_months": POOL_AGE_MONTHS,
        },
    }

    if args.rank_all:
        threshold = mean_s_i(local_s_i)
        ranking = []
        for column in frame.columns:
            if column in {"date", "instrument", "forward_return"}:
                continue
            stats = seat_stats(ic_series(frame, column))
            if not np.isfinite(stats.s_i_a):
                continue
            ranking.append(
                {
                    "column": column,
                    "s_i_a": stats.s_i_a,
                    "ic_mean": stats.ic_mean,
                    "icir": stats.icir,
                    "win_rate": stats.win_rate,
                    "marginal_points": marginal_points(local_s_i, stats.s_i_a),
                }
            )
        ranking.sort(key=lambda row: row["s_i_a"], reverse=True)
        payload["sixth_seat_ranking"] = ranking
        print(f"  top candidates for seat 6 (threshold s_i >= {threshold:.5f}):")
        for row in ranking[:12]:
            print(
                f"    {row['column']:44s} s_i {row['s_i_a']:.5f} "
                f"ic {row['ic_mean']:.4f} ir {row['icir']:.3f} win {row['win_rate']:.3f} "
                f"delta A points {row['marginal_points']:+.0f}/month"
            )

    failed = mean_rel_error > MEAN_TOLERANCE or any(
        abs(row["s_i_rel_error"]) > SEAT_TOLERANCE for row in rows
    )
    print(f"  verdict: {'FAIL' if failed else 'OK'} "
          f"(seat tolerance {SEAT_TOLERANCE:.0%}, mean tolerance {MEAN_TOLERANCE:.0%})")

    if args.write:
        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        target = DEFAULT_OUTPUT / "verification.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"  wrote {target.relative_to(ROOT)}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
