"""第 6 席重筛报告生成：Top 候选表 / F-NET01 桥 / 边际贡献对比 / DD 盈亏平衡（零平台算力）。

输入：seat-rescreen-20260924/{baseline.json,seat_rescreen.csv,stage2.csv,
                          nb-dilution-20260924/nb_timing.json(可选)}
输出：seat-rescreen-20260924/report_tables.json + report_tables.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/seat-rescreen-20260924"
NBJSON = ROOT / "research_reports/platform_alignment/nb-dilution-20260924/nb_timing.json"
P1, P2, P3 = 1 - 0.7667 - 0.1167, 0.7667, 0.1167
POINTS = 44000.0
NC_FLOOR, CAP_C = 0.30, 0.60
DD_MONTH = 0.045
PLAT_NET, PLAT_SR = 0.2030, 1.0648


def nc(E: float, T: float) -> float:
    return float(min(1.0, max(E / (CAP_C * max(T, NC_FLOOR)), 0.0)))


def shapley(E5: float, E6: float, t5: float, t6: float, k: int) -> tuple[float, float]:
    """(换手部分, 表现部分) —— 两步 Shapley 中值分解。"""
    def f(Ev, tv):
        return nc(Ev, k * tv)
    turn = 0.5 * ((f(E5, t6) - f(E5, t5)) + (f(E6, t6) - f(E6, t5)))
    perf = (f(E6, t6) - f(E5, t5)) - turn
    return turn, perf


def main() -> int:
    base = json.loads((OUT / "baseline.json").read_text())
    b, base_na = base["base"], base["base_na"]
    d1 = pd.read_csv(OUT / "seat_rescreen.csv")
    d2 = pd.read_csv(OUT / "stage2.csv")
    d = d1.merge(d2[["key", "dpoints_mean", "Tstar_K1", "Tstar_K2", "Tstar_K3",
                 "dNC_exp_K1", "dNC_exp_K2", "dNC_exp_K3"]], on="key", how="left")
    d = d[~d.in_pool].copy()

    si5 = np.array([0.010244872746, 0.01578596817, 0.03725596, 0.01692, 0.01540])
    nb5 = min(si5.mean() / 0.06, 1.0)
    E5 = {"K1": b["net"] * b["sr"] * (1 - 1.2 * b["dd"]),
          "K2": PLAT_NET * PLAT_SR * (1 - 1.2 * DD_MONTH),
          "K3": b["net"] * b["sr"] * (1 - 1.2 * DD_MONTH)}

    rows = []
    for _, r in d.iterrows():
        row = {"key": r["key"], "name": r["name"], "s_i": r["local_s_i"],
               "seat_turn": r["local_turnover"], "seat_net": r["local_net"],
               "corr_size": r["corr_size"], "corr_pool": r["corr_pool"],
               "net_size_neutral": r["net_size_neutral"],
               "T1": r["add6_turn"], "T2": r["T2"], "T3": r["T3"],
               "NC2": r["NC2"], "NC3": r["NC3"], "NA6": r["NA6"],
               "add6_net": r["add6_net"], "add6_sr": r["add6_sr"], "add6_dd": r["add6_dd"],
               "dNA": r["dNA"], "dNB_steady": r["dNB_steady"], "dNB_first": r["dNB_first"]}
        row["dNB_first_extra"] = r["dNB_first"] - r["dNB_steady"]
        for tag in ("K1", "K2", "K3"):
            if tag == "K1":
                e6 = r["add6_net"] * r["add6_sr"] * (1 - 1.2 * min(max(r["add6_dd"], 0), 0.83))
            elif tag == "K2":
                e6 = E5["K2"] * (r["add6_net"] / b["net"]) * (r["add6_sr"] / b["sr"])
            else:
                e6 = r["add6_net"] * r["add6_sr"] * (1 - 1.2 * DD_MONTH)
            dnc, dturn, dperf = 0.0, 0.0, 0.0
            for k, pk in ((1, P1), (2, P2), (3, P3)):
                t5, t6 = b["turn"], r["add6_turn"]
                tu, pe = shapley(E5[tag], e6, t5, t6, k)
                dnc += pk * (tu + pe); dturn += pk * tu; dperf += pk * pe
            dcomb = 0.20 * r["dNA"] + 0.35 * r["dNB_steady"] + 0.45 * dnc
            row[f"dNC_turn_{tag}"] = dturn
            row[f"dNC_perf_{tag}"] = dperf
            row[f"dNC_{tag}"] = dnc
            row[f"dComb_{tag}"] = dcomb
            row[f"dpoints_{tag}"] = POINTS * dcomb
        row["dpoints_mean"] = np.mean([row[f"dpoints_{t}"] for t in ("K1", "K2", "K3")])
        row["pts_NA"] = POINTS * 0.20 * row["dNA"]
        row["pts_NB"] = POINTS * 0.35 * row["dNB_steady"]
        row["pts_NB_first_extra"] = POINTS * 0.35 * row["dNB_first_extra"]
        for tag in ("K1", "K2", "K3"):
            row[f"pts_NC_turn_{tag}"] = POINTS * 0.45 * row[f"dNC_turn_{tag}"]
            row[f"pts_NC_perf_{tag}"] = POINTS * 0.45 * row[f"dNC_perf_{tag}"]
        row["dpoints_turn_cost"] = np.mean([row[f"pts_NC_turn_{t}"] for t in ("K1", "K2", "K3")])
        row["dpoints_turn_cost_K2"] = row["pts_NC_turn_K2"]
        row["dpoints_nb_first"] = row["pts_NB_first_extra"]
        row["sign_positive_all"] = all(row[f"dpoints_{t}"] > 0 for t in ("K1", "K2", "K3"))
        row["n_positive"] = int(sum(row[f"dpoints_{t}"] > 0 for t in ("K1", "K2", "K3")))
        # DD 盈亏平衡：local 比率口径（net/sr 比率来自本地，DD 为自由参数）
        def dcomb_at(dd: float, anchor: bool) -> float:
            if anchor:
                e5 = PLAT_NET * PLAT_SR * (1 - 1.2 * dd)
                e6 = e5 * (r["add6_net"] / b["net"]) * (r["add6_sr"] / b["sr"])
            else:
                e5 = b["net"] * b["sr"] * (1 - 1.2 * dd)
                e6 = r["add6_net"] * r["add6_sr"] * (1 - 1.2 * dd)
            acc = 0.0
            for k, pk in ((1, P1), (2, P2), (3, P3)):
                acc += pk * (nc(e6, k * r["add6_turn"]) - nc(e5, k * b["turn"]))
            return 0.20 * r["dNA"] + 0.35 * r["dNB_steady"] + 0.45 * acc
        for lbl, anchor in (("local", False), ("platform", True)):
            grid = np.linspace(0.0, 0.08, 321)
            vals = np.array([dcomb_at(x, anchor) for x in grid])
            pos = np.where(vals > 0)[0]
            if len(pos) == 0:
                lo = up = float("nan")
            elif len(pos) == len(grid):
                lo, up = float("nan"), float("inf")          # 全区间为正
            elif pos[0] > 0:                                  # 低 DD 不足、高 DD 转正
                lo, up = float(grid[pos[0]]), float("nan")
            else:                                             # 低 DD 为正、高 DD 转负
                lo, up = float("nan"), float(grid[pos[-1]])
            row[f"dd_lo_{lbl}"], row[f"dd_hi_{lbl}"] = lo, up
            row[f"dd_positive_all_{lbl}"] = bool(len(pos) == len(grid))
            # 与 stage2 的 P 加权 dNC 对账
        for tag in ("K1", "K2", "K3"):
            ref = r.get(f"dNC_exp_{tag}")
            if isinstance(ref, float) or isinstance(ref, np.floating):
                row[f"dNC_check_{tag}"] = abs(ref - row[f"dNC_{tag}"])
        rows.append(row)

    out = pd.DataFrame(rows)
    out["turn_bucket"] = pd.cut(out["seat_turn"], [0, 0.30, 0.40, 10], labels=["<=30%", "30-40%", ">40%"])
    out["size_pass"] = out["corr_size"].abs() <= 0.50
    out = out.sort_values("dComb_K2", ascending=False)
    out.to_csv(OUT / "report_table_full.csv", index=False)

    chk = {t: float(pd.to_numeric(out[f"dNC_check_{t}"], errors="coerce").max()) for t in ("K1", "K2", "K3")}
    print("dNC 对账（与 stage2 的 P 加权 dNC_exp 最大绝对差）:", chk, flush=True)

    bridge_rows = []
    for tag in ("qfq", "raw"):
        key = f"fnet01_{tag}"
        r = out[out.key == key].iloc[0]
        b5_nb = min(si5.mean() / 0.06, 1.0)
        base_nc = {t: {"NC2": nc(E5[t], 2 * b["turn"]), "NC3": nc(E5[t], 3 * b["turn"]),
                       "NC1": nc(E5[t], 1 * b["turn"])} for t in ("K1", "K2", "K3")}
        bridge_rows.append(dict(
            key=key, name=r["name"], seat_turn=r["seat_turn"], T2=r["T2"], T3=r["T3"],
            base_NA=base_na, new_NA=r["NA6"], dNA=r["dNA"], base_NC=base_nc,
            base_NB=b5_nb, new_NB=b5_nb + r["dNB_steady"], dNB=r["dNB_steady"],
            nb_first_extra=r["dNB_first_extra"],
            base_net=b["net"], new_net=r["add6_net"], base_sr=b["sr"], new_sr=r["add6_sr"],
            base_dd=b["dd"], new_dd=r["add6_dd"], base_turn=b["turn"], new_turn=r["T1"],
            new_NC={"NC1": r["NC2"], "NC2": r["NC2"], "NC3": r["NC3"]},
            dNC_turn={"K1": r["dNC_turn_K1"], "K2": r["dNC_turn_K2"], "K3": r["dNC_turn_K3"]},
            dNC_perf={"K1": r["dNC_perf_K1"], "K2": r["dNC_perf_K2"], "K3": r["dNC_perf_K3"]},
            dpoints={"K1": r["dpoints_K1"], "K2": r["dpoints_K2"], "K3": r["dpoints_K3"]},
            dpoints_mean=r["dpoints_mean"], dpoints_nb_first=r["dpoints_nb_first"],
            dpoints_turn_cost=r["dpoints_turn_cost"]))

    # ---- K5：逐月实测（本地日频账本的月度 Rex/SR/DD + 当月真实调仓次数 × 实测换手） ----
    DDJSON = ROOT / "research_reports/platform_alignment/daily-dd-20260924/daily_dd.json"
    PLAT_REX_SCALE = 0.853   # 本地净超额对平台的系统性高估（20.3/23.8）
    PLAT_SR_SCALE = 1.0648 / 1.1317246776061485
    k5 = {}
    if DDJSON.exists():
        dd = json.loads(DDJSON.read_text())["portfolios"]
        base_m = dd["base_5seat"]["monthly_c_inputs"]
        for r in rows:
            key = r["key"]
            name = f"add6_{key}"
            if name not in dd:
                continue
            vm = dd[name]["monthly_c_inputs"]
            common = sorted(set(base_m) & set(vm))
            acc = {"local": [], "plat": []}
            acc_turn = {"local": [], "plat": []}
            for m in common:
                bm, cm = base_m[m], vm[m]
                k_n = bm["n_reb"]
                for tag in ("local", "plat"):
                    scale = 1.0 if tag == "local" else PLAT_REX_SCALE
                    sr_scale = 1.0 if tag == "local" else PLAT_SR_SCALE
                    e5 = scale * bm["rex_ann"] * sr_scale * bm["sr_ann"] * (1 - 1.2 * bm["maxdd"])
                    e6 = scale * cm["rex_ann"] * sr_scale * cm["sr_ann"] * (1 - 1.2 * cm["maxdd"])
                    t5, t6 = k_n * b["turn"], k_n * r["T1"]
                    tu, pe = shapley(e5, e6, t5 / k_n if k_n else 0, t6 / k_n if k_n else 0, k_n or 1)
                    dnc_m = tu + pe
                    dcomb_m = 0.20 * r["dNA"] + 0.35 * r["dNB_steady"] + 0.45 * dnc_m
                    acc[tag].append(POINTS * dcomb_m)
                    acc_turn[tag].append(POINTS * 0.45 * tu)
            if not acc["local"]:
                continue
            k5[key] = {"name": r["name"], "months": len(acc["local"])}
            for tag in ("local", "plat"):
                x = np.array(acc[tag]); xt = np.array(acc_turn[tag])
                k5[key][tag] = {"mean_dpoints": float(x.mean()), "median": float(np.median(x)),
                                "p10": float(np.percentile(x, 10)), "p90": float(np.percentile(x, 90)),
                                "share_negative": float((x < 0).mean()),
                                "mean_dpoints_turn_part": float(xt.mean())}
            k5[key]["dpoints_mean"] = r["dpoints_mean"]
            k5[key]["dd"] = {"base_median": float(np.median([base_m[m]["maxdd"] for m in common]))}
        out["k5_mean_dpoints"] = out.key.map({k: v["plat"]["mean_dpoints"] for k, v in k5.items()})
        out["k5_median_dpoints"] = out.key.map({k: v["plat"]["median"] for k, v in k5.items()})
        out["k5_share_negative"] = out.key.map({k: v["plat"]["share_negative"] for k, v in k5.items()})
        out["k5_turn_part_plat"] = out.key.map({k: v["plat"]["mean_dpoints_turn_part"] for k, v in k5.items()})

    nb = json.loads(NBJSON.read_text()) if NBJSON.exists() else None
    summary = {
        "baseline": {"net": b["net"], "sr": b["sr"], "dd_full": b["dd"], "turn_per_reb": b["turn"],
                     "NA": base_na, "NB_proxy": nb5, "Comb2": base["base_comb2"],
                     "Tstar_K1": E5["K1"] / 0.6, "Tstar_K2": E5["K2"] / 0.6, "Tstar_K3": E5["K3"] / 0.6},
        "top_by_dComb_K2": out.head(12)[
            ["name", "s_i", "seat_turn", "T2", "T3", "corr_size", "net_size_neutral", "dNA",
             "dNB_steady", "dNB_first_extra", "dNC_K1", "dNC_K2", "dNC_K3",
             "dNC_turn_K2", "dNC_perf_K2", "dComb_K1", "dComb_K2", "dComb_K3",
             "dpoints_K1", "dpoints_K2", "dpoints_K3", "dpoints_mean", "turn_bucket",
             "size_pass", "n_positive"]].round(4).to_dict("records"),
        "by_bucket": out.groupby("turn_bucket", observed=True).apply(
            lambda g: {"n": len(g), "best_dpoints_K2": float(g.dpoints_K2.max()),
                       "median_dpoints_K2": float(g.dpoints_K2.median()),
                       "n_positive_K2": int((g.dpoints_K2 > 0).sum()),
                       "best_name": g.loc[g.dpoints_K2.idxmax(), "name"] if len(g) else None},
            include_groups=False).to_dict(),
        "size_guard": {
            "n_total": len(out), "n_abs_corr_le_0_5": int(out.size_pass.sum()),
            "n_pass_all_gates": int(((out.s_i >= 0.035) & (out.seat_net >= 0.15) & out.size_pass).sum()),
            "best_t10_family": out[out.name.str.contains("T10-ADD|T10-SIZE-PLUS", na=False)][
                ["name", "s_i", "seat_turn", "corr_size", "net_size_neutral", "dpoints_K1",
                 "dpoints_K2", "dpoints_K3", "dd_hi_platform", "dd_lo_platform"]].round(4).to_dict("records"),
        },
        "fnet01_bridge": bridge_rows,
        "k5_per_month": k5,
        "nb_dilution": None if nb is None else {
            k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)}
            for k, v in nb["scenarios"].items()},
        "nb_empirical_mean_si_b": None if nb is None else {
            k: float(np.mean(v["monthly_NB_no_add"])) for k, v in nb["scenarios"].items()},
    }
    (OUT / "report_tables.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))

    md = []
    md.append("### 表 1 · 第 6 席候选按 ΔComb(K2) 排序（分/月，加席后池级真实边际）\n")
    t1 = out.head(16)[["name", "s_i", "seat_turn", "T2", "T3", "corr_size", "net_size_neutral",
                       "dNA", "dNB_steady", "dNB_first_extra", "pts_NA", "pts_NB",
                       "pts_NC_turn_K2", "pts_NC_perf_K2", "pts_NB_first_extra",
                       "dpoints_K1", "dpoints_K2", "dpoints_K3", "dpoints_mean",
                       "n_positive", "size_pass"]].round(4)
    md.append(t1.to_markdown(index=False))
    md.append("\n### 表 2 · 换手分档\n")
    md.append(pd.DataFrame(summary["by_bucket"]).T.to_markdown())
    md.append("\n### 表 3 · DD 盈亏平衡（ΔComb 转正所需的平台月度 MaxDD 上限）\n")
    md.append(out.nlargest(10, "dComb_K2")[
        ["name", "seat_turn", "corr_size", "dpoints_K1", "dpoints_K2", "dpoints_K3",
         "dd_lo_local", "dd_hi_local", "dd_lo_platform", "dd_hi_platform"]].round(4)
        .to_markdown(index=False))
    md.append("\n### 表 4 · size 达标（|corr_size| ≤ 0.5）候选\n")
    md.append(out[out.size_pass].nlargest(12, "dComb_K2")[
        ["name", "s_i", "seat_turn", "corr_size", "net_size_neutral", "dpoints_K1",
         "dpoints_K2", "dpoints_K3"]].round(4).to_markdown(index=False))
    md.append("\n### 表 5 · F-NET01 加席评分桥\n")
    br = []
    for r in summary["fnet01_bridge"]:
        br.append({"候选": r["name"], "席位换手": round(r["seat_turn"], 4),
                   "池 T2": round(r["T2"], 4), "池 T3": round(r["T3"], 4),
                   "ΔNA": round(r["dNA"], 4), "ΔNB(稳态)": round(r["dNB"], 4),
                   "ΔNB(首期额外)": round(r["nb_first_extra"], 4),
                   "ΔNC 换手(K2)": round(r["dNC_turn"]["K2"], 5),
                   "ΔNC 表现(K2)": round(r["dNC_perf"]["K2"], 5),
                   "ΔComb(K1)": round(r["dpoints"]["K1"] / POINTS, 4),
                   "分/月 K1": round(r["dpoints"]["K1"]), "分/月 K2": round(r["dpoints"]["K2"]),
                   "分/月 K3": round(r["dpoints"]["K3"]),
                   "首期 NB 稀释(一次性,分)": round(r["dpoints_nb_first"])})
    md.append(pd.DataFrame(br).to_markdown(index=False))
    (OUT / "report_tables.md").write_text("\n".join(md) + "\n")

    pd.set_option("display.width", 400)
    cols = ["name", "s_i", "seat_turn", "T2", "corr_size", "dNA", "dNB_steady", "dNB_first_extra",
            "dNC_turn_K2", "dNC_perf_K2", "dNC_K1", "dNC_K2", "dNC_K3",
            "dpoints_K1", "dpoints_K2", "dpoints_K3", "dpoints_mean", "n_positive", "size_pass"]
    print("base:", {k: round(v, 4) for k, v in summary["baseline"].items()})
    print("\n== F-NET01 桥 ==")
    print(json.dumps(summary["fnet01_bridge"], indent=1, ensure_ascii=False, default=str))
    print("\n== Top 20 by dComb_K2 ==")
    print(out[cols].head(20).round(4).to_string(index=False))
    print("\n== T* and bucket ==")
    print(json.dumps(summary["by_bucket"], indent=1, ensure_ascii=False, default=str))
    print("\n== K5 逐月实测（平台口径校正后）==")
    kk = sorted(k5.items(), key=lambda kv: -kv[1]["plat"]["mean_dpoints"])[:10]
    for key, v in kk:
        print(f'{v["name"]:36s} 月数 {v["months"]:3d}  月均 {v["plat"]["mean_dpoints"]:+8.0f}  '
              f'中位 {v["plat"]["median"]:+8.0f}  p10 {v["plat"]["p10"]:+8.0f}  p90 {v["plat"]["p90"]:+8.0f}  '
              f'负月占比 {v["plat"]["share_negative"]:.2f}  换手部分 {v["plat"]["mean_dpoints_turn_part"]:+8.0f}  '
              f'| local月均 {v["local"]["mean_dpoints"]:+8.0f}')

    print("\n== size guard ==")
    print(json.dumps(summary["size_guard"], indent=1, ensure_ascii=False, default=str))
    if nb is not None:
        print("\n== NB dilution ==")
        print(json.dumps(summary["nb_dilution"], indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
