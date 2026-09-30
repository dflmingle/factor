#!/usr/bin/env python3
"""VV6 第六席评估（2026-09-28，零平台算力）。

候选 = 量波动稳定性腿（volV 家族）：Inv(STD(VOLUME,k)/STD(VOLUME,base))。
本地受 max_backtrack_days=756 限制，基准窗口用 500（2y）/750（3y）代理平台 1250（5y）。
输出：
  opp-halfcenter-20260928/vv6_seat_corr.csv   —— 与五席的逐日期 Spearman 均值
  e-decomp-20260928/cand_summary.csv（追加）  —— ΔE/ΔT/ΔNC/ΔC/ΔComb
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import e_decomp_20260928 as ed  # noqa: E402
import alphaprobe_gp_tushare as gp  # noqa: E402

OUT = ed.DEFAULT_OUT
CORR_OUT = ROOT / "research_reports/platform_alignment/opp-halfcenter-20260928"

SPECS = {
    "VV6_500": "Inv(Div(TsStd(volume,6),TsStd(volume,500)))",
    "VV6_750": "Inv(Div(TsStd(volume,6),TsStd(volume,750)))",
    "VV6_MIX500": (
        "Add(Mul(0.6,Rank(Inv(Div(TsStd(volume,6),TsStd(volume,500))))),"
        "Mul(0.4,Rank(Inv(Div(TsMean(turnover,5),TsMean(turnover,500))))))"
    ),
}


def main() -> int:
    payload = pickle.load(ed.DEFAULT_REBUILD.open("rb"))
    market = ed.Market(payload, torch.device("cpu"))
    seats_raw = payload["raw"]

    rows = []
    for name, formula in SPECS.items():
        expr = gp.evaluate_formula(formula, market.namespace)
        with torch.no_grad():
            values = gp.finite_as_nan(expr.evaluate(market.data))
        del expr
        spots = np.asarray(market.context.signal_data_positions, dtype=np.int64)
        panel = pd.DataFrame(values[spots].detach().cpu().numpy(), index=market.dates,
                             columns=[str(x) for x in market.data._stock_ids])
        del values
        flat = panel.stack(dropna=False).reindex(market.signal_index).rename("cand")
        finite = float(np.isfinite(panel.to_numpy()).mean())
        print(f"[{name}] finite_share={finite:.4f}", flush=True)
        for key, seat in seats_raw.items():
            df = pd.DataFrame({"cand": flat.to_numpy(), "seat": seat.to_numpy()},
                              index=flat.index)
            corr = df.groupby(level=0).apply(
                lambda g: g.cand.corr(g.seat, method="spearman")
                if g.cand.notna().sum() > 100 else np.nan)
            rows.append(dict(cand=name, seat=key, corr=float(corr.mean()), finite_share=finite))
            print(f"  [{name}] vs {key:<32} rho={corr.mean():+.4f}", flush=True)
        del flat, panel

    corr_df = pd.DataFrame(rows)
    corr_df.to_csv(CORR_OUT / "vv6_seat_corr.csv", index=False, encoding="utf-8-sig")
    print(corr_df.pivot(index="cand", columns="seat", values="corr").to_string())

    ed.candidates_mode(market, OUT, SPECS, False)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
