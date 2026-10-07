# -*- coding: utf-8 -*-
"""行为金融因子池级初筛（2026-10-03，本地零平台算力）。

薄包装 e_decomp_direct_20260929：
  - 席位面板指向本机可用副本 ab-batch-20260925/seat_panels_rebuilt.pkl；
  - 候选腿库替换为 behavioral_legs_20261003.build_all（原腿库 + 9 条行为金融腿）。
每个候选按"加第 6 席"记账：ΔE / ΔT / ΔNC / ΔC / ΔComb(uplift|poolrule)，
叠加候选自身 s_i / corr_size / 内在换手。

用法：
  python scripts/_behavioral_screen_20261003.py \
      --specs research_reports/platform_alignment/behavioral-20261003/specs_behavioral_20261003.json \
      --out  research_reports/platform_alignment/behavioral-20261003 --save-daily
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
import behavioral_legs_20261003 as bl  # noqa: E402

direct.get_raw_legs = bl.build_all

if __name__ == "__main__":
    raise SystemExit(direct.main())