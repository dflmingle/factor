#!/usr/bin/env python3
"""Build the platform scoring bridge for the four approved 6-seat pool tests."""
from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "platform_pool_tests_20260924"
POINTS = 44_000.0
BASE_SI = [0.010244872746, 0.01578596817, 0.016915119, 0.015396024336, 0.03725596]
BASE_METRICS = {
    "net": 0.2030,
    "sharpe": 1.0648,
    "dd": 0.3164,
    "turn_per_reb": 0.1339,
}
CANDIDATES = {
    "AGG": {
        "key": "agg",
        "single_result": ROOT / "t10-more-additions-20260911-candidates.results/6aa3ca1451cdfe29b2e0bce4.json",
        "si": 0.1057 * 0.4379 * 0.6167,
    },
    "G13": {
        "key": "g13",
        "single_result": ROOT / "t10-additions-20260911-candidates.results/6aa3c61451cdfe29b2e0bcdd.json",
        "si": 0.1043 * 0.4295 * 0.6167,
    },
    "DOWNSIDE": {
        "key": "downside",
        "single_result": ROOT / "t10-more-additions-20260911-candidates.results/6aa3c9208b01f62dc5146090.json",
        "si": 0.1067 * 0.4389 * 0.6167,
    },
    "WC": {
        "key": "wc",
        "single_result": ROOT / "t10-newdirections-20260911-candidates.results/6aa3690a6df2a192a47e7c60.json",
        "si": 0.1052 * 0.4421 * 0.65,
    },
}


def pct(value: str) -> float:
    if value.endswith("%"):
        return float(value[:-1]) / 100.0
    return float(value)


def top_group(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text())
    analysis = payload["results"]["factor_analysis"]
    row = next(row for row in analysis["query_group_return_analysis"] if row["group"] == "分组10")
    return {
        "net": pct(row["excessAnnualized"]),
        "sharpe": pct(row["sharpeRatio"]),
        "dd": pct(row["maxDrawdown"]),
        "turn_per_reb": pct(row["turnoverRate"]),
        "factor_id": payload["factor_id"],
        "run_id": payload["factor_run_id"],
        "cost": int(payload["billing"]["deducted"]),
    }


def score(metrics: dict[str, float], mean_si: float) -> dict[str, float]:
    raw_a = mean_si
    na = min(raw_a / 0.08, 0.70)
    nb = min(mean_si / 0.06, 1.0)
    turnover_month = metrics["turn_per_reb"] * 21.0 / 10.0
    raw_c = max(metrics["net"], 0.0) / max(turnover_month, 0.30)
    raw_c *= metrics["sharpe"] * (1.0 - 1.2 * metrics["dd"])
    nc = min(raw_c / 0.60, 1.0)
    comb = 0.20 * na + 0.35 * nb + 0.45 * nc
    return {
        "mean_si": mean_si,
        "raw_a": raw_a,
        "na": na,
        "nb": nb,
        "turnover_month": turnover_month,
        "raw_c": raw_c,
        "nc": nc,
        "comb": comb,
        "points": POINTS * comb,
    }


def main() -> int:
    base_si_mean = sum(BASE_SI) / len(BASE_SI)
    base_score = score(BASE_METRICS, base_si_mean)
    rows = []
    for name, spec in CANDIDATES.items():
        pool_metrics = top_group(OUT / f"{spec['key']}.run.json")
        pool_score = score(pool_metrics, (sum(BASE_SI) + spec["si"]) / 6)
        row = {
            "candidate": name,
            **pool_metrics,
            "single_si": spec["si"],
            "delta_net": pool_metrics["net"] - BASE_METRICS["net"],
            "delta_turn_per_reb": pool_metrics["turn_per_reb"] - BASE_METRICS["turn_per_reb"],
            "delta_sharpe": pool_metrics["sharpe"] - BASE_METRICS["sharpe"],
            "delta_dd": pool_metrics["dd"] - BASE_METRICS["dd"],
            **{f"delta_{key}": pool_score[key] - base_score[key] for key in ("na", "nb", "nc", "comb", "points")},
            "pool_comb": pool_score["comb"],
            "pool_points": pool_score["points"],
        }
        rows.append(row)

    rows.sort(key=lambda row: row["delta_points"], reverse=True)
    payload = {"base": {**BASE_METRICS, **base_score}, "candidates": rows}
    (OUT / "platform_bridge.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with (OUT / "platform_bridge.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
