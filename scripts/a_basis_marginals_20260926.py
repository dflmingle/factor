"""Corrected A/B/C marginals under the VERIFIED arena rule (zero platform compute).

s_i        = |RankIC_mean| * IR(RankIC series) * P(aligned RankIC > +0.02)
raw_a      = mean of s_i over seats            (verified to 1e-12 on 283 pools)
na         = min(raw_a / 0.08, 0.70)
raw_b      = same structure on the out-of-sample window (model, unverified)
nb         = min(raw_b / 0.06, 1.0)
points/mo  = 44000 * (0.20 na + 0.35 nb + 0.45 nc)      [44000 = 40000 * 1.1 bonus]
"""
from __future__ import annotations
import io, sys
from pathlib import Path
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
OUT = Path(r"D:\factor\research_reports\platform_alignment\a-basis-correction-20260926")
OUT.mkdir(parents=True, exist_ok=True)

BONUS_POINTS = 44_000.0
W_A, W_B, W_C = 0.20, 0.35, 0.45
A_ANCHOR, B_ANCHOR = 0.08, 0.06
PTS_A, PTS_B = BONUS_POINTS * W_A / A_ANCHOR, BONUS_POINTS * W_B / B_ANCHOR

# arena-measured (2026-09-24 pool record, window 20210927..20260826) ------------------
SEAT_SI_ARENA = {
    "t10_size_plus_impact_bm": 0.05926662119415439,
    "book_to_market_lf_minus_size": 0.021011254255464188,
    "book_to_market_lf_plus_impact": 0.022068061621976547,
    "impact60": 0.017982594724007532,
    "size_only": 0.009135508656026116,
}
RAW_A_BASE = sum(SEAT_SI_ARENA.values()) / len(SEAT_SI_ARENA)          # 0.025892808
SEAT_SI_LOCAL_REBUILT = {   # what ab-batch / pending4 / turnover-sim actually used
    "size_only": 0.010244872746, "impact60": 0.01578596817,
    "t10_size_plus_impact_bm": 0.03725596,
    "book_to_market_lf_minus_size": 0.01692,
    "book_to_market_lf_plus_impact": 0.01540,
}
BASE_SI_AS_USED = sum(SEAT_SI_LOCAL_REBUILT.values()) / 5

# candidates: s_i recomputed from each platform single-factor run's RankIC series ------
CANDIDATES = {   # name: (run json, s_i from scan, old bridge value)
    "AGG": (r"t10-more-additions-20260911-candidates.results\6aa3ca1451cdfe29b2e0bce4.json", 0.045278, 0.028545),
    "G13": (r"t10-additions-20260911-candidates.results\6aa3c61451cdfe29b2e0bcdd.json", 0.043116, 0.027626),
    "DOWNSIDE": (r"t10-more-additions-20260911-candidates.results\6aa3c9208b01f62dc5146090.json", 0.046256, 0.028880),
    "WC": (r"t10-newdirections-20260911-candidates.results\6aa3690a6df2a192a47e7c60.json", 0.048009, 0.030231),
}
# measured pool metrics from the 2026-09-24 six-seat runs ------------------------------
POOL_MEASURED = {   # name: (net, turn_per_reb, sharpe, dd)  -> full-period-DD C proxy
    "AGG": (0.2257, 0.1626, 1.0626, 0.3184),
    "G13": (0.2261, 0.1626, 1.0636, 0.3178),
    "DOWNSIDE": (0.2260, 0.1636, 1.0632, 0.3184),
    "WC": (0.2199, 0.1680, 1.0448, 0.3181),
}
BASE_POOL = (0.2030, 0.1339, 1.0648, 0.3164)


def nc_of(net: float, turn: float, sharpe: float, dd: float) -> float:
    turn_month = turn * 2.1
    raw_c = max(net, 0.0) / max(turn_month, 0.30) * sharpe * (1.0 - 1.2 * dd)
    return min(max(raw_c / 0.60, 0.0), 1.0)


def rows() -> list[dict]:
    base_nc = nc_of(*BASE_POOL)
    out = []
    for name, (path, s_new, s_old_bridge) in CANDIDATES.items():
        net, turn, sharpe, dd = POOL_MEASURED[name]
        d_nc = nc_of(net, turn, sharpe, dd) - base_nc
        for scenario in ("add-6th", "swap-T10-ADD-BM", "swap-SIZE-ONLY"):
            if scenario == "add-6th":
                d_raw = (s_new - RAW_A_BASE) / 6.0
                d_raw_fixed_base = (s_new - BASE_SI_AS_USED) / 6.0
                d_nc_scenario = d_nc            # measured (full-period-DD proxy)
                measured = True
            elif scenario == "swap-T10-ADD-BM":
                d_raw = (s_new - SEAT_SI_ARENA["t10_size_plus_impact_bm"]) / 5.0
                d_raw_fixed_base = (s_new - SEAT_SI_LOCAL_REBUILT["t10_size_plus_impact_bm"]) / 5.0
                d_nc_scenario = None
                measured = False
            else:
                d_raw = (s_new - SEAT_SI_ARENA["size_only"]) / 5.0
                d_raw_fixed_base = (s_new - SEAT_SI_LOCAL_REBUILT["size_only"]) / 5.0
                d_nc_scenario = None
                measured = False
            points_c = (BONUS_POINTS * W_C * d_nc_scenario) if d_nc_scenario is not None else None
            out.append(dict(
                candidate=name, scenario=scenario,
                s_new_corrected=s_new, s_new_old_bridge=s_old_bridge,
                d_raw_a=d_raw, d_na=d_raw / A_ANCHOR,
                points_A=PTS_A * d_raw, points_B=PTS_B * d_raw,
                d_nc_measured=d_nc_scenario,
                points_C=points_c,
                points_A_plus_B=PTS_A * d_raw + PTS_B * d_raw,
                points_total=PTS_A * d_raw + PTS_B * d_raw + (points_c or 0.0),
                d_raw_a_old_basis=d_raw_fixed_base,
                points_A_old_basis=PTS_A * d_raw_fixed_base,
            ))
    return out


def main() -> int:
    frame = pd.DataFrame(rows())
    frame.to_csv(OUT / "marginals.csv", index=False, encoding="utf-8-sig")
    print(f"raw_a base (arena)   = {RAW_A_BASE:.6f}  -> na {RAW_A_BASE/0.08:.4f}")
    print(f"raw_a base (as used) = {BASE_SI_AS_USED:.6f}  -> na {BASE_SI_AS_USED/0.08:.4f}")
    with pd.option_context("display.width", 200):
        print(frame[["candidate", "scenario", "s_new_corrected", "s_new_old_bridge", "d_raw_a",
                     "points_A", "points_B", "points_C", "points_total"]].to_string(index=False))
    print("\n(base nc with the full-period-DD proxy:", round(nc_of(*BASE_POOL), 4), ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
