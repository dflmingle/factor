"""候选新簇 vs B/N 基线对照报告（本地，零平台算力）。

输入：
- cluster-profile-nearest-correlation-20260920.md（B/N 基线，平台 report 口径）
- candidate-new-clusters-20260925/new_clusters_profile.csv（106 新簇，09-25 口径）
输出：candidate-new-clusters-20260925/cluster-vs-baseline-20260925.md
"""
from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research_reports" / "platform_alignment"
OUT = BASE / "candidate-new-clusters-20260925"
BASELINE_MD = BASE / "cluster-profile-nearest-correlation-20260920.md"
PROFILE_CSV = OUT / "new_clusters_profile.csv"
REPORT = OUT / "cluster-vs-baseline-20260925.md"

ROW = re.compile(r"^\|\s*([BN]\d{2})\s*\|")


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_range(text: str):
    text = (text or "").strip().replace("%", "")
    if not text or text == "n/a":
        return None, None
    if "~" in text:
        lo, hi = text.split("~")
        return to_float(lo), to_float(hi)
    value = to_float(text)
    return value, value


def load_baseline() -> list[dict]:
    rows = []
    for line in BASELINE_MD.read_text(encoding="utf-8").splitlines():
        if not ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        net_lo, net_hi = parse_range(cells[4])
        turn_lo, turn_hi = parse_range(cells[5])
        dd_lo, dd_hi = parse_range(cells[6])
        ic_lo, ic_hi = parse_range(cells[7])
        rows.append({
            "cluster": cells[0], "feature": cells[1], "size": int(cells[2]),
            "best_member": cells[3], "net_lo": net_lo, "net_hi": net_hi,
            "turn_lo": turn_lo, "turn_hi": turn_hi, "dd_lo": dd_lo, "dd_hi": dd_hi,
            "ic_lo": ic_lo, "ic_hi": ic_hi,
        })
    return rows


def load_new_clusters() -> list[dict]:
    with PROFILE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        raw = list(csv.DictReader(handle))
    rows = []
    for row in raw:
        net_lo, net_hi = parse_range(row["net_range"])
        turn_lo, turn_hi = parse_range(row["turnover_range"])
        dd_lo, dd_hi = parse_range(row["drawdown_range"])
        rows.append({
            "cluster": row["cluster"], "feature": row["feature"], "size": int(row["size"]),
            "best_member": row["best_member"], "net_lo": net_lo, "net_hi": net_hi,
            "turn_lo": turn_lo, "turn_hi": turn_hi, "dd_lo": dd_lo, "dd_hi": dd_hi,
            "range": f"{row['net_range']}", "turn_range": row["turnover_range"],
            "dd_range": row["drawdown_range"], "ic_range": row["rank_ic_range"],
            "net": to_float(row["best_net"]), "net26": to_float(row["best_net_y2026"]),
            "rho": to_float(row["max_known_abs_rho"]),
            "nearest": f"{row['nearest_known_factor']} / {row['nearest_known_cluster']}",
            "links": row["high_correlation_clusters"], "bands": row["bands"],
        })
    rows.sort(key=lambda r: (-(r["net"] if r["net"] is not None else -9), r["cluster"]))
    return rows


def cell(value, digits=2, suffix=""):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}{suffix}"


TIERS = [
    ("A", "净超额 >= 13.63%（基线除 B01 外全部成员之上）", lambda r: r["net"] is not None and r["net"] >= 0.1363),
    ("B", "10%~13.63%（与 B06、N34 同级）", lambda r: r["net"] is not None and 0.10 <= r["net"] < 0.1363),
    ("C", "5%~10%（基线中段 B02 同级或更高）", lambda r: r["net"] is not None and 0.05 <= r["net"] < 0.10),
    ("D", "0~5%", lambda r: r["net"] is not None and 0.0 <= r["net"] < 0.05),
    ("E", "净超额为负", lambda r: r["net"] is not None and r["net"] < 0.0),
]


def main() -> int:
    baseline = load_baseline()
    new = load_new_clusters()
    baseline.sort(key=lambda r: (-(r["net_hi"] if r["net_hi"] is not None else -9), r["cluster"]))

    base_hi = max(r["net_hi"] for r in baseline if r["net_hi"] is not None)
    base_top = [r for r in baseline if r["net_hi"] == base_hi][0]
    second = sorted({r["net_hi"] for r in baseline if r["net_hi"] is not None}, reverse=True)[1]
    new_best = max((r for r in new if r["net"] is not None), key=lambda r: r["net"])
    tail = [r for r in baseline if r["cluster"] not in {"B01", "B06", "N34"}]
    mid_hi = max(r["net_hi"] for r in tail if r["net_hi"] is not None)
    above_mid = [r for r in new if r["net"] is not None and r["net"] * 100 >= mid_hi]
    positive_new = [r for r in new if (r["net"] or -9) > 0]

    assigned = {}
    for code, _, pred in TIERS:
        assigned[code] = [r for r in new if pred(r)]

    shortlist = [r for r in new
                 if r["net"] is not None and r["net"] >= 0.10
                 and (r["net26"] or -9) > 0
                 and (r["turn_hi"] or 999) <= 50
                 and (r["dd_hi"] or 999) <= 35]
    shortlist.sort(key=lambda r: -(r["net26"] or -9))
    borderline = [r for r in shortlist if (r["rho"] or 0) >= 0.75]
    independent = [r for r in new if (r["rho"] or 0) < 0.60]
    both_positive = [r for r in new if (r["net"] or -9) > 0 and (r["net26"] or -9) > 0]

    lines = [
        "# 候选新簇 vs B/N 基线对照（2026-09-25）",
        "",
        "用途：为决赛候选筛选提供并排对照。左侧是平台已保存的 B/N 基线簇，右侧是 "
        "2026-09-24 GP 挖出的候选新簇（已剔除与 B/N 重合），两边用同一套八列口径排列。",
        "",
        "## 结论速览",
        "",
        f"- 基线最强成员仍是 **{base_top['cluster']} / {base_top['best_member']}**，"
        f"5 年净超额 {cell(base_hi, suffix='%')}；新簇最高是 "
        f"**{new_best['cluster']} / {new_best['best_member']}** {cell(new_best['net'] * 100 if new_best['net'] is not None else None, suffix='%')}，"
        f"没有候选超过 B01 的头部。",
        f"- 基线里除 {base_top['cluster']}、B06、N34 之外，其余 {len(tail)} 个簇的净超额上限最高只有 "
        f"{cell(mid_hi, suffix='%')}（B02）；新簇中净超额达到或超过 {cell(mid_hi, suffix='%')} 的有 "
        f"**{len(above_mid)} 条**。",
        f"- 独立性：**{len(independent)}/{len(new)}** 个新簇与任何已知簇成员的最高 abs(rho) < 0.60，"
        f"不属于 B/N 的换皮版本。",
        f"- 双正：**{len(both_positive)}** 个新簇 5 年净超额与 2026 净超额同时为正。",
        f"- 决赛短名单（净超额 >=10%、2026 为正、换手 <=50%、回撤 <=35%）：**{len(shortlist)} 条**，"
        f"其中 {len(borderline)} 条与已知簇相关在 0.75~0.80 的边界上，需要特别甄别。",
        "",
        "## 口径与可比性",
        "",
        "- B/N 基线数值直接来自平台原始 `*.report.csv`（09-20 报告），窗口 `20210907..20260907`。",
        "- 新簇数值来自 09-24 本地 GP 筛选（净超额/换手率/RankIC）+ 本机回撤复算"
        "（`candidate_drawdown.csv` 的 `absolute_max_drawdown`）。",
        "- 基线簇内混有 5 日与 10 日调仓记录，新簇统一 10 日，因此两边不能视为严格同参数对照；"
        "对照只看量级和排序，不做小数点级比较。",
        "- 新簇的净超额来自单次本地筛选运行，与本机复算相关性 0.975、换手 0.994、"
        "平均差 -0.84pp（最大 7.7pp）；候选入决赛前必须用平台回测确认。",
        "- 两边都是“成员范围”，不是簇组合后的表现。",
        "",
        "## B/N 基线（46 簇，按净超额上限排序）",
        "",
        "| 簇 | 特色 | 成员数 | 代表因子（标签） | 净超额范围 | 换手率范围 | 成员最大回撤范围 | RankIC 范围 |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in baseline:
        lines.append(
            f"| {row['cluster']} | {row['feature']} | {row['size']} | {row['best_member']} | "
            f"{cell(row['net_lo'], suffix='%')}~{cell(row['net_hi'], suffix='%')} | "
            f"{cell(row['turn_lo'], suffix='%')}~{cell(row['turn_hi'], suffix='%')} | "
            f"{cell(row['dd_lo'], suffix='%')}~{cell(row['dd_hi'], suffix='%')} | "
            f"{cell(row['ic_lo'], digits=4)}~{cell(row['ic_hi'], digits=4)} |"
        )

    lines += ["", "## 新簇分档（106 簇，本口径）", "",
              "| 档 | 定义 | 数量 |", "|---|---|---:|"]
    for code, label, _ in TIERS:
        lines.append(f"| {code} | {label} | {len(assigned[code])} |")

    for code, label, _ in TIERS:
        rows = sorted(assigned[code], key=lambda r: -(r["net26"] if r["net26"] is not None else -9))
        if not rows:
            continue
        lines += ["", f"### 档 {code}：{label}（{len(rows)} 条，按 2026 净超额排序）", "",
                  "| 簇 | 特色 | 成员数 | 代表因子 | 净超额 | 2026 净超额 | 换手率范围 | 回撤范围 | RankIC | 与已知簇 max abs(rho) | 最近已知簇 |",
                  "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|"]
        for row in rows:
            lines.append(
                f"| {row['cluster']} | {row['feature']} | {row['size']} | {row['best_member']} | "
                f"{cell(row['net'] * 100 if row['net'] is not None else None, suffix='%')} | "
                f"{cell(row['net26'] * 100 if row['net26'] is not None else None, suffix='%')} | "
                f"{row['turn_range']} | {row['dd_range']} | {row['ic_range']} | "
                f"{cell(row['rho'], digits=3)} | {row['nearest']} |"
            )

    lines += ["", "## 决赛候选短名单", "",
              "筛选条件：5 年净超额 >= 10%、2026 净超额 > 0、换手率上限 <= 50%、成员最大回撤上限 <= 35%，"
              "按 2026 净超额排序。", "",
              "| # | 簇 | 代表因子 | 净超额 | 2026 净超额 | 换手率范围 | 回撤范围 | RankIC | 与已知簇 max abs(rho) | 最近已知簇 | 边界提示 |",
              "|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for index, row in enumerate(shortlist, 1):
        note = "与已知簇 0.75~0.80，需甄别" if (row["rho"] or 0) >= 0.75 else "—"
        lines.append(
            f"| {index} | {row['cluster']} | {row['best_member']} | "
            f"{cell(row['net'] * 100 if row['net'] is not None else None, suffix='%')} | "
            f"{cell(row['net26'] * 100 if row['net26'] is not None else None, suffix='%')} | "
            f"{row['turn_range']} | {row['dd_range']} | {row['ic_range']} | "
            f"{cell(row['rho'], digits=3)} | {row['nearest']} | {note} |"
        )

    lines += ["", "## 与基线的三处直接对照", "",
              f"1. **头部差距**：基线 {base_top['best_member']} {cell(base_hi, suffix='%')} 对"
              f"新簇最高 {cell(new_best['net'] * 100 if new_best['net'] is not None else None, suffix='%')}"
              f"（{new_best['cluster']}），差 {cell(base_hi - (new_best['net'] * 100 if new_best['net'] is not None else 0), suffix='pp')}。"
              "候选的价值不在单点更高，而在提供 B01 之外的独立信息。",
              f"2. **中段厚度**：基线里除 B01/B06/N34 之外的 {len(tail)} 个簇上限不到 "
              f"{cell(mid_hi, suffix='%')}，且 N 系几乎全为负；新簇里净超额为正的有 {len(positive_new)} 条、"
              f"达到 {cell(mid_hi, suffix='%')} 的有 {len(above_mid)} 条，中段明显更厚。",
              f"3. **独立性**：新簇 {len(independent)} 条与已知簇 abs(rho) < 0.60，"
              f"其中 {sum(1 for r in independent if (r['net'] or -9) > 0.10)} 条净超额 >= 10%，"
              "是真正可能带来增量的一批。",
              "",
              "## 风险与下一步",
              "",
              "- 本机复算与 09-24 远程运行不是同一环境（净超额相关性 0.975），短名单排序在 1pp 量级上可能变化；"
              "正式结论必须用平台回测确认。",
              "- 短名单里与已知簇相关 0.75~0.80 的条目属于边界簇，入池前应先做簇内信号对照，避免重复计数。",
              "- 下一步（需用户批准）：从短名单里挑 <=12 条提交平台单轮回测（平台口径、同一 5 年窗口），"
              "平台净超额与本地差异 >5pp 的按约定写入 failure registry。",
              ""]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"baseline clusters={len(baseline)} new clusters={len(new)} shortlist={len(shortlist)}")
    print("tier counts:", {code: len(rows) for code, rows in assigned.items()})
    print("wrote", REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())