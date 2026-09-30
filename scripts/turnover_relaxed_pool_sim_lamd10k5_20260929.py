"""Turnover-relaxed pool re-simulation with the platform-correct monthly C term.

Zero platform compute. For each candidate: build its cross-sectional score from the
same full-A / qfq / total_mv panel, append it to the verified 5-seat pool, and score
the 6-seat pool MONTH BY MONTH:

  NC_m = min(1, Rex_ann * SR_ann * (1 - 1.2*MaxDD_m) / 0.6 / max(T_m, 0.30))
  points_m = min(44000 * (0.20*NA + 0.35*NB + 0.45*NC_m), 40000)

Differences vs relaxed_gp_screen_20260924 / ab_batch_20260925:
  * MaxDD/SR/Rex come from a DAILY equal-weighted curve of the held decile, scoped to
    the calendar month (platform uses the current-month daily ledger), instead of a
    single full-period period-frequency drawdown.
  * T_m is the sum of that month's rebalance turnover (platform `turn`), not max(2t, 0.30).
  * NC is recomputed per month and then averaged.
  * NA reported on two bases: local S_i as-is, and local*1.354 (09-24 fixture uplift).
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402
from independent_information_combination import DATA_START, END  # noqa: E402
from stfilter_local_recheck import ensure_calendar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REBUILT = ROOT / "research_reports/platform_alignment/ab-batch-20260929/seat_panels_rebuilt.pkl"
OUT = ROOT / "research_reports/platform_alignment/turnover-relaxed-lamd10k5-20260929"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI_LOCAL = {"size_only": 0.010244872746, "impact60": 0.01578596817,
                 "t10_size_plus_impact_bm": 0.03725596,
                 "book_to_market_lf_minus_size": 0.01692,
                 "book_to_market_lf_plus_impact": 0.01540}
UPLIFT = 0.02589 / 0.01912
CYCLE, COST, GROUPS = 10, 0.006, 10
BONUS, CAP = 1.10, 40000.0
W_A, W_B, W_C = 0.20, 0.35, 0.45
A_ANCHOR, B_ANCHOR, C_ANCHOR = 0.08, 0.06, 0.60

CANDIDATES = {
 "LAMD10-K5V2": 'Div(Add(Add(Add(RANK(Sub(0,MA(amount,60))), RANK(Sub(0,MA(Div(Sub(close,open),open),20)))), RANK(Sub(0,STDDEV(turnover,20)))), RANK(MA(Div(ABS(RETURNS(close,1)),amount),20))), 5) + Div(RANK(Sub(0,Div(STDDEV(volume,6),STDDEV(volume,756)))), 5)',
}



def rank_ic_stats(context, panel: torch.Tensor, start=None) -> dict:
    indices = context._selected_indices(start, None)
    if not indices:
        return {}
    rows = panel[[context.signal_data_positions[i] for i in indices]]
    returns = context.forward_returns[indices]
    eligible = context.signal_eligible[indices]
    valid = torch.isfinite(rows) & eligible & torch.isfinite(returns)
    counts = valid.sum(dim=1)
    series = gp.batch_spearmanr_linear(rows, returns)
    keep = (counts >= GROUPS * 10) & torch.isfinite(series)
    if not bool(keep.any().item()):
        return {}
    s = series[keep].detach().float()
    mean = float(s.mean().item())
    std = float(s.std(unbiased=True).item()) if s.numel() > 1 else 0.0
    ir = mean / std if std > 0 else 0.0
    win = (float((s > 0.02).float().mean().item()) if mean >= 0
           else float((s < -0.02).float().mean().item()))
    return {"rank_ic": mean, "rank_ic_ir": ir, "rank_ic_win": win,
            "s_i_rank": abs(mean) * abs(ir) * win}


def selection(score_block: np.ndarray, forward_block: np.ndarray,
              instrument_block: np.ndarray, weights: np.ndarray):
    """Replicates _evaluate_combinations_numba for one period and one mask."""
    score_sum = np.zeros(len(forward_block), dtype=np.float64)
    valid = np.isfinite(forward_block)
    for column in range(score_block.shape[1]):
        if weights[column] == 0:
            continue
        column_values = score_block[:, column]
        valid &= np.isfinite(column_values)
        score_sum += np.where(np.isfinite(column_values), column_values, 0.0)
    score_sum = score_sum / weights.sum() + np.arange(len(forward_block)) * 1e-12
    if valid.sum() < GROUPS * 10:
        return None
    index = np.flatnonzero(valid)
    work = score_sum[index]
    cutoff = (len(index) * (GROUPS - 1)) // GROUPS
    partition = np.argpartition(work, cutoff)[cutoff:]
    held_rows = index[partition]
    return dict(held_rows=held_rows,
                held_return=float(forward_block[held_rows].mean()),
                benchmark=float(forward_block[index].mean()),
                instruments=instrument_block[held_rows])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    names = [n for n in (args.only.split(",") if args.only else list(CANDIDATES)) if n]

    payload = pickle.load(REBUILT.open("rb"))
    seats = payload["scores"][POOL].reset_index(drop=True)
    signal_frame = payload["signal_frame"]
    returns_table = payload["returns"]
    dates = [pd.Timestamp(d) for d in payload["dates"]]
    print(f"seats {seats.shape}; signal rows {len(signal_frame)}; dates {len(dates)}", flush=True)

    print("loading full-A frame", flush=True)
    calendar = [pd.Timestamp(x).normalize() for x in ensure_calendar(DATA_START, END, token=None)]
    data_start = pd.Timestamp(DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, data_start, end)
    frame = e.select_market_cap(frame, e.ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    print(f"frame rows {len(frame)} instruments {len(stock_ids)} calendar {len(cal)}", flush=True)

    close = e.panel_close(frame, cal)
    close = close.reindex(index=cal).ffill()
    print(f"close panel {close.shape}", flush=True)

    print("building TushareStockData", flush=True)
    device = torch.device("cpu")
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
        end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
        device=device, financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    context = gp.AlignedNetExcessContext(
        frame=frame, calendar=cal, data=data, start_date=start, end_date=end,
        cycle=CYCLE, label_offset=1, groups=GROUPS, round_trip_cost=COST)
    ctx_dates = [pd.Timestamp(d) for d in context.signal_dates]
    print(f"context signal dates {len(ctx_dates)} {ctx_dates[0].date()}..{ctx_dates[-1].date()}", flush=True)
    assert ctx_dates == dates, "context dates differ from rebuilt seat panels"
    del frame
    gc.collect()

    namespace = gp.expression_namespace()
    signal_index = pd.MultiIndex.from_frame(signal_frame[["date", "instrument"]])
    daily_returns = close.pct_change()
    column_position = {instrument: position for position, instrument in enumerate(close.columns)}
    calendar_position = {date: position for position, date in enumerate(cal)}

    keys = POOL + ["cand"]
    results = []
    for name in names:
        formula = CANDIDATES[name]
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
            del expression
            gc.collect()
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] EVAL FAIL {type(exc).__name__}: {exc}"[:200], flush=True)
            continue

        spots = np.asarray(context.signal_data_positions, dtype=np.int64)
        panel = pd.DataFrame(values[spots].detach().cpu().numpy(),
                             index=dates, columns=[str(x) for x in data._stock_ids])
        finite_share = float(np.isfinite(panel.to_numpy()).mean())
        print(f"[{name}] finite_share={finite_share:.4f}", flush=True)

        stats = None
        for candidate_direction in (1, -1):
            oriented_tensor = values if candidate_direction == 1 else -values
            with torch.no_grad():
                stats = rank_ic_stats(context, oriented_tensor)
            if stats and stats["rank_ic"] >= 0:
                break
        if not stats:
            print(f"[{name}] no rank-IC stats, skip", flush=True)
            continue
        oriented_panel = panel if candidate_direction == 1 else -panel
        flat = oriented_panel.stack(dropna=False).reindex(signal_index)
        cand_score = e._competition_cross_sectional_scores(
            signal_frame, {"cand": flat}, [{"key": "cand", "handler": "cand", "direction": 1}])
        score_frame = pd.concat([seats, cand_score], axis=1).loc[:, keys]

        blocks = e._build_blocks(signal_frame, score_frame, returns_table, dates, keys)
        ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))
        weights_seed = np.array([1, 1, 1, 1, 1, 0], dtype=np.int8)
        weights_six = np.array([1, 1, 1, 1, 1, 1], dtype=np.int8)
        numba = e._evaluate_combinations_numba(
            fs, fr, fi, offsets,
            np.vstack([weights_seed, weights_six]).astype(np.int8),
            np.array([5, 6], dtype=np.int64))
        held_nb, gross_nb, turn_nb, counts_nb, valid_nb = numba

        instrument_block_all = np.asarray(
            [str(x) for x in pd.factorize(np.concatenate([b[1] for b in blocks]))[0]])

        scenarios = {}
        for tag, weights in (("seed", weights_seed), ("six", weights_six)):
            per_period = []
            for period, block in enumerate(blocks):
                begin, finish = int(offsets[period]), int(offsets[period + 1])
                instrument_block = np.asarray(block[1])
                choice = selection(fs[begin:finish], fr[begin:finish], instrument_block, weights)
                per_period.append(choice)
            scenarios[tag] = per_period

        curated = []
        for tag in ("seed", "six"):
            previous = set()
            for period, choice in enumerate(scenarios[tag]):
                if choice is None:
                    curated.append(dict(period=period, scenario=tag, date=dates[period], valid=False))
                    continue
                current = set(choice["instruments"].tolist())
                turnover = 0.5 if not previous else 1.0 - len(current & previous) / len(current)
                previous = current
                curated.append(dict(period=period, scenario=tag, date=dates[period], valid=True,
                                    held=choice["held_return"], benchmark=choice["benchmark"],
                                    turnover=turnover, instruments=choice["instruments"]))
        ledger = pd.DataFrame([{k: v for k, v in row.items() if k != "instruments"}
                               for row in curated])

        merged = ledger.pivot(index="period", columns="scenario")
        for tag, index in (("seed", 0), ("six", 1)):
            np.testing.assert_allclose(merged[("held", tag)].to_numpy(),
                                       held_nb[index], equal_nan=True, rtol=1e-10, atol=1e-12)

        close_values = close.to_numpy(dtype="float64")

        def build_daily(tag: str) -> pd.DataFrame:
            """Official C ledger: buy-and-hold long basket vs buy-and-hold universe.

            Returns daily PORTFOLIO (cost-adjusted) and BENCHMARK returns; SR and
            MaxDD use the portfolio curve, Rex compounds the two separately.
            """
            lookup = {row["period"]: row for row in curated if row["scenario"] == tag}
            days, portfolio, benchmark = [], [], []
            for period, row in lookup.items():
                if not row["valid"]:
                    continue
                base = calendar_position[dates[period]] + 1
                if base + CYCLE >= len(cal):
                    continue
                rows = list(range(base, base + CYCLE + 1))
                block = close_values[rows]
                anchor = block[0]
                held = np.array([column_position[x] for x in row["instruments"]
                                 if x in column_position], dtype=np.int64)
                held = held[np.isfinite(anchor[held]) & (anchor[held] > 0)]
                if held.size < 10:
                    continue
                universe = np.flatnonzero(np.isfinite(anchor) & (anchor > 0))
                portfolio_value = np.nanmean(block[:, held] / anchor[held], axis=1)
                benchmark_value = np.nanmean(block[:, universe] / anchor[universe], axis=1)
                portfolio_return = portfolio_value[1:] / portfolio_value[:-1] - 1.0
                benchmark_return = benchmark_value[1:] / benchmark_value[:-1] - 1.0
                if np.isfinite(row["turnover"]):
                    portfolio_return[0] -= row["turnover"] * COST
                days.extend(cal[base + 1: base + CYCLE + 1])
                portfolio.extend(portfolio_return.tolist())
                benchmark.extend(benchmark_return.tolist())
            return pd.DataFrame({"portfolio": portfolio, "benchmark": benchmark},
                                index=pd.DatetimeIndex(days))

        curves = {tag: build_daily(tag) for tag in ("seed", "six")}

        def monthly_table(tag: str) -> pd.DataFrame:
            """Official monthly C ledger (see competition_rules.md C section)."""
            frame = curves[tag]
            rows = []
            for (year, month), block in frame.groupby([frame.index.year, frame.index.month]):
                p = block["portfolio"].to_numpy(dtype="float64")
                b = block["benchmark"].to_numpy(dtype="float64")
                ok = np.isfinite(p) & np.isfinite(b)
                p, b = p[ok], b[ok]
                n = len(p)
                if n < 2:
                    continue
                r_p = float(np.prod(1 + p) - 1.0)
                r_b = float(np.prod(1 + b) - 1.0)
                rex_ann = (1 + r_p) ** (252.0 / n) - 1.0 - ((1 + r_b) ** (252.0 / n) - 1.0)
                std = float(p.std(ddof=1))
                sr_ann = float(p.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
                equity = np.cumprod(1 + p)
                dd = float(-(equity / np.maximum.accumulate(equity) - 1).min())
                mask = (ledger.date.dt.year == year) & (ledger.date.dt.month == month) \
                       & (ledger.scenario == tag) & ledger.valid
                turns = ledger.turnover[mask].to_numpy(dtype="float64")
                turns = turns[np.isfinite(turns)]
                rows.append(dict(year=year, month=month, days=n, r_p=r_p, r_b=r_b,
                                 rex_ann=rex_ann, sr_ann=sr_ann, max_dd=dd,
                                 turnover_month=float(turns.sum())))
            return pd.DataFrame(rows)

        months = {tag: monthly_table(tag) for tag in ("seed", "six")}
        out_rows = []
        for label, uplift in (("local", 1.0), ("uplifted", UPLIFT)):
            for tag in ("seed", "six"):
                table = months[tag].copy()
                raw_a = float(np.mean(list(SEAT_SI_LOCAL.values())))
                if tag == "six":
                    raw_a = (raw_a * 5 + stats["s_i_rank"]) / 6.0
                raw_a *= uplift
                na = min(raw_a / A_ANCHOR, 0.70)
                nc = np.minimum(np.maximum(
                    table.rex_ann * table.sr_ann * (1 - 1.2 * table.max_dd) / C_ANCHOR
                    / np.maximum(table.turnover_month, 0.30), 0.0), 1.0)
                comb = W_A * na + W_C * nc
                points = np.minimum(CAP * BONUS * comb, CAP)
                table = table.assign(raw_a=raw_a, na=na, nb=0.0, nc=nc, comb=comb,
                                     points=points, scenario=tag, basis=label)
                out_rows.append(table)
        final = pd.concat(out_rows, ignore_index=True)
        pivot = final.pivot_table(index=["basis", "year", "month"],
                                  columns="scenario", values=["nc", "points", "turnover_month"])
        delta = (pivot[("points", "six")] - pivot[("points", "seed")])
        summary = {}
        for label in ("local", "uplifted"):
            series = delta.loc[label]
            summary[label] = dict(
                mean_points_delta=float(series.mean()),
                mean_points_delta_ex_first=float(series.iloc[1:].mean()),
                positive_months=int((series > 0).sum()), months=int(len(series)))
        print(f"[{name}] {json.dumps(summary, ensure_ascii=False)}", flush=True)
        results.append(dict(name=name, formula=formula, stats=stats, summary=summary,
                            finite_share=finite_share))

        final.to_csv(OUT / f"monthly_{name}.csv", index=False, encoding="utf-8-sig")
        ledger.to_csv(OUT / f"ledger_{name}.csv", index=False, encoding="utf-8-sig")
        for tag in ("seed", "six"):
            curves[tag].to_csv(OUT / f"daily_{name}_{tag}.csv", encoding="utf-8-sig")

    (OUT / "pool_resim_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
