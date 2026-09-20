#!/usr/bin/env python3
"""Extend the saved-factor clusters without rerunning the existing matrix.

The 65-record positive-net matrix and its 12 base clusters already exist. This
script rebuilds only the 20 base members plus saved records that are not in
that matrix, then assigns the new records by the same daily cross-sectional
Spearman statistic and ``abs(rho) >= 0.80`` edge rule.

It is offline only: no PandaAI calls, factor creation, or backtests.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import correlation_positive_factors as corr  # noqa: E402
import financial_factor_local as financial_local  # noqa: E402
from financial_factor_local import FINANCIAL_HANDLERS, load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
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
from positive_factor_local_compare import formula_catalog, saved_records  # noqa: E402
from stfilter_local_recheck import CACHE_ROOT, ensure_calendar  # noqa: E402


DEFAULT_MATRIX = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "positive-factor-pair-correlation-20260917.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "all-factor-cluster-expansion-20260919"
)
DEFAULT_PRICE_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = CACHE_ROOT / "financial_full_a"


# These are the retained single-mechanism members in the existing report. The
# IDs are taken from the old matrix, so duplicate runs are kept as records but
# share the same base cluster.
BASE_CLUSTER_NAMES: dict[str, set[str]] = {
    "B01": {
        "SIZE-ONLY-20260911",
        "H03-T10-SINGLE",
        "VERIFY-G260910-13",
        "VERIFY10-G260910-13",
    },
    "B02": {"HT13-TURN-BIAS-1M", "HT13-TURN-BIAS-1M-POS"},
    "B03": {"OSR2-RET40"},
    "B04": {"OSR2-DD120"},
    "B05": {"NONHT-CHIP-COST-250", "HT13-MOMENTUM-120D-D0"},
    "B06": {"F-NET01-PLAT-20260914"},
    "B07": {"NEW-VALUE-EVEBITDA"},
    "B08": {"HT13-VALUE-BP"},
    "B09": {"OSR2-DD60"},
    "B10": {"paper-derived-asset-growth"},
    "B11": {"NONHT-RESVOL-LOW"},
    "B12": {"HT13-VALUE-SP"},
}


def parse_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    return pd.Timestamp(
        pd.to_datetime(text, format="%Y%m%d" if len(text) == 8 else None)
    ).normalize()


def record_key(record: dict[str, Any]) -> str:
    return str(record.get("id"))


def visible_composite(record: dict[str, Any]) -> bool:
    """Conservatively identify formulas that visibly combine mechanisms."""
    handler = str(record.get("handler") or "").lower()
    name = str(record.get("name") or "").lower()
    formula = str(record.get("formula") or "").upper()
    if formula.count("RANK(") >= 2:
        return True
    if any(
        token in handler or token in name
        for token in (
            "reversal_bm",
            "reversal_ep",
            "reversal_turn",
            "reversal_chip",
            "reversal5_",
            "reversal20_",
            "growth_operating_cashflow_reversal",
            "fscore",
            "paper_composite",
            "style_eq",
            "vwap10_volume20_momentum20",
            "weighted_reversal",
            "combo",
            "t10_",
        )
    ):
        return True
    return False


def heuristic_components(record: dict[str, Any]) -> list[str]:
    """Give composite rows a transparent, formula-name level attribution."""
    text = " ".join(
        str(record.get(field) or "").lower()
        for field in ("name", "handler", "formula")
    )
    components: list[str] = []
    if any(token in text for token in ("market_cap", "nomcap", "size", "impact")):
        components.append("B01")
    if any(token in text for token in ("turn", "lowturn", "turnover")):
        components.append("B02")
    if any(token in text for token in ("reversal", "momentum", "oversold")):
        components.append("B03")
    if any(token in text for token in ("dd120", "drawdown120")):
        components.append("B04")
    elif any(token in text for token in ("dd60", "drawdown60")):
        components.append("B09")
    if any(token in text for token in ("chip", "cost")):
        components.append("B05")
    if any(token in text for token in ("book_to_market", "value", "bm_", "ep_", "pcf")):
        components.append("B08")
    if "ev" in text or "ebitda" in text:
        components.append("B07")
    if "asset_growth" in text:
        components.append("B10")
    if "residual" in text or "volatility" in text:
        components.append("B11")
    if any(token in text for token in ("sales", "ratio_sp", "value_sp")):
        components.append("B12")
    return list(dict.fromkeys(components))


def load_records_and_base(
    matrix_path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
    list[dict[str, Any]],
]:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix_records = matrix.get("records")
    if not isinstance(matrix_records, list):
        raise ValueError(f"Existing matrix has no records list: {matrix_path}")
    matrix_ids = {record_key(record) for record in matrix_records}

    supported, unsupported = saved_records(formula_catalog(), "all")
    supported_by_id = {record_key(record): record for record in supported}

    base_cluster_by_id: dict[str, str] = {}
    for cluster, names in BASE_CLUSTER_NAMES.items():
        for record in matrix_records:
            if record.get("name") in names:
                base_cluster_by_id[record_key(record)] = cluster
    if len(base_cluster_by_id) != 20:
        raise ValueError(
            "Existing base cluster membership did not resolve to 20 records: "
            f"{len(base_cluster_by_id)}"
        )

    base_records = [
        supported_by_id.get(record_key(record), record)
        for record in matrix_records
        if record_key(record) in base_cluster_by_id
    ]
    remaining_records = [
        record for record in supported if record_key(record) not in matrix_ids
    ]
    unresolved = list(unsupported)
    old_composites = [
        record for record in matrix_records if record_key(record) not in base_cluster_by_id
    ]
    return (
        base_records,
        remaining_records,
        unresolved,
        base_cluster_by_id,
        old_composites,
    )


def pair_lookup(pair_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in pair_rows:
        left = str(row["factor_a_id"])
        right = str(row["factor_b_id"])
        lookup[tuple(sorted((left, right)))] = row
    return lookup


def pair_for(
    lookup: dict[tuple[str, str], dict[str, Any]],
    left: str,
    right: str,
) -> dict[str, Any] | None:
    return lookup.get(tuple(sorted((left, right))))


def finite_abs(row: dict[str, Any] | None) -> float | None:
    if not row or row.get("abs_correlation") is None:
        return None
    value = float(row["abs_correlation"])
    return value if np.isfinite(value) else None


class UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def build_cluster_assignments(
    *,
    base_records: list[dict[str, Any]],
    remaining_records: list[dict[str, Any]],
    base_cluster_by_id: dict[str, str],
    pair_rows: list[dict[str, Any]],
    threshold: float,
    unusable_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lookup = pair_lookup(pair_rows)
    unusable_ids = set(unusable_ids or ())
    base_ids = [record_key(record) for record in base_records]
    single_remaining = [
        record
        for record in remaining_records
        if not visible_composite(record) and record_key(record) not in unusable_ids
    ]
    single_ids = [record_key(record) for record in single_remaining]
    uf = UnionFind(base_ids + single_ids)

    for index, left in enumerate(base_ids + single_ids):
        for right in (base_ids + single_ids)[index + 1 :]:
            row = pair_for(lookup, left, right)
            if finite_abs(row) is not None and float(row["abs_correlation"]) >= threshold:
                uf.union(left, right)

    components: dict[str, list[str]] = defaultdict(list)
    for item in base_ids + single_ids:
        components[uf.find(item)].append(item)
    component_labels: dict[str, str] = {}
    new_index = 1
    for root, members in components.items():
        base_labels = sorted({base_cluster_by_id[item] for item in members if item in base_cluster_by_id})
        if base_labels:
            component_labels[root] = "+".join(base_labels)
        else:
            component_labels[root] = f"N{new_index:02d}"
            new_index += 1

    rows: list[dict[str, Any]] = []
    base_set = set(base_ids)
    for record in remaining_records:
        factor_id = record_key(record)
        composite = visible_composite(record)
        if factor_id in unusable_ids:
            rows.append(
                {
                    "factor_id": factor_id,
                    "factor_name": record.get("name"),
                    "report": record.get("report"),
                    "handler": record.get("handler"),
                    "formula": record.get("formula"),
                    "platform_net_excess_pct": record.get("platform_net_excess_pct"),
                    "platform_rank_ic": record.get("platform_rank_ic"),
                    "platform_direction": record.get("direction"),
                    "visible_composite": composite,
                    "assignment_status": "local_signal_unavailable",
                    "assigned_cluster": "unassigned",
                    "high_correlation_clusters": "",
                    "high_correlation_links": "[]",
                    "heuristic_components": ";".join(heuristic_components(record))
                    if composite
                    else "",
                    "nearest_base_factor": None,
                    "nearest_base_rho": None,
                    "nearest_base_abs_rho": None,
                    "reason": "local handler returned no finite signal values in the formal window",
                }
            )
            continue
        direct_links: list[dict[str, Any]] = []
        for other in base_records + single_remaining:
            other_id = record_key(other)
            if other_id == factor_id:
                continue
            row = pair_for(lookup, factor_id, other_id)
            absolute = finite_abs(row)
            if absolute is None or absolute < threshold:
                continue
            if other_id in base_set:
                label = base_cluster_by_id[other_id]
            else:
                label = component_labels[uf.find(other_id)]
            direct_links.append(
                {
                    "cluster": label,
                    "factor": other.get("name"),
                    "rho": row.get("correlation"),
                }
            )

        base_pairs = [
            (other, pair_for(lookup, factor_id, record_key(other)))
            for other in base_records
        ]
        valid_base_pairs = [
            (other, row, finite_abs(row))
            for other, row in base_pairs
            if finite_abs(row) is not None
        ]
        valid_base_pairs.sort(key=lambda item: float(item[2]), reverse=True)
        nearest = valid_base_pairs[0] if valid_base_pairs else (None, None, None)

        if composite:
            link_labels = sorted({item["cluster"] for item in direct_links})
            heuristic = heuristic_components(record)
            status = "composite_joined_by_correlation" if link_labels else "composite_not_clustered"
            assigned = ";".join(link_labels) if link_labels else "composite-only"
            reason = "visible multi-mechanism formula; no independent cluster"
        else:
            assigned = component_labels[uf.find(factor_id)]
            link_labels = sorted({item["cluster"] for item in direct_links})
            status = "joined_existing_cluster" if assigned.startswith("B") else "new_independent_cluster"
            reason = (
                "connected to an existing base cluster at the 0.80 threshold"
                if assigned.startswith("B")
                else "no 0.80 edge to existing base clusters; formed a new connected component"
            )
            heuristic = []
        rows.append(
            {
                "factor_id": factor_id,
                "factor_name": record.get("name"),
                "report": record.get("report"),
                "handler": record.get("handler"),
                "formula": record.get("formula"),
                "platform_net_excess_pct": record.get("platform_net_excess_pct"),
                "platform_rank_ic": record.get("platform_rank_ic"),
                "platform_direction": record.get("direction"),
                "visible_composite": composite,
                "assignment_status": status,
                "assigned_cluster": assigned,
                "high_correlation_clusters": ";".join(link_labels),
                "high_correlation_links": json.dumps(direct_links, ensure_ascii=False),
                "heuristic_components": ";".join(heuristic),
                "nearest_base_factor": nearest[0].get("name") if nearest[0] else None,
                "nearest_base_rho": nearest[1].get("correlation") if nearest[1] else None,
                "nearest_base_abs_rho": nearest[2],
                "reason": reason,
            }
        )
    rows.sort(key=lambda row: (str(row["assigned_cluster"]), str(row["factor_name"]), str(row["factor_id"])))

    cluster_rows: list[dict[str, Any]] = []
    cluster_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in base_records + single_remaining:
        factor_id = record_key(record)
        label = component_labels[uf.find(factor_id)]
        cluster_members[label].append(record)
    for row in rows:
        if row["visible_composite"] or row["assignment_status"] == "local_signal_unavailable":
            continue
        if row["assigned_cluster"] not in cluster_members:
            record = next(record for record in remaining_records if record_key(record) == row["factor_id"])
            cluster_members[row["assigned_cluster"]].append(record)
    for label, members in sorted(cluster_members.items()):
        representative = max(
            members,
            key=lambda member: float(member.get("platform_net_excess_pct") or float("-inf")),
        )
        cluster_rows.append(
            {
                "cluster": label,
                "record_count": len(members),
                "member_names": ";".join(str(member.get("name")) for member in members),
                "representative": representative.get("name"),
                "representative_platform_net_excess_pct": representative.get("platform_net_excess_pct"),
                "representative_platform_rank_ic": representative.get("platform_rank_ic"),
                "negative_net_member_count": sum(
                    float(member.get("platform_net_excess_pct") or 0.0) <= 0.0
                    for member in members
                ),
            }
        )
    return rows, cluster_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--output-prefix", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--start", default=ALIGNMENT_START)
    parser.add_argument("--end", default=ALIGNMENT_END)
    parser.add_argument("--price-root", default=str(DEFAULT_PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(DEFAULT_CAP_ROOT))
    parser.add_argument("--financial-root", default=str(DEFAULT_FINANCIAL_ROOT))
    parser.add_argument("--high-correlation-threshold", type=float, default=0.80)
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    if not 0.0 <= args.high_correlation_threshold <= 1.0:
        raise SystemExit("high-correlation-threshold must be between 0 and 1")
    data_start = parse_date(args.data_start)
    start = parse_date(args.start)
    end = parse_date(args.end)
    if data_start > start or start > end:
        raise SystemExit("dates must satisfy data-start <= start <= end")

    base_records, remaining_records, unresolved, base_cluster_by_id, old_composites = load_records_and_base(
        Path(args.matrix)
    )
    computed_remaining_records = [
        record for record in remaining_records if not visible_composite(record)
    ]
    selected_records = base_records + computed_remaining_records
    handlers = sorted({str(record["handler"]) for record in selected_records})
    print(
        f"base_records={len(base_records)} remaining_supported={len(remaining_records)} "
        f"computed_single_remaining={len(computed_remaining_records)} "
        f"unresolved={len(unresolved)} handlers={len(handlers)}",
        flush=True,
    )

    frame = load_full_a_data(Path(args.price_root), Path(args.cap_root), data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(data_start, end, token=None)
    ]
    comparison_dates = [date for date in calendar if start <= date <= end]
    comparison_frame = frame[frame["date"].isin(comparison_dates)].sort_values(
        ["date", "instrument"], kind="stable"
    )
    if comparison_frame.empty:
        raise SystemExit("no local rows on comparison dates")
    print(
        f"frame_rows={len(frame)} comparison_rows={len(comparison_frame)} "
        f"instruments={frame['instrument'].nunique()} comparison_dates={len(comparison_dates)}",
        flush=True,
    )

    financial_handlers = {
        str(record["handler"])
        for record in selected_records
        if str(record["handler"]) in FINANCIAL_HANDLERS
    }
    financial: dict[str, pd.DataFrame] | None = None
    if financial_handlers:
        raw_financial = load_financial_cache(Path(args.financial_root))
        financial = corr.slim_financial_cache(raw_financial)
        del raw_financial
        gc.collect()
        print(f"financial_handlers={len(financial_handlers)}", flush=True)

    snapshot: dict[str, pd.DataFrame] = {}
    if financial is not None:
        snapshot = corr.install_financial_snapshot_cache(frame, comparison_dates)
    comparison_index = comparison_frame.index
    handler_values: dict[str, np.ndarray] = {}
    for index, handler in enumerate(handlers, start=1):
        print(f"building handler={handler} ({index}/{len(handlers)})...", flush=True)
        values = corr.build_factor(
            frame,
            handler,
            financial=financial,
            signal_dates=comparison_dates,
        )
        aligned = pd.to_numeric(values.reindex(comparison_index), errors="coerce")
        # Float32 halves the matrix footprint; ranks are recomputed as float64
        # inside pairwise_daily_spearman, so this does not change the statistic
        # materially while keeping the full expansion in memory.
        handler_values[handler] = aligned.to_numpy(dtype=np.float32)
        print(
            f"handler={handler} valid_rows={int(np.isfinite(handler_values[handler]).sum())}",
            flush=True,
        )
        del values, aligned
        gc.collect()
    unusable_ids = {
        record_key(record)
        for record in computed_remaining_records
        if not np.isfinite(handler_values[str(record["handler"])]).any()
    }
    snapshot.clear()
    financial_local._HISTORICAL_RANK_CACHE.clear()
    del frame, financial
    gc.collect()

    record_values = np.column_stack(
        [handler_values[str(record["handler"])] for record in selected_records]
    )
    del handler_values
    gc.collect()
    record_pairs = [
        (left, right)
        for left in range(len(selected_records))
        for right in range(left + 1, len(selected_records))
    ]
    print(f"calculating_pairs={len(record_pairs)}", flush=True)
    pair_stats = corr.pairwise_daily_spearman(
        comparison_frame,
        record_values,
        record_pairs,
        progress_every=args.progress_every,
    )
    del record_values
    gc.collect()
    pair_rows = corr.enrich_pairs(
        selected_records,
        pair_stats,
        args.high_correlation_threshold,
    )
    assignments, clusters = build_cluster_assignments(
        base_records=base_records,
        remaining_records=remaining_records,
        base_cluster_by_id=base_cluster_by_id,
        pair_rows=pair_rows,
        threshold=args.high_correlation_threshold,
        unusable_ids=unusable_ids,
    )

    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    pairs_path = output_prefix.with_suffix(".pairs.csv")
    assignments_path = output_prefix.with_suffix(".assignments.csv")
    clusters_path = output_prefix.with_suffix(".clusters.csv")
    unresolved_path = output_prefix.with_suffix(".unresolved.csv")
    json_path = output_prefix.with_suffix(".json")
    markdown_path = output_prefix.with_suffix(".md")
    pd.DataFrame(pair_rows).to_csv(pairs_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(assignments).to_csv(assignments_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(clusters).to_csv(clusters_path, index=False, encoding="utf-8-sig")
    unresolved_rows = [
        {
            "factor_id": record.get("id"),
            "factor_name": record.get("name"),
            "report": record.get("report"),
            "formula": record.get("formula"),
            "platform_net_excess_pct": record.get("platform_net_excess_pct"),
            "reason": record.get("reason"),
        }
        for record in unresolved
    ]
    unresolved_rows.extend(
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
        for record in computed_remaining_records
        if record_key(record) in unusable_ids
    )
    pd.DataFrame(unresolved_rows).to_csv(unresolved_path, index=False, encoding="utf-8-sig")

    settings = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "source_matrix": str(Path(args.matrix)),
        "scope": "all saved completed platform records",
        "universe": ALIGNMENT_UNIVERSE_LABEL,
        "price_mode": ALIGNMENT_PRICE_MODE,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "data_start": data_start.strftime("%Y%m%d"),
        "comparison_start": start.strftime("%Y%m%d"),
        "comparison_end": end.strftime("%Y%m%d"),
        "comparison_dates": len(comparison_dates),
        "comparison_rows": len(comparison_frame),
        "correlation_method": ALIGNMENT_CORRELATION_METHOD,
        "correlation_description": ALIGNMENT_CORRELATION_DESCRIPTION,
        "threshold": args.high_correlation_threshold,
        "old_matrix_records": 65,
        "old_base_records": len(base_records),
        "old_composite_records": len(old_composites),
        "new_supported_records": len(remaining_records),
        "new_composite_records_not_recomputed": len(remaining_records) - len(computed_remaining_records),
        "local_signal_unavailable_records": len(unusable_ids),
        "unresolved_records": len(unresolved_rows),
        "recomputed_records": len(selected_records),
        "recomputed_handlers": len(handlers),
        "pair_count": len(pair_rows),
        "high_pair_count": sum(bool(row.get("high_correlation")) for row in pair_rows),
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
        json.dumps(payload, ensure_ascii=False, indent=2, default=corr.json_default) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# All-factor cluster expansion",
        "",
        "This is an offline expansion of the saved factor cluster analysis. It does not contact PandaAI, create factors, or run backtests.",
        "",
        f"- Existing matrix: `{args.matrix}`; 65 records, 20 retained base records, 45 historical composites.",
        f"- Added scope: all saved completed platform records not in that matrix: `{len(remaining_records)}` locally supported records; `{len(remaining_records) - len(computed_remaining_records)}` visible composites are annotated without creating clusters.",
        f"- Unresolved and not forced into a cluster: `{len(unresolved_rows)}` records (`{len(unresolved)}` without a local handler; `{len(unusable_ids)}` with no finite local signal).",
        f"- Window: `{start.strftime('%Y%m%d')}..{end.strftime('%Y%m%d')}`; warm-up `{data_start.strftime('%Y%m%d')}`; universe `{ALIGNMENT_UNIVERSE_LABEL}`; qfq; `total_mv`.",
        f"- Correlation: `{ALIGNMENT_CORRELATION_METHOD}`; {ALIGNMENT_CORRELATION_DESCRIPTION}.",
        f"- Assignment edge: `abs(rho) >= {args.high_correlation_threshold:.2f}`. Composite formulas are annotated but never create independent clusters.",
        "",
        "## Expanded clusters",
        "",
        "| Cluster | Records | Negative-net members | Representative | Representative net excess | Representative RankIC |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for row in clusters:
        lines.append(
            f"| {row['cluster']} | {row['record_count']} | {row['negative_net_member_count']} | "
            f"{row['representative']} | {float(row['representative_platform_net_excess_pct']):.2f}% | "
            f"{float(row['representative_platform_rank_ic']):.4f} |"
        )
    lines.extend(
        [
            "",
            "## Newly assigned records",
            "",
            "`joined_existing_cluster` means the record is connected to an old base cluster at the threshold. `new_independent_cluster` means it creates a new connected component among single-mechanism records. `composite_*` rows are attribution only. `local_signal_unavailable` rows are excluded from the graph.",
            "",
            "| Factor | Net excess | RankIC | Composite | Assignment | High-correlation clusters | Nearest base factor | Nearest abs rho |",
            "|---|---:|---:|:---:|---|---|---|---:|",
        ]
    )
    for row in assignments:
        net = "n/a" if row["platform_net_excess_pct"] is None else f"{float(row['platform_net_excess_pct']):.2f}%"
        rank_ic = "n/a" if row["platform_rank_ic"] is None else f"{float(row['platform_rank_ic']):.4f}"
        nearest = "n/a" if row["nearest_base_abs_rho"] is None else f"{float(row['nearest_base_abs_rho']):.4f}"
        lines.append(
            f"| {row['factor_name']} | {net} | {rank_ic} | "
            f"{'yes' if row['visible_composite'] else 'no'} | {row['assigned_cluster']} ({row['assignment_status']}) | "
            f"{row['high_correlation_clusters'] or 'none'} | {row['nearest_base_factor'] or 'n/a'} | {nearest} |"
        )
    lines.extend(
        [
            "",
            "## Unresolved records",
            "",
            "These platform records have no local handler under the current alignment contract. They are listed for follow-up and are not assigned by guesswork.",
            "",
            "| Factor | Net excess | Status | Reason |",
            "|---|---:|---|---|",
        ]
    )
    for row in unresolved_rows:
        net = "n/a" if row["platform_net_excess_pct"] is None else f"{float(row['platform_net_excess_pct']):.2f}%"
        lines.append(f"| {row['factor_name']} | {net} | {row.get('status', 'no_local_handler')} | {row['reason']} |")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Incremental pair matrix: `{pairs_path}`.",
            f"- New-factor assignments: `{assignments_path}`.",
            f"- Expanded cluster summary: `{clusters_path}`.",
            f"- Unresolved records: `{unresolved_path}`.",
            f"- Machine-readable report: `{json_path}`.",
            "- The 45 old composite annotations remain in `factor-base-clusters-20260919.md` and are not counted again.",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report={markdown_path}", flush=True)
    print(f"clusters={len(clusters)} assignments={len(assignments)} unresolved={len(unresolved)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
