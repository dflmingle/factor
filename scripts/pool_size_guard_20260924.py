"""池级 size 防作弊：加第 6 席后，池组合自身的 corr_size 与 size 中性化净额怎么变。

口径与 GOAL §4.8 / seat_rescreen 一致：中性化 = 逐日按 size 秩序 20 等频桶、桶内去均值，
取残差的 top-decile 净额（0.30% 单边、10 日调仓）。零平台算力。
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pool_seat_rescreen_20260924 as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/seat-rescreen-20260924"
KEYS = ["t10_size_plus_impact_aggregate", "t10_size_plus_impact", "t10_size_plus_impact_g13",
        "t10_size_plus_impact_downside", "t10_size_plus_impact_wc", "t10_size_plus_impact_fscore",
        "t10_nomcap_plus_impact", "fnet01_qfq"]


def main() -> int:
    sf, _raw, returns, _dates = pickle.loads(R.SIGNALS.read_bytes())
    built = pickle.loads(R.SEATS.read_bytes())
    scores = built["scores"]
    frame = sf[["date", "instrument"]].reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"])
    signal_dates = sorted(frame["date"].unique())
    forward = (returns.pivot_table(index="date", columns="instrument", values="forward_return")
               .reindex(index=signal_dates))
    forward.index = pd.to_datetime(forward.index)
    columns = forward.columns
    panel_frame = pd.concat([frame, scores.reset_index(drop=True)], axis=1)
    panels = {}
    for key in list(R.POOL) + KEYS:
        if key in panels:
            continue
        if key == "fnet01_qfq":
            fnet = pickle.loads((R.OUT / "fnet01_panels.pkl").read_bytes())["qfq"]
            pf = frame.copy(); pf["_v"] = fnet.to_numpy()
            panels[key] = pf.pivot_table(index="date", columns="instrument", values="_v")\
                            .reindex(index=signal_dates, columns=columns)
        else:
            panels[key] = panel_frame.pivot_table(index="date", columns="instrument", values=key)\
                                     .reindex(index=signal_dates, columns=columns)
    seat_z = {k: R.zscore(panels[k]) for k in R.POOL}
    base_score = sum(seat_z.values()) / len(seat_z)
    rows = []
    for label, score in [("base_5seat", base_score)] + [
            (k, (sum(seat_z.values()) + R.zscore(panels[k])) / (len(seat_z) + 1)) for k in KEYS]:
        rows.append({
            "label": label,
            "corr_size": R.daily_rank_corr(score, panels["size_only"]),
            "size_neutral_net": R.bucket_neutral_net(score, panels["size_only"], forward),
        })
        print(f'{label:34s} corr_size {rows[-1]["corr_size"]:+.3f}  '
              f'size_neutral_net {rows[-1]["size_neutral_net"]:+.4f}', flush=True)
    base = rows[0]
    for r in rows[1:]:
        r["d_corr_size"] = r["corr_size"] - base["corr_size"]
        r["d_size_neutral_net"] = r["size_neutral_net"] - base["size_neutral_net"]
    (OUT / "pool_size_guard.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
