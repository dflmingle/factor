"""205 条 2026-09-24 GP 候选的内部自相关与成簇检查（本地，零平台算力）。

问题：这批候选彼此之间是否成团（= 新的候选簇），其中有几个是「好簇」。

口径与 2026-09-19 分簇完全一致：
  signal-date 秩面板 -> 按日横截面 Spearman（平均秩）算术平均；
  成簇阈值 |rho| >= 0.80 切连通分量；|rho| >= 0.60 的配对用逐日
  pairwise-complete 重算；每日最少 100 只股票。

函数 accumulate / exact_pair_corr 直接从 gp_candidates_vs_clusters_20260924.py
导入，避免口径转录误差。
"""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLUSTER_SCRIPT = ROOT / "scripts/gp_candidates_vs_clusters_20260924.py"
PANELS = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/panels"
META = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
OUT = ROOT / "research_reports/platform_alignment/candidate-self-cluster-20260925"
THRESHOLD = 0.80
EXACT_FLOOR = 0.60

_spec = importlib.util.spec_from_file_location("gpc_cluster", CLUSTER_SCRIPT)
gpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gpc)


def main() -> int:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(META)
    cand_ids = sorted(int(name[5:9]) for name in (p.name for p in PANELS.glob("cand_*.npy")))
    matrix = np.stack([np.load(PANELS / f"cand_{idx:04d}.npy") for idx in cand_ids])
    n_items, n_days = matrix.shape[0], matrix.shape[1]
    print(f"[load] candidates={n_items} days={n_days} stocks={matrix.shape[2]} "
          f"elapsed={time.time() - started:.0f}s", flush=True)

    corr_sum = np.zeros((n_items, n_items), dtype="float64")
    corr_cnt = np.zeros((n_items, n_items), dtype="float64")
    for day in range(n_days):
        gpc.accumulate(corr_sum, corr_cnt, matrix[:, day, :])
    with np.errstate(invalid="ignore", divide="ignore"):
        rho_fast = corr_sum / np.where(corr_cnt > 0.0, corr_cnt, np.nan)
    print(f"[fast] done elapsed={time.time() - started:.0f}s", flush=True)

    need_exact = np.abs(rho_fast) >= EXACT_FLOOR
    np.fill_diagonal(need_exact, False)
    upper = np.triu(need_exact, 1)
    pairs = np.argwhere(upper)
    print(f"[exact] pairs |rho_fast|>={EXACT_FLOOR}: {len(pairs)}", flush=True)
    rho_exact = np.full(rho_fast.shape, np.nan, dtype="float64")
    for done, (i, j) in enumerate(pairs.tolist(), start=1):
        value = gpc.exact_pair_corr(matrix[i], matrix[j])
        rho_exact[i, j] = rho_exact[j, i] = value
        if done % 200 == 0:
            print(f"[exact] {done}/{len(pairs)} elapsed={time.time() - started:.0f}s", flush=True)

    effective = np.where(np.isfinite(rho_exact), rho_exact, rho_fast)
    np.fill_diagonal(effective, 1.0)

    parent = list(range(n_items))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    linked = np.abs(effective) >= THRESHOLD
    for i, j in np.argwhere(np.triu(linked, 1)).tolist():
        union(i, j)
    groups: dict[int, list[int]] = {}
    for position in range(n_items):
        groups.setdefault(find(position), []).append(position)

    info = meta.set_index("candidate")
    rows = []
    for root_id, positions in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        labels = [f"cand{cand_ids[p]:04d}" for p in positions]
        sub = info.loc[labels]
        best = sub["net_y2026"].astype(float).idxmax()
        rows.append({
            "cluster": f"S{len(rows) + 1:02d}",
            "size": len(positions),
            "members": " | ".join(labels),
            "best_member": best,
            "best_net_y2026": float(sub.loc[best, "net_y2026"]),
            "best_net": float(sub.loc[best, "net"]),
            "median_turnover": float(sub["turnover"].astype(float).median()),
            "bands": ",".join(sorted({str(v) for v in sub["band"]})),
            "any_rediscovery": bool(sub["is_rediscovery"].any()),
            "max_internal_abs_rho": float(np.abs(effective[np.ix_(positions, positions)]).max()),
        })
    clusters = pd.DataFrame(rows)

    pair_rows = []
    for i, j in np.argwhere(np.triu(linked, 1)).tolist():
        pair_rows.append({
            "left": f"cand{cand_ids[i]:04d}", "right": f"cand{cand_ids[j]:04d}",
            "rho_fast": float(rho_fast[i, j]), "rho_exact": float(rho_exact[i, j]),
            "rho": float(effective[i, j]), "abs_rho": abs(float(effective[i, j])),
        })
    pairs_frame = pd.DataFrame(pair_rows).sort_values("abs_rho", ascending=False)

    wide = pd.DataFrame(effective, index=[f"cand{i:04d}" for i in cand_ids],
                        columns=[f"cand{i:04d}" for i in cand_ids])
    wide.to_csv(OUT / "candidate_self_corr_wide.csv")
    pairs_frame.to_csv(OUT / "candidate_self_pairs.csv", index=False)
    clusters.to_csv(OUT / "candidate_self_clusters.csv", index=False)

    multi = clusters[clusters["size"] > 1]
    novel_flags = info["members_over_threshold"].astype(float) == 0
    lines = [
        "# 2026-09-24 GP 候选内部自相关与成簇",
        "",
        f"- 候选 {n_items} 条（全部为本地已物化面板），信号日 {n_days} 个，口径与 2026-09-19 分簇一致。",
        f"- 快速通道整日矩阵；`|rho| >= {EXACT_FLOOR}` 的配对逐日 pairwise-complete 重算（{len(pairs)} 对）。",
        f"- 成簇阈值 `|rho| >= {THRESHOLD}`，连通分量。",
        "",
        "## 结果",
        "",
        f"- 连通分量总数：{len(clusters)}；其中多成员簇 {len(multi)} 个，单成员 {int((clusters['size'] == 1).sum())} 个。",
        f"- 全库 `|rho| >= {THRESHOLD}` 的候选对：{len(pairs_frame)} 对。",
        "",
        "## 多成员簇",
        "",
        "| 簇 | 成员数 | 最优成员 | 2026 净额 | 净额 | 中位换手 | 档位 | 含已知重发现 | 内部 max abs(rho) |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for row in multi.itertuples():
        lines.append(f"| {row.cluster} | {row.size} | {row.best_member} | {row.best_net_y2026:.3f} | "
                     f"{row.best_net:.3f} | {row.median_turnover:.3f} | {row.bands} | "
                     f"{'是' if row.any_rediscovery else '否'} | {row.max_internal_abs_rho:.3f} |")
    lines += ["", "## 成员明细（仅多成员簇）", ""]
    for row in multi.itertuples():
        lines.append(f"### {row.cluster}（{row.size} 成员）")
        lines.append("")
        lines.append("| candidate | band | net | turnover | net_y2026 | 已知成员最高 abs(rho) |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for label in str(row.members).split(" | "):
            rec = info.loc[label]
            lines.append(f"| {label} | {rec['band']} | {float(rec['net']):.3f} | "
                         f"{float(rec['turnover']):.3f} | {float(rec['net_y2026']):.3f} | "
                         f"{float(rec['max_abs_corr_member']):.3f} |")
        lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "run_meta.json").write_text(json.dumps({
        "rule_version": "candidate-self-cluster-20260925",
        "generated_at": pd.Timestamp.now().isoformat(),
        "threshold": THRESHOLD,
        "exact_floor": EXACT_FLOOR,
        "candidates": n_items,
        "days": n_days,
        "exact_pairs": int(len(pairs)),
        "components": int(len(clusters)),
        "multi_member_clusters": int(len(multi)),
        "linked_pairs": int(len(pairs_frame)),
        "panels_dir": str(PANELS),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] components={len(clusters)} multi={len(multi)} pairs={len(pairs_frame)} "
          f"elapsed={time.time() - started:.0f}s -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())