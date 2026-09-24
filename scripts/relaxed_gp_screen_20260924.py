"""按"放宽换手 + 近段表现"新口径筛选宽字段 GP 批次（全部本地，零平台算力）。

口径与 GP 内部完全一致：组合构造、分档、换手、年度化都直接调用
`AlignedNetExcessContext.score / ic_series_stats`（这套代码同时是本地对齐规则的
实现），只额外做三件事：按方向定向、算近段窗口、算与现有 5 席的相关性。

与旧 `net_scale_records` 筛选的差别：
  * 换手分档按**重算值**（record 里的 turnover 在 size 中性化目标下是中性化后的，
    直接分档会把中性化噪声错当成低换手）；
  * 不以低换手本身为目标：<=30% / 30-40% / 40-60% / >60% 分档各自保留，
    主排序用近段净额 + S_i + 全期净额；
  * size 防作弊：与 SIZE 席位的日截面秩相关、以及桶内 size 中性化后的净额；
  * 池级 ΔComb 只作参考列（先看单因子好坏，不是先看第 6 席）。
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
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
COST = 0.006
BUCKETS = 20
BANDS = [("le30", 0.0, 0.30), ("30_40", 0.30, 0.40), ("40_60", 0.40, 0.60), ("gt60", 0.60, 99.0)]
FIELDS_CURATED = ROOT / "research_reports/platform_alignment/wider-field-search-20260923/fields.txt"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def band_of(turnover: float) -> str:
    for name, lo, hi in BANDS:
        if (lo == 0.0 and turnover <= hi) or lo < turnover <= hi:
            return name
    return "gt60"


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def leaf_signature(formula: str, known_fields: set[str]) -> str:
    leaves = sorted({token.lower() for token in IDENT.findall(str(formula))
                     if token.lower() in known_fields})
    return "|".join(leaves)


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


def score_panel(context, panel: torch.Tensor, start=None, end=None) -> dict:
    stats = context.score(panel, start_date=start, end_date=end)
    ic = context.ic_series_stats(panel, start_date=start, end_date=end)
    out = dict(stats)
    out.update({
        "rank_ic": ic.get("rank_ic"), "ic_ir": ic.get("ic_ir"), "ic_win": ic.get("ic_win"),
        "s_i": ic.get("s_i"), "direction": ic.get("direction"),
    })
    return out


def rank_ic_stats(context, panel: torch.Tensor, start=None, end=None) -> dict:
    """Platform-convention S_i: ICIR and win rate from the period RankIC series."""
    indices = context._selected_indices(start, end)
    if not indices:
        return {}
    rows = panel[[context.signal_data_positions[i] for i in indices]]
    returns = context.forward_returns[indices]
    eligible = context.signal_eligible[indices]
    valid = torch.isfinite(rows) & eligible & torch.isfinite(returns)
    counts = valid.sum(dim=1)
    series = gp.batch_spearmanr_linear(rows, returns)
    keep = (counts >= context.groups * 10) & torch.isfinite(series)
    if not bool(keep.any().item()):
        return {}
    series = series[keep].detach().float()
    mean = float(series.mean().item())
    std = float(series.std(unbiased=True).item()) if series.numel() > 1 else 0.0
    ir = mean / std if std > 0 else 0.0
    win = (float((series > 0.02).float().mean().item()) if mean >= 0
           else float((series < -0.02).float().mean().item()))
    return {"rank_ic_ir": ir, "rank_ic_win": win, "s_i_rank": abs(mean) * abs(ir) * win,
            "rank_ic_periods": int(series.numel())}


def pool_metrics(score: pd.DataFrame, forward: pd.DataFrame, eligible: pd.DataFrame,
                 seat_si: dict) -> dict:
    held, gross, turnover, valid = [], [], [], []
    previous: set[str] = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y) & eligible.loc[date].to_numpy(dtype=bool)
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
    held_clean = np.nan_to_num(held[valid])
    bench_clean = np.nan_to_num(held[valid] - gross[valid])
    years = int(valid.sum()) * CYCLE / 252.0
    gross_annual = float(np.prod(1 + held_clean) ** (1 / years)
                         - np.prod(1 + bench_clean) ** (1 / years))
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


def panel_frame(values: torch.Tensor, positions, signal_dates, columns) -> pd.DataFrame:
    return pd.DataFrame(values[positions].detach().cpu().numpy(),
                        index=signal_dates, columns=list(columns))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path,
                        default=ROOT / "research_reports/platform_alignment/relaxed-gp-20260924")
    parser.add_argument("--runs", default="all")
    parser.add_argument("--per-band", type=int, default=25,
                        help="candidates reported per recomputed turnover band")
    parser.add_argument("--pool-per-band", type=int, default=150,
                        help="pre-filter pool per record-level turnover band")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "research_reports/platform_alignment/relaxed-gp-20260924/screen")
    parser.add_argument("--min-periods", type=int, default=100)
    parser.add_argument("--min-coverage", type=float, default=0.50)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--device", default="cpu",
                        help="torch device; cpu keeps the screen from competing with GP runs for VRAM")
    args = parser.parse_args()

    batch_root = args.batch_root.expanduser().resolve()
    if args.runs == "all":
        run_names = sorted(p.name for p in batch_root.iterdir()
                           if (p / "gp" / "aligned_ic_records.json").exists())
    else:
        run_names = [name.strip() for name in args.runs.split(",") if name.strip()]
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for name in run_names:
        p = batch_root / name / "gp" / "aligned_ic_records.json"
        if not p.exists():
            print(f"  [warn] missing {p}", flush=True)
            continue
        frame = pd.DataFrame(json.loads(p.read_text()))
        frame["run"] = name
        frame["objective"] = json.loads((batch_root / name / "gp" / "gp_run.json").read_text()).get("objective")
        frames.append(frame)
        print(f"  records={len(frame)} from {name}", flush=True)
    if not frames:
        raise SystemExit("no records loaded")
    records = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["formula"])
    healthy = records[(records["periods"] >= args.min_periods)
                      & (records["coverage"] >= args.min_coverage)
                      & (records["turnover"] > 0.0)].copy()
    healthy["record_band"] = healthy["turnover"].apply(band_of)
    print(f"records={len(records)} healthy={len(healthy)}", flush=True)

    known_fields = set()
    if FIELDS_CURATED.exists():
        known_fields.update(line.strip().lower() for line in FIELDS_CURATED.read_text().splitlines()
                            if line.strip())
    pool = []
    for name, _lo, _hi in BANDS:
        band = healthy[healthy["record_band"] == name].nlargest(args.pool_per_band, "net_excess").copy()
        band["leaf_sig"] = band["formula"].apply(lambda f: leaf_signature(f, known_fields))
        pool.append(band.groupby("leaf_sig", sort=False).head(3))
    chosen = pd.concat(pool, ignore_index=True).drop_duplicates(subset=["formula"]).reset_index(drop=True)
    if args.shard_count > 1:
        chosen = chosen.iloc[args.shard_index::args.shard_count].reset_index(drop=True)
        print(f"shard {args.shard_index}/{args.shard_count} -> {len(chosen)} candidates", flush=True)
    print(f"evaluating pool={len(chosen)} from record bands", flush=True)

    cache_root = gp.DEFAULT_CACHE_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root, data_start, end).sort_values(
        ["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    device = torch.device(args.device)
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
    eligible = pd.DataFrame(context.signal_eligible.detach().cpu().numpy(),
                            index=signal_dates, columns=list(data._stock_ids))
    recent_start = pd.Timestamp("2026-01-01")
    last12_start = signal_dates[-12]

    bp = gp.build_size_bucket_panel(frame, context, data, BUCKETS)
    bucket = torch.tensor(bp, dtype=torch.long, device=device)
    offsets = (torch.arange(bp.shape[0], device=device, dtype=torch.long).unsqueeze(1)
               * BUCKETS).expand_as(bucket)

    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = pickle.load(SIGNALS.open("rb"))[0][["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in POOL}
    seat_z = {k: zscore(p) for k, p in seat_panels.items()}
    base = pool_metrics(sum(seat_z.values()) / len(POOL), forward, eligible, SEAT_SI)
    print("seed pool:", {k: round(v, 4) for k, v in base.items()}, flush=True)

    namespace = gp.expression_namespace()
    rows = []
    skipped = {"error": 0, "sparse": 0}
    for idx, record in chosen.iterrows():
        formula = str(record["formula"])
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
        except Exception as exc:  # noqa: BLE001
            skipped["error"] += 1
            print(f"  [{idx}] skip {formula[:48]}: {type(exc).__name__}: {exc}"[:160], flush=True)
            continue
        raw = panel_frame(values, context.signal_data_positions, signal_dates, data._stock_ids)
        finite_share = float(np.isfinite(raw.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            skipped["sparse"] += 1
            continue
        with torch.no_grad():
            full = score_panel(context, values)
        direction = int(full.get("direction") or 1)
        oriented_values = values if direction == 1 else -values
        oriented = raw if direction == 1 else -raw
        with torch.no_grad():
            full.update(rank_ic_stats(context, oriented_values))
            y2026 = score_panel(context, oriented_values, start=recent_start)
            y2026.update(rank_ic_stats(context, oriented_values, start=recent_start))
            last12 = score_panel(context, oriented_values, start=last12_start)
            neu_values = gp.size_neutralise_panel(values, bucket, offsets, BUCKETS)
            neu_full = score_panel(context, neu_values)
            neu_direction = int(neu_full.get("direction") or 1)
            if neu_direction == -1:
                neu_full = score_panel(context, -neu_values)
        corrs = {k: daily_rank_corr(oriented, seat_panels[k]) for k in POOL}
        oriented_z = zscore(oriented)
        score6 = (sum(seat_z.values()) + oriented_z) / (len(POOL) + 1)
        seat_si = dict(SEAT_SI); seat_si["candidate"] = full.get("s_i")
        add = pool_metrics(score6, forward, eligible, seat_si)
        turnover = full.get("turnover")
        rows.append(dict(
            run=record["run"], objective=record.get("objective"),
            record_band=record["record_band"], band=band_of(turnover) if turnover is not None else "na",
            formula=formula,
            rec_net=float(record["net_excess"]), rec_turnover=float(record["turnover"]),
            net=full.get("net_excess"), turnover=turnover, periods=full.get("periods"),
            rank_ic=full.get("rank_ic"), ic_ir=full.get("ic_ir"), s_i=full.get("s_i"),
            rank_ic_ir=full.get("rank_ic_ir"), rank_ic_win=full.get("rank_ic_win"),
            s_i_rank=full.get("s_i_rank"), s_i_rank_y2026=y2026.get("s_i_rank"),
            gross=full.get("gross_excess"),
            net_y2026=y2026.get("net_excess"), periods_y2026=y2026.get("periods"),
            s_i_y2026=y2026.get("s_i"), net_last12=last12.get("net_excess"),
            s_i_last12=last12.get("s_i"),
            neu_net=neu_full.get("net_excess"), neu_turnover=neu_full.get("turnover"),
            neu_s_i=neu_full.get("s_i"),
            corr_size=corrs["size_only"],
            corr_max_seat=max(abs(v) for v in corrs.values()),
            corr_max_seat_name=max(corrs, key=lambda k: abs(corrs[k])),
            add6_na=add["pool_na"], add6_nc=add["pool_nc"], add6_comb=add["pool_comb"],
            delta_points=40000 * 1.1 * (add["pool_comb"] - base["pool_comb"])))
        print(f"  [{idx}] {rows[-1]['band']:>5} net={full['net_excess']:+.4f} "
              f"SiR={full.get('s_i_rank'):.5f} "
              f"turn={turnover:.3f} S_i={full.get('s_i'):.4f} "
              f"net26={y2026.get('net_excess'):+.4f} neu={neu_full.get('net_excess'):+.4f} "
              f"corr_size={corrs['size_only']:+.3f} dComb={rows[-1]['delta_points']:+.0f}",
              flush=True)

    out = pd.DataFrame(rows)
    out_name = ("screened_candidates.csv" if args.shard_count <= 1
                else f"screened_candidates.part{args.shard_index:02d}.csv")
    out.to_csv(out_dir / out_name, index=False)
    print(f"skipped={skipped}", flush=True)
    if len(out):
        out["rank_key"] = (out["net_y2026"].fillna(-9)
                           + 0.5 * out["s_i_rank"].fillna(0))
        pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 44)
        cols = ["band", "net", "turnover", "s_i_rank", "net_y2026", "net_last12", "neu_net",
                "corr_size", "corr_max_seat_name", "delta_points"]
        for name, _lo, _hi in BANDS:
            sub = out[out["band"] == name].nlargest(args.per_band, "rank_key")
            if not len(sub):
                continue
            print(f"\n===== {name} (n={len(out[out['band'] == name])}) =====", flush=True)
            print(sub[cols].round(4).to_string(index=False), flush=True)
            for _, r in sub.head(3).iterrows():
                print(f"    {str(r['formula'])[:120]}", flush=True)
    print(f"\nwrote {out_dir / out_name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
