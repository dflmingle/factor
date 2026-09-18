#!/usr/bin/env python3
"""Score a fixed set of low-alignment-risk PandaAI formulas locally."""

from __future__ import annotations

import argparse
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
    batch_pearsonr,
    batch_spearmanr_linear,
    evaluate_formula,
    expression_namespace,
    finite_as_nan,
    load_trade_dates,
    parse_date,
)
from alphagen.data.expression import UnaryOperator  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from local_inspiration_factor_recheck import (  # noqa: E402
    cross_sectional_zscore,
    mean_finite,
)
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


DEFAULT_CACHE_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
DEFAULT_CANDIDATES = PROJECT_ROOT / "local-safe-financial-candidates.txt"
DEFAULT_OUTPUT = DEFAULT_CACHE_ROOT / "reports" / "local_safe_financial_candidates_20260918"
DEFAULT_BATCH_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = DEFAULT_CACHE_ROOT / "financial_full_a"

DISALLOWED_FIELDS = {
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "turnover",
    "market_cap",
    "gr_net_profit_ttm",
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def read_candidates(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("~")]
        if len(parts) not in {2, 3}:
            raise ValueError(f"{path}:{line_number}: expected name ~ formula [~ direction]")
        rows.append(
            {
                "name": parts[0],
                "formula": parts[1],
                "direction": int(parts[2]) if len(parts) == 3 else 1,
            }
        )
    if not rows:
        raise ValueError(f"No candidates found in {path}")
    return rows


def disallowed_fields(formula: str) -> list[str]:
    tokens = {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)}
    return sorted(tokens.intersection(DISALLOWED_FIELDS))


def factor_ic(context: AlignedNetExcessContext, factor: torch.Tensor) -> dict[str, float | int | None]:
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
    values = [stats.get(key) for key in ("net_excess", "absolute_max_drawdown", "excess_max_drawdown")]
    if any(value is None or not np.isfinite(float(value)) for value in values):
        return None
    return float(values[0]) - 0.50 * float(values[1]) - 0.25 * float(values[2])


class CrossSectionalZScore(UnaryOperator):
    """Expression wrapper for PandaAI's per-date cross-sectional ZSCORE."""

    def _apply(self, operand: torch.Tensor) -> torch.Tensor:
        return cross_sectional_zscore(operand)


def pct(value: Any) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
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

    candidates = read_candidates(args.candidates.expanduser().resolve())
    for candidate in candidates:
        forbidden = disallowed_fields(candidate["formula"])
        if forbidden:
            raise ValueError(f"{candidate['name']} contains excluded fields: {', '.join(forbidden)}")

    start = parse_date(args.start)
    end = parse_date(args.end)
    data_start = parse_date(args.data_start)
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

    cache_root = args.cache_root.expanduser().resolve()
    calendar = load_trade_dates(cache_root)
    frame = load_full_a_data(
        args.batch_root.expanduser().resolve(),
        args.cap_root.expanduser().resolve(),
        data_start,
        end,
    ).sort_values(["instrument", "date"], ignore_index=True)
    instruments = sorted(frame["instrument"].astype(str).unique())
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
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
        financial_root=args.financial_root.expanduser().resolve(),
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
    print(f"signal_dates={len(context.signal_dates)} candidates={len(candidates)}", flush=True)
    namespace = expression_namespace()
    namespace["ZSCORE"] = CrossSectionalZScore
    namespace["ZScore"] = CrossSectionalZScore

    evaluated: dict[str, torch.Tensor] = {}
    output_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        name = candidate["name"]
        print(f"scoring={name}", flush=True)
        expression = evaluate_formula(candidate["formula"], namespace)
        with torch.no_grad():
            factor = finite_as_nan(expression.evaluate(data))  # type: ignore[attr-defined]
            evaluated[name] = factor
            stats = context.score(factor)
            early = context.score(factor, start_date=pd.Timestamp("2021-09-07"), end_date=pd.Timestamp("2024-12-31"))
            late = context.score(factor, start_date=pd.Timestamp("2025-01-01"), end_date=end)
            row = {
                **candidate,
                "panda_formula": candidate["formula"],
                **stats,
                "risk_adjusted_score": risk_score(stats),
                "coverage": float(stats["periods"]) / len(context.signal_dates) if stats.get("periods") else 0.0,
                "rank_ic": factor_ic(context, factor)["rank_ic"],
                "early_net_excess": early.get("net_excess"),
                "late_net_excess": late.get("net_excess"),
                "early_abs_max_drawdown": early.get("absolute_max_drawdown"),
                "late_abs_max_drawdown": late.get("absolute_max_drawdown"),
            }
            output_rows.append(row)
        print(f"{name} net={pct(row['net_excess'])} abs_dd={pct(row['absolute_max_drawdown'])} excess_dd={pct(row['excess_max_drawdown'])}", flush=True)

    names = list(evaluated)
    correlations: list[dict[str, Any]] = []
    positions = context.signal_data_positions
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            with torch.no_grad():
                value = mean_finite(batch_spearmanr_linear(evaluated[left][positions], evaluated[right][positions]))
            correlations.append({"left": left, "right": right, "mean_daily_cross_sectional_spearman": value})

    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "completed",
        "method": "low-alignment-risk fixed financial composite recheck",
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment": {
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
        "excluded_fields": sorted(DISALLOWED_FIELDS),
        "candidates": output_rows,
        "correlations": correlations,
        "data": {"rows": len(frame), "instruments": len(instruments), "signal_dates": len(context.signal_dates), "device": str(device)},
    }
    write_json(output / "results.json", payload)
    pd.DataFrame(output_rows).sort_values(["risk_adjusted_score", "net_excess"], ascending=False).to_csv(output / "results.csv", index=False, encoding="utf-8-sig")

    ranked = sorted(output_rows, key=lambda row: (row["risk_adjusted_score"] is None, -(row["risk_adjusted_score"] or -999.0), -(row["net_excess"] or -999.0)))
    lines = [
        "# Low-alignment-risk financial composite recheck",
        "",
        f"- Alignment: `{start:%Y-%m-%d}..{end:%Y-%m-%d}`; cycle `{args.cycle}`; groups `{args.groups}`; label `close(t+1) -> close(t+cycle+1)`",
        "- Universe: full-A `.SH/.SZ`; qfq; `daily_basic.total_mv`; benchmark `factor_valid`; one-way cost `0.30%`",
        f"- Alignment rule: `{ALIGNMENT_RULE_VERSION}`",
        "- Excluded from every candidate: `open`, `close`, `high`, `low`, `volume`, `amount`, `turnover`, `market_cap`, `gr_net_profit_ttm`",
        "- `ZSCORE` is local daily cross-sectional standardization; all financial fields remain explicitly marked as direct/derived/proxy in the field coverage registry.",
        "",
        "| rank | candidate | net excess | abs max DD | excess max DD | turnover | risk score | early net | late net | RankIC |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(ranked, 1):
        lines.append(
            f"| {index} | `{row['name']}` | {pct(row['net_excess'])} | {pct(row['absolute_max_drawdown'])} | {pct(row['excess_max_drawdown'])} | {pct(row['turnover'])} | {pct(row['risk_adjusted_score'])} | {pct(row['early_net_excess'])} | {pct(row['late_net_excess'])} | {row['rank_ic'] if row['rank_ic'] is not None else 'n/a'} |"
        )
    lines.extend(["", "## Formulas", ""])
    for row in ranked:
        lines.extend([f"### `{row['name']}`", "", "```text", row["formula"], "```", ""])
    lines.extend(["## Pairwise correlations", "", "| left | right | mean daily cross-sectional Spearman |", "| --- | --- | ---: |"])
    for row in sorted(correlations, key=lambda item: abs(item["mean_daily_cross_sectional_spearman"] or 0), reverse=True)[:30]:
        lines.append(f"| `{row['left']}` | `{row['right']}` | {row['mean_daily_cross_sectional_spearman']} |")
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
