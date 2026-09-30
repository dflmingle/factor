#!/usr/bin/env python3
"""LEGMIX-NEXT 挖掘（2026-09-29）：按修正标定重挖"平台 ICIR >= .7"族。

修正标定（两条平台实测反推，见 GOAL.md 第 41 条 / legmix-20260928/platform_results.md）：
  - >=6 腿、短窗（<=756 日）复合：本地<->平台校准良好。
    LEGMIX7: 本地 ic .1190 / icir .793 / s_i .0716 -> 平台 icir .846 / 池侧 s_i .0832。
  - 单腿/少腿复合本地 ICIR 系统性虚高（turn x A191: 本地 .80-.88 -> 平台 .55-.59），不可用。
  => 目标族：本地 ICIR >= .66（预期平台 >= .70）的多腿复合，同时压低换手。

本轮核心风险（必须绕开）：
  LEGMIX7 自身换手 56.8%（平台），6 席池换手 24.1%->32.9%，C 段 rawC 每 -0.1 约 -2693 分/月。
  => 目标函数显式含换手惩罚：key = s_i_5y - lam * max(0, turn10 - soft)，lam 扫描。

口径：全 A / qfq / total_mv / label=t+1->t+1+cycle / 10 组 / 0.30% 单边；
      s_i = |mean RankIC| x |RankIC 序列 ICIR| x win(同向 IC > 0.02)。

用法：
  python scripts/legmix_next_mine_20260929.py --lam-turn 0.05 --tag lam005
  python scripts/legmix_next_mine_20260929.py --lam-turn 0.1 --seed legmix7 --tag lam010_seed7
"""
from __future__ import annotations

import argparse
import gc
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legmix_next_legs_20260929 import build_raw_legs, FORMULA  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
OUT = ROOT / "research_reports/platform_alignment/legmix-next-20260929"
CYCLE = 10
W5 = ("2021-09-07", "2026-09-07")
W1 = ("2026-01-01", "2026-09-07")
SEED_LEGMIX7 = ["intr20", "amt60", "maxret20", "retrev5", "pvcorr20", "t_std10_60", "amihud20"]
T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


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
        cur = set(np.argpartition(-np.nan_to_num(x.to_numpy("float64"), nan=-np.inf), k)[:k].tolist())
        if prev is not None:
            chg.append(1.0 - len(cur & prev) / k)
        prev = cur
    return float(np.mean(chg)) if chg else float("nan")


def turn_proxy(values: pd.DataFrame, sched: list, idx: dict) -> float:
    sub = values.iloc[[idx[d] for d in sched]]
    r = sub.rank(axis=1, pct=True)
    d = r.diff().abs().to_numpy("float64")
    return float(np.nanmean(d))


def corr_size(values: pd.DataFrame, sched: list, idx: dict, cap: pd.DataFrame) -> float:
    cs = []
    for date in sched:
        x = values.iloc[idx[date]].to_numpy("float64")
        b = cap.iloc[idx[date]].to_numpy("float64")
        m = np.isfinite(x) & np.isfinite(b)
        if m.sum() >= 200:
            cs.append(float(np.corrcoef(pd.Series(x[m]).rank(), pd.Series(b[m]).rank())[0, 1]))
    return float(np.mean(cs)) if cs else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam-turn", type=float, default=0.0)
    ap.add_argument("--soft-turn", type=float, default=0.30)
    ap.add_argument("--lam-size", type=float, default=0.0, help="|corr_size| 超过 0.45 后的惩罚斜率")
    ap.add_argument("--soft-size", type=float, default=0.45)
    ap.add_argument("--max-legs", type=int, default=16)
    ap.add_argument("--min-improve", type=float, default=1e-5)
    ap.add_argument("--seed", default="", help="legmix7 = 从 LEGMIX7 的 7 腿出发继续贪心")
    ap.add_argument("--exclude", default="", help="逗号分隔，禁用这些腿")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()

    tag = args.tag or f"lam{args.lam_turn:.2f}"
    OUT.mkdir(parents=True, exist_ok=True)

    log("loading panels cache")
    panels = pickle.load(PANELS.open("rb"))
    C = panels["close"]
    cap = panels["mcap"].astype("float32")
    cal = C.index
    idx = {d: i for i, d in enumerate(cal)}

    log("building raw legs")
    raw = build_raw_legs(panels)
    excl = {x.strip() for x in args.exclude.split(",") if x.strip()}
    raw = {k: v for k, v in raw.items() if k not in excl}
    log(f"raw legs: {len(raw)} (excluded {sorted(excl)})")

    w5s, w1s = sched_of(cal, W5), sched_of(cal, W1)
    log(f"schedule 5y={len(w5s)} ({w5s[0].date()}..{w5s[-1].date()}) 1y={len(w1s)}")

    log("ranking + IC 定向")
    legs: dict[str, pd.DataFrame] = {}
    leg_signs: dict[str, float] = {}
    leg_rows = []
    for name, df in raw.items():
        r = df.rank(axis=1, pct=True).astype("float32")
        s5 = ic_series(r, C, cal, w5s, idx)
        mean5 = float(np.nanmean(s5)) if np.isfinite(s5).any() else 0.0
        sign = -1.0 if mean5 < 0 else 1.0
        if sign < 0:
            r = -r
            st = stats(-s5)
        else:
            st = stats(s5)
        leg_signs[name] = sign
        legs[name] = r
        leg_rows.append(dict(leg=name, formula=FORMULA.get(name, ""), **st, turn=turnover_top(r, w5s, idx)))
        log("  leg %-14s ic=%.4f icir=%.3f win=%.3f s_i=%.4f turn=%.3f" % (
            name, st["ic"], st["icir"], st["win"], st["s_i"], leg_rows[-1]["turn"]))
    leg_df = pd.DataFrame(leg_rows).sort_values("s_i", ascending=False)
    leg_df.to_csv(OUT / f"legs_{tag}.csv", index=False, encoding="utf-8-sig")
    log(f"legs table -> {OUT / f'legs_{tag}.csv'}")
    raw = None
    gc.collect()

    names = list(legs)
    selected: list[str] = []
    cur = None
    if args.seed == "legmix7":
        selected = [n for n in SEED_LEGMIX7 if n in legs]
        cur = None
        for n in selected:
            cur = legs[n] if cur is None else cur + legs[n]
        cur = (cur / len(selected)).astype("float32")
        log(f"seed=legmix7 -> {selected}")

    hist = []
    best_prev = -1e9
    for step in range(args.max_legs):
        best = None
        for name in names:
            if name in selected:
                continue
            combo = legs[name] if cur is None else (cur * len(selected) + legs[name]) / (len(selected) + 1)
            st = stats(ic_series(combo, C, cal, w5s, idx))
            t10 = turnover_top(combo, w5s, idx)
            raw_key = st["s_i"] if np.isfinite(st["s_i"]) else -1.0
            key = raw_key - args.lam_turn * max(0.0, t10 - args.soft_turn)
            if best is None or key > best[0]:
                best = (key, name, st, combo, t10, raw_key)
            else:
                del combo
        key, name, st5, combo, t10, raw_key = best
        if key <= best_prev + args.min_improve:
            log(f"stop: no improvement at K={step + 1} (key {key:.5f} <= {best_prev:.5f})")
            del combo
            break
        best_prev = key
        selected.append(name)
        cur = combo.astype("float32")
        s1 = stats(ic_series(cur, C, cal, w1s, idx))
        csz = corr_size(cur, w5s, idx, cap)
        tpx = turn_proxy(cur, w5s, idx)
        row = dict(k=len(selected), added=name, key=key, s_i_5y=st5["s_i"], ic_5y=st5["ic"],
                   icir_5y=st5["icir"], win_5y=st5["win"], n_5y=st5["n"],
                   s_i_1y=s1["s_i"], ic_1y=s1["ic"], icir_1y=s1["icir"], win_1y=s1["win"], n_1y=s1["n"],
                   turn10=t10, turn_proxy=tpx, corr_size=csz,
                   legs="+".join(selected))
        hist.append(row)
        pd.DataFrame(hist).to_csv(OUT / f"{tag}_history.csv", index=False, encoding="utf-8-sig")
        log("K=%2d +%-12s key=%.4f s_i=%.4f (ic %.4f icir %.3f win %.3f) 1y s_i=%.4f | turn10=%.3f proxy=%.4f corr_size=%+.2f" % (
            len(selected), name, key, st5["s_i"], st5["ic"], st5["icir"], st5["win"], s1["s_i"],
            t10, tpx, csz))
        gc.collect()

    specs = dict(tag=tag, lam_turn=args.lam_turn, soft_turn=args.soft_turn, seed=args.seed,
                 excluded=sorted(excl), steps=[
                     dict(k=r["k"], added=r["added"], legs=r["legs"].split("+"),
                          signed={n: leg_signs[n] for n in r["legs"].split("+")},
                          s_i_5y=r["s_i_5y"], icir_5y=r["icir_5y"], turn10=r["turn10"],
                          corr_size=r["corr_size"], s_i_1y=r["s_i_1y"])
                     for r in hist])
    (OUT / f"{tag}_specs.json").write_text(json.dumps(specs, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"selected: {' + '.join(selected)}")
    log(f"wrote {OUT / f'{tag}_specs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
