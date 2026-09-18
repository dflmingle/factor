#!/usr/bin/env python3
"""Compare canonical five-year and recent local results for positive factors."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FULL = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports"
    / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_RECENT = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/positive-factor-recent-20260918"
    / "positive_factor_recent_local_compare.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/positive-factor-window-comparison-20260918"


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def percent(value: Any) -> float | None:
    value = number(value)
    return None if value is None else value * 100.0


def delta(recent: Any, full: Any) -> float | None:
    recent = number(recent)
    full = number(full)
    return None if recent is None or full is None else recent - full


def display(value: Any, digits: int = 2, suffix: str = "%") -> str:
    value = number(value)
    return "n/a" if value is None else f"{value:.{digits}f}{suffix}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_rows(full_payload: dict[str, Any], recent_payload: dict[str, Any]) -> list[dict[str, Any]]:
    full_by_id = {
        str(row["id"]): row
        for row in full_payload.get("results", [])
        if number(row.get("platform_net_excess_pct")) is not None
        and number(row.get("platform_net_excess_pct")) > 0.0
    }
    recent_items = recent_payload.get("results", []) + recent_payload.get("unsupported", [])
    recent_by_id = {str(row["id"]): row for row in recent_items}

    rows: list[dict[str, Any]] = []
    for record_id in sorted(set(full_by_id) | set(recent_by_id)):
        full = full_by_id.get(record_id, {})
        recent = recent_by_id.get(record_id, {})
        full_local_net = percent(full.get("local_net_excess"))
        recent_local_net = number(recent.get("recent_net_excess_pct"))
        full_local_gross = percent(full.get("local_gross_excess"))
        recent_local_gross = number(recent.get("recent_gross_excess_pct"))
        full_turnover = percent(full.get("local_turnover"))
        recent_turnover = number(recent.get("recent_turnover_pct"))
        full_rank_ic = number(full.get("local_rank_ic"))
        recent_rank_ic = number(recent.get("recent_rank_ic"))
        rows.append(
            {
                "id": record_id,
                "name": recent.get("name") or full.get("name"),
                "handler": recent.get("handler") or full.get("handler"),
                "cycle": recent.get("cycle") or full.get("cycle"),
                "platform_net_excess_pct": number(
                    recent.get("platform_net_excess_pct")
                    if recent.get("platform_net_excess_pct") is not None
                    else full.get("platform_net_excess_pct")
                ),
                "five_year_local_net_pct": full_local_net,
                "recent_local_net_pct": recent_local_net,
                "recent_minus_five_year_net_pp": delta(recent_local_net, full_local_net),
                "five_year_local_gross_pct": full_local_gross,
                "recent_local_gross_pct": recent_local_gross,
                "five_year_turnover_pct": full_turnover,
                "recent_turnover_pct": recent_turnover,
                "five_year_rank_ic": full_rank_ic,
                "recent_rank_ic": recent_rank_ic,
                "recent_periods": recent.get("recent_periods"),
                "five_year_alignment_quality": full.get("alignment_quality"),
                "five_year_local_status": "available" if full else "missing",
                "recent_local_status": (
                    "available"
                    if recent_local_net is not None
                    else ("no_recent_window" if recent else "missing")
                ),
                "recent_reason": recent.get("reason"),
            }
        )
    return rows


def write_outputs(output: Path, full_path: Path, recent_path: Path) -> None:
    json_path = output.with_suffix(".json")
    csv_path = output.with_suffix(".csv")
    md_path = output.with_suffix(".md")
    existing = [path for path in [json_path, csv_path, md_path] if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(map(str, existing)))

    full_payload = load_json(full_path)
    recent_payload = load_json(recent_path)
    rows = build_rows(full_payload, recent_payload)
    rows.sort(
        key=lambda row: (
            row["recent_local_net_pct"] is None,
            -(row["recent_local_net_pct"] or 0.0),
            str(row["name"]),
        )
    )

    settings = {
        "alignment_rule_version": recent_payload.get("settings", {}).get("alignment_rule_version"),
        "five_year_report": str(full_path),
        "recent_report": str(recent_path),
        "five_year_window": "2021-09-07 to 2026-09-07",
        "recent_window": "2026-01-01 to 2026-09-07 (usable signal dates end 2026-08-27)",
        "five_year_local_net_unit": "percentage points",
        "recent_local_net_unit": "percentage points",
        "platform_positive_records": len(rows),
        "five_year_local_available": sum(row["five_year_local_status"] == "available" for row in rows),
        "recent_local_available": sum(row["recent_local_status"] == "available" for row in rows),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps({"settings": settings, "results": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    fields = list(rows[0]) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Positive-factor local window comparison",
        "",
        "All rows are saved platform records with full-window platform net excess greater than zero.",
        "The five-year and recent columns are local arithmetic annualized diagnostics under the same alignment contract.",
        "The recent window is short and must not replace the formal five-year result.",
        "",
        f"- five-year window: `{settings['five_year_window']}`",
        f"- recent window: `{settings['recent_window']}`",
        f"- platform-positive records: `{settings['platform_positive_records']}`",
        f"- five-year local values available: `{settings['five_year_local_available']}`",
        f"- recent local values available: `{settings['recent_local_available']}`",
        "",
        "## Comparison",
        "",
        "`change` is recent local net excess minus five-year local net excess, in percentage points.",
        "",
        "| name | handler | cycle | platform net | five-year local net | recent local net | change | five-year turnover | recent turnover | five-year RankIC | recent RankIC | recent periods | full quality | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["name"]),
                    str(row["handler"] or "n/a"),
                    str(row["cycle"] or "n/a"),
                    display(row["platform_net_excess_pct"]),
                    display(row["five_year_local_net_pct"]),
                    display(row["recent_local_net_pct"]),
                    display(row["recent_minus_five_year_net_pp"]),
                    display(row["five_year_turnover_pct"]),
                    display(row["recent_turnover_pct"]),
                    display(row["five_year_rank_ic"], 4, ""),
                    display(row["recent_rank_ic"], 4, ""),
                    str(row["recent_periods"] or "n/a"),
                    str(row["five_year_alignment_quality"] or "n/a"),
                    f"{row['five_year_local_status']}/{row['recent_local_status']}",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Missing recent values",
            "",
            "| name | platform net | reason |",
            "|---|---:|---|",
        ]
    )
    for row in rows:
        if row["recent_local_status"] == "available":
            continue
        lines.append(
            f"| {row['name']} | {display(row['platform_net_excess_pct'])} | {row.get('recent_reason') or 'no recent local value'} |"
        )
    lines.extend(
        [
            "",
            "## Reading notes",
            "",
            "- `platform net` is the saved platform full-window screening value, not a 2026 recent platform result.",
            "- Five-day and ten-day records remain separate; rows with the same factor name but different cycles are not merged.",
            "- Proxy and alignment quality are inherited from the canonical five-year report. A strong recent number does not repair a five-year `field_or_path_mismatch`.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--five-year", type=Path, default=DEFAULT_FULL)
    parser.add_argument("--recent", type=Path, default=DEFAULT_RECENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_outputs(args.output, args.five_year, args.recent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
