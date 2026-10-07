# -*- coding: utf-8 -*-
"""Literature-leg pre-screen (2026-10-05, zero platform compute).

Candidates from Jansen, Swinkels & Zhou (2021), "Anomalies in the China A-share
market", Pacific-Basin Finance Journal 68, 101607:
    EP        = ratio_ep_ttm   (TTM net income / total mcap)
    SP        = ratio_sp_ttm   (TTM revenue / total mcap)
    RETVOL36  = -std(36m monthly returns)                 [paper VOL 3Y]
    IVOL250   = -sqrt(residual var, market model, 250d)   [paper IVOL]
    TURN250   = -mean(turnover, 250d)                     [paper TURN]
    INVASSET  = total asset growth YoY                    [paper INV ASSET]

Conventions identical to scripts/_fundamental_prelim_20261003.py and
scripts/_technical_prelim_20261003.py:
  RankIC series : ed.rank_ic_stats (cycle 10, label_offset 1, best direction)
  s_i           : |mean RankIC| * |ICIR| * win(|IC| > 0.02)
  churn proxy   : top-decile name turnover per signal date
  corr_size     : cross-sectional Spearman vs total_mv

Extra: cross-sectional Spearman vs the 5 incumbent seats and vs representative
existing legs (log size / vol-of-volume / return dispersion / amount / amihud /
turnover level).

Output: research_reports/platform_alignment/literature-legs-20261005/
Usage:
  D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts/_paper_legs_screen_20261005.py
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

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
T0 = time.time()

# reference: local seat s_i mean (matches ed.MEAN_S_LOCAL) and platform-measured peers
MEAN_S_LOCAL = ed.MEAN_S_LOCAL
PLAT_SI = {"K10": 0.0673, "K20": 0.0527, "TOPMIX": 0.0610, "STD20": 0.0557,
           "AMTDISP": 0.0505, "size_only": 0.00914, "impact60": 0.01798,
           "t10_size_plus_impact_bm": 0.05927, "book_to_market_lf_minus_size": 0.02101,
           "book_to_market_lf_plus_impact": 0.02207}


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


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
    original_daily_panel = store._daily_panel

    def _daily_panel(column, *, fill="none"):
        if column == "total_mv":
            return mcap.copy()
        if column == "circ_mv":
            return np.full_like(mcap, np.nan)
        return original_daily_panel(column, fill=fill)

    store._daily_panel = _daily_panel
    return store


def churn_and_size(signal: pd.DataFrame, mcap_signal: pd.DataFrame):
    tops, sizes = [], []
    previous = None
    for date in signal.index:
        row = signal.loc[date]
        valid = row.notna()
        if valid.sum() < 500:
            continue
        ranks = row[valid].rank(pct=True)
        top = set(ranks.index[ranks > 0.9])
        if not top:
            continue
        if previous is not None:
            tops.append(1.0 - len(top & previous) / len(top))
        previous = top
        cap = mcap_signal.loc[date]
        both = valid & cap.notna()
        if int(both.sum()) >= 500:
            a = row[both].rank().to_numpy()
            b = cap[both].rank().to_numpy()
            sizes.append(float(np.corrcoef(a, b)[0, 1]))
    return (float(np.mean(tops)) if tops else np.nan,
            float(np.mean(sizes)) if sizes else np.nan)


def measure(name, arr_eval, market, stocks, signal_dates, positions, mcap_signal):
    finite = float(np.isfinite(arr_eval).mean())
    if finite < 0.1:
        return dict(field=name, direction=0, finite=finite, rank_ic=np.nan,
                    ic_ir=np.nan, win=np.nan, s_i=0.0, churn=np.nan,
                    corr_size=np.nan, recent_ic=np.nan)
    values = torch.from_numpy(np.asarray(arr_eval, dtype=np.float32).copy())
    with torch.no_grad():
        stats = ed.rank_ic_stats(market.context, values)
        stats_neg = ed.rank_ic_stats(market.context, -values)
    chosen = 1
    if not stats or (stats_neg and stats_neg["rank_ic"] > stats["rank_ic"]):
        stats, chosen = stats_neg, -1
    if not stats:
        return None
    signal = pd.DataFrame(np.asarray(arr_eval, dtype=np.float32)[positions],
                          index=signal_dates, columns=stocks)
    if chosen == -1:
        signal = -signal
    churn, corr_size = churn_and_size(signal, mcap_signal)
    with torch.no_grad():
        rstats = ed.rank_ic_stats(market.context, values if chosen == 1 else -values,
                                  start=pd.Timestamp("2026-01-01"))
    recent_ic = float(rstats["rank_ic"]) if rstats else np.nan
    return dict(field=name, direction=chosen, finite=finite, rank_ic=stats["rank_ic"],
                ic_ir=stats["rank_ic_ir"], win=stats["rank_ic_win"], s_i=stats["s_i_rank"],
                churn=churn, corr_size=corr_size, recent_ic=recent_ic)


def per_date_spearman(a: pd.DataFrame, b: pd.DataFrame, min_n: int = 300) -> float:
    """Mean cross-sectional Spearman between two date x stock panels."""
    vals = []
    for date in a.index:
        row_a = a.loc[date]
        row_b = b.loc[date] if date in b.index else None
        if row_b is None:
            continue
        mask = row_a.notna() & row_b.notna()
        if int(mask.sum()) < min_n:
            continue
        ra = row_a[mask].rank().to_numpy()
        rb = row_b[mask].rank().to_numpy()
        vals.append(float(np.corrcoef(ra, rb)[0, 1]))
    return float(np.mean(vals)) if vals else np.nan


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    log("loading seat payload + market ...")
    payload = pickle.load(open(ed.DEFAULT_REBUILD, "rb"))
    market = ed.Market(payload, torch.device("cpu"))
    panels = pickle.load(PANELS.open("rb"))
    log("panels ready")

    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]
    positions = list(market.context.signal_data_positions)
    signal_dates = [pd.Timestamp(d) for d in market.dates]
    log(f"eval_dates {len(eval_dates)} stocks {len(stocks)} signal_dates {len(signal_dates)}")

    store = build_store(market, panels)

    mcap_signal = pd.DataFrame(
        panels["mcap"].reindex(index=eval_dates, columns=stocks).to_numpy()[positions],
        index=signal_dates, columns=stocks)

    C = panels["close"].astype("float64")
    V = panels["volume"].astype("float64")
    A = panels["amount"].astype("float64")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float64")
    ret1 = C.pct_change(fill_method=None)

    def to_eval(panel: pd.DataFrame) -> pd.DataFrame:
        return panel.reindex(index=eval_dates, columns=stocks).astype("float32")

    arrs: dict[str, object] = {}

    # --- EP / SP from platform field catalog (financial as-of, PIT) ---
    for fld, tag in (("ratio_ep_ttm", "EP"), ("ratio_sp_ttm", "SP")):
        try:
            arrs[tag] = np.asarray(store._named_array(fld), dtype=np.float32)
            log(f"{tag} array ok ({fld})")
        except Exception as exc:  # noqa: BLE001
            log(f"{tag} array fail: {type(exc).__name__}: {exc}")

    # --- RETVOL36: 36-month monthly return vol, causal (drop current month) ---
    log("building RETVOL36 ...")
    month_close = C.resample("ME").last()
    mret = month_close.pct_change(fill_method=None)
    rv36 = mret.rolling(36).std().shift(1)
    rv36_daily = rv36.reindex(C.index, method="ffill")
    arrs["RETVOL36"] = to_eval(-rv36_daily).to_numpy()

    # --- IVOL250: residual vol vs equal-weight market over 250d ---
    log("building IVOL250 ...")
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
    ivol = np.sqrt(resid.clip(lower=0.0))
    arrs["IVOL250"] = to_eval(-ivol).to_numpy()
    del mi, mm, mii, mim, mmm, var_i, cov, var_m, beta, resid, ivol

    # --- TURN250: 250d mean turnover ---
    log("building TURN250 ...")
    arrs["TURN250"] = to_eval(-T.rolling(250).mean()).to_numpy()

    # --- INVASSET: total asset growth YoY (PIT quarterly panel) ---
    log("building INVASSET ...")
    try:
        ta = pd.DataFrame(np.asarray(store._named_array("bs_total_assets"), dtype=np.float32),
                          index=eval_dates, columns=stocks)
        ta = ta.where(ta != 0.0)
        growth = (ta / ta.shift(250) - 1.0).astype("float32")
        arrs["INVASSET"] = growth.to_numpy()
        log("INVASSET array ok (bs_total_assets)")
    except Exception as exc:  # noqa: BLE001
        log(f"INVASSET array fail: {type(exc).__name__}: {exc}")

    # --- representative existing legs for overlap check ---
    fam_legs = {
        "size_logmv": to_eval(np.log(panels["mcap"].reindex(index=eval_dates, columns=stocks))),
        "volvol_vs250": to_eval(-(V.rolling(6).std() / V.rolling(250).std())),
        "retdisp_rstd20_60": to_eval(-(ret1.rolling(20).std() / ret1.rolling(60).std())),
        "amt60": to_eval(-A.rolling(60).mean()),
        "amihud20": to_eval(-(ret1.abs() / A).rolling(20).mean()),
        "turn_lvl": to_eval(-T),
    }
    fam_legs = {k: v.reindex(index=eval_dates, columns=stocks) for k, v in fam_legs.items()}

    seats = payload["scores"][ed.POOL].copy()
    seats.index = pd.MultiIndex.from_frame(payload["signal_frame"][["date", "instrument"]])

    rows = []
    corr_rows = []
    for tag in ["EP", "SP", "RETVOL36", "IVOL250", "TURN250", "INVASSET"]:
        if tag not in arrs:
            log(f"{tag} skipped (no array)")
            continue
        arr = arrs[tag]
        res = measure(tag, arr, market, stocks, signal_dates, positions, mcap_signal)
        if res is None:
            log(f"{tag} no stats")
            continue
        signal = pd.DataFrame(np.asarray(arr, dtype=np.float32)[positions],
                              index=signal_dates, columns=stocks)
        if res["direction"] == -1:
            signal = -signal
        # correlation vs seats (aligned by MultiIndex)
        flat = pd.Series(np.asarray(arr, dtype=np.float32)[positions].ravel(),
                         index=pd.MultiIndex.from_arrays(
                             [np.repeat(np.array(signal_dates), len(stocks)),
                              np.tile(np.array(stocks), len(signal_dates))]))
        seat_al = seats.reindex(flat.index)
        corrs = {}
        for col in ed.POOL:
            s = pd.DataFrame({"c": flat.to_numpy(), "s": seat_al[col].to_numpy()},
                             index=np.arange(len(flat)))
            # per signal date spearman
            vals = []
            n = len(stocks)
            cv = s["c"].to_numpy().reshape(len(signal_dates), n)
            sv = s["s"].to_numpy().reshape(len(signal_dates), n)
            for i in range(len(signal_dates)):
                m = np.isfinite(cv[i]) & np.isfinite(sv[i])
                if m.sum() < 300:
                    continue
                vals.append(float(np.corrcoef(pd.Series(cv[i][m]).rank(),
                                              pd.Series(sv[i][m]).rank())[0, 1]))
            corrs[col] = float(np.mean(vals)) if vals else np.nan
        fam_corrs = {k: per_date_spearman(signal, v) for k, v in fam_legs.items()}
        res.update({f"corr_{k}": v for k, v in corrs.items()})
        res.update({f"corr_{k}": v for k, v in fam_corrs.items()})
        res["max_abs_corr_seat"] = float(np.nanmax(np.abs(list(corrs.values()))))
        res["max_abs_corr_fam"] = float(np.nanmax(np.abs(list(fam_corrs.values()))))
        rows.append(res)
        for k, v in list(corrs.items()) + list(fam_corrs.items()):
            corr_rows.append(dict(candidate=tag, other=k, spearman=v))
        log(f"[{tag}] dir={res['direction']:+d} ic={res['rank_ic']:+.4f} ir={res['ic_ir']:+.3f} "
            f"win={res['win']:.2f} s_i={res['s_i']:.4f} churn={res['churn']:.3f} "
            f"corr_size={res['corr_size']:+.2f} recent_ic={res['recent_ic']:+.4f} "
            f"maxCorrSeat={res['max_abs_corr_seat']:.2f} maxCorrFam={res['max_abs_corr_fam']:.2f}")

    frame = pd.DataFrame(rows).sort_values("s_i", ascending=False)
    frame.to_csv(OUT / "paper_legs_screen.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(corr_rows).to_csv(OUT / "paper_legs_corr.csv", index=False, encoding="utf-8-sig")
    meta = {"mean_s_local_reference": MEAN_S_LOCAL, "plat_si": PLAT_SI,
            "gate_s_i": [0.035, 0.045], "gate_churn": 0.15,
            "eval_dates": len(eval_dates), "signal_dates": len(signal_dates),
            "stocks": len(stocks), "window": [str(eval_dates[0].date()), str(eval_dates[-1].date())]}
    (OUT / "screen_meta.json").write_text(
        __import__("json").dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    pd.set_option("display.width", 300)
    print("\n== literature-leg pre-screen (6 candidates vs 5 incumbent seats) ==")
    cols = ["field", "direction", "rank_ic", "ic_ir", "win", "s_i", "churn",
            "corr_size", "recent_ic", "max_abs_corr_seat", "max_abs_corr_fam"]
    print(frame[cols].round(4).to_string(index=False))
    print(f"\nreference: local seat s_i mean = {MEAN_S_LOCAL:.5f}; "
          f"platform peers K10 .0673 / K20 .0527 / STD20 .0557 / AMTDISP .0505")
    print(f"gates: s_i >= 0.035~0.045 AND churn <= 0.15  -> written {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())