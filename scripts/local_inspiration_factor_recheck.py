#!/usr/bin/env python3
"""Recheck hand-built inspiration factors on the aligned local Tushare panel.

This is deliberately a small, deterministic companion to the AlphaPROBE GP
runner.  It evaluates three fixed composite hypotheses, including a manual
cross-sectional ZSCORE implementation, and scores them with the same
``AlignedNetExcessContext`` used by the drawdown-controlled local search.
It never calls PandaAI.
"""

from __future__ import annotations

import argparse
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
    batch_pearsonr,
    batch_spearmanr_linear,
    evaluate_formula,
    expression_namespace,
    finite_as_nan,
    load_trade_dates,
    parse_date,
)
from full_a_local_data import load_full_a_data  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    alignment_config_snapshot,
    validate_alignment_config,
)


DEFAULT_CACHE_ROOT = (
    PROJECT_ROOT
    / "quantlab"
    / ".quantlab"
    / "cache"
    / "research"
    / "cn_equity"
)
DEFAULT_OUTPUT = DEFAULT_CACHE_ROOT / "reports" / "local_inspiration_factors_20260918"
DEFAULT_BATCH_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = DEFAULT_CACHE_ROOT / "financial_full_a"

ABSOLUTE_DD_TARGET = 0.30
EXCESS_DD_TARGET = 0.15
ABSOLUTE_DD_WEIGHT = 0.50
EXCESS_DD_WEIGHT = 0.25
ABSOLUTE_DD_CEILING = 0.45
EXCESS_DD_CEILING = 0.25


COMPONENT_FORMULAS = {
    "reversal40": "(1-RETURNS(CLOSE,40))",
    "vwap_gap250": "((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)",
    "low_turnover40": "(1-WMA(TURNOVER,40)/MA(TURNOVER,504))",
    "value_quality": "((RANK(BOOK_TO_MARKET_RATIO_LYR)+RANK(OPER_ROE_LYR))/2)",
    "small_size": "(-MARKET_CAP)",
    "popularity40": "((WMA(TURNOVER,40)/MA(TURNOVER,504)+WMA(VOLUME,40)/MA(VOLUME,504))/2)",
}

PANDA_FORMULAS = {
    "INSPIRE-Z40-3": (
        "(ZSCORE(1-RETURNS(CLOSE,40))"
        "+ZSCORE((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)"
        "+ZSCORE(1-WMA(TURNOVER,40)/MA(TURNOVER,504)))/3"
    ),
    "INSPIRE-FIVE-RANK": (
        "(RANK(1-RETURNS(CLOSE,40))"
        "+RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)"
        "+RANK(1-WMA(TURNOVER,40)/MA(TURNOVER,504))"
        "+RANK((RANK(BOOK_TO_MARKET_RATIO_LYR)+RANK(OPER_ROE_LYR))/2)"
        "+RANK(-MARKET_CAP))/5"
    ),
    "INSPIRE-CORE-POP": (
        "0.40*RANK(1-RETURNS(CLOSE,40))"
        "+0.25*RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1)"
        "+0.20*RANK((RANK(BOOK_TO_MARKET_RATIO_LYR)+RANK(OPER_ROE_LYR))/2)"
        "+0.15*RANK(-MARKET_CAP)"
        "-0.25*RANK((WMA(TURNOVER,40)/MA(TURNOVER,504)"
        "+WMA(VOLUME,40)/MA(VOLUME,504))/2)"
    ),
}


def json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def cross_sectional_zscore(values: torch.Tensor) -> torch.Tensor:
    """Apply PandaAI's cross-sectional ZSCORE semantics day by day."""
    valid = torch.isfinite(values)
    count = valid.sum(dim=1, keepdim=True).to(dtype=values.dtype)
    safe = torch.where(valid, values, torch.zeros_like(values))
    mean = safe.sum(dim=1, keepdim=True) / count.clamp_min(1.0)
    centered = torch.where(valid, values - mean, torch.zeros_like(values))
    variance = (centered * centered).sum(dim=1, keepdim=True) / count.clamp_min(1.0)
    std = torch.sqrt(variance)
    result = centered / std.clamp_min(torch.finfo(values.dtype).eps)
    return result.masked_fill(~valid | (count < 2) | (std <= torch.finfo(values.dtype).eps), torch.nan)


def evaluate_expression(formula: str, namespace: dict[str, object], data: TushareStockData) -> torch.Tensor:
    expression = evaluate_formula(formula, namespace)
    return finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]


def mean_finite(values: torch.Tensor) -> float | None:
    finite = values[torch.isfinite(values)]
    if finite.numel() == 0:
        return None
    return float(finite.mean().detach().item())


def factor_ic(
    context: AlignedNetExcessContext,
    factor: torch.Tensor,
) -> dict[str, float | int | None]:
    factor_rows = factor[context.signal_data_positions]
    returns = context.forward_returns
    valid = torch.isfinite(factor_rows) & context.signal_eligible & torch.isfinite(returns)
    counts = valid.sum(dim=1)
    keep = counts >= context.groups * 10
    if not bool(keep.any().item()):
        return {"ic": None, "rank_ic": None, "ic_periods": 0}
    ic = batch_pearsonr(factor_rows[keep], returns[keep])
    rank_ic = batch_spearmanr_linear(factor_rows[keep], returns[keep])
    return {
        "ic": mean_finite(ic),
        "rank_ic": mean_finite(rank_ic),
        "ic_periods": int(keep.sum().item()),
    }


def risk_score(stats: dict[str, Any]) -> float | None:
    net = stats.get("net_excess")
    absolute_dd = stats.get("absolute_max_drawdown")
    excess_dd = stats.get("excess_max_drawdown")
    if net is None or absolute_dd is None or excess_dd is None:
        return None
    if absolute_dd > ABSOLUTE_DD_CEILING or excess_dd > EXCESS_DD_CEILING:
        return None
    return float(net) - ABSOLUTE_DD_WEIGHT * float(absolute_dd) - EXCESS_DD_WEIGHT * float(excess_dd)


def build_candidates(
    namespace: dict[str, object],
    data: TushareStockData,
) -> dict[str, torch.Tensor]:
    components = {
        name: evaluate_expression(formula, namespace, data)
        for name, formula in COMPONENT_FORMULAS.items()
    }
    ranked = {
        name: evaluate_expression(f"RANK({formula})", namespace, data)
        for name, formula in COMPONENT_FORMULAS.items()
    }
    z_components = {
        name: cross_sectional_zscore(components[name])
        for name in ("reversal40", "vwap_gap250", "low_turnover40")
    }
    return {
        "INSPIRE-Z40-3": (
            z_components["reversal40"]
            + z_components["vwap_gap250"]
            + z_components["low_turnover40"]
        ) / 3.0,
        "INSPIRE-FIVE-RANK": (
            ranked["reversal40"]
            + ranked["vwap_gap250"]
            + ranked["low_turnover40"]
            + ranked["value_quality"]
            + ranked["small_size"]
        ) / 5.0,
        "INSPIRE-CORE-POP": (
            0.40 * ranked["reversal40"]
            + 0.25 * ranked["vwap_gap250"]
            + 0.20 * ranked["value_quality"]
            + 0.15 * ranked["small_size"]
            - 0.25 * ranked["popularity40"]
        ),
    }


def candidate_correlations(
    candidates: dict[str, torch.Tensor],
    context: AlignedNetExcessContext,
) -> dict[str, dict[str, float | None]]:
    names = list(candidates)
    result: dict[str, dict[str, float | None]] = {name: {} for name in names}
    positions = context.signal_data_positions
    for index, left_name in enumerate(names):
        left = candidates[left_name][positions]
        for right_name in names[index + 1 :]:
            right = candidates[right_name][positions]
            value = mean_finite(batch_spearmanr_linear(left, right))
            result[left_name][right_name] = value
            result[right_name][left_name] = value
    return result


def format_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def write_report(
    output: Path,
    payload: dict[str, Any],
) -> None:
    rows = sorted(
        payload["candidates"],
        key=lambda row: (
            row["risk_adjusted_score"] is None,
            -(row["risk_adjusted_score"] or -999.0),
            -(row["net_excess"] or -999.0),
        ),
    )
    lines = [
        "# Local inspiration-factor recheck",
        "",
        f"- Alignment rule: `{payload['alignment']['rule_version']}`",
        f"- Window: `{payload['alignment']['start']}..{payload['alignment']['end']}`; cycle `{payload['alignment']['cycle']}`; groups `{payload['alignment']['groups']}`",
        "- Universe: `沪深全A`; qfq; `daily_basic.total_mv`; label `close(t+1) -> close(t+cycle+1)`; benchmark `factor_valid`",
        "- Net excess: arithmetic annualized gross excess minus annualized cost from local actual selected-member turnover",
        "- Drawdown: absolute portfolio and relative-equity excess drawdown; the latter is a local proxy",
        "- `OPER_ROE_LYR` and `BOOK_TO_MARKET_RATIO_LYR` use the existing PIT local field/proxy mappings",
        "",
        "## Results",
        "",
        "| rank | candidate | net excess | gross excess | turnover | annual cost | abs max DD | excess max DD | risk score | RankIC | coverage |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | `{row['name']}` | {format_pct(row['net_excess'])} | "
            f"{format_pct(row['gross_excess'])} | {format_pct(row['turnover'])} | "
            f"{format_pct(row['annual_cost'])} | {format_pct(row['absolute_max_drawdown'])} | "
            f"{format_pct(row['excess_max_drawdown'])} | {format_pct(row['risk_adjusted_score'])} | "
            f"{row['rank_ic'] if row['rank_ic'] is not None else 'n/a'} | "
            f"{format_pct(row['coverage'])} |"
        )
    lines.extend(["", "## PandaAI formulas", ""])
    for name, formula in PANDA_FORMULAS.items():
        lines.extend([f"### `{name}`", "", "```text", formula, "```", ""])
    lines.extend(["## Pairwise daily cross-sectional Spearman", "", "| factor | factor | mean rho |", "| --- | --- | ---: |"])
    for left, values in payload["pairwise_correlation"].items():
        for right, value in values.items():
            if left < right:
                lines.append(f"| `{left}` | `{right}` | {value if value is not None else 'n/a'} |")
    lines.extend(["", "## Selection note", "", "- Risk score = net excess - 0.50 x absolute max DD - 0.25 x excess max DD.", "- A high net result with an excessive drawdown ceiling is retained in the raw table but is not risk-score eligible.", "- This is local research only; no PandaAI factor was created or run.", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
    parser.add_argument("--start", default=str(ALIGNMENT_START))
    parser.add_argument("--end", default=str(ALIGNMENT_END))
    parser.add_argument("--data-start", default=str(ALIGNMENT_DATA_START))
    parser.add_argument("--cycle", type=int, default=5)
    parser.add_argument("--groups", type=int, default=ALIGNMENT_GROUPS)
    parser.add_argument("--label-offset", type=int, default=ALIGNMENT_LABEL_OFFSET)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end)
    data_start = parse_date(args.data_start)
    if args.cycle < 1 or args.cycle > 10:
        raise ValueError("--cycle must be between 1 and 10")
    if args.groups < 2 or args.groups > 10:
        raise ValueError("--groups must be between 2 and 10")
    alignment = alignment_config_snapshot()
    alignment.update(
        {
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "data_start": data_start.strftime("%Y%m%d"),
            "groups": args.groups,
            "label_offset": args.label_offset,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        }
    )
    validate_alignment_config(alignment)

    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache_root = args.cache_root.expanduser().resolve()
    batch_root = args.batch_root.expanduser().resolve()
    cap_root = args.cap_root.expanduser().resolve()
    financial_root = args.financial_root.expanduser().resolve()

    calendar = load_trade_dates(cache_root)
    frame = load_full_a_data(batch_root, cap_root, data_start, end)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    instruments = sorted(frame["instrument"].astype(str).unique())
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        print(f"[note] {device} unavailable; falling back to cpu", flush=True)
        device = torch.device("cpu")

    print(f"rows={len(frame)} instruments={len(instruments)} device={device}", flush=True)
    data = TushareStockData.from_aligned_frame(
        frame=frame,
        calendar=calendar,
        instrument=instruments,
        start_time=start.strftime("%Y-%m-%d"),
        end_time=end.strftime("%Y-%m-%d"),
        max_backtrack_days=756,
        max_future_days=0,
        device=device,
        financial_root=financial_root,
    )
    context = AlignedNetExcessContext(
        frame=frame,
        calendar=calendar,
        data=data,
        start_date=start,
        end_date=end,
        cycle=args.cycle,
        label_offset=args.label_offset,
        groups=args.groups,
        round_trip_cost=ALIGNMENT_ROUND_TRIP_COST,
    )
    print(f"signal_dates={len(context.signal_dates)}", flush=True)
    namespace = expression_namespace()
    with torch.no_grad():
        candidates = build_candidates(namespace, data)

    rows: list[dict[str, Any]] = []
    for name, factor in candidates.items():
        print(f"scoring={name}", flush=True)
        with torch.no_grad():
            stats = context.score(factor)
            ic = factor_ic(context, factor)
            risk = risk_score(stats)
            coverage = (
                float(stats["periods"]) / len(context.signal_dates)
                if stats.get("periods") is not None
                else None
            )
            row = {
                "name": name,
                "panda_formula": PANDA_FORMULAS[name],
                **stats,
                "risk_adjusted_score": risk,
                "coverage": coverage,
                **ic,
            }
            rows.append(row)
        print(
            f"{name} net={format_pct(row['net_excess'])} abs_dd={format_pct(row['absolute_max_drawdown'])} "
            f"excess_dd={format_pct(row['excess_max_drawdown'])} rank_ic={row['rank_ic']}",
            flush=True,
        )

    payload = {
        "status": "completed",
        "method": "fixed inspiration-factor local recheck",
        "data_source": "local Tushare full-A qfq + daily_basic + PIT financial cache",
        "alignment": {
            "rule_version": ALIGNMENT_RULE_VERSION,
            "start": start,
            "end": end,
            "data_start": data_start,
            "cycle": args.cycle,
            "groups": args.groups,
            "label_offset": args.label_offset,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "universe": "full_a",
            "market_cap_field": "total_mv",
            "benchmark": "factor_valid",
        },
        "data": {
            "rows": len(frame),
            "instruments": len(instruments),
            "signal_dates": len(context.signal_dates),
            "device": str(device),
            "frame_sources": frame.attrs.get("market_field_sources", {}),
        },
        "candidates": rows,
        "pairwise_correlation": candidate_correlations(candidates, context),
        "panda_formulas": PANDA_FORMULAS,
        "component_formulas": COMPONENT_FORMULAS,
        "drawdown_control": {
            "absolute_dd_target": ABSOLUTE_DD_TARGET,
            "excess_dd_target": EXCESS_DD_TARGET,
            "absolute_dd_weight": ABSOLUTE_DD_WEIGHT,
            "excess_dd_weight": EXCESS_DD_WEIGHT,
            "absolute_dd_ceiling": ABSOLUTE_DD_CEILING,
            "excess_dd_ceiling": EXCESS_DD_CEILING,
            "excess_dd_definition": "relative portfolio equity drawdown against factor_valid benchmark; local proxy",
        },
    }
    write_json(output / "results.json", payload)
    pd.DataFrame(rows).to_csv(output / "results.csv", index=False, encoding="utf-8-sig")
    write_report(output, payload)
    print(f"output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
