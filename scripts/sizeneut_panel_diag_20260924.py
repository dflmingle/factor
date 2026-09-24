"""(diag) Post-hoc checks on the cached top candidate's panels.

Reads /tmp/sizeneut_panels.npz (from sizeneut_panel_cache_20260924.py) and:
  1. verifies the demeaning semantics (recompute from raw + bucket20)
  2. reports tail diagnostics (are extremes driving the size correlation?)
  3. strips the size component in rank space, with aligned buckets, and re-measures
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

CACHE = Path("/tmp/sizeneut_panels.npz")
CYCLE, COST = 10, 0.006


def rank(a: np.ndarray) -> np.ndarray:
    order = np.argsort(np.argsort(a, kind="stable"), kind="stable")
    return order.astype("float64")


def demean_group(panel: np.ndarray, group: np.ndarray) -> np.ndarray:
    out = np.full_like(panel, np.nan, dtype="float64")
    for day in range(panel.shape[0]):
        vals, grp = panel[day], group[day]
        for k in np.unique(grp[grp >= 0]):
            m = (grp == k) & np.isfinite(vals)
            if m.sum() < 5:
                out[day][m] = vals[m]
                continue
            out[day][m] = vals[m] - vals[m].mean()
    return out


def rank_strip(panel: np.ndarray, axis: np.ndarray, group: np.ndarray | None = None) -> np.ndarray:
    """Subtract the linear component of rank(panel) on rank(axis) (optionally within group)."""
    out = np.full_like(panel, np.nan, dtype="float64")
    for day in range(panel.shape[0]):
        y, x = panel[day], axis[day]
        g = group[day] if group is not None else np.zeros_like(x)
        for k in np.unique(g[np.isfinite(x)]):
            m = np.isfinite(x) & np.isfinite(y) & ((g == k) if group is not None else True)
            if m.sum() < 50:
                continue
            rx, ry = rank(x[m]), rank(y[m])
            xs = (rx - rx.mean()) / rx.std()
            A = np.column_stack([np.ones(m.sum()), xs])
            coef, *_ = np.linalg.lstsq(A, ry, rcond=None)
            out[day][m] = ry - A @ coef
    return out


def stats(panel: np.ndarray, fwd: np.ndarray) -> dict:
    gross, turn, rics, prev = [], [], [], None
    for day in range(panel.shape[0]):
        f, r = panel[day], fwd[day]
        ok = np.isfinite(f) & np.isfinite(r)
        if ok.sum() < 100:
            continue
        x, y = f[ok], r[ok]
        n = int(len(x) * 0.1)
        sel = np.argsort(-x)[:n]
        if prev is not None:
            turn.append(1 - len(set(sel.tolist()) & prev) / n)
        prev = set(sel.tolist())
        gross.append(y[sel].mean() - y.mean())
        rics.append(np.corrcoef(rank(x), rank(y))[0, 1])
    gross = np.array(gross)
    years = len(gross) * CYCLE / 252
    ann = float(np.prod(1 + gross) ** (1 / years) - 1)
    tmean = float(np.mean(turn)) if turn else 0.0
    return dict(gross=ann, turnover=tmean, net=ann - tmean * (252 / CYCLE) * COST,
                rank_ic=float(np.mean(rics)))


def corr_with(panel: np.ndarray, axis: np.ndarray) -> float:
    values = []
    for day in range(panel.shape[0]):
        x, y = axis[day], panel[day]
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        a, b = rank(x[ok]), rank(y[ok])
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(values))


def within_group_corr(panel: np.ndarray, axis: np.ndarray, group: np.ndarray) -> float:
    values = []
    for day in range(panel.shape[0]):
        x, y, g = axis[day], panel[day], group[day]
        for k in np.unique(g[g >= 0]):
            m = (g == k) & np.isfinite(x) & np.isfinite(y)
            if m.sum() < 30:
                continue
            a, b = rank(x[m]), rank(y[m])
            if a.std() == 0 or b.std() == 0:
                continue
            values.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(values))


def main() -> int:
    z = np.load(CACHE, allow_pickle=True)
    raw, axis, fwd = z["raw"], z["size_axis"], z["forward"]
    neu20, neu40, neu100 = z["neu20"], z["neu40"], z["neu100"]
    b20, b40, b100 = z["bucket20"], z["bucket40"], z["bucket100"]

    print("=== 1. demean semantics (signal-aligned buckets) ===", flush=True)
    for name, neu, b in (("neu20", neu20, b20), ("neu40", neu40, b40), ("neu100", neu100, b100)):
        recomputed = demean_group(raw, b)
        ok = np.isfinite(neu) & np.isfinite(recomputed)
        print(f"  {name}: max|saved - recomputed| = {np.nanmax(np.abs(neu[ok] - recomputed[ok])):.3e} "
              f"(overlap {ok.mean():.3f})", flush=True)

    print("\n=== 2. tail diagnostics ===", flush=True)
    finite_raw = raw[np.isfinite(raw)]
    print("  raw: p50|.|=%.4g p99|.|=%.4g p99.9|.|=%.4g max|.|=%.4g   frac>1e3=%.4g frac>1e6=%.4g"
          % (np.percentile(np.abs(finite_raw), 50), np.percentile(np.abs(finite_raw), 99),
             np.percentile(np.abs(finite_raw), 99.9), np.abs(finite_raw).max(),
             float((np.abs(finite_raw) > 1e3).mean()), float((np.abs(finite_raw) > 1e6).mean())),
          flush=True)
    for name, panel in (("raw", raw), ("neu20", neu20), ("neu100", neu100)):
        pear = []
        for day in range(panel.shape[0]):
            x, y = axis[day], panel[day]
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 100 or x[ok].std() == 0 or y[ok].std() == 0:
                continue
            pear.append(float(np.corrcoef(x[ok], y[ok])[0, 1]))
        print(f"  {name}: Pearson(y,size)={np.mean(pear):+.4f}  Spearman={corr_with(panel, axis):+.4f}  "
              f"Spearman within bucket20={within_group_corr(panel, axis, b20):+.4f}", flush=True)

    print("\n=== 3. panels ===", flush=True)
    rows = [("raw", raw, None), ("neu20", neu20, None), ("neu40", neu40, None),
            ("neu100", neu100, None)]
    print("  rank-space strips (aligned buckets):", flush=True)
    rows.append(("neu20 + rank-strip on size", rank_strip(neu20, axis), None))
    rows.append(("neu20 + within-bucket rank-strip",
                 rank_strip(neu20, axis, b20), None))
    rows.append(("raw + rank-strip on size", rank_strip(raw, axis), None))
    for name, panel, _ in rows:
        s = stats(panel, fwd)
        print(f"  {name:32s} IC={s['rank_ic']:+.4f} turn={s['turnover']:.3f} "
              f"gross={s['gross']:+.4f} net={s['net']:+.4f} "
              f"corr_size={corr_with(panel, axis):+.3f} "
              f"corr_size_within={within_group_corr(panel, axis, b20):+.3f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
