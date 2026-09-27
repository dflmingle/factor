"""A/B 批次：现役 5 席面板本地重建（零平台算力）。

背景：`pool-screen-20260921-qualitygate3/signals.pkl` 与
`pool-extended-search-20260922/built_signals.pkl` 不在本机（.gitignore 忽略 *.pkl，
handoff_20260924 列为需直拷或重建的缓存）。本脚本只重建 A/B 批次真正需要的部分：
现役 5 席的横截面 Z 分数、signal frame 与 forward returns，写到带 provenance 的
新文件，不冒充原 228 MB 大缓存、不覆盖任何既有产物。

口径与 scripts/prescreen_extended_members_20260922.py::build_members 一致：
同一 full-A/qfq/total_mv 面板、同一 cycle-10 信号日、同一 Winsorize(1%,99%)+Z-score。
方向与平台净额取自本机 qualitygate1 全量对齐报告（该报告与本机数据缓存同代）。
"""
from __future__ import annotations

import gc
import io
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402
from financial_factor_local import load_financial_cache  # noqa: E402
from independent_information_combination import DATA_START, END, build_schedules  # noqa: E402
from positive_factor_local_compare import formula_catalog, saved_records  # noqa: E402
from stfilter_local_recheck import ensure_calendar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/ab-batch-20260925"
CACHE = OUT / "seat_panels_rebuilt.pkl"
VALIDATION = OUT / "seat_rebuild_validation.csv"
CATALOG = (
    ROOT
    / "quantlab/.quantlab/cache/research/cn_equity/reports/"
    "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"
    "turnoverdiag1_qualitygate1/all_factor_local_compare.json"
)
SEATS = [
    "size_only",
    "impact60",
    "t10_size_plus_impact_bm",
    "book_to_market_lf_minus_size",
    "book_to_market_lf_plus_impact",
]
PLATFORM_REFERENCE = {
    "size_only": 21.433288,
    "impact60": 16.443256,
    "t10_size_plus_impact_bm": 18.09228,
    "book_to_market_lf_minus_size": 16.74068,
    "book_to_market_lf_plus_impact": 15.046176,
}
POOL_REFERENCE = dict(net_excess_pct=20.30, turnover_pct=13.39, sharpe_after_cost=1.0648,
                      max_drawdown_pct=31.64, rank_ic=0.0919, ic_ir=0.3675,
                      record="F-P260922-08")


def seat_specs() -> list[dict]:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))["results"]
    specs = []
    for handler in SEATS:
        pool = [
            r
            for r in rows
            if r.get("handler") == handler
            and int(r.get("cycle") or 0) == e.COMMON_CYCLE
            and r.get("local_mining_eligible")
        ]
        if not pool:
            raise RuntimeError(f"no eligible cycle-10 record for {handler}")
        best = max(pool, key=lambda r: r.get("platform_net_excess_pct") or -99.0)
        specs.append(
            dict(
                key=handler,
                handler=handler,
                direction=int(float(best.get("platform_factor_direction") or 1)),
                name=best.get("name"),
                platform_net=float(best.get("platform_net_excess_pct")),
                alignment_quality=best.get("alignment_quality"),
            )
        )
    return specs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    specs = seat_specs()
    for spec in specs:
        print(
            f"seat {spec['key']:<32} dir={spec['direction']} name={spec['name']} "
            f"plat_net={spec['platform_net']:.2f} quality={spec['alignment_quality']}",
            flush=True,
        )

    calendar = [pd.Timestamp(x).normalize() for x in ensure_calendar(DATA_START, END, token=None)]
    supported, _ = saved_records(formula_catalog(), "positive")
    dates = build_schedules(supported, calendar)[e.COMMON_CYCLE]
    print(f"signal dates {dates[0].date()}..{dates[-1].date()} ({len(dates)})", flush=True)

    print("loading full-A panel", flush=True)
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, DATA_START, END)
    frame = e.select_market_cap(frame, e.ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    mask = frame["date"].isin(dates)
    signal_frame = frame.loc[mask, ["date", "instrument"]].reset_index(drop=True)
    print(f"panel rows {len(frame)} signal rows {len(signal_frame)}", flush=True)

    close = e.panel_close(frame, calendar)
    returns = e.forward_returns(close, calendar, dates, e.COMMON_CYCLE, e.LABEL_OFFSET)
    del close
    gc.collect()

    financial = load_financial_cache(e.DEFAULT_FINANCIAL_ROOT)
    raw: dict[str, pd.Series] = {}
    for spec in specs:
        handler = spec["handler"]
        values = e.build_factor(frame, handler, financial=financial, signal_dates=dates)
        series = pd.to_numeric(values.loc[mask].reset_index(drop=True), errors="coerce")
        raw[handler] = series
        print(f"  built {handler:<32} finite_share={float(np.isfinite(series.to_numpy()).mean()):.4f}", flush=True)
        del values
        gc.collect()

    scores = e._competition_cross_sectional_scores(signal_frame, raw, specs)
    keys = [spec["key"] for spec in specs]
    blocks = e._build_blocks(signal_frame, scores, returns, dates, keys)
    ds, offsets, fs, fr, fi, _ = e._flatten_blocks(blocks, len(keys))
    full_window = np.ones(len(ds), dtype=bool)

    def evaluate(selection: tuple[int, ...]) -> tuple[dict, float, float]:
        combo = np.zeros(len(keys), dtype=bool)
        combo[list(selection)] = True
        held, gross, turn, counts, valid = e._evaluate_combinations_numba(
            fs, fr, fi, offsets, combo.reshape(1, -1), np.array([len(selection)], dtype=np.int64)
        )
        summary = e._summary(
            held[0], gross[0], turn[0], counts[0], valid[0].astype(bool),
            ds, e.COMMON_CYCLE, "full", full_window,
        )
        rank_ic, ic = e._exact_period_ics(selection, blocks)
        rank_ic = rank_ic[np.isfinite(rank_ic)]
        ic = ic[np.isfinite(ic)]
        ic_ir = float(ic.mean() / ic.std(ddof=1)) if len(ic) > 2 and ic.std(ddof=1) > 0 else float("nan")
        return summary, float(rank_ic.mean()) if len(rank_ic) else float("nan"), ic_ir

    rows = []
    for index, spec in enumerate(specs):
        summary, rank_ic, ic_ir = evaluate((index,))
        rows.append(
            dict(
                key=spec["key"],
                name=spec["name"],
                direction=spec["direction"],
                platform_net_excess_pct=spec["platform_net"],
                local_net_excess_pct=summary["net_excess_pct"],
                delta_pp=(summary["net_excess_pct"] or 0.0) - spec["platform_net"],
                turnover_pct=summary["turnover_pct"],
                sharpe_after_cost=summary["sharpe_after_cost"],
                max_drawdown_pct=summary["max_drawdown_pct"],
                rank_ic=rank_ic,
                ic_ir=ic_ir,
                periods=summary["periods"],
                reference=PLATFORM_REFERENCE.get(spec["key"]),
            )
        )

    pool_summary, pool_rank_ic, pool_ic_ir = evaluate(tuple(range(len(keys))))
    validation = pd.DataFrame(rows)
    validation.to_csv(VALIDATION, index=False)
    print(validation.to_string(index=False), flush=True)
    print(
        "pool: net={:.2f} turnover={:.2f} sharpe={:.4f} maxdd={:.2f} rankIC={:.4f} icIR={:.4f}".format(
            pool_summary["net_excess_pct"], pool_summary["turnover_pct"],
            pool_summary["sharpe_after_cost"], pool_summary["max_drawdown_pct"],
            pool_rank_ic, pool_ic_ir,
        ),
        flush=True,
    )
    print(f"pool reference {POOL_REFERENCE}", flush=True)

    payload = dict(
        built=specs,
        scores=scores,
        signal_frame=signal_frame,
        returns=returns,
        dates=dates,
        raw=raw,
        pool_summary=pool_summary,
        provenance=dict(
            rebuilt_on="local D:/factor (15.4 GB RAM machine)",
            source_catalog=str(CATALOG.relative_to(ROOT)),
            source_rule_version=json.loads(CATALOG.read_text(encoding="utf-8"))["settings"].get(
                "alignment_rule_version"
            ),
            handlers=SEATS,
            reason="canonical signals.pkl / built_signals.pkl absent locally (gitignored, see handoff_20260924)",
            equivalent_to="prescreen_extended_members_20260922.build_members (5 of 54 members only)",
        ),
    )
    with CACHE.open("wb") as handle:
        pickle.dump(payload, handle)
    print(f"written: {CACHE} ({CACHE.stat().st_size / 1e6:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())