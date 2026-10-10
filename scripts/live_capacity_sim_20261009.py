#!/usr/bin/env python3
"""实盘容量模拟：top-N 等权 + 整手 + 真实费用 vs 完整 top-10% 版（零平台算力）。

对照口径（沿用本地管线）：
  * 信号日 = 平台保存的调仓日期；持有到下一个信号日；基准 = 全 A 等权日收益均值
  * 完整版 = 综合分前 10% 等权（≈500 只，分数权重，无整手约束），成本 0.30% 单边
  * 集中版 = 综合分前 80 名等权
  * 实盘版 = 集中版 + 整手（100 股）+ 佣金(万2.5, 最低 1/5 元) + 印花税 0.05%(卖) + 过户费 + 滑点 5bp
输出：research_reports/live-capacity-20261009/{summary.json, daily.csv}
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
OUT = ROOT / "research_reports/live-capacity-20261009"
START, END = pd.Timestamp("2021-08-01"), pd.Timestamp("2026-09-07")

COST_ROUNDTRIP = 0.006      # 完整版/集中版：0.30% 单边
COMMISSION_RATE = 0.00025   # 万 2.5
STAMP = 0.0005              # 印花税（卖出）
TRANSFER = 0.00002          # 过户费（双边，≈万0.1 各边）
SLIPPAGE = 0.0005           # 单边滑点 5bp
TOP_N = 80


def ann(series: pd.Series, periods: int = 252) -> float:
    """算术年化（与本地管线一致：默认算术累计）。"""
    return float(series.mean() * periods)


def geo(series: pd.Series) -> float:
    curve = (1 + series).prod()
    return float(curve ** (252 / max(len(series), 1)) - 1)


def maxdd(x: pd.Series) -> float:
    curve = (1 + x).cumprod()
    return float(-(curve / curve.cummax() - 1).min())


def monthly_dd(s: pd.Series) -> dict:
    out = {}
    for (yy, mm), chunk in s.groupby([s.index.year, s.index.month]):
        curve = (1 + chunk).cumprod()
        out[f"{yy}-{mm:02d}"] = float(-(curve / curve.cummax() - 1).min())
    return out


def load_panels():
    cache = Path("/tmp/live_capacity_sim_panels_20261009.pkl")
    if cache.exists():
        base, forward, close = pickle.loads(cache.read_bytes())
        print(f"panels from cache {base.shape} {close.shape}", flush=True)
        return base, forward, close
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
    panel_frame = pd.concat([frame, scores.reset_index(drop=True)], axis=1)
    panels = {k: panel_frame.pivot_table(index="date", columns="instrument", values=k)
              .reindex(index=signal_dates, columns=columns) for k in R.POOL}
    seat_z = {k: R.zscore(panels[k]) for k in R.POOL}
    base = sum(seat_z.values()) / len(seat_z)
    print(f"score panel ready {base.shape} {time.time()-T0:.0f}s", flush=True)
    fd = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, START, END,
                            market_cap_field=None)
    close = fd.pivot_table(index="date", columns="instrument", values="close_qfq")
    close.index = pd.to_datetime(close.index)
    close = close.sort_index().ffill()
    print(f"close panel ready {close.shape} {time.time()-T0:.0f}s", flush=True)
    cache.write_bytes(pickle.dumps((base, forward, close)))
    return base, forward, close


def reb_mapping(score, index_like):
    """调仓日 = 信号日之后第一个交易日；返回 (排序后的调仓日, 调仓日→信号日)。"""
    td = [d for d in index_like if d >= pd.Timestamp(score.index[0])]
    pairs = sorted({d for d in td for s in ()})
    out = {}
    for s in score.index:
        s = pd.Timestamp(s)
        nxt = next((d for d in td if d > s), None)
        if nxt is not None:
            out[nxt] = s
    return sorted(out), out


def selection_map(score, forward, n_select=None, exclude_688=False):
    held = {}
    for date in score.index:
        f = score.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        inst = score.columns.to_numpy()[ok]
        vals = f[ok]
        if exclude_688:
            keep = np.array([not c.startswith("688") for c in inst])
            inst, vals = inst[keep], vals[keep]
        k = n_select or int(inst.size * 0.1)
        held[pd.Timestamp(date)] = set(inst[np.argsort(-vals)[:k]].tolist())
    return held


def equal_weight_ledger(score, forward, daily_ret, n_select=None, exclude_688=False):
    """等权账本：信号日次日收盘建仓，持有到下一调仓日收盘；成本 0.30% 单边。"""
    held = selection_map(score, forward, n_select, exclude_688)
    reb_days, reb_map = reb_mapping(score, daily_ret.index)
    prev = set()
    turns = {}
    pnl = pd.Series(0.0, index=daily_ret.index)
    for i, day in enumerate(reb_days):
        s = reb_map[day]
        sel = held.get(s)
        if not sel:
            continue
        nxt = reb_days[i + 1] if i + 1 < len(reb_days) else daily_ret.index[-1]
        window = [d for d in daily_ret.index if day < d <= nxt]
        if not window:
            continue
        t = np.nan if not prev else 1 - len(sel & prev) / len(sel)
        turns[day] = t
        prev = sel
        cols = [c for c in sel if c in daily_ret.columns]
        pnl.loc[window] = daily_ret.loc[window, cols].mean(axis=1).fillna(0.0).to_numpy()
        pnl.loc[window[0]] -= COST_ROUNDTRIP * (t if np.isfinite(t) else 1.0)
    return {"n_names_median": int(np.median([len(v) for v in held.values()])),
            "turnover_mean": float(np.nanmean(list(turns.values())[1:])),
            "daily": pnl}


def _fee_of(notional: float, is_sell: bool, min_fee: float, cost_floor: float = 0.0) -> float:
    fee = max(COMMISSION_RATE * notional, min_fee) + TRANSFER * notional + SLIPPAGE * notional
    if is_sell:
        fee += STAMP * notional
    return max(fee, cost_floor * notional)


def lot_sim(score, forward, close, capital, min_fee, exclude_688=False, top_n=TOP_N,
            reb_log_path=None, cost_floor=0.0, lot_tol=1, exclude_prefixes=()):
    """整手 + 真实费用模拟（资金约束版）。

    单位约定：shares 保存实际股数（100 的整数倍），市值 = 股数 × 价格。
    调仓日执行顺序与实盘一致：先卖（释放现金），再买（用可用现金下单，不足则按可负担倍数削减）。
    """
    prices = close.astype("float64")
    tradable_dates = [d for d in prices.index if d >= pd.Timestamp(score.index[0])]
    reb_days, reb_map = reb_mapping(score, prices.index)

    cash = float(capital)
    shares: dict[str, int] = {}
    value = pd.Series(np.nan, index=tradable_dates)
    fees_paid = 0.0
    turnover_list, order_list, names_list, cash_ratio, exposure_list = [], [], [], [], []
    reb_log = []

    def mark(day):
        px = prices.loc[day]
        mv = 0.0
        for nm, sh in shares.items():
            p = px.get(nm, np.nan)
            mv += sh * (p if np.isfinite(p) else 0.0)
        return mv + cash

    for day in tradable_dates:
        if day in reb_map:
            sdate = reb_map[day]
            f = score.loc[sdate].to_numpy(dtype="float64")
            y = forward.loc[sdate].to_numpy(dtype="float64")
            ok = np.isfinite(f) & np.isfinite(y)
            inst = score.columns.to_numpy()[ok]
            vals = f[ok]
            if exclude_688:
                keep = np.array([not c.startswith("688") for c in inst])
                inst, vals = inst[keep], vals[keep]
            for pf in exclude_prefixes:
                keep = np.array([not c.startswith(pf) for c in inst])
                inst, vals = inst[keep], vals[keep]
            if ok.sum() >= 100 and inst.size > 0:
                order = inst[np.argsort(-vals)][:top_n]
                px = prices.loc[day]
                eq = mark(day)
                n_target = len(order)
                tgt_shares: dict[str, int] = {}
                budget = eq / n_target if n_target else 0.0
                for nm in order:
                    p = px.get(nm, np.nan)
                    if not np.isfinite(p) or p <= 0:
                        continue
                    lots = int(budget // (100.0 * p))
                    if lots > 0:
                        tgt_shares[nm] = lots * 100
                buy_notional = sell_notional = 0.0
                orders = 0
                n_wanted = len(tgt_shares)
                fees_before = fees_paid
                # 1) 先卖：目标之外/超配部分全部卖出，释放现金
                for nm in list(shares):
                    cur = shares[nm]
                    tgt = tgt_shares.get(nm, 0)
                    if tgt >= cur:
                        continue
                    if tgt > 0 and cur - tgt < lot_tol * 100:
                        continue  # 无交易带：相差不足 lot_tol 手不调整
                    p = px.get(nm, np.nan)
                    if not np.isfinite(p) or p <= 0:
                        continue  # 无价（停牌/未上市）无法成交，继续持有
                    notional = (cur - tgt) * p
                    fee = _fee_of(notional, True, min_fee, cost_floor)
                    cash += notional - fee
                    fees_paid += fee
                    sell_notional += notional
                    orders += 1
                    if tgt == 0:
                        shares.pop(nm, None)
                    else:
                        shares[nm] = tgt
                # 2) 再买：受真实可用现金约束，超出则按可负担手数下调
                for nm, tgt in tgt_shares.items():
                    cur = shares.get(nm, 0)
                    if tgt <= cur:
                        continue
                    if cur > 0 and tgt - cur < lot_tol * 100:
                        continue  # 无交易带
                    p = px.get(nm, np.nan)
                    if not np.isfinite(p) or p <= 0:
                        continue
                    want_lots = (tgt - cur) // 100
                    afford = int(cash // (100.0 * p))
                    while afford > 0:
                        notional = afford * 100.0 * p
                        if notional + _fee_of(notional, False, min_fee, cost_floor) <= cash:
                            break
                        afford -= 1
                    lots = min(want_lots, afford)
                    if lots <= 0:
                        continue
                    notional = lots * 100.0 * p
                    fee = _fee_of(notional, False, min_fee, cost_floor)
                    cash -= notional + fee
                    fees_paid += fee
                    buy_notional += notional
                    orders += 1
                    shares[nm] = cur + lots * 100
                traded = buy_notional + sell_notional
                cash_ratio.append(cash / eq if eq > 0 else np.nan)
                exposure_list.append(1.0 - cash / eq if eq > 0 else np.nan)
                turnover_list.append(traded / (2 * eq) if eq > 0 else np.nan)
                order_list.append(orders)
                names_list.append(len(shares))
                reb_log.append({
                    "reb_date": day.date().isoformat(),
                    "signal_date": pd.Timestamp(sdate).date().isoformat(),
                    "equity_before": round(eq, 2),
                    "n_target": n_wanted,
                    "n_selected": int(n_target),
                    "n_hold_after": len(shares),
                    "buy_notional": round(buy_notional, 2),
                    "sell_notional": round(sell_notional, 2),
                    "orders": orders,
                    "fees": round(fees_paid - fees_before, 2),
                    "cash_after": round(cash, 2),
                })
        value.loc[day] = mark(day)
    value = value.ffill()
    daily = value.pct_change().fillna(0.0)
    if reb_log_path is not None:
        pd.DataFrame(reb_log).to_csv(reb_log_path, index=False)
    return {
        "daily": daily,
        "fees_total": fees_paid,
        "fees_annual_pct": fees_paid / capital / max(len(daily) / 252, 1e-9),
        "orders_per_reb_mean": float(np.mean(order_list)) if order_list else 0.0,
        "orders_per_year": float(np.mean(order_list) * len(order_list) / max(len(daily) / 252, 1e-9)) if order_list else 0.0,
        "names_median": int(np.median(names_list)) if names_list else 0,
        "turnover_mean": float(np.nanmean(turnover_list)) if turnover_list else np.nan,
        "cash_ratio_mean": float(np.nanmean(cash_ratio)) if cash_ratio else np.nan,
        "exposure_mean": float(np.nanmean(exposure_list)) if exposure_list else np.nan,
        "final_value": float(value.iloc[-1]),
        "capital": capital,
    }


def summarize(tag: str, daily: pd.Series, bench: pd.Series) -> dict:
    excess = (daily - bench.reindex(daily.index).fillna(0.0)).dropna()
    mdd_m = monthly_dd(excess)
    return {
        "tag": tag,
        "ann_net_excess_arith": ann(excess),
        "ann_net_excess_geo": geo(excess),
        "maxdd_full": maxdd(excess),
        "maxdd_month_median": float(np.median(list(mdd_m.values()))),
        "maxdd_month_p90": float(np.percentile(list(mdd_m.values()), 90)),
        "n_days": int(len(excess)),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    base, forward, close = load_panels()
    daily_ret = close.pct_change().fillna(0.0)
    bench = daily_ret.mean(axis=1)
    results = {}

    full = equal_weight_ledger(base, forward, daily_ret, None)
    results["full_top10pct_frac"] = {**{k: v for k, v in full.items() if k != "daily"},
                                     **summarize("full", full["daily"], bench)}
    print("full done", time.time() - T0, flush=True)

    top80 = equal_weight_ledger(base, forward, daily_ret, TOP_N)
    results["top80_frac_nolot"] = {**{k: v for k, v in top80.items() if k != "daily"},
                                   **summarize("top80_frac", top80["daily"], bench)}
    print("top80 frac done", time.time() - T0, flush=True)

    variants = (
        dict(cap=100_000, fee=1.0, ex688=False, tag="top80_lot_10w_fee1"),
        dict(cap=100_000, fee=5.0, ex688=False, tag="top80_lot_10w_fee5"),
        dict(cap=100_000, fee=1.0, ex688=True, tag="top80_lot_10w_fee1_ex688"),
        dict(cap=300_000, fee=1.0, ex688=False, tag="top80_lot_30w_fee1"),
        dict(cap=630_000, fee=1.0, ex688=False, tag="fulltop10pct_lot_63w_fee1"),
        # 保守口径：单边成本不足 0.30% 时补足到 0.30%（与本地管线/平台口径一致）
        dict(cap=100_000, fee=1.0, ex688=False, tag="top80_lot_10w_fee1_c30", cost_floor=0.003),
        dict(cap=300_000, fee=1.0, ex688=False, tag="top80_lot_30w_fee1_c30", cost_floor=0.003),
        dict(cap=100_000, fee=1.0, ex688=False, tag="top80_lot_10w_fee1_c30_tol2",
             cost_floor=0.003, lot_tol=2),
    )
    for spec in variants:
        tag = spec["tag"]
        top_n = TOP_N if "top80" in tag else 511
        sim = lot_sim(base, forward, close, spec["cap"], spec["fee"], exclude_688=spec["ex688"],
                      top_n=top_n, reb_log_path=OUT / f"rebalance_{tag}.csv",
                      cost_floor=spec.get("cost_floor", 0.0), lot_tol=spec.get("lot_tol", 1))
        series = sim.pop("daily")
        results[tag] = {**sim, **summarize(tag, series, bench)}
        series.rename(tag).to_frame().to_csv(OUT / f"daily_{tag}.csv")
        print(f"{tag} done {time.time()-T0:.0f}s", flush=True)

    full["daily"].rename("full_top10pct_frac").to_frame().to_csv(OUT / "daily_full.csv")
    (OUT / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


T0 = time.time()
if __name__ == "__main__":
    raise SystemExit(main())
