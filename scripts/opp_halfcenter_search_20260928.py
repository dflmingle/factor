#!/usr/bin/env python3
"""对手因子"半厘米"精配搜索（2026-09-28，本地零平台算力）。

对高价值对手目标，在「基底 × 波动/换手稳定性 × 混权 w」空间做 step=0.05 细网格
（P0 只有 step=0.1 × 5 LT），找出比签名地图更进一步接近目标的构造。

v = w * rank(base_signed) + (1-w) * rank(stab_signed)，两秩都在 0~1。
基底：010/042 家族（a191_lw_crack）、120/140（qfq_rich 重建）、价量基础腿。
LT：10 个（lvl1mT / rel_T5_T252 / volT5y / volV5y / volret / rel 均值族 / stdvol 族）。

--phase validate : 加载数据 + 构建基底 + 打印签名（校对重建口径）并缓存 rank。
--phase sweep    : 读缓存，跑混权网格，输出每目标 top。

用法: python3 scripts/opp_halfcenter_search_20260928.py --phase validate
"""
from __future__ import annotations

import argparse
import gc
import io
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import a191_lw_crack_20260928 as crack  # noqa: E402

OUT = ROOT / "research_reports/platform_alignment/opp-halfcenter-20260928"
PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
RICH = (ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/"
        "qfq_rich/daily_batches")
CACHE = OUT / "bases.pkl"
CYCLE = 10
GRID_START = "2021-09-29"
GRID_N = 119
WGRID = [round(0.05 * i, 2) for i in range(1, 20)]  # 0.05..0.95


def load_panels() -> dict:
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    return {k: v.astype("float32") for k, v in panels.items()}


def load_rich() -> dict:
    files = sorted(RICH.glob("*.parquet"))
    cols = ["date", "instrument", "open", "high_qfq", "low_qfq", "close", "volume",
            "amount", "raw_close"]
    parts = []
    for i, f in enumerate(files):
        parts.append(pd.read_parquet(f, columns=cols))
        if (i + 1) % 60 == 0:
            print(f"  rich part {i+1}/{len(files)}", flush=True)
    big = pd.concat(parts, ignore_index=True)
    del parts
    gc.collect()
    big["date"] = pd.to_datetime(big["date"]).dt.normalize()
    big["instrument"] = big["instrument"].astype(str)
    big = big.sort_values(["date", "instrument"]).drop_duplicates(
        ["date", "instrument"], keep="last")
    out = {}
    spec = {"open": "open", "high": "high_qfq", "low": "low_qfq", "close": "close",
            "volume": "volume", "amount": "amount", "raw_close": "raw_close"}
    for name, col in spec.items():
        w = big.pivot(index="date", columns="instrument", values=col)
        out[name] = w.astype("float32")
        print(f"  rich {name} {w.shape}", flush=True)
    del big
    gc.collect()
    return out


def schedule(cal: pd.DatetimeIndex, start: str, step: int, count: int) -> list:
    p0 = int(cal.searchsorted(pd.Timestamp(start), side="left"))
    return [cal[i] for i in range(p0, min(p0 + step * count, len(cal)), step)]


def rank_ic_series(values: pd.DataFrame, cal: pd.DatetimeIndex, sched: list,
                   cycle: int, positions: dict, close: pd.DataFrame) -> np.ndarray:
    out = np.full(len(sched), np.nan)
    for k, date in enumerate(sched):
        i = positions[date]
        if i + 1 + cycle >= len(cal):
            continue
        y = (close.iloc[i + 1 + cycle].to_numpy(dtype="float64")
             / close.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
        x = values.iloc[i].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        xr = pd.Series(x[ok]).rank().to_numpy()
        yr = pd.Series(y[ok]).rank().to_numpy()
        if xr.std() == 0 or yr.std() == 0:
            continue
        out[k] = float(np.corrcoef(xr, yr)[0, 1])
    return out


def ic_stats(series: np.ndarray) -> dict:
    s = series[np.isfinite(series)]
    if len(s) < 30:
        return dict(n=len(s), mean=np.nan, ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan)
    m = float(np.mean(s))
    sd = float(np.std(s, ddof=1))
    sign = 1.0 if m >= 0 else -1.0
    win = float(np.mean(s * sign > 0.02))
    icir = abs(m) / sd if sd > 0 else 0.0
    return dict(n=len(s), mean=m, ic=abs(m), icir=icir, win=win, s_i=abs(m) * icir * win)


def build_bases(panels: dict, rich: dict) -> tuple[dict, dict]:
    C = panels["close"]
    cal = C.index
    idx, cols = cal, C.columns
    ret1 = C.pct_change(fill_method=None)
    O, H, L, V, A, T = (panels[k] for k in ("open", "high", "low", "volume", "amount", "turnover"))
    d_qfq = dict(open=O, close=C, high=H, low=L, volume=V, amount=A,
                 vwap=A * 10.0 / V, turnover=T, returns=ret1)

    bases: dict[str, pd.DataFrame] = {}
    for k, v in crack.build_core010(d_qfq, ret1, C).items():
        bases["010_" + k.split("_", 1)[1]] = v
    for k, v in crack.build_core042(d_qfq, H, V, C).items():
        bases["042_" + k.split("_", 1)[1]] = v

    rc = rich["close"].reindex(index=idx, columns=cols)
    compat = float((rc - C).abs().stack().median())
    print(f"rich close vs panel close median |diff| = {compat:.6f}", flush=True)
    sc = (rich["close"] / rich["raw_close"]).reindex(index=idx, columns=cols).astype("float32")
    data_rich = dict(
        open=rich["open"].reindex(index=idx, columns=cols),
        high=rich["high"].reindex(index=idx, columns=cols),
        low=rich["low"].reindex(index=idx, columns=cols),
        close=rc,
        volume=rich["volume"].reindex(index=idx, columns=cols),
        vwap=((rich["amount"] * 10.0 / rich["volume"]) * sc).reindex(index=idx, columns=cols),
    )
    funcs = crack.load_factors(crack.REFERENCE)
    bases["120_ref"] = funcs["alpha191_120"](data_rich).astype("float32")
    bases["140_ref"] = funcs["alpha191_140"](data_rich).astype("float32")
    del data_rich, sc
    gc.collect()

    bases["intr20"] = ((C - O) / O).rolling(20).mean()
    bases["intr40"] = ((C - O) / O).rolling(40).mean()
    bases["intr60"] = ((C - O) / O).rolling(60).mean()
    bases["maxret20"] = ret1.rolling(20).max()
    bases["amihud20"] = (ret1.abs() / A).rolling(20).mean()
    bases["retrev5"] = -(C / C.shift(5) - 1.0)
    bases["retrev20"] = -(C / C.shift(20) - 1.0)
    bases["amt60"] = np.log(A.rolling(60).mean())
    bases["pvcorr20"] = -H.astype("float64").rolling(20).corr(V.astype("float64"))
    bases["stdvol20_rel5y"] = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()

    LT = {}
    LT["lvl1mT"] = 1.0 - T.rank(axis=1, pct=True)
    LT["rel_T5_T252"] = 1.0 - (T.rolling(5).mean() / T.rolling(252, min_periods=100).mean()).rank(axis=1, pct=True)
    LT["rel_T21_T504"] = 1.0 - (T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()).rank(axis=1, pct=True)
    LT["rel_T21_T252"] = 1.0 - (T.rolling(21).mean() / T.rolling(252, min_periods=100).mean()).rank(axis=1, pct=True)
    LT["lvl1mT21"] = 1.0 - T.rolling(21).mean().rank(axis=1, pct=True)
    LT["volret"] = 1.0 - ret1.rolling(20).std().rank(axis=1, pct=True)
    LT["volT5y"] = 1.0 - (T.rolling(20).std() / T.rolling(1250, min_periods=400).std()).rank(axis=1, pct=True)
    LT["volV5y"] = 1.0 - (V.rolling(10).std() / V.rolling(1250, min_periods=400).std()).rank(axis=1, pct=True)
    for name, df in list(bases.items()) + list(LT.items()):
        if df.isna().all().all():
            raise RuntimeError(f"base {name} all NaN")
    return bases, LT


def make_rank_cache(bases: dict, LT: dict, grid: list, close: pd.DataFrame):
    out = {"base_rank": {}, "lt_rank": {}, "base_stats": {}, "lt_stats": {}}
    cal = close.index
    pos = {d: i for i, d in enumerate(cal)}
    for name, df in bases.items():
        st = ic_stats(rank_ic_series(df, cal, grid, CYCLE, pos, close))
        sign = 1.0 if st["mean"] >= 0 else -1.0
        out["base_stats"][name] = dict(st, sign=sign)
        out["base_rank"][name] = (df * sign).rank(axis=1, pct=True).astype("float32")
        print(f"base {name:<22} ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} "
              f"s_i={st['s_i']:.4f} sign={sign:+.0f}", flush=True)
    for name, df in LT.items():
        st = ic_stats(rank_ic_series(df, cal, grid, CYCLE, pos, close))
        sign = 1.0 if st["mean"] >= 0 else -1.0
        out["lt_stats"][name] = dict(st, sign=sign)
        out["lt_rank"][name] = (df * sign).rank(axis=1, pct=True).astype("float32")
        print(f"lt   {name:<22} ic={st['ic']:.4f} icir={st['icir']:.3f} win={st['win']:.3f} "
              f"s_i={st['s_i']:.4f} sign={sign:+.0f}", flush=True)
    return out


def load_targets() -> list[dict]:
    t = pd.read_csv(ROOT / "research_reports/platform_alignment/side-line-20260927/"
                    "opp_factor_rows.csv", encoding="utf-8-sig")
    wanted = ["F-I01_Alpha191_010_LW", "R03-0.0727-0.8019", "alpha191-042",
              "G17-zscore3", "G16-scale3", "R01-0.0790-0.9569", "R01-0.0847-0.7915",
              "F-J08_Alpha191_140_LW", "E13-P2+skew", "E5-a191x3",
              "ks91-full-ks91-acf-3y", "C260912-B01"]
    rows = []
    for name in wanted:
        r = t[t.name == name]
        if not len(r):
            print(f"!! target not found: {name}", flush=True)
            continue
        r = r.iloc[0]
        rows.append(dict(tag=name, pool=r["pool"], ic=abs(float(r["ic_mean"])),
                         icir=abs(float(r["icir"])), win=float(r["ic_win_rate"])))
    return rows


def validate(panels: dict, rich: dict) -> int:
    bases, LT = build_bases(panels, rich)
    close = panels["close"]
    grid = schedule(close.index, GRID_START, CYCLE, GRID_N)
    print(f"grid {grid[0].date()}..{grid[-1].date()} n={len(grid)}", flush=True)
    cache = make_rank_cache(bases, LT, grid, close)
    cache["grid"] = grid
    cache["targets"] = load_targets()
    print("\ntargets:")
    for t in cache["targets"]:
        print(f"  {t['tag']:<26} ic={t['ic']:.4f} icir={t['icir']:.3f} win={t['win']:.3f}", flush=True)
    with CACHE.open("wb") as fh:
        pickle.dump(cache, fh)
    print(f"cache written {CACHE} ({CACHE.stat().st_size/1e6:.1f} MB)", flush=True)
    return 0


def sweep(panels: dict) -> int:
    with CACHE.open("rb") as fh:
        cache = pickle.load(fh)
    close = panels["close"]
    cal = close.index
    pos = {d: i for i, d in enumerate(cal)}
    grid = cache["grid"]
    targets = cache["targets"]
    base_rank = cache["base_rank"]
    lt_rank = cache["lt_rank"]

    per_target: dict[str, list] = {t["tag"]: [] for t in targets}
    n_done = 0
    total = len(base_rank) * len(lt_rank) * len(WGRID)
    for bname, Rb in base_rank.items():
        for lname, Rl in lt_rank.items():
            for w in WGRID:
                v = w * Rb
                v += (1.0 - w) * Rl
                st = ic_stats(rank_ic_series(v, cal, grid, CYCLE, pos, close))
                n_done += 1
                if n_done % 400 == 0:
                    print(f"  {n_done}/{total}", flush=True)
                for t in targets:
                    d_ic = abs(st["ic"] - t["ic"])
                    d_ir = abs(st["icir"] - t["icir"])
                    d_wn = abs(st["win"] - t["win"])
                    d = d_ic / 0.02 + d_ir / 0.20 + d_wn / 0.06
                    row = dict(base=bname, lt=lname, w=w, ic=st["ic"], icir=st["icir"],
                               win=st["win"], s_i=st["s_i"], d=d, d_ic=d_ic, d_icir=d_ir, d_win=d_wn)
                    lst = per_target[t["tag"]]
                    lst.append(row)
                    if len(lst) > 40:
                        lst.sort(key=lambda r: r["d"])
                        del lst[20:]
    rows = []
    for t in targets:
        best = sorted(per_target[t["tag"]], key=lambda r: r["d"])[:15]
        for i, r in enumerate(best):
            rows.append(dict(target=t["tag"], rank=i + 1, **r))
        print(f"\n=== {t['tag']} (target ic={t['ic']:.4f} icir={t['icir']:.3f} win={t['win']:.3f}) ===",
              flush=True)
        for r in best[:6]:
            print(f"  {r['base']:<20} {r['lt']:<14} w={r['w']:.2f} -> ic={r['ic']:.4f} "
                  f"icir={r['icir']:.3f} win={r['win']:.3f} | d={r['d']:.3f} "
                  f"({r['d_ic']:+.4f}/{r['d_icir']:+.3f}/{r['d_win']:+.3f})", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "matches_top.csv", index=False, encoding="utf-8-sig")
    print(f"\nwritten {OUT/'matches_top.csv'} ({len(out)} rows)", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["validate", "sweep"], default="validate")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    crack.install_shim()
    panels = load_panels()
    if args.phase == "validate":
        rich = load_rich()
        return validate(panels, rich)
    return sweep(panels)


if __name__ == "__main__":
    raise SystemExit(main())
