"""Persist nearest other-cluster relationships from the saved exact matrix.

Cluster similarity = maximum absolute daily-mean Spearman between members.
Original B/N/S memberships remain separate even when composites bridge them.
No platform calls, panel materialization, or return backtests.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/recent-factor-clusters-20261010-average-rank-v2"


def main():
    matrix = pd.read_csv(OUT / "correlation_matrix.csv", index_col=0)
    counts = pd.read_csv(OUT / "valid_dates_matrix.csv", index_col=0)
    refs = pd.read_csv(OUT / "references.csv")
    new = pd.read_csv(OUT / "new_unanchored_clusters.csv")
    members = pd.concat([
        refs[["cluster", "panel_id", "name"]],
        new.rename(columns={"new_cluster": "cluster"})[["cluster", "panel_id", "name"]],
    ], ignore_index=True)
    assert members.panel_id.is_unique
    members = members[members.panel_id.isin(matrix.index)]
    groups = {k: v for k, v in members.groupby("cluster", sort=True)}
    names = members.set_index("panel_id")["name"].to_dict()
    pairs = []
    labels = sorted(groups)
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            block = matrix.loc[groups[a].panel_id, groups[b].panel_id]
            values = block.to_numpy()
            if not np.isfinite(values).any():
                continue
            x, y = np.unravel_index(np.nanargmax(np.abs(values)), values.shape)
            ap, bp = block.index[x], block.columns[y]
            rho = float(values[x, y])
            pairs.append(dict(cluster_a=a, cluster_b=b, rho=rho, abs_rho=abs(rho),
                              member_a=names[ap], member_b=names[bp],
                              panel_a=ap, panel_b=bp, valid_dates=int(counts.loc[ap, bp]),
                              threshold_edge=abs(rho) >= .8))
    pairs = pd.DataFrame(pairs)
    pairs.to_csv(OUT / "cluster_pair_max_correlations.csv", index=False)
    directed = []
    for _, row in pairs.iterrows():
        for reverse in [False, True]:
            a, b = ("b", "a") if reverse else ("a", "b")
            directed.append(dict(cluster=row[f"cluster_{a}"], other_cluster=row[f"cluster_{b}"],
                                 rho=row.rho, abs_rho=row.abs_rho,
                                 member= row[f"member_{a}"], other_member=row[f"member_{b}"],
                                 panel=row[f"panel_{a}"], other_panel=row[f"panel_{b}"],
                                 valid_dates=row.valid_dates, threshold_edge=row.threshold_edge))
    directed = pd.DataFrame(directed).sort_values(
        ["cluster", "abs_rho", "other_cluster"], ascending=[True, False, True])
    directed["rank"] = directed.groupby("cluster").cumcount() + 1
    directed.to_csv(OUT / "cluster_neighbors_ranked.csv", index=False)
    nearest = directed.groupby("cluster", sort=False).head(1).copy()
    old = directed[directed.other_cluster.str.match(r"^[BNS]\d+$")].groupby("cluster", sort=False).head(1)
    old = old.drop(columns="rank").rename(columns={c: "nearest_old_" + c for c in old.columns if c != "cluster"})
    nearest = nearest.merge(old, on="cluster", how="left")
    nearest.to_csv(OUT / "cluster_nearest_other.csv", index=False)
    new_enriched = new.merge(nearest.rename(columns={"cluster": "new_cluster"}), on="new_cluster", how="left")
    new_enriched.to_csv(OUT / "new_unanchored_clusters_with_neighbors.csv", index=False)
    old_all = pd.read_csv(OUT.parent / "all-factor-cluster-expansion-20260919.clusters.csv")
    missing = sorted(set(old_all.cluster) - set(refs.cluster))
    meta = dict(method="max absolute pairwise daily-mean Spearman among cluster members",
                threshold=.8, missing_old_clusters=missing,
                excluded_reference_file="reference_exclusions.csv",
                note="S03 unavailable; SEP-isolated is an unclustered historical reference, not a B/N/S cluster",
                evaluated_clusters=len(labels), cluster_pairs=len(pairs))
    (OUT / "cluster_neighbors_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    lines = ["# 每簇最接近的其他簇", "",
             "簇间相关性取两簇所有成员配对中最大的绝对日均 Spearman，并保留该配对的正负号。"
             "这不是簇中心相关性，也不表示簇内任意成员都如此接近。", "",
             "原 B/N/S 簇不因 C 图的组合桥接而合并；U 簇单独登记。`SEP-isolated` 是历史未归簇 V6-V01，仅为参考标签。", "",
             "## U 簇最高相关性", "",
             "| 簇 | 最近其他簇/参考 | rho | 对应成员 | 最近已覆盖 B/N/S 簇 | rho |",
             "|---|---|---:|---|---|---:|"]
    for _, r in nearest[nearest.cluster.str.startswith("U")].sort_values("cluster").iterrows():
        lines.append(f"| {r.cluster} | {r.other_cluster} | {r.rho:+.4f} | {r.member} ↔ {r.other_member} | {r.nearest_old_other_cluster} | {r.nearest_old_rho:+.4f} |")
    lines += ["", "## 覆盖与使用", "",
              f"旧 B/N 未覆盖：`{' / '.join(missing)}`；S03 参考代理未纳入。不能用暂无旧锚点证明与未覆盖簇独立。",
              "", "每簇最高相关、前排近邻及全部配对均已保存：",
              "- [最高相关](cluster_nearest_other.csv)、[完整排序](cluster_neighbors_ranked.csv)。",
              "- [U 成员台账含近邻](new_unanchored_clusters_with_neighbors.csv)。",
              "- [全部簇间最大相关](cluster_pair_max_correlations.csv)、[口径](cluster_neighbors_metadata.json)。",
              "", "复跑：`python3 scripts/cluster_nearest_neighbors_20261010.py`。仅使用保存矩阵，平台算力为零。", ""]
    (OUT / "cluster-nearest-neighbors.md").write_text("\n".join(lines), encoding="utf-8")
    # Reconcile every chosen nearest against all saved eligible competitors.
    for _, r in nearest.iterrows():
        eligible = directed[directed.cluster.eq(r.cluster)]
        assert np.isclose(r.abs_rho, eligible.abs_rho.max())
        assert r.cluster != r.other_cluster and r.valid_dates >= 1
    assert len(new_enriched) == 32 and new_enriched.other_cluster.notna().all()
    print(nearest[nearest.cluster.str.startswith("U")][
        ["cluster", "other_cluster", "rho", "nearest_old_other_cluster", "nearest_old_rho"]].to_string(index=False))
    print(f"verified {len(labels)} cluster labels, {len(pairs)} pairs, 32 U member annotations")


if __name__ == "__main__":
    main()
