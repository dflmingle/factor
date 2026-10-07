"""Rebuild the missing e-decomp-20260929/panels_cache.pkl from the local full-A cache.

The original cache was a local (gitignored) pickle that fed scripts/repaint_check.py
and the legmix probes; it is absent on this machine.  Layout mirrors the original
builder (scripts/e_decomp_direct_20260929.py::build_panels):
date-index x instrument columns float32 panels keyed
close/open/high/low (qfq), volume, amount, turn=turnover, mcap=total_mv.
"""
import gc
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from full_a_local_data import load_full_a_data

PRICE_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq/daily_batches"
CAP_ROOT = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/daily_basic_full_a"
OUT = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"


def main() -> int:
    frame = load_full_a_data(PRICE_ROOT, CAP_ROOT, pd.Timestamp("2018-01-01"),
                             pd.Timestamp("2026-09-07"), market_cap_field="total_mv")
    print("frame", frame.shape, flush=True)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    panels = {}
    for key, col in (("close", "close_qfq"), ("open", "open_qfq"), ("high", "high_qfq"),
                     ("low", "low_qfq"), ("volume", "volume"), ("amount", "amount"),
                     ("turn", "turnover"), ("mcap", "total_mv")):
        panel = frame.pivot(index="date", columns="instrument", values=col).astype("float32")
        panels[key] = panel
        print(key, panel.shape, panel.index.min().date(), panel.index.max().date(), flush=True)
    del frame
    gc.collect()
    with OUT.open("wb") as fh:
        pickle.dump(panels, fh, protocol=5)
    print("wrote", OUT, OUT.stat().st_size, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
