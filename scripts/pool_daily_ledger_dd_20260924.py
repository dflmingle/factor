"""池组合的日频账本 → 月度日频 MaxDD（校准 C 分项的 DD 基准，零平台算力）。

动机：平台 NC 用的是**当月日频** MaxDD（283 池中位 4.15%），而本地 pool_run 的 27.4%
是 **10 日抽样**的全期 DD；两者不可比，导致 ΔNC 的符号在 K1/K2/K3 三套校准间翻转。
本脚本用同一套 5 席面板 + 同一网格重建**日频**组合净值，直接测出：
  * 全期日频 MaxDD（应与平台回测 31.64% 同量级，同时明显高于抽样值 27.4%）
  * 月度日频 MaxDD 的分布（与榜单 max_dd 同口径）
输出：research_reports/platform_alignment/daily-dd-20260924/daily_dd.json
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
import pool_seat_rescreen_20260924 as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/daily-dd-20260924"
START, END = pd.Timestamp("2021-08-01"), pd.Timestamp("2026-09-07")
COST = 0.006  # 沿用本地管线：每次调仓扣 换手×0.6%（= 2×0.30% 单边）
def _candidate_keys() -> list[str]:
    import pandas as pd
    path = (Path(__file__).resolve().parents[1] /
            "research_reports/platform_alignment/seat-rescreen-20260924/seat_rescreen.csv")
    d = pd.read_csv(path)
    return [k for k in d.loc[~d.in_pool, "key"].tolist()]


KEYS = _candidate_keys()


def monthly_maxdd(daily: pd.Series) -> pd.Series:
    out = {}
    for (year, month), chunk in daily.groupby([daily.index.year, daily.index.month]):
        curve = (1 + chunk).cumprod()
        dd = -(curve / curve.cummax() - 1).min()
        out[f"{year}-{month:02d}"] = float(dd)
    return pd.Series(out)


def maxdd(x: np.ndarray) -> float:
    curve = np.cumprod(1 + x)
    return float(-(curve / np.maximum.accumulate(curve) - 1).min())


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    sf, _raw, returns, _dates = pickle.loads(R.SIGNALS.read_bytes())
    built = pickle.loads(R.SEATS.read_bytes())
    scores = built["scores"]
    frame = sf[["date", "instrument"]].reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    signal_dates = sorted(frame["date"].unique())
    forward = (returns.pivot_table(index="date", columns="instrument", values="forward_return")
               .reindex(index=signal_dates))
    forward.index = pd.to_datetime(forward.index)
    columns = forward.columns
    print(f"signals loaded {time.time()-t0:.0f}s", flush=True)

    panel_frame = pd.concat([frame, scores.reset_index(drop=True)], axis=1)
    panels = {}
    for key in R.POOL:
        panels[key] = panel_frame.pivot_table(index="date", columns="instrument", values=key)\
                                 .reindex(index=signal_dates, columns=columns)
    fnet = pickle.loads((R.OUT / "fnet01_panels.pkl").read_bytes())
    for tag in ("qfq", "raw"):
        pf = frame.copy(); pf["_v"] = fnet[tag].to_numpy()
        panels[f"fnet01_{tag}"] = pf.pivot_table(index="date", columns="instrument", values="_v")\
                                    .reindex(index=signal_dates, columns=columns)
    for key in KEYS:
        if key in panels:
            continue
        panels[key] = panel_frame.pivot_table(index="date", columns="instrument", values=key)\
                                 .reindex(index=signal_dates, columns=columns)
    print(f"panels ready ({len(panels)}) {time.time()-t0:.0f}s", flush=True)

    frame_daily = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, START, END,
                                     market_cap_field=None)
    print(f"daily frame {frame_daily.shape} {time.time()-t0:.0f}s", flush=True)
    close = frame_daily.pivot_table(index="date", columns="instrument", values="close_qfq")
    close.index = pd.to_datetime(close.index)
    close = close.sort_index()
    daily_ret = close.ffill().pct_change().fillna(0.0)
    print(f"close panel {close.shape} {time.time()-t0:.0f}s", flush=True)
    del frame_daily

    trade_dates = [d for d in daily_ret.index if d >= pd.Timestamp(signal_dates[0])]

    seat_z = {k: R.zscore(panels[k]) for k in R.POOL}
    base_score = sum(seat_z.values()) / len(seat_z)
    combos = {"base_5seat": base_score}
    for key in KEYS:
        if key in R.POOL:
            continue
        combos[f"add6_{key}"] = (sum(seat_z.values()) + R.zscore(panels[key])) / (len(seat_z) + 1)

    report = {"cost_roundtrip": COST, "start": str(signal_dates[0]), "end": str(END.date()),
              "portfolios": {}, "field_max_dd_median": 0.0415}
    for name, score in combos.items():
        held_map, turn_map, prev = {}, {}, set()
        for date in score.index:
            f = score.loc[date].to_numpy(dtype="float64")
            y = forward.loc[date].to_numpy(dtype="float64")
            ok = np.isfinite(f) & np.isfinite(y)
            if ok.sum() < 100:
                continue
            inst = score.columns.to_numpy()[ok]
            order = np.argsort(-f[ok])[: int(ok.sum() * 0.1)]
            sel = set(inst[order].tolist())
            held_map[pd.Timestamp(date)] = sel
            turn_map[pd.Timestamp(date)] = np.nan if not prev else 1 - len(sel & prev) / len(sel)
            prev = sel
        reb_dates = sorted(held_map)
        bench = daily_ret.mean(axis=1)
        pnl = pd.Series(0.0, index=trade_dates)
        for i, date in enumerate(reb_dates):
            nxt = reb_dates[i + 1] if i + 1 < len(reb_dates) else daily_ret.index[-1]
            window = [d for d in trade_dates if date < d <= nxt]
            if not window:
                continue
            cols = [c for c in held_map[date] if c in daily_ret.columns]
            block = daily_ret.loc[window, cols].mean(axis=1).fillna(0.0)
            pnl.loc[window] = block.to_numpy()
            coin = [d for d in window if d in daily_ret.index]
            if coin:
                pnl.loc[coin[0]] -= COST * (turn_map[date] if np.isfinite(turn_map[date]) else 1.0)
        pnl_trim = pnl.loc[pnl.index >= pd.Timestamp(reb_dates[0])]
        excess = pnl_trim - bench.reindex(pnl_trim.index).fillna(0.0)
        mdd = monthly_maxdd(pnl_trim)
        mdd_ex = monthly_maxdd(excess)
        # 逐月 C 分项输入（Rex_ann / SR_ann / MaxDD），供逐月实测 ΔNC 用
        bench_trim = bench.reindex(pnl_trim.index).fillna(0.0)
        month_stats = {}
        for (year, month), chunk in pnl_trim.groupby([pnl_trim.index.year, pnl_trim.index.month]):
            n = len(chunk)
            if n < 5:
                continue
            bench_chunk = bench_trim.loc[chunk.index]
            rp = float(np.prod(1 + chunk.to_numpy()) - 1)
            rb = float(np.prod(1 + bench_chunk.to_numpy()) - 1)
            rex = (1 + rp) ** (252.0 / n) - 1 - ((1 + rb) ** (252.0 / n) - 1)
            sd = float(chunk.std(ddof=1))
            sr = float(chunk.mean() / sd * np.sqrt(252.0)) if sd else 0.0
            month_stats[f"{year}-{month:02d}"] = {
                "rex_ann": rex, "sr_ann": sr,
                "maxdd": float(mdd.get(f"{year}-{month:02d}", np.nan)),
                "n_days": n, "n_reb": int(sum(1 for d in reb_dates if (d.year, d.month) == (year, month))),
            }
        report["portfolios"][name] = {
            "n_days": int(len(pnl_trim)), "n_months": int(len(mdd)),
            "full_period_maxdd_daily": maxdd(pnl_trim.to_numpy()),
            "full_period_maxdd_excess": maxdd(excess.to_numpy()),
            "monthly_maxdd_median": float(mdd.median()),
            "monthly_maxdd_mean": float(mdd.mean()),
            "monthly_maxdd_p25": float(mdd.quantile(0.25)),
            "monthly_maxdd_p75": float(mdd.quantile(0.75)),
            "monthly_maxdd_p90": float(mdd.quantile(0.90)),
            "monthly_maxdd_excess_median": float(mdd_ex.median()),
            "monthly_maxdd_by_month": {k: round(v, 5) for k, v in mdd.items()},
            "monthly_c_inputs": month_stats,
        }
        r = report["portfolios"][name]
        print(f"{name:42s} fullDD(daily) {r['full_period_maxdd_daily']:.3f} "
              f"fullDD(excess) {r['full_period_maxdd_excess']:.3f} "
              f"月DD 中位 {r['monthly_maxdd_median']:.4f} p75 {r['monthly_maxdd_p75']:.4f} "
              f"p90 {r['monthly_maxdd_p90']:.4f} | 超额月DD 中位 {r['monthly_maxdd_excess_median']:.4f}",
              flush=True)
    (OUT / "daily_dd.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"done {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
