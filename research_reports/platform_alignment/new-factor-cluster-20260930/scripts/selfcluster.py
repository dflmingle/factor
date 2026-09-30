#!/usr/bin/env python3
"""New-factor self-clustering on the same signal-date rank panels (0.80 cut)."""
import itertools, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, "/data/games/factor_/scripts")
import gp_candidates_vs_clusters_20260924 as M

OUT = Path("/tmp/factor_cluster_20260930/overlap")
panels_dir = OUT / "panels"
cands = pd.read_csv("/tmp/factor_cluster_20260930/nf_candidates.csv")
labels = cands["band"].tolist()
n = len(labels)
cand = {i: np.load(panels_dir / f"cand_{i:04d}.npy") for i in range(n)}
present = sorted(cand)
print("panels present:", [labels[i] for i in present], flush=True)

rho = np.full((n, n), np.nan)
for i, j in itertools.combinations(present, 2):
    a, b = cand[i], cand[j]
    total = 2
    corr_sum = np.zeros((total, total)); corr_cnt = np.zeros((total, total))
    for day in range(a.shape[0]):
        rows = np.stack([a[day], b[day]])
        M.accumulate(corr_sum, corr_cnt, rows)
    with np.errstate(invalid="ignore", divide="ignore"):
        fast = (corr_sum / np.where(corr_cnt > 0, corr_cnt, np.nan))[0, 1]
    if np.isfinite(fast) and abs(fast) >= M.EXACT_FLOOR:
        exact = M.exact_pair_corr(a, b)
        rho[i, j] = rho[j, i] = exact if np.isfinite(exact) else fast
    else:
        rho[i, j] = rho[j, i] = fast
np.fill_diagonal(rho, 1.0)

# connected components at 0.80
edges = [(i, j, abs(rho[i, j])) for i, j in itertools.combinations(present, 2)
         if np.isfinite(rho[i, j]) and abs(rho[i, j]) >= M.THRESHOLD]
parent = list(range(n))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
for i, j, _ in edges:
    parent[find(i)] = find(j)
comp = {}
for i in present:
    comp.setdefault(find(i), []).append(i)
print("\n=== clusters at |rho|>=0.80 among new factors ===", flush=True)
for root, idxs in comp.items():
    names = [labels[i] for i in idxs]
    print("cluster:", names, flush=True)
print("\n=== pairwise |rho| >= 0.60 ===", flush=True)
for i, j in itertools.combinations(present, 2):
    v = rho[i, j]
    if np.isfinite(v) and abs(v) >= M.EXACT_FLOOR:
        print(f"  {labels[i]:28s} {labels[j]:28s} rho={v:+.3f}", flush=True)
pd.DataFrame(rho, index=labels, columns=labels).to_csv(OUT / "newfactor_self_corr.csv", encoding="utf-8")
print("\nwrote newfactor_self_corr.csv", flush=True)
