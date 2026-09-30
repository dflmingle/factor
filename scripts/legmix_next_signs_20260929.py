#!/usr/bin/env python3
"""回填腿定向符号：对每条腿计算 5y 定向（+1/-1），写 leg_signs.json 并回填 *_specs.json。

背景：挖掘器 legs[name] = sign x rankpct(raw)，但 specs JSON 里 signed 错写为全 +1，
导致屏/账本重建复合时部分腿反向。本脚本重建真实符号并原地修复 specs。
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legmix_next_legs_20260929 import build_raw_legs  # noqa: E402
from legmix_next_mine_20260929 import ic_series, sched_of, W5  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/legmix-next-20260929"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
T0 = time.time()


def main() -> int:
    panels = pickle.load(PANELS.open("rb"))
    C = panels["close"]
    cal = C.index
    idx = {d: i for i, d in enumerate(cal)}
    w5s = sched_of(cal, W5)
    raw = build_raw_legs(panels)
    signs = {}
    for name, df in raw.items():
        r = df.rank(axis=1, pct=True).astype("float32")
        s5 = ic_series(r, C, cal, w5s, idx)
        m = float(np.nanmean(s5)) if np.isfinite(s5).any() else 0.0
        signs[name] = 1.0 if m >= 0 else -1.0
        print(f"{name:16s} mean_ic={m:+.4f} sign={signs[name]:+.0f}", flush=True)
    (OUT / "leg_signs.json").write_text(json.dumps(signs, indent=1), encoding="utf-8")
    n_files = 0
    for path in sorted(OUT.glob("*_specs.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            step["signed"] = {n: signs.get(n, 1.0) for n in step["legs"]}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        n_files += 1
        print(f"patched {path.name}", flush=True)
    print(f"[{time.time()-T0:.1f}s] signs for {len(signs)} legs, patched {n_files} specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
