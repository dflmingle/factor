"""Diagnose why TURN and BM top-20 lists disagree with the platform.

Tests two hypotheses:
  1. long rolling windows: full-window requirement (`min_periods=window`) vs
     partial-window allowance for the 504-day turnover mean;
  2. book-to-market vintage: latest reported (MRQ) equity vs annual (LYR) equity
     against the platform's saved book-to-market top-20 list.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
import financial_factor_local as ffl  # noqa: E402

PLATFORM_RUNS = {
    "HT13-TURN-BIAS-1M": "2026-09-04",
    "HT13-VALUE-BP": "2026-09-04",
    "SIZE-ONLY-20260911": "2026-09-07",
    "H03-T10-SINGLE": "2026-09-07",
}


def find_run(factor_name: str) -> tuple[dict, list[dict]]:
    for path in glob.glob("*report.csv") + glob.glob("*/*report.csv"):
        for row in pd.read_csv(path).to_dict("records"):
            if row.get("name") != factor_name:
                continue
            raw = row.get("raw_result")
            if not raw or not Path(str(raw)).exists():
                continue
            payload = json.loads(Path(str(raw)).read_text())
            top = _find_top(payload)
            if top:
                return row, top
    raise SystemExit(f"platform run for {factor_name} not found")


def _find_top(obj):
    if isinstance(obj, dict):
        if "query_last_date_top_factor" in obj:
            return obj["query_last_date_top_factor"]
        for value in obj.values():
            found = _find_top(value)
            if found:
                return found
    if isinstance(obj, str) and obj.lstrip().startswith("{"):
        try:
            return _find_top(json.loads(obj))
        except ValueError:
            return None
    return None


def top_list(values: pd.Series, ascending: bool, n: int = 20) -> list[str]:
    frame = values.dropna().to_frame("v")
    return frame.sort_values(["v"], ascending=[ascending]).head(n).index.tolist()


def overlap(local: list[str], platform: list[str]) -> str:
    return f"{len(set(local) & set(platform))}/{len(platform)}"


def main() -> None:
    print("loading full-A panel", flush=True)
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, e.DATA_START, e.END)
    frame = e.select_market_cap(frame, "total_mv").sort_values(["instrument", "date"], ignore_index=True)
    cache = ffl.load_financial_cache(e.DEFAULT_FINANCIAL_ROOT)
    ffl._FINANCIAL_CACHE = cache

    for name, date_text in PLATFORM_RUNS.items():
        row, top = find_run(name)
        day = pd.Timestamp(date_text)
        platform_symbols = [str(item.get("symbol")) for item in top]
        direction = int(float(row.get("direction", 1)))
        ascending = direction == 0
        print("=" * 90)
        print(f"{name} | platform direction {row.get('direction')} | top date {date_text} | top20 {platform_symbols[:5]}...")

        print(f"  platform list sample: {platform_symbols[:6]}")
        panel = frame[frame["date"].eq(day)].set_index("instrument")
        side_probe = pd.DataFrame(index=panel.index)
        side_probe["total_mv"] = panel["total_mv"]
        side_probe["turnover"] = panel["turnover"]
        for label, key in (("total_mv (SIZE axis)", "total_mv"), ("turnover", "turnover")):
            high = top_list(side_probe[key], ascending=False)
            low = top_list(side_probe[key], ascending=True)
            print(f"  probe {label:18s} high-end overlap {overlap(high, platform_symbols):>6s} | low-end {overlap(low, platform_symbols):>6s}")
        if not panel.empty:
            # variant A: same handler semantics as the comparison tool
            work = frame.copy()
            grouped = work.groupby("instrument", sort=False, observed=True)["turnover"]
            turn21_full = grouped.rolling(21, min_periods=21).mean().reset_index(level=0, drop=True).reindex(work.index)
            turn504_full = grouped.rolling(504, min_periods=504).mean().reset_index(level=0, drop=True).reindex(work.index)
            turn504_part = grouped.rolling(504, min_periods=21).mean().reset_index(level=0, drop=True).reindex(work.index)
            work["turn_full"] = turn21_full.div(turn504_full).sub(1.0)
            work["turn_partial"] = turn21_full.div(turn504_part).sub(1.0)
            day_rows = work[work["date"].eq(day)].set_index("instrument")
            for label, col in (("turn_bias min_periods=504", "turn_full"), ("turn_bias min_periods=21", "turn_partial")):
                for side, asc in (("low-end", True), ("high-end", False)):
                    local = top_list(day_rows[col], asc)
                    print(f"  {label:28s} {side:8s} overlap {overlap(local, platform_symbols):>6s}  sample {local[:4]}")
            if name == "HT13-TURN-BIAS-1M":
                continue

        # book-to-market variants for the BM factor
        selected = ffl._base_signal(frame, [day])
        selected = selected[selected["date"].eq(day)].set_index("instrument")
        for label, col in (
            ("ratio_bm_ttm (MRQ equity)", "ratio_bm_ttm"),
            ("book_to_market_ratio_lyr", "book_to_market_ratio_lyr"),
            ("book_to_market_ratio_lf", "book_to_market_ratio_lf"),
        ):
            if col not in selected.columns:
                continue
            local = top_list(selected[col], ascending)
            print(f"  {label:32s} overlap {overlap(local, platform_symbols):>6s}  sample {local[:5]}")


if __name__ == "__main__":
    main()
