#!/usr/bin/env python3
"""Platform scoring bridge for the 2026-09-26 T2 / T4 6-seat pool tests.

Same convention as scripts/platform_pool_bridge_20260924.py:
  net            = long_excess - turnover_per_reb * 2 * 0.003 * 252/10
  turnover_month = turnover_per_reb * 21/10
  rawC           = max(net,0)/max(turnover_month,0.30) * sharpe * (1 - 1.2*dd)
  NA = min(raw_a/0.08,0.70) with raw_a = mean seat S_i   NB = min(raw_a/0.06,1.0)
  Comb = 0.20 NA + 0.35 NB + 0.45 NC ;  points = 44000 * Comb

CAVEAT: the platform seat S_i of T2 / T4 is not measured directly (only the pool
paste result exists), so raw_a is reported on two bases: the local s_i_rank and the
09-24 uplifted basis (x1.354).  The DD/sharpe here are full-period values, i.e. the
same proxy caveat as the 09-24 bridge - not the official monthly MaxDD C term.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "platform_pool_tests_20260926"
POINTS = 44_000.0
UPLIFT = 0.02589 / 0.01912

BASE_SI = [0.010244872746, 0.01578596817, 0.016915119, 0.015396024336, 0.03725596]
BASE_METRICS = {"net": 0.2030, "sharpe": 1.0648, "dd": 0.3164, "turn_per_reb": 0.1339}

# local s_i_rank from the 09-26 turnover-relaxed pool re-simulation
CANDIDATES = {
    "T2": {"key": "t2", "local_si": 0.0500143201335105},
    "T4": {"key": "t4", "local_si": 0.0398363198770225},
}


def pct(value) -> float:
    text = str(value)
    if text.endswith("%"):
        return float(text[:-1]) / 100.0
    return float(text)


def top_group(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    analysis = payload["results"]["factor_analysis"]
    row = next(r for r in analysis["query_group_return_analysis"] if r["group"] == "分组10")
    long_excess = pct(row["excessAnnualized"])
    turn_per_reb = pct(row["turnoverRate"])
    net = long_excess - turn_per_reb * 2 * 0.003 * 25.2
    return {
        "long_excess": long_excess,
        "turn_per_reb": turn_per_reb,
        "net": net,
        "sharpe": pct(row["sharpeRatio"]),
        "dd": pct(row["maxDrawdown"]),
        "monthly_win": pct(row["monthlyWinRate"]),
        "factor_id": payload.get("factor_id"),
        "run_id": payload.get("factor_run_id"),
    }


def score(metrics: dict, mean_si: float) -> dict:
    na = min(mean_si / 0.08, 0.70)
    nb = min(mean_si / 0.06, 1.0)
    turnover_month = metrics["turn_per_reb"] * 21.0 / 10.0
    raw_c = max(metrics["net"], 0.0) / max(turnover_month, 0.30)
    raw_c *= metrics["sharpe"] * (1.0 - 1.2 * metrics["dd"])
    nc = min(raw_c / 0.60, 1.0)
    comb = 0.20 * na + 0.35 * nb + 0.45 * nc
    return {"mean_si": mean_si, "na": na, "nb": nb, "turnover_month": turnover_month,
            "raw_c": raw_c, "nc": nc, "comb": comb, "points": POINTS * comb}


def main() -> int:
    base_si_mean = sum(BASE_SI) / len(BASE_SI)
    base_score = score(BASE_METRICS, base_si_mean)
    rows = []
    for name, spec in CANDIDATES.items():
        result_path = OUT / f"{spec['key']}.v2.run.json"
        if not result_path.exists():
            print(f"[skip] {name}: no platform result at {result_path}")
            continue
        pool_metrics = top_group(result_path)
        for basis, seat_si in (("local", spec["local_si"]),
                               ("uplifted", spec["local_si"] * UPLIFT)):
            pool_score = score(pool_metrics, (sum(BASE_SI) + seat_si) / 6.0)
            rows.append({
                "candidate": name, "si_basis": basis, "seat_si": seat_si, **pool_metrics,
                "delta_net": pool_metrics["net"] - BASE_METRICS["net"],
                "delta_turn": pool_metrics["turn_per_reb"] - BASE_METRICS["turn_per_reb"],
                "delta_sharpe": pool_metrics["sharpe"] - BASE_METRICS["sharpe"],
                "delta_dd": pool_metrics["dd"] - BASE_METRICS["dd"],
                **{f"delta_{k}": pool_score[k] - base_score[k] for k in ("na", "nb", "nc", "comb", "points")},
                "pool_comb": pool_score["comb"], "pool_points": pool_score["points"],
            })
    rows.sort(key=lambda r: -r["delta_points"])
    payload = {"base": {**BASE_METRICS, **base_score}, "candidates": rows}
    (OUT / "platform_bridge.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    with (OUT / "platform_bridge.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    header = f"{'cand':4s} {'basis':9s} {'net%':>7s} {'turn/reb':>8s} {'sharpe':>7s} {'dd':>6s} {'dNA':>7s} {'dNB':>7s} {'dNC':>7s} {'dComb':>8s} {'pts/mo':>9s}"
    print(header)
    for r in rows:
        print(f"{r['candidate']:4s} {r['si_basis']:9s} {r['net']*100:7.2f} {r['turn_per_reb']*100:8.2f} "
              f"{r['sharpe']:7.4f} {r['dd']*100:6.2f} {r['delta_na']*100:7.2f} {r['delta_nb']*100:7.2f} "
              f"{r['delta_nc']*100:7.2f} {r['delta_comb']:8.4f} {r['delta_points']:9.1f}")
    print(f"\nbase: net {BASE_METRICS['net']*100:.2f}% turn/reb {BASE_METRICS['turn_per_reb']*100:.2f}% "
          f"sharpe {BASE_METRICS['sharpe']} dd {BASE_METRICS['dd']*100:.2f}% -> rawC {base_score['raw_c']:.4f} "
          f"NC {base_score['nc']:.4f} Comb {base_score['comb']:.4f} points {base_score['points']:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())