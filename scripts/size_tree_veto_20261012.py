#!/usr/bin/env python3
"""Fixed, low-complexity shallow-tree vetoes inside the small-cap leg.

The tree signals are precomputed by the strict quarterly walk-forward study in
nonlinear-walkforward-20261012.  This script only evaluates three predeclared
gates; it does not refit, tune, or use future labels.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research_reports/platform_alignment/quant-corpus-source-reproduction-20261012/market_arrays.pkl"
TREE = ROOT / "research_reports/platform_alignment/nonlinear-walkforward-20261012"
OUT = ROOT / "research_reports/platform_alignment/size-tree-veto-20261012"
OUT.mkdir(parents=True, exist_ok=True)

CYCLE = 10
ONE_WAY = 0.003
FORMAL_START = pd.Timestamp("2021-09-07")
FORMAL_END = pd.Timestamp("2026-09-07")
RECENT_START = pd.Timestamp("2026-01-01")


def pct_rank(x: np.ndarray) -> np.ndarray:
    out = np.full(x.shape, np.nan, dtype=np.float32)
    for i in range(x.shape[0]):
        ok = np.isfinite(x[i])
        if ok.any():
            out[i, ok] = rankdata(x[i, ok], method="average") / ok.sum()
    return out


def evaluate(signal: np.ndarray, y: np.ndarray, cap: np.ndarray, dates: pd.DatetimeIndex) -> dict:
    ics, gross, turns, corr_size = [], [], [], []
    prev: set[int] | None = None
    periods = []
    for i, d in enumerate(dates):
        ok = np.isfinite(signal[i]) & np.isfinite(y[i]) & np.isfinite(cap[i])
        ids = np.flatnonzero(ok)
        if len(ids) < 100:
            continue
        order = ids[np.argsort(signal[i, ids], kind="stable")]
        n = max(1, int(np.ceil(len(ids) / 10)))
        top = order[-n:]
        ys = y[i, ids]
        excess = float(y[i, top].mean() - ys.mean())
        ics.append(float(pd.Series(signal[i, ids]).corr(pd.Series(y[i, ids]), method="spearman")))
        corr_size.append(float(pd.Series(signal[i, ids]).corr(pd.Series(-cap[i, ids]), method="spearman")))
        gross.append(excess)
        members = set(top.tolist())
        turn = np.nan if prev is None else 1.0 - len(prev & members) / len(members)
        turns.append(turn)
        prev = members
        periods.append({"date": str(d.date()), "gross_excess": excess, "turnover": turn,
                        "held": len(top), "valid": len(ids)})
    g = float(np.nanmean(gross) * 252.0 / CYCLE * 100.0)
    t = float(np.nanmean(turns))
    net = g - t * (2 * ONE_WAY) * 252.0 / CYCLE * 100.0
    return {
        "periods": len(gross), "rank_ic": float(np.nanmean(ics)),
        "gross_excess_pct": g, "turnover": t, "annual_cost_pct": t * 0.006 * 25.2,
        "net_excess_pct": net, "size_corr": float(np.nanmean(corr_size)),
        "periods_detail": periods,
    }


def main() -> None:
    with DATA.open("rb") as f:
        dates, symbols, fields = pickle.load(f)
    dates = pd.DatetimeIndex(dates)
    # Reuse the saved signal-date ledger; the final grid date is omitted when
    # its forward label is incomplete.
    sig_dates = pd.DatetimeIndex(pd.read_csv(TREE / "NL02_formal_5y_periods.csv")["date"])
    sig_idx = dates.get_indexer(sig_dates)
    if (sig_idx < 0).any():
        raise RuntimeError("saved signal date missing from market calendar")
    close = np.asarray(fields["close"], dtype=np.float32)
    cap = np.asarray(fields["cap"], dtype=np.float32)
    # Label is close(t+1) -> close(t+cycle+1), exactly the local alignment rule.
    yall = close[CYCLE + 1:] / close[1:-CYCLE] - 1.0
    y = np.full_like(close, np.nan, dtype=np.float32)
    y[: len(yall)] = yall
    # Existing tree files are saved on the formal signal grid in this exact order.
    if len(sig_dates) != np.load(TREE / "NL02_signal.npy", mmap_mode="r").shape[0]:
        raise RuntimeError("signal grid mismatch")
    cap_sig = cap[sig_idx]
    size = 1.0 - pct_rank(cap_sig)  # larger = smaller cap
    labels = y[sig_idx]
    tree01 = np.load(TREE / "NL01_signal.npy")
    tree02 = np.load(TREE / "NL02_signal.npy")
    tree01r = pct_rank(tree01)
    tree02r = pct_rank(tree02)

    # Three fixed hypotheses: same size anchor, tree only removes the weakest
    # names inside it. Thresholds are declared before looking at outputs.
    specs = {
        "SIV01_SIZE20_NL02_VETO20": (size, tree02r, 0.20, 0.20),
        "SIV02_SIZE20_NL02_VETO30": (size, tree02r, 0.20, 0.30),
        "SIV03_SIZE25_NL01_VETO20": (size, tree01r, 0.25, 0.20),
    }
    results = {}
    for name, (sz, tr, small_frac, veto_frac) in specs.items():
        small = sz >= 1.0 - small_frac
        gate = np.zeros_like(small, dtype=bool)
        for i in range(len(sig_dates)):
            ids = np.flatnonzero(small[i] & np.isfinite(tr[i]))
            if len(ids):
                threshold = np.nanquantile(tr[i, ids], veto_frac)
                gate[i, ids] = tr[i, ids] >= threshold
        # Keep the full valid universe; excluded names are ranked below all
        # eligible small caps, so the small-cap anchor remains explicit.
        signal = np.where(gate, sz, -1.0).astype(np.float32)
        formal = evaluate(signal, labels, cap_sig, sig_dates)
        recent = sig_dates >= RECENT_START
        recent_res = evaluate(signal[recent], labels[recent], cap_sig[recent], sig_dates[recent])
        results[name] = {"formal_5y": formal, "recent_2026": recent_res,
                         "small_cap_fraction": small_frac, "veto_fraction": veto_frac,
                         "tree": "NL02" if "NL02" in name else "NL01"}

    # Pure small-cap baseline on the same grid.
    base_signal = size.copy()
    results["SIZE_BASE"] = {"formal_5y": evaluate(base_signal, labels, cap_sig, sig_dates),
                             "recent_2026": evaluate(base_signal[ sig_dates >= RECENT_START], labels[sig_dates >= RECENT_START], cap_sig[sig_dates >= RECENT_START], sig_dates[sig_dates >= RECENT_START]),
                             "small_cap_fraction": 1.0, "veto_fraction": 0.0, "tree": None}
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    rows = []
    for name, r in results.items():
        for window, m in (("formal_5y", r["formal_5y"]), ("recent_2026", r["recent_2026"])):
            rows.append({"candidate": name, "window": window, **{k: v for k, v in m.items() if k != "periods_detail"}})
            pd.DataFrame(m["periods_detail"]).to_csv(OUT / f"{name}_{window}_periods.csv", index=False)
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    print(pd.DataFrame(rows).drop(columns=["periods"]).to_string(index=False))


if __name__ == "__main__":
    main()
