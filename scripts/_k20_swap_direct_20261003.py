# -*- coding: utf-8 -*-
"""K20(LAMD20-K5V2) 换席/加席本地全账（2026-10-03，零平台算力）。

薄包装：只把 e_decomp_20260928.DEFAULT_REBUILD 从缺失的
e-decomp-20260928/seat_panels_rebuilt.pkl 改指本机可用的
ab-batch-20260925/seat_panels_rebuilt.pkl（含 5 席 scores/signal_frame/returns/dates），
再调用 e_decomp_direct_20260929.main()；口径、seat_si 字典与输出格式不变。

用法：
  python scripts/_k20_swap_direct_20261003.py \
      --specs research_reports/platform_alignment/k20-swap-eval-20261003/specs_k20_swap.json \
      --out  research_reports/platform_alignment/k20-swap-eval-20261003 --save-daily
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

if __name__ == "__main__":
    raise SystemExit(direct.main())
