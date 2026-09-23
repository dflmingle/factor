"""Full pool simulation for swapping frontier-mined seats into the live pool.

Previous swap estimates held the pool's Rex fixed at its current 20.3%, which
understates any seat that carries its own return stream.  This script rebuilds
the pool composite with the candidate as one equal-weight seat, re-measures the
pool's own net excess / turnover / Sharpe / drawdown, and recomputes NC/Comb.
"""
from __future__ import annotations

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
RUN_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/reports/alphaprobe_gp_tushare"
OUT = ROOT / "research_reports/platform_alignment/ic-frontier-mining-20260923"
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692,
           "book_to_market_lf_plus_impact": 0.01540}
WEAKEST = "size_only"
CYCLE = 10


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def pool_metrics(score: pd.DataFrame, forward: pd.DataFrame, seat_si: dict[str, float]) -> dict:
    """score/forward are date x instrument matrices on the aligned signal dates."""
    held, gross, turnover, counts, valid = [], [], [], [], []
    previous: set[str] = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan)
            counts.append(0); valid.append(False); continue
        x, r = f[ok], y[ok]
        inst = score.columns.to_numpy()[ok]
        n = int(len(x) * 0.1)
        order = np.argsort(-x)[:n]
        selected = set(inst[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean()))
        gross.append(float(r[order].mean() - r.mean()))
        counts.append(len(x)); valid.append(True)
    held = np.array(held); gross = np.array(gross); turnover = np.array(turnover)
    valid = np.array(valid)
    held_clean = np.nan_to_num(held[valid]); bench_clean = np.nan_to_num(held[valid] - gross[valid])
    years = int(valid.sum()) * CYCLE / 252.0
    gross_annual = float(np.prod(1 + held_clean) ** (1 / years) - np.prod(1 + bench_clean) ** (1 / years))
    turn_mean = float(np.nanmean(turnover[valid]))
    annual_cost = turn_mean * (252.0 / CYCLE) * 0.006
    net = gross_annual - annual_cost
    after_cost = held[valid] - np.where(np.isfinite(turnover[valid]), turnover[valid] * 0.006, 0.0)
    sr = float(after_cost.mean() / after_cost.std(ddof=1) * np.sqrt(252.0 / CYCLE))
    curve = np.cumprod(1 + after_cost)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    raw_c = max(net, 0.0) / max(2 * turn_mean, 0.3) * sr * (1 - 1.2 * dd)
    nc = min(max(raw_c / 0.6, 0.0), 1.0)
    return dict(na=na, nc=nc, comb=0.20 * na + 0.45 * nc, net=net, gross=gross_annual,
                turnover=turn_mean, monthly_turnover=2 * turn_mean, sr=sr, dd=dd, raw_c=raw_c)


def main() -> int:
    records = pd.read_csv(OUT / "frontier_records.csv")
    records = records[(records.turnover <= 0.40) | (records.s_i >= 0.05)]
    top = records.nlargest(40, "s_i")
    # cache root / panels
    cache_root = gp.DEFAULT_CACHE_ROOT
    batch_root = gp.DEFAULT_BATCH_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    aligned_start = pd.Timestamp(gp.ALIGNMENT_START)
    aligned_end = pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(batch_root, cap_root, data_start, aligned_end)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    analysis_calendar = [d for d in calendar if data_start <= d <= aligned_end]
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=analysis_calendar, instrument=stock_ids,
        start_time=gp.date_text(aligned_start), end_time=gp.date_text(aligned_end),
        max_backtrack_days=756, max_future_days=0, device=device,
        financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    context = gp.AlignedNetExcessContext(
        frame=frame, calendar=analysis_calendar, data=data, start_date=aligned_start,
        end_date=aligned_end, cycle=CYCLE, label_offset=1, groups=10, round_trip_cost=0.006)
    namespace = gp.expression_namespace()
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(
        context.forward_returns.detach().cpu().numpy(), index=signal_dates, columns=list(data._stock_ids))

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {
        key: seat_frame.pivot(index="date", columns="instrument", values=key)
        .reindex(index=signal_dates, columns=forward.columns)
        for key in POOL
    }
    base_score = sum(zscore(panel) for panel in seat_panels.values()) / len(POOL)
    base = pool_metrics(base_score, forward, SEAT_SI)
    print("seed:", {k: round(v, 4) for k, v in base.items()}, flush=True)

    rows = [dict(candidate="seed", formula="+".join(POOL), s_i=float(np.mean(list(SEAT_SI.values()))),
                 seat_turnover=np.nan, tag="seed", **base)]
    for _, record in top.iterrows():
        formula = str(record["formula"])
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
                candidate_panel = pd.DataFrame(
                    values[context.signal_data_positions].detach().cpu().numpy(),
                    index=signal_dates, columns=list(data._stock_ids)
                ).reindex(index=signal_dates, columns=forward.columns)
        except Exception as exc:  # noqa: BLE001
            print(f"skip {formula[:50]}: {type(exc).__name__}", flush=True)
            continue
        finite_share = float(np.isfinite(candidate_panel.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            print(f"skip degenerate {formula[:44]} finite_share={finite_share:.3f}", flush=True)
            continue
        candidate_z = zscore(candidate_panel)
        for tag, keep in (("replace-SIZE", [k for k in POOL if k != WEAKEST]), ("add-6th", POOL)):
            score = (sum(zscore(seat_panels[k]) for k in keep) + candidate_z) / (len(keep) + 1)
            seat_si = {k: SEAT_SI[k] for k in keep}
            seat_si["candidate"] = float(record["s_i"])
            metrics = pool_metrics(score, forward, seat_si)
            rows.append(dict(candidate=formula[:60], formula=formula, s_i=float(record["s_i"]),
                             seat_turnover=float(record["turnover"]), finite_share=finite_share,
                             tag=tag, **metrics))
    result = pd.DataFrame(rows).sort_values("comb", ascending=False)
    result.to_csv(OUT / "swap_simulation.csv", index=False)
    pd.set_option("display.width", 200)
    print(result[["tag", "s_i", "seat_turnover", "na", "nc", "comb", "net", "monthly_turnover", "sr", "dd"]]
          .head(20).round(4).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
