# -*- coding: utf-8 -*-
"""加 T10 同族变体席的整池账（2026-10-08，零平台算力）。

背景：平台 A 段 = 席位 s_i 的算术平均（已用 8 池精确验证），名单席位上限 50。
榜单 21+ 池普遍用"多席位近变体"抬高 na。本地问题：把已在平台实测过的
T10-ADD-* 变体（s_i .043~.060、与 T10 corr ≥.93）加到现役 5 席池，
A/B 段换来的分数与 C 段代价（E/T/NC）如何。

输出: research_reports/platform_alignment/board-higha-20261008/na_add/
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
import pool_seat_rescreen_20260924 as R  # noqa: E402

OUT = ROOT / "research_reports/platform_alignment/board-higha-20261008/na_add"
T0 = time.time()

SEED = list(ed.POOL)  # 5 incumbent seats
VARIANTS = {
    "t10_size_plus_impact_fscore": 0.0584035301868856,   # T10-ADD-FSCORE
    "t10_nomcap_plus_impact": 0.0594535157177357,        # T10-NOMCAP-PLUS-IMPACT
    "t10_size_plus_impact": 0.0523365081526699,          # T10-SIZE-PLUS-IMPACT
    "t10_size_plus_impact_wc": 0.0482820608359937,       # T10-SIZE-PLUS-WC-MCAP
    "t10_size_plus_impact_downside": 0.0462558584350375, # T10-ADD-DOWNSIDE-IMPACT
    "t10_size_plus_impact_dd120": 0.0455535747717762,    # T10-ADD-DD120
    "t10_size_plus_impact_aggregate": 0.0452778095698734,# T10-ADD-AGG-IMPACT
    "t10_size_plus_impact_g13": 0.043116047130144,       # T10-ADD-G13
}
PLAT_SI = {
    "size_only": 0.009135508656026116,
    "impact60": 0.017982594724007532,
    "book_to_market_lf_minus_size": 0.021011254255464188,
    "book_to_market_lf_plus_impact": 0.022068061621976547,
    "t10_size_plus_impact_bm": 0.05926662119415439,
    **VARIANTS,
}
SEED_MEAN = float(np.mean([PLAT_SI[k] for k in SEED]))
NA_NOW = min(SEED_MEAN / 0.08, 0.70)
A_UNIT = 8800.0

POOLS_FIXED = [
    ("Z1_add_agg", SEED + ["t10_size_plus_impact_aggregate"]),
    ("Z2_add_agg_downside", SEED + ["t10_size_plus_impact_aggregate",
                                    "t10_size_plus_impact_downside"]),
    ("Z3_add_agg_downside_g13", SEED + ["t10_size_plus_impact_aggregate",
                                        "t10_size_plus_impact_downside",
                                        "t10_size_plus_impact_g13"]),
    ("A1_add_fscore", SEED + ["t10_size_plus_impact_fscore"]),
    ("A2_add_fscore_nomcap", SEED + ["t10_size_plus_impact_fscore",
                                     "t10_nomcap_plus_impact"]),
    ("A3_add3_hi", SEED + ["t10_size_plus_impact_fscore", "t10_nomcap_plus_impact",
                           "t10_size_plus_impact"]),
    ("A4_add4_hi", SEED + ["t10_size_plus_impact_fscore", "t10_nomcap_plus_impact",
                           "t10_size_plus_impact", "t10_size_plus_impact_wc"]),
    ("A5_add3_mid", SEED + ["t10_size_plus_impact_fscore",
                            "t10_size_plus_impact_downside",
                            "t10_size_plus_impact_aggregate"]),
    ("A6_add5_farm", SEED + ["t10_size_plus_impact_downside",
                             "t10_size_plus_impact_aggregate",
                             "t10_size_plus_impact_dd120",
                             "t10_size_plus_impact_g13",
                             "t10_size_plus_impact_wc"]),
    ("A7_add8_farm", SEED + list(VARIANTS)),
]


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = pickle.load(ed.DEFAULT_REBUILD.open("rb"))
    ext = pickle.load((ROOT / "research_reports/platform_alignment/"
                       "pool-extended-search-20260922/built_signals.pkl").open("rb"))["scores"]
    for key in VARIANTS:
        assert key in ext.columns, key
    assert payload["scores"].index.equals(ext.index)
    extended = pd.concat([payload["scores"], ext[list(VARIANTS)]], axis=1)
    payload = dict(payload)
    market = ed.Market(payload, torch.device("cpu"))
    market.seats = extended.reset_index(drop=True)
    log(f"market ready; seats {market.seats.shape}")

    sig_dates = [pd.Timestamp(x) for x in market.dates]
    seed_frame = market.seats.loc[:, SEED]
    b_s, o_s, fs_s, fr_s = market.make_blocks(seed_frame, SEED)
    seed_ledger = market.scenario_ledger(b_s, o_s, fs_s, fr_s,
                                         np.ones(len(SEED), dtype=np.int64))
    seed_curve = market.build_daily(seed_ledger)
    seed_table = market.monthly_table(seed_curve, seed_ledger)
    seed_turn = float(seed_ledger.turnover[seed_ledger.valid].mean())
    log(f"[seed] E={seed_table.e_term.mean():.4f} NC={seed_table.nc.mean():.3f} "
        f"T/month={seed_table.turnover_month.mean():.3f} turn/reb={seed_turn:.4f}")

    rows_rows = pd.DataFrame({"d": market.signal_frame["date"].to_numpy(),
                              "i": market.signal_frame["instrument"].to_numpy(),
                              "v": market.seats["size_only"].to_numpy()})
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
    for name, keys in POOLS_FIXED:
        frame = market.seats.loc[:, keys]
        b, o, fs, fr = market.make_blocks(frame, keys)
        led = market.scenario_ledger(b, o, fs, fr, np.ones(len(keys), dtype=np.int64))
        curve = market.build_daily(led)
        table = market.monthly_table(curve, led)
        merged = seed_table.merge(table, on=["year", "month"], suffixes=("_seed", "_p"))
        merged["d_e"] = merged.e_term_p - merged.e_term_seed
        merged["d_t"] = merged.turnover_month_p - merged.turnover_month_seed
        merged["d_nc"] = merged.nc_p - merged.nc_seed
        merged["d_c_points"] = 44000.0 * ed.W_C * merged.d_nc
        merged.to_csv(OUT / f"pool_monthly_{name}.csv", index=False, encoding="utf-8-sig")

        si = np.array([PLAT_SI[k] for k in keys], dtype=float)
        raw_new = float(si.mean())
        na_new = min(raw_new / 0.08, 0.70)
        d_a = (na_new - NA_NOW) * A_UNIT
        raw_delta = raw_new - SEED_MEAN
        d_b = raw_delta / 0.06 * 15400.0
        d_c = float(merged.d_c_points.mean())
        corr, neutral = size_guard(frame.mean(axis=1))
        row = dict(pool=name, n_seats=len(keys), raw_a_new=raw_new, na_new=na_new,
                   d_a_points=d_a, d_c_points=d_c, d_comb_ac=d_a + d_c,
                   d_b_steady_proxy=d_b, d_e_mean=float(merged.d_e.mean()),
                   d_t_mean=float(merged.d_t.mean()), d_nc_mean=float(merged.d_nc.mean()),
                   turn_per_reb=float(led.turnover[led.valid].mean()),
                   nc_mean=float(table.nc.mean()),
                   corr_size=corr, size_neutral_net=neutral,
                   d_corr_size=corr - seed_corr, d_neutral=neutral - seed_neutral,
                   pos_c_months=int((merged.d_c_points > 0).sum()), months=len(merged))
        summary_rows.append(row)
        log(f"[{name}] n={len(keys)} raw_a={raw_new:.5f} na={na_new:.4f} dA={d_a:+,.0f} "
            f"dE={row['d_e_mean']:+.4f} dT={row['d_t_mean']:+.3f} dNC={row['d_nc_mean']:+.4f} "
            f"dC={d_c:+,.0f} turn/reb={row['turn_per_reb']:.4f} corrSize={corr:+.3f} "
            f"neutralNet={neutral:+.4f}")
        del frame, b, o, fs, fr, led, curve, table, merged
        gc.collect()

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "pool_summary.csv", index=False, encoding="utf-8-sig")
    meta = dict(seed=SEED, seed_mean_si=SEED_MEAN, na_now=NA_NOW,
                plat_si=PLAT_SI, seed_turn_per_reb=seed_turn,
                seed_corr_size=seed_corr, seed_size_neutral_net=seed_neutral)
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    pd.set_option("display.width", 260)
    print(summary.round(4).to_string(index=False))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
