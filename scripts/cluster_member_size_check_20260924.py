"""For all 54 clustered/search members: how much of their net excess is size?

Reads research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl
(54 member score panels + platform record) and, for every member, computes the daily
cross-sectional Spearman correlation with the SIZE-ONLY seat, its top-decile turnover,
and the pool impact of adding it as a 6th equal-weight seat.

Output: research_reports/platform_alignment/clusize-check-20260924/member_size_check.csv
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sizeneut_candidate_verify_20260924 as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/clusize-check-20260924"
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"


def main() -> int:
    sf, _raw, returns, _dates = pickle.load(SIGNALS.open("rb"))
    built = pickle.load(SEATS.open("rb"))
    members, scores = built["built"], built["scores"]
    # `scores` is row-aligned with `sf` (552290 rows, 5311 instruments), NOT with
    # `returns` (647400 rows, 5395 instruments). Using the wrong index frame silently
    # shifted every score onto another stock; concatenate on `sf`.
    frame = sf[["date", "instrument"]].reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    panel_frame = pd.concat([frame, scores.reset_index(drop=True)], axis=1)
    signal_dates = sorted(panel_frame["date"].unique())
    forward = (returns.pivot_table(index="date", columns="instrument", values="forward_return")
               .reindex(index=signal_dates))
    forward.index = pd.to_datetime(forward.index)

    # panels live on a 5311-instrument universe, returns on 5395: align both or the
    # element-wise ok-mask pairs different stocks (this silently broke the first run).
    columns = forward.columns
    panels = {m["key"]: panel_frame.pivot_table(index="date", columns="instrument", values=m["key"])
                        .reindex(index=signal_dates, columns=columns)
              for m in members}
    print("panel universe", panel_frame["instrument"].nunique(), "-> aligned", len(columns), flush=True)
    seat_z = {k: V.zscore(panels[k]) for k in V.POOL if k in panels}
    base = V.pool_metrics(sum(seat_z.values()) / len(seat_z), forward, V.SEAT_SI)
    print("seed pool:", {k: round(v, 4) for k, v in base.items()}, flush=True)

    rows = []
    for m in members:
        key = m["key"]
        panel = panels[key]
        direction = int(m.get("direction", 1))
        oriented = panel if direction == 1 else -panel
        stats = V.seat_stats(oriented, forward)
        corr_size = V.daily_rank_corr(oriented, panels["size_only"])
        if key in V.POOL:
            add_comb, delta = base["pool_comb"], 0.0
        else:
            score6 = (sum(seat_z.values()) + V.zscore(oriented)) / (len(seat_z) + 1)
            seat_si = dict(V.SEAT_SI); seat_si["candidate"] = stats["s_i"]
            add = V.pool_metrics(score6, forward, seat_si)
            add_comb = add["pool_comb"]
            delta = 40000 * 1.1 * (add["pool_comb"] - base["pool_comb"])
        rows.append(dict(
            key=key, name=m.get("name", ""), in_pool=key in V.POOL,
            platform_net_pct=m.get("platform_net"), platform_si=m.get("si"),
            local_s_i=stats["s_i"], local_turnover=stats["seat_turnover"],
            local_net=stats["seat_net"], corr_size=corr_size,
            add6_comb=add_comb, delta_points=delta))

    out = pd.DataFrame(rows).sort_values("platform_net_pct", ascending=False)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "member_size_check.csv", index=False)
    pd.set_option("display.width", 250)
    print("\n=== 54 members, sorted by platform net ===", flush=True)
    print(out[["name", "platform_net_pct", "platform_si", "local_s_i", "local_turnover",
               "corr_size", "delta_points"]].round(4).to_string(index=False), flush=True)

    print("\n=== size-independent (|corr|<=0.5) members with platform net >= 5% ===", flush=True)
    sel = out[(out["corr_size"].abs() <= 0.5) & (out["platform_net_pct"] >= 5)]
    print(sel[["name", "platform_net_pct", "platform_si", "local_s_i", "local_turnover",
               "corr_size", "delta_points"]].round(4).to_string(index=False), flush=True)
    print(f"\ncount = {len(sel)} / {len(out)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
