# -*- coding: utf-8 -*-
"""Swap-variant ledger for the AlphaGen pool-opt candidates (zero platform compute).

For each candidate (AGP01W/AGP03W/AGP05W, the optimizer-weighted composites) and
each swap target (size_only, impact60), build the 5-seat pool
    live swapf 5 seats - <target> + <candidate>
and run the same monthly ledger machinery as alphagen_pool_optimize_20261002.py,
diffing against the live 5-seat seed. Output goes to .../alphagen-pool-opt-20261002/swap/.

Usage (easyrl4rec env only):
  D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts/_alphagen_swap_ledger_20261002.py
"""
from __future__ import annotations

import gc
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphagen_pool_optimize_20261002 as apo  # noqa: E402
from legmix_next_legs_20260929 import build_raw_legs  # noqa: E402
from e_decomp_20260928 import (  # noqa: E402
    MEAN_S_LOCAL, MEAN_S_PLAT, W_C, Market, rank_ic_stats,
)
from exhaustive_representative_combination import _competition_cross_sectional_scores  # noqa: E402

OUT = apo.OUT / "swap"
CANDS = [("AGP01W", "AGP01"), ("AGP03W", "AGP03"), ("AGP05W", "AGP05")]
TARGETS = ["size_only", "impact60"]


def main() -> int:
    apo.start_watchdog()
    OUT.mkdir(parents=True, exist_ok=True)

    payload = pickle.load(apo.REBUILD.open("rb"))
    device = torch.device("cpu")
    market = Market(payload, device)
    panels = apo.build_panels_local(market)
    raw_legs = build_raw_legs(panels)
    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]
    signal_dates = set(pd.Timestamp(x) for x in market.dates)
    cap_signal = panels["mcap"].reindex(index=[d for d in eval_dates if d in signal_dates])

    def orient(frame):
        panel = frame.reindex(index=eval_dates, columns=stocks).astype("float32")
        values = torch.from_numpy(panel.to_numpy().copy())
        stats = rank_ic_stats(market.context, values)
        chosen = 1
        if not stats or stats["rank_ic"] < 0:
            stats_neg = rank_ic_stats(market.context, -values)
            if stats_neg and (not stats or stats_neg["rank_ic"] > stats["rank_ic"]):
                stats, chosen = stats_neg, -1
        if chosen == -1:
            panel = (-panel).astype("float32")
        return panel, stats, chosen

    lamd = None
    comps = apo.lamd10_k5v2_components(panels)
    for key in ("amt60", "intr20", "tstd20", "amihud20", "vs756"):
        part = comps[key].reindex(index=eval_dates, columns=stocks).rank(axis=1, pct=True)
        lamd = part if lamd is None else lamd + part
    lamd = (lamd / 5.0).astype("float32")
    del comps
    gc.collect()
    lamd_panel, lamd_stats, lamd_dir = orient(lamd)
    lamd_flat = lamd_panel.stack(dropna=False).reindex(market.signal_index)
    lamd_score = _competition_cross_sectional_scores(
        market.signal_frame, {"lamd": lamd_flat},
        [{"key": "lamd", "handler": "lamd", "direction": 1}])
    base = market.seats.drop(columns=[apo.SWAPPED_OUT])
    seed_frame = pd.concat([base, lamd_score], axis=1)
    seed_keys = list(seed_frame.columns)
    b_s, o_s, fs_s, fr_s = market.make_blocks(seed_frame, seed_keys)
    seed_ledger = market.scenario_ledger(b_s, o_s, fs_s, fr_s,
                                         np.ones(len(seed_keys), dtype=np.int64))
    seed_curve = market.build_daily(seed_ledger)
    seed_table = market.monthly_table(seed_curve, seed_ledger)
    apo.log(f"[seed swapsf 5 seats] E={seed_table.e_term.mean():.4f} "
            f"NC={seed_table.nc.mean():.3f} T={seed_table.turnover_month.mean():.3f}")

    combos = json.loads((apo.OUT / "combos.json").read_text(encoding="utf-8"))
    pairs_by_id = {rc["agp_id"]: rc["pairs"] for rc in combos if rc.get("agp_id")}

    rows = []
    for cand_name, agp in CANDS:
        pairs = pairs_by_id[agp]
        comp = None
        for name, weight in pairs:
            leg = name.split(":", 1)[1]
            part = raw_legs[leg].rank(axis=1, pct=True).astype("float32") * float(weight)
            comp = part if comp is None else comp + part
        frame = (comp / len(pairs)).astype("float32")
        del comp
        panel, stats, chosen = orient(frame)
        flat = panel.stack(dropna=False).reindex(market.signal_index)
        cand_score = _competition_cross_sectional_scores(
            market.signal_frame, {"cand": flat},
            [{"key": "cand", "handler": "cand", "direction": 1}])
        for tgt in TARGETS:
            five_frame = pd.concat([seed_frame.drop(columns=[tgt]), cand_score], axis=1)
            keys5 = [k for k in seed_keys if k != tgt] + ["cand"]
            b5, o5, fs5, fr5 = market.make_blocks(five_frame, keys5)
            led = market.scenario_ledger(b5, o5, fs5, fr5, np.ones(len(keys5), dtype=np.int64))
            curve = market.build_daily(led)
            table = market.monthly_table(curve, led)
            merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_five"))
            merged["d_nc"] = merged.nc_five - merged.nc_seed
            merged["d_c_points"] = 44000.0 * W_C * merged.d_nc
            rid = f"{cand_name}-for-{tgt}"
            merged.to_csv(OUT / f"monthly_{rid}.csv", index=False, encoding="utf-8-sig")
            s_local = stats["s_i_rank"]
            d_c = float(merged.d_c_points.mean())
            d_a_poolrule = apo.A_UNIT_POOLRULE * (s_local - MEAN_S_PLAT)
            rows.append(dict(id=rid, cand=cand_name, out=tgt, direction=chosen,
                             s_i_local=s_local, rank_ic=stats["rank_ic"],
                             ic_ir=stats["rank_ic_ir"], win=stats["rank_ic_win"],
                             d_e_mean=float((merged.e_term_five - merged.e_term_seed).mean()),
                             d_t_mean=float((merged.turnover_month_five - merged.turnover_month_seed).mean()),
                             d_nc_mean=float(merged.d_nc.mean()), d_c_points=d_c,
                             d_a_poolrule=d_a_poolrule,
                             d_comb_poolrule=d_a_poolrule + d_c,
                             pos_months=int((merged.d_c_points > 0).sum()), months=len(merged)))
            apo.log(f"[{rid}] s_i={s_local:.4f} dE={(merged.e_term_five - merged.e_term_seed).mean():+.4f} "
                    f"dT={(merged.turnover_month_five - merged.turnover_month_seed).mean():+.3f} "
                    f"dNC={merged.d_nc.mean():+.4f} dC={d_c:+,.0f} "
                    f"dComb_pool={d_a_poolrule + d_c:+,.0f}")
            del five_frame
            del b5, fs5, fr5, merged
            gc.collect()
        del panel, frame, flat, cand_score
        gc.collect()

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "swap_summary.csv", index=False, encoding="utf-8-sig")
    print(summary.round(3).to_string(index=False))
    apo.log("swap ledger done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
