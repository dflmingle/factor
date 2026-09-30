"""Alpha191 "LW" 席位破解测试台（本地零平台算力）。

目标：把对手已上平台验证的席位在本地配出来（同窗口、同 s_i 口径），
因为"配得上"= 该公式拿到了外部验证的 s_i，可以直接当席位候选报批。

s_i 口径（官方，2026-09-26 修正版）：
    s_i = |mean(RankIC)| * |mean/std(RankIC)| * share(sign_aligned RankIC > 0.02)
标签：label-1（close(t+1) -> close(t+1+cycle)）；股票池=本地全 A qfq 面板。

用法：
    python scripts/a191_lw_crack_20260928.py --phase calib
    python scripts/a191_lw_crack_20260928.py --phase core010
"""
from __future__ import annotations

import argparse
import gc
import pickle
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import alpha191_ops_local as ops  # noqa: E402

PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
RAW_DIR = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/raw_daily"
RICH = ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq_rich/daily_batches"
OUT = ROOT / "research_reports/platform_alignment/a191-lw-crack-20260928"
REFERENCE = ROOT / ".cache/third_party/alpha191_reference.py"

# 对手已上平台验证的席位（top20_factor_details 快照，2026-09-27 抓取）
TARGETS = [
    dict(tag="F-I01_A191_010_LW", pool="换手反转|新人报道", ic=0.1253, icir=0.980, win=0.798,
         start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="F-J06_A191_120_LW", pool="换手反转|新人报道", ic=0.1021, icir=0.826, win=0.765,
         start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="F-J08_A191_140_LW", pool="换手反转|新人报道", ic=0.0653, icir=0.845, win=0.731,
         start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="F-I07_A191_124_LW", pool="换手反转|新人报道", ic=0.0014, icir=0.012, win=0.378,
         start="2021-09-29", end="2026-08-14", cycle=10),
    dict(tag="alpha191-042", pool="啦啦啦啦啦|forests", ic=0.0957, icir=0.975, win=0.773,
         start="2021-09-15", end="2026-08-04", cycle=10),
    dict(tag="F191-010 (LavineX)", pool="稳健多因子Alpha|LavineX", ic=0.0947, icir=0.688, win=0.730,
         start="2021-09-27", end="2026-09-09", cycle=5),
]


def install_shim() -> None:
    def factor_attr(*_a, **_k):
        def deco(fn):
            return fn
        return deco

    lib = types.ModuleType("lib"); lib.__path__ = []
    sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object
    sys.modules["lib.base"] = base
    pkg = types.ModuleType("lib.ops"); pkg.__path__ = []
    sys.modules["lib.ops"] = pkg
    fo = types.ModuleType("lib.ops.factor_ops")
    for name, fn in ops.OPS.items():
        setattr(fo, name, fn)
    sys.modules["lib.ops.factor_ops"] = fo
    ut = types.ModuleType("lib.utils"); ut.__path__ = []
    sys.modules["lib.utils"] = ut
    ma = types.ModuleType("lib.utils.method_attrs"); ma.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = ma
    ql = types.ModuleType("qlib"); ql.__path__ = []
    sys.modules["qlib"] = ql
    qd = types.ModuleType("qlib.data"); qd.__path__ = []
    sys.modules["qlib.data"] = qd
    qo = types.ModuleType("qlib.data.ops")
    for n in ("rolling_slope", "rolling_rsquare", "rolling_resi",
              "expanding_slope", "expanding_rsquare", "expanding_resi"):
        setattr(qo, n, getattr(ops, n))
    sys.modules["qlib.data.ops"] = qo


def load_factors(path: Path) -> dict:
    ns: dict = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
    return {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}


def load_panels() -> dict:
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    return {k: v.astype("float32") for k, v in panels.items()}


def load_raw_panels(dates: pd.DatetimeIndex, instruments: pd.Index) -> dict:
    """raw（未复权）价量面板，与 qfq 面板同网格。"""
    cache = OUT / "raw_panels.pkl"
    if cache.exists():
        with cache.open("rb") as fh:
            return pickle.load(fh)
    frames = []
    for path in sorted(RAW_DIR.glob("raw_*.parquet")):
        frames.append(pd.read_parquet(path))
    allraw = pd.concat(frames, ignore_index=True)
    allraw["date"] = pd.to_datetime(allraw["trade_date"], format="%Y%m%d")
    allraw = allraw.rename(columns={"vol": "volume"})
    out = {}
    for name in ("open", "high", "low", "close", "volume", "amount"):
        if name == "open":
            continue
        wide = allraw.pivot(index="date", columns="ts_code", values=name)
        wide = wide.reindex(index=dates, columns=instruments).astype("float32")
        wide.columns.name = None
        out[name] = wide
    out["open"] = out["close"].shift(0)  # raw_daily 无 open：后续如需再用
    pd.to_pickle(out, cache)
    return out


def schedule(calendar: pd.DatetimeIndex, start: str, end: str, cycle: int) -> list[pd.Timestamp]:
    first = pd.Timestamp(start)
    last = pd.Timestamp(end)
    lo = int(calendar.searchsorted(first, side="left"))
    hi = int(calendar.searchsorted(last, side="right")) - 1
    return [calendar[i] for i in range(lo, hi + 1, cycle)]


def rank_ic_series(values: pd.DataFrame, cal: pd.DatetimeIndex, sched: list, cycle: int,
                   positions: dict) -> np.ndarray:
    out = np.full(len(sched), np.nan)
    close = C_GLOBAL
    for k, date in enumerate(sched):
        i = positions[date]
        if i + 1 + cycle >= len(cal):
            continue
        y = (close.iloc[i + 1 + cycle].to_numpy(dtype="float64")
             / close.iloc[i + 1].to_numpy(dtype="float64") - 1.0)
        x = values.iloc[i].to_numpy(dtype="float64")
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 100:
            continue
        xr = pd.Series(x[valid]).rank().to_numpy()
        yr = pd.Series(y[valid]).rank().to_numpy()
        if np.std(xr) == 0 or np.std(yr) == 0:
            continue
        out[k] = float(np.corrcoef(xr, yr)[0, 1])
    return out


def aligned_stats(series: np.ndarray) -> dict:
    s = series[np.isfinite(series)]
    if len(s) < 30:
        return dict(n=len(s), ic=np.nan, icir=np.nan, win=np.nan, s_i=np.nan)
    mean = float(np.mean(s))
    sd = float(np.std(s, ddof=1))
    sign = 1.0 if mean >= 0 else -1.0
    win = float(np.mean(s * sign > 0.02))
    icir = abs(mean) / sd if sd > 0 else 0.0
    return dict(n=len(s), ic=abs(mean), icir=icir, win=win, s_i=abs(mean) * icir * win)


def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="calib")
    parser.add_argument("--out", default=str(OUT / "results.csv"))
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    install_shim()

    global C_GLOBAL
    panels = load_panels()
    C = panels["close"]
    C_GLOBAL = C
    cal = C.index
    positions = {d: i for i, d in enumerate(cal)}
    V, A, O, H, L, T = (panels[k] for k in ("volume", "amount", "open", "high", "low", "turnover"))
    ret1 = C.pct_change(fill_method=None)

    d_qfq = dict(open=O, close=C, high=H, low=L, volume=V, amount=A,
                 vwap=A * 10.0 / V, turnover=T, returns=ret1)

    factors = load_factors(REFERENCE)
    sched_cache = {}
    def sched_for(t):
        key = (t["start"], t["end"], t["cycle"])
        if key not in sched_cache:
            sched_cache[key] = schedule(cal, t["start"], t["end"], t["cycle"])
        return sched_cache[key]

    candidates: dict[str, pd.DataFrame] = {}
    phase = args.phase

    if phase == "calib":
        candidates["maxret20"] = ret1.rolling(20).max()
        candidates["size_total_mv"] = panels["total_mv"]
        candidates["rev20"] = -(C / C.shift(20) - 1.0)
        candidates["volstd10_log"] = np.log(V).rolling(10).std()
        candidates["stdvol20_rel5y"] = V.rolling(20).std() / V.rolling(1250, min_periods=400).std()
        candidates["intradayma60"] = ((C - O) / O).rolling(60).mean()
        candidates["amt60_log"] = np.log(A.rolling(60).mean())
    elif phase == "core010":
        candidates.update(build_core010(d_qfq, ret1, C))
    elif phase == "core042":
        candidates.update(build_core042(d_qfq, H, V, C))
    else:
        raise SystemExit(f"unknown phase {phase}")

    rows = []
    for name, values in candidates.items():
        for t in TARGETS:
            if t["cycle"] != 10 and phase != "calib":
                continue
            sched = sched_for(t)
            if len(sched) < 30:
                continue
            ics = rank_ic_series(values, cal, sched, t["cycle"], positions)
            st = aligned_stats(ics)
            rows.append(dict(candidate=name, pool=t["pool"], target=t["tag"], window=f"{t['start']}..{t['end']}",
                             cycle=t["cycle"], **st,
                             d_ic=None if np.isnan(st["ic"]) else st["ic"] - t["ic"],
                             d_icir=None if np.isnan(st["icir"]) else st["icir"] - t["icir"],
                             d_win=None if np.isnan(st["win"]) else st["win"] - t["win"]))
            print("%-22s %-22s n=%3d ic=%.4f icir=%.3f win=%.3f s_i=%.4f | d=%+.4f/%+.3f/%+.3f" % (
                name, t["tag"], st["n"], st["ic"], st["icir"], st["win"], st["s_i"],
                st["ic"] - t["ic"], st["icir"] - t["icir"], st["win"] - t["win"]), flush=True)
        del values
        gc.collect()

    df = pd.DataFrame(rows)
    out = Path(args.out)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nwrote {out} ({len(df)} rows)")
    return 0


def build_core010(d, ret1, C) -> dict:
    """#010 家族：官方参考实现 + 两种变体（ts_max / 平方口径）。"""
    out = {}
    cond = ret1 < 0
    std20 = ret1.rolling(20).std()
    base = std20.where(cond, C) ** 2
    out["010_ref"] = np.maximum(base, 5.0).rank(axis=1, pct=True)
    out["010_tsmax5"] = base.rolling(5).max().rank(axis=1, pct=True)
    out["010_nomax"] = base.rank(axis=1, pct=True)
    out["010_ref_neg"] = -out["010_ref"]
    out["010_tsmax5_neg"] = -out["010_tsmax5"]
    if "raw_close" in d:
        C_r = d["raw_close"]
        std20r = C_r.pct_change(fill_method=None).rolling(20).std()
        baser = std20r.where(cond, C_r) ** 2
        out["010_raw_ref"] = np.maximum(baser, 5.0).rank(axis=1, pct=True)
        out["010_raw_tsmax5"] = baser.rolling(5).max().rank(axis=1, pct=True)
    return out


def build_core042(d, H, V, C) -> dict:
    out = {}
    std10 = H.rolling(10).std()
    corr10 = H.astype("float64").rolling(10).corr(V.astype("float64"))
    out["042_ref"] = -(std10.rank(axis=1, pct=True) * corr10)
    out["042_ref_neg"] = -out["042_ref"]
    out["042_stdonly"] = -std10.rank(axis=1, pct=True)
    out["042_stdonly_neg"] = -out["042_stdonly"]
    return out


if __name__ == "__main__":
    raise SystemExit(main())
