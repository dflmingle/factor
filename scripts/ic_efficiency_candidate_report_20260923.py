"""Merge aligned_ic_efficiency GP runs and rank the mined formulas.

Stage 1 (cheap): merge every ``aligned_ic_records.json`` under the run root,
deduplicate by formula, apply the seat admission gates we agreed on
(per-rebalance turnover <= 10%, S_i >= 0.02, net excess >= 12%, >= 100 aligned
periods) and rank by S_i per unit turnover ("efficiency").

Stage 2 (optional, ``--correlation``): reload the aligned panels, evaluate the
surviving formulas and report their average cross-sectional rank correlation
against the five seats of the submitted pool, so a candidate that merely
duplicates SIZE/H03/E/F/T10-ADD-BM is filtered out.

Offline only; no platform calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402

OUT = Path("research_reports/platform_alignment/ic-efficiency-mining-20260923")
RUN_ROOT = Path(
    "quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare"
)
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="ic_eff_run*_20260923")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--max-turnover", type=float, default=0.10)
    parser.add_argument("--min-si", type=float, default=0.02)
    parser.add_argument("--min-net", type=float, default=0.12)
    parser.add_argument(
        "--min-abs-net",
        action="store_true",
        help="treat the net-excess gate as |net|, admitting factors that must be submitted reversed",
    )
    parser.add_argument("--min-periods", type=int, default=100)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--correlation", action="store_true")
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def load_records(pattern: str) -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(RUN_ROOT.glob(f"{pattern}/aligned_ic_records.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload:
            item = dict(item)
            item["run"] = path.parent.name
            rows.append(item)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.drop_duplicates(subset=["formula"], keep="first")
    frame["turnover"] = pd.to_numeric(frame["turnover"], errors="coerce")
    frame["s_i"] = pd.to_numeric(frame["s_i"], errors="coerce")
    frame["net_excess"] = pd.to_numeric(frame["net_excess"], errors="coerce")
    frame["efficiency"] = pd.to_numeric(frame["efficiency"], errors="coerce")
    if "ic_periods" not in frame.columns:
        frame["ic_periods"] = pd.to_numeric(frame.get("periods"), errors="coerce")
    if "ic_mean" not in frame.columns:
        frame["ic_mean"] = np.nan
    return frame


def seat_signals(data, context, namespace, formulas: list[str]) -> dict[str, torch.Tensor]:
    """Evaluate each formula and slice it onto the aligned signal dates."""
    panels: dict[str, torch.Tensor] = {}
    for formula in formulas:
        expression = gp.evaluate_formula(formula, namespace)
        with torch.no_grad():
            factor = gp.finite_as_nan(expression.evaluate(data))
            panels[formula] = factor[context.signal_data_positions]
    return panels


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frame = load_records(args.runs)
    if frame.empty:
        print("no aligned_ic_records.json found")
        return 1
    total = len(frame)
    net_metric = frame["net_excess"].abs() if args.min_abs_net else frame["net_excess"]
    gated = frame[
        (frame["turnover"] <= args.max_turnover)
        & (frame["s_i"] >= args.min_si)
        & (net_metric >= args.min_net)
        & (frame["ic_periods"] >= args.min_periods)
    ].copy()
    gated["submitted_direction"] = np.where(gated["ic_mean"] >= 0, "1", "0(reversed)")
    gated = gated.sort_values("s_i", ascending=False)
    gated.to_csv(args.output / "mined_candidates_gated.csv", index=False)
    frame.sort_values("s_i", ascending=False).to_csv(
        args.output / "mined_candidates_all.csv", index=False
    )
    print(
        f"scored formulas {total}; passing gates {len(gated)} "
        f"(turnover<={args.max_turnover:.0%}, S_i>={args.min_si}, net>={args.min_net:.0%})"
    )
    if gated.empty:
        best = frame.sort_values("efficiency", ascending=False).head(5)
        print("closest by efficiency:")
        print(best[["formula", "s_i", "turnover", "efficiency", "net_excess"]].to_string(index=False))
        return 0
    top = gated.head(args.top)
    print(top[["formula", "s_i", "turnover", "efficiency", "net_excess", "rank_ic", "ic_ir", "ic_win"]]
          .to_string(index=False))
    if not args.correlation:
        return 0

    # ---- stage 2: correlation against the submitted pool seats -------------
    cache_root = gp.DEFAULT_CACHE_ROOT
    batch_root = gp.DEFAULT_BATCH_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    aligned_start = pd.Timestamp(gp.ALIGNMENT_START)
    aligned_end = pd.Timestamp(gp.ALIGNMENT_END)
    frame_panel = gp.load_full_a_data(batch_root, cap_root, data_start, aligned_end)
    frame_panel = frame_panel.sort_values(["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame_panel["instrument"].astype(str).unique())
    analysis_calendar = [d for d in calendar if data_start <= d <= aligned_end]
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame_panel,
        calendar=analysis_calendar,
        instrument=stock_ids,
        start_time=gp.date_text(aligned_start),
        end_time=gp.date_text(aligned_end),
        max_backtrack_days=756,
        max_future_days=0,
        device=device,
        financial_root=gp.DEFAULT_FINANCIAL_ROOT,
    )
    context = gp.AlignedNetExcessContext(
        frame=frame_panel,
        calendar=analysis_calendar,
        data=data,
        start_date=aligned_start,
        end_date=aligned_end,
        cycle=10,
        label_offset=1,
        groups=10,
        round_trip_cost=0.006,
    )
    namespace = gp.expression_namespace()
    candidate_panels = seat_signals(data, context, namespace, top["formula"].tolist())

    # Pool seats come from the qualitygate3 signal cache (their PandaAI formulas
    # are not evaluable in the AlphaPROBE namespace), so align on (date, instrument).
    import pickle

    cached_signals = Path(
        "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
    )
    sf, _raw, _returns, _dates = pickle.load(cached_signals.open("rb"))
    seat_frame = sf[["date", "instrument"]].copy()
    seat_scores = pickle.load(
        Path("research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl").open("rb")
    )["scores"][POOL]
    seat_frame = pd.concat([seat_frame.reset_index(drop=True), seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]

    rows = []
    for formula, panel in candidate_panels.items():
        values = panel.detach().cpu().numpy()
        frame = pd.DataFrame(values, index=signal_dates, columns=list(data._stock_ids))
        long = frame.stack(dropna=False).rename("candidate").reset_index()
        long.columns = ["date", "instrument", "candidate"]
        merged = long.merge(seat_frame, on=["date", "instrument"], how="inner")
        correlations = [
            float(
                merged.groupby("date")
                .apply(lambda group: group["candidate"].corr(group[key], method="spearman"))
                .mean()
            )
            for key in POOL
        ]
        record = top[top["formula"] == formula].iloc[0]
        rows.append(dict(
            formula=formula,
            s_i=float(record["s_i"]),
            turnover=float(record["turnover"]),
            efficiency=float(record["efficiency"]),
            net_excess=float(record["net_excess"]),
            max_pool_corr=float(np.nanmax(correlations)),
            corr_size=correlations[0], corr_h03=correlations[1],
            corr_t10=correlations[2], corr_e=correlations[3], corr_f=correlations[4],
        ))
    report = pd.DataFrame(rows).sort_values(["max_pool_corr", "s_i"], ascending=[True, False])
    report.to_csv(args.output / "mined_candidates_correlation.csv", index=False)
    print(report.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
