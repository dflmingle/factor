#!/usr/bin/env python3
"""新基底 × turn/vol 模板候选的池级全账（直接面板版，2026-09-29，零平台算力）。

背景：第五轮全 191 扫描（cycle=5）找到一批 .76-.78 ICIR 的新基底
（182/149/062/083/090/099/032/016…）。本脚本把它们与 turn 腿的混权信号
直接喂进 e_decomp_20260928 的池级逐月账本（6 席 = 现役 5 席 + 候选），
得到平台 literal 口径的 ΔE / ΔT / ΔNC / ΔA / ΔComb，以及候选自身
s_i（RankIC 序列）/ 内在换手 / corr_size。

与 e_decomp candidates 模式唯一差别：不做公式解析，候选面板直接由
本地 qfq 面板 + alpha191 参考实现 + turn 腿算出（同一全 A 宇宙/日期网格）。
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import pickle
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e_decomp_20260928 as ed  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402
import alphaprobe_gp_tushare as gp  # noqa: E402
import alpha191_ops_local as ops  # noqa: E402
from independent_information_combination import DATA_START, END  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/e-decomp-20260929"
T0 = time.time()
MEAN_S_PLAT = 0.025893        # 平台实测 5 席池侧 s_i 均值（.1295/5）
A_UNIT_POOLRULE = 40000.0 * 1.1 * 0.20 * 12.5 / 6.0   # 池侧公式：divA = 18333 x (s_i - .025893)


def log(m: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)


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
    for name in ("rolling_slope", "rolling_rsquare", "rolling_resi",
                 "expanding_slope", "expanding_rsquare", "expanding_resi"):
        setattr(qo, name, getattr(ops, name))
    sys.modules["qlib.data.ops"] = qo


def build_panels(market) -> dict:
    cache = OUT / "panels_cache.pkl"
    if cache.exists():
        log("panels from cache")
        return pickle.load(cache.open("rb"))
    frame = e.load_full_a_data(e.DEFAULT_PRICE_ROOT, e.DEFAULT_CAP_ROOT, DATA_START, END)
    frame = e.select_market_cap(frame, e.ALIGNMENT_MARKET_CAP_FIELD)
    frame = frame.sort_values(["instrument", "date"], ignore_index=True)
    cal = market.cal
    stocks = [str(x) for x in market.data._stock_ids]
    pv = lambda c: frame.pivot(index="date", columns="instrument", values=c) \
        .reindex(index=cal, columns=stocks).astype("float32")
    panels = dict(close=pv("close_qfq"), open=pv("open_qfq"), high=pv("high_qfq"),
                  low=pv("low_qfq"), volume=pv("volume"), amount=pv("amount"),
                  turn=pv("turnover"), mcap=pv("total_mv"))
    del frame
    gc.collect()
    panels["vwap"] = (panels["amount"] / panels["volume"] * 10.0).astype("float32")
    with cache.open("wb") as fh:
        pickle.dump(panels, fh, protocol=5)
    return panels


_RAW_LEG_CACHE: dict = {}


def get_raw_legs(panels: dict) -> dict:
    key = id(panels)
    if key not in _RAW_LEG_CACHE:
        from legmix_next_legs_20260929 import build_raw_legs
        _RAW_LEG_CACHE[key] = build_raw_legs(panels)
    return _RAW_LEG_CACHE[key]


def candidate_panel(spec: dict, panels: dict, funcs: dict) -> pd.Series:
    """Return long Series indexed by (date, instrument)."""
    if spec.get("base") == "composite":
        raw = get_raw_legs(panels)
        comp = None
        for leg, sign in spec["signed"].items():
            r = raw[leg].rank(axis=1, pct=True).astype("float32") * float(sign)
            comp = r if comp is None else comp + r
        return (comp / len(spec["signed"])).astype("float32")
    src = panels[spec["src"]]
    ratio = src.rolling(spec["k"]).std() / \
        src.rolling(spec["n"], min_periods=int(spec["n"] * 0.32)).std()
    rsm = int(spec.get("ratio_smooth", 1))
    if rsm > 1:
        ratio = ratio.rolling(rsm).mean()
    leg = 1.0 - ratio.rank(axis=1, pct=True)
    smooth = int(spec.get("smooth", 1))
    mode = spec.get("smooth_mode", "mix")
    base_rank = None
    if spec["base"] != "leg_only":
        fn = funcs[f"alpha191_{spec['base']}"]
        res = fn({k: panels[k] for k in ("close", "open", "high", "low",
                                         "volume", "amount", "vwap", "turn")})
        base_rank = res.rank(axis=1, pct=True)
    if smooth > 1 and mode == "leg":
        leg = leg.rolling(smooth).mean()
    if smooth > 1 and mode == "base" and base_rank is not None:
        base_rank = base_rank.rolling(smooth).mean()
    if spec["base"] == "leg_only":
        mixed = leg
    else:
        mixed = spec["w"] * base_rank + (1.0 - spec["w"]) * leg
    if smooth > 1 and mode == "mix":
        mixed = mixed.rolling(smooth).mean()
    return mixed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", type=Path, default=None,
                    help="JSON list of {name, base, src, k, n, w}")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--save-daily", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.specs is not None:
        specs = json.loads(args.specs.read_text(encoding="utf-8"))
    else:
        specs = []
        for base in ("182", "149", "062", "083", "090", "099", "032", "016", "010", "042"):
            specs.append(dict(name=f"a{base}_turn5x750_w10", base=base,
                              src="turn", k=5, n=750, w=0.1))
        for base in ("149", "182", "083"):
            specs.append(dict(name=f"a{base}_turn6x504_w20", base=base,
                              src="turn", k=6, n=504, w=0.2))
        specs.append(dict(name="leg_turn5x750_only", base="leg_only",
                          src="turn", k=5, n=750, w=1.0))

    install_shim()
    ns: dict = {}
    ref = ROOT / ".cache/third_party/alpha191_reference.py"
    exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
    funcs = {k: v for k, v in ns.items() if k.startswith("alpha191_") and callable(v)}

    payload = pickle.load(open(ed.DEFAULT_REBUILD, "rb"))
    device = torch.device("cpu")
    market = ed.Market(payload, device)
    log("market ready")

    # ---- seed (5 seat) ledger ----
    keys = ed.POOL + ["cand"]
    seed_frame = market.seats.loc[:, ed.POOL]
    blocks_seed, offsets_seed, fs_seed, fr_seed = market.make_blocks(seed_frame, ed.POOL)
    seed_ledger = market.scenario_ledger(blocks_seed, offsets_seed, fs_seed, fr_seed,
                                         np.ones(len(ed.POOL), dtype=np.int64))
    seed_curve = market.build_daily(seed_ledger)
    seed_table = market.monthly_table(seed_curve, seed_ledger)
    log(f"[seed] E={seed_table.e_term.mean():.4f} NC={seed_table.nc.mean():.3f} "
        f"T={seed_table.turnover_month.mean():.3f}")

    panels = build_panels(market)
    log("panels ready")

    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]
    signal_dates = set(pd.Timestamp(x) for x in market.dates)
    cap_signal = panels["mcap"].reindex(index=[d for d in eval_dates if d in signal_dates])

    summary_rows, failures = [], []
    for spec in specs:
        name = spec["name"]
        try:
            mixed = candidate_panel(spec, panels, funcs)
        except Exception as exc:  # noqa: BLE001
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            log(f"[{name}] PANEL FAIL {exc}"[:160])
            continue
        panel = mixed.reindex(index=eval_dates, columns=stocks).astype("float32")
        arr = panel.to_numpy()
        values = torch.from_numpy(arr.copy())
        with torch.no_grad():
            stats = ed.rank_ic_stats(market.context, values)
        chosen = 1
        if not stats or stats["rank_ic"] < 0:
            with torch.no_grad():
                stats_neg = ed.rank_ic_stats(market.context, -values)
            if stats_neg and (not stats or stats_neg["rank_ic"] > stats["rank_ic"]):
                stats, chosen = stats_neg, -1
        if not stats:
            failures.append((name, "no stats"))
            continue
        oriented = panel if chosen == 1 else -panel
        finite_share = float(np.isfinite(arr).mean())
        # corr_size on signal dates
        cs_vals = []
        for d in cap_signal.index:
            a = oriented.loc[d].to_numpy(dtype="float64") if d in oriented.index else None
            if a is None:
                continue
            b = cap_signal.loc[d].to_numpy(dtype="float64")
            m = np.isfinite(a) & np.isfinite(b)
            if m.sum() < 200:
                continue
            ar = pd.Series(a[m]).rank().to_numpy(); br = pd.Series(b[m]).rank().to_numpy()
            cs_vals.append(float(np.corrcoef(ar, br)[0, 1]))
        corr_size = float(np.mean(cs_vals)) if cs_vals else np.nan

        flat = oriented.stack(dropna=False).reindex(market.signal_index)
        cand_score = e._competition_cross_sectional_scores(
            market.signal_frame, {"cand": flat},
            [{"key": "cand", "handler": "cand", "direction": 1}])
        swap = spec.get("swap")
        if swap:
            keep = [k2 for k2 in ed.POOL if k2 != swap]
            score_frame = pd.concat([market.seats.loc[:, keep], cand_score], axis=1) \
                .loc[:, keep + ["cand"]]
            keys2 = keep + ["cand"]
        else:
            score_frame = pd.concat([market.seats, cand_score], axis=1).loc[:, keys]
            keys2 = keys
        blocks, offsets, fs, fr = market.make_blocks(score_frame, keys2)
        six_ledger = market.scenario_ledger(blocks, offsets, fs, fr,
                                            np.ones(len(keys2), dtype=np.int64))
        six_curve = market.build_daily(six_ledger)
        six_table = market.monthly_table(six_curve, six_ledger)

        merged = seed_table.merge(six_table, on=["year", "month"], suffixes=("_seed", "_six"))
        merged["d_e"] = merged.e_term_six - merged.e_term_seed
        merged["d_t"] = merged.turnover_month_six - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_six - merged.nc_seed
        merged["d_c_points"] = 44000.0 * ed.W_C * merged.d_nc
        merged.to_csv(args.out / f"cand_monthly_{name}.csv", index=False,
                      encoding="utf-8-sig")
        if args.save_daily:
            pd.DataFrame({"seed": seed_curve["portfolio"],
                          "six": six_curve["portfolio"]}).to_csv(
                args.out / f"cand_daily_{name}.csv", encoding="utf-8-sig")

        s_local = stats["s_i_rank"]
        if swap:
            # platform-measured seat s_i (a-basis-correction-20260926);
            # impact60 = H03-T10 (.0180), bm_plus = VERIFY10-F (.0221)
            seat_si = {"size_only": 0.00914, "impact60": 0.01798,
                       "t10_size_plus_impact_bm": 0.05927,
                       "book_to_market_lf_minus_size": 0.02101,
                       "book_to_market_lf_plus_impact": 0.02207}[swap]
            unit5 = 0.20 / (5 * 0.08) * 44000.0
            d_a_local = unit5 * (s_local - seat_si)
            d_a_uplift = unit5 * ed.UPLIFT * (s_local - seat_si)
        else:
            d_a_local = ed.A_UNIT * (s_local - ed.MEAN_S_LOCAL)
            d_a_uplift = ed.A_UNIT * ed.UPLIFT * (s_local - ed.MEAN_S_LOCAL)
        d_c = float(merged.d_c_points.mean())
        d_a_poolrule = A_UNIT_POOLRULE * (s_local - MEAN_S_PLAT)
        row = dict(name=name, base=spec["base"], src=spec.get("src", "composite"),
                   k=spec.get("k", 0), n=spec.get("n", 0), w=spec.get("w", 1.0),
                   direction=chosen, swap=swap or "none",
                   finite_share=finite_share, rank_ic=stats["rank_ic"],
                   ic_ir=stats["rank_ic_ir"], win=stats["rank_ic_win"],
                   s_i_local=s_local, corr_size=corr_size,
                   turn_intrinsic=float(six_ledger.turnover[six_ledger.valid].mean()),
                   turn_pool_seed=float(seed_ledger.turnover[seed_ledger.valid].mean()),
                   d_e_mean=float(merged.d_e.mean()), d_e_median=float(merged.d_e.median()),
                   d_t_mean=float(merged.d_t.mean()), d_nc_mean=float(merged.d_nc.mean()),
                   d_c_points=d_c, d_a_points_local=d_a_local,
                   d_a_points_uplift=d_a_uplift, d_comb_uplift=d_a_uplift + d_c,
                   d_a_poolrule=d_a_poolrule, d_comb_poolrule=d_a_poolrule + d_c,
                   pos_months=int((merged.d_c_points > 0).sum()), months=len(merged))
        summary_rows.append(row)
        log(f"[{name}] s_i={s_local:.4f} corrSz={corr_size:+.2f} dE={row['d_e_mean']:+.4f} "
            f"dT={row['d_t_mean']:+.3f} dNC={row['d_nc_mean']:+.4f} "
            f"dC={d_c:+,.0f} dComb_up={row['d_comb_uplift']:+,.0f}")
        del panel, arr, values, flat, cand_score, score_frame, blocks, fs, fr
        gc.collect()

    if summary_rows:
        summary = pd.DataFrame(summary_rows).sort_values("d_comb_uplift", ascending=False)
        summary.to_csv(args.out / "cand_summary_direct.csv", index=False,
                       encoding="utf-8-sig")
        pd.set_option("display.width", 250)
        print("\n== 直接面板候选池级全账（6 席 vs 5 席）==")
        print(summary.round(4).to_string(index=False))
    if failures:
        print("\n失败:", failures)
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
