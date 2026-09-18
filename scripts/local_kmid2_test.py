#!/usr/bin/env python3
"""Run an alignment-contract local diagnostic for the Qlib Alpha158 KMID2 factor.

This is intentionally a local-only test for a formula that has no saved
PandaAI result yet.  It reuses the canonical local evaluator but does not
pretend that generated calendar dates are platform signal dates.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_START,
    ALIGNMENT_UNIVERSE,
    alignment_config_snapshot,
    validate_alignment_config,
)
from positive_factor_local_compare import evaluate, panel_close  # noqa: E402
from stfilter_local_recheck import ensure_calendar  # noqa: E402


FORMULA_Q_LIB = "(close-open)/(high-low+1e-12)"
FORMULA_PANDAAI = "(CLOSE-OPEN)/(HIGH-LOW+0.000000000001)"

DEFAULT_CACHE_ROOT = Path(
    os.environ.get(
        "FACTOR_RESEARCH_CACHE_ROOT",
        str(PROJECT_ROOT / "quantlab/.quantlab/cache/research/cn_equity"),
    )
).expanduser()
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports/platform_alignment/kmid2_local_test_20260918"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--price-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT / "tushare_factor_recheck/qfq/daily_batches",
    )
    parser.add_argument(
        "--cap-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT / "tushare_factor_recheck/daily_basic_full_a",
    )
    parser.add_argument("--cycle", type=int, default=5, choices=range(1, 11))
    parser.add_argument(
        "--direction",
        choices=["both", "1", "0"],
        default="both",
        help="1 holds the highest decile; 0 holds the lowest decile",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def local_signal_dates(
    calendar: list[pd.Timestamp],
    start: pd.Timestamp,
    cycle: int,
    label_offset: int,
) -> list[pd.Timestamp]:
    start_position = calendar.index(start)
    return [
        date
        for position, date in enumerate(calendar[start_position:], start=start_position)
        if (position - start_position) % cycle == 0
        and position + label_offset + cycle < len(calendar)
    ]


def finite_json(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, dict):
        return {str(key): finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite_json(item) for item in value]
    if value is pd.NA:
        return None
    return value


def percentage(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# KMID2 本地测试",
        "",
        "该结果是本地诊断，不是 PandaAI 在线回测或平台对齐结果。",
        "",
        f"- 规则版本：`{payload['alignment_rule_version']}`",
        f"- 规则文档：`{payload['alignment_rules_document']}`",
        f"- Qlib 公式：`{payload['formula_qlib']}`",
        f"- PandaAI 写法：`{payload['formula_pandaai']}`",
        f"- 数据：沪深全 A、qfq、`daily_basic.total_mv`，暖机 `{payload['data_start']}`",
        f"- 窗口：`{payload['start_date']}..{payload['end_date']}`",
        f"- 调仓：每 `{payload['cycle']}` 个交易日；信号日期来源为本地交易日历固定步长",
        f"- 标签：`{payload['return_label']}`；分组：10 组；单边成本：0.30%",
        f"- 高低价来源：`{payload['field_sources'].get('high_qfq')}` / `{payload['field_sources'].get('low_qfq')}`",
        "",
        "## 结果",
        "",
        "| 方向 | 持仓组 | 有效期数 | 平均股票数 | RankIC | IC | 毛超额 | 换手 | 年化成本 | 净超额 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in payload["results"]:
        lines.append(
            f"| {result['direction']} | {result['selected_group']} | {result['periods']} | "
            f"{result['stock_count_mean']:.0f} | {result['rank_ic']:.4f} | {result['ic_mean']:.4f} | "
            f"{percentage(result['gross_excess'])} | {percentage(result['turnover'])} | "
            f"{percentage(result['annual_cost'])} | {percentage(result['net_excess'])} |"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 方向 1 测试收盘位于当日振幅高位的股票，方向 0 测试低位股票。",
            "- 结果使用本地实际分组成员计算换手；没有平台换手、平台 Top20 或平台净超额可供比较。",
            "- 该公式的分母在日内高低价相等时由 `1e-12` 防止除零；高低价若使用缓存代理，已在上方明确标记。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    alignment_config = alignment_config_snapshot()
    validate_alignment_config(alignment_config)
    data_start = pd.Timestamp(ALIGNMENT_DATA_START)
    start = pd.Timestamp(ALIGNMENT_START)
    end = pd.Timestamp(ALIGNMENT_END)
    calendar = ensure_calendar(data_start, end, token=None)
    signal_dates = local_signal_dates(calendar, start, args.cycle, ALIGNMENT_LABEL_OFFSET)
    if not signal_dates:
        raise RuntimeError("No valid local signal dates were generated")

    frame = load_full_a_data(args.price_root, args.cap_root, data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    close = panel_close(frame, calendar)
    factor_values = (
        frame["close_qfq"] - frame["open_qfq"]
    ).div(frame["high_qfq"] - frame["low_qfq"] + 1e-12)

    directions = [1, 0] if args.direction == "both" else [int(args.direction)]
    results: list[dict[str, Any]] = []
    for direction in directions:
        result = evaluate(
            frame,
            factor_values,
            close,
            {"top": [], "group_metrics": {}, "metrics": {}},
            direction,
            signal_dates,
            calendar,
            args.cycle,
            ALIGNMENT_LABEL_OFFSET,
            handler=None,
        )
        result.update(
            {
                "direction": direction,
                "selected_group": result["selected_group"],
                "signal_date_source": "generated_calendar_fixed_cycle",
            }
        )
        results.append(result)

    payload = {
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment_config": alignment_config,
        "universe": ALIGNMENT_UNIVERSE,
        "data_start": data_start.strftime("%Y%m%d"),
        "start_date": start.strftime("%Y%m%d"),
        "end_date": end.strftime("%Y%m%d"),
        "cycle": args.cycle,
        "return_label": f"close(t+{ALIGNMENT_LABEL_OFFSET}) -> close(t+{ALIGNMENT_LABEL_OFFSET}+{args.cycle})",
        "groups": 10,
        "one_way_cost": 0.003,
        "formula_qlib": FORMULA_Q_LIB,
        "formula_pandaai": FORMULA_PANDAAI,
        "field_sources": frame.attrs.get("market_field_sources", {}),
        "signal_date_source": "generated_calendar_fixed_cycle",
        "signal_periods": len(signal_dates),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(
        json.dumps(finite_json(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output.with_suffix(".md").write_text(build_markdown(payload), encoding="utf-8")
    print(f"output={args.output.with_suffix('.json')}")
    print(f"output={args.output.with_suffix('.md')}")
    print(f"rows={len(frame)} stocks={frame['instrument'].nunique()} periods={len(signal_dates)}")
    for result in results:
        print(
            f"direction={result['direction']} periods={result['periods']} "
            f"rank_ic={result['rank_ic']:.6f} ic={result['ic_mean']:.6f} "
            f"gross={percentage(result['gross_excess'])} turnover={percentage(result['turnover'])} "
            f"cost={percentage(result['annual_cost'])} net={percentage(result['net_excess'])}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
