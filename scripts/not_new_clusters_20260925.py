"""把"与已知 B/N 体系高相关、不应再算作新簇"的候选簇单独落档。

口径：新簇目录（candidate-new-clusters-20260925）用 |rho| >= 0.80 硬切剔除重合候选，
但 0.60-0.80 区间的簇仍被留在"新簇"名单里。项目登记表口径（CONTINUE.md 第 12 节）把
|rho| >= 0.60 记为高相关预警，本脚本按同一阈值把它们标为"非新簇"，
0.45-0.60 记为边界待判，其余才算独立新簇。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research_reports/platform_alignment/candidate-new-clusters-20260925"
OVERLAP = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
PROFILE = BASE / "new_clusters_profile.csv"
ASSIGN = BASE / "candidate_new_cluster_assignment.csv"
OUT_MD = BASE / "not_new_clusters_20260925.md"
OUT_CSV = BASE / "not_new_clusters_20260925.csv"
HARD_LIMIT = 0.80
KNOWN_LIMIT = 0.60
GRAY_LIMIT = 0.45
COLUMNS = [
    "cluster", "size", "best_member", "best_net", "best_net_y2026", "bands",
    "nearest_known_cluster", "nearest_known_factor", "max_known_abs_rho",
    "high_correlation_clusters", "class", "members",
]


def classify(rho: float) -> str:
    if rho >= KNOWN_LIMIT:
        return "非新簇（与已知簇高相关）"
    if rho >= GRAY_LIMIT:
        return "边界（待人工判定）"
    return "独立新簇"


def main() -> int:
    profile = pd.read_csv(PROFILE)
    assign = pd.read_csv(ASSIGN)
    overlap = pd.read_csv(OVERLAP)
    profile["class"] = profile["max_known_abs_rho"].apply(classify)
    tagged = profile[COLUMNS].sort_values("max_known_abs_rho", ascending=False)
    tagged.to_csv(OUT_CSV, index=False)

    members = assign.groupby("new_cluster")["candidate"].apply(lambda s: ",".join(s))

    def block(frame: pd.DataFrame, title: str, note: str) -> list[str]:
        lines = [f"### {title}", "", note, "",
                 "| 新簇 | 条数 | 最优成员 | 净超额 | 2026 净额 | 换手档 | 最近已知簇 | 最近已知成员 | max|rho| | 与已知高相关簇 |",
                 "| --- | ---: | --- | ---: | ---: | --- | --- | --- | ---: | --- |"]
        for row in frame.itertuples():
            lines.append(
                "| {c} | {n} | {m} | {net:.3f} | {y:.3f} | {b} | {kc} | {kf} | {r:.3f} | {hc} |".format(
                    c=row.cluster, n=int(row.size), m=row.best_member,
                    net=row.best_net if np.isfinite(row.best_net) else float("nan"),
                    y=row.best_net_y2026 if np.isfinite(row.best_net_y2026) else float("nan"),
                    b=row.bands, kc=row.nearest_known_cluster, kf=row.nearest_known_factor,
                    r=row.max_known_abs_rho,
                    hc=row.high_correlation_clusters if isinstance(row.high_correlation_clusters, str) else "",
                )
            )
        lines.append("")
        return lines

    not_new = tagged[tagged["max_known_abs_rho"] >= KNOWN_LIMIT]
    gray = tagged[(tagged["max_known_abs_rho"] >= GRAY_LIMIT) & (tagged["max_known_abs_rho"] < KNOWN_LIMIT)]
    fresh = tagged[tagged["max_known_abs_rho"] < GRAY_LIMIT]
    best_of_not_new = not_new[not_new["best_net_y2026"].notna()].sort_values(
        "best_net_y2026", ascending=False
    )

    lines = [
        "# 不应再算作新簇的候选（2026-09-25 复判）",
        "",
        "对新簇目录 `candidate-new-clusters-20260925`（205 条 2026-09-24 GP 候选、硬切阈值 |rho| = 0.80）",
        "做一次复判：硬切只剔除与任一已知成员 |rho| >= 0.80 的候选，但 0.60-0.80 区间的簇仍留在新簇名单中。",
        "按项目登记表口径（`CONTINUE.md` 第 12 节：|rho| >= 0.60 记为与已有因子的高相关预警），",
        "把与已知 B/N/复合体系最高相关 >= 0.60 的簇标为**非新簇**，0.45-0.60 记为边界待判。",
        "",
        f"- 原新簇数：**{len(profile)}**（多成员 {int((profile['size'] > 1).sum())}，单成员 {int((profile['size'] == 1).sum())}）",
        f"- 非新簇（max|rho| >= {KNOWN_LIMIT:.2f}）：**{len(not_new)}** 个",
        f"- 边界待判（{GRAY_LIMIT:.2f} <= max|rho| < {KNOWN_LIMIT:.2f}）：**{len(gray)}** 个",
        f"- 独立新簇（max|rho| < {GRAY_LIMIT:.2f}）：**{len(fresh)}** 个",
        "",
        "判定使用的相关性口径：每日有效截面 Spearman 相关后的交易日均值，与 `cluster-overlap-20260924/candidate_matches.csv` 同源。",
        "",
        "## 一、不应再算作新簇（max|rho| >= 0.60）",
        "",
        "| 新簇 | 条数 | 最优成员 | 净超额 | 2026 净额 | 换手档 | 最近已知簇 | 最近已知成员 | max|rho| |",
        "| --- | ---: | --- | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for row in not_new.itertuples():
        y = row.best_net_y2026
        lines.append(
            "| {c} | {n} | {m} | {net} | {y} | {b} | {kc} | {kf} | {r:.3f} |".format(
                c=row.cluster, n=int(row.size), m=row.best_member,
                net=f"{row.best_net:.3f}" if np.isfinite(row.best_net) else "n/a",
                y=f"{y:.3f}" if np.isfinite(y) else "—", b=row.bands,
                kc=row.nearest_known_cluster, kf=row.nearest_known_factor, r=row.max_known_abs_rho,
            )
        )
    lines += [
        "",
        "簇内成员：",
        "",
    ]
    for row in not_new.itertuples():
        lines.append(f"- {row.cluster}：{members.get(row.cluster, row.best_member)}")
    lines += [
        "",
        "## 二、边界待判（0.45 <= max|rho| < 0.60）",
        "",
        "这一档与已知簇相关不低但未过高相关预警线，单独保留、不并入正式新簇统计，也不直接淘汰。",
        "",
        "| 新簇 | 条数 | 最优成员 | 净超额 | 2026 净额 | 换手档 | 最近已知簇 | 最近已知成员 | max|rho| |",
        "| --- | ---: | --- | ---: | ---: | --- | --- | --- | ---: |",
    ]
    for row in gray.itertuples():
        y = row.best_net_y2026
        lines.append(
            "| {c} | {n} | {m} | {net} | {y} | {b} | {kc} | {kf} | {r:.3f} |".format(
                c=row.cluster, n=int(row.size), m=row.best_member,
                net=f"{row.best_net:.3f}" if np.isfinite(row.best_net) else "n/a",
                y=f"{y:.3f}" if np.isfinite(y) else "—", b=row.bands,
                kc=row.nearest_known_cluster, kf=row.nearest_known_factor, r=row.max_known_abs_rho,
            )
        )
    lines += [
        "",
        "## 三、复判后的有效新簇数",
        "",
        f"扣掉非新簇 {len(not_new)} 个后，正式可用于新簇多样性统计的是 **{len(tagged) - len(not_new)}** 个",
        f"（其中独立新簇 {len(fresh)} 个、边界 {len(gray)} 个）。",
        "",
        "## 四、非新簇里 2026 净额仍较高者（仅作参考，不进新簇统计）",
        "",
        "| 新簇 | 最优成员 | 净超额 | 2026 净额 | 最近已知成员 | max|rho| |",
        "| --- | --- | ---: | ---: | --- | ---: |",
    ]
    for row in best_of_not_new.head(8).itertuples():
        lines.append(
            "| {c} | {m} | {net:.3f} | {y:.3f} | {kf} | {r:.3f} |".format(
                c=row.cluster, m=row.best_member, net=row.best_net, y=row.best_net_y2026,
                kf=row.nearest_known_factor, r=row.max_known_abs_rho,
            )
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"not_new={len(not_new)} gray={len(gray)} fresh={len(fresh)} total={len(tagged)}")
    print(f"written: {OUT_MD.name}, {OUT_CSV.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())