# -*- coding: utf-8 -*-
"""技术指标目录（cal-date / MA / oscillators / volume）200 字段快速预屏。

口径同 _fundamental_prelim_20261003.py：ed.rank_ic_stats + 顶十分位换手 + corr_size。
- 字段实现直接调用 pandaai_fields_local._catalog_technical_panel（与平台目录 1:1 命名）；
- 日线输入用 e-decomp-20260929/panels_cache.pkl 注入（_daily_panel shim）；
- 跳过 6 个 O(T×N) Python 双循环实现（mdd20/60、aroon_up/down、cal_5d_max/min_*_idx）；
- 输出：field-recon-20261003/technical_prelim.csv
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
import pandaai_fields_local as f  # noqa: E402

ed.DEFAULT_REBUILD = (ROOT / "research_reports" / "platform_alignment"
                      / "ab-batch-20260925" / "seat_panels_rebuilt.pkl")  # AB-BATCH-OVERRIDE
OUT = ROOT / "research_reports" / "platform_alignment" / "field-recon-20261003"
PANELS = ROOT / "research_reports" / "platform_alignment" / "e-decomp-20260929" / "panels_cache.pkl"

SKIP = {"mdd20", "mdd60", "aroon_up", "aroon_down",
        "cal_5d_max_high_idx", "cal_5d_min_low_idx"}


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
    frame = pd.DataFrame({"date": [], "instrument": []})
    store = f.PandaAIFieldStore(data=stub, frame=frame, financial_root=gp.DEFAULT_FINANCIAL_ROOT,
                                max_cached_fields=2, max_cached_arrays=8)
    columns = {
        "open_qfq": panels["open"], "open": panels["open"],
        "close_qfq": panels["close"], "close": panels["close"],
        "high_qfq": panels["high"], "high": panels["high"],
        "low_qfq": panels["low"], "low": panels["low"],
        "volume": panels["volume"], "amount": panels["amount"],
        "turnover": panels["turn"], "total_mv": panels["mcap"],
    }
    prepared = {}
    for name, panel in columns.items():
        prepared[name] = panel.reindex(index=eval_dates, columns=stub._stock_ids).astype("float32")

    def _daily_panel(column, *, fill="none"):
        candidates = (column,) if isinstance(column, str) else column
        for candidate in candidates:
            if candidate in prepared:
                result = prepared[candidate].to_numpy(dtype=np.float32, copy=True)
                if fill == "ffill":
                    result = pd.DataFrame(result).ffill().to_numpy(dtype=np.float32)
                elif fill == "zero":
                    result = np.nan_to_num(result, nan=0.0)
                return result
        return np.full((len(eval_dates), stub.n_stocks), np.nan, dtype=np.float32)

    store._daily_panel = _daily_panel
    store._daily_available = lambda column: True
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
        if not top:
            continue
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


def measure(name, arr_eval, market, stocks, signal_dates, positions, mcap_signal):
    finite = float(np.isfinite(arr_eval).mean())
    if finite < 0.1:
        return dict(field=name, direction=0, finite=finite, rank_ic=np.nan, ic_ir=np.nan,
                    win=np.nan, s_i=0.0, churn=np.nan, corr_size=np.nan, recent_ic=np.nan)
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


def main() -> int:
    fields = sorted(f.CATALOG_DAILY_TECHNICAL_FIELD_NAMES - SKIP)
    meta = {name: {"category": f.PLATFORM_FIELD_CATEGORIES.get(name, ""),
                   "label": f.PLATFORM_FIELD_LABELS.get(name, ""),
                   "source": f.PLATFORM_FIELD_SOURCE_FILES.get(name, "")}
            for name in fields}
    print(f"technical fields to screen: {len(fields)} (skipped {len(SKIP)})")

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

    partial = OUT / "technical_prelim_partial.csv"
    rows = []
    done: set[str] = set()
    if partial.exists():
        old_rows = pd.read_csv(partial)
        rows = old_rows.to_dict("records")
        done = {str(value) for value in old_rows["field"]}
        print(f"resuming: {len(done)} fields already measured", flush=True)
    for index, name in enumerate(fields):
        if name in done:
            continue
        try:
            arr = np.asarray(store._named_array(name), dtype=np.float32)
        except Exception as exc:  # noqa: BLE001
            print(f"[{index}/{len(fields)}][{name}] array fail: {type(exc).__name__}: {exc}"[:160], flush=True)
            continue
        result = measure(name, arr, market, stocks, signal_dates, positions, mcap_signal)
        if result is None:
            print(f"[{index}/{len(fields)}][{name}] no stats", flush=True)
            continue
        result.update(meta[name])
        rows.append(result)
        pd.DataFrame(rows).to_csv(partial, index=False, encoding="utf-8-sig")
        if (index + 1) % 10 == 0 or result["s_i"] > 0.02:
            print(f"[{index}/{len(fields)}][{name}] ic={result['rank_ic']:+.4f} ir={result['ic_ir']:+.3f} "
                  f"win={result['win']:.2f} s_i={result['s_i']:.4f} churn={result['churn']:.3f} "
                  f"corr_size={result['corr_size']:+.2f} recent={result['recent_ic']:+.4f}", flush=True)

    frame = pd.DataFrame(rows).sort_values("s_i", ascending=False)
    frame.to_csv(OUT / "technical_prelim.csv", index=False, encoding="utf-8-sig")
    if partial.exists():
        partial.unlink()
    print(f"\nwrote {OUT / 'technical_prelim.csv'} ({len(frame)} rows)")
    top = frame.head(25)
    print(top[["field", "category", "direction", "rank_ic", "ic_ir", "win", "s_i",
               "churn", "corr_size", "recent_ic"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())