#!/usr/bin/env python3
"""GP 输出 → L3 六场景账本 的衔接器（2026-09-28，零平台算力）。

读 seat-scenario-gp-20260928/aligned_ic_records.json（含 AlphaPROBE formula、fitness、
s_i、turnover），取 top-N 写成 candidates JSON，交给 opp_swapsearch_20260928.py 跑真账本。

用法: python3 scripts/opp_seatscenario_pipeline_20260928.py --top 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "research_reports/platform_alignment/seat-scenario-gp-20260928"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=RUN)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--min-si", type=float, default=0.0)
    args = ap.parse_args()

    records = json.loads((args.run / "aligned_ic_records.json").read_text(encoding="utf-8-sig"))
    rows = [
        r for r in records
        if r.get("formula") and r.get("s_i") is not None
        and float(r["s_i"]) >= args.min_si
    ]
    rows.sort(key=lambda r: -float(r.get("fitness") or -1e9))
    picked = {}
    for i, r in enumerate(rows[: args.top], start=1):
        picked[f"SC{i:02d}"] = r["formula"]
    out = args.run / "swapsearch_candidates.json"
    out.write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"records={len(records)} picked={len(picked)} -> {out}")
    for i, r in enumerate(rows[: args.top], start=1):
        print(f"  SC{i:02d} fit={float(r.get('fitness') or 0):9.1f} s_i={float(r['s_i']):.4f} "
              f"turn={float(r.get('turnover') or 0):.3f} | {r['formula'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
