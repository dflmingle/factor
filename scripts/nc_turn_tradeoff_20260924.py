"""NC(C 分项) 与换手的真实关系 —— 用平台原生榜单字段反解并验证官方评分公式。

输入:
  research_reports/platform_alignment/goal-20260924/leaderboard_points_20260923_raw.csv (283 池, 2026-09-23)
  research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl   (平台统一调仓日序列)
输出:
  research_reports/platform_alignment/nc-turn-20260924/{score_formula.json,elasticity.json,
      nc_turn_curve.csv,turnover_tradeoff.csv,rebalance_calendar.json}
零平台算力。
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "research_reports/platform_alignment/goal-20260924/leaderboard_points_20260923_raw.csv"
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
OUT = ROOT / "research_reports/platform_alignment/nc-turn-20260924"
OUT.mkdir(parents=True, exist_ok=True)

# 本地代理基线（GOAL.md 第二节）
POOL_TURN_PER_REBAL = 0.1339   # 每次调仓换手
REBAL_PER_MONTH = 2.0          # 主体假设（10 日周期：77% 的月份 2 次）
POOL_NA = 0.239
SEAT_S = [0.0102, 0.0158, 0.0169, 0.0154, 0.0373]
NC_FLOOR = 0.30
POINTS_PER_COMB = 40000.0
BONUS = 1.10


def load() -> pd.DataFrame:
    raw = pd.read_csv(SRC)
    d = raw[["rank", "pool_id", "pool_name"] + [c for c in raw.columns if c.startswith("metrics.")]].copy()
    d.columns = [c if not c.startswith("metrics.") else "m_" + c[8:] for c in d.columns]
    for c in d.columns:
        if c.startswith("m_"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def verify(d: pd.DataFrame) -> dict:
    rawc_proxy = d.m_annual_rex.clip(lower=0) / np.maximum(d.m_turn, NC_FLOOR) * d.m_annual_sr * (1 - 1.2 * d.m_max_dd)
    err = (rawc_proxy - d.m_raw_c).abs()
    res = {
        "rawC_formula": "rawC = max(Rex_ann,0) / max(Turnover_month,0.30) * SR_ann * (1 - 1.2*MaxDD_month)",
        "n_pools": int(len(d)),
        "comb_resid_max": float((0.20 * d.m_na + 0.35 * d.m_nb + 0.45 * d.m_nc - d.m_comb).abs().max()),
        "points_per_comb": float(np.median(d.m_points_before_newbie / d.m_comb)),
        "points_resid_max": float((d.m_points_before_newbie - POINTS_PER_COMB * d.m_comb).abs().max()),
        "monthly_vs_bonus_resid_max": float((d.m_monthly_points - d.m_points_before_newbie * d.m_newbie_factor).abs().max()),
        "na_cap_resid_max": float((d.m_na - np.minimum(d.m_raw_a / 0.08, 0.70)).abs().max()),
        "nb_cap_resid_max": float((d.m_nb - np.minimum(d.m_raw_b / 0.06, 1.0)).abs().max()),
        "nc_cap_resid_max": float((d.m_nc - np.minimum(np.maximum(d.m_raw_c / 0.60, 0.0), 1.0)).abs().max()),
        "rawC_identity_frac_exact": float((err < 1e-9).mean()),
        "rawC_identity_frac_within_1e-3": float((err < 1e-3).mean()),
        "rawC_fail_all_rex_neg": bool((d.loc[err > 1e-3, "m_annual_rex"] <= 0).all()),
        "build_phase_rows": int(np.isclose(d.m_turn, 0.5).sum()),
        "build_phase_all_age0": bool((d.pipe(lambda x: x.loc[np.isclose(x.m_turn, 0.5), "m_pool_age_months"]) == 0).all()),
        "min_turn_nonbuild": float(d.loc[~np.isclose(d.m_turn, 0.5), "m_turn"].min()),
    }
    return res


def fit_elasticity(d: pd.DataFrame) -> dict:
    s = d[(d.m_turn > 0.55) & (d.m_raw_c > 0) & (d.m_annual_rex > 0)].copy()
    y = np.log(s.m_raw_c.values)
    X = np.c_[np.log(s.m_annual_rex.values), np.log(s.m_turn.values), np.ones(len(s))]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {
        "n": int(len(s)),
        "beta_log_rex": float(coef[0]),
        "beta_log_turn": float(coef[1]),
        "r2": float(1 - ((y - X @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
    }


def calendar() -> dict:
    sf, raw, returns, dates = pickle.loads(SIGNALS.read_bytes())
    per_month = pd.to_datetime(pd.Series(dates)).dt.to_period("M").value_counts()
    dist = {int(k): int(v) for k, v in per_month.value_counts().sort_index().items()}
    return {"n_months": int(len(per_month)), "rebalances_per_month": dist,
            "share_3": float((per_month == 3).mean()), "share_2": float((per_month == 2).mean()),
            "mean": float(per_month.mean())}


def tradeoff(t_star: float) -> pd.DataFrame:
    rows = []
    base_t = np.mean(SEAT_S)
    for t6, s6 in [(0.10, 0.035), (0.1339, 0.035), (0.20, 0.050), (0.23, 0.050), (0.30, 0.050),
                   (0.335, 0.060), (0.40, 0.075), (0.50, 0.100)]:
        tbar = (5 * POOL_TURN_PER_REBAL + t6) / 6
        T2, T3 = tbar * 2, tbar * 3
        nc2 = min(1.0, t_star / max(T2, NC_FLOOR))
        nc3 = min(1.0, t_star / max(T3, NC_FLOOR))
        nc_base2 = min(1.0, t_star / max(POOL_TURN_PER_REBAL * 2, NC_FLOOR))
        nc_base3 = min(1.0, t_star / max(POOL_TURN_PER_REBAL * 3, NC_FLOOR))
        cost_month = 0.45 * ((nc_base2 - nc2) * 0.767 + (nc_base3 - nc3) * 0.117) * POINTS_PER_COMB * BONUS
        rows.append(dict(
            seat_turnover=t6, pool_turn_per_rebal=tbar, T_2rebal=T2, T_3rebal=T3,
            NC_2rebal=nc2, NC_3rebal=nc3, expected_monthly_cost=cost_month,
            seat_S_i=s6,
            gain_from_A=0.20 * (s6 - base_t) / 6 / 0.08 * POINTS_PER_COMB * BONUS,
        ))
        rows[-1]["net"] = rows[-1]["gain_from_A"] - rows[-1]["expected_monthly_cost"]
    return pd.DataFrame(rows).round(6)


def main() -> None:
    d = load()
    res = verify(d)
    el = fit_elasticity(d)
    cal = calendar()
    t_star = 0.337  # GOAL.md 本地代理隐含（首月 0.68 / 三调仓月 0.84 / 常态 1.00 反解）
    tab = tradeoff(t_star)

    (OUT / "score_formula.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    (OUT / "elasticity.json").write_text(json.dumps(el, indent=2, ensure_ascii=False))
    (OUT / "rebalance_calendar.json").write_text(json.dumps(cal, indent=2, ensure_ascii=False))
    tab.to_csv(OUT / "turnover_tradeoff.csv", index=False)

    bins = [0.55, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0, 3.0, 100]
    g = d[~np.isclose(d.m_turn, 0.5)].copy()
    g["turn_bin"] = pd.cut(g.m_turn, bins)
    curve = g.groupby("turn_bin", observed=True).agg(
        n=("m_nc", "size"), nc_mean=("m_nc", "mean"),
        nc_frac_capped=("m_nc", lambda x: float((x >= 1).mean())),
        na_mean=("m_na", "mean"), raw_c_median=("m_raw_c", "median"),
        comb_mean=("m_comb", "mean"))
    curve.to_csv(OUT / "nc_turn_curve.csv")

    print(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(el, indent=2, ensure_ascii=False))
    print(json.dumps(cal, indent=2, ensure_ascii=False))
    print()
    print(tab.to_string(index=False))
    print()
    print(curve.to_string())


if __name__ == "__main__":
    main()
