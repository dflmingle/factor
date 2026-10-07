# -*- coding: utf-8 -*-
"""L6 variant ledger (2026-10-05, zero platform compute).

Wraps _poolmix_ledger_20261004 with extra pool variants around L6, to decide
what (if anything) deserves tonight's expiring platform credits.

Variants:
  L6_control             t10 + K10 + K20 + STD20 + AMTDISP          (current main)
  L6b_topmix_for_amt     t10 + K10 + K20 + STD20 + TOPMIX           (higher raw_a, higher turnover?)
  L6c_plus_topmix        L6 + TOPMIX (6 seats, raw_a still > .056 -> NA capped .70?)
  L6e_plus_bm_minus      L6 + book_to_market_lf_minus_size (6 seats, low-turnover 6th)
  L2c_keep_impact60      t10 + impact60 + K10 + TOPMIX + STD20      (designated backup)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _poolmix_ledger_20261004 as pm  # noqa: E402

T10 = "t10_size_plus_impact_bm"
BMM = "book_to_market_lf_minus_size"

pm.POOLS_FIXED = [
    ("L6_control", [T10, "K10", "K20", "STD20", "AMTDISP"]),
    ("L6b_topmix_for_amt", [T10, "K10", "K20", "STD20", "TOPMIX"]),
    ("L6c_plus_topmix", [T10, "K10", "K20", "STD20", "AMTDISP", "TOPMIX"]),
    ("L6e_plus_bm_minus", [T10, "K10", "K20", "STD20", "AMTDISP", BMM]),
    ("L2c_keep_impact60", [T10, "impact60", "K10", "TOPMIX", "STD20"]),
]
pm.OUT = ROOT / "research_reports" / "platform_alignment" / "pool-variants-20261005"

if __name__ == "__main__":
    raise SystemExit(pm.main())