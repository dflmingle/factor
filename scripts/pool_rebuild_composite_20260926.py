"""重建池综合口径枚举（2026-09-26 夜，零平台算力）。

问题：把现役 5 席全部推倒，用全库 s_i 最强 / 综合最优的因子重建池，能不能赢现役？

口径（同 swap_size_marginals_20260926 与 SCORE_RULES.md）：
  rawA = mean(席位 s_i)；NA = min(rawA/0.08, 0.70)
  net = 席位净额均值；turn = 席位每次调仓换手均值
  T* = net*SR*(1-1.2*DDm)/0.6；NC(k) = min(1, T*/max(k*turn, 0.30))，k 按 46/7/7 个月
  Comb = 0.20*NA + 0.35*NB + 0.45*E[NC]，NB=0（新池 B 未起算）；分/月 = Comb*40000*1.10
席位 s_i 来自 platform_si_scan.csv（243 个 run 的 RankIC 序列重算）。
"""
from __future__ import annotations
import io, itertools, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/rebuild-composite-20260926"
OUT.mkdir(parents=True, exist_ok=True)

DD_MONTH_BASE = 0.0459
DD5_BASE = 0.3164
KS = {1: 7, 2: 46, 3: 7}

INCUMBENT = ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "VERIFY10-E260910-04",
             "VERIFY10-F260910-12", "T10-ADD-BM-20260911"]

reps = []
for f in sorted(ROOT.glob("*.report.csv")):
    try:
        d = pd.read_csv(f, encoding="utf-8-sig")
    except Exception:
        continue
    if "run_id" not in d.columns:
        continue
    d = d.copy()
    d["report_file"] = f.name
    reps.append(d)
rep = pd.concat(reps, ignore_index=True)
rep = rep[rep["run_id"].notna()]

scan = pd.read_csv(ROOT / "research_reports/platform_alignment/a-basis-correction-20260926/platform_si_scan.csv",
                   encoding="utf-8-sig")
scan["run_id"] = scan["path"].str.replace("\\", "/", regex=False).str.split("/").str[-1].str.replace(".json", "", regex=False)
scan = scan.rename(columns={"rank_ic": "scan_rank_ic", "rank_ic_ir": "scan_ir", "win": "scan_win"})

j = rep.merge(scan[["run_id", "s_i", "scan_rank_ic", "scan_ir", "scan_win", "n_periods"]], on="run_id", how="inner")
j["status"] = j["status"].astype(str)
j = j[j["status"].isin(["completed", "1", "Completed"])]
j = j.dropna(subset=["s_i", "turnover_pct", "net_excess_pct", "long_sharpe", "long_max_drawdown_pct"])
j = j.sort_values("s_i", ascending=False).drop_duplicates(subset=["run_id"], keep="first")
mask_pool = j["name"].str.match(r"(?i)^(f-p\d|f-\ds-|f-1y-|f-3m-|pool)")
j = j[~mask_pool]
j = j.sort_values("s_i", ascending=False).drop_duplicates(subset=["name"], keep="first")

seats = j[["name", "s_i", "turnover_pct", "net_excess_pct", "long_sharpe",
           "long_max_drawdown_pct", "scan_rank_ic", "scan_ir", "scan_win", "n_periods", "run_id"]].copy()
seats = seats.rename(columns={"turnover_pct": "turn", "net_excess_pct": "net",
                              "long_sharpe": "sr", "long_max_drawdown_pct": "dd"})
seats["turn"] = seats["turn"] / 100.0
seats["net"] = seats["net"] / 100.0
seats["dd"] = seats["dd"] / 100.0
seats["is_incumbent"] = seats["name"].isin(INCUMBENT)
seats = seats.sort_values("s_i", ascending=False, ignore_index=True)
seats.to_csv(OUT / "seat_library.csv", index=False, encoding="utf-8-sig")
print("seat library:", len(seats), "rows with s_i + platform metrics")


def evaluate(df, syn_net=0.0, syn_sr=0.0):
    raw_a = float(df["s_i"].mean())
    na = min(raw_a / 0.08, 0.70)
    net = float(df["net"].mean()) + syn_net
    turn = float(df["turn"].mean())
    sr = float(df["sr"].mean()) + syn_sr
    dd5 = float(df["dd"].mean())
    dd_m = DD_MONTH_BASE * dd5 / DD5_BASE
    t_star = max(net, 0.0) * sr * (1 - 1.2 * dd_m) / 0.6
    nc_k = {k: min(1.0, t_star / max(k * turn, 0.30)) for k in KS}
    e_nc = sum(KS[k] * nc_k[k] for k in KS) / sum(KS.values())
    comb = 0.20 * na + 0.45 * e_nc
    return dict(raw_a=raw_a, na=na, net=net, turn=turn, sr=sr, dd5=dd5, dd_m=dd_m,
                t_star=t_star, nc1=nc_k[1], nc2=nc_k[2], nc3=nc_k[3], e_nc=e_nc,
                comb_no_b=comb, pts=comb * 40000 * 1.10, n=len(df))


inc = seats[seats["name"].isin(INCUMBENT)]
inc_model = evaluate(inc)
print("[校准] 现役 5 席，席位均值模型（无协同）:")
for k, v in inc_model.items():
    print(f"    {k} = {v:.4f}" if isinstance(v, float) else f"    {k} = {v}")
inc_pts_actual = (0.2 * 0.323662 + 0.45 * 1.0) * 44000
print(f"[校准] 平台实测: net=0.2030 turn=0.1339 sr=1.0648 T*=0.340 E[NC]=0.982(近期NC=1.0) pts={inc_pts_actual:.0f}")

SHORT = pd.concat([seats.head(22), inc]).drop_duplicates(subset=["name"])
print("shortlist:", len(SHORT), "席")
names = SHORT["name"].tolist()
by_name = {r["name"]: r for r in SHORT.to_dict("records")}


def make_rows(combo):
    df = pd.DataFrame([by_name[n] for n in combo])
    out = {"seats": " + ".join(sorted(combo))}
    for tag, kw in (("plain", {}), ("syn", dict(syn_net=0.0275, syn_sr=0.081))):
        e = evaluate(df, **kw)
        for kk in ("raw_a", "na", "net", "turn", "sr", "t_star", "e_nc", "comb_no_b", "pts"):
            out[f"{tag}_{kk}"] = e[kk]
    out["n_t10"] = sum(1 for n in combo if "T10" in n.upper())
    out["n_inc"] = sum(1 for n in combo if n in INCUMBENT)
    return out


rows5 = [make_rows(c) for c in itertools.combinations(names, 5)]
rows6 = [make_rows(c) for c in itertools.combinations(names, 6)]
df5 = pd.DataFrame(rows5).sort_values("plain_pts", ascending=False)
df6 = pd.DataFrame(rows6).sort_values("plain_pts", ascending=False)
df5.to_csv(OUT / "top_pools_5seat.csv", index=False, encoding="utf-8-sig")
df6.to_csv(OUT / "top_pools_6seat.csv", index=False, encoding="utf-8-sig")
print("enumerated", len(df5), "5-seat and", len(df6), "6-seat pools")

frontier = []
for cap in (0.12, 0.15, 0.18, 0.22, 0.30, 0.45):
    sub = df5[df5["plain_turn"] <= cap]
    if len(sub):
        r = sub.iloc[0]
        frontier.append(dict(turn_cap=cap, pts=r["plain_pts"], syn_pts=r["syn_pts"], raw_a=r["plain_raw_a"],
                             na=r["plain_na"], e_nc=r["plain_e_nc"], turn=r["plain_turn"],
                             net=r["plain_net"], seats=r["seats"]))
fr = pd.DataFrame(frontier)
fr.to_csv(OUT / "turnover_frontier_5seat.csv", index=False, encoding="utf-8-sig")

cand_rows = []
for r in seats.head(30).to_dict("records"):
    solo_t = max(r["net"], 0) * r["sr"] * (1 - 1.2 * DD_MONTH_BASE * r["dd"] / DD5_BASE) / 0.6
    e6 = evaluate(pd.DataFrame([by_name[n] for n in INCUMBENT] + [r]))
    e_sw = evaluate(pd.DataFrame([by_name[n] for n in INCUMBENT if n != "SIZE-ONLY-20260911"] + [r]))
    cand_rows.append(dict(name=r["name"], s_i=r["s_i"], turn=r["turn"], net=r["net"], sr=r["sr"],
                          dd=r["dd"], solo_t_star=solo_t, add6_pts=e6["pts"], add6_d=e6["pts"] - inc_model["pts"],
                          swapSIZE_pts=e_sw["pts"], swapSIZE_d=e_sw["pts"] - inc_model["pts"]))
cd = pd.DataFrame(cand_rows)
cd.to_csv(OUT / "candidate_composite.csv", index=False, encoding="utf-8-sig")

pd.set_option("display.width", 260)
show5 = ["seats", "plain_pts", "syn_pts", "plain_raw_a", "plain_na", "plain_net", "plain_turn", "plain_t_star", "plain_e_nc", "n_t10", "n_inc"]
print()
print("== 5 席组合 TOP12（plain = 无协同保守口径；syn = 沿用现役池协同 +2.75pp/+0.081） ==")
with pd.option_context("display.max_colwidth", 120):
    print(df5[show5].head(12).to_string(index=False))
print()
print("== 6 席组合 TOP8 ==")
with pd.option_context("display.max_colwidth", 120):
    print(df6[show5].head(8).to_string(index=False))
print()
print("== 换手前沿（5 席） ==")
with pd.option_context("display.max_colwidth", 110):
    print(fr.to_string(index=False))
print()
print("== 逐候选综合边际（TOP20 by s_i；模型现役基线 %.0f 分/月） ==" % inc_model["pts"])
with pd.option_context("display.max_colwidth", 60):
    print(cd.head(20).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print()
print("written:", OUT)
