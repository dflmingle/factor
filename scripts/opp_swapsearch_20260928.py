#!/usr/bin/env python3
"""候选 × 六场景（1 加席 + 5 换席）真实账本评估（2026-09-28，零平台算力）。

对每个候选：
  append        : 现役五席 + cand（第 6 席）
  swap_<seat>   : 现役 − seat + cand
逐月账面 ΔE / ΔT / ΔNC / ΔC 分/月，另给 A 段结构分（换席分母 5、加席分母 6）。
输出：e-decomp-20260928/swapsearch_summary.csv

用法: python3 scripts/opp_swapsearch_20260928.py --candidates <json> [--names a,b] [--top N]
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import e_decomp_20260928 as ed  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402
import alphaprobe_gp_tushare as gp  # noqa: E402

OUT = ed.DEFAULT_OUT
W_C = ed.W_C
SEAT_S_LOCAL = {  # SCORE_RULES 五席本地 s_i
    "size_only": 0.00881,
    "impact60": 0.01761,
    "t10_size_plus_impact_bm": 0.06061,
    "book_to_market_lf_minus_size": 0.02274,
    "book_to_market_lf_plus_impact": 0.02317,
}
MEAN_S_LOCAL = float(np.mean(list(SEAT_S_LOCAL.values())))
A_UNIT6 = 44000.0 * ed.W_A / (6 * 0.08)
A_UNIT5 = 44000.0 * ed.W_A / (5 * 0.08)
UPLIFT = ed.UPLIFT


def cand_scores(market, formula: str) -> tuple[pd.DataFrame, float, float]:
    expr = gp.evaluate_formula(formula, market.namespace)
    with torch.no_grad():
        values = gp.finite_as_nan(expr.evaluate(market.data))
    del expr
    stats = ed.rank_ic_stats(market.context, values)
    direction = 1 if (stats and stats["rank_ic"] >= 0) else -1
    oriented = values if direction == 1 else -values
    spots = np.asarray(market.context.signal_data_positions, dtype=np.int64)
    panel = pd.DataFrame(oriented[spots].detach().cpu().numpy(), index=market.dates,
                         columns=[str(x) for x in market.data._stock_ids])
    flat = panel.stack(dropna=False).reindex(market.signal_index)
    seat_size = market.seats["size_only"].reset_index(drop=True)
    corr_df = pd.DataFrame({"cand": flat.to_numpy(),
                            "seat": seat_size.to_numpy()}, index=flat.index)
    corr_size = float(corr_df.groupby(level=0).apply(
        lambda g: g.cand.corr(g.seat, method="spearman")
        if g.cand.notna().sum() > 100 else np.nan).mean())
    score = e._competition_cross_sectional_scores(
        market.signal_frame, {"cand": flat},
        [{"key": "cand", "handler": "cand", "direction": 1}])
    del values, oriented, panel, corr_df
    return score, float(stats["s_i_rank"]), corr_size


def run_frame(market, frame: pd.DataFrame, keys: list[str]):
    blocks, offsets, fs, fr = market.make_blocks(frame, keys)
    ledger = market.scenario_ledger(blocks, offsets, fs, fr, np.ones(len(keys), dtype=np.int64))
    curve = market.build_daily(ledger)
    return market.monthly_table(curve, ledger)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--names", default="")
    ap.add_argument("--top", type=int, default=0, help="只跑 0=全部")
    ap.add_argument("--out-name", default="swapsearch_summary.csv")
    args = ap.parse_args()

    specs = __import__("json").loads(args.candidates.read_text(encoding="utf-8"))
    if args.names:
        wanted = [x for x in args.names.split(",") if x]
        specs = {k: v for k, v in specs.items() if k in wanted}

    payload = pickle.load(ed.DEFAULT_REBUILD.open("rb"))
    market = ed.Market(payload, torch.device("cpu"))
    seats = market.seats
    seed_table = run_frame(market, seats.loc[:, ed.POOL].copy(), list(ed.POOL))
    print(f"[seed] E={seed_table.e_term.mean():.4f} NC={seed_table.nc.mean():.3f}", flush=True)

    rows = []
    for name, formula in specs.items():
        try:
            cand_score, s_local, corr_size = cand_scores(market, formula)
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] EVAL FAIL {type(exc).__name__}: {exc}"[:160], flush=True)
            continue
        scenarios = {"append": list(ed.POOL)}
        for seat in ed.POOL:
            scenarios[f"swap_{seat}"] = [k for k in ed.POOL if k != seat]
        for label, kept in scenarios.items():
            if label == "append":
                frame = pd.concat([seats.loc[:, ed.POOL], cand_score], axis=1)
                keys = list(ed.POOL) + ["cand"]
                d_a = A_UNIT6 * UPLIFT * (s_local - MEAN_S_LOCAL) / 6 * 6  # 分母6
                d_a = A_UNIT6 * UPLIFT * (s_local - MEAN_S_LOCAL)
                d_raw = (s_local - MEAN_S_LOCAL) / 6
            else:
                frame = pd.concat([seats.loc[:, kept], cand_score], axis=1)
                keys = kept + ["cand"]
                old = SEAT_S_LOCAL[label.split("swap_", 1)[1]]
                d_a = A_UNIT5 * UPLIFT * (s_local - old)
                d_raw = (s_local - old) / 5
            table = run_frame(market, frame, keys)
            merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_x"))
            d_c = float((44000.0 * W_C * (merged.nc_x - merged.nc_seed)).mean())
            rows.append(dict(
                name=name, scenario=label, s_i_local=s_local, corr_size=corr_size,
                d_raw_a=d_raw, d_a_points=d_a, d_c_points=d_c, d_comb=d_a + d_c,
                d_comb_with_b=d_a + d_c + 15400.0 * d_raw / 0.06,
                d_e_mean=float((merged.e_term_x - merged.e_term_seed).mean()),
                d_t_mean=float((merged.turnover_month_x - merged.turnover_month_seed).mean()),
                d_nc=float((merged.nc_x - merged.nc_seed).mean()),
                tau=float(table.turnover_month.mean()),
            ))
            print(f"[{name}] {label:<32} dA={d_a:+8.0f} dC={d_c:+8.0f} dComb={d_a+d_c:+8.0f} "
                  f"(dE={rows[-1]['d_e_mean']:+.3f} dT={rows[-1]['d_t_mean']:+.3f} dNC={rows[-1]['d_nc']:+.4f})",
                  flush=True)
        pd.DataFrame(rows).to_csv(OUT / args.out_name, index=False, encoding="utf-8-sig")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / args.out_name, index=False, encoding="utf-8-sig")
    if len(df):
        best = df.sort_values("d_comb", ascending=False).groupby("name").head(1)
        print("\n=== 每候选最优场景（按 ΔComb = A + C）===", flush=True)
        print(best.sort_values("d_comb", ascending=False)
              [["name", "scenario", "s_i_local", "d_a_points", "d_c_points", "d_comb", "d_comb_with_b"]]
              .round(3).to_string(index=False), flush=True)
    print(f"\nwritten {OUT/args.out_name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
