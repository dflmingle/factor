#!/usr/bin/env python3
"""平滑探测（2026-09-29）：对腿与复合候选测 MA2/3/5 平滑的 s_i / turn10 改进。

背景：低换手约束（LEGMIX7 57% 换手 → C 段代价）与高 ICIR 腿（volstab 等，turn .66+）冲突。
平滑（MA on ranks）平台可表达：MA((RANK(l1)+RANK(l2)+...)/K, n)，或外面再套 RANK。
本脚本量化：每腿按 s_i 的平滑增益（Δs_i / Δturn10）；每个 mining 复合候选的三种变体。
输出 smooth_probe_legs.csv / smooth_probe_comp.csv（零平台算力）。
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legmix_next_legs_20260929 import build_raw_legs  # noqa: E402
from legmix_next_mine_20260929 import ic_series, stats, turnover_top, sched_of, W5, CYCLE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_reports/platform_alignment/legmix-next-20260929"
PANELS = ROOT / "research_reports/platform_alignment/e-decomp-20260929/panels_cache.pkl"
T0 = time.time()
KS = (2, 3, 5)


def log(m):
    print(f"[{time.time()-T0:7.1f}s] {m}", flush=True)


def main() -> int:
    panels = pickle.load(PANELS.open("rb"))
    C = panels["close"]
    cal = C.index
    idx = {d: i for i, d in enumerate(cal)}
    w5s = sched_of(cal, W5)
    raw = build_raw_legs(panels)
    log(f"raw legs {len(raw)}")

    # 1) 腿级平滑
    leg_rows = []
    legs_ranked = {}
    for name, df in raw.items():
        r0 = df.rank(axis=1, pct=True).astype("float32")
        s5a = ic_series(r0, C, cal, w5s, idx)
        if np.isfinite(s5a).any() and np.nanmean(s5a) < 0:
            r0 = -r0
            base = stats(-s5a)
        else:
            base = stats(s5a)
        legs_ranked[name] = r0
        t0 = turnover_top(r0, w5s, idx)
        leg_rows.append(dict(leg=name, k=0, s_i=base["s_i"], icir=base["icir"], ic=base["ic"],
                             win=base["win"], turn10=t0))
        for k in KS:
            rs = r0.rolling(k).mean().astype("float32")
            st = stats(ic_series(rs, C, cal, w5s, idx))
            tt = turnover_top(rs, w5s, idx)
            leg_rows.append(dict(leg=name, k=k, s_i=st["s_i"], icir=st["icir"], ic=st["ic"],
                                 win=st["win"], turn10=tt))
        del r0
        gc.collect()
    legs_df = pd.DataFrame(leg_rows)
    legs_df.to_csv(OUT / "smooth_probe_legs.csv", index=False, encoding="utf-8-sig")
    piv = legs_df.pivot(index="leg", columns="k", values="s_i")
    pivt = legs_df.pivot(index="leg", columns="k", values="turn10")
    base = piv.iloc[:, 0]
    show = piv.copy(); show.columns = [f"s_i_{c}" for c in show.columns]
    t = pivt.copy(); t.columns = [f"turn_{c}" for c in t.columns]
    show = show.join(t)
    show.insert(0, "k0", [c for c in piv.columns][0] if False else 0)
    show = show[base >= 0.010].sort_values("s_i_0", ascending=False)
    show = show.drop(columns=["k0"])
    log("legs smoothing probe done")
    print(show.round(4).to_string())

    # 2) 复合候选平滑
    comp_rows = []
    for path in sorted(OUT.glob("*_specs.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in data["steps"]:
            if step["k"] < 4:
                continue
            legs = step.get("signed") or {n: 1.0 for n in step["legs"]}
            comp = None
            for name, sign in legs.items():
                v = legs_ranked[name] * float(sign)
                comp = v if comp is None else comp + v
            comp = (comp / len(legs)).astype("float32")
            name = f"{data['tag']}K{step['k']}"
            st0 = stats(ic_series(comp, C, cal, w5s, idx))
            comp_rows.append(dict(name=name, variant="raw", s_i=st0["s_i"], icir=st0["icir"],
                                  win=st0["win"], ic=st0["ic"], turn10=turnover_top(comp, w5s, idx)))
            for k in KS:
                cs = comp.rolling(k).mean().astype("float32")
                st = stats(ic_series(cs, C, cal, w5s, idx))
                comp_rows.append(dict(name=name, variant=f"ma{k}", s_i=st["s_i"], icir=st["icir"],
                                      win=st["win"], ic=st["ic"], turn10=turnover_top(cs, w5s, idx)))
                csr = cs.rank(axis=1, pct=True).astype("float32")
                st2 = stats(ic_series(csr, C, cal, w5s, idx))
                comp_rows.append(dict(name=name, variant=f"ma{k}_rerank", s_i=st2["s_i"], icir=st2["icir"],
                                      win=st2["win"], ic=st2["ic"], turn10=turnover_top(csr, w5s, idx)))
                del cs, csr
            del comp
            gc.collect()
    comp_df = pd.DataFrame(comp_rows)
    comp_df.to_csv(OUT / "smooth_probe_comp.csv", index=False, encoding="utf-8-sig")
    log("composites smoothing probe done")
    best = comp_df.sort_values("s_i", ascending=False).head(30)
    print(best.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
