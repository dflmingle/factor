#!/usr/bin/env python3
"""Board-inspired construction screen (2026-10-08, local, zero platform compute).

Takes the mechanism families observed on the published board (pools ranked 21+,
never screened before) and evaluates *our own* generic constructions of those
mechanisms locally, under the house conventions (all-A panel, platform signal
dates, cycle-10 label, top-decile turnover, 0.30% one-way cost).

Families screened:
  A. liquidity/size composite: low turnover ratio x low amount x small cap
     (mechanism behind several 21+ pools: LowTurnover_LowAmount_SmallCap etc.)
  B. A191 hybrids: official-reference Alpha191 members blended with stability
     legs (mechanism behind the Alpha191 modifier schools on the board)
  C. reversal x low-amount composites

Output: research_reports/platform_alignment/board-higha-20261008/local_screen.csv
"""
from __future__ import annotations

import io
import pickle
import sys
import types
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import alpha191_ops_local as ops  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402

OUT = ROOT / "research_reports/platform_alignment/board-higha-20261008"
PANELS = ROOT / "research_reports/platform_alignment/alpha191-local-20260923/panels.pkl"
REFERENCE = ROOT / ".cache/third_party/alpha191_reference.py"
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
CYCLE = 10
WARMUP_START = pd.Timestamp("2020-06-01")


def install_shim() -> None:
    def factor_attr(*_args, **_kwargs):
        def decorator(function):
            return function
        return decorator

    lib = types.ModuleType("lib"); lib.__path__ = []  # type: ignore[attr-defined]
    sys.modules["lib"] = lib
    base = types.ModuleType("lib.base"); base.FactorBase = object
    sys.modules["lib.base"] = base
    ops_pkg = types.ModuleType("lib.ops"); ops_pkg.__path__ = []  # type: ignore[attr-defined]
    sys.modules["lib.ops"] = ops_pkg
    factor_ops = types.ModuleType("lib.ops.factor_ops")
    for name, function in ops.OPS.items():
        setattr(factor_ops, name, function)
    sys.modules["lib.ops.factor_ops"] = factor_ops
    utils = types.ModuleType("lib.utils"); utils.__path__ = []  # type: ignore[attr-defined]
    sys.modules["lib.utils"] = utils
    method_attrs = types.ModuleType("lib.utils.method_attrs")
    method_attrs.factor_attr = factor_attr
    sys.modules["lib.utils.method_attrs"] = method_attrs

    qlib = types.ModuleType("qlib"); qlib.__path__ = []  # type: ignore[attr-defined]
    sys.modules["qlib"] = qlib
    qlib_data = types.ModuleType("qlib.data"); qlib_data.__path__ = []  # type: ignore[attr-defined]
    sys.modules["qlib.data"] = qlib_data
    qlib_ops = types.ModuleType("qlib.data.ops")
    for name in ("rolling_slope", "rolling_rsquare", "rolling_resi",
                 "expanding_slope", "expanding_rsquare", "expanding_resi"):
        setattr(qlib_ops, name, getattr(ops, name))
    sys.modules["qlib.data.ops"] = qlib_ops


def load_factors(path: Path) -> dict:
    namespace: dict = {}
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), namespace)
    return {k: v for k, v in namespace.items()
            if k.startswith("alpha191_") and callable(v)}


def pct_rank(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rank(axis=1, pct=True).astype("float32")


def inv(frame: pd.DataFrame) -> pd.DataFrame:
    return (1.0 - frame).astype("float32")


def evaluate(values: pd.DataFrame, schedule, forward_returns, calendar, positions,
             seat_frame) -> dict:
    held = np.full(len(schedule), np.nan)
    gross = np.full(len(schedule), np.nan)
    turnover = np.full(len(schedule), np.nan)
    counts = np.zeros(len(schedule), dtype=np.int32)
    valid_flags = np.zeros(len(schedule), dtype=np.uint8)
    rank_ics = np.full(len(schedule), np.nan)
    ics = np.full(len(schedule), np.nan)
    previous: set = set()
    for index, date in enumerate(schedule):
        row = values.iloc[positions[date]].to_numpy(dtype="float64")
        forward = forward_returns[date]
        ok = np.isfinite(row) & np.isfinite(forward)
        if ok.sum() < 100:
            continue
        x = row[ok]; y = forward[ok]
        if np.std(x) == 0 or np.std(y) == 0:
            continue
        instruments = values.columns.to_numpy()[ok]
        top_n = int(len(x) * 0.1)
        order = np.argsort(-x)[:top_n]
        selected = set(instruments[order].tolist())
        if previous:
            turnover[index] = 1.0 - len(selected & previous) / len(selected)
        previous = selected
        held[index] = float(y[order].mean())
        gross[index] = held[index] - float(y.mean())
        counts[index] = len(x)
        valid_flags[index] = 1
        rank_ics[index] = float(np.corrcoef(pd.Series(x).rank().to_numpy(),
                                            pd.Series(y).rank().to_numpy())[0, 1])
        ics[index] = float(np.corrcoef(x, y)[0, 1])
    summary = e._summary(held, gross, turnover, counts, valid_flags.astype(bool),
                         np.asarray([d.to_datetime64() for d in schedule]),
                         CYCLE, "5y", np.ones(len(schedule), bool))
    r = rank_ics[np.isfinite(rank_ics)]; i_ = ics[np.isfinite(ics)]
    mean_rank = float(np.mean(r)); mean_ic = float(np.mean(i_))
    std_ic = float(np.std(i_, ddof=1))
    direction = 1 if mean_ic >= 0 else 0
    win = float(np.mean(i_ > 0.02)) if direction == 1 else float(np.mean(i_ < -0.02))
    ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0
    corr = {}
    if seat_frame is not None:
        seat_like = pd.Series(values.to_numpy().ravel(), index=pd.MultiIndex.from_product(
            [values.index, values.columns]))
        merged = pd.DataFrame({"alpha": seat_like}).join(seat_frame, how="inner")
        for seat in POOL:
            corr[seat] = float(merged.groupby(level=0)
                               .apply(lambda g: g["alpha"].corr(g[seat], method="spearman")).mean())
    return dict(rank_ic=mean_rank, ic_ir=ic_ir, win=win,
                s_i=abs(mean_rank) * abs(ic_ir) * win, direction=direction,
                turnover=(summary["turnover_pct"] or 0.0) / 100.0,
                net_excess=summary["net_excess_pct"],
                gross_excess=summary["gross_excess_pct"],
                max_pool_corr=max(corr.values()) if corr else None,
                corr_size=corr.get("size_only"), corr_h03=corr.get("impact60"),
                corr_t10=corr.get("t10_size_plus_impact_bm"),
                corr_e=corr.get("book_to_market_lf_minus_size"),
                corr_f=corr.get("book_to_market_lf_plus_impact"))


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


def ic_stats(rank_ics: np.ndarray, ics: np.ndarray) -> dict:
    rank_ics = rank_ics[np.isfinite(rank_ics)]
    if len(rank_ics) == 0:
        return dict(rank_ic=None)
    return dict(rank_ic=float(np.mean(rank_ics)))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    install_shim()
    factors = load_factors(REFERENCE)
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    close = panels["close"].loc[WARMUP_START:]
    calendar = close.index
    positions = {d: i for i, d in enumerate(calendar)}
    data = {name: frame.loc[WARMUP_START:] for name, frame in panels.items()}
    data["close"] = close
    O, H, L, V, A, T = (data[k] for k in ("open", "high", "low", "volume", "amount", "turnover"))
    MV = data["total_mv"]
    ret1 = C = None
    C = close
    ret1 = C.pct_change(fill_method=None)
    print(f"panel={close.shape} {calendar[0].date()}..{calendar[-1].date()}", flush=True)

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    signal_dates = [pd.Timestamp(v) for v in sorted(sf["date"].unique())]
    schedule, forward_returns = [], {}
    for date in signal_dates:
        if date not in positions:
            continue
        cur = positions[date] + 1
        fut = cur + CYCLE
        if fut >= len(calendar):
            continue
        schedule.append(date)
        forward_returns[date] = (close.iloc[fut] / close.iloc[cur] - 1.0).to_numpy()
    print(f"signal dates={len(schedule)} {schedule[0].date()}..{schedule[-1].date()}", flush=True)

    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(schedule)].set_index(["date", "instrument"])

    # ---- legs ---------------------------------------------------------------
    legs: dict[str, pd.DataFrame] = {}
    legs["relT"] = inv(pct_rank(T.rolling(5).mean() / T.rolling(252, min_periods=100).mean()))
    legs["relT21"] = inv(pct_rank(T.rolling(21).mean() / T.rolling(504, min_periods=200).mean()))
    legs["amt60"] = inv(pct_rank(A.rolling(60).mean()))
    legs["amt250"] = inv(pct_rank(A.rolling(250, min_periods=120).mean()))
    legs["mv"] = inv(pct_rank(MV))
    legs["rev20"] = inv(pct_rank(C / C.shift(20) - 1.0))
    legs["amtstd"] = inv(pct_rank(A.rolling(20).std() / A.rolling(20).mean()))
    legs["volstd"] = inv(pct_rank(V.rolling(10).std() / V.rolling(20).mean()))

    a191_wanted = ["010", "042", "070", "095", "100", "132"]
    
    a191_names = []
    for tag in a191_wanted:
        name = f"alpha191_{tag}"
        try:
            values = factors[name](data).astype("float32")
        except Exception as exc:  # noqa: BLE001
            print(f"!! {name} failed: {exc}", flush=True)
            continue
        series = rank_ic_series(values, calendar, schedule, CYCLE, positions, close)
        st = ic_stats(series, series)
        sign = 1.0 if np.nanmean(series) >= 0 else -1.0
        legs[f"S{tag}"] = pct_rank(values) if sign > 0 else inv(pct_rank(values))
        print(f"leg {name}: ic={abs(st['rank_ic'] or 0):.4f} sign={sign:+.0f}", flush=True)
        a191_names.append(f"S{tag}")
    del data
    # keep panels subset used by legs only
    for k in ("open", "high", "low", "volume", "amount", "turnover", "vwap", "returns"):
        pass
    print("legs built:", sorted(legs), flush=True)

    # ---- constructions ------------------------------------------------------
    cands: dict[str, dict] = {}

    def add(name: str, weights: dict):
        cands[name] = weights

    # family A: (relT/relT21) x amt60/250 x mv, weight grid step .2
    grid = [round(0.2 * i, 1) for i in range(6)]
    for amt in ("amt60", "amt250"):
        for w1 in grid:
            for w2 in grid:
                w3 = round(1.0 - w1 - w2, 1)
                if w3 < -1e-9 or w3 > 1:
                    continue
                add(f"A|{amt}|{w1:.1f}/{w2:.1f}/{w3:.1f}", {"relT": w1, amt: w2, "mv": w3})
    for w1, w2, w4 in ((0.4, 0.2, 0.2), (0.3, 0.3, 0.2), (0.3, 0.2, 0.3), (0.25, 0.25, 0.25)):
        w3 = round(1.0 - w1 - w2 - w4, 2)
        add(f"A4|{w1:.2f}/{w2:.2f}/{w3:.2f}/{w4:.2f}",
            {"relT": w1, "amt60": w2, "mv": w3, "amtstd": w4})
    # family B: A191 hybrids
    add("B1|010+relT", {"S010": 0.5, "relT": 0.5})
    add("B2|010+relT+amtstd", {"S010": 0.35, "relT": 0.35, "amtstd": 0.3})
    add("B3|042+relT", {"S042": 0.5, "relT": 0.5})
    add("B4|042+relT+amtstd", {"S042": 0.4, "relT": 0.3, "amtstd": 0.3})
    add("B5|070+relT+amtstd+mv", {"S070": 0.3, "relT": 0.3, "amtstd": 0.2, "mv": 0.2})
    add("B6|eq5", {k: 0.2 for k in ("S010", "S042", "S070", "relT", "amtstd")})
    add("B7|lowturn3+relT", {"S095": 0.25, "S132": 0.25, "S100": 0.25, "relT": 0.25})
    add("B8|010rev+relT", {"S010inv": 0.5, "relT": 0.5})
    # family C: reversal x low amount
    add("C1|rev20+amt60", {"rev20": 0.5, "amt60": 0.5})
    add("C2|rev20+relT+amt60", {"rev20": 0.4, "relT": 0.4, "amt60": 0.2})
    add("C3|rev20+amtstd", {"rev20": 0.5, "amtstd": 0.5})

    legs["S010inv"] = inv(legs["S010"])

    rows = []
    # evaluate legs themselves first (sanity)
    for name in sorted(legs):
        st = evaluate(legs[name], schedule, forward_returns, calendar, positions, seat_frame)
        rows.append(dict(candidate=f"LEG|{name}", **st))
        print(f"leg {name:<8} s_i={st['s_i']:.4f} ic={st['rank_ic']:+.4f} icir={st['ic_ir']:+.3f} "
              f"win={st['win']:.3f} turn={st['turnover']:.3f} net={st['net_excess']:.2f}", flush=True)

    for name, weights in cands.items():
        base = None
        for leg, w in weights.items():
            if w <= 0:
                continue
            part = legs[leg] * float(w)
            base = part if base is None else base + part
        st = evaluate(base, schedule, forward_returns, calendar, positions, seat_frame)
        rows.append(dict(candidate=name, **st))
        print(f"{name:<24} s_i={st['s_i']:.4f} ic={st['rank_ic']:+.4f} icir={st['ic_ir']:+.3f} "
              f"win={st['win']:.3f} turn={st['turnover']:.3f} net={st['net_excess']:.2f}", flush=True)

    frame = pd.DataFrame(rows).sort_values("s_i", ascending=False)
    frame.to_csv(OUT / "local_screen.csv", index=False)
    print("\ntop 25 by s_i:")
    print(frame.head(25)[["candidate", "s_i", "rank_ic", "ic_ir", "win", "turnover",
                          "net_excess", "max_pool_corr"]].to_string(index=False, float_format="%.4f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
