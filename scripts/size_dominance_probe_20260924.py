"""Is high net excess in our explored space really pinned to the size axis?

Three falsifiable checks, all offline:

  A. pool decomposition  - recompute the pool's net excess with SIZE dropped,
                           and the 5x5 seat correlation matrix.
  B. population scan     - take the top-N mined formulas by net excess and measure
                           each one's correlation with the size seat, plus its
                           net excess AFTER daily cross-sectional neutralisation
                           against size.  If size is the well, neutralised net
                           collapses and corr<->net move together.
  C. counterexample hunt - report any formula with net excess >= 10% AND
                           |corr_size| <= 0.5.  A single one falsifies "size only".

Offline only; no platform credits.
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
RECORDS = [
    ROOT / "research_reports/platform_alignment/net-scale-mining-20260923/net_scale_records.csv",
    ROOT / "research_reports/platform_alignment/ic-frontier-mining-20260923/frontier_records.csv",
]
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
WEAKEST = "size_only"
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692,
           "book_to_market_lf_plus_impact": 0.01540}
CYCLE = 10


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


def neutralise(panel: pd.DataFrame, axis: pd.DataFrame, buckets: int = 20) -> pd.DataFrame:
    """Bucket the cross-section by the axis and demean the panel inside each bucket."""
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
            if mask.sum() < 5:
                continue
            residual[mask] -= residual[mask].mean()
        row = np.full(panel.shape[1], np.nan)
        row[np.flatnonzero(ok)] = residual
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
        held.append(float(r[order].mean()))
        bench.append(float(r.mean()))
    if len(held) < 3:
        return dict(periods=len(held), gross=np.nan, net=np.nan, turnover=np.nan)
    held, bench = np.array(held), np.array(bench)
    years = len(held) * CYCLE / 252
    gross = float(np.prod(1 + held) ** (1 / years) - np.prod(1 + bench) ** (1 / years))
    turnover = float(np.mean(turns)) if turns else 0.0
    return dict(periods=len(held), gross=gross, turnover=turnover,
                net=gross - turnover * (252.0 / CYCLE) * 0.006)


def pool_net(score: pd.DataFrame, forward: pd.DataFrame) -> dict:
    return portfolio_net(score, forward)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--min-net", type=float, default=0.05)
    parser.add_argument("--sample", choices=["top", "random"], default="top")
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

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
    namespace = gp.expression_namespace()
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(context.forward_returns.detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids))
    print(f"window {signal_dates[0].date()}..{signal_dates[-1].date()} "
          f"{len(signal_dates)} dates, {forward.shape[1]} instruments", flush=True)

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in POOL}
    seat_z = {k: zscore(p) for k, p in seat_panels.items()}

    # ---- A. pool decomposition -------------------------------------------------
    print("\n=== A. seat correlation matrix (daily cross-sectional rank) ===", flush=True)
    matrix = pd.DataFrame(
        [[daily_rank_corr(seat_panels[a], seat_panels[b]) for b in POOL] for a in POOL],
        index=POOL, columns=POOL)
    print(matrix.round(3).to_string(), flush=True)
    base = pool_net(sum(seat_z.values()) / len(POOL), forward)
    without = pool_net(sum(seat_z[k] for k in POOL if k != WEAKEST) / (len(POOL) - 1), forward)
    print(f"\npool net with all 5 seats : {base['net']:+.4f}  turnover {base['turnover']:.3f}", flush=True)
    print(f"pool net without SIZE    : {without['net']:+.4f}  turnover {without['turnover']:.3f}", flush=True)
    neutral_seat_z = {k: zscore(neutralise(seat_panels[k], seat_panels[WEAKEST]))
                      for k in POOL}
    neutral_pool = pool_net(sum(neutral_seat_z.values()) / len(POOL), forward)
    print(f"pool net, all 5 seats size-neutralised: {neutral_pool['net']:+.4f}  "
          f"turnover {neutral_pool['turnover']:.3f}", flush=True)
    only_neutral = pool_net(neutral_seat_z[WEAKEST], forward)
    print(f"size-only seat neutralised           : {only_neutral['net']:+.4f}  "
          f"turnover {only_neutral['turnover']:.3f}", flush=True)
    pd.DataFrame([dict(scenario="all-5", **base), dict(scenario="drop-SIZE", **without),
                  dict(scenario="all-5-size-neutralised", **neutral_pool),
                  dict(scenario="size-seat-neutralised", **only_neutral)]).to_csv(
        args.out / "pool_decomposition.csv", index=False)

    # ---- B. population scan ----------------------------------------------------
    records = []
    for path in RECORDS:
        chunk = pd.read_csv(path)
        chunk["source"] = path.parent.name
        records.append(chunk)
    records = pd.concat(records, ignore_index=True)
    records = records.dropna(subset=["formula", "net_excess"])
    healthy = records[(records["periods"].fillna(0) >= 100) & (records["coverage"].fillna(0) >= 0.5)]
    print(f"\n=== B. population scan ===", flush=True)
    print(f"records {len(records)} | healthy {len(healthy)}", flush=True)
    if args.sample == "top":
        top = healthy.nlargest(args.top, "net_excess").drop_duplicates("formula")
    else:
        top = (healthy.drop_duplicates("formula")
               .sample(n=min(args.top, healthy.drop_duplicates("formula").shape[0]),
                       random_state=args.seed))
    print(f"scanning {len(top)} sampled by '{args.sample}'", flush=True)

    rows, failures = [], 0
    for i, record in enumerate(top.itertuples(), 1):
        formula = str(record.formula)
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
            panel = pd.DataFrame(values[context.signal_data_positions].detach().cpu().numpy(),
                                 index=signal_dates, columns=list(data._stock_ids)
                                 ).reindex(index=signal_dates, columns=forward.columns)
        except Exception:  # noqa: BLE001
            failures += 1
            continue
        finite_share = float(np.isfinite(panel.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            failures += 1
            continue
        corr = daily_rank_corr(panel, seat_panels[WEAKEST])
        raw = portfolio_net(panel if corr >= 0 else -panel, forward)
        neutral = portfolio_net(neutralise(panel if corr >= 0 else -panel, seat_panels[WEAKEST]), forward)
        rows.append(dict(formula=formula, source=record.source,
                         gp_net_excess=float(record.net_excess), corr_size=corr,
                         finite_share=finite_share, raw_net=raw["net"],
                         raw_turnover=raw["turnover"], neutralised_net=neutral["net"],
                         neutralised_turnover=neutral["turnover"],
                         net_kept=(neutral["net"] / raw["net"]) if raw["net"] and np.isfinite(raw["net"]) else np.nan))
        if i % 25 == 0:
            print(f"  {i}/{len(top)} scanned, {len(rows)} scored, {failures} skipped", flush=True)

    scan = pd.DataFrame(rows)
    scan.to_csv(args.out / "population_scan.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"\nscored {len(scan)}, skipped {failures}", flush=True)
    if len(scan):
        bins = pd.cut(scan["corr_size"], [-1.01, -0.6, -0.3, 0.3, 0.6, 0.8, 0.95, 1.01])
        summary = scan.groupby(bins, observed=True).agg(
            n=("formula", "size"), mean_raw_net=("raw_net", "mean"),
            mean_neutral_net=("neutralised_net", "mean"),
            mean_corr=("corr_size", "mean")).round(4)
        print("\n-- net excess by size correlation bucket --", flush=True)
        print(summary.to_string(), flush=True)
        strong = scan[scan["raw_net"] >= 0.10]
        print(f"\nraw seat net >= 10%: {len(strong)} / {len(scan)}", flush=True)
        survivors = strong[strong["corr_size"].abs() <= 0.5]
        print(f"  ... of which |corr with SIZE| <= 0.5 : {len(survivors)}", flush=True)
        if len(survivors):
            print(survivors.sort_values("raw_net", ascending=False)
                  [["formula", "raw_net", "corr_size", "neutralised_net"]].head(15).to_string(index=False),
                  flush=True)
        print("\n-- best neutralised (size removed) --", flush=True)
        print(scan.nlargest(10, "neutralised_net")
              [["formula", "raw_net", "corr_size", "neutralised_net", "neutralised_turnover", "net_kept"]]
              .round(4).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
