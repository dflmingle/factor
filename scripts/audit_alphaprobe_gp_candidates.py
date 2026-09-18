#!/usr/bin/env python3
"""Audit GP expressions for novelty, split stability, and size exposure."""

from __future__ import annotations

import argparse
import csv
import json
import re
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
    expression_to_panda_formula,
    finite_as_nan,
    load_trade_dates,
    parse_date,
)
from factor_formula_dedupe import (  # noqa: E402
    load_scale_invariant_signatures,
    load_signatures,
    normalize_formula,
    normalize_scale_invariant_formula,
)
from full_a_local_data import load_full_a_data  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE,
)


DEFAULT_CACHE_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
DEFAULT_GP_RUN = (
    DEFAULT_CACHE_ROOT
    / "reports"
    / "alphaprobe_gp_tushare"
    / "orthogonal-fundamental-verified-multifield-net-20260918"
    / "gp_run.json"
)
DEFAULT_REGISTRY = PROJECT_ROOT / "research_reports" / "platform_alignment" / "factor_formula_registry.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports" / "platform_alignment" / "gp-multifield-novelty-audit-20260918"
DEFAULT_BATCH_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = DEFAULT_CACHE_ROOT / "financial_full_a"

SPLITS = (
    ("train", "20210907", "20240906"),
    ("valid", "20240909", "20250905"),
    ("test", "20250908", "20260907"),
)


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


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def used_fields(formula: str, search_fields: set[str]) -> list[str]:
    values = {
        token.lower()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
        if token.lower() in search_fields
    }
    return sorted(values)


def load_unique_candidates(
    gp_run: Path,
    registry: Path,
    scan_count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    payload = json.loads(gp_run.read_text(encoding="utf-8"))
    cache = payload.get("cache") or {}
    settings = payload.get("settings") or {}
    search_fields = {
        str(item).strip().lower()
        for item in settings.get("search_fields", [])
        if not str(item).startswith("Constant(")
    }
    existing = load_signatures(registry)
    existing_scale_invariant = load_scale_invariant_signatures(registry)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_formula, fitness in sorted(
        ((str(formula), number(score) or -1.0) for formula, score in cache.items()),
        key=lambda item: item[1],
        reverse=True,
    ):
        try:
            panda_formula = expression_to_panda_formula(raw_formula)
        except ValueError:
            panda_formula = raw_formula
        signature = normalize_formula(panda_formula)
        scale_signature = normalize_scale_invariant_formula(panda_formula)
        if signature is None or signature in seen:
            continue
        seen.add(signature)
        fields = used_fields(raw_formula, search_fields)
        rows.append(
            {
                "raw_formula": raw_formula,
                "formula": panda_formula,
                "signature": signature,
                "scale_signature": scale_signature,
                "gp_fitness": fitness,
                "used_fields": fields,
                "distinct_fields": len(fields),
                "historical_exact_match": signature in existing,
                "historical_scale_match": scale_signature in existing_scale_invariant,
                "formula_length": len(panda_formula),
            }
        )
        if len(rows) >= scan_count:
            break
    return payload, rows, len(existing), len(existing_scale_invariant)


def market_cap_tensor(
    frame: pd.DataFrame,
    data: TushareStockData,
) -> torch.Tensor:
    indexed = frame.set_index(["date", "instrument"])
    panel = indexed["total_mv"].unstack("instrument")
    panel = panel.reindex(index=data._evaluation_dates, columns=data._stock_ids)
    return torch.tensor(panel.to_numpy(dtype=np.float32), dtype=torch.float32, device=data.device)


def evaluate_rows(
    rows: list[dict[str, Any]],
    *,
    data: TushareStockData,
    context: AlignedNetExcessContext,
    market_cap: torch.Tensor,
    namespace: dict[str, object],
) -> None:
    signal_positions = context.signal_data_positions
    cap_signal = market_cap[signal_positions]
    for index, row in enumerate(rows, start=1):
        if row["historical_exact_match"]:
            row["decision"] = "reject_exact_historical_formula"
            continue
        if row["historical_scale_match"]:
            row["decision"] = "reject_scale_invariant_historical_formula"
            continue
        try:
            expression = evaluate_formula(row["raw_formula"], namespace)
            with torch.no_grad():
                factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
                full = context.score(factor)
                split_stats = {
                    name: context.score(
                        factor,
                        start_date=parse_date(start),
                        end_date=parse_date(end),
                    )
                    for name, start, end in SPLITS
                }
                factor_signal = factor[signal_positions]
                size_corr = batch_spearmanr_linear(factor_signal, cap_signal)
                size_corr = torch.nanmean(size_corr)
            row.update(
                {
                    "full_net_excess": full.get("net_excess"),
                    "full_gross_excess": full.get("gross_excess"),
                    "full_turnover": full.get("turnover"),
                    "full_annual_cost": full.get("annual_cost"),
                    "size_rank_corr": float(size_corr.item()) if torch.isfinite(size_corr) else None,
                    "split_stats": split_stats,
                }
            )
            valid_net = number(split_stats["valid"].get("net_excess"))
            test_net = number(split_stats["test"].get("net_excess"))
            full_net = number(full.get("net_excess"))
            size_value = number(row.get("size_rank_corr"))
            if full_net is None or full_net <= 0:
                row["decision"] = "reject_nonpositive_full_net"
            elif valid_net is None or valid_net <= 0 or test_net is None or test_net <= 0:
                row["decision"] = "reject_nonpositive_valid_or_test_net"
            elif size_value is None or abs(size_value) >= 0.45:
                row["decision"] = "reject_size_exposure"
            else:
                row["decision"] = "eligible_local_screen"
        except Exception as exc:
            row["decision"] = "reject_evaluation_error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        print(f"audited={index}/{len(rows)} decision={row['decision']} formula={row['formula'][:160]}", flush=True)

    # GP often emits the same rank signal with different non-zero constants or
    # a different ordering of a division chain. Keep the highest-fitness member
    # of each scale-invariant signal in the final candidate set.
    best_by_scale: dict[str, dict[str, Any]] = {}
    for row in rows:
        scale_signature = row.get("scale_signature")
        if not scale_signature or row.get("historical_scale_match"):
            continue
        current = best_by_scale.get(scale_signature)
        if current is None or float(row.get("gp_fitness") or -1.0) > float(current.get("gp_fitness") or -1.0):
            best_by_scale[scale_signature] = row
    for row in rows:
        scale_signature = row.get("scale_signature")
        best = best_by_scale.get(scale_signature) if scale_signature else None
        if best is not None and best is not row and row.get("decision") == "eligible_local_screen":
            row["decision"] = "reject_scale_invariant_batch_duplicate"
            row["duplicate_of"] = best.get("formula")


def flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key != "split_stats" and key != "used_fields"}
    result["used_fields"] = ",".join(row.get("used_fields", []))
    for split_name in ("train", "valid", "test"):
        stats = row.get("split_stats", {}).get(split_name, {})
        for key in ("periods", "net_excess", "gross_excess", "turnover", "annual_cost"):
            result[f"{split_name}_{key}"] = stats.get(key)
    return result


def write_outputs(output: Path, payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_path = output.with_suffix(".json")
    json_path.write_text(json.dumps({**payload, "candidates": rows}, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    flat = pd.DataFrame([flatten_row(row) for row in rows])
    flat.to_csv(output.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    eligible = [row for row in rows if row.get("decision") == "eligible_local_screen"]
    lines = [
        "# GP candidate novelty audit",
        "",
        "- This is an offline local audit; it does not create or run PandaAI factors.",
        f"- Scanned unique GP expressions: `{len(rows)}`; eligible after historical scale dedup, split, and size screens: `{len(eligible)}`.",
        f"- Split windows: train `{SPLITS[0][1]}..{SPLITS[0][2]}`, valid `{SPLITS[1][1]}..{SPLITS[1][2]}`, test `{SPLITS[2][1]}..{SPLITS[2][2]}`.",
        "- Local screen: full/valid/test net excess > 0; absolute daily size RankIC < 0.45; historical exact and scale-invariant signatures absent; batch scale duplicates removed.",
        "",
        "| rank | decision | formula | fields | full net | train net | valid net | test net | size RankIC | turnover |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    ordered = sorted(rows, key=lambda row: (row.get("decision") != "eligible_local_screen", -(number(row.get("full_net_excess")) or -999.0)))
    for index, row in enumerate(ordered, start=1):
        def pct(value: Any) -> str:
            parsed = number(value)
            return "n/a" if parsed is None else f"{parsed * 100:.2f}%"

        lines.append(
            f"| {index} | `{row.get('decision')}` | `{row.get('formula')}` | `{','.join(row.get('used_fields', []))}` | "
            f"{pct(row.get('full_net_excess'))} | {pct(row.get('split_stats', {}).get('train', {}).get('net_excess'))} | "
            f"{pct(row.get('split_stats', {}).get('valid', {}).get('net_excess'))} | {pct(row.get('split_stats', {}).get('test', {}).get('net_excess'))} | "
            f"{pct(row.get('size_rank_corr'))} | {pct(row.get('full_turnover'))} |"
        )
    lines.extend(
        [
            "",
        "The JSON/CSV files retain rejected candidates and their reasons. A formula that differs only by a normalized algebraic, scalar, or idempotent rolling rewrite is one signal, not a new factor.",
        ]
    )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gp-run", type=Path, default=DEFAULT_GP_RUN)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--scan-count", type=int, default=200)
    args = parser.parse_args()

    gp_payload, rows, existing_count, existing_scale_count = load_unique_candidates(
        args.gp_run.resolve(), args.registry.resolve(), args.scan_count
    )
    calendar = load_trade_dates(args.cache_root.resolve())
    start = parse_date(ALIGNMENT_START)
    end = parse_date(ALIGNMENT_END)
    data_start = parse_date(ALIGNMENT_DATA_START)
    frame = load_full_a_data(args.batch_root.resolve(), args.cap_root.resolve(), data_start, end)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    analysis_calendar = [date for date in calendar if data_start <= date <= end]
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data = TushareStockData.from_aligned_frame(
        frame=frame,
        calendar=analysis_calendar,
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
        calendar=analysis_calendar,
        data=data,
        start_date=start,
        end_date=end,
        cycle=5,
        label_offset=ALIGNMENT_LABEL_OFFSET,
        groups=ALIGNMENT_GROUPS,
        round_trip_cost=ALIGNMENT_ROUND_TRIP_COST,
    )
    cap = market_cap_tensor(frame, data)
    evaluate_rows(rows, data=data, context=context, market_cap=cap, namespace=expression_namespace())
    audit_payload = {
        "alignment": {
            "universe": ALIGNMENT_UNIVERSE,
            "data_start": data_start,
            "start": start,
            "end": end,
            "cycle": 5,
            "label_offset": ALIGNMENT_LABEL_OFFSET,
            "groups": ALIGNMENT_GROUPS,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        },
        "sources": {
            "gp_run": args.gp_run.resolve(),
            "formula_registry": args.registry.resolve(),
        },
        "gp_settings": gp_payload.get("settings", {}),
        "historical_registry_signature_count": existing_count,
        "historical_scale_invariant_signature_count": existing_scale_count,
        "scanned_unique_expression_count": len(rows),
    }
    write_outputs(args.output.resolve(), audit_payload, rows)
    print(f"report={args.output.with_suffix('.md').resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
