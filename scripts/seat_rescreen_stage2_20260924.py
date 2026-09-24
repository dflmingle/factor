"""第 6 席重筛 · 第二阶段：NC 锚定校准 + 分档 + size 防护 + 排序。

第一阶段（pool_seat_rescreen_20260924.py）给出每席的真实组合结果
（加席后的 net / SR / DD / 换手）。本阶段把 C 分项按三套校准重算，
因为官方 `MaxDD_month` 是**当月**回撤，而本地管线只能给出全期回撤，
两者不可混用；三套校准构成 ΔNC 的上下界。

K1 本地自洽（全期 DD 27.41%）      E5 = net5*sr5*(1-1.2*dd5)                 -> T*5 = 0.301
K2 锚定平台回测(20.3%/1.0648)+月度DD 4.5%   E5 = 0.203*1.0648*0.946          -> T*5 = 0.341
K3 本地管线 + 月度 DD 4.5%          E5 = net5*sr5*0.946                       -> T*5 = 0.425
输出: research_reports/platform_alignment/seat-rescreen-20260924/{stage2.csv,stage2.json}
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/seat-rescreen-20260924"
P1, P2, P3 = 1 - 0.7667 - 0.1167, 0.7667, 0.1167
POINTS = 40000.0 * 1.10
DD_MONTH = 0.045          # 榜单 283 池的 MaxDD_month 中位 4.15%，取 4.5%
PLAT_NET, PLAT_SR = 0.2030, 1.0648
GATE_SI, GATE_NET, GATE_TURN = 0.035, 0.15, 0.30
SIZE_GUARD = 0.50


def main() -> int:
    base = json.loads((OUT / "baseline.json").read_text())
    b = base["base"]
    d = pd.read_csv(OUT / "seat_rescreen.csv")
    E5 = {
        "K1": b["net"] * b["sr"] * (1 - 1.2 * b["dd"]),
        "K2": PLAT_NET * PLAT_SR * (1 - 1.2 * DD_MONTH),
        "K3": b["net"] * b["sr"] * (1 - 1.2 * DD_MONTH),
    }
    T5 = {k: 2 * b["turn"] for k in E5}
    T5_3 = 3 * b["turn"]

    rows = []
    for _, r in d.iterrows():
        if r["in_pool"]:
            continue
        row = dict(key=r["key"], name=r["name"], s_i=r["local_s_i"], seat_turn=r["local_turnover"],
                   corr_size=r["corr_size"], corr_pool=r["corr_pool"],
                   seat_net=r["local_net"], size_neutral_net=r["net_size_neutral"],
                   pool_turn=r["add6_turn"], T2=r["T2"], T3=r["T3"],
                   dNA=r["dNA"], dNB_steady=r["dNB_steady"], dNB_first=r["dNB_first"])
        for tag, basis in (("K1", "local"), ("K2", "ratio"), ("K3", "monthly")):
            if basis == "local":
                E6 = r["add6_net"] * r["add6_sr"] * (1 - 1.2 * min(max(r["add6_dd"], 0), 0.83))
            elif basis == "ratio":
                E6 = E5["K2"] * (r["add6_net"] / b["net"]) * (r["add6_sr"] / b["sr"])
            else:
                E6 = r["add6_net"] * r["add6_sr"] * (1 - 1.2 * DD_MONTH)
            def nc(E, T):
                return float(min(1.0, max(E / (0.6 * max(T, 0.30)), 0.0)))
            nc5_2, nc6_2 = nc(E5[tag], T5[tag]), nc(E6, r["T2"])
            nc5_3, nc6_3 = nc(E5[tag], T5_3), nc(E6, r["T3"])
            nc5_1, nc6_1 = nc(E5[tag], 1 * b["turn"]), nc(E6, 1 * r["add6_turn"])
            d_exp = P1 * (nc6_1 - nc5_1) + P2 * (nc6_2 - nc5_2) + P3 * (nc6_3 - nc5_3)
            row[f"Tstar_{tag}"] = float(E5[tag] / 0.6)
            row[f"NC6_2_{tag}"] = nc6_2
            row[f"NC6_3_{tag}"] = nc6_3
            row[f"dNC2_{tag}"] = nc6_2 - nc5_2
            row[f"dNC3_{tag}"] = nc6_3 - nc5_3
            row[f"dNC_exp_{tag}"] = d_exp
            row[f"dComb_{tag}"] = 0.20 * r["dNA"] + 0.35 * r["dNB_steady"] + 0.45 * d_exp
            row[f"dpoints_{tag}"] = POINTS * row[f"dComb_{tag}"]
        row["dpoints_mean"] = float(np.mean([row[f"dpoints_{t}"] for t in ("K1", "K2", "K3")]))
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("dpoints_mean", ascending=False)
    out["turn_bucket"] = pd.cut(out["seat_turn"], [0, 0.30, 0.40, 10],
                                labels=["<=30%", "30-40%", ">40%"])
    out["size_pass"] = out["corr_size"].abs() <= SIZE_GUARD
    out["gate_pass"] = (out["s_i"] >= GATE_SI) & (out["seat_net"] >= GATE_NET) & out["size_pass"]
    out.to_csv(OUT / "stage2.csv", index=False)
    (OUT / "stage2.json").write_text(json.dumps(
        {"E5": E5, "Tstar5": {k: v / 0.6 for k, v in E5.items()}, "T5_2": T5,
         "DD_month_assumed": DD_MONTH, "platform_anchor": {"net": PLAT_NET, "sr": PLAT_SR},
         "size_guard": SIZE_GUARD, "gate": {"s_i": GATE_SI, "net": GATE_NET, "turn": GATE_TURN}},
        indent=2, ensure_ascii=False))

    pd.set_option("display.width", 300)
    cols = ["name", "s_i", "seat_turn", "T2", "corr_size", "corr_pool", "dNA", "dNB_steady",
            "dNC_exp_K1", "dNC_exp_K2", "dNC_exp_K3", "dpoints_K1", "dpoints_K2", "dpoints_K3",
            "dpoints_mean", "gate_pass"]
    print("T*5 (K1/K2/K3) =", {k: round(v, 4) for k, v in (E5.items())}, flush=True)
    print("T*5 =", {k: round(v / 0.6, 4) for k, v in E5.items()}, flush=True)
    print("\n=== 全部 51 个候选（按三套校准平均 Δpoints 排序）===", flush=True)
    print(out[cols].round(4).to_string(index=False), flush=True)

    print("\n=== 换手分档统计 ===", flush=True)
    print(out.groupby("turn_bucket", observed=True).agg(
        n=("key", "size"), best=("dpoints_mean", "max"), median=("dpoints_mean", "median"),
        n_positive=("dpoints_mean", lambda x: int((x > 0).sum()))).round(1).to_string(), flush=True)
    print("\n=== size 达标 (|corr_size|<=0.5) 的候选 ===", flush=True)
    sel = out[out.size_pass]
    print(sel[cols].round(4).to_string(index=False), flush=True)
    print("\n=== 新门槛 (S_i>=0.035 & net>=15% & |corr_size|<=0.5) 通过者 ===", flush=True)
    print(out[out.gate_pass][cols].round(4).to_string(index=False), flush=True)
    print(f"count = {int(out.gate_pass.sum())}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
