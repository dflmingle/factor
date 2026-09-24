"""生成第 6 席重筛报告 summary.md 的表 1~表 7（数字全部来自落盘产物）。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/seat-rescreen-20260924"
DD = ROOT / "research_reports/platform_alignment/daily-dd-20260924/daily_dd.json"
NB = ROOT / "research_reports/platform_alignment/nb-dilution-20260924/nb_timing.json"

f = pd.read_csv(OUT / "report_table_full.csv")
r = json.loads((OUT / "report_tables.json").read_text())
k5 = {k: v for k, v in r["k5_per_month"].items()}
d = f.copy()
d["K5"] = d.key.map({k: v["plat"]["mean_dpoints"] for k, v in k5.items()})
d["K5中位"] = d.key.map({k: v["plat"]["median"] for k, v in k5.items()})
d["K5p10"] = d.key.map({k: v["plat"]["p10"] for k, v in k5.items()})
d["负月占比"] = d.key.map({k: v["plat"]["share_negative"] for k, v in k5.items()})
d["K5换手部"] = d.key.map({k: v["plat"]["mean_dpoints_turn_part"] for k, v in k5.items()})
d = d.sort_values("K5", ascending=False)

T = {}

t1a = d.head(12)[["name", "s_i", "seat_turn", "T1", "T2", "T3", "corr_size", "net_size_neutral"]].copy()
t1a.columns = ["候选", "S_i", "席位换手/次", "加席后池换手/次", "T(2调仓月)", "T(3调仓月)", "corr_size", "size 中性化净额"]
T["t1a"] = t1a.round(4).to_markdown(index=False)

t1b = d.head(12)[["name", "dNA", "pts_NA", "dNB_steady", "pts_NB", "pts_NB_first_extra",
                  "dNC_turn_K2", "pts_NC_turn_K2", "dNC_perf_K2", "pts_NC_perf_K2",
                  "dpoints_K1", "dpoints_K2", "dpoints_K3", "K5", "K5中位", "K5p10", "负月占比"]].copy()
t1b.columns = ["候选", "ΔNA", "分/月(NA)", "ΔNB 稳态", "分/月(NB)", "首期 NB 稀释(一次性)",
               "ΔNC 换手(K2)", "分/月(换手)", "ΔNC 表现(K2)", "分/月(表现)",
               "K1 分/月", "K2 分/月", "K3 分/月", "K5 月均", "K5 中位", "K5 p10", "K5 负月占比"]
T["t1b"] = t1b.round(3).to_markdown(index=False)

b = d.assign(bucket=pd.cut(d.seat_turn, [0, 0.30, 0.40, 10], labels=["≤30%", "30–40%", ">40%"]))
g = b.groupby("bucket", observed=True).agg(
    n=("key", "size"), K5月均最大=("K5", "max"), K5月均中位=("K5", "median"),
    月均为正条数=("K5", lambda x: int((x > 0).sum())),
    size达标条数=("corr_size", lambda x: int((x.abs() <= 0.5).sum())))
g["本档最优"] = [b[b.bucket == i].nlargest(1, "K5")["name"].iloc[0] if len(b[b.bucket == i]) else "" for i in g.index]
T["t2"] = g.round(1).to_markdown()

dd = d.nlargest(8, "K5")[["name", "seat_turn", "corr_size", "dpoints_K1", "dpoints_K2", "dpoints_K3",
                          "K5", "dd_hi_platform", "dd_lo_platform", "dd_positive_all_local"]].copy()
dd.columns = ["候选", "席位换手/次", "corr_size", "K1 分/月", "K2 分/月", "K3 分/月", "K5 月均",
              "平台口径 DD 上限", "平台口径 DD 下限", "本地口径全区间为正"]
T["t3"] = dd.round(4).to_markdown(index=False)

pool = json.loads((OUT / "pool_size_guard.json").read_text())
base_pool = [x for x in pool if x["label"] == "base_5seat"][0]
t5 = pd.DataFrame(pool)
t5["Δcorr_size"] = t5.corr_size - base_pool["corr_size"]
t5["Δsize 中性化净额"] = t5.size_neutral_net - base_pool["size_neutral_net"]
T["t5"] = t5[["label", "corr_size", "Δcorr_size", "size_neutral_net", "Δsize 中性化净额"]].round(4).to_markdown(index=False)

nb = json.loads(NB.read_text())["scenarios"]
key = "fnet01_qfq|M_all"
s = nb[key]
traj = pd.DataFrame({"月份": [f"M{i+1:02d}" for i in range(12)],
                     "无加席": s["monthly_NB_no_add"], "选项 A(10-01~03)": s["monthly_NB_A"],
                     "选项 B(晚一期)": s["monthly_NB_B"], "A−B(分/月)": s["monthly_dNB_A_minus_B"]}).round(3)
T["t6"] = traj.to_markdown(index=False)
T["t6_summary"] = json.dumps({k: {kk: round(vv, 1) if isinstance(vv, (int, float)) else vv
                                  for kk, vv in v.items() if not isinstance(vv, list)}
                              for k, v in nb.items()}, indent=2, ensure_ascii=False)

# 表 7：S_i^B 盈亏平衡
rows = []
for _, x in d.iterrows():
    if x.key not in k5:
        continue
    dnc_pts = 44000 * 0.45 * (k5[x.key]["plat"]["mean_dpoints"] / 44000 - 0.20 * x["dNA"] - 0.35 * x["dNB_steady"])
    need_nb = -(0.20 * x["dNA"] + dnc_pts / 44000) / 0.35
    si5 = np.array([0.010244872746, 0.01578596817, 0.03725596, 0.01692, 0.01540])
    s6 = 6 * (min(si5.mean() / 0.06, 1.0) + need_nb) * 0.06 - si5.sum()
    rows.append({"候选": x["name"], "S_i(历史代理)": x["s_i"], "盈亏平衡所需 S_i^B": s6,
                 "安全垫": x["s_i"] - s6, "corr_size": x["corr_size"], "K5 月均": x["K5"]})
T["t7"] = pd.DataFrame(rows).nlargest(8, "K5 月均").round(4).to_markdown(index=False)

ddf = json.loads(DD.read_text())["portfolios"]["base_5seat"]
T["dd_base"] = json.dumps({k: round(v, 4) for k, v in ddf.items()
                           if isinstance(v, (int, float))}, indent=2, ensure_ascii=False)

(OUT / "report_tables_md.json").write_text(json.dumps(T, indent=1, ensure_ascii=False))
for k, v in T.items():
    print(f"===== {k} =====")
    print(v)
