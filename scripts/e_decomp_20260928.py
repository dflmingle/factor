"""E 分解 + 候选全账重排（2026-09-28，零平台算力）。

两种模式：
  seats      现役五席：seed / drop_X（leave-one-out）/ only_X（单席）
             → 逐月 E=rex*sr*(1-1.2dd)、T、rawC、NC；每席边际；收益层 size 回归
  candidates 候选作第 6 席：six vs seed → 逐月 ΔE/ΔT/ΔNC/Δ积分（C 段单列）

复用口径（与 turnover_relaxed_pool_sim_20260926.py / competition_rules.md 一致）：
  - 5+1 席各自横截面 Winsorize(1%,99%)+Z-score，等权相加，10 组取多头十分位
  - 日频等权买入持有净值（组合已扣成本），全 A 等权基准
  - 月度口径：rex_ann / sr_ann / maxDD_month / turnover_month → rawC → NC
"""
from __future__ import annotations

import argparse
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
from independent_information_combination import DATA_START, END  # noqa: E402
from stfilter_local_recheck import ensure_calendar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "research_reports/platform_alignment/e-decomp-20260928"
DEFAULT_REBUILD = DEFAULT_OUT / "seat_panels_rebuilt.pkl"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
MEAN_S_LOCAL = 0.019121
MEAN_S_PLAT = 0.025893
UPLIFT = MEAN_S_PLAT / MEAN_S_LOCAL
CYCLE, COST, GROUPS = 10, 0.006, 10
W_A, W_C = 0.20, 0.45
A_ANCHOR, C_ANCHOR = 0.08, 0.60
A_UNIT = W_A / (6 * A_ANCHOR) * 44000.0  # 分/月 per unit of raw_a (6-seat mean delta)


def rank_ic_stats(context, panel: torch.Tensor, start=None) -> dict:
    indices = context._selected_indices(start, None)
    if not indices:
        return {}
    rows = panel[[context.signal_data_positions[i] for i in indices]]
    returns = context.forward_returns[indices]
    eligible = context.signal_eligible[indices]
    valid = torch.isfinite(rows) & eligible & torch.isfinite(returns)
    counts = valid.sum(dim=1)
    series = gp.batch_spearmanr_linear(rows, returns)
    keep = (counts >= GROUPS * 10) & torch.isfinite(series)
    if not bool(keep.any().item()):
        return {}
    s = series[keep].detach().float()
    mean = float(s.mean().item())
    std = float(s.std(unbiased=True).item()) if s.numel() > 1 else 0.0
    ir = mean / std if std > 0 else 0.0
    win = (float((s > 0.02).float().mean().item()) if mean >= 0
           else float((s < -0.02).float().mean().item()))
    return {"rank_ic": mean, "rank_ic_ir": ir, "rank_ic_win": win,
            "s_i_rank": abs(mean) * abs(ir) * win}


def selection(score_block: np.ndarray, forward_block: np.ndarray, weights: np.ndarray):
    """One period, one scenario: top decile by weighted mean score."""
    score_sum = np.zeros(len(forward_block), dtype=np.float64)
    valid = np.isfinite(forward_block)
    for column in range(score_block.shape[1]):
        if weights[column] == 0:
            continue
        column_values = score_block[:, column]
        valid &= np.isfinite(column_values)
        score_sum += np.where(np.isfinite(column_values), column_values, 0.0)
    score_sum = score_sum / weights.sum() + np.arange(len(forward_block)) * 1e-12
    if valid.sum() < GROUPS * 10:
        return None
    index = np.flatnonzero(valid)
    work = score_sum[index]
    cutoff = (len(index) * (GROUPS - 1)) // GROUPS
    partition = np.argpartition(work, cutoff)[cutoff:]
    held_rows = index[partition]
    return dict(held_rows=held_rows,
                held_return=float(forward_block[held_rows].mean()),
                benchmark=float(forward_block[index].mean()),
                instruments=None)


class Market:
    """One-time full-A context shared by every scenario."""

    def __init__(self, payload: dict, device: torch.device):
        self.device = device
        seats = payload["scores"][POOL].reset_index(drop=True)
        self.signal_frame = payload["signal_frame"]
        self.returns_table = payload["returns"]
        self.dates = [pd.Timestamp(d) for d in payload["dates"]]
        print(f"seats {seats.shape}; signal rows {len(self.signal_frame)}; "
              f"dates {len(self.dates)}", flush=True)
        self.seats = seats

        calendar = [pd.Timestamp(x).normalize()
                    for x in ensure_calendar(DATA_START, END, token=None)]
        data_start = pd.Timestamp(DATA_START)
        start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
        print("loading full-A frame", flush=True)
        frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, data_start, end)
        frame = e.select_market_cap(frame, e.ALIGNMENT_MARKET_CAP_FIELD)
        frame = frame.sort_values(["instrument", "date"], ignore_index=True)
        stock_ids = sorted(frame["instrument"].astype(str).unique())
        cal = [d for d in calendar if data_start <= d <= end]
        print(f"frame rows {len(frame)} instruments {len(stock_ids)} calendar {len(cal)}",
              flush=True)
        close = e.panel_close(frame, cal)
        close = close.reindex(index=cal).ffill()
        print(f"close panel {close.shape}", flush=True)
        print("building TushareStockData", flush=True)
        data = gp.TushareStockData.from_aligned_frame(
            frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
            end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
            device=device, financial_root=gp.DEFAULT_FINANCIAL_ROOT)
        context = gp.AlignedNetExcessContext(
            frame=frame, calendar=cal, data=data, start_date=start, end_date=end,
            cycle=CYCLE, label_offset=1, groups=GROUPS, round_trip_cost=COST)
        ctx_dates = [pd.Timestamp(d) for d in context.signal_dates]
        print(f"context signal dates {len(ctx_dates)} {ctx_dates[0].date()}.."
              f"{ctx_dates[-1].date()}", flush=True)
        assert ctx_dates == self.dates, "context dates differ from rebuilt seat panels"
        del frame
        gc.collect()
        self.cal = cal
        self.close = close
        self.data = data
        self.context = context
        self.close_values = close.to_numpy(dtype="float64")
        self.column_position = {ins: pos for pos, ins in enumerate(close.columns)}
        self.calendar_position = {d: pos for pos, d in enumerate(cal)}
        self.namespace = gp.expression_namespace()
        self.signal_index = pd.MultiIndex.from_frame(self.signal_frame[["date", "instrument"]])

    def make_blocks(self, score_frame: pd.DataFrame, keys: list[str]):
        blocks = e._build_blocks(self.signal_frame, score_frame, self.returns_table,
                                 self.dates, keys)
        ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))
        return blocks, offsets, fs, fr

    def scenario_ledger(self, blocks, offsets, fs, fr, weights) -> pd.DataFrame:
        weights = np.asarray(weights, dtype=np.int64)
        curated = []
        previous = set()
        for period, block in enumerate(blocks):
            begin, finish = int(offsets[period]), int(offsets[period + 1])
            choice = selection(fs[begin:finish], fr[begin:finish], weights)
            if choice is None:
                curated.append(dict(period=period, date=self.dates[period], valid=False))
                continue
            current = set(np.asarray(block[1])[choice["held_rows"]].tolist())
            turnover = 0.5 if not previous else 1.0 - len(current & previous) / len(current)
            previous = current
            curated.append(dict(period=period, date=self.dates[period], valid=True,
                                held=choice["held_return"], benchmark=choice["benchmark"],
                                turnover=turnover, instruments=choice["held_rows"],
                                instrument_names=np.asarray(block[1])[choice["held_rows"]]))
        return pd.DataFrame(curated)

    def build_daily(self, ledger: pd.DataFrame) -> pd.DataFrame:
        days, portfolio, benchmark = [], [], []
        for row in ledger.to_dict("records"):
            if not row["valid"]:
                continue
            date = row["date"]
            base = self.calendar_position[date] + 1
            if base + CYCLE >= len(self.cal):
                continue
            block = self.close_values[list(range(base, base + CYCLE + 1))]
            anchor = block[0]
            held = np.asarray([self.column_position[x] for x in row["instrument_names"]
                               if x in self.column_position], dtype=np.int64)
            held = held[np.isfinite(anchor[held]) & (anchor[held] > 0)]
            if held.size < 10:
                continue
            universe = np.flatnonzero(np.isfinite(anchor) & (anchor > 0))
            portfolio_value = np.nanmean(block[:, held] / anchor[held], axis=1)
            benchmark_value = np.nanmean(block[:, universe] / anchor[universe], axis=1)
            portfolio_return = portfolio_value[1:] / portfolio_value[:-1] - 1.0
            benchmark_return = benchmark_value[1:] / benchmark_value[:-1] - 1.0
            if np.isfinite(row["turnover"]):
                portfolio_return[0] -= row["turnover"] * COST
            days.extend(self.cal[base + 1: base + CYCLE + 1])
            portfolio.extend(portfolio_return.tolist())
            benchmark.extend(benchmark_return.tolist())
        return pd.DataFrame({"portfolio": portfolio, "benchmark": benchmark},
                            index=pd.DatetimeIndex(days))

    def monthly_table(self, curve: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for (year, month), block in curve.groupby([curve.index.year, curve.index.month]):
            p = block["portfolio"].to_numpy(dtype="float64")
            b = block["benchmark"].to_numpy(dtype="float64")
            ok = np.isfinite(p) & np.isfinite(b)
            p, b = p[ok], b[ok]
            n = len(p)
            if n < 2:
                continue
            r_p = float(np.prod(1 + p) - 1.0)
            r_b = float(np.prod(1 + b) - 1.0)
            rex_ann = (1 + r_p) ** (252.0 / n) - 1.0 - ((1 + r_b) ** (252.0 / n) - 1.0)
            std = float(p.std(ddof=1))
            sr_ann = float(p.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
            equity = np.cumprod(1 + p)
            dd = float(-(equity / np.maximum.accumulate(equity) - 1).min())
            mask = (ledger["date"].dt.year == year) & (ledger["date"].dt.month == month) \
                & ledger["valid"]
            turns = ledger.turnover[mask].to_numpy(dtype="float64")
            turns = turns[np.isfinite(turns)]
            e_term = rex_ann * sr_ann * (1 - 1.2 * dd)
            # platform-literal: only Rex is clamped at 0 (board-verified 285 pools, 2026-09-28)
            raw_c = (max(rex_ann, 0.0) * sr_ann * (1 - 1.2 * dd)) / max(float(turns.sum()), 0.30)
            rows.append(dict(year=year, month=month, days=n, r_p=r_p, r_b=r_b,
                             rex_ann=rex_ann, sr_ann=sr_ann, max_dd=dd,
                             turnover_month=float(turns.sum()), e_term=e_term,
                             raw_c=raw_c, nc=min(max(raw_c, 0.0) / C_ANCHOR, 1.0)))
        return pd.DataFrame(rows)


def seats_mode(market: Market, out: Path, save_daily: bool) -> None:
    keys = POOL
    score_frame = market.seats.loc[:, keys]
    blocks, offsets, fs, fr = market.make_blocks(score_frame, keys)
    n = len(keys)
    scenarios = [("seed", np.ones(n, dtype=np.int64))]
    for i, key in enumerate(keys):
        drop = np.ones(n, dtype=np.int64)
        drop[i] = 0
        scenarios.append((f"drop_{key}", drop))
        only = np.zeros(n, dtype=np.int64)
        only[i] = 1
        scenarios.append((f"only_{key}", only))

    monthly_all, daily_slim, daily_bench, summary_rows = [], {}, {}, []
    ledgers = {}
    for label, weights in scenarios:
        ledger = market.scenario_ledger(blocks, offsets, fs, fr, weights)
        ledgers[label] = ledger
        curve = market.build_daily(ledger)
        table = market.monthly_table(curve, ledger)
        table["scenario"] = label
        monthly_all.append(table)
        daily_slim[label] = curve["portfolio"]
        daily_bench[label] = curve["benchmark"]
        per_rebalance = float(ledger.turnover[ledger.valid].mean()) if ledger.valid.any() else np.nan
        row = dict(scenario=label,
                   five_turn=per_rebalance,
                   e_mean=float(table.e_term.mean()),
                   e_median=float(table.e_term.median()),
                   e_p10=float(table.e_term.quantile(0.10)),
                   e_p90=float(table.e_term.quantile(0.90)),
                   t_mean=float(table.turnover_month.mean()),
                   t_2rebal=float(2 * per_rebalance if np.isfinite(per_rebalance) else np.nan),
                   t_3rebal=float(3 * per_rebalance if np.isfinite(per_rebalance) else np.nan),
                   rawc_mean=float(table.raw_c.mean()),
                   nc_mean=float(table.nc.mean()),
                   nc_min=float(table.nc.min()),
                   months=len(table))
        summary_rows.append(row)
        print(f"[{label}] E={row['e_mean']:.4f} T={row['t_mean']:.3f} "
              f"NC={row['nc_mean']:.3f}", flush=True)

    monthly = pd.concat(monthly_all, ignore_index=True)
    monthly.to_csv(out / "seats_monthly.csv", index=False, encoding="utf-8-sig")

    seed_summary = {r["scenario"]: r for r in summary_rows}
    margin = []
    for i, key in enumerate(keys):
        drop = seed_summary[f"drop_{key}"]
        only = seed_summary[f"only_{key}"]
        margin.append(dict(
            seat=key,
            drop_e_mean=drop["e_mean"], seed_minus_drop_e=seed_summary["seed"]["e_mean"] - drop["e_mean"],
            drop_nc_mean=drop["nc_mean"], seed_minus_drop_nc=seed_summary["seed"]["nc_mean"] - drop["nc_mean"],
            only_e_mean=only["e_mean"], only_nc_mean=only["nc_mean"],
            only_t_mean=only["t_mean"],
        ))
    marg = pd.DataFrame(margin)
    marg.to_csv(out / "seats_marginals.csv", index=False, encoding="utf-8-sig")

    daily_frame = pd.DataFrame(daily_slim)
    bench_frame = pd.DataFrame(daily_bench)
    if save_daily:
        daily_frame.to_csv(out / "seats_daily_portfolio.csv", encoding="utf-8-sig")
        bench_frame[["seed"]].rename(columns={"seed": "benchmark"}).to_csv(
            out / "seats_daily_benchmark.csv", encoding="utf-8-sig")

    bench = bench_frame["seed"]
    excess = {label: daily_frame[label] - bench for label in daily_frame.columns}
    size_proxy = excess.get("only_size_only")
    reg_rows = []
    for label in daily_frame.columns:
        y = excess[label].to_numpy(dtype="float64")
        x = size_proxy.to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        xv, yv = x[ok], y[ok]
        beta = float(np.cov(xv, yv)[0, 1] / np.var(xv, ddof=1)) if np.var(xv, ddof=1) > 0 else np.nan
        corr = float(np.corrcoef(xv, yv)[0, 1])
        share = beta ** 2 * float(np.var(xv, ddof=1)) / float(np.var(yv, ddof=1))
        reg_rows.append(dict(scenario=label, beta_size=beta, r2_size=corr ** 2,
                             share_size=share))
    reg = pd.DataFrame(reg_rows)
    reg.to_csv(out / "seats_size_regression.csv", index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(summary_rows)
    summary = summary.merge(reg, on="scenario", how="left")
    summary.to_csv(out / "seats_summary.csv", index=False, encoding="utf-8-sig")

    with pd.option_context("display.width", 220):
        print("\n=== scenarios ===")
        print(summary.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
        print("\n=== marginals ===")
        print(marg.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))


def candidates_mode(market: Market, out: Path, specs: dict, save_daily: bool) -> None:
    keys = POOL + ["cand"]
    seed_frame = market.seats.loc[:, POOL]
    blocks_seed, offsets_seed, fs_seed, fr_seed = market.make_blocks(seed_frame, POOL)
    seed_ledger = market.scenario_ledger(blocks_seed, offsets_seed, fs_seed, fr_seed,
                                         np.ones(len(POOL), dtype=np.int64))
    seed_curve = market.build_daily(seed_ledger)
    seed_table = market.monthly_table(seed_curve, seed_ledger)
    seed_table.to_csv(out / "seed_monthly.csv", index=False, encoding="utf-8-sig")
    print(f"[seed] E={seed_table.e_term.mean():.4f} NC={seed_table.nc.mean():.3f}", flush=True)

    summary_rows = []
    for name, formula in specs.items():
        try:
            expression = gp.evaluate_formula(formula, market.namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(market.data))
            del expression
            gc.collect()
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] EVAL FAIL {type(exc).__name__}: {exc}"[:200], flush=True)
            continue
        spots = np.asarray(market.context.signal_data_positions, dtype=np.int64)
        panel = pd.DataFrame(values[spots].detach().cpu().numpy(),
                             index=market.dates, columns=[str(x) for x in market.data._stock_ids])
        finite_share = float(np.isfinite(panel.to_numpy()).mean())
        stats = None
        chosen_direction = 1
        for direction in (1, -1):
            oriented = values if direction == 1 else -values
            with torch.no_grad():
                stats = rank_ic_stats(market.context, oriented)
            chosen_direction = direction
            if stats and stats["rank_ic"] >= 0:
                break
        if not stats:
            print(f"[{name}] no rank-IC stats, skip", flush=True)
            continue
        oriented_panel = panel if chosen_direction == 1 else -panel
        flat = oriented_panel.stack(dropna=False).reindex(market.signal_index)
        cand_score = e._competition_cross_sectional_scores(
            market.signal_frame, {"cand": flat},
            [{"key": "cand", "handler": "cand", "direction": 1}])
        score_frame = pd.concat([market.seats, cand_score], axis=1).loc[:, keys]
        blocks, offsets, fs, fr = market.make_blocks(score_frame, keys)
        six_weights = np.ones(len(keys), dtype=np.int64)
        six_ledger = market.scenario_ledger(blocks, offsets, fs, fr, six_weights)
        six_curve = market.build_daily(six_ledger)
        six_table = market.monthly_table(six_curve, six_ledger)

        merged = seed_table.merge(six_table, on=["year", "month"], suffixes=("_seed", "_six"))
        merged["d_e"] = merged.e_term_six - merged.e_term_seed
        merged["d_t"] = merged.turnover_month_six - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_six - merged.nc_seed
        merged["d_c_points"] = 44000.0 * W_C * merged.d_nc
        merged.to_csv(out / f"cand_monthly_{name}.csv", index=False, encoding="utf-8-sig")
        if save_daily:
            pd.DataFrame({"seed": seed_curve["portfolio"], "six": six_curve["portfolio"]}).to_csv(
                out / f"cand_daily_{name}.csv", encoding="utf-8-sig")

        s_local = stats["s_i_rank"]
        d_a_local = A_UNIT * (s_local - MEAN_S_LOCAL)
        d_a_uplift = A_UNIT * UPLIFT * (s_local - MEAN_S_LOCAL)
        d_c = float(merged.d_c_points.mean())
        row = dict(name=name, formula=formula, finite_share=finite_share,
                   rank_ic=stats["rank_ic"], ic_ir=stats["rank_ic_ir"], win=stats["rank_ic_win"],
                   s_i_local=s_local,
                   turn_intrinsic=float(six_ledger.turnover[six_ledger.valid].mean()),
                   turn_pool_seed=float(seed_ledger.turnover[seed_ledger.valid].mean()),
                   d_e_mean=float(merged.d_e.mean()), d_e_median=float(merged.d_e.median()),
                   d_t_mean=float(merged.d_t.mean()), d_nc_mean=float(merged.d_nc.mean()),
                   d_c_points=d_c, d_a_points_local=d_a_local, d_a_points_uplift=d_a_uplift,
                   d_comb_local=d_a_local + d_c, d_comb_uplift=d_a_uplift + d_c,
                   pos_months=int((merged.d_c_points > 0).sum()), months=len(merged),
                   e_seed_mean=float(seed_table.e_term.mean()),
                   e_six_mean=float(six_table.e_term.mean()))
        summary_rows.append(row)
        print(f"[{name}] s_i={s_local:.4f} dE={row['d_e_mean']:+.4f} "
              f"dT={row['d_t_mean']:+.3f} dNC={row['d_nc_mean']:+.4f} "
              f"dC={d_c:+,.0f} dComb_up={row['d_comb_uplift']:+,.0f}", flush=True)

    if summary_rows:
        summary = pd.DataFrame(summary_rows)
        path = out / "cand_summary.csv"
        if path.exists():
            old = pd.read_csv(path)
            summary = pd.concat([old[~old.name.isin(summary.name)], summary], ignore_index=True)
        summary.sort_values("d_comb_uplift", ascending=False).to_csv(
            path, index=False, encoding="utf-8-sig")
        print(f"\nwritten {path} ({len(summary)} candidates)", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["seats", "candidates"])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--rebuild", type=Path, default=DEFAULT_REBUILD)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--candidates", type=Path, default=None,
                    help="JSON {name: formula} for candidates mode")
    ap.add_argument("--names", default="", help="comma-separated subset")
    ap.add_argument("--save-daily", action="store_true")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    payload = pickle.load(args.rebuild.open("rb"))
    device = torch.device(args.device)
    market = Market(payload, device)

    if args.mode == "seats":
        seats_mode(market, args.out, args.save_daily)
    else:
        if args.candidates is None:
            raise SystemExit("--candidates JSON required for candidates mode")
        specs = json.loads(args.candidates.read_text(encoding="utf-8"))
        if args.names:
            wanted = [x for x in args.names.split(",") if x]
            specs = {k: v for k, v in specs.items() if k in wanted}
        candidates_mode(market, args.out, specs, args.save_daily)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
