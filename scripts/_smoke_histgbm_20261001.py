"""Smoke test: sklearn HistGBM tree extraction semantics (2026-10-01).

Verifies: predictors structure, leaf marker, missing_go_to_left handling, and that
baseline + sum(leaf values) reproduces model.predict (learning-rate handling).
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

rs = np.random.RandomState(7)
n = 60000
X = rs.rand(n, 4).astype("float32")
mask = rs.rand(n) < 0.10
X[mask, 2] = np.nan
X[mask, 1] = np.nan
y = (2.0 * np.nan_to_num(X[:, 0], nan=0.5) - np.nan_to_num(X[:, 2], nan=0.5)
     + rs.randn(n) * 0.1).astype("float32")

model = HistGradientBoostingRegressor(
    max_iter=40, learning_rate=0.06, max_leaf_nodes=31,
    min_samples_leaf=200, l2_regularization=1.0, random_state=7,
)
model.fit(X, y)
print("n_iter_", model.n_iter_, "n_predictors", len(model._predictors))
print("pred0 type", type(model._predictors[0]), "len", len(model._predictors[0]),
      "elem", type(model._predictors[0][0]))
bp = model._baseline_prediction
print("baseline", type(bp), np.ravel(bp)[:1], getattr(bp, "dtype", None))
nodes = model._predictors[0][0].nodes
print("fields", nodes.dtype.names)
print("is_categorical any", bool(np.any(nodes["is_categorical"])))
leaves = nodes["is_leaf"].astype(bool)
print("leaf feature_idx sample", nodes["feature_idx"][leaves][:3])
print("leaf left/right sample", nodes["left"][leaves][:3], nodes["right"][leaves][:3])
print("threshold dtype", nodes["num_threshold"].dtype, "value dtype", nodes["value"].dtype)


def predict_manual(model, X, lr):
    rows = np.arange(X.shape[0])
    out = np.full(X.shape[0], float(np.ravel(model._baseline_prediction)[0]), dtype=np.float64)
    for it in model._predictors:
        for tp in it:
            nd = tp.nodes
            node = np.zeros(X.shape[0], dtype=np.int64)
            for _ in range(100):
                is_leaf = nd["is_leaf"][node].astype(bool)
                f = nd["feature_idx"][node].astype(np.int64)
                safe_f = np.where(f < 0, 0, f)
                v = X[rows, safe_f].astype(np.float64)
                v = np.where(f < 0, np.nan, v)
                nan = np.isnan(v)
                gl = np.where(nan, nd["missing_go_to_left"][node].astype(bool),
                              v <= nd["num_threshold"][node])
                nxt = np.where(gl, nd["left"][node], nd["right"][node])
                node = np.where(is_leaf, node, nxt)
                if is_leaf.all():
                    break
            out += nd["value"][node].astype(np.float64) * lr
    return out


want = model.predict(X[:8000])
for lr in (1.0, 0.06):
    got = predict_manual(model, X[:8000], lr)
    print(f"lr={lr} maxdiff={np.max(np.abs(got - want)):.3e}")
