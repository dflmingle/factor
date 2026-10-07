# -*- coding: utf-8 -*-
"""Keep-all-5 add-seat variants (2026-10-05, zero platform compute).

B-clock relevance: keeping all 5 current seats means den_b stays >= 4, so the
sample-out clock is never reset.  Only the pool-level A/C move.
  A6_keep5_add_K10                现役5 + K10
  A9_keep5_add_K10K20STD20AMTDISP 现役5 + K10 + K20 + STD20 + AMTDISP
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _poolmix_ledger_20261004 as pm  # noqa: E402

SEED = list(pm.ed.POOL)
pm.POOLS_FIXED = [
    ("A6_keep5_add_K10", SEED + ["K10"]),
    ("A9_keep5_add_4seats", SEED + ["K10", "K20", "STD20", "AMTDISP"]),
]
pm.OUT = ROOT / "research_reports" / "platform_alignment" / "bclock-ledger-20261005"

if __name__ == "__main__":
    raise SystemExit(pm.main())