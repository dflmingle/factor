# -*- coding: utf-8 -*-
"""Panel-only literature legs (2026-10-05, zero platform compute).

Legs re-derivable from qfq daily panels alone (no financial store):
    retvol36 = -std(36m monthly returns), causal (drops the running month)
    ivol250  = -sqrt(residual var vs equal-weight market, 250d window)
    turn250  = -mean(turnover, 250d)

Signs are pre-oriented so that higher = better (direction is still auto-checked
by the ledger engine via rank IC).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_paper_legs(panels: dict) -> dict:
    C = panels["close"].astype("float64")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float64")
    ret1 = C.pct_change(fill_method=None)
    out: dict[str, pd.DataFrame] = {}

    # RETVOL36: 36-month monthly-return volatility, negative (paper VOL 3Y)
    month_close = C.resample("ME").last()
    mret = month_close.pct_change(fill_method=None)
    rv36 = mret.rolling(36).std().shift(1)
    out["retvol36"] = (-rv36.reindex(C.index, method="ffill")).astype("float32")

    # IVOL250: idiosyncratic vol vs equal-weight market, 250d, negative
    mkt = ret1.mean(axis=1)
    w = 250
    mi = ret1.rolling(w).mean()
    mm = mkt.rolling(w).mean()
    mii = (ret1 * ret1).rolling(w).mean()
    mim = ret1.mul(mkt, axis=0).rolling(w).mean()
    mmm = (mkt * mkt).rolling(w).mean()
    var_i = mii - mi * mi
    cov = mim.sub(mi.mul(mm, axis=0))
    var_m = mmm - mm * mm
    beta = cov.div(var_m, axis=0)
    resid = var_i - beta * cov
    out["ivol250"] = (-np.sqrt(resid.clip(lower=0.0))).astype("float32")
    del mi, mm, mii, mim, mmm, var_i, cov, var_m, beta, resid

    # TURN250: 250d mean turnover level, negative
    out["turn250"] = (-T.rolling(250).mean()).astype("float32")
    return out


def build_all(panels: dict) -> dict:
    return build_paper_legs(panels)