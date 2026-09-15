#!/usr/bin/env python3
"""Persist high-correlation references in the local factor records.

The input correlation report is produced by the offline correlation workflow.
This command updates the target state/report and a small cumulative registry;
it never contacts PandaAI or starts a backtest.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORRELATION_REPORT = PROJECT_ROOT / (
    "research_reports/platform_alignment/"
    "target-vs-positive-factor-correlation-20260915.json"
)
DEFAULT_TARGET_REPORT = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.report.csv"
DEFAULT_TARGET_STATE = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.txt.state.json"
DEFAULT_TARGET_MARKDOWN = PROJECT_ROOT / "alphaprobe-net1-platform-20260914-candidates.report.md"
DEFAULT_REGISTRY = PROJECT_ROOT / "research_reports/platform_alignment/factor-correlation-registry.json"
DEFAULT_THRESHOLD = 0.60


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def project_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def target_record(
    report_path: Path,
    state_path: Path,
    correlation: dict[str, Any],
) -> dict[str, Any]:
    target = correlation["target"]
    with report_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    completed = [row for row in rows if row.get("status") == "completed"]
    if not completed:
        raise ValueError(f"No completed target row found in {report_path}")
    row = completed[0]
    performance = {
        "platform_rank_ic": number(row.get("rank_ic")),
        "platform_ic_mean": number(row.get("ic_mean")),
        "platform_ic_ir": number(row.get("ic_ir")),
        "platform_ic_p_value": number(row.get("ic_p_value")),
        "platform_monotonicity": number(row.get("monotonicity")),
        "platform_long_excess_pct": number(row.get("long_excess_pct")),
        "platform_turnover_pct": number(row.get("turnover_pct")),
        "platform_annual_cost_pct": number(row.get("annual_cost_pct")),
        "platform_net_excess_pct": number(row.get("net_excess_pct")),
        "platform_long_sharpe": number(row.get("long_sharpe")),
        "platform_long_max_drawdown_pct": number(row.get("long_max_drawdown_pct")),
        "platform_long_monthly_win_rate_pct": number(row.get("long_monthly_win_rate_pct")),
    }
    return {
        "record_id": f"{report_path.stem}:{row.get('name')}",
        "name": row.get("name"),
        "factor_id": row.get("factor_id"),
        "run_id": row.get("run_id"),
        "formula": target["formula"],
        "handler": target.get("handler"),
        "direction": row.get("direction"),
        "performance": performance,
        "source_report": project_path(report_path),
        "source_state": project_path(state_path),
    }


def existing_records(correlation: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = Path(correlation["source"]["positive_records"])
    source = load_json(source_path)
    by_id = {str(row.get("id")): row for row in source.get("results", [])}
    records: list[dict[str, Any]] = []
    for row in correlation.get("results", []):
        source_row = by_id.get(str(row.get("id")), {})
        performance = {
            key: source_row[key]
            for key in (
                "platform_net_excess_pct",
                "platform_rank_ic",
                "platform_ic_mean",
                "platform_turnover_pct",
                "platform_gross_excess_pct",
                "platform_annual_cost_pct",
                "local_net_excess",
                "local_gross_excess",
                "local_turnover",
                "local_rank_ic",
                "local_ic_mean",
            )
            if key in source_row
        }
        records.append(
            {
                "record_id": str(row["id"]),
                "name": row.get("name"),
                "factor_id": row.get("platform_factor_id"),
                "run_id": row.get("platform_run_id"),
                "formula": row.get("formula"),
                "handler": row.get("handler"),
                "direction": row.get("platform_direction"),
                "performance": performance,
                "source_record": project_path(source_path),
            }
        )
    return records


def peer(record: dict[str, Any], correlation: float) -> dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "name": record.get("name"),
        "factor_id": record.get("factor_id"),
        "run_id": record.get("run_id"),
        "formula": record.get("formula"),
        "handler": record.get("handler"),
        "platform_net_excess_pct": record.get("performance", {}).get("platform_net_excess_pct"),
        "correlation": float(correlation),
        "abs_correlation": abs(float(correlation)),
    }


def build_profiles(
    target: dict[str, Any],
    existing: list[dict[str, Any]],
    correlation: dict[str, Any],
    threshold: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_id = {str(row["record_id"]): row for row in existing}
    target_id = str(target["record_id"])
    target_high: list[dict[str, Any]] = []
    for row in correlation.get("results", []):
        value = number(row.get("correlation"))
        if value is None or abs(value) < threshold:
            continue
        existing_row = by_id[str(row["id"])]
        target_high.append(peer(existing_row, value))
    target_high.sort(key=lambda item: item["abs_correlation"], reverse=True)
    target_profile = {
        "method": correlation["settings"]["correlation_method"],
        "method_description": correlation["settings"]["correlation_description"],
        "window": f"{correlation['settings']['comparison_start']}..{correlation['settings']['comparison_end']}",
        "reference_set": "saved completed factors with platform net excess > 0",
        "reference_count": len(existing),
        "comparisons_available": len(correlation.get("results", [])),
        "high_correlation_threshold_abs": threshold,
        "highly_correlated_factors": target_high,
        "source_report": project_path(DEFAULT_CORRELATION_REPORT),
    }

    by_existing_id = {str(row["record_id"]): row for row in existing}
    profiles: list[dict[str, Any]] = []
    for row in correlation.get("results", []):
        value = number(row.get("correlation"))
        if value is None:
            continue
        existing_row = by_existing_id[str(row["id"])]
        high = [peer(target, value)] if abs(value) >= threshold else []
        profiles.append(
            {
                "record_id": existing_row["record_id"],
                "reference_set": "target factor F-NET01",
                "reference_count": 1,
                "comparisons_available": 1,
                "high_correlation_threshold_abs": threshold,
                "highly_correlated_factors": high,
                "source_report": project_path(DEFAULT_CORRELATION_REPORT),
            }
        )
    return target_profile, profiles


def update_registry(
    path: Path,
    target: dict[str, Any],
    existing: list[dict[str, Any]],
    target_profile: dict[str, Any],
    existing_profiles: list[dict[str, Any]],
    correlation: dict[str, Any],
    threshold: float,
) -> None:
    if path.exists():
        registry = load_json(path)
    else:
        registry = {"schema_version": 1, "records": []}
    old_records = {
        str(row.get("record_id")): row
        for row in registry.get("records", [])
        if isinstance(row, dict) and row.get("record_id")
    }
    target["correlation_profile"] = target_profile
    old_records[target["record_id"]] = target
    profile_by_id = {row["record_id"]: row for row in existing_profiles}
    for row in existing:
        row["correlation_profile"] = profile_by_id[row["record_id"]]
        old_records[row["record_id"]] = row
    registry.update(
        {
            "schema_version": 1,
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "correlation_method": correlation["settings"]["correlation_method"],
            "correlation_description": correlation["settings"]["correlation_description"],
            "high_correlation_threshold_abs": threshold,
            "alignment_rule_version": correlation["settings"]["alignment_rule_version"],
            "comparison_window": {
                "start": correlation["settings"]["comparison_start"],
                "end": correlation["settings"]["comparison_end"],
            },
            "records": sorted(old_records.values(), key=lambda row: str(row["record_id"])),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_target_state(
    path: Path,
    target_profile: dict[str, Any],
    registry_path: Path,
    correlation_path: Path,
) -> None:
    state = load_json(path)
    if len(state) != 1:
        raise ValueError(f"Expected one target entry in {path}")
    entry = next(iter(state.values()))
    entry["correlation_references"] = {
        "registry": project_path(registry_path),
        "correlation_report": project_path(correlation_path),
        "method": target_profile["method"],
        "window": target_profile["window"],
        "reference_set": target_profile["reference_set"],
        "reference_count": target_profile["reference_count"],
        "comparisons_available": target_profile["comparisons_available"],
        "high_correlation_threshold_abs": target_profile["high_correlation_threshold_abs"],
        "highly_correlated_factors": target_profile["highly_correlated_factors"],
    }
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def markdown_section(
    target_profile: dict[str, Any],
    correlation_path: Path,
    registry_path: Path,
) -> str:
    high = target_profile["highly_correlated_factors"]
    lines = [
        "## Correlation references",
        "",
        f"The factor was compared with `{target_profile['reference_count']}` saved factors whose platform net excess is positive. The fixed method is `{target_profile['method']}` over `{target_profile['window']}`. High correlation is recorded at `abs(rho) >= {target_profile['high_correlation_threshold_abs']:.2f}`.",
        "",
        "| Rank | Factor | Handler | Correlation | Platform net excess | Formula |",
        "|---:|---|---|---:|---:|---|",
    ]
    for index, row in enumerate(high, start=1):
        formula = str(row.get("formula") or "").replace("|", "\\|").replace("\n", " ")
        net = row.get("platform_net_excess_pct")
        net_text = "n/a" if net is None else f"{float(net):.2f}%"
        lines.append(
            f"| {index} | {row.get('name')} | `{row.get('handler')}` | {float(row['correlation']):+.6f} | {net_text} | `{formula}` |"
        )
    if not high:
        lines.append("| none | | | | | |")
    lines.extend(
        [
            "",
            f"Full pairwise results: `{project_path(correlation_path)}`. The cumulative per-factor record is `{project_path(registry_path)}`.",
        ]
    )
    return "\n".join(lines)


def update_target_markdown(
    path: Path,
    target_profile: dict[str, Any],
    correlation_path: Path,
    registry_path: Path,
) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "## Correlation references"
    head = text.split(marker, 1)[0].rstrip()
    path.write_text(
        head
        + "\n\n"
        + markdown_section(target_profile, correlation_path, registry_path)
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correlation-report", type=Path, default=DEFAULT_CORRELATION_REPORT)
    parser.add_argument("--target-report", type=Path, default=DEFAULT_TARGET_REPORT)
    parser.add_argument("--target-state", type=Path, default=DEFAULT_TARGET_STATE)
    parser.add_argument("--target-markdown", type=Path, default=DEFAULT_TARGET_MARKDOWN)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    if args.threshold < 0 or args.threshold > 1:
        raise SystemExit("--threshold must be between 0 and 1")

    correlation = load_json(args.correlation_report)
    target = target_record(args.target_report, args.target_state, correlation)
    existing = existing_records(correlation)
    target_profile, existing_profiles = build_profiles(
        target, existing, correlation, args.threshold
    )
    update_registry(
        args.registry,
        target,
        existing,
        target_profile,
        existing_profiles,
        correlation,
        args.threshold,
    )
    update_target_state(args.target_state, target_profile, args.registry, args.correlation_report)
    update_target_markdown(
        args.target_markdown,
        target_profile,
        args.correlation_report,
        args.registry,
    )
    print(
        f"registered={len(existing) + 1} high_for_target={len(target_profile['highly_correlated_factors'])} "
        f"threshold={args.threshold:.2f} registry={args.registry}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
