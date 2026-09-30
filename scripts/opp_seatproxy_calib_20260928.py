#!/usr/bin/env python3
"""席位边际代理的标定（2026-09-28，本地零算力）。

目标：给 GP 找"秒算但与真实 ΔComb 同序"的适应度。
本步：对 cand_summary.csv 的 46 个已算过 ΔComb 的候选，补算它们
  rho_seat = 与现役五席逐日期 Spearman 均值（max / mean）
再检验：ΔComb ~ f(s_i, turn_intrinsic, rho) 的排序力（spearman）。

输出：e-decomp-20260928/seatproxy_calib.csv
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


def main() -> int:
    summary = pd.read_csv(OUT / "cand_summary.csv")
    specs = dict(zip(summary.name, summary.formula))
    print(f"candidates: {len(specs)}", flush=True)

    payload = pickle.load(ed.DEFAULT_REBUILD.open("rb"))
    market = ed.Market(payload, torch.device("cpu"))
    seats_raw = payload["raw"]

    rows = []
    for name, formula in specs.items():
        try:
            expr = gp.evaluate_formula(formula, market.namespace)
            with torch.no_grad():
                values = gp.finite_as_nan(expr.evaluate(market.data))
            del expr
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] EVAL FAIL {exc}"[:160], flush=True)
            continue
        spots = np.asarray(market.context.signal_data_positions, dtype=np.int64)
        panel = pd.DataFrame(values[spots].detach().cpu().numpy(), index=market.dates,
                             columns=[str(x) for x in market.data._stock_ids])
        del values
        flat = panel.stack(dropna=False).reindex(market.signal_index).rename("cand")
        corrs = {}
        for key, seat in seats_raw.items():
            df = pd.DataFrame({"cand": flat.to_numpy(), "seat": seat.to_numpy()}, index=flat.index)
            c = df.groupby(level=0).apply(
                lambda g: g.cand.corr(g.seat, method="spearman")
                if g.cand.notna().sum() > 100 else np.nan)
            corrs[key] = float(c.mean())
        rho_max = max(corrs.values())
        rho_mean = float(np.mean(list(corrs.values())))
        rows.append(dict(name=name, rho_max=rho_max, rho_mean=rho_mean,
                         rho_t10=corrs.get("t10_size_plus_impact_bm")))
        print(f"[{name}] rho_max={rho_max:+.3f} rho_mean={rho_mean:+.3f}", flush=True)
        del flat, panel

    cal = pd.DataFrame(rows).merge(summary, on="name", how="left")
    cal.to_csv(OUT / "seatproxy_calib.csv", index=False, encoding="utf-8-sig")

    from itertools import product
    base = cal.dropna(subset=["d_comb_uplift"])
    best = None
    for a, b, g in product([1, 2, 4, 8], [0, 80, 160, 320], [0, 2000, 4000, 8000]):
        x = a * 1000 * base.s_i_local - b * base.turn_intrinsic - g * base.rho_max.clip(lower=0.3)
        r = x.corr(base.d_comb_uplift, method="spearman")
        if best is None or abs(r) > abs(best[0]):
            best = (r, a, b, g)
    print("\n最佳代理 spearman=%+.3f  (a=%s, b=%s, g=%s: 1000*s_i*a - turn*b - max(rho-0.3,0)*g)"
          % best)
    print("baseline: s_i only  spearman=%+.3f" % base.s_i_local.corr(base.d_comb_uplift, method="spearman"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
