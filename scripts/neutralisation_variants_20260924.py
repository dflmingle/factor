"""Size-neutralisation variants for the pool, to check the headline result is
not an artefact of one particular neutralisation recipe.

Variants (all cross-sectional, per signal date, on the aligned window):
  N1 bucket-20 demean, seat-first   then equal-weight sum   [reported earlier]
  N2 bucket-20 demean, composite-first
  N3 OLS residual on the size rank, composite-first
  N4 OLS residual on log(total_mv), composite-first
  N5 bucket-20 demean on raw total_mv buckets, composite-first

The axis for N1/N2/N5 is rank-consistent, so bucket membership is identical;
the variants differ in *what* gets neutralised and in linearity.
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/size-dominance-probe-20260924"
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
CYCLE = 10


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def bucket_demean(panel: pd.DataFrame, axis: pd.DataFrame, buckets: int = 20) -> pd.DataFrame:
    out = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for date in panel.index:
        x = panel.loc[date].to_numpy(dtype="float64")
        a = axis.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(a)
        if ok.sum() < 200:
            continue
        ranks = pd.Series(a[ok]).rank(method="first").to_numpy()
        group = np.minimum((ranks / ok.sum() * buckets).astype(int), buckets - 1)
        residual = x[ok].copy()
        for g in range(buckets):
            mask = group == g
            if mask.sum() >= 5:
                residual[mask] -= residual[mask].mean()
        row = np.full(panel.shape[1], np.nan)
        row[np.flatnonzero(ok)] = residual
        out.loc[date] = row
    return out


def ols_residual(panel: pd.DataFrame, axis: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for date in panel.index:
        x = panel.loc[date].to_numpy(dtype="float64")
        a = axis.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(a) & np.isfinite(a)
        if ok.sum() < 200:
            continue
        design = np.column_stack([np.ones(ok.sum()), a[ok], a[ok] ** 2])
        beta, *_ = np.linalg.lstsq(design, x[ok], rcond=None)
        row = np.full(panel.shape[1], np.nan)
        row[np.flatnonzero(ok)] = x[ok] - design @ beta
        out.loc[date] = row
    return out


def portfolio_net(panel: pd.DataFrame, forward: pd.DataFrame) -> dict:
    held, bench, turns = [], [], []
    previous: set[str] = set()
    for date in panel.index:
        f = panel.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        x, r = f[ok], y[ok]
        if np.std(x) == 0:
            continue
        instruments = panel.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        if previous:
            turns.append(1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); bench.append(float(r.mean()))
    if len(held) < 3:
        return dict(periods=len(held), gross=np.nan, net=np.nan, turnover=np.nan)
    held, bench = np.array(held), np.array(bench)
    years = len(held) * CYCLE / 252
    gross = float(np.prod(1 + held) ** (1 / years) - np.prod(1 + bench) ** (1 / years))
    turnover = float(np.mean(turns)) if turns else 0.0
    return dict(periods=len(held), gross=round(gross, 4), turnover=round(turnover, 4),
                net=round(gross - turnover * (252.0 / CYCLE) * 0.006, 4))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

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

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in POOL}
    seat_z = {k: zscore(p) for k, p in seat_panels.items()}
    axis = seat_panels["size_only"]          # = -rank(total_mv), small cap = high
    composite = sum(seat_z.values()) / len(POOL)

    rows = []
    rows.append(dict(variant="composite, no neutralisation", **portfolio_net(composite, forward)))
    seat_first = sum(zscore(bucket_demean(seat_panels[k], axis)) for k in POOL) / len(POOL)
    rows.append(dict(variant="N1 seat-first bucket-20", **portfolio_net(seat_first, forward)))
    rows.append(dict(variant="N2 composite bucket-20",
                     **portfolio_net(bucket_demean(composite, axis), forward)))
    rows.append(dict(variant="N3 composite OLS on size rank",
                     **portfolio_net(ols_residual(composite, axis), forward)))
    flat_axis = axis.rank(axis=1, pct=True)
    rows.append(dict(variant="N4 composite bucket-20 on pct-rank",
                     **portfolio_net(bucket_demean(composite, flat_axis), forward)))
    result = pd.DataFrame(rows)
    result.to_csv(args.out / "neutralisation_variants.csv", index=False)
    pd.set_option("display.width", 200)
    print(result.to_string(index=False), flush=True)

    # sanity: how well does the axis explain the composite?
    ics = []
    for date in composite.index:
        x = composite.loc[date].to_numpy(dtype="float64")
        a = axis.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(a)
        if ok.sum() < 200:
            continue
        ics.append(float(np.corrcoef(pd.Series(x[ok]).rank(), pd.Series(a[ok]).rank())[0, 1]))
    print(f"\ncomposite vs size rank: mean daily rank corr = {np.mean(ics):.4f} "
          f"(n={len(ics)} dates)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
