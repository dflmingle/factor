#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Signed (equal-weight) variant ledger for the AlphaGen pool-opt candidates.

Companion to scripts/alphagen_pool_optimize_20261002.py (zero platform compute).
The main script's ledger evaluated the optimiser-weighted (W) composites; this
run evaluates the signed equal-weight (S) specs (specs_alphagen.json) with the
exact same seed / pool machinery, writing to .../alphagen-pool-opt-20261002/signed/
so the W results are left untouched.

Usage (easyrl4rec env only):
  D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts/_alphagen_signed_ledger_20261002.py
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
    A_UNIT, MEAN_S_LOCAL, MEAN_S_PLAT, UPLIFT, W_C, Market, rank_ic_stats,
)
from exhaustive_representative_combination import _competition_cross_sectional_scores  # noqa: E402

OUT = apo.OUT / "signed"
SPECS = apo.OUT / "specs_alphagen.json"
WANT = ["AGP01S", "AGP03S", "AGP05S"]


def signed_composite(raw_legs: dict, signed: dict) -> pd.DataFrame:
    comp = None
    for name, sign in signed.items():
        part = (float(sign) * raw_legs[name]).rank(axis=1, pct=True).astype("float32")
        comp = part if comp is None else comp + part
    return (comp / float(len(signed))).astype("float32")


def main() -> int:
    apo.start_watchdog()
    OUT.mkdir(parents=True, exist_ok=True)

    specs = {s["name"]: s for s in json.loads(SPECS.read_text(encoding="utf-8"))}
    picked = [specs[n] for n in WANT if n in specs]
    apo.log(f"signed ledger specs: {[s['name'] for s in picked]}")

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

    rows = []
    for spec in picked:
        frame = signed_composite(raw_legs, spec["signed"])
        panel, stats, chosen = orient(frame)
        flat = panel.stack(dropna=False).reindex(market.signal_index)
        cand_score = _competition_cross_sectional_scores(
            market.signal_frame, {"cand": flat},
            [{"key": "cand", "handler": "cand", "direction": 1}])
        six_frame = pd.concat([seed_frame, cand_score], axis=1)
        keys6 = seed_keys + ["cand"]
        b6, o6, fs6, fr6 = market.make_blocks(six_frame, keys6)
        led = market.scenario_ledger(b6, o6, fs6, fr6, np.ones(len(keys6), dtype=np.int64))
        curve = market.build_daily(led)
        table = market.monthly_table(curve, led)
        merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_six"))
        merged["d_e"] = merged.e_term_six - merged.e_term_seed
        merged["d_t"] = merged.turnover_month_six - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_six - merged.nc_seed
        merged["d_c_points"] = 44000.0 * W_C * merged.d_nc
        merged.to_csv(OUT / f"monthly_{spec['name']}.csv", index=False, encoding="utf-8-sig")
        s_local = stats["s_i_rank"]
        d_c = float(merged.d_c_points.mean())
        d_a_uplift = A_UNIT * UPLIFT * (s_local - MEAN_S_LOCAL)
        d_a_poolrule = apo.A_UNIT_POOLRULE * (s_local - MEAN_S_PLAT)
        cs_vals = []
        for d in cap_signal.index:
            if d not in panel.index:
                continue
            a = panel.loc[d].to_numpy(dtype="float64")
            b = cap_signal.loc[d].to_numpy(dtype="float64")
            m = np.isfinite(a) & np.isfinite(b)
            if int(m.sum()) < 200:
                continue
            ar = pd.Series(a[m]).rank().to_numpy()
            br = pd.Series(b[m]).rank().to_numpy()
            cs_vals.append(float(np.corrcoef(ar, br)[0, 1]))
        corr_size = float(np.mean(cs_vals)) if cs_vals else float("nan")
        turn_intrinsic = float(led.turnover[led.valid].mean())
        rows.append(dict(
            id=spec["name"], n_legs=len(spec["signed"]),
            legs=";".join(f"{n}:{w:+.0f}" for n, w in spec["signed"].items()),
            direction=chosen, s_i_local=s_local, rank_ic=stats["rank_ic"],
            ic_ir=stats["rank_ic_ir"], win=stats["rank_ic_win"], corr_size=corr_size,
            turn_intrinsic=turn_intrinsic, d_e_mean=float(merged.d_e.mean()),
            d_t_mean=float(merged.d_t.mean()), d_nc_mean=float(merged.d_nc.mean()),
            d_c_points=d_c, d_a_uplift=d_a_uplift, d_comb_uplift=d_a_uplift + d_c,
            d_a_poolrule=d_a_poolrule, d_comb_poolrule=d_a_poolrule + d_c,
            pos_months=int((merged.d_c_points > 0).sum()), months=len(merged)))
        apo.log(f"[{spec['name']}] s_i={s_local:.4f} corrSz={corr_size:+.2f} "
                f"dE={merged.d_e.mean():+.4f} dT={merged.d_t.mean():+.3f} "
                f"dNC={merged.d_nc.mean():+.4f} dC={d_c:+,.0f} "
                f"dComb_up={d_a_uplift + d_c:+,.0f} dComb_pool={d_a_poolrule + d_c:+,.0f}")
        del panel, frame, flat, cand_score, six_frame, b6, fs6, fr6, merged
        gc.collect()

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "ledger_summary_signed.csv", index=False, encoding="utf-8-sig")
    print(summary.round(3).to_string(index=False))
    apo.log("signed ledger done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
