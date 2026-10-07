# -*- coding: utf-8 -*-
"""整池账（2026-10-04，零平台算力）：同族强腿 + 已测强席拼成 5 席池 vs 现役。

回答：整池换席后 NA 能从 .3237 推到多少、C 段代价多大、B 段怎么算。
- A 段：平台实测 s_i（K10 .0673 / K20 .0527 / TOPMIX .0610 / STD20 .0557 / AMTDISP .0505）
- C 段：e_decomp 官方月度账本（dE/dT/dNC/dC，cycle 10、120 期、60 月）
- B 段：稳态代理 d_raw_a/0.06*15400，单列；首期稀释见报告
- 规则②：池级 corr_size 与 size 中性化净额（pool_seat_rescreen_20260924 同口径）

用法：
  D:\\anaconda3\\envs\\easyrl4rec\\python.exe scripts/_poolmix_ledger_20261004.py
"""
from __future__ import annotations

import gc
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import e_decomp_20260928 as ed  # noqa: E402

ed.DEFAULT_REBUILD = (ROOT / "research_reports" / "platform_alignment"
                      / "ab-batch-20260925" / "seat_panels_rebuilt.pkl")

import alphagen_pool_optimize_20261002 as apo  # noqa: E402
import caltech_legs_20261003 as ct  # noqa: E402
import exhaustive_representative_combination as e  # noqa: E402
import pool_seat_rescreen_20260924 as R  # noqa: E402

OUT = ROOT / "research_reports" / "platform_alignment" / "pool-family-20261004"
T0 = time.time()

PLAT_SI = {
    "size_only": 0.009135508656026116,
    "impact60": 0.017982594724007532,
    "book_to_market_lf_minus_size": 0.021011254255464188,
    "book_to_market_lf_plus_impact": 0.022068061621976547,
    "t10_size_plus_impact_bm": 0.05926662119415439,
    "K10": 0.0673, "K20": 0.0527, "TOPMIX": 0.0610,
    "STD20": 0.0557, "AMTDISP": 0.0505,
}
SEED_MEAN = float(np.mean([PLAT_SI[k] for k in ed.POOL]))
NA_NOW = min(SEED_MEAN / 0.08, 0.70)
A_UNIT = 8800.0  # points per +1.0 NA (0.20 * 40000 * 1.10)

# 池阶梯：seat 键 = 现役列名（ed.POOL 元素）或候选名（K10/K20/TOPMIX/STD20/AMTDISP/FAM*）
POOLS_FIXED = [
    ("L1_swapF_K10", ["t10_size_plus_impact_bm", "book_to_market_lf_minus_size",
                      "impact60", "size_only", "K10"]),
    ("L2_keep_size", ["t10_size_plus_impact_bm", "size_only", "K10", "TOPMIX", "STD20"]),
    ("L2c_keep_impact60", ["t10_size_plus_impact_bm", "impact60", "K10", "TOPMIX", "STD20"]),
    ("L5_keep_t10", ["t10_size_plus_impact_bm", "K10", "TOPMIX", "STD20", "AMTDISP"]),
    ("L6_keep_t10_lowturn", ["t10_size_plus_impact_bm", "K10", "K20", "STD20", "AMTDISP"]),
    ("L4_all_new", ["K10", "K20", "TOPMIX", "STD20", "AMTDISP"]),
]
FAMILY_COMPOSITES = {
    "fam_vol": ["vs250", "vs500", "vs756"],
    "fam_disp": ["tstd20_60", "vstd10_60"],
    "fam_retdisp": ["rstd20_60", "amp20"],
    "fam_mixvol": ["vs756", "tstd20_60", "rstd20_60"],
    "fam_mix3": ["vs250", "tstd20_60", "vstd10_60"],
}


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def family_legs(panels: dict) -> dict:
    """混权/volstab 同族腿（与 legmix_next_legs_20260929.build_raw_legs 同定义）。"""
    C = panels["close"].astype("float32")
    O = panels["open"].astype("float32")
    H = panels["high"].astype("float32")
    L = panels["low"].astype("float32")
    V = panels["volume"].astype("float32")
    A = panels["amount"].astype("float32")
    T = (panels["turn"] if "turn" in panels else panels["turnover"]).astype("float32")
    vwap = panels["vwap"].astype("float32") if "vwap" in panels else (A * 10.0 / V)
    ret1 = C.pct_change(fill_method=None)
    legs = {}
    legs["amt60"] = -A.rolling(60).mean()
    legs["intr20"] = -((C - O) / O).rolling(20).mean()
    legs["amihud20"] = -(ret1.abs() / A).rolling(20).mean()
    legs["t_lvl"] = -T
    legs["drift20"] = -((C - vwap) / vwap).rolling(20).mean()
    legs["vs250"] = -(V.rolling(6).std() / V.rolling(250).std())
    legs["vs500"] = -(V.rolling(6).std() / V.rolling(500).std())
    legs["vs756"] = -(V.rolling(6).std() / V.rolling(756).std())
    legs["tstd20_60"] = -(T.rolling(20).std() / T.rolling(60).std())
    legs["vstd10_60"] = -(V.rolling(10).std() / V.rolling(60).std())
    legs["rstd20_60"] = -(ret1.rolling(20).std() / ret1.rolling(60).std())
    legs["amp20"] = -(H.rolling(20).max() / L.rolling(20).min() - 1.0)
    return legs


def rank_mean(legs: dict, names: list) -> pd.DataFrame:
    comp = None
    for name in names:
        r = legs[name].rank(axis=1, pct=True).astype("float32")
        comp = r if comp is None else comp + r
    return (comp / float(len(names))).astype("float32")

def build_candidates(panels: dict, eval_dates, stocks) -> dict:
    cands = {}
    cands["K10"] = apo.lamd10_k5v2_slice(panels, eval_dates, stocks)
    log("K10 built")
    legs = family_legs(panels)
    signed = {"amt60": 1.0, "t_lvl": 1.0, "amihud20": -1.0, "intr20": 1.0, "drift20": 1.0}
    comp = None
    for name, sign in signed.items():
        r = (float(sign) * legs[name]).rank(axis=1, pct=True).astype("float32")
        comp = r if comp is None else comp + r
    cands["K20"] = (comp / float(len(signed))).reindex(
        index=eval_dates, columns=stocks).astype("float32")
    del comp
    gc.collect()
    log("K20 built")
    for name, members in FAMILY_COMPOSITES.items():
        cands[name] = rank_mean(legs, members).reindex(
            index=eval_dates, columns=stocks).astype("float32")
    del legs
    gc.collect()
    log("family composites built")
    ct_legs = ct.build_caltech_legs(panels)
    for src, name in (("ct_comp_topmix", "TOPMIX"), ("ct_amt_std20", "STD20"),
                      ("ct_comp_amtdisp", "AMTDISP")):
        cands[name] = ct_legs[src].reindex(index=eval_dates, columns=stocks).astype("float32")
    del ct_legs
    gc.collect()
    log("caltech seats built")
    return cands


def make_score_column(frame: pd.DataFrame, market, eval_dates, stocks, name: str):
    """Winsorize/Z-score 注入 + 方向定向（同 e_decomp_direct 口径）。"""
    panel = frame.reindex(index=eval_dates, columns=stocks).astype("float32")
    values = torch.from_numpy(panel.to_numpy().copy())
    with torch.no_grad():
        stats = ed.rank_ic_stats(market.context, values)
    chosen = 1
    if not stats or stats["rank_ic"] < 0:
        with torch.no_grad():
            stats_neg = ed.rank_ic_stats(market.context, -values)
        if stats_neg and (not stats or stats_neg["rank_ic"] > stats["rank_ic"]):
            stats, chosen = stats_neg, -1
    if chosen == -1:
        panel = (-panel).astype("float32")
    flat = panel.stack(dropna=False).reindex(market.signal_index)
    score = e._competition_cross_sectional_scores(
        market.signal_frame, {"cand": flat},
        [{"key": "cand", "handler": "cand", "direction": 1}])
    return score["cand"].rename(name), stats, chosen

def main() -> int:
    apo.start_watchdog()
    OUT.mkdir(parents=True, exist_ok=True)

    payload = pickle.load(ed.DEFAULT_REBUILD.open("rb"))
    log(f"payload scores {payload['scores'].shape} dates {len(payload['dates'])}")
    market = ed.Market(payload, torch.device("cpu"))
    log("market ready")
    panels = apo.build_panels_local(market)
    log("panels ready")
    eval_dates = [pd.Timestamp(x) for x in market.data._evaluation_dates]
    stocks = [str(x) for x in market.data._stock_ids]
    sig_dates = [pd.Timestamp(x) for x in market.dates]

    cands = build_candidates(panels, eval_dates, stocks)
    cand_scores, seat_rows = {}, []
    for name, frame in sorted(cands.items()):
        score, stats, chosen = make_score_column(frame, market, eval_dates, stocks, name)
        cand_scores[name] = score
        seat_rows.append(dict(seat=name, s_i_local=stats["s_i_rank"],
                              rank_ic=stats["rank_ic"], ic_ir=stats["rank_ic_ir"],
                              win=stats["rank_ic_win"], direction=chosen,
                              s_i_plat=PLAT_SI.get(name, float("nan"))))
        log(f"[seat {name}] local s_i={stats['s_i_rank']:.4f} ric={stats['rank_ic']:+.4f} "
            f"icir={stats['rank_ic_ir']:.3f} win={stats['rank_ic_win']:.3f} dir={chosen:+d}")
        del frame
        gc.collect()
    fam_rank = sorted((r for r in seat_rows if r["seat"].startswith("fam_")),
                      key=lambda r: -r["s_i_local"])
    for idx, r in enumerate(fam_rank, start=1):
        PLAT_SI[f"FAM{idx}"] = float("nan")
        cand_scores[f"FAM{idx}"] = cand_scores[r["seat"]]
    pd.DataFrame(seat_rows).to_csv(OUT / "seat_stats.csv", index=False, encoding="utf-8-sig")
    pools = list(POOLS_FIXED)
    pools.append(("L7_family_mix",
                  ["t10_size_plus_impact_bm", "K10", "STD20", "FAM1", "FAM2"]))
    pools.append(("L8_family_pure", ["FAM1", "FAM2", "FAM3", "FAM4", "FAM5"]))
    log(f"family ranking: {[ (r['seat'], round(r['s_i_local'],4)) for r in fam_rank ]}")
    seed_frame = market.seats.loc[:, ed.POOL]
    b_s, o_s, fs_s, fr_s = market.make_blocks(seed_frame, ed.POOL)
    seed_ledger = market.scenario_ledger(b_s, o_s, fs_s, fr_s,
                                         np.ones(len(ed.POOL), dtype=np.int64))
    seed_curve = market.build_daily(seed_ledger)
    seed_table = market.monthly_table(seed_curve, seed_ledger)
    seed_turn = float(seed_ledger.turnover[seed_ledger.valid].mean())
    log(f"[seed] E={seed_table.e_term.mean():.4f} NC={seed_table.nc.mean():.3f} "
        f"T/month={seed_table.turnover_month.mean():.3f} turn/reb={seed_turn:.4f}")

    rows_rows = pd.DataFrame({"d": market.signal_frame["date"].to_numpy(),
                              "i": market.signal_frame["instrument"].to_numpy(),
                              "v": payload["scores"]["size_only"].to_numpy()})
    size_axis = rows_rows.pivot_table(index="d", columns="i", values="v").reindex(index=sig_dates)
    forward_wide = (payload["returns"]
                    .pivot_table(index="date", columns="instrument", values="forward_return")
                    .reindex(index=sig_dates, columns=size_axis.columns))
    del rows_rows
    gc.collect()

    def size_guard(score_flat: pd.Series):
        frame = pd.DataFrame({"d": market.signal_frame["date"].to_numpy(),
                              "i": market.signal_frame["instrument"].to_numpy(),
                              "v": np.asarray(score_flat, dtype=float)})
        wide = frame.pivot_table(index="d", columns="i", values="v").reindex(
            index=sig_dates, columns=size_axis.columns)
        return (float(R.daily_rank_corr(wide, size_axis)),
                float(R.bucket_neutral_net(wide, size_axis, forward_wide)))

    seed_corr, seed_neutral = size_guard(seed_frame.mean(axis=1))
    log(f"[seed rule2] corr_size={seed_corr:+.3f} size_neutral_net={seed_neutral:+.4f}")

    summary_rows = []
    for name, keys in pools:
        missing = [k for k in keys if k not in cand_scores and k not in market.seats.columns]
        if missing:
            log(f"[{name}] SKIP missing {missing}")
            continue
        cols = {}
        for k in keys:
            cols[k] = cand_scores[k] if k in cand_scores else market.seats[k]
        frame = pd.DataFrame(cols)
        keys5 = list(frame.columns)
        b, o, fs, fr = market.make_blocks(frame, keys5)
        led = market.scenario_ledger(b, o, fs, fr, np.ones(len(keys5), dtype=np.int64))
        curve = market.build_daily(led)
        table = market.monthly_table(curve, led)
        merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_p"))
        merged["d_e"] = merged.e_term_p - merged.e_term_seed
        merged["d_t"] = merged.turnover_month_p - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_p - merged.nc_seed
        merged["d_c_points"] = 44000.0 * ed.W_C * merged.d_nc
        merged.to_csv(OUT / f"pool_monthly_{name}.csv", index=False, encoding="utf-8-sig")

        si = np.array([PLAT_SI.get(k, np.nan) for k in keys5], dtype=float)
        if np.all(np.isfinite(si)):
            raw_new = float(si.mean())
            na_new = min(raw_new / 0.08, 0.70)
            d_a = (na_new - NA_NOW) * A_UNIT
            raw_delta = raw_new - SEED_MEAN
            d_b = raw_delta / 0.06 * 15400.0
        else:
            raw_new, na_new, d_a, raw_delta, d_b = (float("nan"),) * 5
        d_c = float(merged.d_c_points.mean())
        corr, neutral = size_guard(frame.mean(axis=1))
        row = dict(pool=name, seats="|".join(keys5), raw_a_new=raw_new, na_new=na_new,
                   d_a_points=d_a, d_c_points=d_c, d_comb_ac=d_a + d_c,
                   d_b_steady_proxy=d_b,
                   d_e_mean=float(merged.d_e.mean()),
                   d_t_mean=float(merged.d_t.mean()),
                   d_nc_mean=float(merged.d_nc.mean()),
                   turn_per_reb=float(led.turnover[led.valid].mean()),
                   nc_mean=float(table.nc.mean()),
                   corr_size=corr, size_neutral_net=neutral,
                   d_corr_size=corr - seed_corr, d_neutral=neutral - seed_neutral,
                   pos_c_months=int((merged.d_c_points > 0).sum()), months=len(merged))
        summary_rows.append(row)
        log(f"[{name}] raw_a={raw_new:.5f} na={na_new:.4f} dA={d_a:+,.0f} "
            f"dE={row['d_e_mean']:+.4f} dT={row['d_t_mean']:+.3f} dNC={row['d_nc_mean']:+.4f} "
            f"dC={d_c:+,.0f} dComb_AC={row['d_comb_ac']:+,.0f} "
            f"turn/reb={row['turn_per_reb']:.4f} corrSize={corr:+.3f} neutralNet={neutral:+.4f}")
        del frame, b, o, fs, fr, led, curve, table, merged
        gc.collect()
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "pool_summary.csv", index=False, encoding="utf-8-sig")
    meta = dict(payload=str(ed.DEFAULT_REBUILD), seed_mean_si=SEED_MEAN, na_now=NA_NOW,
                plat_si=PLAT_SI, family_legend={f"FAM{i}": r["seat"] for i, r in
                                                enumerate(fam_rank, start=1)},
                seed_turn_per_reb=seed_turn, seed_corr_size=seed_corr,
                seed_size_neutral_net=seed_neutral)
    (OUT / "ledger_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pd.set_option("display.width", 260)
    print(summary.round(4).to_string(index=False))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())