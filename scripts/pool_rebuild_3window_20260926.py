"""重建池三窗口综合评分（2026-09-26 夜，零平台算力）。

口径（与 platform-three-window-20260923 一致）：
- 窗口：5 年 = 全部（20210907..20260907，120 期）；1 年 = date >= 2025-09-07（25 期）；3 个月 = date >= 2026-06-07（6-7 期）。
- 席位窗口指标全部从本仓 run JSON 的 query_factor_excess_chart / query_return_chart 重算：
    毛超额_年化 = (窗口末 cum_excess - 窗口前 cum_excess) × 25.2 / 窗口期数
    净超额 = 毛超额 - 换手×0.1512（换手取平台 5 年 run 值，作三窗口公共代理）
    SR 代理 = mean/std(ddof=1) of 组合收益增量 × sqrt(25.2)，再按席位 5 年平台 SR 做比例校准
    DD = 窗口内组合净值曲线（1+组收益 cum）的 MaxDD（5 年口径已验证 = 平台 long_max_drawdown_pct）
    s_i = |RankIC 均值| × IR(ddof=1) × 胜率(>0.02 同号计数)，窗口切片
- 池指标 = 席位的窗口指标均值；每窗口 NC = min(1, net/max(turn,0.30)×SR×(1-1.2×DD)/0.6)（三窗口报告同款，DD 用窗口实测当"月回撤"，保守）。
- 综合分数 = 0.20×NA(5 年) + 0.45×NC(三窗口均值)；另给 NA 三窗口均值变体。
"""
from __future__ import annotations
import glob, io, itertools, json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(r"D:\factor")
OUT = ROOT / "research_reports/platform_alignment/rebuild-3window-20260926"
OUT.mkdir(parents=True, exist_ok=True)

INCUMBENT = ["SIZE-ONLY-20260911", "H03-T10-SINGLE", "VERIFY10-E260910-04",
             "VERIFY10-F260910-12", "T10-ADD-BM-20260911"]
WINS = {"5y": "2021-01-01", "1y": "2025-09-07", "3m": "2026-06-07"}
PPY = 25.2

# ---- reports ----
reps = []
for f in sorted(ROOT.glob("*.report.csv")):
    try:
        d = pd.read_csv(f, encoding="utf-8-sig")
    except Exception:
        continue
    if "run_id" not in d.columns:
        continue
    d = d.copy(); d["report_file"] = f.name
    reps.append(d)
rep = pd.concat(reps, ignore_index=True)
rep = rep[rep["run_id"].notna()]
rep["status"] = rep["status"].astype(str)
rep = rep[rep["status"].isin(["completed", "1", "Completed"])]

scan = pd.read_csv(ROOT / "research_reports/platform_alignment/a-basis-correction-20260926/platform_si_scan.csv", encoding="utf-8-sig")
scan["run_id"] = scan["path"].str.replace("\\", "/", regex=False).str.split("/").str[-1].str.replace(".json", "", regex=False)

j = rep.merge(scan[["run_id", "path", "s_i"]], on="run_id", how="inner")
j = j.dropna(subset=["s_i", "turnover_pct", "net_excess_pct", "long_sharpe", "long_max_drawdown_pct"])
j = j.sort_values("s_i", ascending=False).drop_duplicates(subset=["run_id"], keep="first")
mask_pool = j["name"].str.match(r"(?i)^(f-p\d|f-\ds-|f-1y-|f-3m-|pool)")
j = j[~mask_pool]
j = j.sort_values("s_i", ascending=False).drop_duplicates(subset=["name"], keep="first")

def load_run(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return d.get("results") or d

def chart_series(an, chart, name):
    for e in an[chart]["y"]:
        if e["name"] == name:
            return np.asarray([np.nan if v is None else float(v) for v in e["data"]], dtype=float)
    return None

def dates_of(an):
    return [str(v)[:10] for v in an["query_rank_ic_sequence_chart"]["x"][0]["data"]]

def maxdd(level):
    peak = np.maximum.accumulate(level)
    return float(np.nanmax(peak - level))

rows = []
for r in j.to_dict("records"):
    run = load_run(r["path"])
    if run is None:
        continue
    an = run["factor_analysis"]
    try:
        ds = dates_of(an)
        ric = chart_series(an, "query_rank_ic_sequence_chart", "Rank_IC")
        grp = "组10" if int(r["direction"]) == 1 else "组1"
        exc = chart_series(an, "query_factor_excess_chart", grp)
        ret = chart_series(an, "query_return_chart", grp)
    except Exception:
        continue
    if ric is None or exc is None or ret is None or len(ds) != len(ric):
        continue
    ds = np.asarray(ds)
    turn = float(r["turnover_pct"]) / 100.0
    sr_rep = float(r["long_sharpe"])
    out = {"name": r["name"], "direction": int(r["direction"]), "run_id": r["run_id"],
           "s_i_5y_scan": float(r["s_i"]), "turn": turn, "net_rep_5y": float(r["net_excess_pct"]) / 100.0,
           "sr_rep_5y": sr_rep, "dd_rep_5y": float(r["long_max_drawdown_pct"]) / 100.0}
    ok = True
    for w, start in WINS.items():
        sel = ds >= start
        n = int(sel.sum())
        if n < 5:
            ok = False
            break
        idx = np.where(sel)[0]
        i0 = idx[0]
        cum_end = float(exc[idx[-1]])
        cum_beg = float(exc[i0 - 1]) if i0 - 1 >= 0 else 0.0
        gross = (cum_end - cum_beg) * PPY / n
        net = gross - turn * 0.1512
        rsel = ric[sel]
        fin = rsel[np.isfinite(rsel)]
        mean = float(fin.mean()); std = float(fin.std(ddof=1)) if fin.size > 1 else float("nan")
        ir = mean / std if std and std > 0 else float("nan")
        aligned = fin if mean >= 0 else -fin
        win_ = float((aligned > 0.02).mean())
        s_i = abs(mean) * abs(ir) * win_ if np.isfinite(ir) else float("nan")
        inc = np.diff(ret[idx], prepend=float(ret[i0 - 1]) if i0 - 1 >= 0 else 0.0)
        sd = inc.std(ddof=1)
        sr_proxy = float(inc.mean() / sd * np.sqrt(PPY)) if sd > 0 else float("nan")
        lvl = np.concatenate([[1.0], 1.0 + ret[idx]])
        dd = maxdd(lvl)
        out.update({f"gross_{w}": gross, f"net_{w}": net, f"s_i_{w}": s_i, f"sr_proxy_{w}": sr_proxy,
                    f"dd_{w}": dd, f"rankic_{w}": mean, f"n_{w}": n})
    if not ok:
        continue
    # SR 比例校准：SR_est(w) = proxy(w) × (sr_rep / proxy_5y)
    k = sr_rep / out["sr_proxy_5y"] if out["sr_proxy_5y"] and np.isfinite(out["sr_proxy_5y"]) else 1.0
    for w in WINS:
        out[f"sr_{w}"] = out[f"sr_proxy_{w}"] * k
    rows.append(out)

seats = pd.DataFrame(rows)
seats["is_incumbent"] = seats["name"].isin(INCUMBENT)
seats.to_csv(OUT / "seat_windows.csv", index=False, encoding="utf-8-sig")
print("seats with 3 windows:", len(seats))

# ---- 校准输出 ----
inc = seats[seats["is_incumbent"]].set_index("name")
print("\n[校准] 现役 5 席（5 年窗口 vs 平台 report）")
for nm, r in inc.iterrows():
    print(f"  {nm:<22} gross {r['gross_5y']:+.2%} | net {r['net_5y']:+.2%} (rep {r['net_rep_5y']:+.2%}) | SR {r['sr_5y']:.3f} (rep {r['sr_rep_5y']:.3f}) | DD {r['dd_5y']:.2%} (rep {r['dd_rep_5y']:.2%})")
diff_net = (seats["net_5y"] - seats["net_rep_5y"]).abs()
diff_sr = (seats["sr_5y"] - seats["sr_rep_5y"]).abs()
diff_dd = (seats["dd_5y"] - seats["dd_rep_5y"]).abs()
print(f"  全库 5y 校准: |Δnet| 中位 {diff_net.median():.4f} p95 {diff_net.quantile(0.95):.4f} | |ΔSR| 中位 {diff_sr.median():.4f} | |ΔDD| 中位 {diff_dd.median():.4f}")


def nc_mix(net, turn, sr, dd):
    """月换手 = k×每次换手（k=1/2/3，月分布 7/46/7），地板 0.30；另给 flat 2× 变体。"""
    base = max(net, 0.0) * sr * max(0.0, 1 - 1.2 * dd) / 0.6
    ncs = {k: min(1.0, base / max(k * turn, 0.30)) for k in (1, 2, 3)}
    mix = (7 * ncs[1] + 46 * ncs[2] + 7 * ncs[3]) / 60
    flat = min(1.0, base / max(2 * turn, 0.30))
    return mix, flat, ncs

# ---- 池评估 ----
def pool_eval(idx):
    d = seats.iloc[list(idx)]
    out = {}
    for w in WINS:
        net = float(d[f"net_{w}"].mean()); turn = float(d["turn"].mean())
        sr = float(d[f"sr_{w}"].mean()); dd = float(d[f"dd_{w}"].mean())
        mix, flat, ncs = nc_mix(net, turn, sr, dd)
        out[f"net_{w}"] = net; out[f"sr_{w}"] = sr; out[f"dd_{w}"] = dd
        out[f"nc_{w}"] = mix
        out[f"nc_flat_{w}"] = flat
    out["nc_3win"] = (out["nc_5y"] + out["nc_1y"] + out["nc_3m"]) / 3
    rawA5 = float(d["s_i_5y"].mean()); rawA1 = float(d["s_i_1y"].mean()); rawA3 = float(d["s_i_3m"].mean())
    out["rawA_5y"] = rawA5; out["na_5y"] = min(max(rawA5 / 0.08, 0), 0.70)
    out["rawA_3win"] = (rawA1 + rawA5 + rawA3) / 3; out["na_3win"] = min(max(out["rawA_3win"] / 0.08, 0), 0.70)
    out["turn"] = float(d["turn"].mean())
    out["comb_5yNA"] = 0.20 * out["na_5y"] + 0.45 * out["nc_3win"]
    out["comb_3winNA"] = 0.20 * out["na_3win"] + 0.45 * out["nc_3win"]
    out["pts_5yNA"] = out["comb_5yNA"] * 40000 * 1.10
    out["pts_3winNA"] = out["comb_3winNA"] * 40000 * 1.10
    return out

inc_idx = seats.index[seats["is_incumbent"]].tolist()
inc_eval = pool_eval(inc_idx)
print("\n[现役池 三窗口]")
for w in ("5y", "1y", "3m"):
    print(f"  {w}: net {inc_eval[f'net_{w}']:+.2%} SR {inc_eval[f'sr_{w}']:.3f} DD {inc_eval[f'dd_{w}']:.2%} NC {inc_eval[f'nc_{w}']:.3f}")
print(f"  NC 三窗口均值 {inc_eval['nc_3win']:.3f} | rawA(5y) {inc_eval['rawA_5y']:.4f} NA {inc_eval['na_5y']:.3f} | Comb(5yNA) {inc_eval['comb_5yNA']:.4f} -> {inc_eval['pts_5yNA']:.0f} 分/月")
print(f"  rawA(3win) {inc_eval['rawA_3win']:.4f} NA(3win) {inc_eval['na_3win']:.3f} | Comb(3winNA) {inc_eval['comb_3winNA']:.4f} -> {inc_eval['pts_3winNA']:.0f} 分/月")

# 现役席位三窗口明细表
print("\n[现役席位三窗口明细]")
show_cols = ["name", "turn"]
for w in ("5y", "1y", "3m"):
    show_cols += [f"net_{w}", f"s_i_{w}", f"sr_{w}", f"dd_{w}", f"rankic_{w}"]
tbl = inc.reset_index()[show_cols].copy()
with pd.option_context("display.width", 240, "display.float_format", lambda v: f"{v:.4f}"):
    print(tbl.to_string(index=False))

# ---- 枚举 ----
SHORT = pd.concat([seats.sort_values("s_i_5y_scan", ascending=False).head(22), seats[seats["is_incumbent"]]]).drop_duplicates(subset=["name"])
names = SHORT["name"].tolist()
idx_map = {nm: i for i, nm in enumerate(names)}
M = {w: {k: SHORT[k].to_numpy(dtype=float) for k in (f"net_{w}", f"sr_{w}", f"dd_{w}", f"s_i_{w}")} for w in WINS}
TURN = SHORT["turn"].to_numpy(dtype=float)

def eval_combo(idx):
    n = len(idx)
    nc = {}; nc_flat = {}
    for w in WINS:
        net = M[w][f"net_{w}"][idx].mean(); sr = M[w][f"sr_{w}"][idx].mean(); dd = M[w][f"dd_{w}"][idx].mean()
        mix, flat, ncs = nc_mix(net, TURN[idx].mean(), sr, dd)
        nc[w] = mix
        nc_flat[w] = flat
    nc3 = (nc["5y"] + nc["1y"] + nc["3m"]) / 3
    nc3f = (nc_flat["5y"] + nc_flat["1y"] + nc_flat["3m"]) / 3
    ra5 = M["5y"]["s_i_5y"][idx].mean(); ra1 = M["1y"]["s_i_1y"][idx].mean(); ra3 = M["3m"]["s_i_3m"][idx].mean()
    na5 = min(max(ra5 / 0.08, 0), 0.70); na3w = min(max(((ra1 + ra5 + ra3) / 3) / 0.08, 0), 0.70)
    pts5 = (0.20 * na5 + 0.45 * nc3) * 44000
    pt3w = (0.20 * na3w + 0.45 * nc3) * 44000
    return dict(nc_5y=nc["5y"], nc_1y=nc["1y"], nc_3m=nc["3m"], nc_3win=nc3, nc3_flat=nc3f,
                rawA_5y=ra5, rawA_3win=(ra1 + ra5 + ra3) / 3, na_5y=na5, na_3win=na3w,
                turn=float(TURN[idx].mean()), net_5y=float(M["5y"]["net_5y"][idx].mean()),
                pts_5yNA=pts5, pts_3winNA=pt3w)

rows5, rows6 = [], []
for combo in itertools.combinations(range(len(names)), 5):
    e = eval_combo(list(combo))
    e["seats"] = " + ".join(sorted(names[i] for i in combo))
    rows5.append(e)
for combo in itertools.combinations(range(len(names)), 6):
    e = eval_combo(list(combo))
    e["seats"] = " + ".join(sorted(names[i] for i in combo))
    rows6.append(e)
df5 = pd.DataFrame(rows5).sort_values("pts_5yNA", ascending=False)
df6 = pd.DataFrame(rows6).sort_values("pts_5yNA", ascending=False)
df5.to_csv(OUT / "top_pools_5seat.csv", index=False, encoding="utf-8-sig")
df6.to_csv(OUT / "top_pools_6seat.csv", index=False, encoding="utf-8-sig")

# 逐候选边际（3 窗口口径）
cand = []
for r in seats.sort_values("s_i_5y_scan", ascending=False).head(30).to_dict("records"):
    i = list(seats.index[seats["name"] == r["name"]])[0]
    base = pool_eval(inc_idx)
    add6 = pool_eval(inc_idx + [i])
    swap = pool_eval([x for x in inc_idx if seats.loc[x, "name"] != "SIZE-ONLY-20260911"] + [i])
    cand.append(dict(name=r["name"], s_i_5y_scan=r["s_i_5y_scan"], turn=r["turn"],
                     net_5y=r["net_5y"], net_1y=r["net_1y"], net_3m=r["net_3m"],
                     s_i_5y=r["s_i_5y"], s_i_1y=r["s_i_1y"], s_i_3m=r["s_i_3m"],
                     add6_pts=add6["pts_5yNA"], add6_d=add6["pts_5yNA"] - base["pts_5yNA"],
                     add6_d3=add6["pts_3winNA"] - base["pts_3winNA"],
                     swapSIZE_pts=swap["pts_5yNA"], swapSIZE_d=swap["pts_5yNA"] - base["pts_5yNA"]))
cd = pd.DataFrame(cand)
cd.to_csv(OUT / "candidate_composite_3win.csv", index=False, encoding="utf-8-sig")

pd.set_option("display.width", 260)
show = ["seats", "pts_5yNA", "pts_3winNA", "nc_5y", "nc_1y", "nc_3m", "nc_3win", "rawA_5y", "na_5y", "turn"]
print("\n== 5 席组合 TOP10（三窗口综合） ==")
with pd.option_context("display.max_colwidth", 110):
    print(df5[show].head(10).to_string(index=False))
print("\n== 6 席组合 TOP6 ==")
with pd.option_context("display.max_colwidth", 110):
    print(df6[show].head(6).to_string(index=False))
print("\n== 逐候选三窗口边际（模型现役基线 %.0f 分/月） ==" % inc_eval["pts_5yNA"])
with pd.option_context("display.max_colwidth", 60):
    print(cd.head(20).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print("\nwritten:", OUT)
