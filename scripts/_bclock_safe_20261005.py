# -*- coding: utf-8 -*-
"""B-safe frontier: never drop more than 1 of the 5 live seats (2026-10-05).

den_b >= 4 保证样本外时钟不重开 => 最多删 1 席、其余靠"加席"补 A。
  S1_keep4_drop_size_add4   保留 4（丢 size_only）+ K10 K20 STD20 AMTDISP           -> 8 席
  S2_keep4_drop_size_add5   同上 + TOPMIX                                          -> 9 席
  S3_keep4_drop_impact_add5 丢 impact60（保留 size_only）+ K10 K20 STD20 AMTDISP TOPMIX -> 9 席
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _poolmix_ledger_20261004 as pm  # noqa: E402

KEEP_NO_SIZE = ["t10_size_plus_impact_bm", "book_to_market_lf_minus_size",
                "book_to_market_lf_plus_impact", "impact60"]
KEEP_NO_IMPACT = ["t10_size_plus_impact_bm", "book_to_market_lf_minus_size",
                  "book_to_market_lf_plus_impact", "size_only"]
NEW4 = ["K10", "K20", "STD20", "AMTDISP"]

pm.POOLS_FIXED = [
    ("S1_keep4_drop_size_add4", KEEP_NO_SIZE + NEW4),
    ("S2_keep4_drop_size_add5", KEEP_NO_SIZE + NEW4 + ["TOPMIX"]),
    ("S3_keep4_drop_impact_add5", KEEP_NO_IMPACT + NEW4 + ["TOPMIX"]),
]
pm.OUT = ROOT / "research_reports" / "platform_alignment" / "bclock-ledger-20261005"

if __name__ == "__main__":
    raise SystemExit(pm.main())