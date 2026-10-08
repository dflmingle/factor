#!/usr/bin/env python3
"""10-04 榜单新增席位的本地最近邻复现扫描（2026-10-08，零平台算力）。

目的：把 10-01~03 换席窗口后新出现在榜单上的席位，拿去和本地生成器签名库
（复用 opp_nearest_full_20260929.load_generators + 本轮 board-higha 本地筛 72 条）
重跑最近邻，挑出"s_i ≥ .03 且本地有 hit/near"的新目标 = 可复现的好因子候选。

输出：research_reports/platform_alignment/board-higha-20261008/nearest_new_20261004.csv
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from opp_nearest_full_20260929 import load_generators  # noqa: E402

PA = ROOT / "research_reports" / "platform_alignment"
NEW_BOARD = PA / "board-details-20261004-period202609" / "factors_all.csv"
OLD_MATCH = PA / "board-details-20260929" / "nearest_local_full.csv"
OUT = PA / "board-higha-20261008" / "nearest_new_20261004.csv"


def main() -> int:
    g = load_generators()
    extra = pd.read_csv(PA / "board-higha-20261008" / "local_screen.csv")
    extra = extra.rename(columns={"candidate": "name", "rank_ic": "ic", "ic_ir": "icir"})
    extra["source"] = "BHA"
    extra = extra[["source", "name", "ic", "icir", "win", "s_i"]]
    g = pd.concat([g, extra], ignore_index=True)
    print(f"generators: {len(g)} rows（A191/P1FAM/BASE/LEG/LEGMIX/BLEND/P2B + BHA72）", flush=True)

    t = pd.read_csv(NEW_BOARD, encoding="utf-8-sig")
    old = pd.read_csv(OLD_MATCH, encoding="utf-8-sig")
    old_keys = set(zip(old["display_name"], old["target"]))
    t = t[t["sample_count"] >= 100].copy()
    t["key"] = list(zip(t["display_name"], t["factor_name"]))
    new = t[~t["key"].isin(old_keys)].copy()
    new = new[(new["ic_mean"].abs() >= 0.03)]
    print(f"10-04 席位 {len(t)} 条（n≥100）；其中相对 09-29 明细为新增 {len(new)} 条（|ic|≥.03）", flush=True)

    gic = g["ic_abs"].to_numpy(float)
    gir = g["icir_abs"].to_numpy(float)
    gwn = g["win"].to_numpy(float)
    rows = []
    for _, r in new.iterrows():
        dic = np.abs(gic - abs(r["ic_mean"]))
        dir_ = np.abs(gir - abs(r["icir"]))
        dwn = np.abs(gwn - r["ic_win_rate"])
        score = dic / 0.02 + dir_ / 0.20 + dwn / 0.06
        b = int(np.argmin(score))
        d0, r0, w0 = float(dic[b]), float(dir_[b]), float(dwn[b])
        verdict = "hit" if (d0 <= 0.010 and r0 <= 0.10 and w0 <= 0.05) else (
            "near" if (d0 <= 0.025 and r0 <= 0.25 and w0 <= 0.10) else "far")
        rows.append(dict(
            display_name=r["display_name"], pool_name=r["pool_name"], rank=r["rank"], cycle=r["cycle"],
            target=r["factor_name"], opp_ic=r["ic_mean"], opp_icir=r["icir"], opp_win=r["ic_win_rate"],
            opp_n=r["sample_count"], opp_si=float(abs(r["ic_mean"]) * abs(r["icir"]) * r["ic_win_rate"]),
            best_source=g["source"].iloc[b], best_cand=g["name"].iloc[b],
            d_ic=d0, d_icir=r0, d_win=w0, verdict=verdict))
    m = pd.DataFrame(rows).sort_values("opp_si", ascending=False)
    m.to_csv(OUT, index=False, encoding="utf-8-sig")

    print("verdict:", m.verdict.value_counts().to_dict())
    good = m[m.verdict != "far"]
    print(f"\n=== 新增且非 far 的席位（{len(good)} 条），按 s_i 排序前 25 ===")
    cols = ["display_name", "target", "opp_si", "opp_ic", "opp_icir", "opp_win", "best_source", "best_cand", "d_ic", "d_icir", "d_win", "verdict"]
    print(good[cols].head(25).to_string(index=False))
    print(f"\n输出 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
