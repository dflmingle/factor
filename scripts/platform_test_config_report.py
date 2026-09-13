#!/usr/bin/env python3
"""Build an offline index of saved PandaAI test configurations.

The registry is the source of platform parameters.  This command only reads
the local registry, candidate state files, and saved report CSVs; it never
contacts PandaAI and never creates or runs a factor.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "pandaai-workflow-registry.json"
OUTPUT_JSON = PROJECT_ROOT / "pandaai-platform-test-configs.json"
OUTPUT_MD = PROJECT_ROOT / "pandaai-platform-test-configs.md"


CONFIG_FIELDS = (
    "factor_id",
    "workflow_name",
    "run_id",
    "mode",
    "market",
    "stock_pool",
    "start_date",
    "end_date",
    "adjustment_cycle",
    "group_number",
    "factor_direction",
)


def text(value: Any) -> str:
    return "" if value is None else str(value)


def escape(value: Any) -> str:
    return text(value).replace("|", "\\|").replace("\n", " ")


def load_manifests() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path in sorted(PROJECT_ROOT.glob("*.txt")):
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("~")]
            if len(parts) < 3 or parts[-1] not in {"0", "1"}:
                continue
            result.setdefault(
                parts[0],
                {
                    "manifest": path.name,
                    "formula": " ~ ".join(parts[1:-1]),
                    "direction": parts[-1],
                },
            )
    return result


def workflow_config(workflow: dict[str, Any]) -> dict[str, Any]:
    info = workflow.get("factor_info") or {}
    return {
        "factor_id": workflow.get("_id"),
        "workflow_name": workflow.get("name"),
        "run_id": workflow.get("last_run_id"),
        "mode": info.get("mode"),
        "market": info.get("market"),
        "stock_pool": info.get("stock_pool"),
        "start_date": info.get("start_date"),
        "end_date": info.get("end_date"),
        "adjustment_cycle": info.get("adjustment_cycle"),
        "group_number": info.get("group_number"),
        "factor_direction": info.get("factor_direction"),
    }


def load_report_rows(
    manifests: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(PROJECT_ROOT.glob("*.report.csv")):
        try:
            source_rows = csv.DictReader(path.open(encoding="utf-8-sig", newline=""))
            for source in source_rows:
                if source.get("status") != "completed":
                    continue
                run_id = source.get("run_id") or ""
                factor_id = source.get("factor_id") or ""
                raw_result = (source.get("raw_result") or "").replace("\\", "/")
                platform_net = source.get("net_excess_pct")
                if not platform_net:
                    continue
                try:
                    net_excess = float(platform_net)
                except ValueError:
                    continue
                name = source.get("name") or ""
                item: dict[str, Any] = {
                    "report": path.name,
                    "name": name,
                    "factor_id_from_report": factor_id,
                    "run_id": run_id,
                    "raw_result": raw_result,
                    "direction_from_report": source.get("direction"),
                    "platform_rank_ic": source.get("rank_ic"),
                    "platform_gross_excess_pct": source.get("long_excess_pct"),
                    "platform_net_excess_pct": net_excess,
                    "platform_turnover_pct": source.get("turnover_pct"),
                    "formula": manifests.get(name, {}).get("formula"),
                    "manifest": manifests.get(name, {}).get("manifest"),
                }
                rows.append(item)
        except OSError:
            continue
    return rows


def build_payload(registry: dict[str, Any]) -> dict[str, Any]:
    manifests = load_manifests()
    workflows = registry.get("workflows", [])
    by_factor: dict[str, dict[str, Any]] = {}
    by_run: dict[str, dict[str, Any]] = {}
    configs: list[dict[str, Any]] = []

    for workflow in workflows:
        config = workflow_config(workflow)
        config["local_runs"] = []
        configs.append(config)
        factor_id = text(config.get("factor_id"))
        if factor_id:
            by_factor[factor_id] = config
        for entry in (workflow.get("local") or {}).get("entries", []):
            local = {
                "state_file": entry.get("state_file"),
                "candidate_name": entry.get("candidate_name"),
                "factor_id": entry.get("factor_id"),
                "run_id": entry.get("run_id"),
                "raw_result": entry.get("raw_result"),
            }
            local["formula"] = (entry.get("manifest_metadata") or {}).get("formula")
            config["local_runs"].append(local)
            if local["run_id"]:
                by_run[text(local["run_id"])] = config

    positive_results = []
    for row in load_report_rows(manifests):
        if row["platform_net_excess_pct"] <= 0:
            continue
        config = by_run.get(text(row["run_id"]))
        binding = "run_id" if config else ""
        if config is None:
            config = by_factor.get(text(row["factor_id_from_report"]))
            binding = "factor_id" if config else "historical_not_in_registry"
        result = dict(row)
        result["config_binding"] = binding
        result["config"] = {
            key: config.get(key) for key in CONFIG_FIELDS
        } if config else None
        positive_results.append(result)

    pool_counts = Counter(
        text(config.get("stock_pool")) or "<empty>" for config in configs
    )
    matched = sum(item["config_binding"] in {"run_id", "factor_id"} for item in positive_results)
    payload = {
        "schema_version": 1,
        "generated_at": registry.get("synced_at"),
        "source_registry": str(REGISTRY_PATH.name),
        "summary": {
            "platform_workflows": len(configs),
            "pool_counts": dict(pool_counts),
            "positive_saved_results": len(positive_results),
            "positive_results_with_config": matched,
            "positive_results_without_current_config": len(positive_results) - matched,
        },
        "positive_results": sorted(
            positive_results,
            key=lambda item: item["platform_net_excess_pct"],
            reverse=True,
        ),
        "workflows": configs,
    }
    return payload


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PandaAI Platform Test Configurations",
        "",
        f"Registry snapshot: `{payload.get('generated_at')}`. This file is built from the local registry and saved report files; it does not call PandaAI.",
        "",
        "## Snapshot",
        "",
        f"- current platform workflows: `{summary['platform_workflows']}`",
        f"- saved positive results: `{summary['positive_saved_results']}`",
        f"- positive results bound to a current config: `{summary['positive_results_with_config']}`",
        f"- positive results without a current config: `{summary['positive_results_without_current_config']}`",
        "",
        "| stock pool value from factor_info | workflow count |",
        "|---|---:|",
    ]
    for pool, count in sorted(summary["pool_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {escape(pool)} | {count} |")
    lines.extend(
        [
            "",
            "## Saved Positive Results",
            "",
            "The configuration columns below are copied from `factor_info`; the result columns are copied from the saved local report CSVs.",
            "",
            "| result | factor_id | run_id | pool | dates | cycle | groups | direction | net excess | binding |",
            "|---|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for item in payload["positive_results"]:
        config = item.get("config") or {}
        dates = f"{text(config.get('start_date'))}..{text(config.get('end_date'))}"
        lines.append(
            "| "
            + " | ".join(
                escape(value)
                for value in (
                    item.get("name"),
                    config.get("factor_id") or item.get("factor_id_from_report"),
                    item.get("run_id"),
                    config.get("stock_pool") if config else "<not in registry>",
                    dates if config else "",
                    config.get("adjustment_cycle") if config else "",
                    config.get("group_number") if config else "",
                    config.get("factor_direction") if config else item.get("direction_from_report"),
                    f"{item['platform_net_excess_pct']:.2f}%",
                    item.get("config_binding"),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Current Workflow Index",
            "",
            "| workflow | factor_id | last run_id | pool | market | dates | cycle | groups | direction | local runs |",
            "|---|---|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for config in payload["workflows"]:
        lines.append(
            "| "
            + " | ".join(
                escape(value)
                for value in (
                    config.get("workflow_name"),
                    config.get("factor_id"),
                    config.get("run_id"),
                    config.get("stock_pool"),
                    config.get("market"),
                    f"{text(config.get('start_date'))}..{text(config.get('end_date'))}",
                    config.get("adjustment_cycle"),
                    config.get("group_number"),
                    config.get("factor_direction"),
                    len(config.get("local_runs", [])),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUTPUT_MD.write_text(build_markdown(payload), encoding="utf-8")


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload = build_payload(registry)
    write_outputs(payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"wrote {OUTPUT_JSON.name}")
    print(f"wrote {OUTPUT_MD.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
