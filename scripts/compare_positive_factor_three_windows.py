#!/usr/bin/env python3
"""Build a three-window report for saved platform-positive factor records.

This script is intentionally report-only. It reads existing JSON snapshots and
does not contact PandaAI, Tushare, or start a local factor calculation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIVE_YEAR = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports"
    / "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_turnoverdiag1_qualitygate1"
    / "all_factor_local_compare.json"
)
DEFAULT_2026 = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/positive-factor-recent-20260918"
    / "positive_factor_recent_local_compare.json"
)
DEFAULT_JUNE = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/positive-factor-recent-20260919-0601"
    / "positive_factor_recent_local_compare.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "research_reports/platform_alignment/positive-factor-three-window-comparison-20260920"
)

ALIGNMENT_RULE_VERSION = (
    "full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1"
)


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def percent(value: Any, *, fraction: bool = False) -> float | None:
    result = number(value)
    if result is None:
        return None
    return result * 100.0 if fraction else result


def text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def all_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("results", "unsupported"):
        values = payload.get(key, [])
        if isinstance(values, list):
            rows.extend(row for row in values if isinstance(row, dict))
    return rows


def positive_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in all_rows(payload)
        if (platform_net := number(row.get("platform_net_excess_pct"))) is not None
        and platform_net > 0.0
    ]


def by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {text(row.get("id")): row for row in rows if row.get("id") is not None}


def row_value(row: dict[str, Any] | None, *keys: str) -> Any:
    if not row:
        return None
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def cycle(row: dict[str, Any] | None) -> Any:
    return row_value(row, "cycle", "configured_cycle", "platform_configured_cycle")


def source_machine(payload: dict[str, Any], *, default: str) -> str:
    settings = payload.get("settings", {})
    profile = settings.get("machine_profile")
    label = settings.get("machine_label")
    if profile and label:
        return f"{profile} / {label}"
    if profile:
        return text(profile)
    return default


def safe_md(value: Any) -> str:
    return text(value, "n/a").replace("|", "\\|").replace("\n", " ")


def display(value: Any, digits: int = 2, suffix: str = "%") -> str:
    value = number(value)
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}{suffix}"


def display_periods(value: Any) -> str:
    value = number(value)
    if value is None:
        return "n/a"
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def local_net(row: dict[str, Any] | None, *, fraction_input: bool) -> float | None:
    if not row:
        return None
    return percent(row.get("local_net_excess"), fraction=True) if fraction_input else percent(
        row.get("recent_net_excess_pct")
    )


def local_gross(row: dict[str, Any] | None, *, fraction_input: bool) -> float | None:
    if not row:
        return None
    return percent(row.get("local_gross_excess"), fraction=True) if fraction_input else percent(
        row.get("recent_gross_excess_pct")
    )


def local_turnover(row: dict[str, Any] | None, *, fraction_input: bool) -> float | None:
    if not row:
        return None
    return percent(row.get("local_turnover"), fraction=True) if fraction_input else percent(
        row.get("recent_turnover_pct")
    )


def local_rank_ic(row: dict[str, Any] | None, *, recent: bool) -> float | None:
    if not row:
        return None
    return number(row.get("recent_rank_ic" if recent else "local_rank_ic"))


def local_periods(row: dict[str, Any] | None, *, recent: bool) -> int | None:
    if not row:
        return None
    value = number(row.get("recent_periods" if recent else "periods"))
    return None if value is None else int(value)


def status_for(
    result: dict[str, Any] | None,
    unsupported: dict[str, Any] | None,
    source: dict[str, Any] | None,
    *,
    missing_label: str,
) -> str:
    if result is not None:
        return "available"
    if unsupported is not None:
        return "unsupported"
    if source is not None:
        return "no_local_value"
    return missing_label


def reason_for(
    result: dict[str, Any] | None,
    unsupported: dict[str, Any] | None,
    *,
    missing_reason: str,
) -> str | None:
    if result is not None:
        return None
    if unsupported is not None:
        return text(unsupported.get("reason"), "unsupported without a reason")
    return missing_reason


def actual_dates(payload: dict[str, Any]) -> str:
    settings = payload.get("settings", {})
    start = settings.get("recent_signal_dates_min")
    end = settings.get("recent_signal_dates_max")
    if start and end:
        return f"{start} to {end}"
    if settings.get("recent_start") and settings.get("end"):
        return f"requested {settings['recent_start']} to {settings['end']}; per-factor usable dates vary"
    return "per-factor usable dates vary"


def formal_dates(payload: dict[str, Any]) -> str:
    rows = payload.get("results", [])
    for row in rows:
        if row.get("platform_start_date") and row.get("platform_end_date"):
            return f"{row['platform_start_date']} to {row['platform_end_date']}"
    return "20210907 to 20260907"


def build_rows(
    full_payload: dict[str, Any],
    recent_payload: dict[str, Any],
    june_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    latest_positive = positive_rows(june_payload)
    full_results = by_id(
        [
            row
            for row in full_payload.get("results", [])
            if isinstance(row, dict)
            and (net := number(row.get("platform_net_excess_pct"))) is not None
            and net > 0.0
        ]
    )
    full_unsupported = by_id(
        [row for row in full_payload.get("unsupported", []) if isinstance(row, dict)]
    )
    recent_results = by_id(
        [row for row in recent_payload.get("results", []) if isinstance(row, dict)]
    )
    recent_unsupported = by_id(
        [row for row in recent_payload.get("unsupported", []) if isinstance(row, dict)]
    )
    june_results = by_id(
        [row for row in june_payload.get("results", []) if isinstance(row, dict)]
    )
    june_unsupported = by_id(
        [row for row in june_payload.get("unsupported", []) if isinstance(row, dict)]
    )

    rows: list[dict[str, Any]] = []
    for latest in latest_positive:
        record_id = text(latest.get("id"))
        full = full_results.get(record_id)
        full_missing = None if full or record_id in full_unsupported else "not in canonical five-year report"
        full_local = full if local_net(full, fraction_input=True) is not None else None
        recent = recent_results.get(record_id)
        recent_missing = None if recent or record_id in recent_unsupported else "not in the 2026 window report"
        recent_local = recent if local_net(recent, fraction_input=False) is not None else None
        june = june_results.get(record_id)
        june_local = june if local_net(june, fraction_input=False) is not None else None

        rows.append(
            {
                "id": record_id,
                "name": row_value(latest, "name") or row_value(full, "name") or row_value(recent, "name"),
                "formula": row_value(latest, "formula") or row_value(full, "formula") or row_value(recent, "formula"),
                "handler": row_value(latest, "handler") or row_value(full, "handler") or row_value(recent, "handler"),
                "direction": row_value(latest, "direction") or row_value(full, "platform_factor_direction") or row_value(recent, "direction"),
                "cycle": cycle(latest) or cycle(full) or cycle(recent),
                "platform_five_year_net_pct": number(
                    row_value(latest, "platform_net_excess_pct")
                    or row_value(full, "platform_net_excess_pct")
                    or row_value(recent, "platform_net_excess_pct")
                ),
                "five_year_local_net_pct": local_net(full, fraction_input=True),
                "five_year_local_gross_pct": local_gross(full, fraction_input=True),
                "five_year_turnover_pct": local_turnover(full, fraction_input=True),
                "five_year_rank_ic": local_rank_ic(full, recent=False),
                "five_year_periods": local_periods(full, recent=False),
                "five_year_period_coverage": number(full.get("period_coverage")) if full else None,
                "five_year_alignment_quality": row_value(full, "alignment_quality"),
                "five_year_fidelity": row_value(full, "fidelity"),
                "five_year_turnover_alignment": row_value(full, "turnover_alignment"),
                "five_year_top20_overlap": row_value(full, "top20_overlap"),
                "five_year_status": status_for(
                    full_local,
                    full_unsupported.get(record_id),
                    full,
                    missing_label="not_in_canonical_report",
                ),
                "five_year_reason": reason_for(
                    full_local,
                    full_unsupported.get(record_id),
                    missing_reason=(
                        full_missing
                        or ("result has no local_net_excess" if full else "no five-year local result")
                    ),
                ),
                "recent_2026_local_net_pct": local_net(recent, fraction_input=False),
                "recent_2026_local_gross_pct": local_gross(recent, fraction_input=False),
                "recent_2026_turnover_pct": local_turnover(recent, fraction_input=False),
                "recent_2026_rank_ic": local_rank_ic(recent, recent=True),
                "recent_2026_periods": local_periods(recent, recent=True),
                "recent_2026_start": row_value(recent, "recent_start"),
                "recent_2026_end": row_value(recent, "recent_end"),
                "recent_2026_status": status_for(
                    recent_local,
                    recent_unsupported.get(record_id),
                    recent,
                    missing_label="not_in_window_report",
                ),
                "recent_2026_reason": reason_for(
                    recent_local,
                    recent_unsupported.get(record_id),
                    missing_reason=(
                        recent_missing
                        or ("result has no recent_net_excess_pct" if recent else "no 2026 local result")
                    ),
                ),
                "june_2026_local_net_pct": local_net(june, fraction_input=False),
                "june_2026_local_gross_pct": local_gross(june, fraction_input=False),
                "june_2026_turnover_pct": local_turnover(june, fraction_input=False),
                "june_2026_rank_ic": local_rank_ic(june, recent=True),
                "june_2026_periods": local_periods(june, recent=True),
                "june_2026_start": row_value(june, "recent_start"),
                "june_2026_end": row_value(june, "recent_end"),
                "june_2026_status": status_for(
                    june_local,
                    june_unsupported.get(record_id),
                    june,
                    missing_label="not_in_window_report",
                ),
                "june_2026_reason": reason_for(
                    june_local,
                    june_unsupported.get(record_id),
                    missing_reason=(
                        "result has no recent_net_excess_pct" if june else "no 2026-06-01+ local result"
                    ),
                ),
            }
        )
    return rows


def sort_rows(rows: list[dict[str, Any]]) -> None:
    rows.sort(
        key=lambda row: (
            row["june_2026_local_net_pct"] is None,
            -(row["june_2026_local_net_pct"] or 0.0),
            row["recent_2026_local_net_pct"] is None,
            -(row["recent_2026_local_net_pct"] or 0.0),
            row["five_year_local_net_pct"] is None,
            -(row["five_year_local_net_pct"] or 0.0),
            text(row["name"]),
        )
    )


def summary_stats(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [number(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return {"count": 0, "min_pct": None, "mean_pct": None, "max_pct": None}
    return {
        "count": len(values),
        "min_pct": min(values),
        "mean_pct": mean(values),
        "max_pct": max(values),
    }


def window_cell(row: dict[str, Any], prefix: str, *, recent: bool) -> str:
    if prefix == "five_year":
        net = row["five_year_local_net_pct"]
        gross = row["five_year_local_gross_pct"]
        turnover = row["five_year_turnover_pct"]
        rank_ic = row["five_year_rank_ic"]
        periods = row["five_year_periods"]
        status = row["five_year_status"]
    elif prefix == "recent_2026":
        net = row["recent_2026_local_net_pct"]
        gross = row["recent_2026_local_gross_pct"]
        turnover = row["recent_2026_turnover_pct"]
        rank_ic = row["recent_2026_rank_ic"]
        periods = row["recent_2026_periods"]
        status = row["recent_2026_status"]
    else:
        net = row["june_2026_local_net_pct"]
        gross = row["june_2026_local_gross_pct"]
        turnover = row["june_2026_turnover_pct"]
        rank_ic = row["june_2026_rank_ic"]
        periods = row["june_2026_periods"]
        status = row["june_2026_status"]
    return "<br>".join(
        [
            f"净 {display(net)}",
            f"毛 {display(gross)}",
            f"换手 {display(turnover)}",
            f"RankIC {display(rank_ic, 4, '')}",
            f"期数 {display_periods(periods)}",
            f"状态 {safe_md(status)}",
        ]
    )


def output_paths(output: Path) -> tuple[Path, Path, Path]:
    base = output.with_suffix("") if output.suffix in {".json", ".csv", ".md"} else output
    return base.with_suffix(".json"), base.with_suffix(".csv"), base.with_suffix(".md")


def write_report(
    output: Path,
    *,
    full_path: Path,
    recent_path: Path,
    june_path: Path,
    full_payload: dict[str, Any],
    recent_payload: dict[str, Any],
    june_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    overwrite: bool,
) -> None:
    json_path, csv_path, md_path = output_paths(output)
    existing = [path for path in (json_path, csv_path, md_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(map(str, existing)))

    latest_positive_count = len(positive_rows(june_payload))
    settings = {
        "report_type": "positive_factor_three_window_local_comparison",
        "generated_date": "2026-09-20",
        "generated_machine_profile": "home",
        "generated_machine_label": "家用电脑",
        "data_source": "existing local Tushare-cache reports; no calculation started by this script",
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "five_year_window": formal_dates(full_payload),
        "2026_window": f"{recent_payload.get('settings', {}).get('recent_start', '20260101')} to {recent_payload.get('settings', {}).get('end', '20260907')}",
        "2026_actual_signal_dates": actual_dates(recent_payload),
        "june_2026_window": f"{june_payload.get('settings', {}).get('recent_start', '20260601')} to {june_payload.get('settings', {}).get('end', '20260907')}",
        "june_2026_actual_signal_dates": actual_dates(june_payload),
        "five_year_source_machine": "office / 公司电脑（既有 canonical JSON 未记录机器字段，按历史报告约定归档）",
        "2026_source_machine": source_machine(recent_payload, default="office / 公司电脑"),
        "june_2026_source_machine": source_machine(june_payload, default="home / 家用电脑"),
        "five_year_report": str(full_path),
        "2026_report": str(recent_path),
        "june_2026_report": str(june_path),
        "platform_positive_records_from_latest_window": latest_positive_count,
        "five_year_local_available": sum(row["five_year_status"] == "available" for row in rows),
        "2026_local_available": sum(row["recent_2026_status"] == "available" for row in rows),
        "june_2026_local_available": sum(row["june_2026_status"] == "available" for row in rows),
        "june_2026_unsupported": sum(row["june_2026_status"] == "unsupported" for row in rows),
        "stats": {
            "five_year_local_net_pct": summary_stats(rows, "five_year_local_net_pct"),
            "2026_local_net_pct": summary_stats(rows, "recent_2026_local_net_pct"),
            "june_2026_local_net_pct": summary_stats(rows, "june_2026_local_net_pct"),
        },
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps({"settings": settings, "results": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    fields = list(rows[0]) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 正净超额因子三窗口本地复现对照",
        "",
        "本报告只读取已保存的本地 JSON 结果，没有启动 PandaAI、Tushare 拉取或本地回测。汇总文件生成于 `home / 家用电脑`。",
        "平台正净超额因子集合以最新的 `2026-06-01+` 报告为准；因此新增记录会保留在表中，但没有对应本地值的窗口明确显示为 `n/a`。",
        "",
        "## 口径与来源",
        "",
        f"- 对齐规则版本：`{ALIGNMENT_RULE_VERSION}`",
        "- 固定口径：全 A `.SH/.SZ`、qfq、`daily_basic.total_mv`、`20180101` 暖机、label-1、10 组、`factor_valid`、单边成本 `0.30%`。",
        f"- 正式五年窗口：`{settings['five_year_window']}`；来源机器：`{settings['five_year_source_machine']}`。",
        f"- `2026-01-01+`：请求窗口 `{settings['2026_window']}`，实际可用信号日期 `{settings['2026_actual_signal_dates']}`；来源机器：`{settings['2026_source_machine']}`。",
        f"- `2026-06-01+`：请求窗口 `{settings['june_2026_window']}`，实际可用信号日期 `{settings['june_2026_actual_signal_dates']}`；来源机器：`{settings['june_2026_source_machine']}`。",
        "- 五年本地净超额来自 canonical 报告中的 `local_net_excess`（分数转为百分比）；两个近期窗口使用各自报告的 `recent_net_excess_pct`。",
        "- 平台净超额是平台保存的正式五年筛选值，不是近期窗口的平台回测值；近期窗口只作为本地诊断，不能替代正式五年结论。",
        "",
        "## 汇总",
        "",
        f"- 最新平台正净超额记录：`{settings['platform_positive_records_from_latest_window']}`",
        f"- 五年本地可用：`{settings['five_year_local_available']}`；`2026-01-01+` 本地可用：`{settings['2026_local_available']}`；`2026-06-01+` 本地可用：`{settings['june_2026_local_available']}`。",
        "- 表内近期窗口按 `2026-06-01+` 本地净超额降序排列；不可用值排在末尾。每个窗口单元格依次给出净超额、毛超额、换手率、RankIC、有效期数和状态。",
        "",
        "| # | 因子 | 公式 | handler | 周期 | 平台五年净超额 | 五年本地 | 2026-01-01+ 本地 | 2026-06-01+ 本地 | 五年质量 |",
        "|---:|---|---|---|---:|---:|---|---|---|---|",
    ]
    for index, row in enumerate(rows, 1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    safe_md(row["name"]),
                    safe_md(row["formula"]),
                    safe_md(row["handler"]),
                    safe_md(row["cycle"]),
                    display(row["platform_five_year_net_pct"]),
                    window_cell(row, "five_year", recent=False),
                    window_cell(row, "recent_2026", recent=True),
                    window_cell(row, "june_2026", recent=True),
                    safe_md(row["five_year_alignment_quality"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 缺失与不支持",
            "",
            "`not_in_canonical_report` 表示该记录在最新平台正因子集合中，但正式五年 JSON 生成时尚未包含；这不是把近期值填入五年值。",
            "",
            "| 因子 | 五年状态/原因 | 2026-01-01+ 状态/原因 | 2026-06-01+ 状态/原因 |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        if all(
            row[key] == "available"
            for key in ("five_year_status", "recent_2026_status", "june_2026_status")
        ):
            continue
        lines.append(
            f"| {safe_md(row['name'])} | {safe_md(row['five_year_status'])}: {safe_md(row['five_year_reason'])} | "
            f"{safe_md(row['recent_2026_status'])}: {safe_md(row['recent_2026_reason'])} | "
            f"{safe_md(row['june_2026_status'])}: {safe_md(row['june_2026_reason'])} |"
        )

    lines.extend(
        [
            "",
            "## 净超额统计",
            "",
            "统计只对对应窗口有本地数值的记录计算，单位为百分比。",
            "",
            "| 窗口 | 数量 | 最小 | 均值 | 最大 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, field in (
        ("五年", "five_year_local_net_pct"),
        ("2026-01-01+", "recent_2026_local_net_pct"),
        ("2026-06-01+", "june_2026_local_net_pct"),
    ):
        stats = summary_stats(rows, field)
        lines.append(
            f"| {label} | {stats['count']} | {display(stats['min_pct'])} | "
            f"{display(stats['mean_pct'])} | {display(stats['max_pct'])} |"
        )

    lines.extend(
        [
            "",
            "## 解读边界",
            "",
            "- 近期窗口有效期数较少，尤其是 `2026-06-01+`，只能用于近期诊断；不能根据短窗口排名替换正式五年结论。",
            "- `proxy`、`field_or_path_mismatch`、`turnover_dominant` 等质量信息继承自五年 canonical 报告；近期数值好看不会自动修复五年口径差异。",
            "- 本报告是家用电脑上的文件汇总，不代表公司电脑重新计算，也没有声称三个窗口在同一台电脑上重新跑过。",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--five-year", type=Path, default=DEFAULT_FIVE_YEAR)
    parser.add_argument("--recent-2026", type=Path, default=DEFAULT_2026)
    parser.add_argument("--june-2026", type=Path, default=DEFAULT_JUNE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    for path in (args.five_year, args.recent_2026, args.june_2026):
        if not path.exists():
            raise FileNotFoundError(path)

    full_payload = load_json(args.five_year)
    recent_payload = load_json(args.recent_2026)
    june_payload = load_json(args.june_2026)
    versions = {
        payload.get("settings", {}).get("alignment_rule_version")
        for payload in (full_payload, recent_payload, june_payload)
    }
    if versions != {ALIGNMENT_RULE_VERSION}:
        raise ValueError(f"Incompatible alignment rule versions: {sorted(versions)}")

    rows = build_rows(full_payload, recent_payload, june_payload)
    if not rows:
        raise ValueError("No positive platform records found in the latest June-window report")
    sort_rows(rows)
    write_report(
        args.output,
        full_path=args.five_year,
        recent_path=args.recent_2026,
        june_path=args.june_2026,
        full_payload=full_payload,
        recent_payload=recent_payload,
        june_payload=june_payload,
        rows=rows,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
