"""(diagnostic) Raw-orientation view of the size-neutral GP candidates.

The GP optimised net excess on a *size-bucket-demeaned* panel. That panel is not
what the platform ranks, so this script re-reads the same formulas in their raw
form: both orientations, gross vs cost split, and the size correlation of the
raw panel.

Output: research_reports/platform_alignment/sizeneut-gp-20260924/raw_orientation_diag.csv
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    records = pd.DataFrame(json.loads((run_dir / "aligned_ic_records.json").read_text()))
    chosen = records.nlargest(args.top, "net_excess")
    print(f"run={run_dir.name} records={len(records)} diagnosing top={len(chosen)}", flush=True)

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

    bp = gp.build_size_bucket_panel(frame, context, data, V.BUCKETS)
    bucket = torch.tensor(bp, dtype=torch.long, device=device)
    offsets = (torch.arange(bp.shape[0], device=device, dtype=torch.long).unsqueeze(1)
               * V.BUCKETS).expand_as(bucket)

    sf, _raw, _returns, _dates = pickle.load(V.SIGNALS.open("rb"))
    seat_scores = pickle.load(V.SEATS.open("rb"))["scores"][V.POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in V.POOL}

    namespace = gp.expression_namespace()
    rows = []
    for _, record in chosen.iterrows():
        formula = str(record["formula"])
        expression = gp.evaluate_formula(formula, namespace)
        with torch.no_grad():
            values = gp.finite_as_nan(expression.evaluate(data))
            raw_panel = pd.DataFrame(values[context.signal_data_positions].detach().cpu().numpy(),
                                     index=signal_dates, columns=list(data._stock_ids)
                                     ).reindex(index=signal_dates, columns=forward.columns)
            neu_values = gp.size_neutralise_panel(values, bucket, offsets, V.BUCKETS)
            neu_panel = pd.DataFrame(neu_values[context.signal_data_positions].detach().cpu().numpy(),
                                     index=signal_dates, columns=list(data._stock_ids)
                                     ).reindex(index=signal_dates, columns=forward.columns)

        row = {"formula": formula[:70], "gp_neutralised_net": record["net_excess"]}
        for tag, panel in (("raw", raw_panel), ("neu", neu_panel)):
            plus = V.seat_stats(panel, forward)      # top decile by descending value
            minus = V.seat_stats(-panel, forward)     # flipped orientation
            best = plus if plus["seat_net"] >= minus["seat_net"] else minus
            row.update({
                f"{tag}_rank_ic": plus["rank_ic"], f"{tag}_ic_ir": plus["ic_ir"],
                f"{tag}_ic_win": plus["win"],
                f"{tag}_turnover": plus["seat_turnover"],
                f"{tag}_gross": plus["seat_gross"], f"{tag}_net": plus["seat_net"],
                f"{tag}_net_flipped": minus["seat_net"],
                f"{tag}_gross_flipped": minus["seat_gross"],
                f"{tag}_turnover_flipped": minus["seat_turnover"],
                f"{tag}_best_net": best["seat_net"], f"{tag}_best_dir": best["direction"],
            })
        # size correlation of the raw panel, in the orientation that makes it best
        raw_dir = 1 if V.seat_stats(raw_panel, forward)["seat_net"] >= V.seat_stats(-raw_panel, forward)["seat_net"] else -1
        neu_dir = 1 if V.seat_stats(neu_panel, forward)["seat_net"] >= V.seat_stats(-neu_panel, forward)["seat_net"] else -1
        row["raw_dir"] = raw_dir
        row["neu_dir"] = neu_dir
        row["raw_corr_size"] = V.daily_rank_corr(raw_panel if raw_dir == 1 else -raw_panel,
                                                 seat_panels["size_only"])
        row["neu_corr_size"] = V.daily_rank_corr(neu_panel if neu_dir == 1 else -neu_panel,
                                                 seat_panels["size_only"])
        row["raw_corr_neu"] = V.daily_rank_corr(raw_panel, neu_panel)
        rows.append(row)
        print(f"  raw: ic={row['raw_rank_ic']:+.4f} turn={row['raw_turnover']:.3f} "
              f"gross={row['raw_gross']:+.4f} net={row['raw_net']:+.4f} "
              f"| flipped net={row['raw_net_flipped']:+.4f} | corr_size={row['raw_corr_size']:+.3f} "
              f"| neu net={row['neu_net']:+.4f} corr_size={row['neu_corr_size']:+.3f}",
              flush=True)

    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "raw_orientation_diag.csv", index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 30)
    print("\n=== raw orientation ===", flush=True)
    print(out[["formula", "raw_rank_ic", "raw_turnover", "raw_gross", "raw_net",
               "raw_net_flipped", "raw_corr_size", "neu_net", "neu_corr_size"]]
          .round(4).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
