"""Local operator set used to evaluate Alpha191 formulas.

Wide-panel convention throughout: ``DataFrame`` indexed by date, columns are
instruments, exactly like the reference factor implementation this screen
consumes (see ``alpha191_local_screen_20260923.py`` for the source note).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import lfilter


def _fir(frame: pd.DataFrame, weights: np.ndarray) -> pd.DataFrame:
    """FIR filter along the date axis (weights newest last)."""
    values = frame.to_numpy(dtype="float64")
    out = lfilter(weights[::-1], [1.0], values, axis=0)
    n = len(weights)
    out[: n - 1] = np.nan
    return pd.DataFrame(out, index=frame.index, columns=frame.columns)


def RANK(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True)


def IFELSE(condition: pd.DataFrame, a, b):
    if isinstance(a, pd.DataFrame):
        return a.where(condition, b)
    if isinstance(b, pd.DataFrame):
        return b.where(~condition, a)
    raise ValueError("IFELSE needs at least one DataFrame branch")


def COUNT(condition: pd.DataFrame, n: int, na_map: pd.DataFrame | None = None) -> pd.DataFrame:
    counted = condition.astype(float)
    if na_map is not None:
        counted = counted + na_map
    return counted.rolling(n).sum()


def SMA(frame: pd.DataFrame, n: int, m: int, ignore_nan: bool = True) -> pd.DataFrame:
    return frame.ewm(alpha=m / n, ignore_na=ignore_nan).mean()


def WMA(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    weights = np.arange(1, n + 1, dtype="float64")
    return _fir(frame, weights / weights.sum())


def DECAYLINEAR(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    weights = np.array([2 * i / (n * (n + 1)) for i in range(1, n + 1)], dtype="float64")
    return _fir(frame, weights)


def DELTA(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.diff(n)


def DELAY(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.shift(n)


def SUM(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).sum()


def MEAN(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).mean()


def STD(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).std()


def CORR(a: pd.DataFrame, b: pd.DataFrame, n: int) -> pd.DataFrame:
    return a.rolling(n).corr(b)


def COVARIANCE(a: pd.DataFrame, b: pd.DataFrame, n: int, sign: bool = False) -> pd.DataFrame:
    covariance = a.rolling(n).cov(b)
    return np.sign(covariance) if sign else covariance


def MAX(a, b):
    return np.maximum(a, b)


def MIN(a, b):
    return np.minimum(a, b)


def TS_MAX(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).max()


def TS_MIN(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).min()


def TS_RANK(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).rank(pct=True)


def _rolling_distance(frame: pd.DataFrame, n: int, *, mode: str) -> pd.DataFrame:
    """Distance (in bars) to the rolling max/min, 1-based like the reference."""
    values = frame.to_numpy(dtype="float64")
    out = np.full(values.shape, np.nan)
    for start in range(n - 1, len(values)):
        window = values[start - n + 1 : start + 1]
        idx = np.nanargmax(window, axis=0) if mode == "max" else np.nanargmin(window, axis=0)
        out[start] = n - idx
    return pd.DataFrame(out, index=frame.index, columns=frame.columns)


def HIGHDAY(frame: pd.DataFrame, n: int, zero_diff: bool = False) -> pd.DataFrame:
    return _rolling_distance(frame, n, mode="max") - int(zero_diff)


def LOWDAY(frame: pd.DataFrame, n: int, zero_diff: bool = False) -> pd.DataFrame:
    return _rolling_distance(frame, n, mode="min") - int(zero_diff)


def SHARPE(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    return frame.rolling(n).mean() / (frame.rolling(n).std() + 1e-7)


def REGBETA(x: pd.DataFrame, y: pd.DataFrame, n: int) -> pd.DataFrame:
    return x.rolling(n).cov(y) / x.rolling(n).var()


def REGRESI(x: pd.DataFrame, y: pd.DataFrame, n: int) -> pd.DataFrame:
    return x.rolling(n).mean() - y.rolling(n).mean() * REGBETA(x, y, n)


def SUMIF(condition: pd.DataFrame, value: pd.DataFrame, n: int) -> pd.DataFrame:
    return IFELSE(condition, value, 0.0).rolling(n).sum()


def SEQUENCE(n: int, index: pd.Index, columns: pd.Index) -> pd.DataFrame:
    values = np.tile(np.arange(1, n + 1, dtype="float64")[:, None], (1, len(columns)))
    padded = np.full((len(index), len(columns)), np.nan)
    padded[-n:] = values
    return pd.DataFrame(padded, index=index, columns=columns)


OPS = dict(
    RANK=RANK, IFELSE=IFELSE, COUNT=COUNT, SMA=SMA, WMA=WMA, DECAYLINEAR=DECAYLINEAR,
    DELTA=DELTA, DELAY=DELAY, SUM=SUM, MEAN=MEAN, STD=STD, CORR=CORR, COVARIANCE=COVARIANCE,
    MAX=MAX, MIN=MIN, TS_MAX=TS_MAX, TS_MIN=TS_MIN, TS_RANK=TS_RANK, HIGHDAY=HIGHDAY,
    LOWDAY=LOWDAY, SHARPE=SHARPE, REGBETA=REGBETA, REGRESI=REGRESI, SUMIF=SUMIF,
    SEQUENCE=SEQUENCE,
)


# --------------------------------------------------------------------------
# qlib-style rolling regression helpers used by a handful of Alpha191 entries
# --------------------------------------------------------------------------
def _rolling_regression(values: np.ndarray, n: int, kind: str) -> np.ndarray:
    values = np.asarray(values, dtype="float64")
    out = np.full(values.shape, np.nan)
    x = np.arange(1, n + 1, dtype="float64")
    x_centered = x - x.mean()
    x_var = (x_centered**2).sum()
    for start in range(n - 1, len(values)):
        y = values[start - n + 1 : start + 1]
        if np.isnan(y).any():
            continue
        y_centered = y - y.mean()
        slope = float((x_centered * y_centered).sum() / x_var)
        intercept = float(y.mean() - slope * x.mean())
        if kind == "slope":
            out[start] = slope
        elif kind == "intercept":
            out[start] = intercept
        elif kind == "rsquare":
            fitted = intercept + slope * x
            ss_res = float(((y - fitted) ** 2).sum())
            ss_tot = float((y_centered**2).sum())
            out[start] = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        elif kind == "resi":
            out[start] = float((y - fitted)[-1])
        else:  # pragma: no cover - defensive
            raise ValueError(kind)
    return out


def rolling_slope(values: np.ndarray, n: int) -> np.ndarray:
    return _rolling_regression(values, n, "slope")


def rolling_rsquare(values: np.ndarray, n: int) -> np.ndarray:
    return _rolling_regression(values, n, "rsquare")


def rolling_resi(values: np.ndarray, n: int) -> np.ndarray:
    return _rolling_regression(values, n, "resi")


def expanding_slope(values: np.ndarray, n: int) -> np.ndarray:
    return _rolling_regression(values, n, "slope")


def expanding_rsquare(values: np.ndarray, n: int) -> np.ndarray:
    return _rolling_regression(values, n, "rsquare")


def expanding_resi(values: np.ndarray, n: int) -> np.ndarray:
    return _rolling_regression(values, n, "resi")
