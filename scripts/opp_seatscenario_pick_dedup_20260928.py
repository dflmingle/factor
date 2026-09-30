#!/usr/bin/env python3
"""GP 输出 → L3 候选：按“叶字段集合”去重后取头部（2026-09-28，零算力）。

动机：v5 GP 用 `Greater(Greater(x,y),y)` 套娃把同一信号刷满 top-12。
本脚本以叶子字段集合为族键，每族只留 fitness 最高的一条，再取 top-N。

用法: python3 scripts/opp_seatscenario_pick_dedup_20260928.py --run <dir> --top 14
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

OPS = set(
    "Sub Add Mul Div Greater Less Rank Log Abs Sign Mean Std Var Max Min TsMax TsMin TsSum "
    "TsMean TsStd TsMed TsWMA TsEMA TsDelta TsIr TsRank Ref Delay Delta SLog1p Exp Sqrt TsCorr "
    "TsCov TsMinMaxDiff TsMaxDiff TsMinDiff Constant Pow Neg Inv Tanh Sigmoid IfElse TsMad TsDiv "
    "TsVar TsZScore".split()
)


def leaves(formula: str) -> frozenset[str]:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    return frozenset(t for t in tokens if t not in OPS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--top", type=int, default=14)
    ap.add_argument("--min-si", type=float, default=0.0)
    args = ap.parse_args()
    records = json.loads((args.run / "aligned_ic_records.json").read_text(encoding="utf-8-sig"))
    rows = [
        r for r in records
        if r.get("formula") and r.get("s_i") is not None and float(r["s_i"]) >= args.min_si
    ]
    rows.sort(key=lambda r: -float(r.get("fitness") or -1e9))
    groups: dict[tuple[str, ...], dict] = {}
    for r in rows:
        key = tuple(sorted(leaves(r["formula"])))
        groups.setdefault(key, r)
    picked = list(groups.values())[: args.top]
    out = {f"V{i:02d}": r["formula"] for i, r in enumerate(picked, start=1)}
    path = args.run / "swapsearch_candidates.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"records={len(records)} leaf_groups={len(groups)} picked={len(picked)} -> {path}")
    for i, r in enumerate(picked, start=1):
        print(f"  V{i:02d} fit={float(r['fitness']):8.0f} s_i={float(r['s_i']):.4f} "
              f"turn={float(r.get('turnover') or 0):.3f} | {r['formula'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
