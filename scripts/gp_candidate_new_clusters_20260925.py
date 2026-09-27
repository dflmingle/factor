"""相对 B/N 体系的「新簇」清单（本地，零平台算力）。

口径（2026-09-25 修订）：
  1. 剔除与既有 B/N/复合簇有重合的候选：即 members_over_threshold >= 1
     （在 cluster-overlap-20260924 口径下，对任一已知成员 |rho| >= 0.80）。
  2. 余下候选之间用 |rho| >= 0.80 切连通分量；**单成员分量也算一个独立新簇**。
  3. 相关矩阵直接复用 candidate-self-cluster-20260925 已算好的 205x205
     （含逐日 pairwise-complete 重算），不重算面板。

规则版本：candidate-new-clusters-20260925（与 candidate-self-cluster-20260925 分开存放）。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PA = ROOT / "research_reports/platform_alignment"
WIDE = PA / "candidate-self-cluster-20260925/candidate_self_corr_wide.csv"
META = PA / "cluster-overlap-20260924/candidate_matches.csv"
OUT = PA / "candidate-new-clusters-20260925"
THRESHOLD = 0.80


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wide = pd.read_csv(WIDE, index_col=0)
    meta = pd.read_csv(META).set_index("candidate")
    labels = list(wide.index)
    meta = meta.loc[labels]

    overlap = meta["members_over_threshold"].astype(float) >= 1
    partial = (meta["members_near_threshold"].astype(float) >= 1) & ~overlap
    kept = [label for label in labels if not bool(overlap.loc[label])]
    dropped = [label for label in labels if bool(overlap.loc[label])]
    print(f"[filter] total={len(labels)} dropped_overlap={len(dropped)} kept={len(kept)}", flush=True)

    positions = {label: index for index, label in enumerate(labels)}
    parent = {label: label for label in kept}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    matrix = wide.to_numpy(dtype="float64")
    for i, left in enumerate(kept):
        for right in kept[i + 1:]:
            if abs(matrix[positions[left], positions[right]]) >= THRESHOLD:
                union(left, right)

    groups: dict[str, list[str]] = {}
    for label in kept:
        groups.setdefault(find(label), []).append(label)

    rows = []
    for root in sorted(groups):
        members = sorted(groups[root])
        sub = meta.loc[members]
        best = sub["net_y2026"].astype(float).idxmax()
        rows.append({
            "new_cluster": "",
            "size": len(members),
            "best_member": best,
            "best_net": float(sub.loc[best, "net"]),
            "best_net_y2026": float(sub.loc[best, "net_y2026"]),
            "best_turnover": float(sub.loc[best, "turnover"]),
            "median_net": float(sub["net"].astype(float).median()),
            "median_net_y2026": float(sub["net_y2026"].astype(float).median()),
            "median_turnover": float(sub["turnover"].astype(float).median()),
            "bands": ",".join(sorted({str(v) for v in sub["band"]})),
            "both_positive": bool((sub["net"].astype(float) > 0).any()
                                  and (sub["net_y2026"].astype(float) > 0).any()),
            "max_known_abs_rho": float(sub["max_abs_corr_member"].astype(float).max()),
            "touches_partial_band": bool(partial.loc[members].any()),
            "members": " | ".join(members),
        })
    frame = pd.DataFrame(rows).sort_values(
        ["size", "best_net_y2026"], ascending=[False, False]).reset_index(drop=True)
    frame["new_cluster"] = [f"K{i + 1:03d}" for i in range(len(frame))]
    frame.to_csv(OUT / "new_clusters.csv", index=False)

    assignment = meta.loc[kept, ["band", "net", "turnover", "net_y2026",
                                 "max_abs_corr_member", "max_abs_corr_member_name"]].copy()
    assignment["new_cluster"] = ""
    for row in frame.itertuples():
        for label in str(row.members).split(" | "):
            assignment.loc[label, "new_cluster"] = row.new_cluster
    assignment.to_csv(OUT / "candidate_new_cluster_assignment.csv")

    good = frame[(frame["best_net"] > 0) & (frame["best_net_y2026"] > 0)]
    top = frame.sort_values("best_net_y2026", ascending=False).head(20)
    lines = [
        "# 相对 B/N 体系的候选新簇（2026-09-25 口径）",
        "",
        "- 剔除与既有 B/N/复合簇重合的候选（对任一已知成员 `|rho| >= 0.80`），余下候选之间用 "
        "`|rho| >= 0.80` 切连通分量；**单成员分量也计为一个独立新簇**。",
        f"- 输入：205 条 2026-09-24 GP 候选；剔除重合 {len(dropped)} 条，保留 {len(kept)} 条。",
        f"- 相关矩阵复用 `candidate-self-cluster-20260925`（同口径，含逐日 pairwise-complete 重算）。",
        "",
        "## 结果",
        "",
        f"- 新簇总数：**{len(frame)}** 个；其中多成员 {int((frame['size'] > 1).sum())} 个，"
        f"单成员 {int((frame['size'] == 1).sum())} 个。",
        f"- 净额与 2026 净额同时为正的簇：{len(good)} 个。",
        "",
        "## 按簇内最优成员的 2026 净额排序（前 20）",
        "",
        "| 新簇 | 条数 | 最优成员 | 净额 | 2026 净额 | 换手 | 中位 2026 | 档位 | 双正 | 与已知最高 abs(rho) |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for row in top.itertuples():
        lines.append(f"| {row.new_cluster} | {row.size} | {row.best_member} | {row.best_net:.3f} | "
                     f"{row.best_net_y2026:.3f} | {row.best_turnover:.3f} | "
                     f"{row.median_net_y2026:.3f} | {row.bands} | "
                     f"{'是' if row.both_positive else '否'} | {row.max_known_abs_rho:.3f} |")
    lines += ["", "## 多成员新簇明细", ""]
    for row in frame[frame["size"] > 1].itertuples():
        lines.append(f"### {row.new_cluster}（{row.size} 条，中位 2026 净额 {row.median_net_y2026:.3f}）")
        lines.append("")
        lines.append("| candidate | band | net | turnover | net_y2026 | 与已知最高 abs(rho) |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for label in str(row.members).split(" | "):
            rec = meta.loc[label]
            lines.append(f"| {label} | {rec['band']} | {float(rec['net']):.3f} | "
                         f"{float(rec['turnover']):.3f} | {float(rec['net_y2026']):.3f} | "
                         f"{float(rec['max_abs_corr_member']):.3f} |")
        lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "run_meta.json").write_text(json.dumps({
        "rule_version": "candidate-new-clusters-20260925",
        "generated_at": pd.Timestamp.now().isoformat(),
        "threshold": THRESHOLD,
        "candidates_total": len(labels),
        "dropped_overlapping": len(dropped),
        "kept": len(kept),
        "new_clusters": int(len(frame)),
        "multi_member": int((frame["size"] > 1).sum()),
        "singletons": int((frame["size"] == 1).sum()),
        "both_positive_clusters": int(len(good)),
        "source_matrix": str(WIDE),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] new_clusters={len(frame)} multi={int((frame['size'] > 1).sum())} "
          f"both_positive={len(good)} -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())