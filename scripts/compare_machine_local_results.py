#!/usr/bin/env python3
"""Compare two local factor result catalogs without rerunning any factor."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from machine_profile import MACHINE_LABELS


METRIC_FIELDS = (
    "local_net_excess",
    "local_gross_excess",
    "local_turnover",
    "local_rank_ic",
    "local_ic_mean",
    "periods",
)
PERCENT_FIELDS = frozenset(
    {"local_net_excess", "local_gross_excess", "local_turnover"}
)
IDENTITY_FIELDS = ("platform_factor_id", "platform_run_id", "handler", "cycle")
VALUE_TOLERANCE = 1e-12


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected an object at the top level: {path}")
    return payload


def index_records(payload: dict[str, Any], path: Path) -> dict[str, dict[str, Any]]:
    records = list(payload.get("results", [])) + list(payload.get("unsupported", []))
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = str(record.get("id", ""))
        if not record_id:
            raise ValueError(f"Record without id in {path}")
        if record_id in indexed:
            raise ValueError(f"Duplicate record id {record_id!r} in {path}")
        indexed[record_id] = record
    return indexed


def compare_value(old: Any, new: Any) -> dict[str, Any]:
    old_number = finite_number(old)
    new_number = finite_number(new)
    if old_number is None or new_number is None:
        equal = old is None and new is None
        return {"old": old, "new": new, "delta": None, "equal": equal}
    difference = new_number - old_number
    return {
        "old": old_number,
        "new": new_number,
        "delta": difference,
        "equal": abs(difference) <= VALUE_TOLERANCE,
    }


def compare_identity(old: dict[str, Any], new: dict[str, Any]) -> dict[str, bool]:
    return {
        field: old.get(field) == new.get(field) for field in IDENTITY_FIELDS
    }


def machine_metadata(
    payload: dict[str, Any],
    profile_override: str | None,
    label_override: str | None,
) -> dict[str, str]:
    settings = payload.get("settings", {})
    saved_profile = settings.get("machine_profile")
    saved_label = settings.get("machine_label")
    profile = profile_override or saved_profile or "unlabeled"
    label = label_override or saved_label or MACHINE_LABELS.get(str(profile), "未记录")
    return {"machine_profile": str(profile), "machine_label": str(label)}


def build_rows(
    old_payload: dict[str, Any],
    new_payload: dict[str, Any],
    old_path: Path,
    new_path: Path,
) -> list[dict[str, Any]]:
    old_records = index_records(old_payload, old_path)
    new_records = index_records(new_payload, new_path)
    ordered_ids = [str(record["id"]) for record in new_payload.get("results", [])]
    ordered_ids += [
        str(record["id"])
        for record in new_payload.get("unsupported", [])
        if str(record["id"]) not in ordered_ids
    ]
    ordered_ids += sorted(set(old_records) - set(ordered_ids))

    rows: list[dict[str, Any]] = []
    for record_id in ordered_ids:
        old = old_records.get(record_id)
        new = new_records.get(record_id)
        if old is None or new is None:
            rows.append(
                {
                    "id": record_id,
                    "name": (new or old).get("name"),
                    "handler": (new or old).get("handler"),
                    "status": "missing_old" if old is None else "missing_new",
                    "identity": {},
                    "metrics": {
                        field: compare_value(
                            old.get(field) if old else None,
                            new.get(field) if new else None,
                        )
                        for field in METRIC_FIELDS
                    },
                }
            )
            continue

        identity = compare_identity(old, new)
        metrics = {
            field: compare_value(old.get(field), new.get(field))
            for field in METRIC_FIELDS
        }
        all_equal = all(item["equal"] for item in metrics.values())
        identity_equal = all(identity.values())
        rows.append(
            {
                "id": record_id,
                "name": new.get("name") or old.get("name"),
                "handler": new.get("handler") or old.get("handler"),
                "status": (
                    "same_within_tolerance"
                    if all_equal and identity_equal
                    else "changed"
                ),
                "identity": identity,
                "metrics": metrics,
            }
        )
    return rows


def field_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [row["metrics"][field] for row in rows]
    comparable = [item for item in values if item["delta"] is not None]
    missing = len(values) - len(comparable)
    absolute_deltas = [abs(float(item["delta"])) for item in comparable]
    return {
        "records": len(values),
        "comparable": len(comparable),
        "equal_within_tolerance": sum(item["equal"] for item in comparable),
        "changed": sum(not item["equal"] for item in comparable),
        "missing_or_non_numeric": missing,
        "max_abs_delta": max(absolute_deltas) if absolute_deltas else None,
        "mean_abs_delta": (
            sum(absolute_deltas) / len(absolute_deltas)
            if absolute_deltas
            else None
        ),
    }


def make_payload(
    old_payload: dict[str, Any],
    new_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    old_path: Path,
    new_path: Path,
    old_machine_profile: str | None = None,
    old_machine_label: str | None = None,
    new_machine_profile: str | None = None,
    new_machine_label: str | None = None,
) -> dict[str, Any]:
    old_machine = machine_metadata(old_payload, old_machine_profile, old_machine_label)
    new_machine = machine_metadata(new_payload, new_machine_profile, new_machine_label)
    identity_mismatches = [
        {
            "id": row["id"],
            "name": row["name"],
            "fields": [
                field for field, equal in row["identity"].items() if not equal
            ],
        }
        for row in rows
        if row["status"] == "changed" and row["identity"]
        and not all(row["identity"].values())
    ]
    return {
        "settings": {
            "old_report": str(old_path),
            "new_report": str(new_path),
            "old_machine_profile": old_machine["machine_profile"],
            "old_machine_label": old_machine["machine_label"],
            "new_machine_profile": new_machine["machine_profile"],
            "new_machine_label": new_machine["machine_label"],
            "old_alignment_rule_version": old_payload.get("settings", {}).get(
                "alignment_rule_version"
            ),
            "new_alignment_rule_version": new_payload.get("settings", {}).get(
                "alignment_rule_version"
            ),
            "metric_fields": list(METRIC_FIELDS),
            "percentage_fields": sorted(PERCENT_FIELDS),
            "numeric_tolerance": VALUE_TOLERANCE,
            "comparison_definition": (
                "same_within_tolerance requires equal factor identity and all six "
                "local metrics within the numeric tolerance"
            ),
            "old_results": len(old_payload.get("results", [])),
            "new_results": len(new_payload.get("results", [])),
            "old_unsupported": len(old_payload.get("unsupported", [])),
            "new_unsupported": len(new_payload.get("unsupported", [])),
            "same_within_tolerance": sum(
                row["status"] == "same_within_tolerance" for row in rows
            ),
            "changed": sum(row["status"] == "changed" for row in rows),
            "missing_old": sum(row["status"] == "missing_old" for row in rows),
            "missing_new": sum(row["status"] == "missing_new" for row in rows),
            "identity_mismatches": identity_mismatches,
        },
        "field_summaries": {
            field: field_summary(rows, field) for field in METRIC_FIELDS
        },
        "results": rows,
    }


def format_value(field: str, value: Any) -> str:
    if value is None:
        return "n/a"
    number = finite_number(value)
    if number is None:
        return str(value)
    if field in PERCENT_FIELDS:
        return f"{number * 100.0:.6f}%"
    if field == "periods":
        return f"{number:.0f}"
    return f"{number:.10f}"


def format_delta(field: str, value: Any) -> str:
    if value is None:
        return "n/a"
    number = finite_number(value)
    if number is None:
        return str(value)
    if field in PERCENT_FIELDS:
        return f"{number * 100.0:+.6f}pp"
    if field == "periods":
        return f"{number:+.0f}"
    return f"{number:+.10f}"


def csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        flat: dict[str, Any] = {
            "id": row["id"],
            "name": row.get("name"),
            "handler": row.get("handler"),
            "status": row["status"],
        }
        for field, comparison in row["metrics"].items():
            flat[f"old_{field}"] = comparison["old"]
            flat[f"new_{field}"] = comparison["new"]
            flat[f"delta_{field}"] = comparison["delta"]
        for field, equal in row["identity"].items():
            flat[f"same_{field}"] = equal
        output.append(flat)
    return output


def write_outputs(output_prefix: Path, payload: dict[str, Any]) -> None:
    paths = {
        "json": output_prefix.with_suffix(".json"),
        "csv": output_prefix.with_suffix(".csv"),
        "md": output_prefix.with_suffix(".md"),
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(map(str, existing)))
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    flat_rows = csv_rows(payload["results"])
    fieldnames = list(flat_rows[0]) if flat_rows else ["id", "status"]
    with paths["csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)

    settings = payload["settings"]
    lines = [
        "# Machine-to-machine local factor comparison",
        "",
        "This report compares the local metrics from two completed catalogs. It does not rerun factors and does not compare either local result with the platform headline.",
        "",
        f"- old catalog: `{settings['old_report']}`",
        f"- new catalog: `{settings['new_report']}`",
        f"- old machine: `{settings['old_machine_profile']}` ({settings['old_machine_label']})",
        f"- new machine: `{settings['new_machine_profile']}` ({settings['new_machine_label']})",
        f"- machine direction: `{settings['old_machine_label']} -> {settings['new_machine_label']}`",
        f"- old rule version: `{settings['old_alignment_rule_version'] or 'not recorded'}`",
        f"- new rule version: `{settings['new_alignment_rule_version'] or 'not recorded'}`",
        f"- numeric tolerance: `{settings['numeric_tolerance']}`",
        f"- same within tolerance: `{settings['same_within_tolerance']}`",
        f"- changed: `{settings['changed']}`",
        f"- missing from old: `{settings['missing_old']}`",
        f"- missing from new: `{settings['missing_new']}`",
        "",
        "A percentage metric is displayed as a percent; its delta is in percentage points. Rank IC and IC mean deltas are raw decimal differences. `periods` is the number of evaluation dates.",
        "",
        "## Field Summary",
        "",
        "| field | records | comparable | equal | changed | missing/non-numeric | max absolute delta | mean absolute delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for field in METRIC_FIELDS:
        summary = payload["field_summaries"][field]
        unit = "pp" if field in PERCENT_FIELDS else ""
        max_delta = summary["max_abs_delta"]
        mean_delta = summary["mean_abs_delta"]
        if max_delta is not None and field in PERCENT_FIELDS:
            max_text = f"{max_delta * 100.0:.10f}pp"
            mean_text = f"{mean_delta * 100.0:.10f}pp"
        elif max_delta is not None:
            max_text = f"{max_delta:.10f}{unit}"
            mean_text = f"{mean_delta:.10f}{unit}"
        else:
            max_text = mean_text = "n/a"
        lines.append(
            f"| {field} | {summary['records']} | {summary['comparable']} | {summary['equal_within_tolerance']} | {summary['changed']} | {summary['missing_or_non_numeric']} | {max_text} | {mean_text} |"
        )

    lines.extend(
        [
            "",
            "## All Factors",
            "",
            "Each row is keyed by the saved report record ID. `same_within_tolerance` means all six requested local metrics and the saved factor identity match.",
            "",
            "| name | handler | status | net old | net new | net delta | gross old | gross new | gross delta | turnover old | turnover new | turnover delta | RankIC delta | IC mean delta | periods old | periods new | periods delta |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["results"]:
        metrics = row["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("name") or row["id"]).replace("|", "\\|"),
                    str(row.get("handler") or "n/a"),
                    row["status"],
                    format_value("local_net_excess", metrics["local_net_excess"]["old"]),
                    format_value("local_net_excess", metrics["local_net_excess"]["new"]),
                    format_delta("local_net_excess", metrics["local_net_excess"]["delta"]),
                    format_value("local_gross_excess", metrics["local_gross_excess"]["old"]),
                    format_value("local_gross_excess", metrics["local_gross_excess"]["new"]),
                    format_delta("local_gross_excess", metrics["local_gross_excess"]["delta"]),
                    format_value("local_turnover", metrics["local_turnover"]["old"]),
                    format_value("local_turnover", metrics["local_turnover"]["new"]),
                    format_delta("local_turnover", metrics["local_turnover"]["delta"]),
                    format_delta("local_rank_ic", metrics["local_rank_ic"]["delta"]),
                    format_delta("local_ic_mean", metrics["local_ic_mean"]["delta"]),
                    format_value("periods", metrics["periods"]["old"]),
                    format_value("periods", metrics["periods"]["new"]),
                    format_delta("periods", metrics["periods"]["delta"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This is the requested local-vs-local reproducibility check after refreshing the Tushare cache.",
            "- The platform comparison quality labels (`aligned` and `field_or_path_mismatch`) are intentionally not used as machine-to-machine differences.",
            "- A nonzero delta means the two saved local catalogs did not produce the same metric for that record; inspect the JSON/CSV row and data-cache metadata before accepting it as a data-source difference.",
        ]
    )
    paths["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    for path in paths.values():
        print(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--old-machine-profile")
    parser.add_argument("--old-machine-label")
    parser.add_argument("--new-machine-profile")
    parser.add_argument("--new-machine-label")
    args = parser.parse_args()
    old_payload = load_payload(args.old)
    new_payload = load_payload(args.new)
    rows = build_rows(old_payload, new_payload, args.old, args.new)
    payload = make_payload(
        old_payload,
        new_payload,
        rows,
        args.old,
        args.new,
        args.old_machine_profile,
        args.old_machine_label,
        args.new_machine_profile,
        args.new_machine_label,
    )
    write_outputs(args.output_prefix, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
