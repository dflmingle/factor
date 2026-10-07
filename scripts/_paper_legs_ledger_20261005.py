# -*- coding: utf-8 -*-
"""Pool-level ledger for literature legs (2026-10-05, zero platform compute).

Wraps e_decomp_direct_20260929 with panel-only literature legs
(paper_legs_20261005).  Each spec is booked as either a 6th seat or a swap for
one weak incumbent seat, against the current 5-seat pool.

Usage:
  python scripts/_paper_legs_ledger_20261005.py \
      --specs research_reports/platform_alignment/literature-legs-20261005/specs_swap.json \
      --out  research_reports/platform_alignment/literature-legs-20261005 --save-daily
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import e_decomp_20260928 as ed  # noqa: E402

ed.DEFAULT_REBUILD = (ROOT / "research_reports" / "platform_alignment"
                      / "ab-batch-20260925" / "seat_panels_rebuilt.pkl")

import e_decomp_direct_20260929 as direct  # noqa: E402
import paper_legs_20261005 as pl  # noqa: E402

direct.get_raw_legs = pl.build_all

if __name__ == "__main__":
    raise SystemExit(direct.main())