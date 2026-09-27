"""Turnover-relaxed re-ranking of the 253 wide-field GP candidates (see summary.md)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path("D:/factor")
OUT = ROOT / "research_reports/platform_alignment/turnover-relaxed-20260926"
OUT.mkdir(parents=True, exist_ok=True)

MEAN_S = 0.01912          # local 5-seat mean S_i
MEAN_S_PLAT = 0.02589     # platform raw_a of the same pool (09-24 fixture)
BASE_TURN = 0.1339
MONTH_MIX = {1: 0.117, 2: 0.767, 3: 0.117}
POINTS, WEIGHT_C = 44_000.0, 0.45
A_UNIT = 0.20 / (6 * 0.08) * POINTS          # 18,333 pts per unit of raw_a
UPLIFT = MEAN_S_PLAT / MEAN_S                # 1.354, local -> platform scale


def nc(t_k, t_star):
    return float(min(1.0, t_star / max(t_k, 0.30)))


def delta_c(t6, t_star):
    old, new = 5 * BASE_TURN / 6, (5 * BASE_TURN + t6) / 6
    return WEIGHT_C * POINTS * sum(
        p * (nc(k * new, t_star) - nc(k * old, t_star)) for k, p in MONTH_MIX.items())


def need(t6, t_star, uplift):
    """Break-even local s_i_rank, consistent with the A basis used for the gain."""
    return MEAN_S - delta_c(t6, t_star) / (A_UNIT * uplift)


def main():
    d = pd.read_csv(ROOT / "research_reports/platform_alignment/relaxed-gp-20260924/"
                           "screen2/screened_candidates.csv")
    d = d[(d.turnover > 0) & (d.s_i_rank > 0.0005)].copy()
    for tag, t_star in (("337", 0.337), ("300", 0.300), ("400", 0.400)):
        d[f"dc_{tag}"] = [delta_c(t, t_star) for t in d.turnover]
        for up_tag, up in (("lo", 1.0), ("up", UPLIFT)):
            gain = A_UNIT * up * (d.s_i_rank - MEAN_S)
            d[f"net_{tag}_{up_tag}"] = gain + d[f"dc_{tag}"]
    show = ["run", "band", "s_i_rank", "turnover", "net", "net_y2026", "corr_size",
            "net_337_lo", "net_337_up", "net_400_up"]
    d.sort_values("net_337_up", ascending=False).to_csv(
        OUT / "corrected_rank.csv", index=False, encoding="utf-8-sig")

    print(f"kept {len(d)} candidates (s_i_rank > 0.0005)")
    for c in ["net_337_lo", "net_337_up", "net_300_up", "net_400_up"]:
        print(f"  {c} > 0 : {int((d[c] > 0).sum())}")

    print("\n=== break-even local s_i_rank needed (uplift=1.354) ===")
    print("  t6  | " + " | ".join(f"T*={t:.3f}" for t in (0.30, 0.337, 0.40, 0.45)))
    for t6 in (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60):
        print(f"{t6:5.2f} | " + " | ".join(f"{need(t6, t, UPLIFT):9.4f}"
                                           for t in (0.30, 0.337, 0.40, 0.45)))

    print("\n=== top 12 by corrected net (T*=0.337, uplift) ===")
    with pd.option_context("display.width", 220):
        print(d.sort_values("net_337_up", ascending=False).head(12)[show].to_string(
            index=False, float_format=lambda v: f"{v:,.4f}"))

    print("\n=== window 20-45% turnover, top 10 ===")
    w = d[(d.turnover >= 0.20) & (d.turnover <= 0.45)].sort_values("net_337_up", ascending=False)
    with pd.option_context("display.width", 220, "display.max_colwidth", 90):
        print(w.head(10)[show + ["formula"]].to_string(
            index=False, float_format=lambda v: f"{v:,.4f}"))


if __name__ == "__main__":
    main()