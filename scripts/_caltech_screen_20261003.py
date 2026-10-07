# -*- coding: utf-8 -*-
"""技术指标目录池级初筛（2026-10-03，本地零平台算力）。

薄包装 e_decomp_direct_20260929：
  - 席位面板指向本机 ab-batch-20260925/seat_panels_rebuilt.pkl；
  - 腿库替换为 caltech_legs_20261003.build_all（19 条 cal/技术腿 + 4 条组合腿）。
每个候选按"加第 6 席"（或 Swap）记账：ΔE / ΔT / ΔNC / ΔC / ΔComb，
叠加候选自身 s_i / corr_size / 内在换手。

用法：
  python scripts/_caltech_screen_20261003.py \
      --specs research_reports/platform_alignment/caltech-20261003/specs_caltech_20261003.json \
      --out  research_reports/platform_alignment/caltech-20261003 --save-daily
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
import caltech_legs_20261003 as ct  # noqa: E402

direct.get_raw_legs = ct.build_all

if __name__ == "__main__":
    raise SystemExit(direct.main())