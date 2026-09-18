#!/usr/bin/env python3
"""Finalize AlphaPROBE GP candidates after historical signal deduplication.

This is an offline step. It evaluates the eligible candidates and all locally
reconstructable historical platform formulas on the same aligned panel, then
removes candidates whose daily cross-sectional rank signal is already present
or duplicated by another candidate in the current batch.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alphaprobe_gp_tushare import (  # noqa: E402
    AlignedNetExcessContext,
    TushareStockData,
    batch_spearmanr_linear,
    evaluate_formula,
    expression_namespace,
    finite_as_nan,
    load_trade_dates,
    parse_date,
)
from audit_alphaprobe_gp_candidates import (  # noqa: E402
    DEFAULT_BATCH_ROOT,
    DEFAULT_CACHE_ROOT,
    DEFAULT_CAP_ROOT,
    DEFAULT_FINANCIAL_ROOT,
)
from factor_formula_dedupe import normalize_formula  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from local_safe_financial_candidates import CrossSectionalZScore  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_START,
)


DEFAULT_AUDIT = PROJECT_ROOT / "research_reports/platform_alignment/gp-multifield-novelty-audit-final-20260918.json"
DEFAULT_HISTORICAL = (
    DEFAULT_CACHE_ROOT
    / "reports/all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/gp-multifield-novelty-final-20260918"
HISTORICAL_DUPLICATE_THRESHOLD = 0.90
BATCH_DUPLICATE_THRESHOLD = 0.90


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    return value


def finite_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def split_net(row: dict[str, Any], split: str) -> float | None:
    return finite_number((row.get("split_stats") or {}).get(split, {}).get("net_excess"))


def load_historical_formulas(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.get("results", []):
        formula = str(raw.get("formula") or "").strip()
        signature = normalize_formula(formula)
        if not formula or signature is None or signature in seen:
            continue
        seen.add(signature)
        rows.append(
            {
                "id": raw.get("id"),
                "name": raw.get("name"),
                "handler": raw.get("handler"),
                "formula": formula,
                "signature": signature,
                "local_net_excess": raw.get("local_net_excess"),
                "platform_net_excess_pct": raw.get("platform_net_excess_pct"),
            }
        )
    return rows


def daily_rank_correlation(left: torch.Tensor, right: torch.Tensor) -> tuple[float | None, int]:
    with torch.no_grad():
        values = batch_spearmanr_linear(left, right)
        values = values[torch.isfinite(values)]
        if values.numel() == 0:
            return None, 0
        return float(values.abs().mean().item()), int(values.numel())


def evaluate_signal(
    formula: str,
    namespace: dict[str, object],
    data: TushareStockData,
    positions: list[int],
) -> torch.Tensor:
    expression = evaluate_formula(formula, namespace)
    with torch.no_grad():
        factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
        signal = factor[positions].detach().cpu()
    del factor, expression
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return signal


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key not in {"historical_closest", "batch_closest"}}
    for prefix in ("historical_closest", "batch_closest"):
        closest = row.get(prefix) or {}
        result[f"{prefix}_name"] = closest.get("name") or closest.get("formula")
        result[f"{prefix}_abs_rank_corr"] = closest.get("abs_rank_corr")
        result[f"{prefix}_signed_rank_corr"] = closest.get("signed_rank_corr")
        result[f"{prefix}_periods"] = closest.get("periods")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    args = parser.parse_args()

    audit = json.loads(args.audit.resolve().read_text(encoding="utf-8"))
    candidates = [row for row in audit["candidates"] if row.get("decision") == "eligible_local_screen"]
    historical = load_historical_formulas(args.historical.resolve())
    print(f"candidates={len(candidates)} historical_formulas={len(historical)}", flush=True)

    start = parse_date(ALIGNMENT_START)
    end = parse_date(ALIGNMENT_END)
    data_start = parse_date(ALIGNMENT_DATA_START)
    calendar = load_trade_dates(args.cache_root.resolve())
    panel_calendar = [date for date in calendar if data_start <= date <= end]
    frame = load_full_a_data(
        args.batch_root.resolve(), args.cap_root.resolve(), data_start, end
    ).sort_values(["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data = TushareStockData.from_aligned_frame(
        frame=frame,
        calendar=panel_calendar,
        instrument=stock_ids,
        start_time=start,
        end_time=end,
        max_backtrack_days=756,
        max_future_days=0,
        device=device,
        financial_root=args.financial_root.resolve(),
    )
    context = AlignedNetExcessContext(
        frame=frame,
        calendar=panel_calendar,
        data=data,
        start_date=start,
        end_date=end,
        cycle=5,
        label_offset=ALIGNMENT_LABEL_OFFSET,
        groups=ALIGNMENT_GROUPS,
        round_trip_cost=ALIGNMENT_ROUND_TRIP_COST,
    )
    namespace = expression_namespace()
    namespace["ZSCORE"] = CrossSectionalZScore
    namespace["ZScore"] = CrossSectionalZScore

    candidate_signals: dict[str, torch.Tensor] = {}
    for index, row in enumerate(candidates, start=1):
        candidate_signals[row["formula"]] = evaluate_signal(
            row["raw_formula"], namespace, data, context.signal_data_positions
        )
        print(f"candidate={index}/{len(candidates)}", flush=True)

    historical_signals: list[tuple[dict[str, Any], torch.Tensor]] = []
    skipped_historical: list[dict[str, Any]] = []
    for index, row in enumerate(historical, start=1):
        try:
            signal = evaluate_signal(row["formula"], namespace, data, context.signal_data_positions)
            if not bool(torch.isfinite(signal).any().item()):
                raise ValueError("no finite signal")
            historical_signals.append((row, signal))
        except Exception as exc:
            skipped_historical.append({**row, "error": f"{type(exc).__name__}: {exc}"})
        if index % 10 == 0 or index == len(historical):
            print(
                f"historical={index}/{len(historical)} usable={len(historical_signals)} skipped={len(skipped_historical)}",
                flush=True,
            )

    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        formula = candidate["formula"]
        signal = candidate_signals[formula]
        closest_historical: dict[str, Any] | None = None
        for historical_row, historical_signal in historical_signals:
            abs_corr, periods = daily_rank_correlation(signal, historical_signal)
            if abs_corr is None:
                continue
            signed_corr, _ = daily_rank_correlation_signed(signal, historical_signal)
            item = {
                "name": historical_row.get("name"),
                "handler": historical_row.get("handler"),
                "formula": historical_row.get("formula"),
                "abs_rank_corr": abs_corr,
                "signed_rank_corr": signed_corr,
                "periods": periods,
                "local_net_excess": historical_row.get("local_net_excess"),
                "platform_net_excess_pct": historical_row.get("platform_net_excess_pct"),
            }
            if closest_historical is None or abs_corr > closest_historical["abs_rank_corr"]:
                closest_historical = item

        rows.append({**candidate, "historical_closest": closest_historical})
        print(
            f"historical_compare={index}/{len(candidates)} closest="
            f"{closest_historical['abs_rank_corr'] if closest_historical else None}",
            flush=True,
        )

    # Keep one candidate from each highly correlated current-batch cluster.
    for row in rows:
        row["batch_closest"] = None
        signal = candidate_signals[row["formula"]]
        for other in rows:
            if other is row:
                continue
            abs_corr, periods = daily_rank_correlation(signal, candidate_signals[other["formula"]])
            if abs_corr is None:
                continue
            signed_corr, _ = daily_rank_correlation_signed(signal, candidate_signals[other["formula"]])
            item = {
                "name": other.get("formula"),
                "formula": other.get("formula"),
                "abs_rank_corr": abs_corr,
                "signed_rank_corr": signed_corr,
                "periods": periods,
            }
            if row["batch_closest"] is None or abs_corr > row["batch_closest"]["abs_rank_corr"]:
                row["batch_closest"] = item

    # Test-period net excess is the tie-breaker for a redundant cluster.
    ordered = sorted(
        rows,
        key=lambda row: (
            -(split_net(row, "test") or -999.0),
            -(split_net(row, "valid") or -999.0),
            -(finite_number(row.get("gp_fitness")) or -999.0),
        ),
    )
    kept: list[dict[str, Any]] = []
    for row in ordered:
        historical_corr = (row.get("historical_closest") or {}).get("abs_rank_corr")
        if historical_corr is not None and historical_corr >= HISTORICAL_DUPLICATE_THRESHOLD:
            row["final_decision"] = "reject_historical_signal_duplicate"
            continue
        redundant = False
        for previous in kept:
            corr, _ = daily_rank_correlation(
                candidate_signals[row["formula"]], candidate_signals[previous["formula"]]
            )
            if corr is not None and corr >= BATCH_DUPLICATE_THRESHOLD:
                row["final_decision"] = "reject_batch_signal_duplicate"
                row["duplicate_of"] = previous["formula"]
                redundant = True
                break
        if not redundant:
            row["final_decision"] = "final_novel_candidate"
            kept.append(row)

    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "alignment": {
            "universe": "沪深全A",
            "start": str(ALIGNMENT_START),
            "end": str(ALIGNMENT_END),
            "data_start": str(ALIGNMENT_DATA_START),
            "cycle": 5,
            "label_offset": ALIGNMENT_LABEL_OFFSET,
            "groups": ALIGNMENT_GROUPS,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        },
        "thresholds": {
            "historical_duplicate_abs_daily_rank_corr": HISTORICAL_DUPLICATE_THRESHOLD,
            "batch_duplicate_abs_daily_rank_corr": BATCH_DUPLICATE_THRESHOLD,
        },
        "sources": {"audit": args.audit.resolve(), "historical": args.historical.resolve()},
        "candidate_count_after_audit": len(candidates),
        "historical_formula_count": len(historical),
        "historical_signal_count": len(historical_signals),
        "historical_signal_skipped_count": len(skipped_historical),
        "final_candidate_count": len(kept),
        "candidates": rows,
        "final_candidates": kept,
        "skipped_historical": skipped_historical,
    }
    json_path = args.output.resolve().with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    with args.output.resolve().with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = sorted({key for row in rows for key in flatten(row)})
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if rows:
            writer.writeheader()
            writer.writerows(flatten(row) for row in rows)

    lines = [
        "# AlphaPROBE GP final novel candidates",
        "",
        "This is an offline local result. No PandaAI factor was created or run.",
        "",
        f"- Eligible after formula/split/size audit: `{len(candidates)}`",
        f"- Historical platform formulas compared: `{len(historical_signals)}` usable of `{len(historical)}`",
        f"- Final novel candidates: `{len(kept)}`",
        f"- Historical duplicate threshold: absolute daily RankIC `{HISTORICAL_DUPLICATE_THRESHOLD:.2f}`",
        f"- Current-batch duplicate threshold: absolute daily RankIC `{BATCH_DUPLICATE_THRESHOLD:.2f}`",
        "",
        "Only final novel candidates are listed below; rejected existing/duplicate formulas are retained in the JSON/CSV audit but are not presented as candidates.",
        "",
        "| rank | formula | full net | valid net | test net | size RankIC | closest historical abs RankIC |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    final_sorted = sorted(kept, key=lambda row: -(split_net(row, "test") or -999.0))
    for rank, row in enumerate(final_sorted, start=1):
        closest = row.get("historical_closest") or {}
        def pct(value: Any) -> str:
            parsed = finite_number(value)
            return "n/a" if parsed is None else f"{parsed * 100:.2f}%"
        lines.append(
            f"| {rank} | `{row['formula']}` | {pct(row.get('full_net_excess'))} | "
            f"{pct(split_net(row, 'valid'))} | {pct(split_net(row, 'test'))} | "
            f"{pct(row.get('size_rank_corr'))} | {closest.get('abs_rank_corr', float('nan')):.4f} |"
        )
    lines.extend(
        [
            "",
            "The closest historical formula name/handler and all rejected rows are available only in the machine-readable JSON/CSV for audit purposes.",
        ]
    )
    args.output.resolve().with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report={args.output.resolve().with_suffix('.md')}", flush=True)
    return 0


def daily_rank_correlation_signed(left: torch.Tensor, right: torch.Tensor) -> tuple[float | None, int]:
    with torch.no_grad():
        values = batch_spearmanr_linear(left, right)
        values = values[torch.isfinite(values)]
        if values.numel() == 0:
            return None, 0
        return float(values.mean().item()), int(values.numel())


if __name__ == "__main__":
    raise SystemExit(main())
