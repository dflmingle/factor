"""多腿复合贪心挖掘（2026-09-28，本地零平台算力）。

动机：榜单顶部 IC 普遍 .09-.11，分水岭是 ICIR（.8-.98 vs 我们 .5-.7）。
多腿复合是拉 ICIR 的主要手段（对手 G1-raw+41 / E5-a191x3 / P2-a191mix 同型）。
约束：所有腿窗口 ≤ 60 交易日（平台滚动历史起点 ≈ 2021-05-07，长窗会 NaN）。
口径：全 A / qfq / label-1（t+1 → t+1+cycle）；s_i = |IC| × ICIR × win(带符号 IC>0.02)。
用法：python scripts/legmix_mine_20260928.py [--max-legs 14]
"""
from __future__ import annotations

import argparse
import gc
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
OUT = ROOT / "research_reports/platform_alignment/legmix-20260928"
CYCLE = 10
W5 = ("2021-09-07", "2026-09-07")
W1 = ("2026-01-01", "2026-09-07")


def load_panels() -> dict:
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    return {k: v.astype("float32") for k, v in panels.items()}


def sched_of(cal: pd.DatetimeIndex, span) -> list:
    lo = int(cal.searchsorted(pd.Timestamp(span[0]), side="left"))
    hi = int(cal.searchsorted(pd.Timestamp(span[1]), side="right")) - 1
    return list(cal[lo:hi + 1:CYCLE])


def ic_series(values: pd.DataFrame, close: pd.DataFrame, cal: pd.DatetimeIndex,
              sched: list, idx: dict) -> np.ndarray:
    out = np.full(len(sched), np.nan)
    for k, date in enumerate(sched):
        i = idx[date]
        if i + 1 + CYCLE >= len(cal):
            continue
        y = (close.iloc[i + 1 + CYCLE].to_numpy("float64") / close.iloc[i + 1].to_numpy("float64") - 1.0)
        x = values.iloc[i].to_numpy("float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        xr = pd.Series(x[ok]).rank().to_numpy()
        yr = pd.Series(y[ok]).rank().to_numpy()
        if xr.std() == 0 or yr.std() == 0:
            continue
        out[k] = float(np.corrcoef(xr, yr)[0, 1])
    return out


def stats(s: np.ndarray) -> dict:
    s = s[np.isfinite(s)]
    if len(s) < 6:
        return dict(n=len(s), ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan)
    mean = float(s.mean())
    sd = float(s.std(ddof=1))
    sign = 1.0 if mean >= 0 else -1.0
    icir = abs(mean) / sd if sd > 0 else 0.0
    win = float(np.mean(s * sign > 0.02))
    return dict(n=len(s), ic=abs(mean), icir=icir, win=win, s_i=abs(mean) * icir * win)


def turnover_top(values: pd.DataFrame, sched: list, idx: dict, top: float = 0.10) -> float:
    prev = None
    chg = []
    for date in sched:
        x = values.iloc[idx[date]]
        k = max(int(np.isfinite(x).sum() * top), 1)
        if k < 5:
            continue
        cur = set(np.argsort(-np.nan_to_num(x.to_numpy("float64"), nan=-np.inf))[:k])
        if prev is not None:
            chg.append(1.0 - len(cur & prev) / k)
        prev = cur
    return float(np.mean(chg)) if chg else float("nan")


def turn_proxy(values: pd.DataFrame, sched: list, idx: dict) -> float:
    """快速换手代理：每周期间截面秩的平均绝对变化（与 top-decile 换手强相关）。"""
    sub = values.iloc[[idx[d] for d in sched]]
    r = sub.rank(axis=1, pct=True)
    d = r.diff().abs().to_numpy("float64")
    return float(np.nanmean(d))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-legs", type=int, default=14)
    ap.add_argument("--lam-turn", type=float, default=0.0, help="换手惩罚斜率（超出 soft 部分）")
    ap.add_argument("--soft-turn", type=float, default=0.30)
    ap.add_argument("--out", default=str(OUT / "legmix_results.csv"))
    args = ap.parse_args()

    panels = load_panels()
    C = panels["close"]
    cal = C.index
    idx = {d: i for i, d in enumerate(cal)}
    V, A, O, H, L, T = (panels[k] for k in ("volume", "amount", "open", "high", "low", "turnover"))
    vwap = (A * 10.0 / V)
    ret1 = C.pct_change(fill_method=None)
    hl = (H - L) / C
    intr = (C - O) / O
    drift = (C - vwap) / vwap

    def rk(df):
        return df.rank(axis=1, pct=True)

    print("building legs ...", flush=True)
    legs: dict[str, pd.DataFrame] = {}
    def add(name, df):
        legs[name] = rk(df).astype("float32")

    add("t_lvl", -T)
    add("t_ma5", -T.rolling(5).mean())
    add("t_ma20", -T.rolling(20).mean())
    add("t_rel_ma5_60", -(T.rolling(5).mean() / T.rolling(60).mean()))
    add("t_rel_ma20_60", -(T.rolling(20).mean() / T.rolling(60).mean()))
    add("t_std10", -T.rolling(10).std())
    add("t_std20", -T.rolling(20).std())
    add("t_std10_60", -(T.rolling(10).std() / T.rolling(60).std()))
    add("t_std20_60", -(T.rolling(20).std() / T.rolling(60).std()))
    add("v_std10_60", -(V.rolling(10).std() / V.rolling(60).std()))
    add("v_std20_60", -(V.rolling(20).std() / V.rolling(60).std()))
    add("a_std20_60", -(A.rolling(20).std() / A.rolling(60).std()))
    add("v_ma5_60", -(V.rolling(5).mean() / V.rolling(60).mean()))
    add("v_ma20_60", -(V.rolling(20).mean() / V.rolling(60).mean()))
    add("retrev5", -(C / C.shift(5) - 1))
    add("retrev10", -(C / C.shift(10) - 1))
    add("retrev20", -(C / C.shift(20) - 1))
    add("retmom60", C / C.shift(60) - 1)
    add("cstd20", -C.rolling(20).std())
    add("cstd20_60", -(C.rolling(20).std() / C.rolling(60).std()))
    add("retstd20", -ret1.rolling(20).std())
    add("retstd20_60", -(ret1.rolling(20).std() / ret1.rolling(60).std()))
    add("maxret20", -ret1.rolling(20).max())
    add("minret20", -ret1.rolling(20).min())
    add("hl20", -hl.rolling(20).mean())
    add("amp20", -(H.rolling(20).max() / L.rolling(20).min() - 1))
    add("intr5", -intr.rolling(5).mean())
    add("intr20", -intr.rolling(20).mean())
    add("drift5", -drift.rolling(5).mean())
    add("drift20", -drift.rolling(20).mean())
    add("closepos20", -(C - L.rolling(20).min()) / (H.rolling(20).max() - L.rolling(20).min()))
    add("pvcorr20", H.astype("float64").rolling(20).corr(V.astype("float64")).astype("float32"))
    add("vretcorr20", ret1.rolling(20).corr(V.rolling(1).mean()))
    add("amihud20", -(ret1.abs() / A).rolling(20).mean())
    add("amt60", -A.rolling(60).mean())
    add("skew20", -ret1.rolling(20).skew())
    add("downup", -(ret1.where(ret1 < 0, 0.0).rolling(20).std() / ret1.where(ret1 > 0, 0.0).rolling(20).std()))
    add("vdiff", -(V - V.rolling(20).mean()) / V.rolling(20).std())
    add("tdiff", -(T - T.rolling(20).mean()) / T.rolling(20).std())

    w5s, w1s = sched_of(cal, W5), sched_of(cal, W1)
    print(f"legs={len(legs)}  schedule 5y={len(w5s)} 1y={len(w1s)}", flush=True)

    # --- 每腿自评（方向由自身 IC 符号决定，统一翻正） ---
    leg_rows, leg_dir = [], {}
    for name, df in legs.items():
        s5 = ic_series(df, C, cal, w5s, idx)
        st = stats(s5)
        d = 1.0 if st["ic"] and np.isfinite(st["ic"]) and float(np.nanmean(s5)) >= 0 else -1.0
        leg_dir[name] = d
        if d < 0:
            legs[name] = -df  # 反向翻正
            st = stats(-s5 * 0 - s5 * -1) if False else stats(-s5)
        leg_rows.append(dict(leg=name, **st, turn=turnover_top(legs[name], w5s, idx)))
        print("  leg %-16s ic=%.4f icir=%.3f win=%.3f s_i=%.4f" % (
            name, leg_rows[-1]["ic"], leg_rows[-1]["icir"], leg_rows[-1]["win"], leg_rows[-1]["s_i"]), flush=True)

    pd.DataFrame(leg_rows).sort_values("s_i", ascending=False).to_csv(
        OUT / "legs.csv", index=False, encoding="utf-8-sig")

    # --- 贪心前向选择：目标 = 5y s_i（并列时看 1y） ---
    names = list(legs)
    selected: list[str] = []
    cache5, cache1 = {}, {}
    best_hist = []
    cur = None
    for step in range(args.max_legs):
        best = None
        for name in names:
            if name in selected:
                continue
            combo = legs[name] if cur is None else (cur * len(selected) + legs[name]) / (len(selected) + 1)
            s5 = cache5.get(tuple(sorted(selected + [name])))
            if s5 is None:
                s5 = ic_series(combo, C, cal, w5s, idx)
            st = stats(s5)
            tp = turn_proxy(combo, w5s, idx)
            raw = st["s_i"] if np.isfinite(st["s_i"]) else -1.0
            key = raw - args.lam_turn * max(0.0, tp - args.soft_turn)
            if best is None or key > best[0]:
                s1 = ic_series(combo, C, cal, w1s, idx)
                best = (key, name, st, stats(s1), combo, s5, tp, raw)
            del combo
        key, name, st5, st1, combo, s5, tp, raw = best
        if best_hist and key <= best_hist[-1][0] + 1e-5:
            print(f"stop: no improvement at K={step + 1} (best {key:.4f})", flush=True)
            break
        selected.append(name)
        cur = combo
        best_hist.append((raw, name, st5, st1))
        print("K=%2d +%-16s 5y s_i=%.4f (ic %.4f icir %.3f win %.3f) | 1y s_i=%.4f turn10=%.3f proxy=%.4f" % (
            len(selected), name, st5["s_i"], st5["ic"], st5["icir"], st5["win"], st1["s_i"],
            turnover_top(cur, w5s, idx), tp), flush=True)
        gc.collect()

    rows = []
    for k in range(1, len(best_hist) + 1):
        key, name, st5, st1 = best_hist[k - 1]
        rows.append(dict(k=k, leg=name, s_i_5y=st5["s_i"], ic_5y=st5["ic"], icir_5y=st5["icir"],
                         win_5y=st5["win"], n_5y=st5["n"], s_i_1y=st1["s_i"], ic_1y=st1["ic"],
                         icir_1y=st1["icir"], win_1y=st1["win"], n_1y=st1["n"]))
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print("\nselected legs:", " + ".join(selected))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
