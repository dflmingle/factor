"""Measure named-field panel lookup cost (cold vs warm) for the wide GP search."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ROOT / "research_reports/platform_alignment/wider-field-search-20260923/fields.txt"


def build_data():
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
    return gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
        end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
        device=device, financial_root=gp.DEFAULT_FINANCIAL_ROOT)


def timed_lookup(store, names: list[str]) -> dict:
    t0 = time.perf_counter()
    slowest = (None, 0.0)
    for name in names:
        t = time.perf_counter()
        store.get_named_feature(name)
        cost = time.perf_counter() - t
        if cost > slowest[1]:
            slowest = (name, cost)
    total = time.perf_counter() - t0
    return dict(total=total, per_field_ms=1000 * total / max(len(names), 1),
                slowest_field=slowest[0], slowest_ms=1000 * slowest[1])


def main() -> int:
    t0 = time.perf_counter()
    data = build_data()
    print(f"data loaded in {time.perf_counter() - t0:.1f}s", flush=True)
    store = data.pandaai_field_store
    fields = [line.strip().lower() for line in FIELDS.read_text().splitlines() if line.strip()]
    active = set(store.active_search_fields(include_period_variants=True))
    fields = [f for f in fields if f in active]
    print(f"probe fields={len(fields)} default_cache={store.max_cached_fields}", flush=True)

    # warm-up single pass so the underlying financial cache is hot
    store.get_named_feature("close")
    print("close cold:", timed_lookup(store, ["close"]), flush=True)

    for cache_size in (24, 400):
        store.max_cached_fields = cache_size
        store._array_cache.clear()
        store._panel_cache.clear()
        cold = timed_lookup(store, fields)
        warm = timed_lookup(store, fields)
        print(f"cache={cache_size} pass1(cold)={cold}", flush=True)
        print(f"cache={cache_size} pass2(warm)={warm}", flush=True)

    # expression-level repeat cost on a financial leaf vs a price leaf
    namespace = gp.expression_namespace()
    for formula in (
        "Div(TsDiv(book_to_market_ratio_lyr,40),market_cap)",
        "Div(TsStd(close,20),market_cap)",
        "Div(TsStd(total_assets_mrq_3,20),market_cap)",
    ):
        expression = gp.evaluate_formula(formula, namespace)
        with torch.no_grad():
            t = time.perf_counter(); expression.evaluate(data); first = time.perf_counter() - t
            t = time.perf_counter(); expression.evaluate(data); second = time.perf_counter() - t
        print(f"eval {formula}: first={1000*first:.1f}ms repeat={1000*second:.1f}ms", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
