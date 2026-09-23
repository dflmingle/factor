"""Build wide (date x instrument) panels for the local Alpha191 screen.

Source: the same qualitygate3 caches the alignment pipeline uses
(qfq daily batches + daily_basic snapshots).  No new download, no platform call.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_a_local_data import load_full_a_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "quantlab/.quantlab/cache/research/cn_equity"
PRICE_ROOT = CACHE / "tushare_factor_recheck/qfq/daily_batches"
CAP_ROOT = CACHE / "tushare_factor_recheck/daily_basic_full_a"
OUT = ROOT / "research_reports/platform_alignment/alpha191-local-20260923"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-09-07")
FIELD_MAP = {
    "open": "open_qfq",
    "close": "close_qfq",
    "high": "high_qfq",
    "low": "low_qfq",
    "volume": "volume",
    "amount": "amount",
    "turnover": "turnover",
    "total_mv": "total_mv",
    "circ_mv": "circ_mv",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, START, END)
    frame = frame.sort_values(["date", "instrument"], ignore_index=True)
    print(f"rows={len(frame)} instruments={frame['instrument'].nunique()} "
          f"dates={frame['date'].nunique()}", flush=True)
    panels: dict[str, pd.DataFrame] = {}
    for field, source in FIELD_MAP.items():
        if source not in frame.columns:
            print(f"  [warn] field missing: {source}", flush=True)
            continue
        wide = frame.pivot(index="date", columns="instrument", values=source).astype("float32")
        panels[field] = wide.sort_index().sort_index(axis=1)
        print(f"  {field}: {wide.shape}", flush=True)
    close = panels["close"]
    panels["vwap"] = (panels["amount"].to_numpy() / panels["volume"].to_numpy()).astype("float32")
    panels["vwap"] = pd.DataFrame(panels["vwap"], index=panels["amount"].index,
                                  columns=panels["amount"].columns)
    panels["returns"] = close.pct_change(fill_method=None).astype("float32")
    payload = dict(
        panels=panels,
        meta=dict(source="qualitygate3 qfq+daily_basic cache", start=str(START.date()),
                  end=str(END.date()), fields=sorted(panels)),
    )
    target = OUT / "panels.pkl"
    with target.open("wb") as handle:
        pickle.dump(payload, handle, protocol=5)
    print(f"wrote {target} ({target.stat().st_size / 1e6:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
