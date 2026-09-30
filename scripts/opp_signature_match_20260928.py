"""对手因子签名匹配地图（2026-09-28，本地零平台算力）。

目标库：榜单 20 池 297 条对手因子（名字+平台签名 ic/icir/win），
生成器库：本地已有四个签名来源（全部 5y / n=120 口径）——
  A191 全库 alpha191_local_screen.csv
  P1 家族 p1_family_scan.csv
  repro 基线 repro_opp_factors.csv
  LEGMIX 腿/复合 legs.csv + legmix_results.csv
  （可选 BLEND、P2B 三窗口表）

输出：每条对手目标的最近本地构造 + 维度缺口；按 verdict 汇总。
verdict: hit（|dic|<=.010, |dicir|<=.10, |dwin|<=.05）/ near（.025/.25/.10）/ far。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PA = ROOT / "research_reports/platform_alignment"
OUT = PA / "opp-signature-match-20260928"


def load_generators() -> pd.DataFrame:
    rows = []
    a = pd.read_csv(PA / "alpha191-local-20260923/alpha191_local_screen.csv")
    a = a.rename(columns={"factor": "name", "rank_ic": "ic", "ic_ir": "icir"})
    a["source"] = "A191"
    rows.append(a[["source", "name", "ic", "icir", "win", "s_i"]])

    p = pd.read_csv(PA / "side-line-20260927/p1_family_scan.csv")
    p = p.rename(columns={"cand": "name"})
    p["source"] = "P1FAM"
    rows.append(p[["source", "name", "ic", "icir", "win", "s_i"]])

    r = pd.read_csv(PA / "side-line-20260927/repro_opp_factors.csv")
    r = r.rename(columns={"candidate": "name", "ic_mean": "ic"})
    r["source"] = "BASE"
    rows.append(r[["source", "name", "ic", "icir", "win", "s_i"]])

    l = pd.read_csv(PA / "legmix-20260928/legs.csv")
    l = l.rename(columns={"leg": "name"})
    l["source"] = "LEG"
    rows.append(l[["source", "name", "ic", "icir", "win", "s_i"]])

    m = pd.read_csv(PA / "legmix-20260928/legmix_results.csv")
    m = m.rename(columns={"leg": "name", "ic_5y": "ic", "icir_5y": "icir", "win_5y": "win", "s_i_5y": "s_i"})
    m["name"] = "mix" + m["k"].astype(str) + "_" + m["name"]
    m["source"] = "LEGMIX"
    rows.append(m[["source", "name", "ic", "icir", "win", "s_i"]])

    b = pd.read_csv(PA / "side-line-20260927/p0b_blend_sweep.csv")
    b = b.rename(columns={"base": "b0", "lt": "name"})
    b["name"] = b["b0"].astype(str) + "x" + b["name"].astype(str) + "_w" + b["w"].astype(str)
    b["source"] = "BLEND"
    rows.append(b[["source", "name", "ic", "icir", "win", "s_i"]])

    p2 = pd.read_csv(PA / "side-line-20260927/p2b_report.csv")
    p2 = p2.rename(columns={"cand": "name", "ic5": "ic", "ir5": "icir", "win5": "win", "si5": "s_i"})
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
    OUT.mkdir(parents=True, exist_ok=True)
    g = load_generators()
    print(f"generators: {len(g)} rows, sources={g.source.value_counts().to_dict()}", flush=True)
    t = pd.read_csv(PA / "side-line-20260927/opp_factor_rows.csv", encoding="utf-8-sig")
    t["ic_abs"] = t["ic_mean"].abs()
    t["icir_abs"] = t["icir"].abs()
    t["win"] = t["ic_win_rate"]
    print(f"targets: {len(t)}", flush=True)

    gc = g[["source", "name", "ic_abs", "icir_abs", "win", "s_i"]].to_numpy(dtype=object)
    gic = g["ic_abs"].to_numpy(dtype=float)
    gir = g["icir_abs"].to_numpy(dtype=float)
    gwn = g["win"].to_numpy(dtype=float)

    out = []
    for _, row in t.iterrows():
        dic = np.abs(gic - abs(row["ic_mean"]))
        dir_ = np.abs(gir - abs(row["icir"]))
        dwn = np.abs(gwn - row["ic_win_rate"])
        score = dic / 0.02 + dir_ / 0.20 + dwn / 0.06
        order = np.argsort(score)
        picks = []
        for idx in order[:3]:
            picks.append((str(g["source"].iloc[idx]), str(g["name"].iloc[idx]),
                          float(dic[idx]), float(dir_[idx]), float(dwn[idx])))
        b = order[0]
        dic0, dir0, dwn0 = dic[b], dir_[b], dwn[b]
        verdict = "hit" if (dic0 <= 0.010 and dir0 <= 0.10 and dwn0 <= 0.05) else (
            "near" if (dic0 <= 0.025 and dir0 <= 0.25 and dwn0 <= 0.10) else "far")
        top = picks[0]
        out.append(dict(
            pool_rank=row["pool_rank"], pool=row["pool"], target=row["name"],
            opp_ic=row["ic_mean"], opp_icir=row["icir"], opp_win=row["ic_win_rate"], opp_si=row["s_i_a"],
            best_source=top[0], best_cand=top[1],
            d_ic=dic0, d_icir=dir0, d_win=dwn0, verdict=verdict,
            c2=f"{picks[1][0]}:{picks[1][1]}", c3=f"{picks[2][0]}:{picks[2][1]}",
        ))
    match = pd.DataFrame(out)
    match.to_csv(OUT / "match_table.csv", index=False, encoding="utf-8-sig")

    print("\nverdict counts:", match.verdict.value_counts().to_dict(), flush=True)
    print("\n=== hits ===")
    hits = match[match.verdict == "hit"].sort_values("opp_si", ascending=False)
    if len(hits):
        print(hits[["pool", "target", "opp_si", "best_source", "best_cand", "d_ic", "d_icir", "d_win"]]
              .to_string(index=False), flush=True)
    print("\n=== near (top20 by opp_si) ===")
    near = match[match.verdict == "near"].sort_values("opp_si", ascending=False)
    print(near.head(20)[["pool", "target", "opp_si", "best_source", "best_cand", "d_ic", "d_icir", "d_win"]]
          .to_string(index=False), flush=True)
    print("\n=== far but high si (top15) ===")
    far = match[match.verdict == "far"].sort_values("opp_si", ascending=False)
    print(far.head(15)[["pool", "target", "opp_si", "best_source", "best_cand", "d_ic", "d_icir", "d_win"]]
          .to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
