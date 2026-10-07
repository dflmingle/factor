"""Debug: validate HistGBM export_arrays/predict_trees (2026-10-01)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "mlx", ROOT / "scripts" / "ml_combo_walkforward_export_20261001.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

rs = np.random.RandomState(0)
n = 60000
X = rs.rand(n, 5).astype("float32")
X[rs.rand(n) < 0.05, 3] = np.nan
y = (X[:, 0] + np.nan_to_num(X[:, 1]) - X[:, 2]).astype("float32")
m = HistGradientBoostingRegressor(max_iter=12, max_leaf_nodes=31,
                                  min_samples_leaf=200, random_state=7).fit(X, y)

trees = [tp for it in m._predictors for tp in it]
sizes = [len(tp.nodes) for tp in trees]
print("trees", len(trees), "sizes", sizes[:8], "total", sum(sizes))

nd = trees[0].nodes
print("leaf flags:", list(nd["is_leaf"][:12]))
print("feature_idx:", list(nd["feature_idx"][:12]))
print("left:", list(nd["left"][:12]))
print("right:", list(nd["right"][:12]))
print("n_nodes tree0:", len(nd))

pay = mod.export_arrays(m)
print("arrays len", len(pay["feat"]), "offsets head", list(pay["offsets"][:5]))
start = 0
bad = 0
for k, sz in enumerate(sizes):
    for i in range(sz):
        j = start + i
        if pay["feat"][j] >= 0:
            l_, r_ = int(pay["left"][j]), int(pay["right"][j])
            if not (start <= l_ < start + sz) or not (start <= r_ < start + sz):
                bad += 1
                if bad < 8:
                    print("BAD tree", k, "node", i, "base", start, "left", l_, "right", r_)
    start += sz
print("bad refs", bad)

got = mod.predict_trees(X[:5000], pay)
want = m.predict(X[:5000])
print("maxdiff", np.max(np.abs(got - want)))
