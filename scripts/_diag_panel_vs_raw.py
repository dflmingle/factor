"""单条候选的原始值 vs 秩面板打分对照（诊断用）。"""
from __future__ import annotations
import gc, sys, time
from pathlib import Path
import numpy as np, pandas as pd, torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import alphaprobe_gp_tushare as gp
import relaxed_gp_screen_20260924 as screen

PANELS = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/panels"
MATCHES = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "cand0125"
    idx = int(target[4:])
    meta = pd.read_csv(MATCHES)
    row = meta[meta["candidate"] == target].iloc[0]
    print(f"formula: {row['formula'][:120]}", flush=True)
    print(f"csv net={float(row['net']):.6f} turnover={float(row['turnover']):.6f}", flush=True)

    cache_root = gp.DEFAULT_CACHE_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root, data_start, end).sort_values(
        ["instrument", "date"], ignore_index=True)
    downcast = {c: "float32" for c in frame.columns if frame[c].dtype == "float64"}
    if downcast:
        frame = frame.astype(downcast); gc.collect()
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
        end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
        device=torch.device("cpu"), financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    context = gp.AlignedNetExcessContext(
        frame=frame, calendar=cal, data=data, start_date=start, end_date=end,
        cycle=screen.CYCLE, label_offset=1, groups=10, round_trip_cost=screen.COST)
    print("data ready", flush=True)

    namespace = gp.expression_namespace()
    expr = gp.evaluate_formula(str(row["formula"]), namespace)
    with torch.no_grad():
        values = gp.finite_as_nan(expr.evaluate(data))
    raw_stats = context.score(values)
    print(f"[raw ] net={raw_stats['net_excess']:.6f} turnover={raw_stats['turnover']:.6f} "
          f"dd={raw_stats['absolute_max_drawdown']:.4f} excess_dd={raw_stats['excess_max_drawdown']:.4f}",
          flush=True)

    panel = np.load(PANELS / f"cand_{idx:04d}.npy")
    buffer = np.full((len(cal), len(stock_ids)), np.nan, dtype="float32")
    buffer[list(context.signal_data_positions), :] = panel
    rank_stats = context.score(torch.from_numpy(buffer))
    print(f"[rank] net={rank_stats['net_excess']:.6f} turnover={rank_stats['turnover']:.6f} "
          f"dd={rank_stats['absolute_max_drawdown']:.4f} excess_dd={rank_stats['excess_max_drawdown']:.4f}",
          flush=True)

    raw_panel = gp.finite_as_nan(values).detach().cpu().numpy()
    same = np.nanmax(np.abs(panel.astype("float64") - 0.0)) if panel.size else 0.0
    print(f"[diag] panel finite share={np.isfinite(panel).mean():.3f} "
          f"raw finite share={np.isfinite(raw_panel[[context.signal_data_positions], :]).mean():.3f}",
          flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())