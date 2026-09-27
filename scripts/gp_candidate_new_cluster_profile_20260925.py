"""为 106 个候选新簇补齐 09-20 格式的簇画像（本地，零平台算力）。

输出：
- candidate-new-clusters-20260925/new_clusters_profile.md / .csv
- 追加到 candidate-new-clusters-20260925/summary.md 的八列表

列：簇 / 特色 / 成员数 / 代表因子（标签）/ 净超额范围 / 换手率范围 /
    成员最大回撤范围 / RankIC 范围

口径：
- 净超额、换手率、RankIC 来自 2026-09-24 GP 筛选运行
  （relaxed-gp-20260924/screen2/screened_candidates.csv，按公式 join），
  与 summary.md / new_clusters_with_links.csv 完全同源。
- 成员最大回撤来自本机复算 candidate_drawdown.csv 的 absolute_max_drawdown
  （多头持仓最大回撤，与 09-20 报告 long_max_drawdown 同义）。
- 特色由代表成员公式的叶子字段中文标签 + 顶层算子机制推导，只作簇标签。
"""
from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import pandaai_fields_local as pf  # noqa: E402

BASE = ROOT / "research_reports" / "platform_alignment"
OUT = BASE / "candidate-new-clusters-20260925"
CLUSTERS = OUT / "new_clusters_with_links.csv"
MATCHES = BASE / "cluster-overlap-20260924" / "candidate_matches.csv"
SCREENED = BASE / "relaxed-gp-20260924" / "screen2" / "screened_candidates.csv"
DRAWDOWN = OUT / "candidate_drawdown.csv"
SUMMARY = OUT / "summary.md"
PROFILE_MARKER = "## 簇画像（八列，2026-09-25 补齐）"

FIELD_NAMES = set(pf.PLATFORM_DECLARED_FIELD_NAMES)
RAW_LABELS = pf.PLATFORM_FIELD_LABELS

DTOKEN = re.compile(r"^(double|float|int|long|bool|boolean|string|str|nan|object)\s*$", re.I)
LABEL_LIMIT = 14
TRIM_TOKENS = (" |", " (", "（", ":", "：", "=", "，", ",", "<br>", " x ", ";", "；")
SHORTEN = (
    ("日成交金额的移动平均值", "日成交额均值"),
    ("日的成交金额移动平均值", "日成交额均值"),
    ("日成交金额", "日成交额"),
    ("的移动平均值", "均值"),
    ("的移动平均", "均值"),
)


def short_label(field: str) -> str:
    text = (RAW_LABELS.get(field) or field).strip()
    parts = [p.strip() for p in text.split("|")]
    parts = [p for p in parts if p and not DTOKEN.match(p)]
    text = parts[0] if parts else field
    for token in TRIM_TOKENS:
        if token in text:
            text = text.split(token)[0].strip()
    for src, dst in SHORTEN:
        text = text.replace(src, dst)
    text = text.strip(" -·")
    if not text:
        return field
    if len(text) > LABEL_LIMIT:
        text = text[:LABEL_LIMIT]
    return text


MECHANISM = {
    "Inv": "反向", "Neg": "反向", "Greater": "阈值门槛", "GreaterEqual": "阈值门槛",
    "Less": "阈值门槛", "LessEqual": "阈值门槛", "TsCorr": "时序相关", "TsCov": "时序协动",
    "TsStd": "波动", "TsVar": "方差", "TsSkew": "偏度", "TsKurt": "峰度",
    "TsMad": "绝对偏差", "TsMean": "均值", "TsMedian": "中位数", "TsSum": "累计",
    "TsProd": "累乘", "TsRank": "时序分位", "TsIr": "信息比", "TsMax": "区间高点",
    "TsMin": "区间低点", "TsMinMaxDiff": "区间振幅", "TsDelta": "变化量", "TsRef": "滞后",
    "TsDiv": "时序比值", "TsZScore": "时序标准化", "TsQuantile": "时序分位",
    "Log": "对数缩放", "Sqrt": "平方根缩放", "Pow": "幂次缩放", "Sign": "符号",
    "Abs": "绝对值", "Sub": "差值", "Div": "比率", "Mul": "乘积", "Add": "合成",
}


def formula_leaves(formula: str) -> list[str]:
    leaves: list[str] = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula):
        if token in FIELD_NAMES and token not in leaves:
            leaves.append(token)
    return leaves


def mechanism(formula: str) -> str:
    text = formula.strip()
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
    op = match.group(1) if match else ""
    tags = []
    if op in MECHANISM:
        tags.append(MECHANISM[op])
    by_amount = "amount" in text or "amt" in text
    by_assets = "bs_total_assets" in text
    if by_amount and by_assets:
        tags.append("除以成交额x总资产")
    elif by_amount:
        tags.append("成交额缩放")
    elif by_assets:
        tags.append("除以总资产")
    return " / ".join(dict.fromkeys(tags))


def feature(best_formula: str) -> str:
    labels = [short_label(name) for name in formula_leaves(best_formula)[:2]]
    parts = list(dict.fromkeys(labels))
    mech = mechanism(best_formula)
    if mech:
        parts.append(mech)
    return " · ".join(parts) if parts else "未识别"


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_range(values, percent: bool, digits: int = 2) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return "n/a"
    lo, hi = min(vals), max(vals)
    if percent:
        if abs(hi - lo) < 1e-9:
            return f"{lo * 100:.{digits}f}%"
        return f"{lo * 100:.{digits}f}%~{hi * 100:.{digits}f}%"
    if abs(hi - lo) < 1e-9:
        return f"{lo:.4f}"
    return f"{lo:.4f}~{hi:.4f}"


def build_records() -> list[dict]:
    clusters = load(CLUSTERS)
    matches = {row["candidate"]: row for row in load(MATCHES)}
    screened: dict[str, dict] = {}
    for row in load(SCREENED):
        screened.setdefault(row["formula"].strip(), row)
    drawdown = {row["candidate"]: row for row in load(DRAWDOWN)}

    records = []
    for cluster in clusters:
        members = [m.strip() for m in str(cluster["members"]).split("|") if m.strip()]
        nets, turnovers, ics, dds = [], [], [], []
        missing = []
        for member in members:
            match = matches.get(member)
            if match is None:
                missing.append(f"{member}:no-match")
                continue
            screen = screened.get(str(match["formula"]).strip())
            if screen is None:
                missing.append(f"{member}:no-screen")
            else:
                nets.append(to_float(screen.get("net")))
                turnovers.append(to_float(screen.get("turnover")))
                ics.append(to_float(screen.get("rank_ic")))
            dd = drawdown.get(member)
            if dd is None:
                missing.append(f"{member}:no-dd")
            else:
                dds.append(to_float(dd.get("absolute_max_drawdown")))
        best = str(cluster["best_member"]).strip()
        best_formula = str(matches.get(best, {}).get("formula", ""))
        best_screen = screened.get(best_formula.strip())
        best_net = to_float(cluster["best_net"])
        best_net_y2026 = to_float(cluster["best_net_y2026"])
        if best_screen is not None:
            if best_net is None:
                best_net = to_float(best_screen.get("net"))
            if best_net_y2026 is None:
                best_net_y2026 = to_float(best_screen.get("net_y2026"))
        records.append({
            "cluster": cluster["new_cluster"],
            "feature": feature(best_formula),
            "size": int(cluster["size"]),
            "best_member": best,
            "best_formula": best_formula,
            "net_range": fmt_range(nets, percent=True),
            "turnover_range": fmt_range(turnovers, percent=True),
            "drawdown_range": fmt_range(dds, percent=True),
            "rank_ic_range": fmt_range(ics, percent=False),
            "net_values": nets,
            "best_net": best_net,
            "best_net_y2026": best_net_y2026,
            "bands": cluster["bands"],
            "nearest_known_factor": cluster["nearest_known_factor"],
            "nearest_known_cluster": cluster["nearest_known_cluster"],
            "max_known_abs_rho": to_float(cluster["max_known_abs_rho"]),
            "high_correlation_clusters": cluster["high_correlation_clusters"],
            "members": " | ".join(members),
            "missing": ";".join(missing),
        })
    records.sort(key=lambda r: (-(r["best_net_y2026"] or -9), r["cluster"]))
    return records


def main_table(records) -> list[str]:
    lines = [
        "| 簇 | 特色 | 成员数 | 代表因子（标签） | 净超额范围 | 换手率范围 | 成员最大回撤范围 | RankIC 范围 |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in records:
        lines.append(
            f"| {row['cluster']} | {row['feature']} | {row['size']} | {row['best_member']} | "
            f"{row['net_range']} | {row['turnover_range']} | {row['drawdown_range']} | "
            f"{row['rank_ic_range']} |"
        )
    return lines


def main() -> int:
    records = build_records()
    table = main_table(records)

    fieldnames = ["cluster", "feature", "size", "best_member", "net_range",
                  "turnover_range", "drawdown_range", "rank_ic_range", "best_net",
                  "best_net_y2026", "bands", "nearest_known_cluster",
                  "nearest_known_factor", "max_known_abs_rho",
                  "high_correlation_clusters", "members", "best_formula", "missing"]
    with (OUT / "new_clusters_profile.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k) for k in fieldnames})

    multi = [r for r in records if r["size"] > 1]
    lines = [
        "# 候选新簇画像（2026-09-25 口径）",
        "",
        "本表把 `candidate-new-clusters-20260925` 的 106 个新簇按 2026-09-20 "
        "`cluster-profile-nearest-correlation-20260920.md` 的格式补齐八列。",
        "",
        "## 口径",
        "",
        "- 成簇：候选之间 `|rho| >= 0.80` 取连通分量；任一成员与已保存 B/N/复合簇成员 "
        "`|rho| >= 0.80` 的候选整条剔除；单成员连通分量也算独立新簇。",
        "- 成簇窗口：`20210907..20260907`；10 日调仓、10 组、0.30% 单边成本、全 A、qfq、`total_mv`。",
        "- 净超额、换手率、RankIC 来自 2026-09-24 GP 筛选运行 "
        "(`relaxed-gp-20260924/screen2/screened_candidates.csv`)，与 `summary.md`、"
        "`new_clusters_with_links.csv` 完全同源；表中是该簇全部成员的 min~max 范围。",
        "- 成员最大回撤来自本机复算 `candidate_drawdown.csv` 的 `absolute_max_drawdown`"
        "（多头持仓最大回撤，等价于 09-20 报告的 long_max_drawdown）。",
        "- 本机复算与 09-24 远程运行并非同一环境：换手相关性 0.994、净超额相关性 0.975、"
        "净超额平均差 -0.84pp（最大 7.7pp）。回撤列与前三列不是同一运行环境的产物，"
        "只作诊断；正式候选确认仍以平台回测为准。",
        "- 最大回撤列是“成员最大回撤范围”，不是簇内合成组合的回撤。",
        "- 特色由代表成员公式的叶子字段中文标签（平台字段目录）+ 顶层算子机制推导，只作簇标签。",
        "",
        "## 簇整体指标范围（按代表成员 2026 净超额排序）",
        "",
    ]
    lines += table

    lines += ["", f"## 多成员新簇明细（{len(multi)} 个）", ""]
    for row in sorted(multi, key=lambda r: (-r["size"], -((r["best_net_y2026"] or -9)))):
        lines.append(f"### {row['cluster']}（{row['size']} 条）—— {row['feature']}")
        lines.append("")
        lines.append(f"- 净超额范围 {row['net_range']}；换手率范围 {row['turnover_range']}；"
                     f"成员最大回撤范围 {row['drawdown_range']}；RankIC 范围 {row['rank_ic_range']}")
        net26 = f"{row['best_net_y2026']:+.4f}" if row["best_net_y2026"] is not None else "n/a"
        lines.append(f"- 代表因子（标签）：`{row['best_member']}`；档位 {row['bands']}；"
                     f"代表成员 2026 净超额 {net26}")
        if row["max_known_abs_rho"] is not None:
            lines.append(f"- 与已知簇最高 abs(rho) {row['max_known_abs_rho']:.3f}"
                         f"（{row['nearest_known_factor']} / {row['nearest_known_cluster']}）")
        else:
            lines.append("- 与已知簇关系：无 >=0.60 的高相关成员")
        if row["high_correlation_clusters"]:
            lines.append(f"- 高相关其它新簇：{row['high_correlation_clusters']}")
        lines.append(f"- 成员：{row['members']}")
        lines.append("")

    with (OUT / "new_clusters_profile.md").open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    summary = SUMMARY.read_text(encoding="utf-8")
    head = summary.split(PROFILE_MARKER)[0].rstrip()
    section = [
        "",
        PROFILE_MARKER,
        "",
        "八列口径与完整明细见 `new_clusters_profile.md`；本表与其同源同序。",
        "",
    ] + table + [""]
    SUMMARY.write_text(head + "\n" + "\n".join(section), encoding="utf-8")

    missing_any = [r for r in records if r["missing"]]
    print(f"clusters={len(records)} multi={len(multi)} single={len(records) - len(multi)}")
    print(f"clusters with missing fields: {len(missing_any)}")
    for row in missing_any[:10]:
        print("  ", row["cluster"], row["missing"])
    print("features sample:", " | ".join(r["feature"] for r in records[:5]))
    print("wrote", OUT / "new_clusters_profile.md")
    print("wrote", OUT / "new_clusters_profile.csv")
    print("updated", SUMMARY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())