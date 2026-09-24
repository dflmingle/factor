"""(attribution) How much of the size-neutral objective's edge is still size?

The GP maximised net excess on a 20-bucket size-demeaned panel. The best family
scores +13~15% there while its *raw* orientation has ~zero IC, so the question is
whether the residual alpha is itself size. This script re-measures the same
formulas after progressively stronger size strips:

  V0 none                     raw panel
  V1 b20                      20 quantile buckets, within-bucket demean  (the objective)
  V2 b40                      40 buckets
  V3 b100                     100 buckets
  V4 b20 + daily global OLS   remove the residual's per-day linear size-rank component
  V5 b20 + within-bucket OLS  remove the per-day, per-bucket size-rank component

For every variant we report gross / turnover / net (best of the two orientations),
rank IC, and the mean per-day within-bucket rank correlation with the size axis.

Output: research_reports/platform_alignment/sizeneut-gp-20260924/size_attribution.csv
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
import sizeneut_candidate_verify_20260924 as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/sizeneut-gp-20260924"


def demean_within(panel: np.ndarray, bucket: np.ndarray, n_buckets: int) -> np.ndarray:
    """Subtract the per-(date, bucket) mean; entries with missing bucket stay put."""
    out = panel.copy()
    for day in range(panel.shape[0]):
        row_b, row_v = bucket[day], panel[day]
        valid = (row_b >= 0) & np.isfinite(row_v)
        if not valid.any():
            continue
        idx = row_b[valid]
        vals = row_v[valid]
        sums = np.bincount(idx, weights=vals, minlength=n_buckets)
        counts = np.bincount(idx, minlength=n_buckets)
        means = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
        row_v[valid] = vals - means[idx]
        out[day] = row_v
    return out


def strip_linear(panel: np.ndarray, axis: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Per-day OLS residual of panel on `axis` (optionally restricted to `mask`)."""
    out = panel.copy()
    for day in range(panel.shape[0]):
        x = axis[day].astype("float64")
        y = panel[day].astype("float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if mask is not None:
            ok &= mask[day]
        if ok.sum() < 30:
            continue
        xs = pd.Series(x[ok]).rank().to_numpy()
        if xs.std() == 0:
            continue
        A = np.column_stack([np.ones(ok.sum()), (xs - xs.mean()) / xs.std()])
        coef, *_ = np.linalg.lstsq(A, y[ok], rcond=None)
        out[day][ok] = y[ok] - A @ coef
    return out


def within_bucket_corr(panel: np.ndarray, axis: np.ndarray, bucket: np.ndarray) -> float:
    values = []
    for day in range(panel.shape[0]):
        x, y, b = axis[day], panel[day], bucket[day]
        for k in np.unique(b[b >= 0]):
            ok = (b == k) & np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 30:
                continue
            a = pd.Series(x[ok]).rank(); c = pd.Series(y[ok]).rank()
            if a.std() == 0 or c.std() == 0:
                continue
            values.append(float(np.corrcoef(a, c)[0, 1]))
    return float(np.mean(values)) if values else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    records = pd.DataFrame(json.loads((run_dir / "aligned_ic_records.json").read_text()))
    chosen = records.nlargest(args.top, "net_excess")
    print(f"run={run_dir.name} records={len(records)} attribution on top={len(chosen)}", flush=True)

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
        cycle=V.CYCLE, label_offset=1, groups=10, round_trip_cost=0.006)
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(context.forward_returns.detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids))

    bp = {}
    for n in (20, 40, 100):
        bp[n] = gp.build_size_bucket_panel(frame, context, data, n)
    bucket_t = {n: torch.tensor(v, dtype=torch.long, device=device) for n, v in bp.items()}
    offsets = {n: (torch.arange(v.shape[0], device=device, dtype=torch.long).unsqueeze(1) * n).expand_as(v)
               for n, v in bucket_t.items()}

    total_mv = frame.set_index(["date", "instrument"])["total_mv"].unstack("instrument")
    total_mv = total_mv.reindex(index=context.calendar, columns=context.stock_ids)
    size_signal = total_mv.iloc[context.signal_calendar_positions]
    size_signal.index = signal_dates
    size_panel = size_signal.reindex(columns=forward.columns)
    size_axis = (-size_panel.rank(axis=1)).to_numpy(dtype="float64")  # -rank(total_mv)

    namespace = gp.expression_namespace()
    rows = []
    for _, record in chosen.iterrows():
        formula = str(record["formula"])
        expression = gp.evaluate_formula(formula, namespace)
        with torch.no_grad():
            values = gp.finite_as_nan(expression.evaluate(data))
            raw = values[context.signal_data_positions].detach().cpu().numpy()
        neu = {}
        for n in (20, 40, 100):
            with torch.no_grad():
                neu[n] = gp.size_neutralise_panel(values, bucket_t[n], offsets[n], n
                                                  )[context.signal_data_positions].detach().cpu().numpy()
        variants = {"V0 none": raw, "V1 b20": neu[20], "V2 b40": neu[40], "V3 b100": neu[100]}
        variants["V4 b20 + daily OLS on size"] = strip_linear(neu[20], size_axis)
        variants["V5 b20 + within-bucket OLS on size"] = strip_linear(neu[20], size_axis,
                                                                     mask=bp[20] >= 0)
        for name, panel in variants.items():
            frame_panel = pd.DataFrame(panel, index=signal_dates, columns=forward.columns)
            plus = V.seat_stats(frame_panel, forward)
            minus = V.seat_stats(-frame_panel, forward)
            best = plus if plus["seat_net"] >= minus["seat_net"] else minus
            oriented = frame_panel if best is plus else -frame_panel
            rows.append(dict(
                formula=formula[:48], variant=name,
                rank_ic=plus["rank_ic"], turnover=best["seat_turnover"],
                gross=best["seat_gross"], net=best["seat_net"],
                best_dir=best["direction"],
                corr_size=V.daily_rank_corr(oriented, pd.DataFrame(size_axis, index=signal_dates,
                                                                   columns=forward.columns)),
                corr_size_within_bucket=within_bucket_corr(panel, size_axis, bp[20]),
            ))
            print(f"  {formula[:34]:34s} {name:38s} ic={plus['rank_ic']:+.4f} "
                  f"turn={best['seat_turnover']:.3f} gross={best['seat_gross']:+.4f} "
                  f"net={best['seat_net']:+.4f} corr_size={rows[-1]['corr_size']:+.3f} "
                  f"corr_size_in_bucket={rows[-1]['corr_size_within_bucket']:+.3f}", flush=True)

    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "size_attribution.csv", index=False)
    print("\n=== attribution ===", flush=True)
    pd.set_option("display.width", 300)
    print(out[["variant", "rank_ic", "turnover", "gross", "net", "corr_size",
               "corr_size_within_bucket"]].round(4).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
