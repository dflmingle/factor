"""待批 4 条候选（AGG / G13 / DOWNSIDE / WC）的池级 ΔComb 复核（2026-09-26，零平台算力）。

背景：交接单 HANDOFF_20260924 §4 列了 4 条待上平台验证的候选，旧口径 6 席池 ΔComb 为
+148.8 / +148.3 / +108.7 / −783.3 分/月，从未验证过。本脚本用今天重建的现役 5 席面板
（`ab-batch-20260925/seat_panels_rebuilt.pkl`）+ 与 A/B 批次完全相同的账本口径复核。

四条都是本地 handler（不是 GP 表达式），走 `exhaustive_representative_combination.build_factor`
与席位同一条代码路径；方向取自本机 qualitygate1 对齐报告。

A 项三种口径并列：
  local_pearson  = GP 内部 Pearson s_i（A/B 批次用的那套；对多数候选恒为 0，已知缺陷）
  rank_ic        = 项目已有的 s_i_rank（RankIC 的 ICIR × 胜率）
  neutral        = 把 A 项抵扣归零，只看 0.45·ΔNC
"""
from __future__ import annotations

import gc
import io
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402
from financial_factor_local import load_financial_cache  # noqa: E402
import ab_batch_20260925 as ab  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/pending4-eval-20260926"
SEATS = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
CATALOG = (
    ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/"
    "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
    "turnoverdiag1_qualitygate1/all_factor_local_compare.json"
)
CANDIDATES = [
    ("AGG", "t10_size_plus_impact_aggregate", "T10-ADD-AGG-IMPACT-20260911"),
    ("G13", "t10_size_plus_impact_g13", "T10-ADD-G13-20260911"),
    ("DOWNSIDE", "t10_size_plus_impact_downside", "T10-ADD-DOWNSIDE-IMPACT-20260911"),
    ("WC", "t10_size_plus_impact_wc", "T10-SIZE-PLUS-IMPACT-WC"),
]
POOL = ab.POOL
POINTS = ab.POINTS


def catalog_rows() -> dict[str, dict]:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))["results"]
    return {str(r.get("name")): r for r in rows}


def rank_ic_stats(panel: pd.DataFrame, forward: pd.DataFrame, eligible: pd.DataFrame) -> dict:
    values = []
    for date in panel.index:
        x = panel.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        flag = eligible.loc[date].to_numpy(dtype=bool)
        ok = np.isfinite(x) & np.isfinite(y) & flag
        if ok.sum() < 100:
            continue
        a = pd.Series(x[ok]).rank().to_numpy()
        b = pd.Series(y[ok]).rank().to_numpy()
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    series = np.asarray(values, dtype="float64")
    if series.size < 3:
        return dict(rank_ic=float("nan"), rank_ic_ir=float("nan"), rank_ic_win=float("nan"),
                    s_i_rank=float("nan"), periods=int(series.size))
    mean = float(series.mean())
    std = float(series.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    win = float((series > 0.02).mean()) if mean >= 0 else float((series < -0.02).mean())
    return dict(rank_ic=mean, rank_ic_ir=ir, rank_ic_win=win,
                s_i_rank=abs(mean) * abs(ir) * win, periods=int(series.size))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    catalogue = catalog_rows()
    specs = []
    for tag, handler, name in CANDIDATES:
        record = catalogue.get(name)
        if record is None:
            raise KeyError(f"catalog record missing: {name}")
        specs.append(dict(
            tag=tag, handler=handler, name=name,
            direction=int(float(record.get("platform_factor_direction") or 1)),
            platform_net=float(record["platform_net_excess_pct"]),
            platform_turnover=record.get("platform_turnover"),
            platform_rank_ic=record.get("platform_rank_ic"),
            alignment_quality=record.get("alignment_quality"),
            eligibility=record.get("local_mining_eligible"),
        ))
    for spec in specs:
        print(f"{spec['tag']:<9} {spec['handler']:<32} dir={spec['direction']} "
              f"plat_net={spec['platform_net']:.2f}% plat_turn={spec['platform_turnover']} "
              f"quality={spec['alignment_quality']}", flush=True)

    payload = pickle.load(SEATS.open("rb"))
    seat_scores = payload["scores"][POOL]
    seat_frame = payload["signal_frame"].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])

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
        cycle=ab.CYCLE, label_offset=1, groups=10, round_trip_cost=0.006)
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(context.forward_returns.detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids))
    eligible = pd.DataFrame(context.signal_eligible.detach().cpu().numpy(),
                            index=signal_dates, columns=list(data._stock_ids))
    print(f"aligned {signal_dates[0].date()}..{signal_dates[-1].date()} "
          f"({len(signal_dates)} dates, {forward.shape[1]} names)", flush=True)

    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {k: seat_frame.pivot(index="date", columns="instrument", values=k)
                   .reindex(index=signal_dates, columns=forward.columns) for k in POOL}
    seat_z = {k: ab.zscore(p) for k, p in seat_panels.items()}
    base_score = sum(seat_z.values()) / len(POOL)
    base, base_df = ab.pool_metrics(base_score, forward, eligible, ab.SEAT_SI)
    print("base:", {k: round(v, 4) for k, v in base.items() if k != "T_cap"}, flush=True)
    grid = frame.loc[frame["date"].isin(signal_dates), ["date", "instrument"]].reset_index(drop=True)
    financial = load_financial_cache(e.DEFAULT_FINANCIAL_ROOT)

    rows, scen, monthly = [], [], []
    for spec in specs:
        handler = spec["handler"]
        try:
            values = e.build_factor(frame, handler, financial=financial, signal_dates=signal_dates)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {spec['tag']}: {type(exc).__name__}: {exc}", flush=True)
            continue
        series = pd.to_numeric(values.loc[frame["date"].isin(signal_dates)].reset_index(drop=True),
                               errors="coerce")
        panel = grid.assign(_value=series.to_numpy()).pivot(
            index="date", columns="instrument", values="_value").reindex(
            index=signal_dates, columns=forward.columns)
        finite_share = float(np.isfinite(panel.to_numpy()).mean(axis=1).mean())
        del values
        gc.collect()
        oriented = panel if spec["direction"] == 1 else -panel
        standalone, _ = ab.pool_metrics(oriented, forward, eligible, {"x": 1.0})
        flipped, _ = ab.pool_metrics(-panel if spec["direction"] == 1 else panel,
                                     forward, eligible, {"x": 1.0})
        stats = rank_ic_stats(oriented, forward, eligible)
        corrs = {k: ab.daily_rank_corr(oriented, seat_panels[k]) for k in POOL}
        oriented_z = ab.zscore(oriented)
        rows.append(dict(
            tag=spec["tag"], handler=handler, name=spec["name"], direction=spec["direction"],
            platform_net_excess_pct=spec["platform_net"], platform_turnover=spec["platform_turnover"],
            alignment_quality=spec["alignment_quality"], local_mining_eligible=spec["eligibility"],
            finite_share=finite_share, net=standalone["pool_net"], turnover=standalone["pool_turnover"],
            sharpe=standalone["pool_sr"], maxdd=standalone["pool_dd"],
            net_flipped=flipped["pool_net"], turnover_flipped=flipped["pool_turnover"],
            **stats, corr_size=corrs["size_only"],
            corr_max=float(np.nanmax(np.abs(list(corrs.values())))),
            corr_max_seat=max(corrs, key=lambda k: abs(corrs[k])),
            **{f"corr_{k}": corrs[k] for k in POOL},
        ))
        print(f"  built {spec['tag']:<9} finite={finite_share:.3f} net={standalone['pool_net']:+.3f} "
              f"turn={standalone['pool_turnover']:.3f} rankIC={stats['rank_ic']:+.4f} "
              f"s_i_rank={stats['s_i_rank']:.5f} corrMax={max(abs(v) for v in corrs.values()):.3f}"
              f"({max(corrs, key=lambda k: abs(corrs[k]))})", flush=True)

        keep_rest = [k for k in POOL if k != ab.WEAKEST]
        scenarios = [("add-6th", POOL), ("replace-SIZE", keep_rest)]
        scenarios += [(f"swap-{k}", [x for x in POOL if x != k]) for k in POOL if k != ab.WEAKEST]
        for tag, keep in scenarios:
            score = (sum(seat_z[k] for k in keep) + oriented_z) / (len(keep) + 1)
            for a_tag, cand_si in (("local_pearson", 0.0), ("rank_ic", stats["s_i_rank"])):
                si = {k: ab.SEAT_SI[k] for k in keep}
                si["candidate"] = cand_si
                m, _ = ab.pool_metrics(score, forward, eligible, si)
                scen.append(dict(candidate=spec["tag"], scenario=tag, a_term=a_tag,
                                 d_comb=m["pool_comb"] - base["pool_comb"],
                                 d_points=POINTS * (m["pool_comb"] - base["pool_comb"]),
                                 d_na=m["pool_na"] - base["pool_na"],
                                 d_nc=m["pool_nc"] - base["pool_nc"],
                                 d_comb_nc_only=0.45 * (m["pool_nc"] - base["pool_nc"]),
                                 d_points_nc_only=POINTS * 0.45 * (m["pool_nc"] - base["pool_nc"]),
                                 d_net=m["pool_net"] - base["pool_net"],
                                 d_turn=m["pool_turnover"] - base["pool_turnover"],
                                 **m))
        score6 = (sum(seat_z.values()) + oriented_z) / (len(POOL) + 1)
        _, df6 = ab.pool_metrics(score6, forward, eligible,
                                 dict(ab.SEAT_SI, candidate=stats["s_i_rank"]))
        md = ab.monthly_dcomb(base_df, df6)
        blk = ab.monthly_dcomb(base_df, df6, block=6)
        monthly.append(dict(candidate=spec["tag"], n_months=len(md),
                            dcomb_month_mean=float(np.mean(md)) if md else np.nan,
                            dcomb_month_positive=float(np.mean([x > 0 for x in md])) if md else np.nan,
                            n_blocks=len(blk),
                            dcomb_block6_mean=float(np.mean(blk)) if blk else np.nan,
                            dcomb_block6_positive=float(np.mean([x > 0 for x in blk])) if blk else np.nan))

    pd.DataFrame(rows).to_csv(OUT / "candidate_stats.csv", index=False)
    pd.DataFrame(scen).to_csv(OUT / "pool_scenarios.csv", index=False)
    pd.DataFrame(monthly).to_csv(OUT / "monthly_dcomb.csv", index=False)
    pd.DataFrame([base]).to_csv(OUT / "base_pool.csv", index=False)
    (OUT / "run_provenance.json").write_text(json.dumps(dict(
        seat_source="ab-batch-20260925/seat_panels_rebuilt.pkl",
        handlers=[s["handler"] for s in specs],
        a_terms=["local_pearson", "rank_ic"],
        scenarios=[row["scenario"] for row in scen if row["a_term"] == "local_pearson"],
        rules="pending4-eval-20260926", platform_compute=0.0,
    ), ensure_ascii=False, indent=1), encoding="utf-8")
    print("written:", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())