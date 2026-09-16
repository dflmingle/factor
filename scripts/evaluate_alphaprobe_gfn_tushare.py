#!/usr/bin/env python3
"""Evaluate an AlphaPROBE GFlowNet pool on the aligned local Tushare panels."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALPHAPROBE_SRC = PROJECT_ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"
if str(ALPHAPROBE_SRC) not in sys.path:
    sys.path.insert(0, str(ALPHAPROBE_SRC))

from alpha_gfn.alpha_pool import AlphaPoolGFN  # noqa: E402
from alphagen.data.tree import ExpressionParser  # noqa: E402
from alphagen.utils.correlation import batch_pearsonr  # noqa: E402
from alphaprobe_gfn_tushare import (  # noqa: E402
    DEFAULT_OUTPUT,
    build_parser as build_training_parser,
    load_panels,
    resolve_device,
    safe_batch_spearmanr,
)


def build_parser() -> argparse.ArgumentParser:
    parser = build_training_parser()
    parser.description = __doc__
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="directory containing final_pool.json",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=None,
        help="directory for factor_metrics.csv and factor_metrics.json; defaults to --run-dir",
    )
    return parser


def evaluate(args: argparse.Namespace) -> dict:
    run_dir = args.run_dir.expanduser().resolve()
    report_output = (args.report_output or run_dir).expanduser().resolve()
    final_pool = json.loads((run_dir / "final_pool.json").read_text(encoding="utf-8"))
    saved_metadata_path = run_dir / "run_metadata.json"
    saved_metadata = (
        json.loads(saved_metadata_path.read_text(encoding="utf-8"))
        if saved_metadata_path.exists()
        else {}
    )
    # Runs created before --ic-objective existed used the absolute-IC pool.
    # The evaluator does not need the mode to calculate values, but preserving
    # it in metadata prevents a historical run from being mislabeled.
    saved_objective = saved_metadata.get("ic_objective", "absolute")
    if saved_objective in {"absolute", "signed_positive"}:
        args.ic_objective = saved_objective
    device = resolve_device(args.device)
    panels, target, metadata = load_panels(args, device)
    metadata["evaluated_run_metadata"] = saved_metadata
    metadata["ic_objective"] = saved_objective
    parser = ExpressionParser()
    target_values = {
        split: target.evaluate(panel) for split, panel in panels.items()
    }
    ensemble_values = {
        split: torch.zeros_like(value) for split, value in target_values.items()
    }
    rows: list[dict[str, object]] = []

    with torch.no_grad():
        for rank, (formula, weight) in enumerate(
            zip(final_pool["exprs"], final_pool["weights"]), start=1
        ):
            expression = parser.parse(formula)
            row: dict[str, object] = {
                "rank": rank,
                "formula": formula,
                "weight": float(weight),
            }
            for split, panel in panels.items():
                value = AlphaPoolGFN._normalize_by_day(expression.evaluate(panel))
                target_value = target_values[split]
                row[f"{split}_ic"] = float(
                    batch_pearsonr(value, target_value).mean().item()
                )
                row[f"{split}_rank_ic"] = float(
                    safe_batch_spearmanr(value, target_value).mean().item()
                )
                ensemble_values[split] = ensemble_values[split] + value * float(weight)
                del value
            rows.append(row)

    ensemble: dict[str, dict[str, float]] = {}
    for split, value in ensemble_values.items():
        target_value = target_values[split]
        ensemble[split] = {
            "ic": float(batch_pearsonr(value, target_value).mean().item()),
            "rank_ic": float(safe_batch_spearmanr(value, target_value).mean().item()),
        }

    report_output.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank",
        "weight",
        "train_ic",
        "train_rank_ic",
        "valid_ic",
        "valid_rank_ic",
        "test_ic",
        "test_rank_ic",
        "formula",
    ]
    with (report_output / "factor_metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in rows)

    result = {
        "run_dir": str(run_dir),
        "report_output": str(report_output),
        "factor_count": len(rows),
        "ensemble": ensemble,
        "metadata": metadata,
        "factors": rows,
    }
    (report_output / "factor_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    args = build_parser().parse_args()
    result = evaluate(args)
    print(
        json.dumps(
            {
                "run_dir": result["run_dir"],
                "report_output": result["report_output"],
                "factor_count": result["factor_count"],
                "ensemble": result["ensemble"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    for row in sorted(
        result["factors"], key=lambda item: float(item["test_rank_ic"]), reverse=True
    )[:10]:
        print(
            json.dumps(
                {
                    key: row[key]
                    for key in [
                        "rank",
                        "weight",
                        "train_rank_ic",
                        "valid_rank_ic",
                        "test_rank_ic",
                        "formula",
                    ]
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
