"""A/B 批次的 ΔComb 分解与决策表（零算力，读 ab-batch-20260925 既有产物）。"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/ab-batch-20260925"
POINTS = 40000.0 * 1.10
A_WEIGHT, C_WEIGHT = 0.20, 0.45


def main() -> int:
    base = pd.read_csv(OUT / "base_pool.csv").iloc[0]
    scen = pd.read_csv(OUT / "pool_scenarios.csv")
    stats = pd.read_csv(OUT / "seat_stats.csv")
    monthly = pd.read_csv(OUT / "monthly_dcomb.csv")

    scen["d_na"] = scen["pool_na"] - base["pool_na"]
    scen["d_nc"] = scen["pool_nc"] - base["pool_nc"]
    scen["d_comb_check"] = A_WEIGHT * scen["d_na"] + C_WEIGHT * scen["d_nc"]
    scen["d_comb_nc_only"] = C_WEIGHT * scen["d_nc"]
    scen["d_points_nc_only"] = POINTS * scen["d_comb_nc_only"]
    scen = scen.sort_values(["tag", "d_comb"], ascending=[True, False])
    scen.to_csv(OUT / "pool_scenarios.csv", index=False)

    missing = float(np.abs(scen["d_comb"] - scen["d_comb_check"]).max())
    print(f"decomposition residual max = {missing:.3e}")

    decision = scen.copy()
    decision["verdict"] = np.where(
        decision["d_comb"] > 0, "进池有利",
        np.where(decision["d_comb_nc_only"] > 0, "仅收益项为正（A 项抵扣后转负）", "进池不利"),
    )
    keep = ["candidate", "tag", "d_comb", "d_points", "d_na", "d_nc", "d_comb_nc_only",
            "d_points_nc_only", "d_net", "d_turn", "turn_excess", "verdict"]
    decision[keep].to_csv(OUT / "decision_table.csv", index=False)

    merged = decision.merge(
        monthly[["candidate", "n_months", "dcomb_month_mean", "dcomb_month_positive",
                 "n_blocks", "dcomb_block6_mean", "dcomb_block6_positive"]],
        on="candidate", how="left",
    ).merge(
        stats[["candidate", "net", "turnover", "rank_ic", "neu_net", "corr_size",
               "corr_max", "corr_max_seat"]],
        on="candidate", how="left",
    )
    merged.to_csv(OUT / "ab_batch_final_table.csv", index=False)

    print(merged[["candidate", "tag", "d_comb", "d_na", "d_nc", "d_comb_nc_only",
                  "d_points_nc_only", "dcomb_block6_mean", "corr_max",
                  "corr_max_seat"]].round(4).to_string(index=False))

    provenance = json.loads((OUT / "run_provenance.json").read_text(encoding="utf-8"))
    print("seat source:", provenance["seat_source"])
    print("written:", OUT / "decision_table.csv", OUT / "ab_batch_final_table.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())