"""Evaluate the full374b net-excess GP candidates (s901/s902/s903) as pool seats.

The three candidate files were produced offline by the net-excess objective over
the widened 374-field space but were never scored: not locally as seats, and not
on the platform.  This script scores them offline, on the same aligned window and
the same seat definition the pool pipeline uses, and answers three questions:

  1. standalone seat quality  -> RankIC / ICIR / win -> S_i, turnover, net excess
  2. novelty                  -> daily cross-sectional rank correlation vs the
                                 five live pool seats
  3. pool impact              -> rebuild the pool composite with the candidate as
                                 one equal-weight seat (replace-SIZE or add-6th),
                                 then re-measure NA / NC / Comb / net / turnover.

Offline only: no platform credits are spent.
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/full374b-net-seat-20260924"
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692,
           "book_to_market_lf_plus_impact": 0.01540}
WEAKEST = "size_only"
CYCLE = 10
POINTS_PER_COMB = 40000 * 1.10


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def seat_structure(panel: pd.DataFrame, forward: pd.DataFrame) -> dict:
    """Seat-level diagnostics on the pool's top-decile convention."""
    rics, ics, turns, held, bench = [], [], [], [], []
    previous: set[str] = set()
    for date in panel.index:
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
        return {"periods": len(ics)}
    rics, ics = np.array(rics), np.array(ics)
    mean_rank, mean_ic = float(rics.mean()), float(ics.mean())
    std_ic = float(ics.std(ddof=1))
    win = float((ics > 0.02).mean()) if mean_ic >= 0 else float((ics < -0.02).mean())
    ic_ir = mean_ic / std_ic if std_ic else 0.0
    turnover = float(np.mean(turns)) if turns else 0.0
    years = len(held) * CYCLE / 252
    gross = float(np.prod(1 + np.array(held)) ** (1 / years)
                  - np.prod(1 + np.array(bench)) ** (1 / years))
    return dict(periods=len(ics), rank_ic=mean_rank, ic_ir=ic_ir, win=win,
                s_i=abs(mean_rank) * abs(ic_ir) * win, direction=int(mean_ic >= 0),
                seat_turnover=turnover, seat_gross=gross,
                seat_net=gross - turnover * (252.0 / CYCLE) * 0.006)


def pair_correlation(left: pd.DataFrame, right: pd.DataFrame) -> float:
    """Mean daily cross-sectional Spearman correlation over shared instruments."""
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


def pool_metrics(score: pd.DataFrame, forward: pd.DataFrame, seat_si: dict) -> dict:
    held, gross, turnover, valid = [], [], [], []
    previous: set[str] = set()
    for date, row in score.iterrows():
        f = row.to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            held.append(np.nan); gross.append(np.nan); turnover.append(np.nan)
            valid.append(False); continue
        x, r = f[ok], y[ok]
        instruments = score.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean()))
        gross.append(float(r[order].mean() - r.mean()))
        valid.append(True)
    held, gross, turnover = np.array(held), np.array(gross), np.array(turnover)
    valid = np.array(valid)
    if valid.sum() < 3:
        return dict(pool_na=np.nan, pool_nc=np.nan, pool_comb=np.nan, pool_net=np.nan,
                    pool_gross=np.nan, pool_turnover=np.nan, pool_monthly_turnover=np.nan,
                    pool_sr=np.nan, pool_dd=np.nan, raw_c=np.nan)
    held_clean = np.nan_to_num(held[valid]); bench_clean = np.nan_to_num(held[valid] - gross[valid])
    years = int(valid.sum()) * CYCLE / 252.0
    gross_annual = float(np.prod(1 + held_clean) ** (1 / years) - np.prod(1 + bench_clean) ** (1 / years))
    turn_mean = float(np.nanmean(turnover[valid]))
    net = gross_annual - turn_mean * (252.0 / CYCLE) * 0.006
    after_cost = held[valid] - np.where(np.isfinite(turnover[valid]), turnover[valid] * 0.006, 0.0)
    sr = float(after_cost.mean() / after_cost.std(ddof=1) * np.sqrt(252.0 / CYCLE))
    curve = np.cumprod(1 + after_cost)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    na = min(float(np.mean(list(seat_si.values()))) / 0.08, 0.7)
    raw_c = max(net, 0.0) / max(2 * turn_mean, 0.3) * sr * (1 - 1.2 * dd)
    nc = min(max(raw_c / 0.6, 0.0), 1.0)
    return dict(pool_na=na, pool_nc=nc, pool_comb=0.20 * na + 0.45 * nc, pool_net=net,
                pool_gross=gross_annual, pool_turnover=turn_mean,
                pool_monthly_turnover=2 * turn_mean, pool_sr=sr, pool_dd=dd, raw_c=raw_c)


def load_candidates(paths: list[Path]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, rest = line.partition(" ~ ")
            formula = rest.rsplit(" ~ ", 1)[0].strip()
            out.append((f"{path.stem.split('_')[2]}:{name}", formula))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, nargs="+", default=[
        ROOT / "full374b_net_s901_20260923-candidates.txt",
        ROOT / "full374b_net_s902_20260923-candidates.txt",
        ROOT / "full374b_net_s903_20260923-candidates.txt"])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    candidates = load_candidates(args.candidates)
    print(f"candidates: {len(candidates)}", flush=True)

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
        cycle=CYCLE, label_offset=1, groups=10, round_trip_cost=0.006)
    namespace = gp.expression_namespace()
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    forward = pd.DataFrame(context.forward_returns.detach().cpu().numpy(),
                           index=signal_dates, columns=list(data._stock_ids))
    print(f"aligned window {signal_dates[0].date()} .. {signal_dates[-1].date()} "
          f"({len(signal_dates)} signal dates, {forward.shape[1]} instruments)", flush=True)

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(signal_dates)]
    seat_panels = {
        key: seat_frame.pivot(index="date", columns="instrument", values=key)
        .reindex(index=signal_dates, columns=forward.columns) for key in POOL}
    seat_z = {key: zscore(panel) for key, panel in seat_panels.items()}
    base = pool_metrics(sum(seat_z.values()) / len(POOL), forward, SEAT_SI)
    print("seed:", {k: round(v, 4) for k, v in base.items()}, flush=True)

    rows, failures = [], {}
    for name, formula in candidates:
        try:
            expression = gp.evaluate_formula(formula, namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expression.evaluate(data))
            panel = pd.DataFrame(values[context.signal_data_positions].detach().cpu().numpy(),
                                 index=signal_dates, columns=list(data._stock_ids)
                                 ).reindex(index=signal_dates, columns=forward.columns)
        except Exception as exc:  # noqa: BLE001
            failures[name] = f"{type(exc).__name__}: {exc}"
            continue
        finite_share = float(np.isfinite(panel.to_numpy()).mean(axis=1).mean())
        stats = seat_structure(panel, forward)
        if finite_share < 0.5:
            failures[name] = f"degenerate: finite share {finite_share:.3f}"
            print(f"  skip degenerate {name} finite_share={finite_share:.3f}", flush=True)
            continue
        if stats.get("periods", 0) < 100:
            failures[name] = f"insufficient periods ({stats.get('periods')})"
            continue
        oriented = panel if stats["direction"] == 1 else -panel
        oriented_z = zscore(oriented)
        correlations = {key: pair_correlation(oriented, seat_panels[key]) for key in POOL}
        record = dict(candidate=name, formula=formula, finite_share=finite_share, **stats)
        record.update({f"corr_{key}": value for key, value in correlations.items()})
        record["corr_max_abs"] = float(np.nanmax(np.abs(list(correlations.values()))))
        record["corr_max_abs_seat"] = max(correlations, key=lambda k: abs(correlations[k]))
        for tag, keep in (("replace-SIZE", [k for k in POOL if k != WEAKEST]), ("add-6th", POOL)):
            score = (sum(seat_z[k] for k in keep) + oriented_z) / (len(keep) + 1)
            seat_si = {k: SEAT_SI[k] for k in keep}
            seat_si["candidate"] = stats["s_i"]
            metrics = pool_metrics(score, forward, seat_si)
            rows.append(dict(**record, tag=tag,
                             delta_comb=metrics["pool_comb"] - base["pool_comb"],
                             delta_points=POINTS_PER_COMB * (metrics["pool_comb"] - base["pool_comb"]),
                             **metrics))
        print(f"  scored {name}: S_i={stats['s_i']:.4f} turn={stats['seat_turnover']:.3f} "
              f"net={stats['seat_net']:+.3f} corr_max={record['corr_max_abs']:.3f}"
              f"({record['corr_max_abs_seat']})", flush=True)

    result = pd.DataFrame(rows)
    if len(result):
        result.sort_values(["tag", "pool_comb"], ascending=[True, False]).to_csv(
            args.out / "seat_simulation.csv", index=False)
    (args.out / "failures.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in sorted(failures.items())) + "\n", encoding="utf-8")
    pd.set_option("display.width", 240)
    print("\n=== seed vs candidates (per scenario) ===", flush=True)
    if len(result):
        print(result[["tag", "candidate", "s_i", "seat_turnover", "seat_net", "corr_max_abs",
                      "corr_max_abs_seat", "pool_na", "pool_nc", "pool_comb", "delta_comb", "delta_points",
                      "pool_monthly_turnover", "pool_sr", "pool_dd"]].round(4).to_string(index=False), flush=True)
    else:
        print("no candidate scored", flush=True)
    print("\nfailures:", failures, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
