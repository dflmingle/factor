"""第 6 席重筛（新门槛口径）+ F-NET01 池级边际贡献 —— 全部本地，零平台算力。

与 2026-09-24 之前的 `cluster_member_size_check` 的差别：
  * NC 用**已用 283 池验证到机器精度**的平台原式
    `NC = min(1, max(Rex,0)/max(Turnover_month,0.3) * SR * (1-1.2*DD) / 0.6)`，
    而不是只对 2 调仓月成立的近似；
  * 同时给出 2 调仓月 / 3 调仓月 / 期望（P2=0.767, P3=0.117）三套 ΔNC 与 ΔComb；
  * 桥式拆解 ΔNA / ΔNC(性能部分) / ΔNC(换手部分) / ΔNB（稳态 + 首期稀释）；
  * size 防作弊：与 SIZE-ONLY 的日截面秩相关 + 桶内 size 中性化后的净额；
  * 换手分档：<=30% 主筛 / 30-40% 保留 / >40% 单列。

输入: pool-screen-20260921-qualitygate3/signals.pkl (5 席 + 网格 + 前瞻收益)
      pool-extended-search-20260922/built_signals.pkl (54 个已建面板候选)
      F-NET01 = WMA(((1/LOW)/LOW)/VOLUME, 40)，本地重建（两种复权口径）
输出: research_reports/platform_alignment/seat-rescreen-20260924/
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import exhaustive_representative_combination as e  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ROOT / "research_reports/platform_alignment/pool-screen-20260921-qualitygate3/signals.pkl"
SEATS = ROOT / "research_reports/platform_alignment/pool-extended-search-20260922/built_signals.pkl"
OUT = ROOT / "research_reports/platform_alignment/seat-rescreen-20260924"

POOL = ["size_only", "impact60", "t10_size_plus_impact_bm",
        "book_to_market_lf_minus_size", "book_to_market_lf_plus_impact"]
SEAT_SI = {"size_only": 0.010244872746, "impact60": 0.01578596817,
           "t10_size_plus_impact_bm": 0.03725596,
           "book_to_market_lf_minus_size": 0.01692,
           "book_to_market_lf_plus_impact": 0.01540}
CYCLE = 10
P2, P3 = 0.7667, 0.1167          # 平台 2021-09~2026-08 的每月调仓次数分布
POINTS = 40000.0 * 1.10           # 加成后
NC_FLOOR, CAP_C = 0.30, 0.60
BUCKETS = 20


# ---------------------------------------------------------------- 基础工具
def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean, std = frame.mean(axis=1), frame.std(axis=1, ddof=0).replace(0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def daily_rank_corr(left: pd.DataFrame, right: pd.DataFrame) -> float:
    values = []
    for date in left.index:
        x = left.loc[date].to_numpy(dtype="float64")
        y = right.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        a, b = pd.Series(x[ok]).rank(), pd.Series(y[ok]).rank()
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(values)) if values else float("nan")


def seat_stats(panel: pd.DataFrame, forward: pd.DataFrame) -> dict:
    rics, ics, turns, held, bench = [], [], [], [], []
    previous: set[str] = set()
    for date in panel.index:
        f = panel.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            continue
        x, r = f[ok], y[ok]
        if np.std(x) == 0 or np.std(r) == 0:
            continue
        instruments = panel.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        selected = set(instruments[order].tolist())
        if previous:
            turns.append(1 - len(selected & previous) / len(selected))
        previous = selected
        held.append(float(r[order].mean())); bench.append(float(r.mean()))
        rics.append(float(np.corrcoef(pd.Series(x).rank(), pd.Series(r).rank())[0, 1]))
        ics.append(float(np.corrcoef(x, r)[0, 1]))
    if len(ics) < 3:
        return {"periods": len(ics), "ics": [], "rics": []}
    rics, ics = np.array(rics), np.array(ics)
    mean_rank, mean_ic = float(rics.mean()), float(ics.mean())
    std_ic = float(ics.std(ddof=1))
    win = float((ics > 0.02).mean()) if mean_ic >= 0 else float((ics < -0.02).mean())
    ic_ir = mean_ic / std_ic if std_ic else 0.0
    turnover = float(np.mean(turns)) if turns else 0.0
    years = len(held) * CYCLE / 252
    gross = float(np.prod(1 + np.array(held)) ** (1 / years)
                  - np.prod(1 + np.array(bench)) ** (1 / years))
    return dict(periods=len(ics), rank_ic=mean_rank, ic_mean=mean_ic, ic_ir=ic_ir, win=win,
                s_i=abs(mean_rank) * abs(ic_ir) * win, direction=int(mean_ic >= 0),
                seat_turnover=turnover, seat_gross=gross,
                seat_net=gross - turnover * (252.0 / CYCLE) * 0.006,
                ics=ics.tolist(), rics=rics.tolist())


def bucket_neutral_net(panel: pd.DataFrame, size_axis: pd.DataFrame,
                       forward: pd.DataFrame) -> float:
    """按 size 秩序 20 等频桶、桶内去均值后的 top-decile 净额（size 中性化净额代理）。"""
    held, bench, turns = [], [], []
    previous: set[str] = set()
    for date in panel.index:
        f = panel.loc[date].to_numpy(dtype="float64")
        s = size_axis.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y) & np.isfinite(s)
        if ok.sum() < 200:
            continue
        x, r, sz = f[ok], y[ok], s[ok]
        inst = panel.columns.to_numpy()[ok]
        try:
            bucket = pd.qcut(pd.Series(sz).rank(method="first"), BUCKETS, labels=False)
        except ValueError:
            continue
        resid = pd.Series(x) - pd.Series(x).groupby(bucket).transform("mean")
        resid = resid.to_numpy(dtype="float64")
        order = np.argsort(-resid)[: int(len(resid) * 0.1)]
        sel = set(inst[order].tolist())
        turns.append(np.nan if not previous else 1 - len(sel & previous) / len(sel))
        previous = sel
        held.append(float(r[order].mean())); bench.append(float(r.mean()))
    if len(held) < 3:
        return float("nan")
    years = len(held) * CYCLE / 252.0
    gross = float(np.prod(1 + np.array(held)) ** (1 / years) - np.prod(1 + np.array(bench)) ** (1 / years))
    turn = float(np.nanmean(turns[1:])) if len(turns) > 1 else 0.0
    return gross - turn * (252.0 / CYCLE) * 0.006


def pool_run(score: pd.DataFrame, forward: pd.DataFrame) -> dict:
    """官方 C 口径：组合与基准分别复合再相减；SR/DD 用组合自身净值（非超额）。"""
    held, bench, turnover, valid = [], [], [], []
    previous: set[str] = set()
    for date in score.index:
        f = score.loc[date].to_numpy(dtype="float64")
        y = forward.loc[date].to_numpy(dtype="float64")
        ok = np.isfinite(f) & np.isfinite(y)
        if ok.sum() < 100:
            held.append(np.nan); bench.append(np.nan); turnover.append(np.nan)
            valid.append(False); continue
        x, r = f[ok], y[ok]
        inst = score.columns.to_numpy()[ok]
        order = np.argsort(-x)[: int(len(x) * 0.1)]
        sel = set(inst[order].tolist())
        turnover.append(np.nan if not previous else 1 - len(sel & previous) / len(sel))
        previous = sel
        held.append(float(r[order].mean())); bench.append(float(r.mean()))
        valid.append(True)
    held, bench, turnover = np.array(held), np.array(bench), np.array(turnover)
    valid = np.array(valid)
    if valid.sum() < 3:
        return {}
    h = np.nan_to_num(held[valid]); b = np.nan_to_num(bench[valid]); turn = turnover[valid]
    years = int(valid.sum()) * CYCLE / 252.0
    gross = float(np.prod(1 + h) ** (1 / years) - np.prod(1 + b) ** (1 / years))
    turn_mean = float(np.nanmean(turn))
    net = gross - turn_mean * (252.0 / CYCLE) * 0.006
    after_cost = h - np.where(np.isfinite(turn), turn * 0.006, 0.0)
    sr = float(after_cost.mean() / after_cost.std(ddof=1) * np.sqrt(252.0 / CYCLE))
    curve = np.cumprod(1 + after_cost)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    return dict(gross=gross, net=net, turn=turn_mean, sr=sr, dd=dd)


def nc_curve(net: float, sr: float, dd: float, turn_mean: float, k: int) -> float:
    E = max(net, 0.0) * sr * (1 - 1.2 * dd)
    T = k * turn_mean
    if T < NC_FLOOR:
        T = NC_FLOOR
    return float(min(1.0, max(E / (CAP_C * T), 0.0)))


def na_of(seat_si: dict) -> float:
    return float(min(np.mean(list(seat_si.values())) / 0.08, 0.70))


# ---------------------------------------------------------------- 主流程
def build_fnet01(sf: pd.DataFrame, cache: Path) -> dict[str, pd.Series]:
    """在池子的同一网格上重建 F-NET01（plain qfq 与 raw 两种口径）。"""
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    out: dict[str, pd.Series] = {}
    from stfilter_local_recheck import DEFAULT_DATA_START, DEFAULT_END  # noqa: E402

    for tag, price_root in (("qfq", e.DEFAULT_PRICE_ROOT),
                            ("raw", ROOT / "quantlab/.quantlab/cache/research/cn_equity/tushare_factor_recheck/qfq_rich/daily_batches")):
        frame = e.load_full_a_data(price_root, e.DEFAULT_CAP_ROOT,
                                   pd.Timestamp(DEFAULT_DATA_START), pd.Timestamp(DEFAULT_END),
                                   market_cap_field="total_mv")
        frame = frame.sort_values(["instrument", "date"], ignore_index=True)
        dates = sorted(pd.to_datetime(sf["date"]).unique())
        values = e.build_factor(frame, "wma_low_volume40", signal_dates=dates)
        key = sf[["date", "instrument"]].copy()
        key["date"] = pd.to_datetime(key["date"])
        merged = key.merge(pd.DataFrame({"date": frame["date"], "instrument": frame["instrument"],
                                         "_v": pd.to_numeric(values, errors="coerce").to_numpy()}),
                           on=["date", "instrument"], how="left")
        out[tag] = pd.to_numeric(merged["_v"], errors="coerce")
        print(f"  fnet01[{tag}] built, coverage {out[tag].notna().mean():.3f}", flush=True)
        del frame
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(pickle.dumps(out))
    return out


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    sf, raw_members, returns, _dates = pickle.loads(SIGNALS.read_bytes())
    built = pickle.loads(SEATS.read_bytes())
    members, scores = built["built"], built["scores"]

    frame = sf[["date", "instrument"]].reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    signal_dates = sorted(frame["date"].unique())
    forward = (returns.pivot_table(index="date", columns="instrument", values="forward_return")
               .reindex(index=signal_dates))
    forward.index = pd.to_datetime(forward.index)
    columns = forward.columns

    print("building F-NET01 on the pool grid ...", flush=True)
    fnet = build_fnet01(frame, OUT / "fnet01_panels.pkl")

    panel_frame = pd.concat([frame, scores.reset_index(drop=True)], axis=1)
    panels: dict[str, pd.DataFrame] = {}
    meta: dict[str, dict] = {}
    for m in members:
        key = m["key"]
        p = panel_frame.pivot_table(index="date", columns="instrument", values=key)\
                         .reindex(index=signal_dates, columns=columns)
        panels[key] = p
        meta[key] = m
    for tag, series in fnet.items():
        key = f"fnet01_{tag}"
        pf = frame.copy(); pf[key] = series.to_numpy()
        panels[key] = pf.pivot_table(index="date", columns="instrument", values=key)\
                        .reindex(index=signal_dates, columns=columns)
        meta[key] = dict(key=key, name=f"F-NET01-PLAT-20260914 ({tag} 口径)",
                         direction=1, platform_net=13.63, si=None,
                         formula="WMA(((1/LOW)/LOW)/VOLUME),40)", source="local_rebuild")
    print(f"panels ready ({len(panels)}) in {time.time()-t0:.0f}s", flush=True)

    seat_z = {k: zscore(panels[k]) for k in POOL}
    base_score = sum(seat_z.values()) / len(seat_z)
    base = pool_run(base_score, forward)
    base_na = na_of(SEAT_SI)
    base_comb = {k: 0.20 * base_na + 0.45 * nc_curve(base["net"], base["sr"], base["dd"], base["turn"], k)
                 for k in (2, 3)}
    base_comb["exp"] = P2 * base_comb[2] + P3 * base_comb[3] + (1 - P2 - P3) * (
        0.20 * base_na + 0.45 * nc_curve(base["net"], base["sr"], base["dd"], base["turn"], 1))
    base_corr_size = daily_rank_corr(base_score, panels["size_only"])
    print("seed pool:", {k: round(v, 4) for k, v in base.items()}, "NA", round(base_na, 4),
          "comb2", round(base_comb[2], 4), "|corr_size|", round(abs(base_corr_size), 3), flush=True)

    rows = []
    for key, panel in panels.items():
        m = meta[key]
        direction = int(m.get("direction", 1) or 1)
        oriented = panel if direction == 1 else -panel
        st = seat_stats(oriented, forward)
        if not st.get("periods"):
            continue
        row = {
            "key": key, "name": m.get("name", ""), "in_pool": key in POOL,
            "platform_net_pct": m.get("platform_net"), "platform_si": m.get("si"),
            "local_s_i": st["s_i"], "local_rank_ic": st["rank_ic"], "local_ic_ir": st["ic_ir"],
            "local_win": st["win"], "local_turnover": st["seat_turnover"],
            "local_net": st["seat_net"],
            "corr_size": daily_rank_corr(oriented, panels["size_only"]),
            "net_size_neutral": bucket_neutral_net(oriented, panels["size_only"], forward),
        }
        if key in POOL:
            row.update(add6_net=base["net"], add6_turn=base["turn"], NC2=base_comb and nc_curve(base["net"], base["sr"], base["dd"], base["turn"], 2),
                       NC3=nc_curve(base["net"], base["sr"], base["dd"], base["turn"], 3),
                       dNA=0.0, dNC2=0.0, dNC3=0.0, dNC_exp=0.0, dComb2=0.0, dComb_exp=0.0,
                       dNC_turn=0.0, dNC_perf=0.0, dNB_steady=0.0, dNB_first=0.0,
                       corr_pool=float("nan"))
            rows.append(row); continue
        score6 = (sum(seat_z.values()) + zscore(oriented)) / (len(seat_z) + 1)
        run6 = pool_run(score6, forward)
        seat_si6 = dict(SEAT_SI); seat_si6["candidate"] = st["s_i"]
        na6 = na_of(seat_si6)
        nc6 = {k: nc_curve(run6["net"], run6["sr"], run6["dd"], run6["turn"], k) for k in (1, 2, 3)}
        nc5 = {k: nc_curve(base["net"], base["sr"], base["dd"], base["turn"], k) for k in (1, 2, 3)}
        comb6 = {k: 0.20 * na6 + 0.45 * nc6[k] for k in (1, 2, 3)}
        comb5 = {k: 0.20 * base_na + 0.45 * nc5[k] for k in (1, 2, 3)}
        comb6["exp"] = P2 * comb6[2] + P3 * comb6[3] + (1 - P2 - P3) * comb6[1]
        comb5["exp"] = P2 * comb5[2] + P3 * comb5[3] + (1 - P2 - P3) * comb5[1]

        # 精确两步分解（Shapley 中值）：换手部分 / 表现部分
        def E(run): return max(run["net"], 0.0) * run["sr"] * (1 - 1.2 * run["dd"])
        def ncE(Ev, turn, k):
            T = max(k * turn, NC_FLOOR)
            return float(min(1.0, max(Ev / (CAP_C * T), 0.0)))
        E5, E6 = E(base), E(run6)
        dNC_turn = 0.5 * ((ncE(E5, run6["turn"], 2) - ncE(E5, base["turn"], 2))
                          + (ncE(E6, run6["turn"], 2) - ncE(E6, base["turn"], 2)))
        dNC_perf = (nc6[2] - nc5[2]) - dNC_turn
        # NB：rawB = Σ S_i^B / M，新席首期无记录 -> 贡献 0
        s5 = np.array(list(SEAT_SI.values()))
        dNB_steady = (min(s5.mean() + (st["s_i"] - s5.mean()) / 6, 0.06) / 0.06
                      - min(s5.mean() / 0.06, 1.0))
        dNB_steady = min((s5.sum() + st["s_i"]) / 6 / 0.06, 1.0) - min(s5.mean() / 0.06, 1.0)
        dNB_first = min(s5.mean() / 6 * 5 / 0.06, 1.0) - min(s5.mean() / 0.06, 1.0)
        row.update(
            add6_net=run6["net"], add6_sr=run6["sr"], add6_dd=run6["dd"], add6_turn=run6["turn"],
            T2=2 * run6["turn"], T3=3 * run6["turn"], NA6=na6,
            NC1=nc6[1], NC2=nc6[2], NC3=nc6[3],
            dNA=na6 - base_na, dNC1=nc6[1] - nc5[1], dNC2=nc6[2] - nc5[2], dNC3=nc6[3] - nc5[3],
            dNC_turn=dNC_turn, dNC_perf=dNC_perf,
            dNC_exp=(P2 * nc6[2] + P3 * nc6[3] + (1 - P2 - P3) * nc6[1])
                    - (P2 * nc5[2] + P3 * nc5[3] + (1 - P2 - P3) * nc5[1]),
            dComb2=comb6[2] - comb5[2], dComb3=comb6[3] - comb5[3], dComb_exp=comb6["exp"] - comb5["exp"],
            dNB_steady=dNB_steady, dNB_first=dNB_first,
            dpoints_exp=POINTS * (comb6["exp"] - comb5["exp"]),
            dpoints2=POINTS * (comb6[2] - comb5[2]),
            corr_pool=daily_rank_corr(oriented, base_score),
        )
        rows.append(row)
        print(f"  {key:46s} S_i {st['s_i']:.4f} turn {st['seat_turnover']:.3f} "
              f"corr_size {row['corr_size']:+.3f} dComb(exp) {row['dComb_exp']:+.4f} "
              f"dPts {row['dpoints_exp']:+.0f}", flush=True)

    out = pd.DataFrame(rows).sort_values("dComb_exp", ascending=False)
    out.to_csv(OUT / "seat_rescreen.csv", index=False)
    (OUT / "baseline.json").write_text(json.dumps(
        {"base": base, "base_na": base_na, "base_comb2": base_comb[2], "base_comb3": base_comb[3],
         "base_comb_exp": base_comb["exp"], "base_corr_size": base_corr_size,
         "P2": P2, "P3": P3, "points_per_comb": POINTS}, indent=2, ensure_ascii=False))
    pd.set_option("display.width", 260)
    cols = ["name", "local_s_i", "local_turnover", "local_net", "corr_size", "net_size_neutral",
            "dNA", "dNC_turn", "dNC_perf", "dNC_exp", "dNB_steady", "dNB_first", "dComb_exp", "dpoints_exp"]
    print("\n=== 重筛：按 ΔComb(期望) 排序 ===", flush=True)
    print(out[cols].round(4).to_string(index=False), flush=True)
    print(f"\nelapsed {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
