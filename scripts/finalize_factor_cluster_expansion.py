#!/usr/bin/env python3
"""Finalize an expansion report from an already-computed pair matrix.

This is a read-only correlation post-processing step. It exists so a factor
whose local handler returned no finite values can be removed from the cluster
graph without rebuilding the long-window signal matrix.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import expand_factor_clusters as expansion  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_CORRELATION_DESCRIPTION,
    ALIGNMENT_CORRELATION_METHOD,
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE_LABEL,
)


DEFAULT_MATRIX = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "positive-factor-pair-correlation-20260917.json"
)
DEFAULT_PAIR_CSV = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "all-factor-cluster-expansion-20260919.pairs.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "all-factor-cluster-expansion-20260919"
)


def load_pair_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Pair matrix is empty: {path}")
    return rows


def coverage_by_factor(pair_rows: list[dict[str, Any]]) -> dict[str, int]:
    """Use jointly valid row counts to detect all-empty handlers."""
    coverage: dict[str, int] = defaultdict(int)
    for row in pair_rows:
        try:
            pair_rows_count = int(float(row.get("pair_rows") or 0))
        except (TypeError, ValueError):
            pair_rows_count = 0
        for side in ("a", "b"):
            factor_id = row.get(f"factor_{side}_id")
            if factor_id:
                coverage[str(factor_id)] = max(
                    coverage[str(factor_id)], pair_rows_count
                )
    return coverage


def restore_saved_base_pairs(
    pair_rows: list[dict[str, Any]],
    matrix_path: Path,
    base_records: list[dict[str, Any]],
) -> None:
    """Use the persisted matrix for relationships among the old base nodes.

    The expansion may run after a local cache or handler implementation has
    changed. New-to-base and new-to-new edges are still taken from the current
    expansion, but the original base graph remains the source of truth for the
    already-persisted B01-B12 clusters.
    """
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    old_pairs = {
        tuple(sorted((str(row["factor_a_id"]), str(row["factor_b_id"])))): row
        for row in matrix.get("pairs", [])
    }
    base_ids = {str(record.get("id")) for record in base_records}
    restored = 0
    for row in pair_rows:
        left = str(row.get("factor_a_id"))
        right = str(row.get("factor_b_id"))
        if left not in base_ids or right not in base_ids:
            continue
        old = old_pairs.get(tuple(sorted((left, right))))
        if old is None:
            continue
        for field in ("correlation", "abs_correlation", "high_correlation", "days"):
            if field in old:
                row[field] = old[field]
        restored += 1
    expected = len(base_ids) * (len(base_ids) - 1) // 2
    if restored != expected:
        raise ValueError(
            f"Restored {restored} saved base pairs, expected {expected}"
        )


def fmt_pct(value: Any) -> str:
    return "n/a" if value in (None, "") else f"{float(value):.2f}%"


def fmt_num(value: Any, digits: int = 4) -> str:
    return "n/a" if value in (None, "") else f"{float(value):.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--pair-csv", default=str(DEFAULT_PAIR_CSV))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--threshold", type=float, default=0.80)
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--start", default=ALIGNMENT_START)
    parser.add_argument("--end", default=ALIGNMENT_END)
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    pair_path = Path(args.pair_csv)
    output_prefix = Path(args.output_prefix)
    pair_rows = load_pair_rows(pair_path)
    base_records, remaining_records, unsupported, base_cluster_by_id, old_composites = (
        expansion.load_records_and_base(matrix_path)
    )
    restore_saved_base_pairs(pair_rows, matrix_path, base_records)
    coverage = coverage_by_factor(pair_rows)
    unusable_ids = {
        expansion.record_key(record)
        for record in remaining_records
        if not expansion.visible_composite(record)
        and coverage.get(expansion.record_key(record), 0) <= 0
    }
    assignments, clusters = expansion.build_cluster_assignments(
        base_records=base_records,
        remaining_records=remaining_records,
        base_cluster_by_id=base_cluster_by_id,
        pair_rows=pair_rows,
        threshold=args.threshold,
        unusable_ids=unusable_ids,
    )

    unresolved_rows = [
        {
            "factor_id": record.get("id"),
            "factor_name": record.get("name"),
            "report": record.get("report"),
            "handler": record.get("handler"),
            "formula": record.get("formula"),
            "platform_net_excess_pct": record.get("platform_net_excess_pct"),
            "status": "no_local_handler",
            "reason": record.get("reason"),
        }
        for record in unsupported
    ]
    for record in remaining_records:
        if expansion.record_key(record) not in unusable_ids:
            continue
        unresolved_rows.append(
            {
                "factor_id": record.get("id"),
                "factor_name": record.get("name"),
                "report": record.get("report"),
                "handler": record.get("handler"),
                "formula": record.get("formula"),
                "platform_net_excess_pct": record.get("platform_net_excess_pct"),
                "status": "local_signal_unavailable",
                "reason": "local handler returned no finite signal values in the formal window",
            }
        )
    unresolved_rows.sort(key=lambda row: (str(row["status"]), str(row["factor_name"])))

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    pairs_path = output_prefix.with_suffix(".pairs.csv")
    assignments_path = output_prefix.with_suffix(".assignments.csv")
    clusters_path = output_prefix.with_suffix(".clusters.csv")
    unresolved_path = output_prefix.with_suffix(".unresolved.csv")
    json_path = output_prefix.with_suffix(".json")
    markdown_path = output_prefix.with_suffix(".md")
    # Persist the merged matrix as well: old-base pairs are restored from the
    # saved matrix above, while all edges touching a new record come from the
    # expansion run.
    pd.DataFrame(pair_rows).to_csv(pairs_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(assignments).to_csv(assignments_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(clusters).to_csv(clusters_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(unresolved_rows).to_csv(unresolved_path, index=False, encoding="utf-8-sig")

    usable_new_single = sum(
        not expansion.visible_composite(record)
        and expansion.record_key(record) not in unusable_ids
        for record in remaining_records
    )
    composite_new = sum(expansion.visible_composite(record) for record in remaining_records)
    high_pair_count = sum(
        row.get("abs_correlation") not in (None, "")
        and float(row["abs_correlation"]) >= args.threshold
        for row in pair_rows
    )
    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "source_matrix": str(matrix_path),
        "source_pair_matrix": str(pair_path),
        "scope": "all saved completed platform records",
        "universe": ALIGNMENT_UNIVERSE_LABEL,
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": args.data_start,
        "comparison_start": args.start,
        "comparison_end": args.end,
        "correlation_method": ALIGNMENT_CORRELATION_METHOD,
        "correlation_description": ALIGNMENT_CORRELATION_DESCRIPTION,
        "threshold": args.threshold,
        "old_matrix_records": 65,
        "old_base_records": len(base_records),
        "old_composite_records": len(old_composites),
        "new_supported_records": len(remaining_records),
        "new_single_cluster_eligible_records": usable_new_single,
        "new_composite_records_not_clustered": composite_new,
        "no_local_handler_records": len(unsupported),
        "local_signal_unavailable_records": len(unusable_ids),
        "unresolved_records": len(unresolved_rows),
        "pair_count": len(pair_rows),
        "high_pair_count": high_pair_count,
        "cluster_count": len(clusters),
    }
    payload = {
        "settings": settings,
        "clusters": clusters,
        "assignments": assignments,
        "unresolved": unresolved_rows,
        "artifacts": {
            "pairs": str(pairs_path),
            "assignments": str(assignments_path),
            "clusters": str(clusters_path),
            "unresolved": str(unresolved_path),
        },
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# All-factor cluster expansion",
        "",
        "This is an offline expansion of the saved factor cluster analysis. It does not contact PandaAI, create factors, or run backtests.",
        "",
        f"- Existing matrix: `{matrix_path}`; 65 records, 20 retained base records, 45 historical composites.",
        f"- Added scope: `{len(remaining_records)}` locally supported records; `{composite_new}` visible composites are annotated without creating clusters.",
        f"- New single-mechanism records eligible for clustering: `{usable_new_single}`.",
        f"- Not assigned: `{len(unresolved_rows)}` records (`{len(unsupported)}` without a local handler, `{len(unusable_ids)}` with no finite local signal).",
        f"- Window: `{args.start}..{args.end}`; warm-up `{args.data_start}`; universe `{ALIGNMENT_UNIVERSE_LABEL}`; qfq; `total_mv`.",
        f"- Correlation: `{ALIGNMENT_CORRELATION_METHOD}`; {ALIGNMENT_CORRELATION_DESCRIPTION}.",
        f"- Assignment edge: `abs(rho) >= {args.threshold:.2f}`. Composite formulas and unusable signals never create independent clusters.",
        "",
        "## Expanded clusters",
        "",
        "| Cluster | Records | Negative-net members | Representative | Representative net excess | Representative RankIC |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for row in clusters:
        lines.append(
            f"| {row['cluster']} | {row['record_count']} | {row['negative_net_member_count']} | "
            f"{row['representative']} | {fmt_pct(row['representative_platform_net_excess_pct'])} | "
            f"{fmt_num(row['representative_platform_rank_ic'])} |"
        )
    lines.extend(
        [
            "",
            "## Remaining-factor assignments",
            "",
            "`joined_existing_cluster` means an edge to an old base cluster at the threshold. `new_independent_cluster` means a new connected component among single-mechanism records. `composite_*` rows are attribution only. `local_signal_unavailable` rows are excluded from the graph.",
            "",
            "| Factor | Net excess | RankIC | Composite | Assignment | High-correlation clusters | Nearest base factor | Nearest abs rho |",
            "|---|---:|---:|:---:|---|---|---|---:|",
        ]
    )
    for row in assignments:
        lines.append(
            f"| {row['factor_name']} | {fmt_pct(row['platform_net_excess_pct'])} | "
            f"{fmt_num(row['platform_rank_ic'])} | {'yes' if row['visible_composite'] else 'no'} | "
            f"{row['assigned_cluster']} ({row['assignment_status']}) | "
            f"{row['high_correlation_clusters'] or 'none'} | {row['nearest_base_factor'] or 'n/a'} | "
            f"{fmt_num(row['nearest_base_abs_rho'])} |"
        )
    lines.extend(
        [
            "",
            "## Unresolved records",
            "",
            "These records are retained in the catalog but are not forced into a cluster.",
            "",
            "| Factor | Net excess | Status | Reason |",
            "|---|---:|---|---|",
        ]
    )
    for row in unresolved_rows:
        lines.append(
            f"| {row['factor_name']} | {fmt_pct(row['platform_net_excess_pct'])} | "
            f"{row['status']} | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Pair matrix: `{pairs_path}`.",
            f"- Remaining-factor assignments: `{assignments_path}`.",
            f"- Expanded cluster summary: `{clusters_path}`.",
            f"- Unresolved records: `{unresolved_path}`.",
            f"- Machine-readable report: `{json_path}`.",
            "- The 45 old composite annotations remain in `factor-base-clusters-20260919.md` and are not counted again.",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"report={markdown_path} clusters={len(clusters)} assignments={len(assignments)} "
        f"unresolved={len(unresolved_rows)} unusable={len(unusable_ids)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
