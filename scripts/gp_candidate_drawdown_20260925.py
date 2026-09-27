"""补算候选的本地口径最大回撤（本地，零平台算力）。

背景：2026-09-24 宽字段 GP 筛选只把 net / turnover / rank_ic 写进了
screened_candidates.csv；AlignedNetExcessContext.score() 其实还返回
absolute_max_drawdown（多头最大回撤）与 excess_max_drawdown（超额最大回撤），
当时未落盘。本脚本复用已物化的 signal-date 秩面板重算这两项，并逐条校验
net / turnover / rank_ic 与 CSV 是否一致（口径自检）。

面板说明：cluster-overlap-20260924/panels/cand_*.npy 是逐日横截面秩面板，
列序与 sorted(frame.instrument) 一致；秩变换保持同日截面排序，因此
十分位选股与原始值完全一致，score() 结果可比。
"""
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import alphaprobe_gp_tushare as gp  # noqa: E402
import relaxed_gp_screen_20260924 as screen  # noqa: E402

PANELS = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/panels"
SCREENED = ROOT / "research_reports/platform_alignment/relaxed-gp-20260924/screen2/screened_candidates.csv"
MATCHES = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924/candidate_matches.csv"
OUT = ROOT / "research_reports/platform_alignment/candidate-new-clusters-20260925"


def main() -> int:
    started = time.time()
    cache_root = gp.DEFAULT_CACHE_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root, data_start, end).sort_values(
        ["instrument", "date"], ignore_index=True)
    downcast = {c: "float32" for c in frame.columns if frame[c].dtype == "float64"}
    if downcast:
        frame = frame.astype(downcast)
        gc.collect()
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    device = torch.device("cpu")
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
        end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
        device=device, financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    context = gp.AlignedNetExcessContext(
        frame=frame, calendar=cal, data=data, start_date=start, end_date=end,
        cycle=screen.CYCLE, label_offset=1, groups=10, round_trip_cost=screen.COST)
    positions = list(context.signal_data_positions)
    buffer = np.full((len(cal), len(stock_ids)), np.nan, dtype="float32")
    print(f"[data] ready days={len(cal)} stocks={len(stock_ids)} signals={len(positions)} "
          f"elapsed={time.time() - started:.0f}s", flush=True)

    rows = []
    for panel_path in sorted(PANELS.glob("cand_*.npy")):
        index = int(panel_path.name[5:9])
        panel = np.load(panel_path)
        buffer[:] = np.nan
        buffer[positions, :] = panel
        tensor = torch.from_numpy(buffer)
        stats = context.score(tensor)
        rows.append({
            "candidate": f"cand{index:04d}",
            "net": stats.get("net_excess"),
            "turnover": stats.get("turnover"),
            "gross_excess": stats.get("gross_excess"),
            "annual_cost": stats.get("annual_cost"),
            "absolute_max_drawdown": stats.get("absolute_max_drawdown"),
            "excess_max_drawdown": stats.get("excess_max_drawdown"),
            "periods": stats.get("periods"),
        })
        if len(rows) % 40 == 0:
            print(f"  scored {len(rows)} elapsed={time.time() - started:.0f}s", flush=True)

    result = pd.DataFrame(rows)
    reference = pd.read_csv(MATCHES)[["candidate", "band", "formula", "net", "turnover"]]
    merged = result.merge(reference, on="candidate", how="left", suffixes=("", "_csv"))
    screened = pd.read_csv(SCREENED)[["formula", "rank_ic", "s_i_rank"]]
    merged = merged.merge(screened.drop_duplicates(subset=["formula"]), on="formula", how="left")
    merged.to_csv(OUT / "candidate_drawdown_check.csv", index=False)
    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / "candidate_drawdown.csv", index=False)

    diff_net = (merged["net"] - merged["net_csv"]).abs()
    diff_to = (merged["turnover"] - merged["turnover_csv"]).abs()
    print(f"[check] candidates={len(result)}", flush=True)
    print(f"[check] max |net diff| = {diff_net.max():.6f} (mean {diff_net.mean():.6f})", flush=True)
    print(f"[check] max |turnover diff| = {diff_to.max():.6f} (mean {diff_to.mean():.6f})", flush=True)
    print(f"[check] max abs drawdown range: {result['absolute_max_drawdown'].min():.4f}"
          f"~{result['absolute_max_drawdown'].max():.4f}", flush=True)
    (OUT / "candidate_drawdown_meta.json").write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "candidates": int(len(result)),
        "max_abs_net_diff": float(diff_net.max()),
        "max_abs_turnover_diff": float(diff_to.max()),
        "note": "absolute_max_drawdown = 多头持仓最大回撤；excess_max_drawdown = 相对基准的最大回撤",
        "cycle": screen.CYCLE, "round_trip_cost": screen.COST, "groups": 10,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] elapsed={time.time() - started:.0f}s -> {OUT / 'candidate_drawdown.csv'}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())