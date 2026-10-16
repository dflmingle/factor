"""Three predeclared seat corrections. No labels, fitting, or platform calls.

Z is per-date 1%/99% winsorisation followed by population z-score.
Inputs are incumbent F scores and causal quarterly NL02 predictions on the
same ordered signal dates and stocks. Apply history before slicing 2026.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def normalize(x):
    # Fix layout so NumPy reductions use the same order for a full panel and
    # its prefix; even float64 rounding differences fail repaint checks.
    x = np.ascontiguousarray(x, dtype=np.float64)
    x = np.where(np.isfinite(x), x, np.nan)
    lo = np.nanquantile(x, .01, axis=1, keepdims=True)
    hi = np.nanquantile(x, .99, axis=1, keepdims=True)
    clipped = np.clip(x, lo, hi)
    sd = np.nanstd(clipped, axis=1, keepdims=True)
    return np.divide(clipped - np.nanmean(clipped, axis=1, keepdims=True),
                     sd, out=np.where(np.isfinite(clipped), 0., np.nan),
                     where=sd > 1e-12)


def tree_percentiles(tree):
    tree = np.asarray(tree, dtype=float)
    n = np.isfinite(tree).sum(axis=1, keepdims=True)
    return rankdata(tree, axis=1, method="average", nan_policy="omit") / np.maximum(n, 1)


def hysteresis(q, valid):
    state = np.zeros(q.shape[1], dtype=bool)
    history = np.zeros(q.shape, dtype=bool)
    for i in range(len(q)):
        state = np.where(valid[i], np.where(q[i] < .15, True,
                                           np.where(q[i] > .25, False, state)), False)
        history[i] = state
    return history


def corrections(f_score, tree):
    """Correct F only; every output is Z-normalized before five-seat averaging."""
    f = np.asarray(f_score, dtype=float)
    q = tree_percentiles(tree)
    if f.shape != q.shape:
        raise ValueError("Seat and tree axes must be identical")
    q = np.where(np.isfinite(q), q, 1.)  # unavailable tree: retain incumbent
    z = normalize(f)
    hard = normalize(np.where(np.isfinite(f) & (q < .20), -10., f))
    continuous = normalize(z - .25 * np.maximum(0., 1. - q / .20))
    state = hysteresis(q, np.isfinite(f) & np.isfinite(tree))
    sticky = z - .25 * state
    return {"P01_NORMALIZED_HARD_F": hard,
            "P02_BOUNDED_CONTINUOUS_F": continuous,
            "P03_HYSTERESIS_F": normalize(sticky)}
