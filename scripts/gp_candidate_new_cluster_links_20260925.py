"""给 2026-09-25 候选新簇补记跨簇高相关关系（对齐 B/N 记录方式）。

口径与 2026-09-20 跨簇画像一致：两个簇之间取「全部成员两两相关性的最大 abs(rho)」，
列出所有 > 0.60 的其它簇；同时记录最近已知因子（名称 / 有符号 rho / abs rho）。

输入（都已算好，不重算面板）：
  candidate-new-clusters-20260925/candidate_new_cluster_assignment.csv  （候选 -> 新簇）
  candidate-self-cluster-20260925/candidate_self_corr_wide.csv          （候选 x 候选）
  cluster-overlap-20260924/candidate_member_correlation_long.csv        （候选 x 已知成员）

输出：
  candidate-new-clusters-20260925/new_clusters_with_links.csv
  candidate-new-clusters-20260925/new_cluster_links.csv
  candidate-new-clusters-20260925/cross_cluster_links.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PA = ROOT / "research_reports/platform_alignment"
NEW = PA / "candidate-new-clusters-20260925"
SELF = PA / "candidate-self-cluster-20260925/candidate_self_corr_wide.csv"
LONG = PA / "cluster-overlap-20260924/candidate_member_correlation_long.csv"
LINK_THRESHOLD = 0.60


def main() -> int:
    assignment = pd.read_csv(NEW / "candidate_new_cluster_assignment.csv", index_col=0)
    clusters = pd.read_csv(NEW / "new_clusters.csv")
    wide = pd.read_csv(SELF, index_col=0)
    long_frame = pd.read_csv(LONG)

    cluster_of = assignment["new_cluster"].to_dict()
    members_of: dict[str, list[str]] = {}
    for candidate, cluster in cluster_of.items():
        members_of.setdefault(cluster, []).append(candidate)

    self_matrix = wide.to_numpy(dtype="float64")
    self_labels = list(wide.index)
    self_pos = {label: index for index, label in enumerate(self_labels)}
    signed = wide.copy()

    known_clusters = sorted({str(v) for v in long_frame["member_cluster"].unique()})
    member_candidates = long_frame.pivot_table(index="candidate", columns="member",
                                               values="rho", aggfunc="first")

    link_rows = []
    detail: dict[str, list[str]] = {}
    nearest: dict[str, tuple[str, str, float]] = {}
    for cluster, members in members_of.items():
        entries: list[tuple[float, str]] = []
        for other, other_members in members_of.items():
            if other == cluster:
                continue
            block = self_matrix[np.ix_([self_pos[m] for m in members],
                                       [self_pos[m] for m in other_members])]
            index = np.unravel_index(np.nanargmax(np.abs(block)), block.shape)
            value = float(block[index])
            if abs(value) > LINK_THRESHOLD:
                left, right = members[index[0]], other_members[index[1]]
                entries.append((abs(value), other))
                link_rows.append({"new_cluster": cluster, "other_cluster": other,
                                  "other_kind": "new_cluster", "max_abs_rho": abs(value),
                                  "signed_rho": value, "pair": f"{left}|{right}"})
        for known in known_clusters:
            block = member_candidates.reindex(index=members, columns=long_frame[
                long_frame["member_cluster"] == known]["member"].unique())
            if block.empty or block.isna().all().all():
                continue
            values = block.to_numpy(dtype="float64")
            index = np.unravel_index(np.nanargmax(np.abs(values)), values.shape)
            value = float(values[index])
            if abs(value) > LINK_THRESHOLD:
                left = block.index[index[0]]
                right = block.columns[index[1]]
                entries.append((abs(value), known))
                link_rows.append({"new_cluster": cluster, "other_cluster": known,
                                  "other_kind": "known_cluster", "max_abs_rho": abs(value),
                                  "signed_rho": value, "pair": f"{left}|{right}"})
        entries.sort(reverse=True)
        detail[cluster] = [f"{name}:{value:.3f}" for value, name in entries]

        sub = long_frame[long_frame["candidate"].isin(members)]
        best = sub.loc[sub["abs_rho"].idxmax()] if len(sub) else None
        nearest[cluster] = ((str(best["member"]), str(best["member_cluster"]),
                             float(best["rho"])) if best is not None else ("", "", float("nan")))

    clusters["high_correlation_clusters"] = ["; ".join(detail.get(c, [])) for c in clusters["new_cluster"]]
    clusters["high_correlation_count"] = [len(detail.get(c, [])) for c in clusters["new_cluster"]]
    clusters["nearest_known_factor"] = [nearest.get(c, ("", "", np.nan))[0] for c in clusters["new_cluster"]]
    clusters["nearest_known_cluster"] = [nearest.get(c, ("", "", np.nan))[1] for c in clusters["new_cluster"]]
    clusters["nearest_known_rho"] = [nearest.get(c, ("", "", np.nan))[2] for c in clusters["new_cluster"]]
    clusters["nearest_known_abs_rho"] = clusters["nearest_known_rho"].abs()
    order = ["new_cluster", "size", "best_member", "best_net", "best_net_y2026", "best_turnover",
             "median_net", "median_net_y2026", "median_turnover", "bands", "both_positive",
             "max_known_abs_rho", "touches_partial_band", "nearest_known_factor",
             "nearest_known_cluster", "nearest_known_rho", "nearest_known_abs_rho",
             "high_correlation_count", "high_correlation_clusters", "members"]
    clusters[order].to_csv(NEW / "new_clusters_with_links.csv", index=False)
    links = pd.DataFrame(link_rows).sort_values(["new_cluster", "max_abs_rho"],
                                                ascending=[True, False])
    links.to_csv(NEW / "new_cluster_links.csv", index=False)

    linked = clusters[clusters["high_correlation_count"] > 0].sort_values(
        "high_correlation_count", ascending=False)
    lines = [
        "# 候选新簇的跨簇高相关关系（2026-09-25）",
        "",
        "- 口径同 2026-09-20 跨簇画像：两簇之间取全部成员两两相关性的最大 abs(rho)，"
        "列出所有 `> 0.60` 的其它簇；同时给出最近已知因子。",
        "- 「其它簇」包含：其它候选新簇（K 系列）、B01-B12、N01-N33（已物化部分）、以及未入簇的可见复合成员。",
        f"- {len(clusters)} 个新簇中，{len(linked)} 个存在 >0.60 的跨簇高相关关系；"
        f"共 {len(links)} 条关系记录。",
        "",
        "## 高相关关系最多的新簇",
        "",
        "| 新簇 | 条数 | 最近已知因子 | |rho| | 高相关簇（max abs rho） |",
        "| --- | ---: | --- | ---: | --- |",
    ]
    for row in linked.head(25).itertuples():
        lines.append(f"| {row.new_cluster} | {row.size} | {row.nearest_known_factor} "
                     f"({row.nearest_known_cluster}) | {row.nearest_known_abs_rho:.3f} | "
                     f"{row.high_correlation_clusters} |")
    lines += ["", "## 与已知簇（B/N/复合）高相关的新簇", ""]
    known_links = links[links["other_kind"] == "known_cluster"]
    if len(known_links):
        lines.append("| 新簇 | 已知簇 | max abs rho | 有符号 rho | 触发因子对 |")
        lines.append("| --- | --- | ---: | ---: | --- |")
        for row in known_links.sort_values("max_abs_rho", ascending=False).itertuples():
            lines.append(f"| {row.new_cluster} | {row.other_cluster} | {row.max_abs_rho:.3f} | "
                         f"{row.signed_rho:+.3f} | {row.pair} |")
    else:
        lines.append("（无）")
    (NEW / "cross_cluster_links.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] clusters={len(clusters)} with_links={len(linked)} link_rows={len(links)}",
          flush=True)
    print(f"[known] {len(known_links)} 条 与已知簇的高相关记录", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())