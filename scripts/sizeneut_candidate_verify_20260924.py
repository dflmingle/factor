"""Verify the size-neutral GP candidates: novelty, seat quality, pool impact.

For each candidate produced by `--objective aligned_size_neutral_net`:
  * recompute raw net and size-neutralised net under the project convention
  * |daily cross-sectional rank corr| against the size axis and against the five
    live pool seats
  * seat S_i (|RankIC| x |ICIR| x win), turnover, net
  * pool impact as a 6th equal-weight seat
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692,
           "book_to_market_lf_plus_impact": 0.01540}
CYCLE = 10
BUCKETS = 20


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def daily_rank_corr(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = []
    for date in left.index:
        x = left.loc[date].to_numpy(dtype="float64")
        y = right.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        a, b = pd.Series(x[ok]).rank(), pd.Series(y[ok]).rank()
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(values)) if values else float("nan")


def seat_stats(panel: pd.DataFrame, forward: pd.DataFrame) -> dict:
    rics, ics, turns, held, bench = [], [], [], [], []
    previous: set[str] = set()
    for date in panel.index:
        f = panel.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        x, r = f[ok], y[ok]
        if np.std(x) == 0 or np.std(r) == 0:
            continue
        instruments = panel.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        if previous:
            turns.append(1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); bench.append(float(r.mean()))
        rics.append(float(np.corrcoef(pd.Series(x).rank(), pd.Series(r).rank())[0, 1]))
        ics.append(float(np.corrcoef(x, r)[0, 1]))
    if len(ics) < 3:
        return {"periods": len(ics)}
    rics, ics = np.array(rics), np.array(ics)
    mean_rank, mean_ic = float(rics.mean()), float(ics.mean())
    std_ic = float(ics.std(ddof=1))
    win = float((ics > 0.02).mean()) if mean_ic >= 0 else float((ics < -0.02).mean())
    ic_ir = mean_ic / std_ic if std_ic else 0.0
    turnover = float(np.mean(turns)) if turns else 0.0
    years = len(held) * CYCLE / 252
    gross = float(np.prod(1 + np.array(held)) ** (1 / years)
                  - np.prod(1 + np.array(bench)) ** (1 / years))
    return dict(periods=len(ics), rank_ic=mean_rank, ic_ir=ic_ir, win=win,
                s_i=abs(mean_rank) * abs(ic_ir) * win, direction=int(mean_ic >= 0),
                seat_turnover=turnover, seat_gross=gross,
                seat_net=gross - turnover * (252.0 / CYCLE) * 0.006)


def pool_metrics(score: pd.DataFrame, forward: pd.DataFrame, seat_si: dict) -> dict:
    held, gross, turnover, valid = [], [], [], []
    previous: set[str] = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan)
            valid.append(False); continue
        x, r = f[ok], y[ok]
        instruments = score.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); gross.append(float(r[order].mean() - r.mean()))
        valid.append(True)
    held, gross, turnover = np.array(held), np.array(gross), np.array(turnover)
    valid = np.array(valid)
    if valid.sum() < 3:
        return dict(pool_na=np.nan, pool_nc=np.nan, pool_comb=np.nan, pool_net=np.nan,
                    pool_turnover=np.nan)
    held_clean = np.nan_to_num(held[valid]); bench_clean = np.nan_to_num(held[valid] - gross[valid])
    years = int(valid.sum()) * CYCLE / 252.0
    gross_annual = float(np.prod(1 + held_clean) ** (1 / years) - np.prod(1 + bench_clean) ** (1 / years))
    turn_mean = float(np.nanmean(turnover[valid]))
    net = gross_annual - turn_mean * (252.0 / CYCLE) * 0.006
    after_cost = held[valid] - np.where(np.isfinite(turnover[valid]), turnover[valid] * 0.006, 0.0)
    sr = float(after_cost.mean() / after_cost.std(ddof=1) * np.sqrt(252.0 / CYCLE))
    curve = np.cumprod(1 + after_cost)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    raw_c = max(net, 0.0) / max(2 * turn_mean, 0.3) * sr * (1 - 1.2 * dd)
    nc = min(max(raw_c / 0.6, 0.0), 1.0)
    return dict(pool_na=na, pool_nc=nc, pool_comb=0.20 * na + 0.45 * nc, pool_net=net,
                pool_turnover=turn_mean)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    records = pd.DataFrame(json.loads((run_dir / "aligned_ic_records.json").read_text()))
    chosen = records.nlargest(args.top, "net_excess")
    print(f"run={run_dir.name} records={len(records)} top={len(chosen)}", flush=True)

    cache_root = gp.DEFAULT_CACHE_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root, data_start, end).sort_values(
        ["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
        end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
        device=device, financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    context = gp.AlignedNetExcessContext(
        frame=frame, calendar=cal, data=data, start_date=start, end_date=end,
        cycle=CYCLE, label_offset=1, groups=10, round_trip_cost=0.006)
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(context.forward_returns.detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids))

    bp = gp.build_size_bucket_panel(frame, context, data, BUCKETS)
    bucket = torch.tensor(bp, dtype=torch.long, device=device)
    offsets = (torch.arange(bp.shape[0], device=device, dtype=torch.long).unsqueeze(1)
               * BUCKETS).expand_as(bucket)

    total_mv = frame.set_index(["date", "instrument"])["total_mv"].unstack("instrument")
    total_mv = total_mv.reindex(index=context.calendar, columns=context.stock_ids)
    total_mv_signal = total_mv.iloc[context.signal_calendar_positions]
    total_mv_signal.index = signal_dates
    size_panel = total_mv_signal.reindex(columns=forward.columns)

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in POOL}
    seat_z = {k: zscore(p) for k, p in seat_panels.items()}
    base = pool_metrics(sum(seat_z.values()) / len(POOL), forward, SEAT_SI)
    print("seed pool:", {k: round(v, 4) for k, v in base.items()}, flush=True)

    namespace = gp.expression_namespace()
    rows = []
    for _, record in chosen.iterrows():
        formula = str(record["formula"])
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
                raw_panel = pd.DataFrame(values[context.signal_data_positions].detach().cpu().numpy(),
                                         index=signal_dates, columns=list(data._stock_ids)
                                         ).reindex(index=signal_dates, columns=forward.columns)
                neu_values = gp.size_neutralise_panel(values, bucket, offsets, BUCKETS)
                neu_panel = pd.DataFrame(neu_values[context.signal_data_positions].detach().cpu().numpy(),
                                         index=signal_dates, columns=list(data._stock_ids)
                                         ).reindex(index=signal_dates, columns=forward.columns)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {formula[:50]}: {type(exc).__name__}", flush=True)
            continue
        finite_share = float(np.isfinite(raw_panel.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            continue
        raw_stats = seat_stats(raw_panel, forward)
        neu_stats = seat_stats(neu_panel, forward)
        direction = neu_stats["direction"] if np.isfinite(neu_stats.get("direction", np.nan)) else 1
        oriented = neu_panel if direction == 1 else -neu_panel
        corr_size = daily_rank_corr(oriented, seat_panels["size_only"])
        corrs = {k: daily_rank_corr(oriented, seat_panels[k]) for k in POOL}
        oriented_z = zscore(oriented)
        score6 = (sum(seat_z.values()) + oriented_z) / (len(POOL) + 1)
        seat_si = dict(SEAT_SI); seat_si["candidate"] = neu_stats["s_i"]
        add = pool_metrics(score6, forward, seat_si)
        rows.append(dict(
            formula=formula[:70], raw_net=raw_stats.get("seat_net"), neu_net=neu_stats.get("seat_net"),
            neu_turnover=neu_stats.get("seat_turnover"), s_i=neu_stats.get("s_i"),
            s_i_raw=raw_stats.get("s_i"), rank_ic=neu_stats.get("rank_ic"), ic_ir=neu_stats.get("ic_ir"),
            win=neu_stats.get("win"), corr_size=corr_size,
            corr_max_seat=max(abs(v) for v in corrs.values()),
            corr_max_seat_name=max(corrs, key=lambda k: abs(corrs[k])),
            add6_na=add["pool_na"], add6_nc=add["pool_nc"], add6_comb=add["pool_comb"],
            delta_points=40000 * 1.1 * (add["pool_comb"] - base["pool_comb"])))
        print(f"  ok net_neu={neu_stats['seat_net']:+.4f} turn={neu_stats['seat_turnover']:.3f} "
              f"S_i={neu_stats['s_i']:.4f} corr_size={corr_size:+.3f}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(run_dir / "candidate_verification.csv", index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 40)
    print("\n=== verification ===", flush=True)
    print(out[["raw_net", "neu_net", "neu_turnover", "s_i", "rank_ic", "ic_ir", "win",
               "corr_size", "corr_max_seat", "corr_max_seat_name", "add6_comb", "delta_points"]]
          .round(4).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
