"""Score the 354 locally-mappable fields we have never used as pool seats.

For every field: build its raw panel through the AlphaPROBE adapter, then
measure it exactly like a seat - RankIC / ICIR / win -> S_i, top-decile
turnover, cost-adjusted net excess - on the same 120 aligned signal dates used
by the pool pipeline.  Fields are then ranked by S_i and by S_i per unit
turnover so the promising ones can be tested as marginal seats later.

Offline only.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path, PurePath

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402
from search_field_policy import ALIGNMENT_VERIFIED_SEARCH_FIELDS  # noqa: E402

OUT = Path("research_reports/platform_alignment/field-seat-screen-20260923")
FIELD_FILE = Path("research_reports/platform_alignment/wider-field-search-20260923/fields.txt")
VERIFIED = {str(f).lower() for f in ALIGNMENT_VERIFIED_SEARCH_FIELDS}
CYCLE = 10


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fields = [line.strip() for line in FIELD_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    fields = [f for f in fields if f not in VERIFIED]
    print(f"fields to screen (excluding the 20 verified): {len(fields)}", flush=True)

    cache_root = gp.DEFAULT_CACHE_ROOT
    batch_root = gp.DEFAULT_BATCH_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start = pd.Timestamp(gp.ALIGNMENT_START)
    end = pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(batch_root, cap_root, data_start, end).sort_values(
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

    rows = []
    failures = {}
    for index, field in enumerate(fields, start=1):
        try:
            expression = gp.evaluate_formula(field, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
            panel = pd.DataFrame(values[context.signal_data_positions].detach().cpu().numpy(),
                                 index=signal_dates, columns=list(data._stock_ids))
        except Exception as exc:  # noqa: BLE001
            failures[field] = f"{type(exc).__name__}: {exc}"
            continue
        finite_share = float(np.isfinite(panel.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            failures[field] = f"degenerate: finite share {finite_share:.3f}"
            continue
        rics, ics, turns, held, bench = [], [], [], [], []
        previous: set[str] = set()
        for date in signal_dates:
            f = panel.loc[date].to_numpy(dtype="float64")
            y = forward.loc[date].to_numpy(dtype="float64")
            ok = np.isfinite(f) & np.isfinite(y)
            if ok.sum() < 100:
                continue
            x, r = f[ok], y[ok]
            if np.std(x) == 0 or np.std(r) == 0:
                continue
            instruments = panel.columns.to_numpy()[ok]
            n = int(len(x) * 0.1)
            order = np.argsort(-x)[:n]
            selected = set(instruments[order].tolist())
            if previous:
                turns.append(1 - len(selected & previous) / len(selected))
            previous = selected
            held.append(float(r[order].mean()))
            bench.append(float(r.mean()))
            rics.append(float(np.corrcoef(pd.Series(x).rank().to_numpy(),
                                         pd.Series(r).rank().to_numpy())[0, 1]))
            ics.append(float(np.corrcoef(x, r)[0, 1]))
        if len(ics) < 100:
            failures[field] = f"insufficient periods ({len(ics)})"
            continue
        rics = np.array(rics); ics = np.array(ics)
        mean_rank, mean_ic, std_ic = float(rics.mean()), float(ics.mean()), float(ics.std(ddof=1))
        direction = 1 if mean_ic >= 0 else 0
        win = float((ics > 0.02).mean()) if direction == 1 else float((ics < -0.02).mean())
        ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0
        turnover = float(np.mean(turns)) if turns else 0.0
        years = len(held) * CYCLE / 252
        gross = float(np.prod(1 + np.array(held)) ** (1 / years)
                      - np.prod(1 + np.array(bench)) ** (1 / years))
        net = gross - turnover * (252.0 / CYCLE) * 0.006
        rows.append(dict(field=field, direction=direction, periods=len(ics),
                         rank_ic=mean_rank, ic_ir=ic_ir, win=win,
                         s_i=abs(mean_rank) * abs(ic_ir) * win,
                         turnover=turnover, gross=gross, net=net,
                         efficiency=abs(mean_rank) * abs(ic_ir) * win / max(turnover, 0.02),
                         finite_share=finite_share))
        if index % 25 == 0:
            print(f"  {index}/{len(fields)} done, {len(rows)} scored", flush=True)
    frame_out = pd.DataFrame(rows)
    frame_out.to_csv(OUT / "field_seat_screen.csv", index=False)
    (OUT / "failures.txt").write_text("\n".join(f"{k}: {v}" for k, v in sorted(failures.items())) + "\n",
                                      encoding="utf-8")
    print(f"scored {len(frame_out)} fields, failures {len(failures)}", flush=True)
    if len(frame_out):
        top = frame_out.sort_values("s_i", ascending=False).head(15)
        print(top[["field", "direction", "s_i", "rank_ic", "ic_ir", "win", "turnover", "net"]]
              .round(4).to_string(index=False), flush=True)
        print("\nbest efficiency (S_i per unit turnover):", flush=True)
        print(frame_out.sort_values("efficiency", ascending=False).head(10)[
            ["field", "s_i", "turnover", "efficiency", "net"]].round(4).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
