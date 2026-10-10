"""A组（K008/K021/K015 池级 ΔComb）+ B组（K020 消解版 / K024 补强轮）本地评估，零平台算力。

口径：与 relaxed_gp_screen_20260924 / full374b 完全一致（同一 5 席池、同一成本、同一分档）。
输出：research_reports/platform_alignment/ab-batch-20260925/{seat_stats.csv,pool_scenarios.csv,monthly_dcomb.csv}
"""
from __future__ import annotations
import argparse, json, pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alphaprobe_gp_tushare as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
REBUILT = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
OUT = ROOT / "research_reports/platform_alignment/new-cluster-pool-eval-20261010"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692, "book_to_market_lf_plus_impact": 0.01540}
CYCLE, COST, BUCKETS = 10, 0.006, 20
POINTS = 40000.0 * 1.10
P2, P3 = 0.7667, 0.1167
WEAKEST = "size_only"

FORMULAS = {
 "A_K008_cand0000": "Inv(Sub(a_share_market_val,TsStd(TsMax(is_operate_profit,10),30)))",
 "A_K021_cand0013": "Div(Div(Div(TsCorr(asi,vma3,30),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)",
 "A_K015_cand0003": "Div(Div(Div(Div(davol5,cal_30d_ret_vol_corr),cal_20d_amt_ma),amount),bs_total_assets)",
 "B_K020a_rankfix": "Div(Div(Div(ratio_bm_lyr,Add(TsRank(cal_30d_price_vol_corr,40),0.5)),cal_20d_amt_ma),bs_total_assets)",
 "B_K020b_xrankfix": "Div(Div(Div(ratio_bm_lyr,Add(Rank(cal_30d_price_vol_corr),0.5)),cal_20d_amt_ma),bs_total_assets)",
 "B_K024a_denoise": "Div(Div(Div(ratio_bm_lyr,TsRank(TsMax(ev_lf,40),20)),cal_20d_amt_ma),bs_total_assets)",
 "B_K024b_smooth": "Div(Div(Div(ratio_bm_lyr,TsMean(TsRank(TsMax(ev_lf,40),20),30)),cal_20d_amt_ma),bs_total_assets)",
 "B_K024c_keep2": "Div(Div(Div(Div(ratio_bm_lyr,TsRank(TsMax(ev_lf,40),20)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)",
 "B_K024d_compK021": "Add(Rank(Div(Div(Div(Div(ratio_bm_lyr,TsDelta(TsRank(TsMax(ev_lf,40),20),30)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)),Rank(Div(Div(Div(TsCorr(asi,vma3,30),cal_20d_amt_ma),qtyr_5_20),bs_total_assets)))",
 "B_K024e_compK008": "Add(Rank(Div(Div(Div(Div(ratio_bm_lyr,TsDelta(TsRank(TsMax(ev_lf,40),20),30)),cal_20d_amt_ma),bs_total_assets),bs_total_assets)),Rank(Inv(Sub(a_share_market_val,TsStd(TsMax(is_operate_profit,10),30)))))",
 "C_N34": "Div(book_to_market_ratio_lf,oper_main_profit_ttm)",
 "C_U01_LOW": "Inv(low)",
}


def load_seats() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """席位面板来源：优先交接单里的正式大缓存，缺失时回退到本机重建版。"""
    if SIGNALS.exists() and SEATS.exists():
        sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
        return sf, pickle.load(SEATS.open("rb"))["scores"][POOL], "canonical_pkl"
    payload = pickle.load(REBUILT.open("rb"))
    marker = "rebuilt:" + str(payload.get("provenance", {}).get("source_rule_version"))
    return payload["signal_frame"], payload["scores"][POOL], marker


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


def score_panel(context, panel, start=None, end=None) -> dict:
    stats = context.score(panel, start_date=start, end_date=end)
    ic = context.ic_series_stats(panel, start_date=start, end_date=end)
    out = dict(stats)
    out.update({"rank_ic": ic.get("rank_ic"), "ic_ir": ic.get("ic_ir"), "ic_win": ic.get("ic_win"),
                "s_i": ic.get("s_i"), "direction": ic.get("direction")})
    return out


def ledger(score: pd.DataFrame, forward: pd.DataFrame, eligible: pd.DataFrame):
    held, gross, turnover, valid, dates = [], [], [], [], []
    previous: set[str] = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y) & eligible.loc[date].to_numpy(dtype=bool)
        if ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan); valid.append(False); continue
        x, r = f[ok], y[ok]
        instruments = score.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); gross.append(float(r[order].mean() - r.mean()))
        valid.append(True)
    return pd.DataFrame({"date": list(score.index), "held": held, "gross": gross,
                         "turnover": turnover, "valid": valid})


def pool_metrics(score, forward, eligible, seat_si):
    df = ledger(score, forward, eligible)
    d = df[df["valid"]].copy()
    if len(d) < 3:
        return {}, df
    held = d["held"].to_numpy(); gross = d["gross"].to_numpy(); turn = d["turnover"].to_numpy()
    years = len(d) * CYCLE / 252.0
    gross_annual = float(np.prod(1 + held) ** (1 / years) - np.prod(1 + (held - gross)) ** (1 / years))
    turn_mean = float(np.nanmean(turn))
    net = gross_annual - turn_mean * (252.0 / CYCLE) * COST
    after = held - np.where(np.isfinite(turn), turn * COST, 0.0)
    sr = float(after.mean() / after.std(ddof=1) * np.sqrt(252.0 / CYCLE)) if after.std(ddof=1) else 0.0
    curve = np.cumprod(1 + after)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    raw_c = max(net, 0.0) / max(2 * turn_mean, 0.30) * sr * (1 - 1.2 * dd)
    nc = min(max(raw_c / 0.6, 0.0), 1.0)
    tstar = max(net, 0.0) * sr * (1 - 1.2 * dd) / 0.6
    return dict(pool_na=na, pool_nc=nc, pool_comb=0.20 * na + 0.45 * nc, pool_net=net,
                pool_gross=gross_annual, pool_turnover=turn_mean, pool_sr=sr, pool_dd=dd,
                raw_c=raw_c, T_monthly_k2=2 * turn_mean, T_monthly_k3=3 * turn_mean,
                T_star=tstar, T_cap=1.15 * tstar), df


def _block_nc(group: pd.DataFrame) -> float:
    """一个分块内独立算 Rex/SR/DD/换手，再折算成 NC。"""
    held = group["held"].to_numpy()
    turn = group["turnover"].to_numpy()
    rex = float(np.prod(1 + held) ** (252.0 / CYCLE / len(group)) - 1)
    after = held - np.where(np.isfinite(turn), turn * COST, 0.0)
    sr = float(after.mean() / after.std(ddof=1) * np.sqrt(252.0 / CYCLE)) if after.std(ddof=1) else 0.0
    curve = np.cumprod(1 + after)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    threshold = float(np.nanmean(turn)) * 2
    return min(max(max(rex, 0.0) / max(threshold, 0.30) * sr * (1 - 1.2 * dd) / 0.6, 0.0), 1.0)


def monthly_dcomb(base_df, cand_df, block=None, min_periods=2):
    """分块日频账本口径的 ΔComb：每块独立算 Rex/SR/DD/换手 -> ΔNC -> ΔComb = 0.45*ΔNC。

    block=None 用自然月（10 日调仓下每月约 2 期）；block=N 用连续 N 期分块（更稳）。
    """
    def grouped(frame):
        data = frame[frame["valid"]].copy()
        if block:
            data["_key"] = (np.arange(len(data)) // int(block)).astype(str)
        else:
            data["_key"] = data["date"].dt.to_period("M").astype(str)
        return {str(k): g for k, g in data.groupby("_key")}

    base_groups, cand_groups = grouped(base_df), grouped(cand_df)
    out = []
    for key in sorted(set(base_groups) & set(cand_groups)):
        left, right = base_groups[key], cand_groups[key]
        if len(left) < min_periods or len(right) < min_periods:
            continue
        out.append(0.45 * (_block_nc(right) - _block_nc(left)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="C_N34,C_U01_LOW")
    args = ap.parse_args()
    wanted = {x for x in args.only.split(",") if x}
    OUT.mkdir(parents=True, exist_ok=True)
    cache_root = gp.DEFAULT_CACHE_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root, data_start, end).sort_values(
        ["instrument", "date"], ignore_index=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    device = torch.device("cpu")
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
    eligible = pd.DataFrame(context.signal_eligible.detach().cpu().numpy(),
                            index=signal_dates, columns=list(data._stock_ids))
    bp = gp.build_size_bucket_panel(frame, context, data, BUCKETS)
    bucket = torch.tensor(bp, dtype=torch.long, device=device)
    offsets = (torch.arange(bp.shape[0], device=device, dtype=torch.long).unsqueeze(1) * BUCKETS).expand_as(bucket)
    print(f"aligned {signal_dates[0].date()}..{signal_dates[-1].date()} ({len(signal_dates)} dates, {forward.shape[1]} names)", flush=True)

    sf, seat_scores, seat_source = load_seats()
    print(f"seat source: {seat_source}", flush=True)
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in POOL}
    seat_z = {k: zscore(p) for k, p in seat_panels.items()}
    base_score = sum(seat_z.values()) / len(POOL)
    base, base_df = pool_metrics(base_score, forward, eligible, SEAT_SI)
    print("base:", {k: round(v, 4) for k, v in base.items() if k != "T_cap"}, flush=True)

    rows, scen, monthly = [], [], []
    for name, formula in FORMULAS.items():
        if wanted and name not in wanted:
            continue
        try:
            expr = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expr.evaluate(data))
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}", flush=True)
            continue
        raw = pd.DataFrame(values[context.signal_data_positions].detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids)).reindex(
                           index=signal_dates, columns=forward.columns)
        finite_share = float(np.isfinite(raw.to_numpy()).mean(axis=1).mean())
        if finite_share < 0.5:
            print(f"  sparse {name} {finite_share:.3f}", flush=True)
            continue
        with torch.no_grad():
            full = score_panel(context, values)
        direction = int(full.get("direction") or 1)
        oriented_values = values if direction == 1 else -values
        oriented = raw if direction == 1 else -raw
        with torch.no_grad():
            neu_values = gp.size_neutralise_panel(values, bucket, offsets, BUCKETS)
            neu_full = score_panel(context, neu_values)
            if int(neu_full.get("direction") or 1) == -1:
                neu_full = score_panel(context, -neu_values)
        corrs = {k: daily_rank_corr(oriented, seat_panels[k]) for k in POOL}
        oriented_z = zscore(oriented)
        stat = dict(candidate=name, formula=formula, finite_share=finite_share,
                    net=full.get("net_excess"), turnover=full.get("turnover"),
                    rank_ic=full.get("rank_ic"), ic_ir=full.get("ic_ir"), ic_win=full.get("ic_win"),
                    s_i=full.get("s_i"), direction=direction, neu_net=neu_full.get("net_excess"),
                    neu_turnover=neu_full.get("turnover"), corr_size=corrs.get("size_only"),
                    corr_max=float(np.nanmax(np.abs(list(corrs.values())))),
                    corr_max_seat=max(corrs, key=lambda k: abs(corrs[k])))
        stat.update({f"corr_{k}": corrs[k] for k in POOL})
        rows.append(stat)
        for tag, keep in (("replace-SIZE", [k for k in POOL if k != WEAKEST]), ("add-6th", POOL)):
            score = (sum(seat_z[k] for k in keep) + oriented_z) / (len(keep) + 1)
            si = {k: SEAT_SI[k] for k in keep}; si["candidate"] = full.get("s_i")
            m, df = pool_metrics(score, forward, eligible, si)
            if not m:
                continue
            scen.append(dict(candidate=name, tag=tag, d_comb=m["pool_comb"] - base["pool_comb"],
                             d_points=POINTS * (m["pool_comb"] - base["pool_comb"]),
                             d_na=m["pool_na"] - base["pool_na"],
                             d_nc=m["pool_nc"] - base["pool_nc"],
                             d_comb_nc_only=0.45 * (m["pool_nc"] - base["pool_nc"]),
                             d_points_nc_only=POINTS * 0.45 * (m["pool_nc"] - base["pool_nc"]),
                             d_net=m["pool_net"] - base["pool_net"],
                             d_turn=m["pool_turnover"] - base["pool_turnover"],
                             turn_excess=m["T_monthly_k2"] - m["T_cap"], **m))
        # 月度 ΔComb（add-6th 口径）
        score6 = (sum(seat_z.values()) + oriented_z) / (len(POOL) + 1)
        _m6, df6 = pool_metrics(score6, forward, eligible, dict(SEAT_SI, candidate=full.get("s_i")))
        md = monthly_dcomb(base_df, df6)
        blk = monthly_dcomb(base_df, df6, block=6)
        monthly.append(dict(candidate=name, n_months=len(md),
                            dcomb_month_mean=float(np.mean(md)) if md else np.nan,
                            dcomb_month_positive=float(np.mean([x > 0 for x in md])) if md else np.nan,
                            dcomb_points_month_mean=POINTS * float(np.mean(md)) if md else np.nan,
                            n_blocks=len(blk),
                            dcomb_block6_mean=float(np.mean(blk)) if blk else np.nan,
                            dcomb_block6_positive=float(np.mean([x > 0 for x in blk])) if blk else np.nan))
        print(f"  scored {name}: net={stat['net']:+.3f} turn={stat['turnover']:.3f} "
              f"rankIC={stat['rank_ic']:+.4f} neu={stat['neu_net']:+.3f} "
              f"corrMax={stat['corr_max']:.3f}({stat['corr_max_seat']})", flush=True)

    pd.DataFrame(rows).to_csv(OUT / "seat_stats.csv", index=False)
    pd.DataFrame(scen).to_csv(OUT / "pool_scenarios.csv", index=False)
    pd.DataFrame(monthly).to_csv(OUT / "monthly_dcomb.csv", index=False)
    pd.DataFrame([base]).to_csv(OUT / "base_pool.csv", index=False)
    (OUT / "run_provenance.json").write_text(
        json.dumps(dict(seat_source=seat_source, seat_panels=list(POOL), cycle=CYCLE,
                        cost=COST, buckets=BUCKETS, points=POINTS, weakest=WEAKEST,
                        rules="ab-batch-20260925"), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("written:", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())