"""(debug) Cache the top candidate's panels so variants can be re-run without a reload.

Writes /tmp/sizeneut_panels.npz with raw / neu20 / neu40 / neu100 panels, the size
axis, the signal-aligned 20-bucket panel, forward returns and the signal dates,
then prints distribution diagnostics for each panel.
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
import sizeneut_candidate_verify_20260924 as V  # noqa: E402

OUT = Path("/tmp/sizeneut_panels.npz")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    records = pd.DataFrame(json.loads((run_dir / "aligned_ic_records.json").read_text()))
    record = records.nlargest(1, "net_excess").iloc[0]
    formula = str(record["formula"])
    print("formula:", formula, flush=True)

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
    signal_dates = np.array([str(pd.Timestamp(d).date()) for d in context.signal_dates])
    forward = context.forward_returns.detach().cpu().numpy()

    buckets, neutrals = {}, {}
    for n in (20, 40, 100):
        buckets[n] = gp.build_size_bucket_panel(frame, context, data, n)
        bt = torch.tensor(buckets[n], dtype=torch.long, device=device)
        offsets = (torch.arange(bt.shape[0], device=device, dtype=torch.long).unsqueeze(1)
                   * n).expand_as(bt)
        neutralals = None
        with torch.no_grad():
            expression = gp.evaluate_formula(formula, gp.expression_namespace())
            values = gp.finite_as_nan(expression.evaluate(data))
            raw_full = values.detach().cpu().numpy()
            neutrals[n] = gp.size_neutralise_panel(values, bt, offsets, n
                                                   ).detach().cpu().numpy()

    total_mv = frame.set_index(["date", "instrument"])["total_mv"].unstack("instrument")
    total_mv = total_mv.reindex(index=context.calendar, columns=context.stock_ids)
    size_signal = total_mv.iloc[context.signal_calendar_positions]
    size_axis = (-size_signal.rank(axis=1)).to_numpy(dtype="float64")

    sig = np.array(context.signal_data_positions)          # model-calendar rows
    sig_cal = np.array(context.signal_calendar_positions)  # trade-calendar rows
    print(f"calendar={len(context.calendar)} model_rows={raw_full.shape[0]} "
          f"signal_data max={sig.max()} signal_cal max={sig_cal.max()} "
          f"total_mv rows={total_mv.shape[0]}", flush=True)
    payload = dict(
        formula=np.array([formula]),
        signal_dates=signal_dates,
        instruments=np.array(list(context.stock_ids)),
        raw=raw_full[sig], size_axis=size_axis, forward=forward,
        **{f"neu{n}": neutrals[n][sig] for n in (20, 40, 100)},
        **{f"bucket{n}": buckets[n][sig] for n in (20, 40, 100)},
    )
    np.savez_compressed(OUT, **payload)
    print("saved", OUT, flush=True)

    for name in ("raw", "neu20", "neu40", "neu100"):
        panel = payload[name]
        finite = np.isfinite(panel)
        print(f"\n{name}: shape={panel.shape} finite={finite.mean():.3f} "
              f"nan={np.isnan(panel).mean():.3f}", flush=True)
        absvals = np.abs(panel[finite])
        if absvals.size:
            qs = np.percentile(absvals, [50, 90, 99, 99.9, 100])
            print(f"  |value| p50/p90/p99/p99.9/max = " + " ".join(f"{q:.4g}" for q in qs),
                  flush=True)
        # per-day Pearson vs size axis
        pear, spear = [], []
        for day in range(panel.shape[0]):
            x, y = payload["size_axis"][day], panel[day]
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 100:
                continue
            a, b = x[ok], y[ok]
            if a.std() == 0 or b.std() == 0:
                continue
            pear.append(float(np.corrcoef(a, b)[0, 1]))
            spear.append(V.daily_rank_corr(
                pd.DataFrame(b[None, :], columns=np.arange(b.size)),
                pd.DataFrame(a[None, :], columns=np.arange(a.size))))
        print(f"  Pearson(y,size)={np.mean(pear):+.4f}  Spearman(y,size)={np.nanmean(spear):+.4f}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
