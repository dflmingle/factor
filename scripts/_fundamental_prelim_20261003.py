# -*- coding: utf-8 -*-
"""财务/估值字段族的快速预屏（2026-10-03，零平台算力）。

目的：在正式建腿/跑席位桥之前，先量化"哪些财务字段有可用 IC + 低换手"。
口径与 e_decomp_20260928 完全一致：
  - RankIC 序列：ed.rank_ic_stats（10 日 cycle、label_offset=1、方向择优）
  - s_i_local = |mean RankIC| x |ICIR| x win(|IC|>0.02)
  - 因子自身换手代理 = 顶十分位名次换手（1 - |top_t & top_{t-1}| / |top_t|）
  - corr_size = 与 total_mv 的截面秩相关（信号日均值）
并追加若干组合/推导候选：质量、价值、成长组合与 accruals、E/P 变化、SUE-lite。

PIT 财务面板由 pandaai_fields_local.PandaAIFieldStore 物化（financialfix2 审计过的
公告日 as-of 连接）；market_cap 从 e-decomp-20260929/panels_cache.pkl 注入。

用法：D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts\\_fundamental_prelim_20261003.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(r"D:\factor")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))

import e_decomp_20260928 as ed  # noqa: E402
import alphaprobe_gp_tushare as gp  # noqa: E402
from pandaai_fields_local import PandaAIFieldStore  # noqa: E402

ed.DEFAULT_REBUILD = (ROOT / "research_reports" / "platform_alignment"
                      / "ab-batch-20260925" / "seat_panels_rebuilt.pkl")  # AB-BATCH-OVERRIDE
OUT = ROOT / "research_reports" / "platform_alignment" / "field-recon-20261003"
PANELS = ROOT / "research_reports" / "platform_alignment" / "e-decomp-20260929" / "panels_cache.pkl"
COVERAGE = OUT / "field_coverage.csv"

FIELDS = [
    # quality / profitability
    "oper_roe_ttm", "oper_roe_lyr", "oper_roe_diluted_ttm", "oper_roa_ttm", "oper_roa_lyr",
    "oper_gross_margin_ttm", "oper_gross_margin_lyr", "oper_net_margin_ttm", "oper_net_margin_lyr",
    "oper_roic_ttm", "oper_roic_lyr", "oper_total_asset_turnover_ttm", "oper_total_asset_turnover_lyr",
    # leverage / balance
    "fin_debt_to_asset_ttm", "fin_debt_to_asset_lyr", "fin_debt_to_asset_lf",
    "fin_current_ratio_ttm", "fin_current_ratio_lyr", "fin_current_ratio_lf",
    # cashflow
    "cfd_ocf_to_debt_ttm", "cfd_ocf_to_debt_lyr", "cfd_ocf_per_share_ttm",
    "cfd_ocf_per_share_lyr", "cfd_flow_per_share_ttm", "cfd_flow_per_share_lyr",
    # growth
    "gr_net_profit_ttm", "gr_np_parent_ttm", "gr_ocf_ttm", "gr_oper_profit_ttm",
    "gr_total_asset_lyr", "gr_total_asset_ttm",
    # value
    "ratio_ep_lyr", "ratio_ep_ttm", "ratio_pe_lyr", "ratio_pe_ttm",
    "ratio_bm_lyr", "ratio_bm_ttm", "ratio_bm_lf", "ratio_sp_lyr", "ratio_sp_ttm",
    "ratio_cfp_lyr", "ratio_cfp_ttm", "ratio_pcf_ocf_lyr", "ratio_pcf_ocf_ttm",
    "ratio_ev_lyr", "ratio_ev_ttm", "ratio_peg_lyr", "ratio_peg_ttm",
    # statements (for composites)
    "bs_total_assets", "cfs_net_cash_operating", "is_n_income_attr_p",
]
COMPOSITES = {
    "comp_quality": [("oper_roe_ttm", None), ("oper_roa_ttm", None), ("oper_gross_margin_ttm", None),
                     ("oper_net_margin_ttm", None), ("oper_roic_ttm", None)],
    "comp_value": [("ratio_ep_ttm", None), ("ratio_bm_lf", None), ("ratio_sp_ttm", None),
                   ("ratio_cfp_ttm", None)],
    "comp_growth": [("gr_net_profit_ttm", None), ("gr_np_parent_ttm", None), ("gr_ocf_ttm", None),
                    ("gr_oper_profit_ttm", None)],
    "comp_qv": [("oper_roe_ttm", None), ("oper_roic_ttm", None), ("ratio_ep_ttm", None),
                ("ratio_bm_lf", None), ("ratio_sp_ttm", None)],
}


class _StubData:
    pass


def build_store(market, panels):
    stub = _StubData()
    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stub._pre_dates = []
    stub._evaluation_dates = eval_dates
    stub._post_dates = []
    stub._pre_padding = 0
    stub.n_stocks = int(market.data.n_stocks)
    stub._stock_ids = [str(x) for x in market.data._stock_ids]
    stub.data = market.data.data
    frame = pd.DataFrame({"date": [], "instrument": [], "total_mv": []})
    store = PandaAIFieldStore(data=stub, frame=frame, financial_root=gp.DEFAULT_FINANCIAL_ROOT,
                              max_cached_fields=2, max_cached_arrays=64)
    mcap = panels["mcap"].reindex(index=eval_dates, columns=stub._stock_ids).to_numpy(dtype=np.float32)
    original_daily_panel = store._daily_panel

    def _daily_panel(column, *, fill="none"):
        if column == "total_mv":
            return mcap.copy()
        if column == "circ_mv":
            return np.full_like(mcap, np.nan)
        return original_daily_panel(column, fill=fill)

    store._daily_panel = _daily_panel  # probe-only shim
    return store


def churn_and_size(signal: pd.DataFrame, mcap_signal: pd.DataFrame):
    tops, sizes = [], []
    previous = None
    for date in signal.index:
        row = signal.loc[date]
        valid = row.notna()
        if valid.sum() < 500:
            continue
        ranks = row[valid].rank(pct=True)
        top = set(ranks.index[ranks > 0.9])
        if previous is not None:
            tops.append(1.0 - len(top & previous) / len(top))
        previous = top
        cap = mcap_signal.loc[date]
        both = valid & cap.notna()
        if int(both.sum()) >= 500:
            a = row[both].rank().to_numpy()
            b = cap[both].rank().to_numpy()
            sizes.append(float(np.corrcoef(a, b)[0, 1]))
    return (float(np.mean(tops)) if tops else np.nan,
            float(np.mean(sizes)) if sizes else np.nan)


def measure(name, arr_eval, market, eval_dates, stocks, signal_dates, positions, mcap_signal):
    finite = float(np.isfinite(arr_eval).mean())
    values = torch.from_numpy(np.asarray(arr_eval, dtype=np.float32).copy())
    with torch.no_grad():
        stats = ed.rank_ic_stats(market.context, values)
        stats_neg = ed.rank_ic_stats(market.context, -values)
    chosen = 1
    if not stats or (stats_neg and stats_neg["rank_ic"] > stats["rank_ic"]):
        stats, chosen = stats_neg, -1
    if not stats:
        return None
    signal = pd.DataFrame(np.asarray(arr_eval, dtype=np.float32)[positions],
                          index=signal_dates, columns=stocks)
    signal = signal[market.context.signal_dates[0]:]
    if chosen == -1:
        signal = -signal
    churn, corr_size = churn_and_size(signal, mcap_signal)
    with torch.no_grad():
        rstats = ed.rank_ic_stats(market.context, values if chosen == 1 else -values,
                                  start=pd.Timestamp("2026-01-01"))
    recent_ic = float(rstats["rank_ic"]) if rstats else np.nan
    return dict(field=name, direction=chosen, finite=finite,
                rank_ic=stats["rank_ic"], ic_ir=stats["rank_ic_ir"], win=stats["rank_ic_win"],
                s_i=stats["s_i_rank"], churn=churn, corr_size=corr_size, recent_ic=recent_ic)


def rank_panel(arr_eval):
    frame = pd.DataFrame(arr_eval)
    return frame.rank(axis=1, pct=True).to_numpy(dtype=np.float32)


def main() -> int:
    coverage = pd.read_csv(COVERAGE)
    available = set(coverage.loc[coverage.status != "unavailable", "field"])
    fields = [name for name in FIELDS if name in available]
    skipped = [name for name in FIELDS if name not in available]
    print(f"fields requested {len(FIELDS)} | available {len(fields)} | skipped {len(skipped)}")
    if skipped:
        print("skipped:", ", ".join(skipped))

    print("loading seat payload + market ...", flush=True)
    payload = pickle.load(open(ed.DEFAULT_REBUILD, "rb"))
    market = ed.Market(payload, torch.device("cpu"))
    panels = pickle.load(PANELS.open("rb"))
    print("panels ready", flush=True)
    store = build_store(market, panels)

    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]
    positions = list(market.context.signal_data_positions)
    signal_dates = [pd.Timestamp(d) for d in market.dates]
    mcap_signal = pd.DataFrame(
        panels["mcap"].reindex(index=eval_dates, columns=stocks).to_numpy()[positions],
        index=signal_dates, columns=stocks)

    arrays: dict[str, np.ndarray] = {}
    rows = []
    for name in fields:
        try:
            arr = np.asarray(store._named_array(name), dtype=np.float32)
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] array fail: {type(exc).__name__}: {exc}"[:160], flush=True)
            continue
        arrays[name] = arr
        result = measure(name, arr, market, eval_dates, stocks, signal_dates, positions, mcap_signal)
        if result is None:
            print(f"[{name}] no stats", flush=True)
            continue
        rows.append(result)
        print(f"[{name}] dir={result['direction']:+d} ic={result['rank_ic']:+.4f} "
              f"ir={result['ic_ir']:+.3f} win={result['win']:.2f} s_i={result['s_i']:.4f} "
              f"churn={result['churn']:.3f} corr_size={result['corr_size']:+.2f} "
              f"recent_ic={result['recent_ic']:+.4f}", flush=True)

    directions = {row["field"]: row["direction"] for row in rows}
    for comp_name, members in COMPOSITES.items():
        parts = []
        for member, _ in members:
            if member not in arrays:
                parts = []
                break
            sign = directions.get(member, 1)
            parts.append(rank_panel(arrays[member]) * float(sign))
        if not parts:
            print(f"[{comp_name}] skipped (missing member)", flush=True)
            continue
        comp = np.nanmean(np.stack(parts, axis=0), axis=0).astype(np.float32)
        arrays[comp_name] = comp
        result = measure(comp_name, comp, market, eval_dates, stocks, signal_dates, positions, mcap_signal)
        if result is None:
            print(f"[{comp_name}] no stats", flush=True)
            continue
        rows.append(result)
        print(f"[{comp_name}] dir={result['direction']:+d} ic={result['rank_ic']:+.4f} "
              f"ir={result['ic_ir']:+.3f} win={result['win']:.2f} s_i={result['s_i']:.4f} "
              f"churn={result['churn']:.3f} corr_size={result['corr_size']:+.2f} "
              f"recent_ic={result['recent_ic']:+.4f}", flush=True)

    # --- derived singles: accruals / EP change / SUE-lite ---
    if {"is_n_income_attr_p", "cfs_net_cash_operating", "bs_total_assets"} <= set(arrays):
        assets = arrays["bs_total_assets"]
        assets = np.where(assets == 0, np.nan, assets)
        accruals = ((arrays["is_n_income_attr_p"] - arrays["cfs_net_cash_operating"]) / assets).astype(np.float32)
        arrays["accruals_cf"] = accruals
        result = measure("accruals_cf", accruals, market, eval_dates, stocks, signal_dates, positions, mcap_signal)
        if result:
            rows.append(result)
            print(f"[accruals_cf] dir={result['direction']:+d} ic={result['rank_ic']:+.4f} "
                  f"ir={result['ic_ir']:+.3f} win={result['win']:.2f} s_i={result['s_i']:.4f} "
                  f"churn={result['churn']:.3f} corr_size={result['corr_size']:+.2f} "
                  f"recent_ic={result['recent_ic']:+.4f}", flush=True)
    if "ratio_ep_ttm" in arrays:
        ep = pd.DataFrame(arrays["ratio_ep_ttm"])
        epchg = (ep - ep.shift(60)).to_numpy(dtype=np.float32)
        arrays["ep_chg60"] = epchg
        result = measure("ep_chg60", epchg, market, eval_dates, stocks, signal_dates, positions, mcap_signal)
        if result:
            rows.append(result)
            print(f"[ep_chg60] dir={result['direction']:+d} ic={result['rank_ic']:+.4f} "
                  f"ir={result['ic_ir']:+.3f} win={result['win']:.2f} s_i={result['s_i']:.4f} "
                  f"churn={result['churn']:.3f} corr_size={result['corr_size']:+.2f} "
                  f"recent_ic={result['recent_ic']:+.4f}", flush=True)

    frame = pd.DataFrame(rows).sort_values("s_i", ascending=False)
    frame.to_csv(OUT / "fundamental_prelim.csv", index=False, encoding="utf-8-sig")
    print(f"\nwrote {OUT / 'fundamental_prelim.csv'} ({len(frame)} rows)")
    print(frame.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())