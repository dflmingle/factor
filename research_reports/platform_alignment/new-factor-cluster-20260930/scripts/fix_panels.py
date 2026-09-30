#!/usr/bin/env python3
"""补算 4 条候选面板（本地代理口径）：
- cand_0006/0007/0008: a046 三件套 (alpha191_046 参考实现 + turn-std ratio, make_leg 口径)
- cand_0000: VV6-1250 (1250 窗用 32% min_periods 代理)
输出与 GP 引擎面板同格式（120 signal dates × 全A股票，float32，已按日排名）。
"""
import gc, json, pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, "/data/games/factor_/scripts")
import gp_candidates_vs_clusters_20260924 as M
import alphaprobe_gp_tushare as gp

ROOT = Path("/data/games/factor_")
PA = ROOT / "research_reports/platform_alignment"
OUT = Path("/tmp/factor_cluster_20260930/overlap/panels")

panels = pickle.load((PA / "e-decomp-20260929/panels_cache.pkl").open("rb"))
print("panels loaded", {k: v.shape for k, v in panels.items() if hasattr(v, "shape")}, flush=True)

import light_cand_screen_20260929 as LCS
LCS.install_shim()
ns = {}
ref = ROOT / ".cache/third_party/alpha191_reference.py"
exec(compile(ref.read_text(encoding="utf-8"), str(ref), "exec"), ns)
fn = ns["alpha191_046"]
keys = ("close", "open", "high", "low", "volume", "amount", "vwap", "turn")
res = fn({k: panels[k] for k in keys})
base = res.rank(axis=1, pct=True)
print("alpha191_046 done", base.shape, flush=True)

turn = panels["turn"]
ratio = turn.rolling(10).std() / turn.rolling(750, min_periods=int(750 * 0.32)).std()

def a046(w, rsmooth):
    r = ratio if rsmooth == 1 else ratio.rolling(rsmooth).mean()
    leg = 1.0 - r.rank(axis=1, pct=True)
    return w * base + (1.0 - w) * leg

vol = panels["volume"]
vv61250 = -(vol.rolling(6).std() / vol.rolling(1250, min_periods=int(1250 * 0.32)).std())

sd = [pd.Timestamp(d) for d in json.loads(
    (PA / "cluster-overlap-20260924/run_meta.json").read_text(encoding="utf-8"))["signal_dates"]]

cache_root = gp.DEFAULT_CACHE_ROOT
cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root,
                            pd.Timestamp(gp.ALIGNMENT_DATA_START), pd.Timestamp(gp.ALIGNMENT_END))
stock_ids = sorted(frame["instrument"].astype(str).unique())
del frame
gc.collect()
print("engine universe:", len(stock_ids), flush=True)

todo = {
    0: vv61250,
    6: a046(0.3, 1),
    7: a046(0.3, 20),
    8: a046(0.2, 40),
}
for idx, series in todo.items():
    panel = series.reindex(index=sd, columns=stock_ids)
    ranks = M.rank_array(panel)
    np.save(OUT / f"cand_{idx:04d}.npy", ranks)
    covered = int(np.isfinite(ranks).any(axis=1).sum())
    print(f"cand_{idx:04d} ok days={covered}/{ranks.shape[0]} shape={ranks.shape} "
          f"finite_cells={int(np.isfinite(ranks).sum())}", flush=True)
print("done", flush=True)
