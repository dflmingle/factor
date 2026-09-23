"""Platform field coverage: which supported fields have we actually exercised?

Sources
* platform formula-mode base fields: `vendor/skill-pandaai-factor-online/references/fields.md`
* platform backtest-factor catalog: the same folder's per-table `fields-*.md`
* local reproducibility status per field: the AlphaPROBE `field_coverage.json`
* formulas we actually submitted: root `*-candidates.txt` batches
* formulas we evaluated locally: `factor_formula_registry.json` + the aligned compare

Output: a per-field checklist plus family-level summary.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "vendor/skill-pandaai-factor-online/references"
OUT = ROOT / "research_reports/platform_alignment/field-coverage-20260923"
COVERAGE_JSON = (
    ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare"
    / "ic_eff_w2_s41_20260923/field_coverage.json"
)
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_reference_fields() -> tuple[dict[str, dict], dict[str, dict]]:
    base: dict[str, dict] = {}
    catalog: dict[str, dict] = {}
    for path in sorted(REFS.glob("fields*.md")):
        text = path.read_text(encoding="utf-8")
        in_base = path.name == "fields.md"
        for line in text.splitlines():
            match = re.match(r"^\|\s*`([A-Za-z_][A-Za-z0-9_]*)`\s*\|(.*)\|\s*$", line)
            if not match:
                continue
            name = match.group(1).lower()
            rest = [cell.strip() for cell in match.group(2).split("|")]
            if in_base:
                base.setdefault(name, {"field": name, "label": rest[0] if rest else ""})
            else:
                ftype = rest[0] if rest else ""
                desc = rest[1] if len(rest) > 1 else ""
                catalog.setdefault(name, {"field": name, "type": ftype, "desc": desc, "file": path.name})
    return base, catalog


def platform_formula_fields() -> set[str]:
    fields: set[str] = set()
    for path in sorted(ROOT.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("~")]
            if len(parts) >= 2:
                fields.update(token.lower() for token in TOKEN.findall(parts[1]))
    return fields


def local_formula_fields() -> set[str]:
    fields: set[str] = set()
    registry = ROOT / "research_reports/platform_alignment/factor_formula_registry.json"
    if registry.exists():
        payload = json.loads(registry.read_text(encoding="utf-8"))
        for item in payload.get("formulas", []):
            text = json.dumps(item, ensure_ascii=False)
            fields.update(token.lower() for token in TOKEN.findall(text))
    compare = (
        ROOT
        / "quantlab/.quantlab/cache/research/cn_equity/reports"
        / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
        "turnoverdiag1_qualitygate3/all_factor_local_compare.json"
    )
    if compare.exists():
        payload = json.loads(compare.read_text(encoding="utf-8"))
        for row in payload.get("results", []):
            formula = str(row.get("formula") or "")
            fields.update(token.lower() for token in TOKEN.findall(formula))
    return fields


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    base, catalog = parse_reference_fields()
    coverage = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    status = {
        str(item["base_field"]).lower(): (item.get("status"), item.get("source") or "")
        for item in coverage["fields"]
        if item.get("status")
    }
    tested_platform = platform_formula_fields()
    tested_local = local_formula_fields()
    family_of = {}
    for name in base:
        family_of[name] = "formula-base"
    for name, item in catalog.items():
        family_of.setdefault(name, item["file"])

    def classify(name: str) -> tuple[str, str, str]:
        local_status, source = status.get(name, ("unknown", ""))
        return (
            "platform" if name in tested_platform else "",
            "local" if name in tested_local else "",
            local_status,
        )

    rows = []
    for name, item in sorted(base.items()):
        on_platform, on_local, local_status = classify(name)
        rows.append(
            dict(field=name, label=item.get("label", ""), family="fields.md base",
                 tested_platform=on_platform, tested_local=on_local,
                 local_status=local_status, in_catalog=int(name in catalog))
        )
    for name, item in sorted(catalog.items()):
        if name in base:
            continue
        on_platform, on_local, local_status = classify(name)
        rows.append(
            dict(field=name, label=item.get("desc", ""), family=item["file"],
                 tested_platform=on_platform, tested_local=on_local,
                 local_status=local_status, in_catalog=1)
        )
    import csv

    with (OUT / "field_checklist.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def summary(subset: list[dict]) -> dict:
        return dict(
            total=len(subset),
            platform=sum(1 for r in subset if r["tested_platform"]),
            local=sum(1 for r in subset if r["tested_local"]),
            untouched=sum(1 for r in subset if not r["tested_platform"] and not r["tested_local"]),
        )

    base_rows = [r for r in rows if r["family"] == "fields.md base"]
    catalog_rows = [r for r in rows if r["family"] != "fields.md base"]
    lines = [
        "# 平台字段覆盖盘点（2026-09-23）",
        "",
        f"- 公式模式基础字段（fields.md）：{len(base_rows)} 个",
        f"- 回测因子目录（14 张表）：{len(catalog_rows)} 个",
        f"- 本地可复现状态（AlphaPROBE field_coverage）："
        f"local_direct {coverage['status_counts']['local_direct']}、"
        f"local_proxy {coverage['status_counts']['local_proxy']}、"
        f"local_derived {coverage['status_counts']['local_derived']}",
        "",
        "## 公式模式基础字段覆盖",
        "",
        "| 口径 | 字段数 | 平台实测过 | 本地算过 | 完全没碰 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, subset in (("fields.md 全部", base_rows),):
        stats = summary(subset)
        lines.append(
            f"| {label} | {stats['total']} | {stats['platform']} | {stats['local']} | {stats['untouched']} |"
        )
    stats_catalog = summary(catalog_rows)
    lines.append(
        f"| 回测目录 | {stats_catalog['total']} | {stats_catalog['platform']} | "
        f"{stats_catalog['local']} | {stats_catalog['untouched']} |"
    )
    lines += ["", "## 公式模式字段里完全没碰过的（按家族）", ""]
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in base_rows:
        if not row["tested_platform"] and not row["tested_local"]:
            groups[row["local_status"]].append(row)
    for local_status, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"### 本地状态 `{local_status}` — {len(items)} 个")
        lines.append("")
        lines.append("| 字段 | 名称 |")
        lines.append("| --- | --- |")
        for item in items[:40]:
            lines.append(f"| `{item['field']}` | {item['label'][:48]} |")
        if len(items) > 40:
            lines.append(f"| … | 其余 {len(items) - 40} 个见 CSV |")
        lines.append("")
    lines += ["## 回测目录里完全没碰过的（按表）", ""]
    groups_catalog: dict[str, list[dict]] = defaultdict(list)
    for row in catalog_rows:
        if not row["tested_platform"] and not row["tested_local"]:
            groups_catalog[row["family"]].append(row)
    lines.append("| 表 | 完全没碰 |")
    lines.append("| --- | ---: |")
    for family, items in sorted(groups_catalog.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {family} | {len(items)} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:20]))
    print()
    print("checklist rows:", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
