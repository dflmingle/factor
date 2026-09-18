#!/usr/bin/env python3
"""Compare RSQR60 on the CNI Chips index universe and full A.

This is an explicitly labelled diagnostic for the externally supplied
2020-01-02..2026-01-09 claim.  The canonical PandaAI pool remains full A and
the PandaAI run for ``Rsquare`` has no completed result.  The CNI site only
publishes the recent constituent-adjustment history, so dates before the
first published interval use the first interval as a survivorship-biased
static sensitivity; the report keeps that result separate from the official
history-only result.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data, select_market_cap  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_MARKET_CAP_FIELD,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
    annualized_turnover_cost,
)
from positive_factor_local_compare import (  # noqa: E402
    build_factor,
    panel_close,
    forward_returns,
)
from rsqr60_local_test import compounded_max_drawdown  # noqa: E402
from stfilter_local_recheck import ensure_calendar  # noqa: E402


INDEX_CODE = "980017"
INDEX_NAME = "国证芯片"
FORMULA = "Rsquare(CLOSE,60)"
HANDLER = "rsquare60"
CYCLE = 5
DIRECTION = 1
CLAIM_START = pd.Timestamp("2020-01-02")
CLAIM_END = pd.Timestamp("2026-01-09")
OFFICIAL_START = pd.Timestamp("2021-12-13")
PRICE_ROOT = (
    PROJECT_ROOT
    / "quantlab"
    / ".quantlab"
    / "cache"
    / "research"
    / "cn_equity"
    / "tushare_factor_recheck"
    / "qfq"
    / "daily_batches"
)
CAP_ROOT = (
    PROJECT_ROOT
    / "quantlab"
    / ".quantlab"
    / "cache"
    / "research"
    / "cn_equity"
    / "tushare_factor_recheck"
    / "daily_basic_full_a"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports" / "platform_alignment" / "rsqr60_chip_compare_20260918"
SCHEDULE_URL = "https://www.cnindex.com.cn/sample-detail/download-adjustment"
INDEX_HISTORY_URL = "https://hq.cnindex.com.cn/market/market/getIndexDailyDataWithDataFormat"
PLATFORM_STATE = PROJECT_ROOT / "rsqr60-platform-20260918-candidates.txt.state.json"
PRIOR_FULL_A_RESULT = (
    PROJECT_ROOT
    / "research_reports"
    / "platform_alignment"
    / "rsqr60_local_20260918"
    / "rsqr60_local_result.json"
)


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def pct(value: Any) -> str:
    return "n/a" if value is None or not np.isfinite(float(value)) else f"{100.0 * float(value):.2f}%"


def zfill_code(value: Any) -> str:
    text = str(value).strip()
    return text.zfill(6)


def parse_dates(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_value = pd.Timestamp(pd.to_datetime(start, format="%Y%m%d")).normalize()
    end_value = pd.Timestamp(pd.to_datetime(end, format="%Y%m%d")).normalize()
    if start_value > end_value:
        raise ValueError("start must not be after end")
    return start_value, end_value


def fetch_adjustment_schedule(index_code: str) -> pd.DataFrame:
    response = requests.get(SCHEDULE_URL, params={"indexcode": index_code}, timeout=30)
    response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(response.content))
    required = {"开始日期", "结束日期", "样本代码", "调整类型"}
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"Index adjustment response missing columns: {sorted(missing)}")
    frame = frame.rename(
        columns={
            "开始日期": "start_date",
            "结束日期": "end_date",
            "样本代码": "code",
            "调整类型": "change_type",
        }
    )
    frame["start_date"] = pd.to_datetime(frame["start_date"]).dt.normalize()
    frame["end_date"] = pd.to_datetime(frame["end_date"]).dt.normalize()
    frame["code"] = frame["code"].map(zfill_code)
    frame["change_type"] = frame["change_type"].fillna("").astype(str).str.strip()
    # OLD plus the new '+' constituents form the active basket.  '-' rows are
    # removals and 备选 rows are reserve names, not index constituents.
    active = frame[frame["change_type"].isin({"OLD", "+"})].copy()
    if active.empty:
        raise RuntimeError(f"No active constituents in adjustment response for {index_code}")
    return active.sort_values(["start_date", "end_date", "code"], ignore_index=True)


def fetch_index_history(index_code: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    response = requests.get(
        INDEX_HISTORY_URL,
        params={
            "indexCode": index_code,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "frequency": "day",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = (payload.get("data") or {}).get("data") or []
    if not data:
        raise RuntimeError(f"No index history returned for {index_code}")
    rows = []
    for row in data:
        if len(row) < 6:
            continue
        rows.append({"date": pd.Timestamp(row[0]).normalize(), "close": pd.to_numeric(row[5], errors="coerce")})
    frame = pd.DataFrame(rows).dropna(subset=["date", "close"])
    frame = frame[frame["date"].between(start, end)].drop_duplicates("date", keep="last")
    return frame.sort_values("date", ignore_index=True)


def build_intervals(schedule: pd.DataFrame, frame: pd.DataFrame) -> list[dict[str, Any]]:
    code_lookup: dict[str, str] = {}
    for instrument in frame["instrument"].astype(str).unique():
        code_lookup.setdefault(instrument.split(".", 1)[0], instrument)
    intervals: list[dict[str, Any]] = []
    for (start_date, end_date), group in schedule.groupby(["start_date", "end_date"], sort=True):
        instruments = sorted({code_lookup[code] for code in group["code"] if code in code_lookup})
        if len(instruments) < ALIGNMENT_GROUPS * 2:
            continue
        intervals.append(
            {
                "start_date": pd.Timestamp(start_date).normalize(),
                "end_date": pd.Timestamp(end_date).normalize(),
                "codes": sorted(group["code"].unique().tolist()),
                "instruments": instruments,
                "raw_count": int(group["code"].nunique()),
            }
        )
    if not intervals:
        raise RuntimeError("No schedule interval overlaps the local price universe")
    return intervals


def interval_for_date(date: pd.Timestamp, intervals: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    for interval in intervals:
        if interval["start_date"] <= date <= interval["end_date"]:
            return interval, "official_schedule"
    if date < intervals[0]["start_date"]:
        return intervals[0], "static_first_interval_survivorship_sensitivity"
    return intervals[-1], "last_interval_carry_forward"


def signal_dates(calendar: list[pd.Timestamp], start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    positions = list(range(calendar.index(start), len(calendar), CYCLE))
    return [
        calendar[position]
        for position in positions
        if calendar[position] <= end and position + ALIGNMENT_LABEL_OFFSET + CYCLE < len(calendar)
    ]


def assign_groups(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="first")
    return np.ceil(ranks * ALIGNMENT_GROUPS / len(values)).astype(int).clip(1, ALIGNMENT_GROUPS)


def evaluate_universe(
    name: str,
    factor_frame: pd.DataFrame,
    returns: pd.DataFrame,
    signal_dates: list[pd.Timestamp],
    membership: dict[pd.Timestamp, set[str]] | None,
    source_label: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    data = factor_frame[factor_frame["date"].isin(signal_dates)].merge(
        returns, on=["date", "instrument"], how="left"
    )
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=["factor", "forward_return"])
    if membership is not None:
        allowed = pd.Series(
            [instrument in membership.get(date, set()) for date, instrument in zip(data["date"], data["instrument"])],
            index=data.index,
        )
        data = data[allowed]

    previous: set[str] | None = None
    rank_ics: list[float] = []
    ics: list[float] = []
    rows: list[dict[str, Any]] = []
    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < ALIGNMENT_GROUPS * 2:
            continue
        current["group"] = assign_groups(current["factor"])
        rank_ic = current["factor"].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        ic = current["factor"].corr(current["forward_return"])
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        if pd.notna(ic):
            ics.append(float(ic))
        benchmark = float(current["forward_return"].mean())
        selected = current[current["group"].eq(ALIGNMENT_GROUPS)]
        selected_return = float(selected["forward_return"].mean())
        members = set(selected["instrument"].astype(str))
        turnover = (
            np.nan
            if previous is None
            else float(1.0 - len(members.intersection(previous)) / len(members))
        )
        previous = members
        rows.append(
            {
                "date": date,
                "stock_count": int(len(current)),
                "benchmark_return": benchmark,
                "selected_return": selected_return,
                "selected_excess": selected_return - benchmark,
                "turnover": turnover,
                "universe_source": source_label,
            }
        )

    periods = pd.DataFrame(rows)
    years = len(periods) * CYCLE / 252.0
    gross_excess = float(periods["selected_excess"].sum() / years) if years and not periods.empty else None
    gross_selected = float(periods["selected_return"].sum() / years) if years and not periods.empty else None
    compound_selected = (
        float(np.prod(1.0 + periods["selected_return"].to_numpy(dtype=float)) - 1.0)
        if not periods.empty
        else None
    )
    compound_benchmark = (
        float(np.prod(1.0 + periods["benchmark_return"].to_numpy(dtype=float)) - 1.0)
        if not periods.empty
        else None
    )
    compound_excess = (
        float(np.prod(1.0 + periods["selected_excess"].to_numpy(dtype=float)) - 1.0)
        if not periods.empty
        else None
    )
    turnover = float(periods["turnover"].dropna().mean()) if periods["turnover"].notna().any() else None
    annual_cost = annualized_turnover_cost(turnover, CYCLE, ALIGNMENT_ROUND_TRIP_COST)
    net_excess = gross_excess - annual_cost if gross_excess is not None and annual_cost is not None else None
    latest_date = periods["date"].max() if not periods.empty else signal_dates[-1]
    latest = factor_frame[factor_frame["date"].eq(latest_date)].dropna(subset=["factor"])
    if membership is not None:
        latest = latest[latest["instrument"].isin(membership.get(latest_date, set()))]
    top20 = latest.sort_values(["factor", "instrument"], ascending=[False, True]).head(20)["instrument"].astype(str).tolist()
    result = {
        "name": name,
        "formula": FORMULA,
        "handler": HANDLER,
        "direction": DIRECTION,
        "selected_group": ALIGNMENT_GROUPS,
        "periods": int(len(periods)),
        "stock_count_mean": float(periods["stock_count"].mean()) if not periods.empty else None,
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "ic_mean": float(np.mean(ics)) if ics else None,
        "gross_selected_return": gross_selected,
        "gross_excess": gross_excess,
        "compound_selected_return": compound_selected,
        "compound_benchmark_return": compound_benchmark,
        "compound_excess": compound_excess,
        "turnover": turnover,
        "annual_cost": annual_cost,
        "net_excess": net_excess,
        "max_drawdown": compounded_max_drawdown(periods["selected_return"]) if not periods.empty else None,
        "monthly_excess_win_rate": (
            float((periods.assign(month=periods["date"].dt.to_period("M")).groupby("month")["selected_excess"].mean() > 0).mean())
            if not periods.empty
            else None
        ),
        "top20": top20,
        "source_label": source_label,
        "start": periods["date"].min() if not periods.empty else None,
        "end": periods["date"].max() if not periods.empty else None,
    }
    return result, periods


def read_platform_status() -> dict[str, Any]:
    try:
        payload = json.loads(PLATFORM_STATE.read_text(encoding="utf-8"))
        row = payload.get("RSQR60-ALPHA158-20260918", {})
        return {
            "status": "failed" if row.get("error") else "unknown",
            "factor_id": row.get("factor_id"),
            "run_id": row.get("run_id"),
            "factor_result_status": row.get("factor_result_status"),
            "error": row.get("error"),
        }
    except (OSError, json.JSONDecodeError):
        return {"status": "missing_state"}


def read_prior_full_a() -> dict[str, Any]:
    try:
        payload = json.loads(PRIOR_FULL_A_RESULT.read_text(encoding="utf-8"))
        return payload.get("result", {})
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--price-root", default=str(PRICE_ROOT))
    parser.add_argument("--cap-root", default=str(CAP_ROOT))
    parser.add_argument("--start", default="20200102")
    parser.add_argument("--end", default="20260109")
    args = parser.parse_args()
    start, end = parse_dates(args.start, args.end)
    data_start = pd.Timestamp(ALIGNMENT_DATA_START)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    calendar = ensure_calendar(data_start, end, token=None)
    claim_dates = signal_dates(calendar, start, end)
    official_start = max(start, OFFICIAL_START)
    official_dates = signal_dates(calendar, official_start, end)
    frame = load_full_a_data(Path(args.price_root), Path(args.cap_root), data_start, end)
    frame = select_market_cap(frame, ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    schedule = fetch_adjustment_schedule(INDEX_CODE)
    intervals = build_intervals(schedule, frame)
    index_codes = sorted({code for interval in intervals for code in interval["codes"]})
    code_set = set(index_codes)
    frame_codes = frame["instrument"].str.split(".").str[0]
    index_frame = frame[frame_codes.isin(code_set)].copy().sort_values(["instrument", "date"], ignore_index=True)
    all_dates = sorted(set(claim_dates + official_dates))
    index_factor = build_factor(index_frame, HANDLER, signal_dates=all_dates)
    index_factor_frame = index_frame[["date", "instrument"]].copy()
    index_factor_frame["factor"] = index_factor.to_numpy(dtype=float)

    all_factor = build_factor(frame, HANDLER, signal_dates=all_dates)
    all_factor_frame = frame[["date", "instrument"]].copy()
    all_factor_frame["factor"] = all_factor.to_numpy(dtype=float)

    index_close = panel_close(index_frame, calendar)
    all_close = panel_close(frame, calendar)
    index_returns_claim = forward_returns(index_close, calendar, claim_dates, CYCLE, ALIGNMENT_LABEL_OFFSET)
    index_returns_official = forward_returns(index_close, calendar, official_dates, CYCLE, ALIGNMENT_LABEL_OFFSET)
    all_returns_claim = forward_returns(all_close, calendar, claim_dates, CYCLE, ALIGNMENT_LABEL_OFFSET)

    membership_claim: dict[pd.Timestamp, set[str]] = {}
    membership_official: dict[pd.Timestamp, set[str]] = {}
    source_claim: dict[pd.Timestamp, str] = {}
    source_official: dict[pd.Timestamp, str] = {}
    for date in claim_dates:
        interval, source = interval_for_date(date, intervals)
        membership_claim[date] = set(interval["instruments"] if interval else [])
        source_claim[date] = source
    for date in official_dates:
        interval, source = interval_for_date(date, intervals)
        membership_official[date] = set(interval["instruments"] if interval else [])
        source_official[date] = source

    # The evaluator accepts one source label for the report; the period CSV
    # retains the date-level official/static distinction.
    index_claim, claim_periods = evaluate_universe(
        "index_980017_claim_window_static_first",
        index_factor_frame,
        index_returns_claim,
        claim_dates,
        membership_claim,
        "static_first_interval_before_2021-12-13_plus_official_after",
    )
    index_official, official_periods = evaluate_universe(
        "index_980017_official_schedule_only",
        index_factor_frame,
        index_returns_official,
        official_dates,
        membership_official,
        "official_schedule_from_2021-12-13",
    )
    full_a_claim, full_a_periods = evaluate_universe(
        "full_a_same_claim_window",
        all_factor_frame,
        all_returns_claim,
        claim_dates,
        None,
        "full_a_factor_valid",
    )

    index_history = fetch_index_history(INDEX_CODE, start, end)
    index_history.to_csv(output / "index_980017_history.csv", index=False, encoding="utf-8-sig")
    schedule.to_csv(output / "index_980017_adjustment_schedule.csv", index=False, encoding="utf-8-sig")
    claim_periods.to_csv(output / "rsqr60_index_claim_periods.csv", index=False, encoding="utf-8-sig")
    official_periods.to_csv(output / "rsqr60_index_official_periods.csv", index=False, encoding="utf-8-sig")
    full_a_periods.to_csv(output / "rsqr60_full_a_claim_periods.csv", index=False, encoding="utf-8-sig")

    index_start = index_history.iloc[0]
    index_end = index_history.iloc[-1]
    index_cumulative = float(index_end["close"] / index_start["close"] - 1.0)
    index_years = max((index_end["date"] - index_start["date"]).days / 365.25, 1.0 / 365.25)
    index_cagr = float((1.0 + index_cumulative) ** (1.0 / index_years) - 1.0)
    prior_full_a = read_prior_full_a()
    platform = read_platform_status()
    results = {
        "index_claim": index_claim,
        "index_official": index_official,
        "full_a_claim": full_a_claim,
        "full_a_prior_canonical": prior_full_a,
    }
    settings = {
        "rule_version": ALIGNMENT_RULE_VERSION,
        "formula": FORMULA,
        "handler": HANDLER,
        "index_code": INDEX_CODE,
        "index_name": INDEX_NAME,
        "data_start": data_start,
        "claim_start": start,
        "claim_end": end,
        "official_start": official_start,
        "cycle": CYCLE,
        "groups": ALIGNMENT_GROUPS,
        "direction": DIRECTION,
        "label": "close(t+1) -> close(t+1+cycle)",
        "one_way_cost": ALIGNMENT_ONE_WAY_COST,
        "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
        "market_cap_field": ALIGNMENT_MARKET_CAP_FIELD,
        "price_mode": "qfq",
        "schedule_source": SCHEDULE_URL,
        "index_history_source": INDEX_HISTORY_URL,
        "schedule_first_interval": intervals[0]["start_date"],
        "schedule_last_interval": intervals[-1]["end_date"],
        "schedule_interval_count": len(intervals),
        "index_union_instruments": len(index_codes),
        "index_price_cumulative": index_cumulative,
        "index_price_cagr": index_cagr,
        "diagnostic_only": True,
        "noncanonical_reasons": [
            "user-supplied window begins before the current canonical full-A window",
            "PandaAI CLI pool is fixed to full A",
            "980017 adjustment history published by the source begins at 2021-12-13; prehistory is static-first sensitivity",
        ],
    }
    payload = {"settings": settings, "platform": platform, "results": results}
    (output / "rsqr60_chip_compare.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8"
    )

    lines = [
        "# RSQR60 国证芯片对比诊断",
        "",
        f"- 因子：`{FORMULA}`；指数：`{INDEX_CODE} {INDEX_NAME}`。",
        f"- 用户窗口：`{start:%Y-%m-%d}..{end:%Y-%m-%d}`；暖机：`{data_start:%Y-%m-%d}`；5 日调仓；10 组。",
        f"- 标签：`close(t+1) -> close(t+1+cycle)`；价格：`qfq`；市值字段：`daily_basic.total_mv`；单边成本：`{100 * ALIGNMENT_ONE_WAY_COST:.2f}%`。",
        f"- 规则版本：`{ALIGNMENT_RULE_VERSION}`。此目录是诊断目录，不覆盖正式全 A 结果。",
        "",
        "## 平台状态",
        "",
        f"- `Rsquare(CLOSE,60)` 平台状态：`{platform.get('status')}`；factor_id：`{platform.get('factor_id') or 'n/a'}`；run_id：`{platform.get('run_id') or 'n/a'}`。",
        f"- 结果状态：`{platform.get('factor_result_status') or 'n/a'}`；错误：`{platform.get('error') or 'n/a'}`。",
        "- PandaAI CLI 当前股票池固定为沪深全 A，且该 Rsquare 运行未完成，因此没有平台芯片子池指标可做字面一一对照。",
        "",
        "## 指数本身",
        "",
        f"- 官网 `980017` 收盘点：`{index_start['date']:%Y-%m-%d} {index_start['close']:.4f}` -> `{index_end['date']:%Y-%m-%d} {index_end['close']:.4f}`。",
        f"- 指数累计价格收益：`{pct(index_cumulative)}`；价格 CAGR 约：`{pct(index_cagr)}`。这不是因子多空/多头超额收益。",
        "",
        "## 因子结果",
        "",
        "| run | periods | mean stocks | RankIC | compound selected | gross excess | turnover | annual cost | net excess | max DD | source |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, result in [("芯片静态前段+官方后段", index_claim), ("芯片官方成分段", index_official), ("全 A 同窗口", full_a_claim), ("全 A 正式旧基线", prior_full_a)]:
        if not result:
            continue
        selected_return = result.get("gross_selected_return", result.get("gross_return"))
        lines.append(
            f"| {key} | {result.get('periods', 'n/a')} | {result.get('stock_count_mean', float('nan')):.1f} | "
            f"{result.get('rank_ic', float('nan')):.6f} | {pct(result.get('compound_selected_return', selected_return))} | "
            f"{pct(result.get('gross_excess'))} | {pct(result.get('turnover'))} | {pct(result.get('annual_cost'))} | "
            f"{pct(result.get('net_excess'))} | {pct(result.get('max_drawdown'))} | {result.get('source_label', 'canonical')} |"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- `芯片静态前段+官方后段` 中 2020-01-02 至 2021-12-10 使用 2021-12-13 首个可取得成分篮子，存在幸存者偏差，只能作为敏感性诊断。",
            "- `芯片官方成分段` 从 2021-12-13 开始，使用官网半年度调整表中 `OLD` 与 `+` 代码；`-` 和 `备选` 不纳入。",
            "- 芯片结果的净超额基准是当期有效因子截面的等权平均收益，沿用 `factor_valid`，不是官网指数的市值加权收益。",
            "- 本地 RSQR60 是按每只股票 qfq 收盘价对时间序列做 60 日滚动 R²，再在信号日横截面分组；这是对平台 `Rsquare` 的直接本地重建，平台本次没有返回可对齐结果。",
            "- 详细逐期数据见 `rsqr60_index_claim_periods.csv`、`rsqr60_index_official_periods.csv` 和 `rsqr60_full_a_claim_periods.csv`。",
            "",
        ]
    )
    (output / "rsqr60_chip_compare.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"report={output / 'rsqr60_chip_compare.md'}")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
