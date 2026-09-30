"""F-I10-01 换席/加席的修正口径重算（2026-09-28，零平台算力）。

背景：09-26 平台实测 `POOL5-SWAPF-FI10-20260926`（现役 −VERIFY10-F + F-I10-01）
是迄今唯一桥为正（+531/月）的换池方向；当时"月度 DD 饱和"近似下约 −26。
本脚本用 09-28 修正后的平台 literal rawC 口径（逐月日频账本）独立裁决。

F-I10-01 = (−RANK(market_cap) + impact60) / 2；由 rebuild pkl 的 raw 精确重建：
  raw_f = (−raw['size_only'] + raw['impact60']) / 2
（raw['size_only'] 与标准化 score 反相 = RANK(market_cap)，raw['impact60'] 同相。）

场景（均为 10 日调仓、10 组、0.30% 单边成本、同一信号日）：
  seed    : 现役五席
  swapF   : 现役 − book_to_market_lf_plus_impact + F-I10-01   （平台已测 +531）
  swapE   : 现役 − book_to_market_lf_minus_size + F-I10-01    （BM4seat 第 2 合规化，未测）
  swapSize: 现役 − size_only + F-I10-01                       （F 的 size 冗余测试）
  add6    : 现役 + F-I10-01（第 6 席）

用法：python3 scripts/swapf_recheck_20260928.py [--out DIR] [--device cpu]
"""
from __future__ import annotations

import argparse
import io
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e_decomp_20260928 as ed  # noqa: E402  (sets utf-8 stdout)
import exhaustive_representative_combination as e  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "research_reports/platform_alignment/e-decomp-20260928"

FOUR = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size"]


def build_fi10(raw: dict, signal_frame: pd.DataFrame) -> pd.DataFrame:
    raw_f = (-pd.to_numeric(raw["size_only"], errors="coerce")
             + pd.to_numeric(raw["impact60"], errors="coerce")) / 2.0
    scores = e._competition_cross_sectional_scores(
        signal_frame,
        {"fi10_01": raw_f},
        [{"key": "fi10_01", "handler": "fi10_01", "direction": 1}],
    )
    return scores


def run_scenario(market, frame: pd.DataFrame, keys: list[str]):
    blocks, offsets, fs, fr = market.make_blocks(frame, keys)
    ledger = market.scenario_ledger(blocks, offsets, fs, fr, np.ones(len(keys), dtype=np.int64))
    curve = market.build_daily(ledger)
    table = market.monthly_table(curve, ledger)
    per_rebal = float(ledger.turnover[ledger.valid].mean())
    return ledger, curve, table, per_rebal


def build_frames(market, fi10: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    seats = market.seats
    frames: dict[str, tuple[pd.DataFrame, list[str]]] = {}
    frames["seed"] = (seats.loc[:, ed.POOL].copy(), list(ed.POOL))

    frame = pd.concat([seats.loc[:, FOUR], fi10], axis=1)
    frame.columns = FOUR + ["fi10_01"]
    frames["swapF"] = (frame, list(frame.columns))

    cols_e = ["size_only", "impact60", "t10_size_plus_impact_bm",
              "book_to_market_lf_plus_impact"]
    frame = pd.concat([seats.loc[:, cols_e], fi10], axis=1)
    frame.columns = cols_e + ["fi10_01"]
    frames["swapE"] = (frame, list(frame.columns))

    cols_s = ["impact60", "t10_size_plus_impact_bm",
              "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
    frame = pd.concat([seats.loc[:, cols_s], fi10], axis=1)
    frame.columns = cols_s + ["fi10_01"]
    frames["swapSize"] = (frame, list(frame.columns))

    frame = pd.concat([seats.loc[:, ed.POOL], fi10], axis=1)
    frames["add6"] = (frame, list(frame.columns))
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    payload = pickle.load((args.out / "seat_panels_rebuilt.pkl").open("rb"))
    market = ed.Market(payload, torch.device(args.device))
    fi10 = build_fi10(payload["raw"], market.signal_frame)
    frames = build_frames(market, fi10)

    results: dict[str, dict] = {}
    for label, (frame, keys) in frames.items():
        ledger, curve, table, per_rebal = run_scenario(market, frame, keys)
        results[label] = dict(ledger=ledger, curve=curve, table=table, per_rebal=per_rebal)
        print(f"[{label}] E={table.e_term.mean():.4f} E_med={table.e_term.median():.4f} "
              f"T_month={table.turnover_month.mean():.3f} per_rebal={per_rebal:.4f} "
              f"NC={table.nc.mean():.3f} rex={table.rex_ann.mean():+.4f} "
              f"sr={table.sr_ann.mean():+.3f} dd={table.max_dd.mean():.3f}", flush=True)

    seed_table = results["seed"]["table"]
    seed_per = results["seed"]["per_rebal"]
    rows = []
    for label, res in results.items():
        if label == "seed":
            continue
        table = res["table"]
        merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_x"))
        merged["d_e"] = merged.e_term_x - merged.e_term_seed
        merged["d_t_month"] = merged.turnover_month_x - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_x - merged.nc_seed
        merged["d_c_points"] = 44000.0 * ed.W_C * merged.d_nc
        merged["d_rex_ann"] = merged.rex_ann_x - merged.rex_ann_seed
        merged.to_csv(args.out / f"swapf_monthly_{label}.csv", index=False, encoding="utf-8-sig")

        row = dict(
            label=label,
            n_months=len(merged),
            d_e_mean=float(merged.d_e.mean()),
            d_e_median=float(merged.d_e.median()),
            d_t_month=float(merged.d_t_month.mean()),
            d_per_rebal=res["per_rebal"] - seed_per,
            d_nc=float(merged.d_nc.mean()),
            d_c_points=float(merged.d_c_points.mean()),
            d_rex_ann_pp=float(merged.d_rex_ann.mean()) * 100.0,
            pos_ec_months=int((merged.d_c_points > 0).sum()),
            nc_seed=float(seed_table.nc.mean()),
            nc_x=float(table.nc.mean()),
            e_seed=float(seed_table.e_term.mean()),
            e_x=float(table.e_term.mean()),
        )
        rows.append(row)
        print(f"[{label}] dE={row['d_e_mean']:+.4f} dT_month={row['d_t_month']:+.4f} "
              f"dT_rebal={row['d_per_rebal']:+.4f} dNC={row['d_nc']:+.4f} "
              f"dC={row['d_c_points']:+,.0f} dRex={row['d_rex_ann_pp']:+.3f}pp", flush=True)

    summary = pd.DataFrame(rows).sort_values("d_c_points", ascending=False)
    summary.to_csv(args.out / "swapf_recheck_summary.csv", index=False, encoding="utf-8-sig")
    meta = dict(
        fi10_formula="(-RANK(market_cap) + impact60) / 2",
        note="raw reconstruction: (-raw[size_only] + raw[impact60]) / 2",
        seed_turnover_per_rebal=seed_per,
        seed_e_mean=float(seed_table.e_term.mean()),
        seed_nc_mean=float(seed_table.nc.mean()),
    )
    (args.out / "swapf_recheck_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + summary.to_string(index=False), flush=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
