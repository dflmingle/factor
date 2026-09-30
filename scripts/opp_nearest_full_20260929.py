#!/usr/bin/env python3
"""全量对手因子 vs 本地生成器签名最近邻（2026-09-29，零平台算力）。

目标库：board-details-20260929/factors_all.csv（286 池、3290 条，抓取 2026-09-29）
生成器库：复用 opp_signature_match_20260928.load_generators（464 条本地构造）
距离：|dic|/.02 + |dicir|/.20 + |dwin|/.06（与 09-28 版一致），全部用绝对值口径。
输出：board-details-20260929/nearest_local_full.csv + 控制台摘要。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

OUT = ROOT / "research_reports/platform_alignment/board-details-20260929"
PA = ROOT / "research_reports/platform_alignment"


def load_generators() -> pd.DataFrame:
    """本地生成器签名库（与 opp_signature_match_20260928.load_generators 相同的来源）。"""
    rows = []
    a = pd.read_csv(PA / "alpha191-local-20260923/alpha191_local_screen.csv")
    a = a.rename(columns={"factor": "name", "rank_ic": "ic", "ic_ir": "icir"})
    a["source"] = "A191"
    rows.append(a[["source", "name", "ic", "icir", "win", "s_i"]])
    p = pd.read_csv(PA / "side-line-20260927/p1_family_scan.csv").rename(columns={"cand": "name"})
    p["source"] = "P1FAM"
    rows.append(p[["source", "name", "ic", "icir", "win", "s_i"]])
    r = pd.read_csv(PA / "side-line-20260927/repro_opp_factors.csv").rename(columns={"candidate": "name", "ic_mean": "ic"})
    r["source"] = "BASE"
    rows.append(r[["source", "name", "ic", "icir", "win", "s_i"]])
    l = pd.read_csv(PA / "legmix-20260928/legs.csv").rename(columns={"leg": "name"})
    l["source"] = "LEG"
    rows.append(l[["source", "name", "ic", "icir", "win", "s_i"]])
    m = pd.read_csv(PA / "legmix-20260928/legmix_results.csv")
    m = m.rename(columns={"leg": "name", "ic_5y": "ic", "icir_5y": "icir", "win_5y": "win", "s_i_5y": "s_i"})
    m["name"] = "mix" + m["k"].astype(str) + "_" + m["name"]
    m["source"] = "LEGMIX"
    rows.append(m[["source", "name", "ic", "icir", "win", "s_i"]])
    b = pd.read_csv(PA / "side-line-20260927/p0b_blend_sweep.csv").rename(columns={"base": "b0", "lt": "name"})
    b["name"] = b["b0"].astype(str) + "x" + b["name"].astype(str) + "_w" + b["w"].astype(str)
    b["source"] = "BLEND"
    rows.append(b[["source", "name", "ic", "icir", "win", "s_i"]])
    p2 = pd.read_csv(PA / "side-line-20260927/p2b_report.csv").rename(columns={"cand": "name", "ic5": "ic", "ir5": "icir", "win5": "win", "si5": "s_i"})
    p2["source"] = "P2B"
    rows.append(p2[["source", "name", "ic", "icir", "win", "s_i"]])
    g = pd.concat(rows, ignore_index=True)
    for c in ("ic", "icir", "win", "s_i"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g.dropna(subset=["ic", "icir", "win"]).reset_index(drop=True)
    g["ic_abs"] = g["ic"].abs()
    g["icir_abs"] = g["icir"].abs()
    return g


def main() -> int:
    g = load_generators()
    t = pd.read_csv(OUT / "factors_all.csv", encoding="utf-8-sig")
    t = t[t["sample_count"] >= 100].copy()  # 排除暖机样本不足的因子
    t["ic_abs"] = t["ic_mean"].abs()
    t["icir_abs"] = t["icir"].abs()
    t["s_i_abs"] = t["ic_abs"] * t["icir_abs"] * t["ic_win_rate"]
    t = t.sort_values("icir_abs", ascending=False)
    print(f"generators: {len(g)} rows | targets(full-sample): {len(t)}", flush=True)

    gic = g["ic_abs"].to_numpy(float)
    gir = g["icir_abs"].to_numpy(float)
    gwn = g["win"].to_numpy(float)
    rows = []
    for _, r in t.iterrows():
        dic = np.abs(gic - r["ic_abs"])
        dir_ = np.abs(gir - r["icir_abs"])
        dwn = np.abs(gwn - r["ic_win_rate"])
        score = dic / 0.02 + dir_ / 0.20 + dwn / 0.06
        b = int(np.argmin(score))
        d0, r0, w0 = float(dic[b]), float(dir_[b]), float(dwn[b])
        verdict = "hit" if (d0 <= 0.010 and r0 <= 0.10 and w0 <= 0.05) else (
            "near" if (d0 <= 0.025 and r0 <= 0.25 and w0 <= 0.10) else "far")
        rows.append(dict(
            display_name=r["display_name"], pool_name=r["pool_name"], cycle=r["cycle"],
            target=r["factor_name"], opp_ic=r["ic_mean"], opp_icir=r["icir"], opp_win=r["ic_win_rate"],
            opp_n=r["sample_count"], opp_si=float(r["s_i_abs"]),
            best_source=g["source"].iloc[b], best_cand=g["name"].iloc[b],
            d_ic=d0, d_icir=r0, d_win=w0, verdict=verdict,
        ))
    m = pd.DataFrame(rows)
    m.to_csv(OUT / "nearest_local_full.csv", index=False, encoding="utf-8-sig")

    print("\nverdict:", m.verdict.value_counts().to_dict())
    top = m.sort_values("opp_icir", ascending=False).head(40)
    print("\n=== icir top40 对手因子 -> 最近本地构造 ===")
    print(top[["display_name", "target", "opp_ic", "opp_icir", "opp_win", "opp_n",
               "best_source", "best_cand", "d_ic", "d_icir", "d_win", "verdict"]].to_string(index=False))
    print("\n=== 800+ ICIR 分布中的 far（icir>=0.9）===")
    far = m[(m.verdict == "far") & (m.opp_icir >= 0.9)]
    print(len(far), "far of", int((m.opp_icir >= 0.9).sum()), "targets with icir>=0.9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
