# -*- coding: utf-8 -*-
"""规则2：换席版（-VERIFY10-F +LAMD10-K5V2）池级 size 中性化检查（2026-10-03，零平台算力）。

数据源（本机重建，口径见 ab-batch-20260925/rebuild.log 与 provenance）：
- 5 席 scores / signal frame / forward returns：ab-batch-20260925/seat_panels_rebuilt.pkl
  （canonical signals.pkl / built_signals.pkl 本机缺失，用 09-25 重建集；池级 net 20.66 vs 平台 20.30）
- LAMD10-K5V2 复合：e-decomp-20260929/panels_cache.pkl + legmix_next_legs 定义
  （amt60/intr20/t_std20/vs_756 +1、amihud20 -1；与提交版 seat_lamd10k5 公式核对一致）。
- 指标函数/口径与 scripts/pool_size_guard_20260924.py 完全一致（R.zscore / R.daily_rank_corr /
  R.bucket_neutral_net，20 桶、cycle 10）。
- 判定：d_size_neutral_net >= 0 且 d_corr_size <= 0 为 PASS。
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pool_seat_rescreen_20260924 as R
from legmix_next_legs_20260929 import build_composite

OUT = ROOT / "research_reports/platform_alignment/pool5-swapf-20260930"
SEATS_PKL = ROOT / "research_reports/platform_alignment/ab-batch-20260925/seat_panels_rebuilt.pkl"
CACHE = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
SIGNED = {"amt60": 1.0, "intr20": 1.0, "t_std20": 1.0, "amihud20": -1.0, "vs_756": 1.0}
FKEY = "book_to_market_lf_plus_impact"


def main() -> int:
    payload = pickle.loads(SEATS_PKL.read_bytes())
    scores = payload["scores"]
    frame = payload["signal_frame"].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    signal_dates = sorted(frame["date"].unique())
    returns = payload["returns"]
    forward = (returns.pivot_table(index="date", columns="instrument", values="forward_return")
               .reindex(index=signal_dates))
    forward.index = pd.to_datetime(forward.index)
    columns = forward.columns
    panel_frame = pd.concat([frame, scores.reset_index(drop=True)], axis=1)
    panels = {}
    for key in R.POOL:
        panels[key] = (panel_frame.pivot_table(index="date", columns="instrument", values=key)
                       .reindex(index=signal_dates, columns=columns))
    print(f"seats ready: {len(signal_dates)} dates x {len(columns)} instruments "
          f"({signal_dates[0].date()}..{signal_dates[-1].date()})", flush=True)

    panels_e = pickle.loads(CACHE.read_bytes())
    comp = build_composite(panels_e, SIGNED)
    del panels_e
    k5 = comp.reindex(index=signal_dates, columns=columns).astype("float32")
    del comp

    ics = []
    for d in k5.index:
        x = k5.loc[d].to_numpy(dtype="float64"); y = forward.loc[d].to_numpy(dtype="float64")
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 200 or np.std(x[ok]) == 0:
            continue
        ics.append(float(np.corrcoef(pd.Series(x[ok]).rank(), pd.Series(y[ok]).rank())[0, 1]))
    ic_mean = float(np.mean(ics)) if ics else float("nan")
    if ic_mean < 0:
        k5 = -k5
    print(f"k5v2 daily rank ic mean over {len(ics)} dates = {ic_mean:+.4f} (flip={ic_mean < 0})", flush=True)

    seat_z = {k: R.zscore(panels[k]) for k in R.POOL}
    base_score = sum(seat_z.values()) / len(seat_z)
    swap_score = (sum(seat_z.values()) - seat_z[FKEY] + R.zscore(k5)) / len(R.POOL)

    rows = {}
    for label, score in (("base_5seat", base_score), ("swap_minusF_plusK5V2", swap_score)):
        rows[label] = {
            "corr_size": float(R.daily_rank_corr(score, panels["size_only"])),
            "size_neutral_net": float(R.bucket_neutral_net(score, panels["size_only"], forward)),
        }
        print(f'{label:24s} corr_size {rows[label]["corr_size"]:+.3f}  '
              f'size_neutral_net {rows[label]["size_neutral_net"]:+.4f}', flush=True)

    b, s = rows["base_5seat"], rows["swap_minusF_plusK5V2"]
    delta = {"d_corr_size": s["corr_size"] - b["corr_size"],
             "d_size_neutral_net": s["size_neutral_net"] - b["size_neutral_net"]}
    delta["rule2_pass"] = bool(delta["d_size_neutral_net"] >= 0 and delta["d_corr_size"] <= 0)
    payload_out = {
        "timestamp": "2026-10-03", "rule": "GOAL decision rule 2-2 (pool-level size guard)",
        "scene": "swap out book_to_market_lf_plus_impact (VERIFY10-F), in LAMD10-K5V2",
        "signed_legs": SIGNED, "k5v2_ic_mean": ic_mean, "k5v2_flip": bool(ic_mean < 0),
        "source_seats": "ab-batch-20260925/seat_panels_rebuilt.pkl (rebuilt, provenance inside)",
        "source_k5v2": "e-decomp-20260929/panels_cache.pkl + legmix_next_legs_20260929.build_composite",
        "dates": len(signal_dates), "instruments": int(len(columns)),
        "first_date": str(signal_dates[0].date()), "last_date": str(signal_dates[-1].date()),
        "cycle": R.CYCLE, "buckets": R.BUCKETS,
        "rows": rows, "deltas_swap_vs_base": delta,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rule2_size_guard_20261003.json").write_text(
        json.dumps(payload_out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("RESULT:", json.dumps(delta, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
