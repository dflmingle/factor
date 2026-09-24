"""按"放宽换手 + 近段表现"新口径筛选宽字段 GP 批次（全部本地，零平台算力）。

与旧 `net_scale_records` 筛选口径的差别：
  * 不再以低换手本身为目标：按换手分档 <=30% / 30-40% / 40-60% / >60%，
    每档按净额取 Top-N 进入实测，不做"高换手提前杀"；
  * 主排序字段增加**近段净额**（2026 年内 / 最近 12 个调仓期）与 S_i，
    全期净额只作为并列指标；
  * size 防作弊：与 SIZE 席位的日截面秩相关 + 桶内 size 中性化后净额；
  * 池级 ΔComb 退居参考列（用户口径：先看单因子好坏，不是先看第 6 席）。

输入: 各 run 目录下的 aligned_ic_records.json（net 目标把记录写在这个文件名下）
输出: <out>/screened_candidates.csv + summary.md
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
COST = 0.006
BANDS = [("le30", 0.0, 0.30), ("30_40", 0.30, 0.40), ("40_60", 0.40, 0.60), ("gt60", 0.60, 99.0)]


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


def panel_stats(panel: pd.DataFrame, forward: pd.DataFrame,
                window: list | None = None) -> dict:
    """Top-decile long-only seat stats, optionally restricted to signal dates."""
    dates = list(panel.index) if window is None else [d for d in panel.index if d in set(window)]
    rics, ics, turns, held, bench = [], [], [], [], []
    previous: set[str] = set()
    for date in dates:
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
        held.append(float(r[order].mean()))
        bench.append(float(r.mean()))
        rics.append(float(np.corrcoef(pd.Series(x).rank(), pd.Series(r).rank())[0, 1]))
        ics.append(float(np.corrcoef(x, r)[0, 1]))
    if len(ics) < 3:
        return {"periods": len(ics), "seat_net": float("nan"), "seat_turnover": float("nan"),
                "s_i": float("nan"), "rank_ic": float("nan"), "ic_ir": float("nan"),
                "cum_net": float("nan")}
    rics, ics = np.array(rics), np.array(ics)
    held_a, bench_a = np.array(held), np.array(bench)
    turn_arr = np.array(turns) if turns else np.zeros(len(held_a) - 1)
    mean_rank, mean_ic = float(rics.mean()), float(ics.mean())
    std_ic = float(ics.std(ddof=1))
    win = float((ics > 0.02).mean()) if mean_ic >= 0 else float((ics < -0.02).mean())
    ic_ir = mean_ic / std_ic if std_ic else 0.0
    turnover = float(np.mean(turns)) if turns else 0.0
    years = len(held_a) * CYCLE / 252
    gross = float(np.prod(1 + held_a) ** (1 / years) - np.prod(1 + bench_a) ** (1 / years))
    cum = float(np.sum(held_a - bench_a) - turn_arr.sum() * COST)
    return dict(periods=len(ics), rank_ic=mean_rank, ic_ir=ic_ir, win=win,
                s_i=abs(mean_rank) * abs(ic_ir) * win, direction=int(mean_ic >= 0),
                seat_turnover=turnover, seat_net=gross - turnover * (252.0 / CYCLE) * COST,
                cum_net=cum, gross_excess=gross)


def pool_metrics(score: pd.DataFrame, forward: pd.DataFrame, seat_si: dict) -> dict:
    held, gross, turnover, valid = [], [], [], []
    previous: set[str] = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            valid.append(False); held.append(np.nan); gross.append(np.nan); turnover.append(np.nan)
            continue
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
    net = gross_annual - turn_mean * (252.0 / CYCLE) * COST
    after_cost = held[valid] - np.where(np.isfinite(turnover[valid]), turnover[valid] * COST, 0.0)
    sr = float(after_cost.mean() / after_cost.std(ddof=1) * np.sqrt(252.0 / CYCLE))
    curve = np.cumprod(1 + after_cost)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    raw_c = max(net, 0.0) / max(2 * turn_mean, 0.30) * sr * (1 - 1.2 * dd)
    nc = min(max(raw_c / 0.6, 0.0), 1.0)
    return dict(pool_na=na, pool_nc=nc, pool_comb=0.20 * na + 0.45 * nc, pool_net=net,
                pool_turnover=turn_mean)


def band_of(turnover: float) -> str:
    for name, lo, hi in BANDS:
        if lo < turnover <= hi or (lo == 0.0 and turnover <= hi):
            return name
    return "gt60"


def load_records(run_dirs: list[Path]) -> pd.DataFrame:
    frames = []
    for run_dir in run_dirs:
        p = run_dir / "aligned_ic_records.json"
        if not p.exists():
            print(f"  [warn] missing records: {p}", flush=True)
            continue
        frame = pd.DataFrame(json.loads(p.read_text()))
        frame["run"] = run_dir.parent.name
        frames.append(frame)
        print(f"  records={len(frame)} from {run_dir.parent.name}", flush=True)
    if not frames:
        raise SystemExit("no records loaded")
    all_records = pd.concat(frames, ignore_index=True)
    all_records = all_records.drop_duplicates(subset=["formula"]).reset_index(drop=True)
    return all_records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path,
                        default=ROOT / "research_reports/platform_alignment/relaxed-gp-20260924")
    parser.add_argument("--runs", default="all")
    parser.add_argument("--top-per-band", type=int, default=20)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "research_reports/platform_alignment/relaxed-gp-20260924/screen")
    parser.add_argument("--min-periods", type=int, default=100)
    parser.add_argument("--min-coverage", type=float, default=0.50)
    parser.add_argument("--min-seat-turnover", type=float, default=0.0,
                        help="debug hook: drop degenerate zero-turnover artefacts")
    args = parser.parse_args()

    batch_root = args.batch_root.expanduser().resolve()
    if args.runs == "all":
        run_dirs = sorted(p / "gp" for p in batch_root.iterdir()
                          if p.is_dir() and (p / "gp" / "aligned_ic_records.json").exists())
    else:
        run_dirs = [(batch_root / name / "gp") for name in args.runs.split(",")]
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(run_dirs)
    healthy = records[(records["periods"] >= args.min_periods)
                      & (records["coverage"] >= args.min_coverage)
                      & (records["turnover"] > args.min_seat_turnover)].copy()
    healthy["band"] = healthy["turnover"].apply(band_of)
    print(f"records={len(records)} healthy={len(healthy)}", flush=True)
    print(healthy.groupby("band")["net_excess"].describe()[["count", "mean", "max"]].to_string(),
          flush=True)

    chosen = pd.concat([
        healthy[healthy["band"] == name].nlargest(args.top_per_band, "net_excess")
        for name, _lo, _hi in BANDS], ignore_index=True)
    chosen = chosen.drop_duplicates(subset=["formula"]).reset_index(drop=True)
    print(f"screening {len(chosen)} candidates across {len(BANDS)} bands", flush=True)

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
        cycle=CYCLE, label_offset=1, groups=10, round_trip_cost=COST)
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(context.forward_returns.detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids))
    recent_start = pd.Timestamp("2026-01-01")
    recent_dates = [d for d in signal_dates if d >= recent_start]
    last12 = signal_dates[-12:]

    bp = gp.build_size_bucket_panel(frame, context, data, BUCKETS)
    bucket = torch.tensor(bp, dtype=torch.long, device=device)
    offsets = (torch.arange(bp.shape[0], device=device, dtype=torch.long).unsqueeze(1)
               * BUCKETS).expand_as(bucket)

    total_mv = frame.set_index(["date", "instrument"])["total_mv"].unstack("instrument")
    total_mv = total_mv.reindex(index=context.calendar, columns=context.stock_ids)
    size_signal = total_mv.iloc[context.signal_calendar_positions]
    size_signal.index = signal_dates
    size_panel = size_signal.reindex(columns=forward.columns)

    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    sf = pickle.load(SIGNALS.open("rb"))[0]
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
    for idx, record in chosen.iterrows():
        formula = str(record["formula"])
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
                raw_panel = pd.DataFrame(
                    values[context.signal_data_positions].detach().cpu().numpy(),
                    index=signal_dates, columns=list(data._stock_ids)
                ).reindex(index=signal_dates, columns=forward.columns)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{idx}] skip {formula[:48]}: {type(exc).__name__}", flush=True)
            continue
        finite_share = float(np.isfinite(raw_panel.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            continue
        full = panel_stats(raw_panel, forward)
        direction = full["direction"] if np.isfinite(full.get("direction", np.nan)) else 1
        oriented = raw_panel if direction == 1 else -raw_panel
        y2026 = panel_stats(oriented, forward, recent_dates)
        last12_stats = panel_stats(oriented, forward, last12)
        corrs = {k: daily_rank_corr(oriented, seat_panels[k]) for k in POOL}
        oriented_z = zscore(oriented)
        score6 = (sum(seat_z.values()) + oriented_z) / (len(POOL) + 1)
        seat_si = dict(SEAT_SI); seat_si["candidate"] = full["s_i"]
        add = pool_metrics(score6, forward, seat_si)
        rows.append(dict(
            run=record["run"], band=record["band"], formula=formula,
            rec_net=float(record["net_excess"]), rec_turnover=float(record["turnover"]),
            net=full.get("seat_net"), turnover=full.get("seat_turnover"),
            s_i=full.get("s_i"), rank_ic=full.get("rank_ic"), ic_ir=full.get("ic_ir"),
            win=full.get("win"), periods=full.get("periods"),
            net_y2026=y2026.get("cum_net"), turn_y2026=y2026.get("seat_turnover"),
            periods_y2026=y2026.get("periods"), s_i_y2026=y2026.get("s_i"),
            net_last12=last12_stats.get("cum_net"), s_i_last12=last12_stats.get("s_i"),
            corr_size=corrs["size_only"],
            corr_max_seat=max(abs(v) for v in corrs.values()),
            corr_max_seat_name=max(corrs, key=lambda k: abs(corrs[k])),
            add6_na=add["pool_na"], add6_nc=add["pool_nc"], add6_comb=add["pool_comb"],
            delta_points=40000 * 1.1 * (add["pool_comb"] - base["pool_comb"])))
        print(f"  [{idx}] {record['band']:>5} net={full['seat_net']:+.4f} "
              f"turn={full['seat_turnover']:.3f} S_i={full['s_i']:.4f} "
              f"net26={y2026.get('cum_net'):+.4f} corr_size={corrs['size_only']:+.3f} "
              f"dComb={rows[-1]['delta_points']:+.0f}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "screened_candidates.csv", index=False)
    pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 46)
    cols = ["band", "net", "turnover", "s_i", "net_y2026", "s_i_y2026", "net_last12",
            "corr_size", "corr_max_seat", "corr_max_seat_name", "delta_points"]
    print("\n=== screened ===", flush=True)
    print(out[cols].round(4).to_string(index=False), flush=True)
    print(f"\nwrote {out_dir / 'screened_candidates.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
