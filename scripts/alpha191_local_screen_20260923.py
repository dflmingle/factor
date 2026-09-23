"""Local Alpha191 screen under the competition (qualitygate3) conventions.

The 191 factor definitions are public research (GTJA 短周期价量因子).  This
script executes a reference implementation of those formulas against our own
cached panels, then scores every factor exactly like a pool seat:

* 10-day unified rebalance schedule taken from the alignment cache,
* RankIC / IC / ICIR / win rate -> ``S_i`` (the A component input),
* per-rebalance top-decile turnover, cost-adjusted net excess, Sharpe,
* cross-sectional rank correlation against the five seats of the current pool.

The reference formula file is downloaded once into ``.cache/third_party`` and
its URL + SHA256 are recorded; no platform call and no new data download.
"""
from __future__ import annotations

import hashlib
import pickle
import sys
import types
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alpha191_ops_local as ops  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/alpha191-local-20260923"
PANELS = OUT / "panels.pkl"
REFERENCE_URL = "https://raw.githubusercontent.com/Daic115/alpha191/master/alpha191.py"
REFERENCE_CACHE = ROOT / ".cache/third_party/alpha191_reference.py"
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
    base = types.ModuleType("lib.base")
    base.FactorBase = object
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


def reference_path() -> Path:
    if not REFERENCE_CACHE.exists():
        REFERENCE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(REFERENCE_URL, timeout=60) as response:
            REFERENCE_CACHE.write_bytes(response.read())
    return REFERENCE_CACHE


def load_factors(path: Path) -> dict:
    namespace: dict = {}
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), namespace)
    return {
        name: value
        for name, value in namespace.items()
        if name.startswith("alpha191_") and callable(value)
    }


def ic_stats(rank_ics: np.ndarray, ics: np.ndarray) -> dict:
    rank_ics = rank_ics[np.isfinite(rank_ics)]
    ics = ics[np.isfinite(ics)]
    if len(ics) < 3 or len(rank_ics) == 0:
        return dict(periods=0, rank_ic=None, ic_ir=None, win=None, s_i=None, direction=None)
    mean_rank = float(np.mean(rank_ics))
    mean_ic = float(np.mean(ics))
    std_ic = float(np.std(ics, ddof=1))
    direction = 1 if mean_ic >= 0 else 0
    win = float(np.mean(ics > 0.02)) if direction == 1 else float(np.mean(ics < -0.02))
    ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0
    return dict(periods=len(ics), rank_ic=mean_rank, ic_ir=ic_ir, win=win,
                s_i=abs(mean_rank) * abs(ic_ir) * win, direction=direction)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    install_shim()
    reference = reference_path()
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    factors = load_factors(reference)
    print(f"reference={reference} sha256={digest[:16]} factors={len(factors)}", flush=True)

    with PANELS.open("rb") as handle:
        payload = pickle.load(handle)
    panels = payload["panels"]
    close = panels["close"].loc[WARMUP_START:]
    calendar = close.index
    data = {name: frame.loc[WARMUP_START:] for name, frame in panels.items()}
    data["close"] = close
    print(f"panel={close.shape} ({calendar[0].date()}..{calendar[-1].date()})", flush=True)

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    signal_dates = [pd.Timestamp(value) for value in sorted(sf["date"].unique())]
    positions = {date: index for index, date in enumerate(calendar)}
    schedule = []
    forward_returns = {}
    for date in signal_dates:
        if date not in positions:
            continue
        current = positions[date] + 1
        future = current + CYCLE
        if future >= len(calendar):
            continue
        schedule.append(date)
        forward_returns[date] = (close.iloc[future] / close.iloc[current] - 1.0).to_numpy()
    print(f"signal dates={len(schedule)}", flush=True)

    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(schedule)].set_index(["date", "instrument"])

    rows = []
    failures = {}
    for name in sorted(factors):
        try:
            values = factors[name](data)
            if values is None:
                failures[name] = "returned None"
                continue
            values = values.loc[schedule]
        except Exception as exc:  # noqa: BLE001 - record and move on
            failures[name] = f"{type(exc).__name__}: {exc}"
            continue
        held = np.full(len(schedule), np.nan)
        gross = np.full(len(schedule), np.nan)
        turnover = np.full(len(schedule), np.nan)
        counts = np.zeros(len(schedule), dtype=np.int32)
        valid_flags = np.zeros(len(schedule), dtype=np.uint8)
        rank_ics = np.full(len(schedule), np.nan)
        ics = np.full(len(schedule), np.nan)
        previous: set[str] = set()
        for index, date in enumerate(schedule):
            factor_row = values.iloc[index].to_numpy(dtype="float64")
            forward = forward_returns[date]
            valid = np.isfinite(factor_row) & np.isfinite(forward)
            if valid.sum() < 100:
                continue
            x = factor_row[valid]
            y = forward[valid]
            if np.std(x) == 0 or np.std(y) == 0:
                continue
            instruments = values.columns.to_numpy()[valid]
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
        stats = ic_stats(rank_ics, ics)
        seat_like = pd.Series(values.to_numpy().ravel(), index=pd.MultiIndex.from_product(
            [values.index, values.columns]))
        correlations = {}
        merged = pd.DataFrame({"alpha": seat_like}).join(seat_frame, how="inner")
        for seat in POOL:
            correlations[seat] = float(
                merged.groupby(level=0).apply(lambda g: g["alpha"].corr(g[seat], method="spearman"))
                .mean()
            )
        rows.append(dict(
            factor=name, periods=stats["periods"], rank_ic=stats["rank_ic"], ic_ir=stats["ic_ir"],
            win=stats["win"], s_i=stats["s_i"], direction=stats["direction"],
            turnover=(summary["turnover_pct"] or 0.0) / 100.0,
            net_excess=summary["net_excess_pct"], gross_excess=summary["gross_excess_pct"],
            sharpe=summary["sharpe_after_cost"], max_dd=summary["max_drawdown_pct"],
            max_pool_corr=max(correlations.values()),
            corr_size=correlations[POOL[0]], corr_h03=correlations[POOL[1]],
            corr_t10=correlations[POOL[2]], corr_e=correlations[POOL[3]],
            corr_f=correlations[POOL[4]],
        ))
        if len(rows) % 20 == 0:
            print(f"  scored {len(rows)}", flush=True)
    frame = pd.DataFrame(rows).sort_values("s_i", ascending=False)
    frame.to_csv(OUT / "alpha191_local_screen.csv", index=False)
    (OUT / "reference_source.txt").write_text(
        f"url={REFERENCE_URL}\nsha256={digest}\nlocal_copy={reference}\n"
        f"factors_scored={len(frame)} failures={len(failures)}\n"
        + "\n".join(f"{k}: {v}" for k, v in sorted(failures.items())) + "\n",
        encoding="utf-8",
    )
    print(f"scored={len(frame)} failures={len(failures)}", flush=True)
    print(frame.head(20)[["factor", "s_i", "rank_ic", "ic_ir", "win", "turnover",
                          "net_excess", "max_pool_corr"]].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
