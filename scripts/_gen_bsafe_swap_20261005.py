# -*- coding: utf-8 -*-
"""Generate the three k=1 B-safe swap-ladder candidates (2026-10-05 round 2).

Same seat code as _gen_bsafe_20261005.py (byte-identical seat definitions), only the seat
list differs: each candidate drops exactly one live seat and adds K10 (1 换 1 => den_b 5->4 >= 4).
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gen_bsafe_20261005 import (HEAD, T10, BMM, BMP, SIZE, IMP, K10)  # noqa: E402

OUT = Path("research_reports/platform_alignment/bsafe-swap-ladder-20261005")

OLD = ('B 钟表账（第 57/58 条）：本池最多只删 1 个现役席位 => den_b >= 4，样本外时钟不重开；\n'
       'A 段靠"加席"补，而不是靠"换席"。席位代码逐字节沿用已通过平台验证的两个来源：')
NEW = ('B 钟表账（第 57/58 条）：本池 1 换 1、只删 1 个现役席位 => den_b 5->4，仍 >= 4，样本外时钟不重开。\n'
       'A 段靠"换入高 s_i 席"补（ΔA 阶梯，第 59 条 §6.4）。席位代码逐字节沿用已通过平台验证的两个来源：')
assert OLD in HEAD
HEAD_SWAP = HEAD.replace(OLD, NEW)

CANDS = [
    ("pool5-swap-size-k10-20261005.py", "Pool5SwapSizeK10Factor",
     "A 阶梯 T1：删 SIZE-ONLY、换入 K10（ΔA +1,280 = 全 B 安全阶梯最高）",
     [T10, BMM, BMP, IMP, K10]),
    ("pool5-swap-impact-k10-20261005.py", "Pool5SwapImpactK10Factor",
     "A 阶梯 T2：删 H03-impact60、换入 K10（ΔA +1,085）",
     [T10, BMM, BMP, SIZE, K10]),
    ("pool5-swap-e-k10-20261005.py", "Pool5SwapEK10Factor",
     "A 阶梯 T3：删 VERIFY10-E（BM 族，与 F 同族）、换入 K10（ΔA +1,018）",
     [T10, BMP, IMP, SIZE, K10]),
]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, cls, doc, seats in CANDS:
        text = HEAD_SWAP.format(cls=cls, doc=doc, seats=", ".join(seats))
        io.open(OUT / fname, "w", encoding="utf-8", newline="").write(text)
        print("wrote", OUT / fname, len(seats), "seats")