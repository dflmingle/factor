"""第 6 席的 NB 稀释：10-01~03 窗口加席 vs 晚一期加席（本地蒙特卡洛，零平台算力）。

官方口径: S_i^B = |mean(RankIC)| * |mean(IC)/std(IC)| * IC胜率, rawB = sum(S_i^B)/M,
          NB = min(rawB/0.06, 1)。样本 <2 条或 std=0 时该因子无 S_i^B。

两种平台实现假设（不可见，两者都算）:
  M_all  : M = 池内因子总数，没有记录的因子贡献 0（=> 会稀释）
  M_valid: M = 只有已经能算出 S_i^B 的因子数（=> 不稀释）

时间线（10 日统一调仓，平台历史均值 2.0 次/月）:
  5 席自 R0=2026-09-24 生效, 第 1 条记录在 R1;
  选项 A（10-01~03 加席）：新席在 R1 进入合成 -> 第 1 条记录在 R2（落后 1 期）
      => 稀释期 = R2 一期（R1 时 5 席也只有 1 条记录，双方都是 0）
  选项 B（11-01~03 加席）：新席在 R3 进入合成 -> 第 1 条记录在 R4（落后 3 期）
      => 稀释期 = R3 + R4 两期
输出: research_reports/platform_alignment/nb-dilution-20260924/
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pool_seat_rescreen_20260924 as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/nb-dilution-20260924"
SEAT_SI = R.SEAT_SI
POOL = R.POOL
N_MONTHS = 12
REB_PER_MONTH = 2          # 平台 2021-09~2026-08 实测均值 2.0 次/月
N_DRAW = int(os.environ.get("NB_DRAW", "4000"))
SEED = 20260924
CAP_B = 0.06
POINTS = 40000.0 * 1.10


def s_i_b(ics: np.ndarray, rics: np.ndarray) -> float:
    n = len(ics)
    if n < 2:
        return 0.0
    sd = ics.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        return 0.0
    mean_ic = float(ics.mean())
    ic_ir = mean_ic / sd
    win = float((ics > 0.02).mean()) if mean_ic >= 0 else float((ics < -0.02).mean())
    return abs(float(rics.mean())) * abs(ic_ir) * win


def nb_from(values: list[float], mode: str) -> float:
    if mode == "M_all":
        raw = float(np.sum(values)) / len(values)
    else:
        valid = [v for v in values if v > 0]
        raw = float(np.mean(valid)) if valid else 0.0
    return float(min(raw / CAP_B, 1.0))


def simulate(series: dict[str, tuple[np.ndarray, np.ndarray]],
             extra: str | None, entry_reb: int | None, mode: str,
             rng: np.random.Generator) -> np.ndarray:
    """返回每个调仓期的 NB（长度 N_MONTHS*REB_PER_MONTH）。"""
    keys = list(series)
    n_reb = N_MONTHS * REB_PER_MONTH
    out = np.zeros(n_reb)
    for k in range(1, n_reb + 1):
        values = []
        for key in keys:
            ics, rics = series[key]
            idx = rng.integers(0, len(ics), size=k)
            values.append(s_i_b(ics[idx], rics[idx]))
        if extra is not None and entry_reb is not None and k >= entry_reb:
            ics, rics = series[extra]
            n6 = k - entry_reb          # 进入后过了多少条记录（进入当期的那条还没有）
            if n6 >= 1:
                idx = rng.integers(0, len(ics), size=n6)
                values.append(s_i_b(ics[idx], rics[idx]))
            else:
                values.append(0.0)
        out[k - 1] = nb_from(values, mode)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sf, _raw, returns, _dates = pickle.loads(R.SIGNALS.read_bytes())
    frame = sf[["date", "instrument"]].reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    signal_dates = sorted(frame["date"].unique())
    forward = (returns.pivot_table(index="date", columns="instrument", values="forward_return")
               .reindex(index=signal_dates))
    forward.index = pd.to_datetime(forward.index)
    columns = forward.columns

    built = pickle.loads(R.SEATS.read_bytes())
    panel_frame = pd.concat([frame, built["scores"].reset_index(drop=True)], axis=1)
    series: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for k in POOL:
        p = panel_frame.pivot_table(index="date", columns="instrument", values=k)\
                          .reindex(index=signal_dates, columns=columns)
        st = R.seat_stats(p, forward)
        series[k] = (np.asarray(st["ics"], dtype="float64"), np.asarray(st["rics"], dtype="float64"))

    fnet = pickle.loads((R.OUT / "fnet01_panels.pkl").read_bytes())
    for tag, values in fnet.items():
        pf = frame.copy(); pf["_v"] = values.to_numpy()
        p = pf.pivot_table(index="date", columns="instrument", values="_v")\
               .reindex(index=signal_dates, columns=columns)
        st = R.seat_stats(p, forward)
        series[f"fnet01_{tag}"] = (np.asarray(st["ics"], dtype="float64"),
                                   np.asarray(st["rics"], dtype="float64"))

    rng = np.random.default_rng(SEED)
    report: dict[str, object] = {"n_draw": N_DRAW, "reb_per_month": REB_PER_MONTH,
                                 "months": N_MONTHS, "scenarios": {}}
    for extra in [k for k in series if k.startswith("fnet01")]:
        for mode in ("M_all", "M_valid"):
            traj = {"no_add": [], "opt_A": [], "opt_B": []}
            for _ in range(N_DRAW):
                traj["no_add"].append(simulate(series, None, None, mode, rng))
                traj["opt_A"].append(simulate(series, extra, 1, mode, rng))
                traj["opt_B"].append(simulate(series, extra, 3, mode, rng))
            print(f"  done {extra}|{mode} ({N_DRAW} draws)", flush=True)
            arr = {k: np.array(v) for k, v in traj.items()}
            monthly = {k: v.reshape(len(v), N_MONTHS, REB_PER_MONTH)[:, :, -1] for k, v in arr.items()}
            d_AB = monthly["opt_A"] - monthly["opt_B"]
            d_NA = monthly["opt_A"] - monthly["no_add"]
            report["scenarios"][f"{extra}|{mode}"] = {
                "NB_first_month_A": float(monthly["opt_A"][:, 0].mean()),
                "NB_first_month_B": float(monthly["opt_B"][:, 0].mean()),
                "dNB_A_minus_B_total_points": float(POINTS * 0.35 * d_AB.sum(axis=1).mean()),
                "dNB_A_minus_B_p10": float(POINTS * 0.35 * np.percentile(d_AB.sum(axis=1), 10)),
                "dNB_A_minus_B_p90": float(POINTS * 0.35 * np.percentile(d_AB.sum(axis=1), 90)),
                "dNB_A_vs_noadd_total_points": float(POINTS * 0.35 * d_NA.sum(axis=1).mean()),
                "monthly_dNB_A_minus_B": [float(x) for x in (POINTS * 0.35 * d_AB.mean(axis=0))],
                "monthly_NB_A": [float(x) for x in monthly["opt_A"].mean(axis=0)],
                "monthly_NB_B": [float(x) for x in monthly["opt_B"].mean(axis=0)],
                "monthly_NB_no_add": [float(x) for x in monthly["no_add"].mean(axis=0)],
            }
        # 单期稀释的瞬时代价（M_all 下，第 1 个可测月）
        sk = f"{extra}|M_all"
        s = report["scenarios"][sk]
        s["single_period_dilution_points"] = float(
            POINTS * 0.35 * (s["monthly_NB_no_add"][0] - s["monthly_NB_A"][0]))
    (OUT / "nb_timing.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(json.dumps({k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)}
                      for k, v in report["scenarios"].items()}, indent=2, ensure_ascii=False))
    for k, v in report["scenarios"].items():
        if not k.endswith("M_all"):
            continue
        print(f"\n{k}  月 NB（无加席 / 选项A / 选项B）")
        for i in range(N_MONTHS):
            print(f"  M{i+1:02d}  {v['monthly_NB_no_add'][i]:.3f}  {v['monthly_NB_A'][i]:.3f}  "
                  f"{v['monthly_NB_B'][i]:.3f}   d(A-B) {v['monthly_dNB_A_minus_B'][i]:+.0f} 分")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
