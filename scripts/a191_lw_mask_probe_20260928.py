"""Alpha191-LW 掩码探针（2026-09-28，本地零平台算力）。

假说：对手四个未解目标的本地 IC 已接近、但 ICIR/win 系统性低 ~.3；
      若其因子只在更干净的子集上有值（长窗相乘/规模阈值 → 天然 NaN 掩码），
      则掩码会同时抬高 IC 与 ICIR。

做法：base 信号 × 逐日股票池掩码 × 目标三元组，一次跑完。
用法：python scripts/a191_lw_mask_probe_20260928.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
OUT = ROOT / "research_reports/platform_alignment/a191-lw-crack-20260928"

TARGETS = [
    dict(tag="010_LW", ic=0.1253, icir=0.980, win=0.798, start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="120_LW", ic=0.1021, icir=0.826, win=0.765, start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="140_LW", ic=0.0653, icir=0.845, win=0.731, start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="042_forests", ic=0.0957, icir=0.975, win=0.773, start="2021-09-15", end="2026-08-04", cycle=10),
]
HOME = {"010v_official": "010_LW", "010v_tsmax5": "010_LW", "volstabV20": "010_LW",
        "042ref": "042_forests", "042stab": "042_forests",
        "120ref_lowturn": "120_LW", "140ref_lowturn": "140_LW",
        "lowturn": "120_LW", "tmaratio": "140_LW"}


def load_panels() -> dict:
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    return {k: v.astype("float32") for k, v in panels.items()}


def schedule(cal, start, end, cycle):
    lo = int(cal.searchsorted(pd.Timestamp(start), side="left"))
    hi = int(cal.searchsorted(pd.Timestamp(end), side="right")) - 1
    return [cal[i] for i in range(lo, hi + 1, cycle)]


def cs_rank(df):
    return df.rank(axis=1, pct=True)


def triplet(values, mask, close, cal, sched, cycle):
    ics = []
    for date in sched:
        i = cal.get_loc(date)
        if i + 1 + cycle >= len(cal):
            continue
        y = (close.iloc[i + 1 + cycle].to_numpy("float64") / close.iloc[i + 1].to_numpy("float64") - 1.0)
        x = values.iloc[i].to_numpy("float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if mask is not None:
            ok &= mask.iloc[i].to_numpy(bool)
        if ok.sum() < 100:
            continue
        xr = pd.Series(x[ok]).rank().to_numpy()
        yr = pd.Series(y[ok]).rank().to_numpy()
        if xr.std() == 0 or yr.std() == 0:
            continue
        ics.append(float(np.corrcoef(xr, yr)[0, 1]))
    s = np.array(ics)
    s = s[np.isfinite(s)]
    if len(s) < 30:
        return dict(n=len(s), ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan)
    mean = float(s.mean())
    sd = float(s.std(ddof=1))
    sign = 1.0 if mean >= 0 else -1.0
    icir = abs(mean) / sd if sd > 0 else 0.0
    win = float(np.mean(s * sign > 0.02))
    return dict(n=len(s), ic=abs(mean), icir=icir, win=win, s_i=abs(mean) * icir * win)


def main() -> int:
    panels = load_panels()
    C = panels["close"]
    cal = C.index
    V, A, O, H, L, T = (panels[k] for k in ("volume", "amount", "open", "high", "low", "turnover"))
    MV = panels["total_mv"]
    ret1 = C.pct_change(fill_method=None)
    vwap = A * 10.0 / V

    print("building bases ...", flush=True)
    bases = {}
    # --- 010 家族 ---
    lo20 = np.log(V + 1.0).rolling(20).std()          # 对数波动，避开量级差
    bases["010v_official"] = np.maximum((ret1.rolling(20).std().where(ret1 < 0, C)) ** 2, 5.0).pipe(cs_rank)
    bases["010v_tsmax5"] = ((ret1.rolling(20).std().where(ret1 < 0, C)) ** 2).rolling(5).max().pipe(cs_rank)
    bases["010v_lrstd"] = cs_rank(ret1.rolling(20).std()).where(ret1 < 0, cs_rank(C))
    # --- 波动稳定性（P0P1 结论） ---
    bases["volstabV20"] = -((V.rolling(20).std() / V.rolling(1250, min_periods=400).std()).pipe(cs_rank))
    bases["volstabT20"] = -((T.rolling(20).std() / T.rolling(1250, min_periods=400).std()).pipe(cs_rank))
    bases["volstablogV"] = -(lo20 / np.log(V + 1.0).rolling(1250, min_periods=400).std()).pipe(cs_rank)
    # --- 低换手 / 换手反转 ---
    bases["lowturn"] = 1.0 - cs_rank(T)
    bases["tmaratio"] = -(T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()).pipe(cs_rank)
    # --- 官方 120 / 140 ---
    a120 = cs_rank(vwap - C) / cs_rank(vwap + C)
    bases["120ref_lowturn"] = (a120.rolling(20).mean() * (1.0 - cs_rank(T)))
    # 140 简化版（第一支路 DECAYLINEAR(rank组合,8) × 低换手，取负）
    d8 = ((cs_rank(O) + cs_rank(L)) - (cs_rank(H) + cs_rank(C))).rolling(8).apply(
        lambda x: (x * np.arange(1, 9)).sum() / np.arange(1, 9).sum(), raw=True)
    bases["140ref_lowturn"] = cs_rank(d8) * (1.0 - cs_rank(T)) * -1.0
    # --- 042 ---
    std10 = H.rolling(10).std().pipe(cs_rank)
    corr10 = H.astype("float64").rolling(10).corr(V.astype("float64"))
    bases["042ref"] = -(std10 * corr10)
    bases["042stab"] = -((H.rolling(10).std() / H.rolling(1250, min_periods=400).std()).pipe(cs_rank) * corr10)

    print("building masks ...", flush=True)
    n = C.notna().cumsum()
    mv_rank = cs_rank(MV)
    amt20 = A.rolling(20).mean()
    amt_rank = cs_rank(amt20)
    masks = {
        "all": None,
        "mv70": mv_rank <= 0.70,
        "mv50": mv_rank <= 0.50,
        "mv30": mv_rank <= 0.30,
        "px5": C >= 5.0,
        "px10": C >= 10.0,
        "amt70": amt_rank <= 0.70,
        "h250": n >= 250,
        "h750": n >= 750,
        "mv50_amt70": (mv_rank <= 0.50) & (amt_rank <= 0.70),
        "mv70_h250": (mv_rank <= 0.70) & (n >= 250),
    }

    rows = []
    for bname, vals in bases.items():
        tg = HOME.get(bname)
        for t in TARGETS:
            sched = schedule(cal, t["start"], t["end"], t["cycle"])
            for mname, m in masks.items():
                st = triplet(vals, m, C, cal, sched, t["cycle"])
                d_ic = st["ic"] - t["ic"]
                mark = ""
                if tg == t["tag"] and abs(d_ic) <= 0.005:
                    mark = "  <== HIT(ic)"
                rows.append(dict(base=bname, mask=mname, target=t["tag"], home=tg == t["tag"], **st, d_ic=d_ic,
                                 d_icir=st["icir"] - t["icir"], d_win=st["win"] - t["win"]))
                if tg == t["tag"] or mark:
                    print("%-16s %-11s %-12s n=%3d ic=%.4f icir=%.3f win=%.3f s_i=%.4f | d=%+.4f/%+.3f/%+.3f%s" % (
                        bname, mname, t["tag"], st["n"], st["ic"], st["icir"], st["win"], st["s_i"],
                        d_ic, st["icir"] - t["icir"], st["win"] - t["win"], mark), flush=True)
        del vals
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "mask_probe.csv", index=False, encoding="utf-8-sig")
    print(f"\nwrote {OUT / 'mask_probe.csv'} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
