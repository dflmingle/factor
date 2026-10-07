# -*- coding: utf-8 -*-
"""Paper-convention replication check for the Jansen/Swinkels/Zhou (2021) legs.

Question: our scoring convention (cycle-10 Top20 rank IC, s_i = |IC|x|ICIR|xwin)
says 0/6.  Is that because the anomaly is dead in 2021-09..2026-08 A-shares, or
because our convention is different from the paper's?

Paper convention replicated here:
  - monthly rebalance, portfolios formed at month-end t, held one month
  - equal-weighted decile long-short: EW(top decile) - EW(bottom decile)
  - universe excludes the smallest 30% by total market cap (shell-value guard)
  - report mean monthly L/S (%) and a simple t-stat

Also runs the same deciles on: full universe (no size cut), and a log-size
sanity anchor (small-minus-big should be strongly positive in A-shares).

Output: research_reports/platform_alignment/literature-legs-20261005/
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\factor")
sys.path.insert(0, str(ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import e_decomp_20260928 as ed  # noqa: E402
import alphaprobe_gp_tushare as gp  # noqa: E402
from pandaai_fields_local import PandaAIFieldStore  # noqa: E402

ed.DEFAULT_REBUILD = (ROOT / "research_reports" / "platform_alignment"
                      / "ab-batch-20260925" / "seat_panels_rebuilt.pkl")
PANELS = ROOT / "research_reports" / "platform_alignment" / "e-decomp-20260929" / "panels_cache.pkl"
OUT = ROOT / "research_reports" / "platform_alignment" / "literature-legs-20261005"
ARRAYS = OUT / "paper_legs_arrays.pkl"
T0 = time.time()

WIN_START = pd.Timestamp("2021-09-01")
WIN_END = pd.Timestamp("2026-08-31")
# paper-reported EW decile L/S, monthly %, in the direction "high factor -> high return"
PAPER = {"EP": 1.10, "SP": 0.93, "RETVOL36": 0.90, "IVOL250": 1.19,
         "TURN250": 0.88, "INVASSET": 0.55}


def log(m: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)


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
    frame = pd.DataFrame({"date": [], "instrument": [], "total_mv": []})
    store = PandaAIFieldStore(data=stub, frame=frame, financial_root=gp.DEFAULT_FINANCIAL_ROOT,
                              max_cached_fields=2, max_cached_arrays=64)
    mcap = panels["mcap"].reindex(index=eval_dates, columns=stub._stock_ids).to_numpy(dtype=np.float32)
    original = store._daily_panel

    def _daily_panel(column, *, fill="none"):
        if column == "total_mv":
            return mcap.copy()
        if column == "circ_mv":
            return np.full_like(mcap, np.nan)
        return original(column, fill=fill)

    store._daily_panel = _daily_panel
    return store


def build_arrays(panels, store, eval_dates, stocks):
    C = panels["close"].astype("float64")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float64")
    ret1 = C.pct_change(fill_method=None)

    def to_eval(p):
        return p.reindex(index=eval_dates, columns=stocks).astype("float32")

    arrs = {}
    for fld, tag in (("ratio_ep_ttm", "EP"), ("ratio_sp_ttm", "SP")):
        arrs[tag] = np.asarray(store._named_array(fld), dtype=np.float32)

    month_close = C.resample("ME").last()
    mret = month_close.pct_change(fill_method=None)
    rv36 = mret.rolling(36).std().shift(1)
    arrs["RETVOL36"] = to_eval(-rv36.reindex(C.index, method="ffill")).to_numpy()

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
    arrs["IVOL250"] = to_eval(-np.sqrt(resid.clip(lower=0.0))).to_numpy()

    arrs["TURN250"] = to_eval(-T.rolling(250).mean()).to_numpy()

    ta = pd.DataFrame(np.asarray(store._named_array("bs_total_assets"), dtype=np.float32),
                      index=eval_dates, columns=stocks)
    ta = ta.where(ta != 0.0)
    arrs["INVASSET"] = (ta / ta.shift(250) - 1.0).astype("float32").to_numpy()
    arrs["_logmv"] = to_eval(np.log(panels["mcap"])).to_numpy()
    return arrs


def month_ends(index):
    s = pd.Series(index, index=index)
    return list(s.groupby([s.index.year, s.index.month]).last())


def decile_ls(factor: pd.DataFrame, fwd: pd.DataFrame, mcap: pd.DataFrame,
              exclude_smallest: float, decile: float = 0.10):
    """Return (mean monthly L/S %, t-stat, n_months) for EW top-bottom decile."""
    ls = []
    for t in factor.index:
        f = factor.loc[t]
        r = fwd.loc[t]
        cap = mcap.loc[t]
        ok = f.notna() & r.notna() & cap.notna()
        if exclude_smallest > 0:
            cut = cap[ok].quantile(exclude_smallest)
            ok &= cap >= cut
        if int(ok.sum()) < 100:
            continue
        fv = f[ok]
        rv = r[ok]
        lo = fv.quantile(decile)
        hi = fv.quantile(1.0 - decile)
        top = rv[fv >= hi]
        bot = rv[fv <= lo]
        if len(top) < 10 or len(bot) < 10:
            continue
        ls.append(float(top.mean() - bot.mean()))
    if not ls:
        return np.nan, np.nan, 0
    a = np.asarray(ls)
    t = float(a.mean() / a.std(ddof=1) * np.sqrt(len(a))) if a.std(ddof=1) > 0 else np.nan
    return float(a.mean() * 100.0), t, len(a)


def main() -> int:
    log("loading seat payload + market ...")
    payload = pickle.load(open(ed.DEFAULT_REBUILD, "rb"))
    market = ed.Market(payload, torch_cpu := __import__("torch").device("cpu"))  # noqa: F841
    panels = pickle.load(PANELS.open("rb"))
    log("panels ready")
    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]

    if ARRAYS.exists():
        arrs = pickle.load(ARRAYS.open("rb"))
        log("arrays from cache")
    else:
        store = build_store(market, panels)
        arrs = build_arrays(panels, store, eval_dates, stocks)
        with ARRAYS.open("wb") as fh:
            pickle.dump(arrs, fh, protocol=5)
        log(f"arrays built -> {ARRAYS}")

    close = panels["close"].reindex(index=eval_dates, columns=stocks).astype("float64")
    mcap = panels["mcap"].reindex(index=eval_dates, columns=stocks).astype("float64")
    me = [d for d in month_ends(close.index) if WIN_START <= d <= WIN_END]
    log(f"month-ends in window: {len(me)} ({me[0].date()}..{me[-1].date()})")

    fwd = pd.DataFrame(index=me, columns=stocks, dtype="float64")
    for i, t in enumerate(me[:-1]):
        t1 = me[i + 1]
        fwd.loc[t] = (close.loc[t1] / close.loc[t] - 1.0).to_numpy()
    fwd = fwd.iloc[:-1]

    rows = []
    for tag in ["EP", "SP", "RETVOL36", "IVOL250", "TURN250", "INVASSET", "_logmv"]:
        if tag not in arrs:
            continue
        fac = pd.DataFrame(arrs[tag], index=eval_dates, columns=stocks).reindex(me)
        fac = fac.reindex(fwd.index)
        for excl, label in ((0.30, "paper(excl 30%)"), (0.0, "full universe")):
            m, t, n = decile_ls(fac, fwd, mcap.reindex(fwd.index), excl)
            rows.append(dict(factor=tag, universe=label, ls_pct=m, t_stat=t, months=n))
            log(f"[{tag}][{label}] L/S={m:+.3f}%/mo t={t:+.2f} n={n}")

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "paper_convention_decile.csv", index=False, encoding="utf-8-sig")

    print("\n== paper-convention monthly decile long-short (EW), window "
          f"{me[0].date()}..{me[-1].date()} ==")
    piv = frame.pivot(index="factor", columns="universe", values=["ls_pct", "t_stat"])
    print(piv.round(3).to_string())
    print("\npaper-reported EW decile L/S for reference (monthly %, high factor -> high return):")
    for k, v in PAPER.items():
        print(f"  {k:<10} +{v:.2f}%")
    print("\nnote: RETVOL36/IVOL250/TURN250 are stored negated (low vol / low turnover = high value),")
    print("      so a POSITIVE L/S here means the paper direction reproduces. INVASSET is stored raw.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())