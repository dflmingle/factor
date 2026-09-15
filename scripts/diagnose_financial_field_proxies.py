#!/usr/bin/env python3
"""Compare offline CFP field proxies under the platform-aligned return label.

This diagnostic reads saved platform results and the local Tushare snapshot. It
does not create a factor or call PandaAI. All variants use the same saved
signal dates, ten groups, direction, qfq price panel, shifted forward-return
label, and turnover-cost calculation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import financial_factor_local as financial_local  # noqa: E402
from financial_factor_local import load_financial_cache  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_BENCHMARK_DESCRIPTION,
    ALIGNMENT_BENCHMARK_MODE,
    ALIGNMENT_DATA_START,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_ONE_WAY_COST,
    ALIGNMENT_PRICE_MODE,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    ALIGNMENT_ROUND_TRIP_COST,
)
from platform_aligned_factor_compare import read_platform_run  # noqa: E402
from positive_factor_local_compare import (  # noqa: E402
    END,
    GROUPS,
    ROUND_TRIP_COST,
    formula_catalog,
    positive_records,
)
from stfilter_local_recheck import ensure_calendar  # noqa: E402


DATA_START = pd.Timestamp(ALIGNMENT_DATA_START)
OUTPUT_DEFAULT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/financial_field_proxy_diagnosis_full_a"
)
PRICE_ROOT_DEFAULT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
)
CAP_ROOT_DEFAULT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
)
FINANCIAL_ROOT_DEFAULT = (
    PROJECT_ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/financial_full_a"
)

CFP_HANDLERS = {
    "reversal_bm_cfp",
    "reversal_bm_cfp_rev2",
    "reversal_bm_cfp_rev3",
    "reversal_bm_cfp_val2",
    "reversal_bm_cfp_val3",
    "reversal_bm_cfp_sp",
    "reversal_bm_cfp_pcf",
    "reversal_bm_cfp_ma63",
    "reversal_bm_cfp_tsrank756",
}

PROXIES = (
    "ocf_ttm_mv",
    "fcf_ttm_mv",
    "cfps_cur_price",
    "ocfps_cur_price",
    "cfps_lyr_price",
    "ocfps_lyr_price",
)


def day_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y%m%d")


def clean_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def cfp_records() -> list[dict[str, Any]]:
    supported, _ = positive_records(formula_catalog())
    result = []
    for record in supported:
        if record["handler"] not in CFP_HANDLERS:
            continue
        raw_path = PROJECT_ROOT / record["raw_result"]
        if not raw_path.exists():
            continue
        result.append(record)
    if not result:
        raise RuntimeError("No saved CFP records are available")
    return result


def rank(values: pd.Series, dates: pd.Series) -> pd.Series:
    return financial_local._rank(values, dates)


def build_base_signal(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    financial: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    financial_local._FINANCIAL_CACHE = financial
    selected = financial_local._base_signal(frame, dates)
    date_series = selected["date"]
    selected["rev_rank"] = rank(1.0 - selected["ret40"], date_series)
    selected["bm_rank"] = rank(selected["ratio_bm_ttm"], date_series)
    selected["sp_rank"] = rank(selected["ratio_sp_ttm"], date_series)
    selected["pcf_rank"] = rank(selected["ratio_pcf_ocf_ttm"], date_series)
    return selected


def historical_proxy_rank(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    proxy: str,
    window: int,
    operation: str,
    result_cache: dict[tuple[str, int, str], pd.Series],
) -> pd.Series:
    key = (proxy, window, operation)
    if key in result_cache:
        return result_cache[key]

    first_date = min(dates)
    last_date = max(dates)
    history = frame[
        frame["date"].between(first_date - pd.Timedelta(days=1400), last_date)
    ][["date", "instrument", "total_mv", "close_qfq"]].copy()
    history["row_id"] = history.index.to_numpy(dtype=np.int64)

    if proxy == "ocf_ttm_mv":
        history = financial_local._attach(
            history,
            cache["cashflow_ttm"],
            "",
            ["ttm_n_cashflow_act"],
        )
        numerator = financial_local._numeric_series(history, "ttm_n_cashflow_act")
        denominator = financial_local._numeric_series(history, "total_mv")
        ratio = numerator.div(denominator.replace(0.0, np.nan))
    elif proxy == "fcf_ttm_mv":
        history = financial_local._attach(
            history,
            cache["cashflow_ttm"],
            "",
            ["ttm_free_cashflow"],
        )
        numerator = financial_local._numeric_series(history, "ttm_free_cashflow")
        denominator = financial_local._numeric_series(history, "total_mv")
        ratio = numerator.div(denominator.replace(0.0, np.nan))
    else:
        field, suffix = proxy.split("_", 1)
        if suffix == "cur_price":
            table = cache["fina_indicator"]
            table_suffix = "_cur"
        elif suffix == "lyr_price":
            table = financial_local._annual(cache["fina_indicator"])
            table_suffix = "_lyr"
        else:
            raise KeyError(f"Unsupported proxy: {proxy}")
        history = financial_local._attach(
            history,
            table,
            table_suffix,
            [field],
        )
        numerator = financial_local._numeric_series(history, f"{field}{table_suffix}")
        denominator = financial_local._numeric_series(history, "close_qfq")
        ratio = numerator.div(denominator.replace(0.0, np.nan))

    history["ratio"] = ratio
    history = history.sort_values(["instrument", "date"]).reset_index(drop=True)
    if operation == "ma":
        history["ratio_transformed"] = financial_local._rolling(
            history, "ratio", window, "mean"
        )
    elif operation == "ts_rank":
        grouped = history.groupby("instrument", sort=False, observed=True)["ratio"]
        values = grouped.rolling(window=window, min_periods=window).rank(pct=True)
        history["ratio_transformed"] = values.reset_index(level=0, drop=True).reindex(
            history.index
        )
    else:
        raise KeyError(f"Unsupported historical operation: {operation}")

    selected = history[history["date"].isin(dates)]
    transformed_rank = rank(selected["ratio_transformed"], selected["date"])
    result = pd.Series(
        transformed_rank.to_numpy(dtype=float),
        index=selected["row_id"].to_numpy(dtype=np.int64),
        dtype=float,
    )
    result_cache[key] = result
    return result


def direct_proxy_ratio(selected: pd.DataFrame, proxy: str) -> pd.Series:
    if proxy == "ocf_ttm_mv":
        return selected["ratio_cfp_ttm"]
    if proxy == "fcf_ttm_mv":
        numerator = financial_local._numeric_series(selected, "ttm_free_cashflow")
        denominator = financial_local._numeric_series(selected, "total_mv")
        return numerator.div(denominator.replace(0.0, np.nan))
    field, suffix = proxy.split("_", 1)
    if suffix == "cur_price":
        column = f"{field}_cur"
    elif suffix == "lyr_price":
        column = f"{field}_lyr"
    else:
        raise KeyError(f"Unsupported proxy: {proxy}")
    numerator = financial_local._numeric_series(selected, column)
    denominator = financial_local._numeric_series(selected, "close_qfq")
    return numerator.div(denominator.replace(0.0, np.nan))


def cfp_rank_for_handler(
    frame: pd.DataFrame,
    selected: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    proxy: str,
    handler: str,
    historical_cache: dict[tuple[str, int, str], pd.Series],
) -> pd.Series:
    date_series = selected["date"]
    if handler in {"reversal_bm_cfp_ma63"}:
        transformed = historical_proxy_rank(
            frame, dates, cache, proxy, 63, "ma", historical_cache
        )
        return selected["row_id"].map(transformed)
    if handler in {"reversal_bm_cfp_tsrank756"}:
        transformed = historical_proxy_rank(
            frame, dates, cache, proxy, 756, "ts_rank", historical_cache
        )
        return selected["row_id"].map(transformed)
    return rank(direct_proxy_ratio(selected, proxy), date_series)


def build_variant_values(
    frame: pd.DataFrame,
    base: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    handler: str,
    proxy: str,
    historical_cache: dict[tuple[str, int, str], pd.Series],
) -> pd.Series:
    selected = base.copy()
    date_series = selected["date"]
    cfp_rank = cfp_rank_for_handler(
        frame, selected, dates, cache, proxy, handler, historical_cache
    )
    rev_rank = selected["rev_rank"]
    bm_rank = selected["bm_rank"]

    if handler == "reversal_bm_cfp":
        factor = (rev_rank + bm_rank + cfp_rank) / 3.0
    elif handler == "reversal_bm_cfp_rev2":
        factor = (2.0 * rev_rank + bm_rank + cfp_rank) / 4.0
    elif handler == "reversal_bm_cfp_rev3":
        factor = (3.0 * rev_rank + bm_rank + cfp_rank) / 5.0
    elif handler == "reversal_bm_cfp_val2":
        factor = (rev_rank + 2.0 * bm_rank + 2.0 * cfp_rank) / 5.0
    elif handler == "reversal_bm_cfp_val3":
        factor = (rev_rank + 3.0 * bm_rank + 3.0 * cfp_rank) / 7.0
    elif handler == "reversal_bm_cfp_sp":
        factor = (rev_rank + bm_rank + cfp_rank + selected["sp_rank"]) / 4.0
    elif handler == "reversal_bm_cfp_pcf":
        factor = (rev_rank + bm_rank + cfp_rank + 1.0 - selected["pcf_rank"]) / 4.0
    elif handler == "reversal_bm_cfp_ma63":
        bm_rank_ma = selected["row_id"].map(
            historical_bm_rank(frame, dates, cache, 63, "ma", historical_cache)
        )
        factor = (rev_rank + bm_rank_ma + cfp_rank) / 3.0
    elif handler == "reversal_bm_cfp_tsrank756":
        bm_rank_ts = selected["row_id"].map(
            historical_bm_rank(frame, dates, cache, 756, "ts_rank", historical_cache)
        )
        factor = (rev_rank + bm_rank_ts + cfp_rank) / 3.0
    else:
        raise KeyError(f"Unsupported CFP handler: {handler}")

    values = pd.Series(np.nan, index=frame.index, dtype=float)
    values.loc[selected["row_id"].to_numpy(dtype=np.int64)] = pd.to_numeric(
        factor, errors="coerce"
    ).to_numpy()
    return values


def historical_bm_rank(
    frame: pd.DataFrame,
    dates: list[pd.Timestamp],
    cache: dict[str, pd.DataFrame],
    window: int,
    operation: str,
    result_cache: dict[tuple[str, int, str], pd.Series],
) -> pd.Series:
    key = ("bm_ttm_mv", window, operation)
    if key in result_cache:
        return result_cache[key]
    first_date = min(dates)
    last_date = max(dates)
    history = frame[
        frame["date"].between(first_date - pd.Timedelta(days=1400), last_date)
    ][["date", "instrument", "total_mv"]].copy()
    history["row_id"] = history.index.to_numpy(dtype=np.int64)
    history = financial_local._attach(
        history,
        cache["balancesheet"],
        "_bs_cur",
        ["total_hldr_eqy_exc_min_int"],
    )
    history["ratio"] = financial_local._numeric_series(
        history, "total_hldr_eqy_exc_min_int_bs_cur"
    ).div(financial_local._numeric_series(history, "total_mv").replace(0.0, np.nan))
    history = history.sort_values(["instrument", "date"]).reset_index(drop=True)
    if operation == "ma":
        history["ratio_transformed"] = financial_local._rolling(
            history, "ratio", window, "mean"
        )
    else:
        grouped = history.groupby("instrument", sort=False, observed=True)["ratio"]
        values = grouped.rolling(window=window, min_periods=window).rank(pct=True)
        history["ratio_transformed"] = values.reset_index(level=0, drop=True).reindex(
            history.index
        )
    selected = history[history["date"].isin(dates)]
    result = pd.Series(
        rank(selected["ratio_transformed"], selected["date"]).to_numpy(dtype=float),
        index=selected["row_id"].to_numpy(dtype=np.int64),
        dtype=float,
    )
    result_cache[key] = result
    return result


def close_panel(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    panel = frame.pivot(index="date", columns="instrument", values="close_qfq")
    return panel.reindex(calendar).sort_index(axis=1).ffill()


def shifted_forward_returns(
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    signal_dates: list[pd.Timestamp],
    cycle: int,
    label_offset: int = ALIGNMENT_LABEL_OFFSET,
) -> pd.DataFrame:
    positions = [calendar.index(date) for date in signal_dates]
    current = close.iloc[[position + label_offset for position in positions]].copy()
    target_positions = [position + cycle + label_offset for position in positions]
    if max(target_positions, default=-1) >= len(calendar):
        raise RuntimeError("Local data does not cover shifted forward targets")
    target = close.iloc[target_positions].copy()
    current.index = signal_dates
    target.index = signal_dates
    current = current.stack(dropna=False).rename("current_close").reset_index()
    target = target.stack(dropna=False).rename("future_close").reset_index()
    current = current.rename(columns={"level_0": "date", "level_1": "instrument"})
    target = target.rename(columns={"level_0": "date", "level_1": "instrument"})
    result = current.merge(target, on=["date", "instrument"], how="left")
    result["forward_return"] = result["future_close"].div(result["current_close"]).sub(1.0)
    return result[["date", "instrument", "forward_return"]]


def evaluate_variant(
    frame: pd.DataFrame,
    values: pd.Series,
    close: pd.DataFrame,
    calendar: list[pd.Timestamp],
    record: dict[str, Any],
    signal_dates: list[pd.Timestamp],
) -> dict[str, Any]:
    factor_frame = frame[["date", "instrument"]].copy()
    factor_frame["factor"] = values.to_numpy(dtype=float)
    factor_frame = factor_frame[factor_frame["date"].isin(signal_dates)]
    returns = shifted_forward_returns(
        close,
        calendar,
        signal_dates,
        int(record["configured_cycle"]),
        ALIGNMENT_LABEL_OFFSET,
    )
    data = factor_frame.merge(returns, on=["date", "instrument"], how="left")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()

    selected_group = GROUPS if int(record["direction"]) == 1 else 1
    previous: set[str] | None = None
    rank_ics: list[float] = []
    group_returns: list[float] = []
    excess_returns: list[float] = []
    turnovers: list[float] = []
    latest_members: list[str] = []
    period_count = 0
    stock_counts: list[int] = []
    for date in signal_dates:
        current = data[data["date"].eq(date)].copy()
        if len(current) < GROUPS * 10:
            continue
        current["group"] = np.ceil(
            current["factor"].rank(method="first") * GROUPS / len(current)
        ).astype(int).clip(1, GROUPS)
        rank_ic = current["factor"].rank(method="average").corr(
            current["forward_return"].rank(method="average")
        )
        if pd.notna(rank_ic):
            rank_ics.append(float(rank_ic))
        benchmark = current["forward_return"].mean()
        if not np.isfinite(benchmark):
            continue
        benchmark = float(benchmark)
        members = set(
            current.loc[current["group"].eq(selected_group), "instrument"].astype(str)
        )
        group_return = float(
            current.loc[current["group"].eq(selected_group), "forward_return"].mean()
        )
        excess = group_return - benchmark
        turnover = (
            float(1.0 - len(members.intersection(previous)) / len(members))
            if previous
            else np.nan
        )
        previous = members
        period_count += 1
        stock_counts.append(len(current))
        group_returns.append(group_return)
        excess_returns.append(excess)
        if np.isfinite(turnover):
            turnovers.append(turnover)
        latest_members = sorted(members)

    if not period_count:
        raise RuntimeError(f"No valid periods for {record['id']}")
    cycle = int(record["configured_cycle"])
    years = period_count * cycle / 252.0
    gross = float(np.sum(excess_returns) / years)
    turnover = float(np.mean(turnovers)) if turnovers else None
    annual_cost = (
        turnover * (252.0 / cycle) * ROUND_TRIP_COST
        if turnover is not None
        else None
    )
    net = gross - annual_cost if annual_cost is not None else None
    platform = read_platform_run(PROJECT_ROOT / record["raw_result"])
    platform_top = [
        str(row["symbol"])
        for row in platform.get("top", [])
        if row.get("symbol") and pd.Timestamp(row.get("date")).normalize() == signal_dates[-1]
    ]
    return {
        "periods": period_count,
        "stock_count_mean": float(np.mean(stock_counts)),
        "rank_ic": float(np.mean(rank_ics)) if rank_ics else None,
        "gross_excess_pct": gross * 100.0,
        "turnover_pct": None if turnover is None else turnover * 100.0,
        "annual_cost_pct": None if annual_cost is None else annual_cost * 100.0,
        "net_excess_pct": None if net is None else net * 100.0,
        "delta_net_pp": None if net is None else net * 100.0 - record["platform_net_excess_pct"],
        "delta_gross_pp": gross * 100.0 - record["platform_gross_excess_pct"],
        "delta_turnover_pp": (
            None
            if turnover is None
            else turnover * 100.0 - record["platform_turnover_pct"]
        ),
        "platform_net_excess_pct": record["platform_net_excess_pct"],
        "platform_gross_excess_pct": record["platform_gross_excess_pct"],
        "platform_turnover_pct": record["platform_turnover_pct"],
        "platform_rank_ic": record["platform_rank_ic"],
        "latest_top20_overlap": (
            len(set(latest_members).intersection(platform_top)) if platform_top else None
        ),
    }


def write_report(
    rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    output: Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": {
            "alignment_rule_version": ALIGNMENT_RULE_VERSION,
            "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
            "data_start": day_text(DATA_START),
            "end": day_text(END),
            "groups": ALIGNMENT_GROUPS,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "one_way_cost": ALIGNMENT_ONE_WAY_COST,
            "price_mode": ALIGNMENT_PRICE_MODE,
            "benchmark_mode": ALIGNMENT_BENCHMARK_MODE,
            "benchmark_description": ALIGNMENT_BENCHMARK_DESCRIPTION,
            "benchmark": "factor-valid qfq panel, matching the final local comparison",
            "label_offset": ALIGNMENT_LABEL_OFFSET,
            "label": f"close(t+{ALIGNMENT_LABEL_OFFSET}) -> close(t+cycle+{ALIGNMENT_LABEL_OFFSET})",
            "records": len(records),
            "proxies": list(PROXIES),
        },
        "results": rows,
    }
    (output / "financial_field_proxy_diagnosis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    def number(value: Any, suffix: str = "") -> str:
        return "n/a" if value is None else f"{float(value):.2f}{suffix}"

    lines = [
        "# Financial field proxy diagnosis",
        "",
        "Offline comparison over saved platform CFP workflows. No factor was created and no platform backtest was run.",
        "",
        f"- alignment rules: `{ALIGNMENT_RULE_VERSION}`; see `{ALIGNMENT_RULES_DOCUMENT}`",
        f"- label: `close(t+{ALIGNMENT_LABEL_OFFSET}) -> close(t+cycle+{ALIGNMENT_LABEL_OFFSET})`",
        f"- price: {ALIGNMENT_PRICE_MODE}; groups: `{ALIGNMENT_GROUPS}`; one-way cost: `{100 * ALIGNMENT_ONE_WAY_COST:.2f}%`",
        f"- benchmark: `{ALIGNMENT_BENCHMARK_MODE}` ({ALIGNMENT_BENCHMARK_DESCRIPTION})",
        f"- saved CFP records: `{len(records)}`; proxy variants: `{len(PROXIES)}`",
        "",
        "| factor | proxy | periods | local net | platform net | delta pp | gross delta pp | turnover delta pp | local RankIC | platform RankIC | top20 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: (item["name"], item["proxy"])):
        top20 = (
            "n/a"
            if row["latest_top20_overlap"] is None
            else f"{row['latest_top20_overlap']}/20"
        )
        lines.append(
            f"| {row['name']} | `{row['proxy']}` | {row['periods']} | "
            f"{number(row['net_excess_pct'], '%')} | {number(row['platform_net_excess_pct'], '%')} | "
            f"{number(row['delta_net_pp'])} | {number(row['delta_gross_pp'])} | "
            f"{number(row['delta_turnover_pp'])} | {number(row['rank_ic'])} | "
            f"{number(row['platform_rank_ic'])} | {top20} |"
        )

    lines.extend(
        [
            "",
            "## Best proxy by factor",
            "",
            "The best row minimizes the absolute net-excess gap under the same shifted label and cost calculation.",
            "",
            "| factor | best proxy | local net | platform net | delta pp | local RankIC |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for name in sorted({row["name"] for row in rows}):
        factor_rows = [row for row in rows if row["name"] == name]
        best = min(factor_rows, key=lambda item: abs(item["delta_net_pp"] or 1e9))
        lines.append(
            f"| {name} | `{best['proxy']}` | {number(best['net_excess_pct'], '%')} | "
            f"{number(best['platform_net_excess_pct'], '%')} | {number(best['delta_net_pp'])} | "
            f"{number(best['rank_ic'])} |"
        )
    lines.extend(
        [
            "",
            "## Proxy definitions",
            "",
            "- `ocf_ttm_mv`: reconstructed TTM operating cash flow / total market value.",
            "- `fcf_ttm_mv`: reconstructed TTM free cash flow / total market value.",
            "- `cfps_cur_price`, `ocfps_cur_price`: latest point-in-time Tushare per-share cash-flow field / qfq close.",
            "- `cfps_lyr_price`, `ocfps_lyr_price`: latest point-in-time annual-report per-share cash-flow field / qfq close.",
            "- MA63 and TS_RANK756 factors apply the corresponding daily point-in-time transform before cross-sectional ranking.",
            "",
        ]
    )
    (output / "financial_field_proxy_diagnosis.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def run(args: argparse.Namespace) -> int:
    records = cfp_records()
    calendar = [
        pd.Timestamp(value).normalize()
        for value in ensure_calendar(DATA_START, END, token=None)
    ]
    frame = load_full_a_data(
        Path(args.price_root),
        Path(args.cap_root),
        DATA_START,
        END,
    ).sort_values(["instrument", "date"], ignore_index=True)
    close = close_panel(frame, calendar)
    financial = load_financial_cache(Path(args.financial_root))
    platform_runs = {
        record["id"]: read_platform_run(PROJECT_ROOT / record["raw_result"])
        for record in records
    }
    dates = sorted(
        {
            pd.Timestamp(value).normalize()
            for platform in platform_runs.values()
            for value in platform["dates"]
        }
    )
    if not dates:
        raise RuntimeError("Saved CFP runs have no chart dates")
    base = build_base_signal(frame, dates, financial)
    historical_cache: dict[tuple[str, int, str], pd.Series] = {}
    rows: list[dict[str, Any]] = []
    for record in records:
        handler = record["handler"]
        signal_dates = [
            pd.Timestamp(value).normalize()
            for value in platform_runs[record["id"]]["dates"]
        ]
        print(f"building={record['name']}", flush=True)
        for proxy in PROXIES:
            values = build_variant_values(
                frame,
                base,
                signal_dates,
                financial,
                handler,
                proxy,
                historical_cache,
            )
            result = evaluate_variant(
                frame,
                values,
                close,
                calendar,
                record,
                signal_dates,
            )
            rows.append(
                {
                    "id": record["id"],
                    "name": record["name"],
                    "handler": handler,
                    "proxy": proxy,
                    "cycle": int(record["configured_cycle"]),
                    "formula": record["formula"],
                    **result,
                }
            )
            print(
                f"  proxy={proxy} net={result['net_excess_pct']:.3f}% "
                f"delta={result['delta_net_pp']:.3f}pp periods={result['periods']}",
                flush=True,
            )
    write_report(rows, records, Path(args.output))
    print(f"report={Path(args.output) / 'financial_field_proxy_diagnosis.md'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-root", default=str(PRICE_ROOT_DEFAULT))
    parser.add_argument("--cap-root", default=str(CAP_ROOT_DEFAULT))
    parser.add_argument("--financial-root", default=str(FINANCIAL_ROOT_DEFAULT))
    parser.add_argument("--output", default=str(OUTPUT_DEFAULT))
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
