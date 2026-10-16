"""Finalize the approved opponent-reproduction report without pool evaluation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
SEARCH = HERE / "search"
ROOT = HERE.parents[2]


def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (np.integer, np.bool_)): return v.item()
    if isinstance(v, (float, np.floating)): return float(v) if np.isfinite(v) else None
    return v


def rank(x):
    a = np.asarray(x, float)
    n = np.isfinite(a).sum(1, keepdims=True)
    return rankdata(a, axis=1, method="average", nan_policy="omit") / np.maximum(n, 1) - .5


def rowcorr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    x = np.where(ok, a, np.nan); y = np.where(ok, b, np.nan)
    x -= np.nanmean(x, 1, keepdims=True); y -= np.nanmean(y, 1, keepdims=True)
    den = np.sqrt(np.nansum(x*x, 1)*np.nansum(y*y, 1))
    return np.divide(np.nansum(x*y, 1), den, out=np.full(len(x), np.nan), where=(den > 1e-15))


def main():
    result = pd.read_csv(SEARCH / "single_results.csv")
    targets = pd.read_csv(HERE / "factor_targets.csv")
    target_names = ["不知所云队", "不抵灼灼目光", "Alpha猎手"]
    targets = targets[(targets.period == "2026-10") & targets.display_name.isin(target_names)]
    distances = []
    for row in result[result.cycle.eq(3) & result.window.eq("formal_5y")].itertuples():
        for t in targets.itertuples():
            distances.append({
                "candidate": row.candidate, "opponent": t.display_name,
                "public_factor": t.factor_name, "public_ic": t.ic_mean,
                "public_ir": t.icir, "public_win": t.ic_win_rate,
                "local_ic": row.rank_ic, "local_ir": row.rank_ir, "local_win": row.rank_win,
                "delta_ic": row.rank_ic-t.ic_mean, "delta_ir": row.rank_ir-t.icir,
                "delta_win": row.rank_win-t.ic_win_rate,
                "identity_recovered": False,
            })
    pd.DataFrame(distances).to_csv(SEARCH / "target_metric_distances.csv", index=False)

    # Signal-cluster correlations are informational only and use common saved dates.
    axes = json.loads((SEARCH / "axes.json").read_text())
    dates = pd.DatetimeIndex(axes["dates"]); stocks = pd.Index(axes["symbols"])
    cluster_root = ROOT / "research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2"
    meta = json.loads((cluster_root / "metadata.json").read_text())
    cd = pd.DatetimeIndex(meta["signal_dates"]); cs = pd.Index(meta["stock_ids"])
    ri, si = dates.get_indexer(cd), stocks.get_indexer(cs)
    refs = pd.read_csv(cluster_root / "references.csv")
    new = pd.read_csv(cluster_root / "new_unanchored_clusters.csv").rename(columns={"new_cluster": "cluster"})
    refs = pd.concat([refs, new[["name", "formula", "cluster", "panel_id"]]], ignore_index=True)
    rows = []
    for name in ["GP", "SYMBOLIC", "TREE"]:
        arr = np.load(SEARCH / f"{name}_all_signals.npy")
        panel = np.full((len(cd), len(cs)), np.nan)
        goodd, goods = np.flatnonzero(ri >= 0), np.flatnonzero(si >= 0)
        panel[np.ix_(goodd, goods)] = arr[np.ix_(ri[goodd], si[goods])]
        rp = rank(panel)
        for ref in refs.itertuples():
            path = cluster_root / "panels" / f"{ref.panel_id}.npy"
            if not path.exists(): continue
            other = np.load(path)
            rho = rowcorr(rp, rank(other))
            good = np.isfinite(rho)
            if good.any(): rows.append({"candidate": name, "cluster": ref.cluster, "member": ref.name, "rho": float(np.nanmean(rho)), "abs_rho": abs(float(np.nanmean(rho))), "dates": int(good.sum())})
    corr = pd.DataFrame(rows).sort_values(["candidate", "abs_rho"], ascending=[True, False])
    corr.to_csv(SEARCH / "member_correlations.csv", index=False)
    corr.groupby(["candidate", "cluster"], sort=False).head(1).to_csv(SEARCH / "cluster_correlations.csv", index=False)

    attempts = sum(1 for _ in (SEARCH / "gp_attempts.jsonl").open())
    symbolic = sum(1 for _ in (SEARCH / "symbolic_evaluations.jsonl").open())
    verification = {
        "status": "complete",
        "platform_runs": 0,
        "live_pool_mutations": False,
        "gp_attempts": attempts,
        "symbolic_structures": symbolic,
        "tree_configs": 6,
        "internal_comparisons": attempts + symbolic + 6,
        "frozen_candidates": 3,
        "raw_prefix_checks": "passed before search scoring",
        "unavailable_label_perturbation_tree": True,
        "native_cycle3_periods": int(result[result.cycle.eq(3) & result.window.eq("formal_5y")].periods.iloc[0]),
        "formal_cycle10_periods": int(result[result.cycle.eq(10) & result.window.eq("formal_5y")].periods.iloc[0]),
        "pool_replacement_evaluation": "cancelled per user steering; reproduction is the only objective",
        "official_opponent_formula_recovered": False,
        "official_opponent_daily_signals_available": False,
    }
    (SEARCH / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n")
    (SEARCH / "complete.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n")

    frozen = json.loads((SEARCH / "frozen_candidates.json").read_text())["candidates"]
    lines = [
        "# 公开榜单重点池的本地复刻结果（2026-10-12）", "",
        "本轮已按用户授权完成：遗传编程1280次表达式评估、符号束搜索600个结构、浅层树6个固定配置；平台算力0。用户随后明确以复现对手为首要目标，因此未继续做现役池替换或F席边际评估。",
        "",
        "## 结论",
        "",
        "没有恢复任何参赛者的私有原公式或逐股票信号。公开指标只有汇总值，多个不同公式可以有相近的IC、IR和胜率；本轮候选只能称为机制近邻和指标形状近邻。",
        "",
        "最接近的三条冻结候选：",
    ]
    for f in frozen:
        lines.append(f"- **{f['name']}**：`{f.get('formula', f.get('model'))}`")
    lines += ["", "## 3日周期正式历史窗口", "", "|候选|RankIC|IR|胜率|S_i|净超额|换手|日度NAV最大回撤|", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in result[(result.cycle == 3) & (result.window == "formal_5y")].itertuples():
        lines.append(f"|{r.candidate}|{r.rank_ic:.4f}|{r.rank_ir:.3f}|{r.rank_win:.1%}|{r.s_i:.4f}|{r.net_excess:.2%}|{r.turnover:.2%}|{r.daily_net_nav_max_dd:.2%}|")
    lines += ["", "公开对照中，榜首主要席位的历史指标约为：非流动性 RankIC .0826、IR .516；低换手 .0699/.372；低波动 .0693/.327；RSI反转 .0479/.306。候选与这些摘要的接近程度见 `target_metric_distances.csv`。", "", "## 候选判断", "", "- GP 选出 `smallsize + lowvol20`，3日五年 RankIC .0737，低于榜首公开非流动性席位；其市值相关约 −.673，说明它主要复现了小市值/低波动轴，不是疯猫或榜首原公式证据。后段历史净超额接近0。", "- 符号搜索选出 `illiquidity20 + reversal60`，3日五年净超额 7.36%，但 RankIC .0618、IR .353，未达到榜首公开席位的 .0826/.516；后段仍为正但强度较低。", "- 浅层树在内部验证段表现最好，3日五年 RankIC .1003、IR .596，后段 RankIC .0703、净超额为 −2.81%，因此它更像验证期选择结果，不能称稳定复刻。", "", "三条候选均没有同时匹配目标均值、IR、胜率，也没有证据表明恢复了私有公式。此前那种六位小数一致的结果属于使用全窗口标签的样本内数值拟合，本轮没有重复。", "", "## 可靠性边界", "", "3日周期日期按公开首日推定，本地得到401个完整标签期；对手公开样本数为402，日期中间序列不可见，不能移动日期或删样本来凑指标。10月实时收益不在本地数据范围内（本地截止2026-09-07）。最后历史段此前已经被研究查看，因此不能称全新盲测。", "", "完整产物：`single_results.csv`、`target_metric_distances.csv`、`member_correlations.csv`、`cluster_correlations.csv`、`frozen_candidates.json`、`verification.json`、`complete.json`。"]
    (HERE / "reproduction_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_files = {
        "single_results.csv": SEARCH / "single_results.csv",
        "frozen_candidates.json": SEARCH / "frozen_candidates.json",
        "verification.json": SEARCH / "verification.json",
        "reproduction_summary.md": HERE / "reproduction_summary.md",
    }
    manifest = {"status": "complete", "platform_compute": 0, "internal_comparisons": attempts + symbolic + 6, "official_formula_recovered": False, "pool_evaluation": "cancelled", "hashes": {f: hashlib.sha256(p.read_bytes()).hexdigest() for f, p in manifest_files.items()}}
    (HERE / "reproduction_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(verification, ensure_ascii=False))


if __name__ == "__main__": main()
