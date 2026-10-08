#!/usr/bin/env python3
"""10-01~03 新增榜单席位的定向本地复现（2026-10-08，零平台算力）。

标的：10-04 明细相对 09-29 新增、且与我们同为 cycle=10 的高 s_i 席位
（见 board-higha-20261008/nearest_new_20261004.csv）——
  * 坐看云起 `20260919_2_ShortTerm_F1_Oversold_Rebound`（ic .111 / icir .724 / s_i .0590, n=119）
  * 坐看云起 `20260919_3_Volatility_F1_LowAmount_DeepDrawdown_ReboundA`（.108 / .720 / .0563, n=119）
  * 超绝韭菜子 `qa_r58_20260914_val_v2_*`（.114 / .690 / .0570, n=119；val 面无本地字段，
    用现役 BM 席位列做 proxy，结果标 proxy）
口径与 `board_higha_eval_20261008.py` 完全一致（全 A、平台信号日、cycle 10、10 组、0.30% 单边）。
输出：research_reports/platform_alignment/board-higha-20261008/local_repro_new/screen.csv
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from board_higha_eval_20261008 import (  # noqa: E402
    CYCLE, PANELS, POOL, SEATS, SIGNALS, WARMUP_START,
    evaluate, install_shim, inv, pct_rank,
)

OUT = ROOT / "research_reports" / "platform_alignment" / "board-higha-20261008" / "local_repro_new"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    install_shim()
    with PANELS.open("rb") as fh:
        panels = pickle.load(fh)["panels"]
    close = panels["close"].loc[WARMUP_START:]
    calendar = close.index
    positions = {d: i for i, d in enumerate(calendar)}
    O, H, L, V, A, T = (panels[k].loc[WARMUP_START:] for k in ("open", "high", "low", "volume", "amount", "turnover"))
    MV = panels["total_mv"].loc[WARMUP_START:]
    C = close
    ret1 = C.pct_change(fill_method=None)
    print(f"panel={close.shape} {calendar[0].date()}..{calendar[-1].date()}", flush=True)

    sf, _raw, _returns, _dates = pickle.load(SIGNALS.open("rb"))
    signal_dates = [pd.Timestamp(v) for v in sorted(sf["date"].unique())]
    schedule, forward_returns = [], {}
    for date in signal_dates:
        if date not in positions:
            continue
        cur = positions[date] + 1
        fut = cur + CYCLE
        if fut >= len(calendar):
            continue
        schedule.append(date)
        forward_returns[date] = (close.iloc[fut] / close.iloc[cur] - 1.0).to_numpy()
    print(f"signal dates={len(schedule)}", flush=True)

    seat_scores = pickle.load(SEATS.open("rb"))["scores"][POOL]
    seat_frame = sf[["date", "instrument"]].reset_index(drop=True)
    seat_frame = pd.concat([seat_frame, seat_scores.reset_index(drop=True)], axis=1)
    seat_frame["date"] = pd.to_datetime(seat_frame["date"])
    seat_frame = seat_frame[seat_frame["date"].isin(schedule)].set_index(["date", "instrument"])

    legs: dict[str, pd.DataFrame] = {}
    legs["amt60"] = inv(pct_rank(A.rolling(60).mean()))
    legs["amt250"] = inv(pct_rank(A.rolling(250, min_periods=120).mean()))
    legs["mv"] = inv(pct_rank(MV))
    legs["relT"] = inv(pct_rank(T.rolling(5).mean() / T.rolling(252, min_periods=100).mean()))
    legs["amtstd"] = inv(pct_rank(A.rolling(20).std() / A.rolling(20).mean()))
    legs["rev5"] = inv(pct_rank(C / C.shift(5) - 1.0))
    legs["vol20"] = inv(pct_rank(ret1.rolling(20).std()))
    legs["dd60"] = inv(pct_rank(C / C.rolling(60, min_periods=30).max()))
    legs["dd120"] = inv(pct_rank(C / C.rolling(120, min_periods=60).max()))
    rng = (C - L.rolling(20).min()) / (H.rolling(20).max() - L.rolling(20).min())
    legs["rng20"] = inv(pct_rank(rng))
    # BM 席位代理（proxy：本地面板无净资产字段，取现役 BM 两列）
    bm_m = (seat_frame["book_to_market_lf_minus_size"].unstack("instrument")
            .reindex(index=calendar, columns=C.columns))
    bm_p = (seat_frame["book_to_market_lf_plus_impact"].unstack("instrument")
            .reindex(index=calendar, columns=C.columns))
    legs["bmM_proxy"] = pct_rank(bm_m)
    legs["bmP_proxy"] = pct_rank(bm_p)
    print("legs built:", sorted(legs), flush=True)

    cands: dict[str, dict] = {}

    def add(name: str, weights: dict):
        cands[name] = weights

    add("D1|dd120+amt60", {"dd120": 0.5, "amt60": 0.5})
    add("D2|dd120+amt60+vol20", {"dd120": 0.4, "amt60": 0.3, "vol20": 0.3})
    add("D3|dd120+amt60+relT", {"dd120": 0.4, "amt60": 0.3, "relT": 0.3})
    add("D4|dd120+dd60+amt60", {"dd120": 0.4, "dd60": 0.3, "amt60": 0.3})
    add("D5|rng20+amt60", {"rng20": 0.5, "amt60": 0.5})
    add("D6|rng20+amt60+relT", {"rng20": 0.4, "amt60": 0.3, "relT": 0.3})
    add("D7|rng20+relT+amtstd", {"rng20": 0.4, "relT": 0.3, "amtstd": 0.3})
    add("D8|rev5+amt60", {"rev5": 0.5, "amt60": 0.5})
    add("D9|rev5+relT+amtstd+mv", {"rev5": 0.3, "relT": 0.3, "amtstd": 0.2, "mv": 0.2})
    add("D10|vol20+amt60+mv", {"vol20": 0.4, "amt60": 0.3, "mv": 0.3})
    add("D11|vol20+amt60+mv+relT", {"vol20": 0.3, "amt60": 0.3, "mv": 0.2, "relT": 0.2})
    add("D12|dd120+vol20+mv", {"dd120": 0.34, "vol20": 0.33, "mv": 0.33})
    add("D13|dd120+relT+amt60+mv", {"dd120": 0.3, "relT": 0.3, "amt60": 0.2, "mv": 0.2})
    add("V1|bmM+amt60(proxy)", {"bmM_proxy": 0.5, "amt60": 0.5})
    add("V2|bmP+amt60+vol20(proxy)", {"bmP_proxy": 0.4, "amt60": 0.3, "vol20": 0.3})
    add("V3|bmM+relT+amtstd(proxy)", {"bmM_proxy": 0.4, "relT": 0.3, "amtstd": 0.3})
    add("V4|bmM+dd120+amt60+mv(proxy)", {"bmM_proxy": 0.3, "dd120": 0.3, "amt60": 0.2, "mv": 0.2})

    rows = []
    for name in sorted(legs):
        st = evaluate(legs[name], schedule, forward_returns, calendar, positions, seat_frame)
        rows.append(dict(candidate=f"LEG|{name}", **st))
        print(f"leg {name:<10} s_i={st['s_i']:.4f} ic={st['rank_ic']:+.4f} icir={st['ic_ir']:+.3f} "
              f"win={st['win']:.3f} turn={st['turnover']:.3f} corrSize={st['corr_size']:+.3f}", flush=True)
    for name, weights in cands.items():
        base = None
        for leg, w in weights.items():
            if w <= 0:
                continue
            part = legs[leg] * float(w)
            base = part if base is None else base + part
        st = evaluate(base, schedule, forward_returns, calendar, positions, seat_frame)
        rows.append(dict(candidate=name, **st))
        print(f"{name:<28} s_i={st['s_i']:.4f} ic={st['rank_ic']:+.4f} icir={st['ic_ir']:+.3f} "
              f"win={st['win']:.3f} turn={st['turnover']:.3f} net={st['net_excess']:.2f}", flush=True)

    frame = pd.DataFrame(rows).sort_values("s_i", ascending=False)
    frame.to_csv(OUT / "screen.csv", index=False)
    print("\ntop 12 by s_i:")
    print(frame.head(12)[["candidate", "s_i", "rank_ic", "ic_ir", "win", "turnover",
                          "net_excess", "corr_size", "max_pool_corr"]].to_string(index=False, float_format="%.4f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
